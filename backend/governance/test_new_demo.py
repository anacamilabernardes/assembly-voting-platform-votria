import secrets

from django.core.management import call_command
from django.test import Client, TestCase, override_settings

from . import services as s
from .domain import RuleError
from .models import Assembly, AuditEvent, Ballot, FloorRequest, Member, ParticipationSession, Proxy, Round


@override_settings(DEBUG=True, DEMO_MODE=True, DEMO_ACCESS_PASSWORD='')
class NewDemoTests(TestCase):
    def setUp(self):
        call_command('seed_demo', verbosity=0)
        self.source = Assembly.objects.get(code='SIM-001')
        self.p = Member.objects.get(mb_number='DEMO-1')
        self.other = Member.objects.get(mb_number='DEMO-2')
        self.command(self.p, lambda a, t: s.check_in(a, self.p, 'test-session', True, t))
        self.command(self.p, lambda a, t: s.install(a, self.p, 2, t))
        item = self.source.agenda.first()
        opened = self.command(self.p, lambda a, t: s.open_round(a, self.p, item.id, 300, t))
        self.round = Round.objects.get(pk=opened['round_id'])
        self.command(
            self.p,
            lambda a, t: s.cast_ballot(
                a, self.p, self.round.id, self.p.id, 'YES', self.round.proposal_hash, t
            ),
        )
        self.command(self.p, lambda a, t: s.close_round(a, self.p, self.round.id, t))
        self.command(self.p, lambda a, t: s.close_assembly(a, self.p, t))
        self.source.refresh_from_db()

    def command(self, actor, operation):
        return s.command(self.source.id, actor, 'test', {}, secrets.token_hex(16), operation)

    def test_new_demo_preserves_minutes_votes_and_events(self):
        previous = s.minutes(self.source)
        events = list(AuditEvent.objects.filter(assembly=self.source).values())
        result = s.start_new_demo(self.source.id, self.p, True)
        new = Assembly.objects.get(pk=result['assembly_id'])
        self.assertEqual(s.minutes(self.source), previous)
        self.assertEqual(events, list(AuditEvent.objects.filter(assembly=self.source).values()))
        self.assertEqual(Ballot.objects.filter(round__assembly=self.source).count(), 1)
        self.source.refresh_from_db()
        self.assertEqual(self.source.state, 'CLOSED')
        self.assertEqual(new.state, 'PUBLISHED')
        self.assertTrue(new.is_demo)
        self.assertEqual(new.electors.count(), 7)
        self.assertEqual(new.agenda.count(), 5)
        self.assertEqual(new.agenda.filter(rule_kind='SPECIAL').count(), 1)
        for model in (Round, Proxy, ParticipationSession, FloorRequest):
            self.assertFalse(model.objects.filter(assembly=new).exists())
        state = s.state(new.id, self.p, 'test-session')
        self.assertEqual(state['quorum']['present'], 0)
        self.assertFalse(any(item['voted'] for item in state['agenda']))

    def test_retries_create_only_one_successor(self):
        first = s.start_new_demo(self.source.id, self.p, True)
        self.assertEqual(first, s.start_new_demo(self.source.id, self.p, True))
        self.assertEqual(Assembly.objects.count(), 2)

    def test_only_president_can_start_another_demo(self):
        with self.assertRaisesRegex(RuleError, 'ROLE_REQUIRED'):
            s.start_new_demo(self.source.id, self.other, True)

    def test_confirmation_required(self):
        with self.assertRaisesRegex(RuleError, 'CONFIRMATION_REQUIRED'):
            s.start_new_demo(self.source.id, self.p, False)

    def test_active_assembly_cannot_be_replaced(self):
        self.source.state = 'INSTALLED'
        self.source.save()
        with self.assertRaisesRegex(RuleError, 'DEMO_NOT_CLOSED'):
            s.start_new_demo(self.source.id, self.p, True)

    def test_official_assembly_is_blocked(self):
        self.source.is_demo = False
        self.source.save()
        with self.assertRaisesRegex(RuleError, 'OFFICIAL_NOT_READY'):
            s.start_new_demo(self.source.id, self.p, True)

    @override_settings(DEMO_MODE=False)
    def test_disabled_demo_is_blocked(self):
        with self.assertRaisesRegex(RuleError, 'OFFICIAL_NOT_READY'):
            s.start_new_demo(self.source.id, self.p, True)

    def client_for(self, member):
        client = Client(enforce_csrf_checks=True)
        client.get('/api/v1/config')
        response = client.post(
            '/api/v1/auth/demo',
            data={'member_id': str(member.id)},
            content_type='application/json',
            HTTP_X_CSRFTOKEN=client.cookies['csrftoken'].value,
        )
        self.assertEqual(response.status_code, 200)
        return client

    def test_http_flow_and_existing_participant_discovers_new_demo(self):
        president = self.client_for(self.p)
        other = self.client_for(self.other)
        endpoint = '/api/v1/assemblies/' + str(self.source.id) + '/new-demo'
        self.assertEqual(
            president.post(endpoint, data={'confirmed': True}, content_type='application/json').status_code,
            403,
        )
        created = president.post(
            endpoint,
            data={'confirmed': True},
            content_type='application/json',
            HTTP_X_CSRFTOKEN=president.cookies['csrftoken'].value,
        )
        self.assertEqual(created.status_code, 200, created.content)
        new_id = created.json()['assembly_id']
        state = other.get('/api/v1/assemblies/' + str(self.source.id) + '/state').json()
        self.assertEqual(state['next_demo_id'], new_id)
        self.assertEqual(other.get('/api/v1/assemblies').json()[0]['id'], new_id)
        checked = other.post(
            '/api/v1/assemblies/' + new_id + '/presence/check-in',
            data={'confirmed': True},
            content_type='application/json',
            HTTP_X_CSRFTOKEN=other.cookies['csrftoken'].value,
            HTTP_IDEMPOTENCY_KEY='new-presence',
        )
        self.assertEqual(checked.status_code, 200, checked.content)
        self.assertEqual(other.get('/api/v1/assemblies/' + new_id + '/state').json()['quorum']['present'], 1)

    def test_http_rejects_other_member_and_non_demo_authentication(self):
        other = self.client_for(self.other)
        endpoint = '/api/v1/assemblies/' + str(self.source.id) + '/new-demo'
        headers = {'HTTP_X_CSRFTOKEN': other.cookies['csrftoken'].value}
        self.assertEqual(
            other.post(
                endpoint, data={'confirmed': True}, content_type='application/json', **headers
            ).status_code,
            403,
        )
        session = other.session
        session['authentication_kind'] = 'OIDC_MFA'
        session.save()
        self.assertEqual(
            other.post(
                endpoint, data={'confirmed': True}, content_type='application/json', **headers
            ).status_code,
            403,
        )

    def test_inbox_is_scoped_to_current_demo(self):
        from datetime import timedelta

        from django.utils import timezone

        from .models import MailboxMessage

        now = timezone.now()
        MailboxMessage.objects.create(
            assembly=self.source,
            recipient=self.p,
            subject='Código anterior',
            ciphertext=s.mailbox_cipher().encrypt(b'old-code').decode(),
            created_at=now,
            expires_at=now + timedelta(hours=1),
        )
        new = s.start_new_demo(self.source.id, self.p, True)
        client = self.client_for(self.p)
        self.assertEqual(client.get('/api/v1/demo/inbox?assembly_id=' + new['assembly_id']).json(), [])
