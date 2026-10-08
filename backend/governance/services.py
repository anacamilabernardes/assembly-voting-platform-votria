import base64, hashlib, secrets, uuid
from datetime import timedelta
from cryptography.fernet import Fernet
from django.conf import settings
from django.db import connection, transaction
from django.utils import timezone
from .domain import RuleError, digest, token_hash, ordinary_result, quorum_required
from .models import *

def server_time():
    if connection.vendor == 'postgresql':
        with connection.cursor() as cursor:
            cursor.execute('SELECT clock_timestamp()')
            return cursor.fetchone()[0]
    return timezone.now()

def mailbox_cipher():
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(('demo-mailbox:'+settings.SECRET_KEY).encode()).digest()))

def audit(a,actor,action,payload,now):
    last = a.events.order_by('-sequence').first()
    previous = last.event_hash if last else ''
    seq = last.sequence+1 if last else 1
    envelope = {'assembly':str(a.id),'actor':str(actor.id) if actor else None,'sequence':seq,'action':action,'payload':payload,'occurred_at':now.isoformat(),'previous_hash':previous,'schema':'mensa-json-v1'}
    return AuditEvent.objects.create(assembly=a,actor=actor,sequence=seq,action=action,payload=payload,occurred_at=now,previous_hash=previous,event_hash=digest(envelope))

def elector(a,member):
    record = Elector.objects.filter(assembly=a,member=member).first()
    if not record:
        raise RuleError('NOT_ELIGIBLE','Você não pertence ao colégio desta assembleia.',403)
    return record

def regular(a,member):
    record = elector(a,member)
    if not record.is_regular or not record.can_vote:
        raise RuleError('NOT_ELIGIBLE','Associado sem direito de voto neste snapshot.',403)
    return record

def require_president(a,actor):
    if a.president_id != actor.id:
        raise RuleError('ROLE_REQUIRED','Esta ação é reservada ao presidente da assembleia.',403)

def present_ids(a,now):
    return set(ParticipationSession.objects.filter(assembly=a,ended_at__isnull=True,lease_until__gt=now).values_list('member_id',flat=True))

def expire_presence(a,now):
    expired = ParticipationSession.objects.filter(assembly=a,ended_at__isnull=True,lease_until__lte=now)
    affected = list(expired.values_list('member_id',flat=True).distinct())
    for session in expired:
        session.ended_at = session.lease_until
        session.end_reason = 'TIMEOUT'
        session.save(update_fields=['ended_at','end_reason'])
        audit(a,None,'presence.timeout',{'member_id':str(session.member_id),'session_id':str(session.id),'effective_at':session.ended_at.isoformat()},now)
    for member_id in affected:
        if not ParticipationSession.objects.filter(assembly=a,member_id=member_id,ended_at__isnull=True,lease_until__gt=now).exists():
            last_end = ParticipationSession.objects.filter(assembly=a,member_id=member_id).order_by('-ended_at').first().ended_at
            PresenceInterval.objects.filter(assembly=a,member_id=member_id,exited_at__isnull=True).update(exited_at=last_end,reason='TIMEOUT')

def proxy_condition(p,live):
    if p.status != 'ACCEPTED':
        return p.status
    if p.grantor_id in live:
        return 'SUSPENDED_GRANTOR_PRESENT'
    if p.representative_id not in live:
        return 'REPRESENTATIVE_ABSENT'
    return 'AVAILABLE'

def active_owners(a,now,item=None):
    live = present_ids(a,now)
    qualified = set(a.electors.filter(is_regular=True,can_vote=True).values_list('member_id',flat=True))
    owners = live & qualified
    proxies = Proxy.objects.filter(assembly=a,status='ACCEPTED')
    if item:
        proxies = proxies.filter(scope=item)
    for p in proxies:
        if p.grantor_id in qualified and p.representative_id in qualified and proxy_condition(p,live)=='AVAILABLE':
            owners.add(p.grantor_id)
    return owners

def authorized_population(r,end):
    qualified = set(r.assembly.electors.filter(is_regular=True,can_vote=True).values_list('member_id',flat=True))
    population = set()
    sessions = list(ParticipationSession.objects.filter(assembly=r.assembly,entered_at__lt=end))
    def overlaps(session,start,finish):
        effective_end = session.ended_at or session.lease_until
        return max(session.entered_at,start)<min(effective_end,finish)
    for s in sessions:
        if s.member_id in qualified and overlaps(s,r.opened_at,end):
            population.add(s.member_id)
    for p in Proxy.objects.filter(assembly=r.assembly,scope=r.agenda_item,accepted_at__isnull=False):
        if p.grantor_id in population or p.grantor_id not in qualified or p.representative_id not in qualified:
            continue
        start = max(r.opened_at,p.accepted_at)
        finish = min(end,p.revoked_at or end)
        if any(s.member_id==p.representative_id and overlaps(s,start,finish) for s in sessions):
            population.add(p.grantor_id)
    return population | set(r.ballots.values_list('owner_id',flat=True))

def finish_round(a,r,actor,now):
    result = ordinary_result(list(r.ballots.values_list('choice',flat=True)))
    population = authorized_population(r,min(now,r.closes_at))
    result.update({'authorized_during_window':len(population),'not_voted':len(population)-r.ballots.count(),'active_at_close':len(active_owners(a,now,r.agenda_item)),'proposal_hash':r.proposal_hash})
    r.state='CLOSED'; r.closed_at=now; r.result=result
    r.save(update_fields=['state','closed_at','result'])
    audit(a,actor,'round.closed',{'round_id':str(r.id),'result':result},now)

def ensure_demo(a):
    if not settings.DEMO_MODE or not a.is_demo:
        raise RuleError('OFFICIAL_NOT_READY','Assembleias oficiais estão bloqueadas neste incremento. Assinaturas fortes e homologação ainda estão pendentes.',403)

@transaction.atomic
def command(assembly_id,actor,action,payload,key,operation):
    if not key or len(key)>100:
        raise RuleError('IDEMPOTENCY_REQUIRED','Informe uma chave de idempotência válida.',422)
    a = Assembly.objects.select_for_update().get(pk=assembly_id)
    ensure_demo(a); elector(a,actor)
    hashed = digest(payload)
    prior = CommandReceipt.objects.filter(assembly=a,actor=actor,action=action,key=key).first()
    if prior:
        if prior.request_hash!=hashed:
            raise RuleError('IDEMPOTENCY_CONFLICT','Esta chave já foi usada com outro conteúdo.')
        return prior.response
    now=server_time()
    expire_presence(a,now)
    for r in Round.objects.filter(assembly=a,state='OPEN',closes_at__lte=now):
        finish_round(a,r,None,now)
    response=operation(a,now)
    CommandReceipt.objects.create(assembly=a,actor=actor,action=action,key=key,request_hash=hashed,response=response)
    return response

def check_in(a,actor,session_key,confirmed,now):
    if a.state=='CLOSED':
        raise RuleError('ASSEMBLY_CLOSED','A assembleia já foi encerrada.')
    if confirmed is not True:
        raise RuleError('PRESENCE_CONFIRMATION_REQUIRED','Confirme a declaração de presença.',422)
    existing=ParticipationSession.objects.filter(assembly=a,member=actor,auth_session_key=session_key,ended_at__isnull=True).first()
    if existing:
        return {'session_id':str(existing.id),'protocol':existing.protocol}
    declaration={'assembly_id':str(a.id),'member_id':str(actor.id),'name':elector(a,actor).name,'time':now.isoformat(),'kind':'DEMO_CONFIRMATION'}
    session=ParticipationSession.objects.create(assembly=a,member=actor,auth_session_key=session_key,entered_at=now,last_seen_at=now,lease_until=now+timedelta(seconds=60),declaration_hash=digest(declaration),protocol='PRES-'+uuid.uuid4().hex)
    PresenceInterval.objects.get_or_create(assembly=a,member=actor,exited_at=None,defaults={'entered_at':now})
    audit(a,actor,'presence.checked_in',{'session_id':str(session.id),'declaration_hash':session.declaration_hash,'proof_kind':'DEMO_CONFIRMATION'},now)
    return {'session_id':str(session.id),'protocol':session.protocol}

def heartbeat(a,actor,session_key,session_id,now):
    s=ParticipationSession.objects.filter(pk=session_id,assembly=a,member=actor,auth_session_key=session_key,ended_at__isnull=True).first()
    if not s:
        raise RuleError('PRESENCE_EXPIRED','Registre sua presença novamente.')
    s.last_seen_at=now; s.lease_until=now+timedelta(seconds=60)
    s.save(update_fields=['last_seen_at','lease_until'])
    return {'lease_until':s.lease_until.isoformat()}

def check_out(a,actor,session_key,now):
    sessions=ParticipationSession.objects.filter(assembly=a,member=actor,auth_session_key=session_key,ended_at__isnull=True)
    ids=list(sessions.values_list('id',flat=True))
    sessions.update(ended_at=now,end_reason='EXPLICIT')
    if not ParticipationSession.objects.filter(assembly=a,member=actor,ended_at__isnull=True,lease_until__gt=now).exists():
        PresenceInterval.objects.filter(assembly=a,member=actor,exited_at__isnull=True).update(exited_at=now,reason='EXPLICIT')
    if ids:
        audit(a,actor,'presence.checked_out',{'sessions':[str(s) for s in ids]},now)
    return {'present':actor.id in present_ids(a,now)}

def issue_proxy(a,actor,representative_id,scope_ids,confirmed,now):
    regular(a,actor)
    if a.installed_at:
        raise RuleError('PROXY_WINDOW_CLOSED','Procurações devem ser aceitas antes da instalação.')
    if confirmed is not True:
        raise RuleError('CONFIRMATION_REQUIRED','Confirme os poderes e o representante.',422)
    representative=Member.objects.get(pk=representative_id); regular(a,representative)
    if actor.id==representative.id:
        raise RuleError('SELF_PROXY','Não é possível outorgar a si próprio.',422)
    Proxy.objects.filter(assembly=a,status='ISSUED',token_expires_at__lte=now).update(status='EXPIRED')
    if Proxy.objects.filter(assembly=a,grantor=actor,status__in=['ISSUED','ACCEPTED']).exists():
        raise RuleError('PROXY_EXISTS','Revogue sua procuração anterior antes de emitir outra.')
    scopes=list(a.agenda.filter(id__in=scope_ids))
    if not scopes or len(scopes)!=len(set(scope_ids)):
        raise RuleError('OUT_OF_SCOPE','Selecione pautas válidas desta assembleia.',422)
    edges=dict(Proxy.objects.filter(assembly=a,status__in=['ISSUED','ACCEPTED']).values_list('grantor_id','representative_id'))
    cursor=representative.id; seen=set()
    while cursor in edges:
        if cursor in seen or cursor==actor.id:
            raise RuleError('PROXY_CYCLE','Esta procuração criaria um ciclo de representação.',422)
        seen.add(cursor); cursor=edges[cursor]
    if cursor==actor.id:
        raise RuleError('PROXY_CYCLE','Esta procuração criaria um ciclo de representação.',422)
    token=secrets.token_urlsafe(24)
    instrument={'assembly_id':str(a.id),'grantor':str(actor.id),'representative':str(representative.id),'grantor_name':elector(a,actor).name,'representative_name':elector(a,representative).name,'scope':[str(i.id) for i in scopes],'issued_at':now.isoformat(),'powers':'Representar e votar exclusivamente nas pautas selecionadas, sem substabelecimento.','proof_kind':'DEMO_CONFIRMATION'}
    p=Proxy.objects.create(assembly=a,grantor=actor,representative=representative,token_hmac=token_hash(token,settings.SECRET_KEY),token_expires_at=now+timedelta(hours=48),issued_at=now,instrument=instrument,instrument_hash=digest(instrument))
    p.scope.set(scopes)
    MailboxMessage.objects.create(recipient=actor,assembly=a,subject='Código da sua procuração',ciphertext=mailbox_cipher().encrypt(token.encode()).decode(),created_at=now,expires_at=now+timedelta(hours=24))
    audit(a,actor,'proxy.issued',{'proxy_id':str(p.id),'instrument_hash':p.instrument_hash},now)
    return {'proxy_id':str(p.id),'delivery':'DEMO_MAILBOX','instrument_hash':p.instrument_hash}

def claim_proxy(a,actor,code,now):
    regular(a,actor)
    if a.installed_at:
        raise RuleError('PROXY_WINDOW_CLOSED','A janela de aceitação foi encerrada.')
    p=Proxy.objects.filter(assembly=a,token_hmac=token_hash(code,settings.SECRET_KEY),representative=actor,status='ISSUED',token_expires_at__gt=now).first()
    if not p:
        raise RuleError('INVALID_PROXY_CODE','Código inválido, expirado ou indisponível.')
    regular(a,p.grantor)
    used=set(Proxy.objects.filter(assembly=a,representative=actor,status='ACCEPTED').values_list('slot',flat=True))
    free=[slot for slot in (1,2) if slot not in used]
    if not free:
        raise RuleError('PROXY_LIMIT','Você já possui duas procurações aceitas.')
    p.status='ACCEPTED'; p.slot=free[0]; p.accepted_at=now
    p.save(update_fields=['status','slot','accepted_at'])
    audit(a,actor,'proxy.accepted',{'proxy_id':str(p.id),'slot':p.slot},now)
    return {'proxy_id':str(p.id),'slot':p.slot}

def revoke_proxy(a,actor,proxy_id,now):
    p=Proxy.objects.get(pk=proxy_id,assembly=a,grantor=actor)
    if a.state=='CLOSED' or p.status not in ('ISSUED','ACCEPTED'):
        raise RuleError('INVALID_TRANSITION','Esta procuração não pode ser revogada.')
    p.status='REVOKED'; p.revoked_at=now; p.slot=None
    p.save(update_fields=['status','revoked_at','slot'])
    audit(a,actor,'proxy.revoked',{'proxy_id':str(p.id)},now)
    return {'proxy_id':str(p.id),'status':p.status}

def install(a,actor,call,now):
    require_president(a,actor)
    if a.installed_at or a.state=='CLOSED':
        raise RuleError('INVALID_TRANSITION','A assembleia já foi instalada ou encerrada.')
    regular(a,actor); regular(a,a.secretary)
    live=present_ids(a,now)
    if actor.id not in live:
        raise RuleError('PRESENCE_REQUIRED','Registre sua presença antes de instalar.')
    n=a.electors.filter(is_regular=True).count(); required=quorum_required(n)
    p=a.electors.filter(is_regular=True,member_id__in=live).count()
    if call not in (1,2) or now<(a.first_call_at if call==1 else a.second_call_at):
        raise RuleError('CALL_NOT_DUE','A convocação ainda não está disponível.')
    if call==1 and p<required:
        raise RuleError('QUORUM_NOT_MET',f'Primeira convocação exige {required} presentes próprios; há {p}.')
    # A tentativa frustrada é registrada junto da instalação de segunda no simulado.
    if call==2:
        audit(a,actor,'installation.first_call_not_installed',{'reason':'Segunda convocação de simulado; primeira não instalada.','first_call_at':a.first_call_at.isoformat()},now)
    a.installed_at=now; a.state='INSTALLED'
    a.installation={'call':call,'eligible':n,'present':p,'required_first_call':required,'attendees':[str(m) for m in sorted(live,key=str)],'snapshot_hash':a.snapshot_hash,'rule':'2/3 na primeira; qualquer número na segunda','at':now.isoformat()}
    a.save(update_fields=['installed_at','state','installation'])
    Proxy.objects.filter(assembly=a,status='ISSUED').update(status='EXPIRED')
    audit(a,actor,'assembly.installed',a.installation,now)
    return a.installation

def open_round(a,actor,item_id,duration,now):
    require_president(a,actor)
    if a.state!='INSTALLED':
        raise RuleError('NOT_INSTALLED','Instale a assembleia antes de votar.')
    item=AgendaItem.objects.get(pk=item_id,assembly=a)
    if item.rule_kind!='SIMPLE':
        raise RuleError('RULE_UNDEFINED','Matéria especial exige regra estatutária homologada.',422)
    if Round.objects.filter(assembly=a,state='OPEN').exists() or Round.objects.filter(agenda_item=item).exists():
        raise RuleError('ROUND_EXISTS','Há votação em andamento ou esta pauta já foi votada.')
    if duration<120 or duration>1800:
        raise RuleError('INVALID_DURATION','A janela deve ter de 2 a 30 minutos.',422)
    r=Round.objects.create(assembly=a,agenda_item=item,proposal_text=item.body,proposal_hash=item.proposal_hash,opened_at=now,closes_at=now+timedelta(seconds=duration))
    audit(a,actor,'round.opened',{'round_id':str(r.id),'proposal_hash':r.proposal_hash,'active_at_open':len(active_owners(a,now,item))},now)
    return {'round_id':str(r.id),'closes_at':r.closes_at.isoformat()}

def cast_ballot(a,actor,round_id,owner_id,choice,proposal_hash,now):
    if a.state!='INSTALLED':
        raise RuleError('NOT_INSTALLED','Não há assembleia deliberativa em andamento.')
    r=Round.objects.get(pk=round_id,assembly=a)
    if r.state!='OPEN' or now>=r.closes_at:
        raise RuleError('ROUND_CLOSED','Esta votação já terminou.')
    if proposal_hash!=r.proposal_hash:
        raise RuleError('PROPOSAL_CHANGED','Recarregue o texto da proposta.',422)
    owner=Member.objects.get(pk=owner_id); record=regular(a,owner); regular(a,actor)
    if choice not in ('YES','NO','ABSTAIN'):
        raise RuleError('INVALID_CHOICE','Escolha SIM, NÃO ou ABSTENÇÃO.',422)
    if r.ballots.filter(owner=owner).exists():
        raise RuleError('ALREADY_VOTED','Já existe um voto confirmado para este titular.')
    live=present_ids(a,now)
    if actor.id not in live:
        raise RuleError('PRESENCE_REQUIRED','Registre sua presença para votar.')
    p=None
    if actor.id!=owner.id:
        if owner.id in live:
            raise RuleError('GRANTOR_PRESENT','O titular está presente e exerce seu próprio voto.')
        p=Proxy.objects.filter(assembly=a,grantor=owner,representative=actor,status='ACCEPTED',scope=r.agenda_item).first()
        if not p:
            raise RuleError('PROXY_NOT_AVAILABLE','Você não pode exercer o voto deste titular.',403)
    receipt={'round_id':str(r.id),'owner_id':str(owner.id),'cast_by_id':str(actor.id),'owner_name':record.name,'executor_name':elector(a,actor).name,'choice':choice,'proxy_id':str(p.id) if p else None,'accepted_at':now.isoformat(),'proposal_hash':r.proposal_hash,'protocol':'VOT-'+uuid.uuid4().hex,'kind':'DEMO_RECEIPT'}
    b=Ballot.objects.create(round=r,owner=owner,cast_by=actor,owner_name=record.name,executor_name=elector(a,actor).name,choice=choice,proxy=p,accepted_at=now,proposal_hash=r.proposal_hash,protocol=receipt['protocol'],receipt_hash=digest(receipt))
    receipt['receipt_hash']=b.receipt_hash
    audit(a,actor,'ballot.accepted',receipt,now)
    return receipt

def close_round(a,actor,round_id,now):
    require_president(a,actor)
    r=Round.objects.get(pk=round_id,assembly=a)
    if r.state!='OPEN':
        return r.result
    finish_round(a,r,actor,now)
    return r.result

def raise_hand(a,actor,kind,now):
    if a.state!='INSTALLED' or not elector(a,actor).can_speak or actor.id not in present_ids(a,now):
        raise RuleError('FLOOR_NOT_AVAILABLE','Registre presença em uma assembleia instalada para pedir a palavra.',403)
    if kind not in ('NORMAL','ORDER'):
        raise RuleError('INVALID_KIND','Tipo de pedido inválido.',422)
    if FloorRequest.objects.filter(assembly=a,member=actor,state__in=['WAITING','GRANTED']).exists():
        raise RuleError('ALREADY_IN_QUEUE','Você já possui pedido ativo.')
    f=FloorRequest.objects.create(assembly=a,member=actor,kind=kind,requested_at=now)
    audit(a,actor,'floor.requested',{'floor_id':str(f.id),'kind':kind},now)
    return {'floor_id':str(f.id)}

def floor_decision(a,actor,floor_id,decision,reason,now):
    f=FloorRequest.objects.get(pk=floor_id,assembly=a)
    if decision=='WITHDRAW' and f.member_id==actor.id:
        state='WITHDRAWN'
    else:
        require_president(a,actor)
        if decision not in ('GRANT','DENY','END'):
            raise RuleError('INVALID_DECISION','Decisão de fala inválida.',422)
        state={'GRANT':'GRANTED','DENY':'DENIED','END':'ENDED'}[decision]
        if decision=='DENY' and not reason:
            raise RuleError('REASON_REQUIRED','Informe o motivo do indeferimento.',422)
    if f.state not in ('WAITING','GRANTED'):
        raise RuleError('INVALID_TRANSITION','Pedido já encerrado.')
    f.state=state; f.reason=reason; f.save(update_fields=['state','reason'])
    audit(a,actor,'floor.decided',{'floor_id':str(f.id),'state':state,'reason':reason},now)
    return {'state':state}

def close_assembly(a,actor,now):
    require_president(a,actor)
    if a.state!='INSTALLED' or Round.objects.filter(assembly=a,state='OPEN').exists():
        raise RuleError('INVALID_TRANSITION','Encerre as votações antes de finalizar a assembleia.')
    ParticipationSession.objects.filter(assembly=a,ended_at__isnull=True).update(ended_at=now,end_reason='ASSEMBLY_CLOSED')
    PresenceInterval.objects.filter(assembly=a,exited_at__isnull=True).update(exited_at=now,reason='ASSEMBLY_CLOSED')
    a.state='CLOSED'; a.closed_at=now; a.save(update_fields=['state','closed_at'])
    audit(a,actor,'assembly.closed',{'closed_at':now.isoformat()},now)
    return {'state':a.state}

@transaction.atomic
def state(assembly_id,actor,session_key):
    a=Assembly.objects.select_for_update().get(pk=assembly_id)
    ensure_demo(a); elector(a,actor)
    now=server_time(); expire_presence(a,now)
    for r in Round.objects.filter(assembly=a,state='OPEN',closes_at__lte=now):
        finish_round(a,r,None,now)
    live=present_ids(a,now)
    proxy_rows=Proxy.objects.filter(assembly=a).filter(models.Q(grantor=actor)|models.Q(representative=actor)).select_related('grantor','representative')
    session=ParticipationSession.objects.filter(assembly=a,member=actor,auth_session_key=session_key,ended_at__isnull=True,lease_until__gt=now).first()
    r=Round.objects.filter(assembly=a).order_by('-opened_at').first()
    round_data=None
    if r:
        entitlements=[actor.id]+list(Proxy.objects.filter(assembly=a,representative=actor,status='ACCEPTED',scope=r.agenda_item).values_list('grantor_id',flat=True))
        cards=[]
        for owner_id in entitlements:
            owner=Member.objects.get(pk=owner_id)
            ballot=r.ballots.filter(owner=owner).first()
            authorized=owner_id in active_owners(a,now,r.agenda_item) and (owner_id==actor.id or owner_id not in live) and actor.id in live
            cards.append({'owner_id':str(owner_id),'name':elector(a,owner).name,'own':owner_id==actor.id,'available':authorized and not ballot and r.state=='OPEN','receipt':{'choice':ballot.choice,'protocol':ballot.protocol,'executor':ballot.executor_name} if ballot else None})
        round_data={'id':str(r.id),'title':r.agenda_item.title,'body':r.proposal_text,'hash':r.proposal_hash,'state':r.state,'closes_at':r.closes_at.isoformat(),'received':r.ballots.count(),'cards':cards,'result':r.result if r.state=='CLOSED' else None,'nominal_votes':list(r.ballots.values('owner_name','executor_name','choice','protocol')) if r.state=='CLOSED' else []}
    return {'id':str(a.id),'code':a.code,'title':a.title,'state':a.state,'is_demo':True,'server_time':now.isoformat(),'president':str(a.president_id),'secretary':str(a.secretary_id),'first_call_at':a.first_call_at.isoformat(),'second_call_at':a.second_call_at.isoformat(),'installation':a.installation,'quorum':{'eligible':a.electors.filter(is_regular=True).count(),'present':a.electors.filter(is_regular=True,member_id__in=live).count(),'required':quorum_required(a.electors.filter(is_regular=True).count()),'represented':len(active_owners(a,now)-live)},'presence':{'present':actor.id in live,'session_id':str(session.id) if session else None},'agenda':[{'id':str(i.id),'position':i.position,'title':i.title,'body':i.body,'rule':i.rule_kind,'voted':Round.objects.filter(agenda_item=i).exists()} for i in a.agenda.all()],'proxies':[{'id':str(p.id),'grantor_id':str(p.grantor_id),'representative_id':str(p.representative_id),'grantor':p.grantor.full_name,'representative':p.representative.full_name,'condition':proxy_condition(p,live),'status':p.status} for p in proxy_rows],'round':round_data,'floor':[{'id':str(f.id),'member_id':str(f.member_id),'name':f.member.full_name,'kind':f.kind,'state':f.state} for f in FloorRequest.objects.filter(assembly=a,state__in=['WAITING','GRANTED']).select_related('member').order_by('-kind','requested_at','id')],'members':[{'id':str(e.member_id),'name':e.name,'mb':e.mb_number} for e in a.electors.all()]}

def minutes(a):
    if a.state!='CLOSED':
        raise RuleError('MINUTES_NOT_READY','Encerre a assembleia antes de gerar a minuta.')
    rounds=[]
    for r in Round.objects.filter(assembly=a).select_related('agenda_item').order_by('opened_at'):
        rounds.append({'title':r.agenda_item.title,'proposal':r.proposal_text,'proposal_hash':r.proposal_hash,'result':r.result,'votes':list(r.ballots.values('owner_name','executor_name','choice','protocol'))})
    facts={'kind':'DEMO_MINUTES_NOT_SIGNED','assembly':a.code,'title':a.title,'installation':a.installation,'closed_at':a.closed_at.isoformat(),'rounds':rounds,'presence':[{'name':i.member.full_name,'entered_at':i.entered_at.isoformat(),'exited_at':i.exited_at.isoformat() if i.exited_at else None,'reason':i.reason} for i in PresenceInterval.objects.filter(assembly=a).select_related('member')],'audit_root':a.events.last().event_hash}
    return {'facts':facts,'facts_hash':digest(facts),'notice':'Minuta de simulação. Não é PDF/A, não possui assinatura ICP-Brasil ou carimbo de tempo e não deve ser apresentada ao RCPJ.'}


def next_demo_code(assembly_id):
    # One successor per source assembly, independent of retries or browser tabs.
    return "SIM-" + uuid.UUID(str(assembly_id)).hex

def start_new_demo(assembly_id, actor, confirmed):
    with transaction.atomic():
        source = Assembly.objects.select_for_update().get(pk=assembly_id)
        ensure_demo(source)
        regular(source, actor)
        require_president(source, actor)
        if source.state != "CLOSED":
            raise RuleError("DEMO_NOT_CLOSED", "Encerre o simulado atual antes de iniciar outro.")
        if confirmed is not True:
            raise RuleError("CONFIRMATION_REQUIRED", "Confirme a criação de um novo simulado.")
        code = next_demo_code(source.id)
        successor = Assembly.objects.filter(code=code).first()
        if successor:
            return {"assembly_id": str(successor.id), "code": successor.code}
        electors = list(source.electors.select_related("member"))
        if not electors or any(e.member.issuer != "demo:local" for e in electors):
            raise RuleError("DEMO_MEMBERS_REQUIRED", "O novo teste exige somente participantes fictícios.", 403)
        now = server_time()
        successor = Assembly.objects.create(
            code=code, title="Assembleia de demonstração", is_demo=True,
            president=source.president, secretary=source.secretary,
            first_call_at=now-timedelta(minutes=40), second_call_at=now-timedelta(minutes=10),
            snapshot_hash=digest([{"id": str(e.member_id), "name": e.name} for e in electors]))
        for e in electors:
            Elector.objects.create(assembly=successor, member=e.member, name=e.name,
                mb_number=e.mb_number, is_regular=e.is_regular, can_vote=e.can_vote, can_speak=e.can_speak)
        for item in source.agenda.all():
            AgendaItem.objects.create(assembly=successor, position=item.position,
                title=item.title, body=item.body, proposal_hash=item.proposal_hash, rule_kind=item.rule_kind)
        audit(successor, actor, "demo.created", {"source_assembly_id": str(source.id)}, now)
        return {"assembly_id": str(successor.id), "code": successor.code}
