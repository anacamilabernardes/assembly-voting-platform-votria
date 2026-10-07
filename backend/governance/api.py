import json
from datetime import timedelta
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db import IntegrityError,OperationalError
from django.http import JsonResponse
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView,exception_handler as default_handler
from . import services as s
from .domain import RuleError
from .models import Assembly,Member,MailboxMessage,ClaimFailure
def exception_handler(exc,context):
    if isinstance(exc,RuleError):
        return Response({'code':exc.code,'detail':exc.detail},status=exc.status)
    if isinstance(exc,ObjectDoesNotExist):
        return Response({'code':'NOT_FOUND','detail':'Recurso não encontrado.'},status=404)
    if isinstance(exc,IntegrityError):
        return Response({'code':'CONFLICT','detail':'A operação conflita com um registro confirmado.'},status=409)
    if isinstance(exc,OperationalError):
        return Response({'code':'TEMPORARILY_UNAVAILABLE','detail':'Tente novamente com a mesma chave de confirmação.','retryable':True},status=503)
    return default_handler(exc,context)
def liveness(request):
    return JsonResponse({'status':'ok','official_ready':False})
def parse(request,fields):
    if not isinstance(request.data,dict) or set(request.data)-set(fields):
        raise ValidationError('Campos desconhecidos ou corpo inválido.')
    schema=type('Input',(serializers.Serializer,),fields)
    serializer=schema(data=request.data); serializer.is_valid(raise_exception=True)
    return json.loads(json.dumps(serializer.validated_data,default=str))
class BaseView(APIView):
    def actor(self,request):
        try:
            m=request.user.member
        except (AttributeError,ObjectDoesNotExist):
            raise RuleError('IDENTITY_NOT_LINKED','Conta sem vínculo associativo.',403)
        return m
    def execute(self,request,assembly_id,action,payload,operation):
        actor=self.actor(request)
        return Response(s.command(assembly_id,actor,action,payload,request.headers.get('Idempotency-Key'),lambda a,now:operation(a,actor,now)))
class MeView(BaseView):
    def get(self,request):
        m=self.actor(request)
        return Response({'id':str(m.id),'name':m.full_name,'email':m.email,'mb':m.mb_number,'authentication_kind':request.session.get('authentication_kind','UNKNOWN')})
class AssemblyListView(BaseView):
    def get(self,request):
        return Response(list(Assembly.objects.filter(electors__member=self.actor(request)).values('id','title','code','state','is_demo')))
class StateView(BaseView):
    def get(self,request,assembly_id):
        return Response(s.state(assembly_id,self.actor(request),request.session.session_key))
class PresenceView(BaseView):
    def post(self,request,assembly_id,action):
        if action=='check-in':
            p=parse(request,{'confirmed':serializers.BooleanField()})
            return self.execute(request,assembly_id,'presence.check-in',p,lambda a,m,t:s.check_in(a,m,request.session.session_key,p['confirmed'],t))
        if action=='heartbeat':
            p=parse(request,{'session_id':serializers.UUIDField()})
            return self.execute(request,assembly_id,'presence.heartbeat',p,lambda a,m,t:s.heartbeat(a,m,request.session.session_key,p['session_id'],t))
        if action=='check-out':
            p=parse(request,{})
            return self.execute(request,assembly_id,'presence.check-out',p,lambda a,m,t:s.check_out(a,m,request.session.session_key,t))
        raise RuleError('NOT_FOUND','Operação desconhecida.',404)
class ProxyView(BaseView):
    def post(self,request,assembly_id):
        p=parse(request,{'representative_id':serializers.UUIDField(),'scope':serializers.ListField(child=serializers.UUIDField(),min_length=1,max_length=100),'confirmed':serializers.BooleanField()})
        return self.execute(request,assembly_id,'proxy.issue',p,lambda a,m,t:s.issue_proxy(a,m,p['representative_id'],p['scope'],p['confirmed'],t))
class ProxyClaimView(BaseView):
    def post(self,request,assembly_id):
        p=parse(request,{'code':serializers.CharField(max_length=100,trim_whitespace=True)})
        m=self.actor(request)
        if ClaimFailure.objects.filter(member=m,occurred_at__gt=timezone.now()-timedelta(minutes=15)).count()>=5:
            raise RuleError('RATE_LIMIT','Aguarde 15 minutos antes de tentar resgatar outro código.',429)
        try:
            return self.execute(request,assembly_id,'proxy.claim',p,lambda a,m,t:s.claim_proxy(a,m,p['code'],t))
        except RuleError as exc:
            if exc.code=='INVALID_PROXY_CODE':
                ClaimFailure.objects.create(member=m,occurred_at=timezone.now())
            raise
class ProxyRevokeView(BaseView):
    def post(self,request,assembly_id,proxy_id):
        p=parse(request,{})
        return self.execute(request,assembly_id,'proxy.revoke:'+str(proxy_id),p,lambda a,m,t:s.revoke_proxy(a,m,proxy_id,t))
class InstallView(BaseView):
    def post(self,request,assembly_id):
        p=parse(request,{'call':serializers.IntegerField(min_value=1,max_value=2)})
        return self.execute(request,assembly_id,'assembly.install',p,lambda a,m,t:s.install(a,m,p['call'],t))
class OpenView(BaseView):
    def post(self,request,assembly_id,item_id):
        p=parse(request,{'duration_seconds':serializers.IntegerField(min_value=120,max_value=1800)})
        return self.execute(request,assembly_id,'round.open:'+str(item_id),p,lambda a,m,t:s.open_round(a,m,item_id,p['duration_seconds'],t))
class BallotView(BaseView):
    def post(self,request,assembly_id,round_id):
        p=parse(request,{'owner_id':serializers.UUIDField(),'choice':serializers.ChoiceField(choices=['YES','NO','ABSTAIN']),'proposal_hash':serializers.CharField(min_length=64,max_length=64)})
        return self.execute(request,assembly_id,'ballot:'+str(round_id),p,lambda a,m,t:s.cast_ballot(a,m,round_id,p['owner_id'],p['choice'],p['proposal_hash'],t))
class CloseRoundView(BaseView):
    def post(self,request,assembly_id,round_id):
        p=parse(request,{})
        return self.execute(request,assembly_id,'round.close:'+str(round_id),p,lambda a,m,t:s.close_round(a,m,round_id,t))
class FloorView(BaseView):
    def post(self,request,assembly_id):
        p=parse(request,{'kind':serializers.ChoiceField(choices=['NORMAL','ORDER'])})
        return self.execute(request,assembly_id,'floor.request',p,lambda a,m,t:s.raise_hand(a,m,p['kind'],t))
class FloorDecisionView(BaseView):
    def post(self,request,assembly_id,floor_id):
        p=parse(request,{'decision':serializers.ChoiceField(choices=['GRANT','DENY','END','WITHDRAW']),'reason':serializers.CharField(max_length=500,required=False,allow_blank=True,default='')})
        return self.execute(request,assembly_id,'floor.decision:'+str(floor_id),p,lambda a,m,t:s.floor_decision(a,m,floor_id,p['decision'],p['reason'],t))
class CloseAssemblyView(BaseView):
    def post(self,request,assembly_id):
        p=parse(request,{})
        return self.execute(request,assembly_id,'assembly.close',p,lambda a,m,t:s.close_assembly(a,m,t))
class MinutesView(BaseView):
    def get(self,request,assembly_id):
        m=self.actor(request)
        a=Assembly.objects.get(pk=assembly_id,electors__member=m)
        s.ensure_demo(a)
        return Response(s.minutes(a))
class InboxView(BaseView):
    def get(self,request):
        if not settings.DEMO_MODE or request.session.get('authentication_kind') != 'DEMO':
            raise RuleError('DEMO_DISABLED','Caixa de teste indisponível.',403)
        m=self.actor(request)
        rows=MailboxMessage.objects.filter(recipient=m,expires_at__gt=timezone.now()).order_by('-created_at')
        return Response([{'id':str(r.id),'subject':r.subject,'code':s.mailbox_cipher().decrypt(r.ciphertext.encode()).decode(),'notice':'Caixa local fictícia: o código está disponível apenas ao outorgante.'} for r in rows])
