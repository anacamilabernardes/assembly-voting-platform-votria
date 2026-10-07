import json, secrets
from django.conf import settings
from django.contrib.auth import login,logout
from django.http import JsonResponse,HttpResponseRedirect
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.utils.crypto import constant_time_compare
from django.views.decorators.csrf import ensure_csrf_cookie,csrf_protect
from django.views.decorators.http import require_POST,require_GET
from authlib.integrations.django_client import OAuth
from authlib.integrations.base_client.errors import OAuthError
from .models import Member,Assembly
from .domain import institutional_email,RuleError
from .services import command,check_out
oauth=OAuth()
if settings.OIDC_ISSUER:
    if not settings.OIDC_ISSUER.startswith('https://'):
        raise ValueError('OIDC_ISSUER deve usar HTTPS.')
    oauth.register('mensa',client_id=settings.OIDC_CLIENT_ID,client_secret=settings.OIDC_CLIENT_SECRET,server_metadata_url=settings.OIDC_ISSUER.rstrip('/')+'/.well-known/openid-configuration',client_kwargs={'scope':'openid email profile','code_challenge_method':'S256'},requests_kwargs={'timeout':10})
def demo_available(request):
    return settings.DEMO_MODE and (bool(settings.DEMO_ACCESS_PASSWORD) or (settings.DEBUG and request.META.get('REMOTE_ADDR') in ('127.0.0.1','::1')))
@ensure_csrf_cookie
@require_GET
def bootstrap(request):
    demo=demo_available(request)
    return JsonResponse({'demo':demo,'demo_password_required':bool(settings.DEMO_ACCESS_PASSWORD),'official_ready':False,'oidc_configured':bool(settings.OIDC_ISSUER and settings.OIDC_CLIENT_ID),'demo_accounts':[{'id':str(m.id),'name':m.full_name,'email':m.email} for m in Member.objects.filter(issuer='demo:local')] if demo else []})
def leave_current_session(request):
    if request.user.is_authenticated and hasattr(request.user,'member'):
        actor=request.user.member
        for a in Assembly.objects.filter(is_demo=True,electors__member=actor):
            command(a.id,actor,'logout',{},secrets.token_hex(16),lambda assembly,now:check_out(assembly,actor,request.session.session_key,now))
@csrf_protect
@require_POST
def demo_login(request):
    if not demo_available(request):
        return JsonResponse({'code':'DEMO_DISABLED','detail':'Login de simulação indisponível.'},status=403)
    try:
        body=json.loads(request.body)
        if not isinstance(body, dict):
            raise ValueError('Corpo inválido')
        if settings.DEMO_ACCESS_PASSWORD and not (request.user.is_authenticated and request.session.get('demo_access_granted')):
            # This limiter is deliberately local to the single demo worker.
            limit_key='demo-login:' + request.META.get('REMOTE_ADDR', 'unknown')
            failures=cache.get(limit_key, 0)
            if failures >= 10:
                return JsonResponse({'code':'RATE_LIMIT','detail':'Aguarde cinco minutos antes de tentar novamente.'},status=429)
            password=body.get('access_password', '')
            if not isinstance(password, str) or not constant_time_compare(password, settings.DEMO_ACCESS_PASSWORD):
                cache.set(limit_key, failures + 1, timeout=300)
                return JsonResponse({'code':'DEMO_ACCESS_DENIED','detail':'Senha de acesso ao simulado inválida.'},status=403)
            cache.delete(limit_key)
        m=Member.objects.get(pk=body['member_id'],issuer='demo:local',user__is_active=True)
        institutional_email(m.email)
    except (ValueError,KeyError,ValidationError,Member.DoesNotExist,RuleError):
        return JsonResponse({'code':'INVALID_ACCOUNT','detail':'Conta de simulação inválida.'},status=400)
    leave_current_session(request)
    login(request,m.user,backend='django.contrib.auth.backends.ModelBackend')
    request.session['authentication_kind']='DEMO'
    request.session['demo_access_granted']=True
    return JsonResponse({'id':str(m.id),'name':m.full_name})
@csrf_protect
@require_POST
def sign_out(request):
    leave_current_session(request)
    logout(request)
    return JsonResponse({'signed_out':True})
@require_GET
def oidc_login(request):
    if not settings.OIDC_ISSUER or not settings.OIDC_REDIRECT_URI:
        return JsonResponse({'code':'OIDC_NOT_CONFIGURED','detail':'O login institucional ainda não foi conectado.'},status=503)
    return oauth.mensa.authorize_redirect(request,settings.OIDC_REDIRECT_URI,nonce=secrets.token_urlsafe(32),acr_values=settings.OIDC_REQUIRED_ACR)
@require_GET
def oidc_callback(request):
    if not settings.OIDC_ISSUER:
        return JsonResponse({'code':'OIDC_NOT_CONFIGURED'},status=503)
    try:
        token=oauth.mensa.authorize_access_token(request)
        # Userinfo aqui é o ID token validado pela Authlib, não um corpo enviado pelo cliente.
        claims=token.get('userinfo')
        if not claims or claims.get('iss')!=settings.OIDC_ISSUER or claims.get('email_verified') is not True or claims.get('acr')!=settings.OIDC_REQUIRED_ACR:
            raise RuleError('MFA_REQUIRED','Identidade verificada e nível MFA institucional são obrigatórios.',403)
        email=institutional_email(claims.get('email',''))
        m=Member.objects.get(email=email)
        if not m.issuer or not m.subject or m.issuer!=claims['iss'] or m.subject!=claims['sub'] or not m.user.is_active:
            raise RuleError('IDENTITY_NOT_LINKED','Vínculo institucional não autorizado.',403)
        login(request,m.user,backend='django.contrib.auth.backends.ModelBackend')
        request.session['authentication_kind']='OIDC_MFA'
        return HttpResponseRedirect('/')
    except (OAuthError,RuleError,Member.DoesNotExist,KeyError,ValueError):
        return JsonResponse({'code':'IDENTITY_REJECTED','detail':'Não foi possível validar o login institucional.'},status=403)
