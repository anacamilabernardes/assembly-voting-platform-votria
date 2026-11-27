import copy
import secrets
from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.db import DatabaseError, transaction
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from . import administration as admin
from . import services as s
from .domain import BLANK, RuleError, digest, election_result
from .identity import link_identity
from .models import (
    Assembly,
    AuditEvent,
    Ballot,
    CommandReceipt,
    Elector,
    MailboxMessage,
    Member,
    Organization,
    Round,
    SecretBallot,
    SecretParticipation,
)


class ElectionRuleTests(SimpleTestCase):
    options = [{'id': 'a', 'label': 'Chapa A'}, {'id': 'b', 'label': 'Chapa B'}]

    def test_plurality_winner(self):
        result = election_result(['a', 'a', 'b', BLANK], self.options)
        self.assertEqual(result['outcome'], 'ELECTED')
        self.assertEqual(result['winner']['label'], 'Chapa A')
        self.assertEqual((result['valid'], result['blank']), (3, 1))

    def test_tie_and_empty(self):
        self.assertEqual(election_result(['a', 'b'], self.options)['outcome'], 'TIE')
        self.assertEqual(election_result([BLANK], self.options)['outcome'], 'NO_VALID_VOTES')


@override_settings(DEBUG=True, DEMO_MODE=True, DEMO_ACCESS_PASSWORD='')
class ProductTestCase(TestCase):
    def setUp(self):
        call_command('seed_demo', verbosity=0)
        self.a = Assembly.objects.get(code='SIM-001')
        self.org = self.a.organization
        self.members = list(Member.objects.order_by('mb_number'))
        self.p, self.sec, self.g, self.rep = self.members[:4]
        self.now = timezone.now()

    def cmd(self, actor, operation, payload=None, assembly=None):
        with patch('governance.services.server_time', return_value=self.now):
            return s.command(
                (assembly or self.a).id, actor, 'test', payload or {}, secrets.token_hex(16), operation
            )

    def enter(self, m, assembly=None):
        return self.cmd(m, lambda a, t: s.check_in(a, m, str(m.id), True, t), assembly=assembly)

    def install_and_open(self, position):
        self.enter(self.p)
        self.cmd(self.p, lambda a, t: s.install(a, self.p, 2, t))
        item = self.a.agenda.get(position=position)
        opened = self.cmd(self.p, lambda a, t: s.open_round(a, self.p, item.id, 300, t))
        return Round.objects.get(pk=opened['round_id'])

    def vote(self, actor, owner, r, choice):
        return self.cmd(
            actor, lambda a, t: s.cast_ballot(a, actor, r.id, owner.id, choice, r.proposal_hash, t)
        )

    def close(self, r):
        return self.cmd(self.p, lambda a, t: s.close_round(a, self.p, r.id, t))


class SecretVotingTests(ProductTestCase):
    def test_secret_ballot_keeps_choice_apart_from_voter(self):
        r = self.install_and_open(4)
        self.enter(self.g)
        receipt = self.vote(self.p, self.p, r, 'YES')
        self.vote(self.g, self.g, r, 'NO')
        self.assertNotIn('choice', receipt)
        self.assertEqual(Ballot.objects.count(), 0)
        self.assertEqual(SecretParticipation.objects.filter(round=r).count(), 2)
        self.assertEqual(
            sorted(SecretBallot.objects.filter(round=r).values_list('choice', flat=True)), ['NO', 'YES']
        )
        participation = AuditEvent.objects.filter(action='ballot.participation')
        self.assertEqual(participation.count(), 2)
        self.assertTrue(all('choice' not in e.payload for e in participation))
        result = self.close(r)
        self.assertEqual((result['yes'], result['no'], result['voting_mode']), (1, 1, 'SECRET'))
        state = s.state(self.a.id, self.p, str(self.p.id))
        self.assertEqual(state['round']['nominal_votes'], [])
        self.assertEqual(
            {v['owner_name'] for v in state['round']['participants']}, {self.p.full_name, self.g.full_name}
        )
        self.assertIsNone(state['round']['cards'][0]['receipt']['choice'])

    def test_secret_vote_once_and_immutable(self):
        r = self.install_and_open(4)
        self.vote(self.p, self.p, r, 'YES')
        with self.assertRaises(RuleError) as ctx:
            self.vote(self.p, self.p, r, 'NO')
        self.assertEqual(ctx.exception.code, 'ALREADY_VOTED')
        for model in (SecretBallot, SecretParticipation):
            with self.assertRaises(DatabaseError), transaction.atomic():
                model.objects.all().delete()

    def test_http_secret_choice_never_reaches_idempotency_record(self):
        client = Client()
        client.post('/api/v1/auth/demo', {'member_id': str(self.p.id)}, content_type='application/json')
        root = f'/api/v1/assemblies/{self.a.id}'

        def post(path, body):
            return client.post(
                root + path, body, content_type='application/json', HTTP_IDEMPOTENCY_KEY=secrets.token_hex(8)
            )

        self.assertEqual(post('/presence/check-in', {'confirmed': True}).status_code, 200)
        self.assertEqual(post('/install', {'call': 2}).status_code, 200)
        item = self.a.agenda.get(position=4)
        round_id = post(f'/agenda/{item.id}/open', {'duration_seconds': 300}).json()['round_id']
        body = {'owner_id': str(self.p.id), 'choice': 'YES', 'proposal_hash': item.proposal_hash}
        response = post(f'/rounds/{round_id}/ballots', body)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('choice', response.json())
        record = CommandReceipt.objects.get(action='ballot:' + round_id)
        self.assertEqual(
            record.request_hash, digest({'owner_id': str(self.p.id), 'proposal_hash': item.proposal_hash})
        )
        self.assertNotIn('YES', str(record.response))


class ElectionTests(ProductTestCase):
    def test_election_counts_options_and_blank(self):
        r = self.install_and_open(5)
        self.enter(self.g)
        self.enter(self.rep)
        first, second = r.options
        self.vote(self.p, self.p, r, first['id'])
        self.vote(self.g, self.g, r, first['id'])
        self.vote(self.rep, self.rep, r, BLANK)
        with self.assertRaises(RuleError):
            self.vote(self.sec, self.sec, r, 'YES')
        result = self.close(r)
        self.assertEqual(result['outcome'], 'ELECTED')
        self.assertEqual(result['winner']['label'], first['label'])
        self.assertEqual(result['blank'], 1)

    def test_nominal_item_rejects_option_choice(self):
        r = self.install_and_open(1)
        with self.assertRaises(RuleError) as ctx:
            self.vote(self.p, self.p, r, BLANK)
        self.assertEqual(ctx.exception.code, 'INVALID_CHOICE')


class AdministrationTests(ProductTestCase):
    CSV = 'name,email,member_number,can_vote\nJoana Lima,{d}joana,N-1,sim\nPaulo Reis,{d}paulo,N-2,não\n'

    def csv(self, domain=None):
        d = domain or self.org.email_domain
        return self.CSV.replace('{d}joana', f'joana@{d}').replace('{d}paulo', f'paulo@{d}')

    def test_only_admins(self):
        with self.assertRaises(RuleError) as ctx:
            admin.organization_overview(self.g)
        self.assertEqual(ctx.exception.code, 'ADMIN_REQUIRED')

    def test_import_creates_and_updates_members(self):
        self.assertEqual(
            admin.import_members(self.p, self.csv(), False), {'created': 2, 'updated': 0, 'simulation': False}
        )
        paulo = Member.objects.get(mb_number='N-2', organization=self.org)
        self.assertFalse(paulo.can_vote)
        self.assertEqual(paulo.issuer, '')
        again = self.csv().replace('Paulo Reis', 'Paulo R. Reis')
        self.assertEqual(admin.import_members(self.p, again, False)['updated'], 2)
        paulo.refresh_from_db()
        self.assertEqual(paulo.full_name, 'Paulo R. Reis')

    def test_import_errors_reject_whole_file_with_lines(self):
        bad = self.csv() + f'Sem Dominio,x@gmail.com,N-3\nRepetido,outro@{self.org.email_domain},N-1\n'
        with self.assertRaises(RuleError) as ctx:
            admin.import_members(self.p, bad, False)
        self.assertEqual(ctx.exception.code, 'IMPORT_INVALID')
        self.assertEqual({e['line'] for e in ctx.exception.detail}, {4, 5})
        self.assertFalse(Member.objects.filter(mb_number__startswith='N-').exists())
        with self.assertRaises(RuleError) as ctx:
            admin.import_members(self.p, 'name,email\nA,a@x.org\n', False)
        self.assertEqual(ctx.exception.code, 'IMPORT_COLUMNS')

    def test_simulation_members_can_use_demo_sign_in(self):
        admin.import_members(self.p, self.csv(), True)
        joana = Member.objects.get(mb_number='N-1', organization=self.org)
        response = Client().post(
            '/api/v1/auth/demo', {'member_id': str(joana.id)}, content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)

    def build(self):
        created = admin.create_assembly(
            self.p,
            'Assembleia ordinária',
            self.now - timedelta(hours=1),
            self.now - timedelta(minutes=30),
            self.p.id,
            self.sec.id,
        )
        admin.add_agenda_item(self.p, created['id'], 'Contas', 'Aprovar as contas.', 'SIMPLE', 'NOMINAL', [])
        admin.add_agenda_item(
            self.p, created['id'], 'Eleição', 'Eleger o conselho.', 'ELECTION', 'SECRET', ['A', 'B']
        )
        return Assembly.objects.get(pk=created['id'])

    def test_create_publish_and_run_assembly(self):
        admin.import_members(self.p, self.csv(), True)
        a = self.build()
        self.assertEqual(a.state, 'DRAFT')
        self.assertFalse(Assembly.objects.filter(electors__member=self.p, state='DRAFT').exists())
        published = admin.publish_assembly(self.p, a.id)
        self.assertEqual(published['electors'], self.org.members.count())
        a.refresh_from_db()
        self.assertEqual(a.state, 'PUBLISHED')
        self.assertFalse(Elector.objects.get(assembly=a, member__mb_number='N-2').can_vote)
        self.assertEqual(
            a.electors.filter(is_regular=True).count(), self.org.members.filter(can_vote=True).count()
        )
        self.enter(self.p, assembly=a)
        self.cmd(self.p, lambda x, t: s.install(x, self.p, 2, t), assembly=a)
        election = a.agenda.get(position=2)
        opened = self.cmd(self.p, lambda x, t: s.open_round(x, self.p, election.id, 300, t), assembly=a)
        self.assertEqual(len(Round.objects.get(pk=opened['round_id']).options), 2)
        with self.assertRaises(RuleError):
            admin.add_agenda_item(self.p, a.id, 'Tarde demais', 'x', 'SIMPLE', 'NOMINAL', [])

    def test_agenda_validation(self):
        a = self.build()
        for kind, mode, options in (
            ('ELECTION', 'NOMINAL', ['A', 'B']),
            ('ELECTION', 'SECRET', ['A']),
            ('SIMPLE', 'NOMINAL', ['A']),
        ):
            with self.assertRaises(RuleError):
                admin.add_agenda_item(self.p, a.id, 'x', 'y', kind, mode, options)
        admin.remove_agenda_item(self.p, a.id, a.agenda.get(position=1).id)
        self.assertEqual(list(a.agenda.values_list('position', flat=True)), [1])
        with self.assertRaises(RuleError) as ctx:
            admin.create_assembly(
                self.p, 'x', self.now, self.now - timedelta(minutes=1), self.p.id, self.sec.id
            )
        self.assertEqual(ctx.exception.code, 'CALL_ORDER')


class IsolationTests(ProductTestCase):
    def setUp(self):
        super().setUp()
        self.other = Organization.objects.create(name='Outra', slug='outra', email_domain='outra.example')
        user = User.objects.create(username='chefe@outra.example')
        self.other_admin = Member.objects.create(
            organization=self.other,
            user=user,
            mb_number='O-1',
            full_name='Chefe',
            email=user.username,
            is_admin=True,
        )

    def test_admin_sees_only_own_organization(self):
        overview = admin.organization_overview(self.other_admin)
        self.assertEqual([m['name'] for m in overview['members']], ['Chefe'])
        self.assertEqual(overview['assemblies'], [])
        with self.assertRaises(RuleError) as ctx:
            admin.draft_detail(self.other_admin, self.a.id)
        self.assertEqual(ctx.exception.code, 'NOT_FOUND')
        with self.assertRaises(RuleError):
            admin.import_members(
                self.other_admin, f'name,email,member_number\nX,x@{self.org.email_domain},X-1\n', False
            )
        with self.assertRaises(RuleError):
            admin.create_assembly(
                self.other_admin, 'x', self.now, self.now + timedelta(hours=1), self.p.id, self.sec.id
            )

    def test_member_cannot_reach_foreign_assembly(self):
        with self.assertRaises(RuleError) as ctx:
            s.state(self.a.id, self.other_admin, 'x')
        self.assertEqual(ctx.exception.code, 'NOT_ELIGIBLE')


class AuditAndRetentionTests(ProductTestCase):
    def test_verify_chain_detects_changes(self):
        r = self.install_and_open(1)
        self.vote(self.p, self.p, r, 'YES')
        events = list(self.a.events.order_by('sequence'))
        self.assertEqual(s.verify_chain(self.a.id, events), [])
        tampered = copy.deepcopy(events)
        tampered[-1].payload['choice'] = 'NO'
        self.assertTrue(any('alterado' in p for p in s.verify_chain(self.a.id, tampered)))
        self.assertTrue(s.verify_chain(self.a.id, events[:1] + events[2:]))
        out = StringIO()
        call_command('verify_audit', stdout=out)
        self.assertIn('íntegros', out.getvalue())

    def test_retention_purges_operational_data_only(self):
        r = self.install_and_open(1)
        self.vote(self.p, self.p, r, 'YES')
        MailboxMessage.objects.create(
            recipient=self.p,
            assembly=self.a,
            subject='x',
            ciphertext='x',
            created_at=self.now,
            expires_at=self.now - timedelta(days=1),
        )
        call_command('apply_retention', '--dry-run', stdout=StringIO())
        self.assertEqual(MailboxMessage.objects.count(), 1)
        call_command('apply_retention', stdout=StringIO())
        self.assertEqual(MailboxMessage.objects.count(), 0)
        self.assertEqual(Ballot.objects.count(), 1)


class MinutesAndHeadersTests(ProductTestCase):
    def test_printable_minutes_show_secret_participation_without_choices(self):
        r = self.install_and_open(4)
        self.vote(self.p, self.p, r, 'YES')
        self.close(r)
        self.cmd(self.p, lambda a, t: s.close_assembly(a, self.p, t))
        client = Client()
        client.post('/api/v1/auth/demo', {'member_id': str(self.p.id)}, content_type='application/json')
        response = client.get(f'/api/v1/assemblies/{self.a.id}/minutes.html')
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('Reajuste da contribuição anual', html)
        self.assertIn('Votação secreta', html.replace('votação', 'Votação'))
        self.assertIn(self.p.full_name, html)
        self.assertNotIn('<td>SIM</td>', html)
        self.assertIn("style-src 'unsafe-inline'", response['Content-Security-Policy'])
        self.assertNotIn('script-src', response['Content-Security-Policy'])

    def test_strict_csp_on_api(self):
        policy = Client().get('/api/v1/config')['Content-Security-Policy']
        self.assertIn("script-src 'self'", policy)
        self.assertIn("frame-ancestors 'none'", policy)


class IdentityLinkTests(ProductTestCase):
    def test_first_sign_in_binds_and_later_must_match(self):
        user = User.objects.create(username=f'real@{self.org.email_domain}')
        m = Member.objects.create(
            organization=self.org, user=user, mb_number='R-1', full_name='Real', email=user.username
        )
        link_identity(m, 'https://idp.example', 'sub-1')
        m.refresh_from_db()
        self.assertEqual((m.issuer, m.subject), ('https://idp.example', 'sub-1'))
        with self.assertRaises(RuleError):
            link_identity(m, 'https://idp.example', 'sub-2')
        with self.assertRaises(RuleError):
            link_identity(self.p, 'https://idp.example', 'sub-3')
