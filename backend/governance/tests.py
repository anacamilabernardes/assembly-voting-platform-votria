import secrets
from datetime import timedelta
from unittest.mock import patch
from django.test import TestCase,SimpleTestCase,Client,override_settings
from django.core.management import call_command
from django.db import DatabaseError,transaction
from django.utils import timezone
from . import services as s
from .domain import RuleError,ordinary_result,quorum_required,institutional_email,digest
from .models import *
class RulesTests(SimpleTestCase):
    def test_simple_majority(self):
        self.assertEqual(ordinary_result(['YES']*40+['NO']*30+['ABSTAIN']*30)['outcome'],'APPROVED')
    def test_tie_and_all_abstain(self):
        for choices in ([],['ABSTAIN']*100,['YES','NO']):
            self.assertEqual(ordinary_result(choices)['outcome'],'NOT_APPROVED')
    def test_abstention_does_not_change_decision(self):
        for n in range(30):
            self.assertEqual(ordinary_result(['YES','YES','NO']+['ABSTAIN']*n)['outcome'],'APPROVED')
    def test_quorum_rounding(self):
        self.assertEqual(quorum_required(8000),5334)
        self.assertEqual(quorum_required(7),5)
    def test_exact_domain(self):
        self.assertEqual(institutional_email(' A@EXAMPLE.ORG ','example.org'),'a@example.org')
        for email in ('a@gmail.com','a@example.org.evil.org','a@sub.example.org'):
            with self.assertRaises(RuleError):
                institutional_email(email,'example.org')
        with self.assertRaises(RuleError):
            institutional_email('a@example.org','')
@override_settings(DEBUG=True,DEMO_MODE=True)
class GovernanceTests(TestCase):
    def setUp(self):
        call_command('seed_demo',verbosity=0)
        self.a=Assembly.objects.get(code='SIM-001')
        self.members=list(Member.objects.order_by('mb_number'))
        self.p,self.sec,self.g,self.rep,self.g2,self.g3,self.other=self.members
        self.item=self.a.agenda.first()
        self.now=timezone.now()
    def cmd(self,actor,action,operation,payload=None,key=None):
        with patch('governance.services.server_time',return_value=self.now):
            return s.command(self.a.id,actor,action,payload or {},key or secrets.token_hex(16),operation)
    def enter(self,m,session=None):
        key=session or str(m.id)
        return self.cmd(m,'enter:'+key,lambda a,t:s.check_in(a,m,key,True,t))
    def leave(self,m,session=None):
        key=session or str(m.id)
        return self.cmd(m,'leave:'+key,lambda a,t:s.check_out(a,m,key,t))
    def issue(self,g,rep=None):
        rep=rep or self.rep
        self.cmd(g,'issue',lambda a,t:s.issue_proxy(a,g,rep.id,[str(self.item.id)],True,t))
        mail=MailboxMessage.objects.filter(recipient=g).latest('created_at')
        return s.mailbox_cipher().decrypt(mail.ciphertext.encode()).decode()
    def claim(self,code,rep=None):
        rep=rep or self.rep
        return self.cmd(rep,'claim',lambda a,t:s.claim_proxy(a,rep,code,t),{'code':code})
    def start(self):
        self.enter(self.p)
        self.cmd(self.p,'install',lambda a,t:s.install(a,self.p,2,t))
        result=self.cmd(self.p,'open',lambda a,t:s.open_round(a,self.p,self.item.id,300,t))
        self.r=Round.objects.get(pk=result['round_id'])
    def vote(self,actor,owner,choice='YES',key=None):
        payload={'owner':str(owner.id),'choice':choice}
        return self.cmd(actor,'vote',lambda a,t:s.cast_ballot(a,actor,self.r.id,owner.id,choice,self.r.proposal_hash,t),payload,key)
    def test_login_does_not_count_presence(self):
        self.assertEqual(s.present_ids(self.a,self.now),set())
    def test_first_quorum_excludes_proxies(self):
        self.claim(self.issue(self.g))
        self.enter(self.p);self.enter(self.rep)
        with self.assertRaisesRegex(RuleError,'QUORUM_NOT_MET'):
            self.cmd(self.p,'install',lambda a,t:s.install(a,self.p,1,t))
    def test_two_device_deduplication(self):
        self.enter(self.g,'tab1');self.enter(self.g,'tab2')
        self.assertEqual(len(s.present_ids(self.a,self.now)),1)
        self.leave(self.g,'tab1')
        self.assertIn(self.g.id,s.present_ids(self.a,self.now))
        self.leave(self.g,'tab2')
        self.assertNotIn(self.g.id,s.present_ids(self.a,self.now))
    def test_lease_expiration_records_effective_exit(self):
        self.enter(self.g);entered=self.now
        self.now+=timedelta(seconds=61)
        self.cmd(self.g,'sweep',lambda a,t:{})
        interval=PresenceInterval.objects.get(member=self.g)
        self.assertEqual(interval.exited_at,entered+timedelta(seconds=60))
    def test_new_entry_after_timeout_is_new_interval(self):
        self.enter(self.g);self.now+=timedelta(seconds=61);self.enter(self.g)
        self.assertEqual(PresenceInterval.objects.filter(member=self.g).count(),2)
    def test_code_is_not_returned_to_representative(self):
        code=self.issue(self.g)
        self.assertFalse(MailboxMessage.objects.filter(recipient=self.rep).exists())
        self.assertNotIn(code,str(list(AuditEvent.objects.values('payload'))))
        self.assertNotEqual(Proxy.objects.get(grantor=self.g).token_hmac,code)
    def test_wrong_representative_cannot_claim(self):
        with self.assertRaisesRegex(RuleError,'INVALID_PROXY_CODE'):
            self.claim(self.issue(self.g),self.other)
    def test_limit_two_proxies(self):
        for grantor in (self.g,self.g2):
            self.claim(self.issue(grantor))
        with self.assertRaisesRegex(RuleError,'PROXY_LIMIT'):
            self.claim(self.issue(self.g3))
        self.assertEqual(Proxy.objects.filter(representative=self.rep,status='ACCEPTED').count(),2)
    def test_present_grantor_blocks_representative(self):
        self.claim(self.issue(self.g));self.enter(self.rep);self.start();self.enter(self.g)
        with self.assertRaisesRegex(RuleError,'GRANTOR_PRESENT'):
            self.vote(self.rep,self.g)
        self.vote(self.g,self.g)
    def test_vote_preserved_after_grantor_enters(self):
        self.claim(self.issue(self.g));self.enter(self.rep);self.start()
        self.vote(self.rep,self.g,'NO');self.enter(self.g)
        with self.assertRaisesRegex(RuleError,'ALREADY_VOTED'):
            self.vote(self.g,self.g)
        self.assertEqual(Ballot.objects.get(owner=self.g).choice,'NO')
    def test_revocation_preserves_previous_vote(self):
        self.claim(self.issue(self.g));self.enter(self.rep);self.start()
        self.vote(self.rep,self.g)
        p=Proxy.objects.get(grantor=self.g)
        self.cmd(self.g,'revoke',lambda a,t:s.revoke_proxy(a,self.g,p.id,t))
        self.assertEqual(Ballot.objects.filter(owner=self.g).count(),1)
    def test_absent_representative_cannot_vote(self):
        self.claim(self.issue(self.g));self.start()
        with self.assertRaisesRegex(RuleError,'PRESENCE_REQUIRED'):
            self.vote(self.rep,self.g)
    def test_no_implicit_redelegation(self):
        self.claim(self.issue(self.g,self.rep),self.rep)
        self.claim(self.issue(self.rep,self.other),self.other)
        self.enter(self.other);self.start()
        with self.assertRaisesRegex(RuleError,'PROXY_NOT_AVAILABLE'):
            self.vote(self.other,self.g)
    def test_cycle_is_rejected(self):
        self.issue(self.g,self.rep)
        with self.assertRaisesRegex(RuleError,'PROXY_CYCLE'):
            self.issue(self.rep,self.g)
    def test_immutable_vote_and_idempotent_retry(self):
        self.start()
        first=self.vote(self.p,self.p,key='stable-key')
        second=self.vote(self.p,self.p,key='stable-key')
        self.assertEqual(first,second)
        self.assertEqual(Ballot.objects.count(),1)
        with self.assertRaisesRegex(RuleError,'IDEMPOTENCY_CONFLICT'):
            self.vote(self.p,self.p,'NO',key='stable-key')
    def test_second_vote_and_database_update_blocked(self):
        self.start();self.vote(self.p,self.p)
        with self.assertRaisesRegex(RuleError,'ALREADY_VOTED'):
            self.vote(self.p,self.p,'NO')
        with self.assertRaises(DatabaseError),transaction.atomic():
            Ballot.objects.all().update(choice='NO')
    def test_deadline_is_exclusive(self):
        self.start();self.now=self.r.closes_at
        with self.assertRaisesRegex(RuleError,'ROUND_CLOSED'):
            self.vote(self.p,self.p)
        self.assertFalse(Ballot.objects.exists())
    def test_departure_does_not_reinstall_quorum(self):
        self.enter(self.g);self.start();self.leave(self.g)
        self.vote(self.p,self.p)
        self.assertEqual(Ballot.objects.count(),1)
    def test_special_rule_is_blocked(self):
        self.start()
        self.cmd(self.p,'close-round',lambda a,t:s.close_round(a,self.p,self.r.id,t))
        special=self.a.agenda.get(rule_kind='SPECIAL')
        with self.assertRaisesRegex(RuleError,'RULE_UNDEFINED'):
            self.cmd(self.p,'special',lambda a,t:s.open_round(a,self.p,special.id,300,t))
    def test_no_partial_result_leak(self):
        self.start();self.vote(self.p,self.p)
        data=s.state(self.a.id,self.sec,'secretary-session')
        self.assertIsNone(data['round']['result'])
        self.assertEqual(data['round']['nominal_votes'],[])
    def test_deterministic_minutes(self):
        self.start();self.vote(self.p,self.p)
        self.now+=timedelta(seconds=1)
        self.cmd(self.p,'close-round',lambda a,t:s.close_round(a,self.p,self.r.id,t))
        self.cmd(self.p,'close-assembly',lambda a,t:s.close_assembly(a,self.p,t))
        self.a.refresh_from_db()
        first=s.minutes(self.a);second=s.minutes(self.a)
        self.assertEqual(first['facts_hash'],second['facts_hash'])
        self.assertEqual(first['facts']['rounds'][0]['result']['outcome'],'APPROVED')
    def test_audit_chain_and_update_rejected(self):
        self.enter(self.p);self.leave(self.p)
        previous=''
        for e in self.a.events.all():
            envelope={'assembly':str(self.a.id),'actor':str(e.actor_id) if e.actor_id else None,'sequence':e.sequence,'action':e.action,'payload':e.payload,'occurred_at':e.occurred_at.isoformat(),'previous_hash':previous,'schema':'votria-json-v1'}
            self.assertEqual(e.previous_hash,previous)
            self.assertEqual(e.event_hash,digest(envelope));previous=e.event_hash
        with self.assertRaises(DatabaseError),transaction.atomic():
            AuditEvent.objects.all().update(action='tampered')
    def test_official_assembly_always_rejected(self):
        self.a.is_demo=False;self.a.save()
        with self.assertRaisesRegex(RuleError,'OFFICIAL_NOT_READY'):
            self.enter(self.p)
    def test_foreign_assembly_access_is_denied(self):
        self.a.electors.filter(member=self.other).delete()
        with self.assertRaises(RuleError):
            s.state(self.a.id,self.other,'outside')
    def test_demo_login_requires_csrf(self):
        client=Client(enforce_csrf_checks=True)
        self.assertEqual(client.post('/api/v1/auth/demo',data={'member_id':str(self.p.id)},content_type='application/json').status_code,403)
        client.get('/api/v1/config')
        csrf=client.cookies['csrftoken'].value
        response=client.post('/api/v1/auth/demo',data={'member_id':str(self.p.id)},content_type='application/json',HTTP_X_CSRFTOKEN=csrf)
        self.assertEqual(response.status_code,200)
    def test_complete_http_flow(self):
        client=Client(enforce_csrf_checks=True)
        client.get('/api/v1/config')
        def post(route,body):
            csrf=client.cookies['csrftoken'].value
            response=client.post(route,data=body,content_type='application/json',HTTP_X_CSRFTOKEN=csrf,HTTP_IDEMPOTENCY_KEY=secrets.token_hex(16),HTTP_ORIGIN='http://127.0.0.1:5173')
            self.assertEqual(response.status_code,200,response.content)
            return response.json()
        post('/api/v1/auth/demo',{'member_id':str(self.p.id)})
        root='/api/v1/assemblies/'+str(self.a.id)
        post(root+'/presence/check-in',{'confirmed':True})
        self.assertTrue(client.get(root+'/state').json()['presence']['present'])
        post(root+'/install',{'call':2})
        opened=post(root+'/agenda/'+str(self.item.id)+'/open',{'duration_seconds':120})
        round_id=opened['round_id']
        receipt=post(root+'/rounds/'+round_id+'/ballots',{'owner_id':str(self.p.id),'choice':'ABSTAIN','proposal_hash':self.item.proposal_hash})
        self.assertTrue(receipt['protocol'].startswith('VOT-'))
        hidden=client.get(root+'/state').json()['round']
        self.assertIsNone(hidden['result'])
        self.assertEqual(hidden['nominal_votes'],[])
        result=post(root+'/rounds/'+round_id+'/close',{})
        self.assertEqual(result['outcome'],'NOT_APPROVED')
        self.assertEqual(result['abstain'],1)
        post(root+'/close',{})
        final=client.get(root+'/minutes')
        self.assertEqual(final.status_code,200)
        self.assertEqual(final.json()['facts']['kind'],'DEMO_MINUTES_NOT_SIGNED')

    @override_settings(DEMO_MODE=False)
    def test_demo_login_disabled(self):
        self.assertEqual(self.client.post('/api/v1/auth/demo',data={'member_id':str(self.p.id)},content_type='application/json').status_code,403)
