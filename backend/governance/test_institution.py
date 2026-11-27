from django.contrib.auth.models import User
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.test import TestCase, SimpleTestCase, Client, override_settings
from .domain import DEFAULT_DEMO_EMAIL_DOMAIN, demo_email, demo_email_domain
from .models import Assembly, AuditEvent, Member
from .test_deployment import DeploymentSettingsTests


class DemoEmailRulesTests(SimpleTestCase):
    def test_demo_domain_follows_configuration(self):
        self.assertEqual(demo_email_domain(""), DEFAULT_DEMO_EMAIL_DOMAIN)
        self.assertEqual(demo_email_domain(" @Example.ORG "), "example.org")
        self.assertEqual(demo_email(3, "example.org"), "demo-participant-3@example.org")


@override_settings(DEBUG=True, DEMO_MODE=True, DEMO_ACCESS_PASSWORD="",
                   VOTRIA_INSTITUTION_NAME="Example Association", VOTRIA_ALLOWED_EMAIL_DOMAIN="example.org")
class InstitutionDomainTests(TestCase):
    def setUp(self):
        call_command("seed_demo", verbosity=0)
        self.client = Client()

    def login(self, member):
        return self.client.post("/api/v1/auth/demo", data={"member_id": str(member.id)}, content_type="application/json")

    def test_seed_uses_institution_domain(self):
        emails = sorted(Member.objects.filter(issuer="demo:local").values_list("email", flat=True))
        self.assertEqual(emails, [f"demo-participant-{i}@example.org" for i in range(1, 8)])
        self.assertTrue(all(u.username == u.email for u in User.objects.all()))

    def test_config_exposes_institution(self):
        data = self.client.get("/api/v1/config").json()
        self.assertEqual(data["institution_name"], "Example Association")
        self.assertEqual(data["institutional_domain"], "example.org")
        self.assertTrue(all(a["email"].endswith("@example.org") for a in data["demo_accounts"]))

    def test_domain_change_moves_demo_accounts_and_keeps_history(self):
        assembly = Assembly.objects.get(code="SIM-001")
        events = AuditEvent.objects.count()
        member = Member.objects.get(mb_number="DEMO-1")
        with self.settings(VOTRIA_ALLOWED_EMAIL_DOMAIN="other.example"):
            self.assertEqual(self.login(member).status_code, 400)
            call_command("seed_demo", verbosity=0)
            member.refresh_from_db()
            self.assertEqual(member.email, "demo-participant-1@other.example")
            self.assertEqual(member.user.username, member.email)
            self.assertEqual(self.login(member).status_code, 200)
        self.assertEqual(list(Assembly.objects.values_list("id", flat=True)), [assembly.id])
        self.assertEqual(AuditEvent.objects.count(), events)

    def test_demo_login_accepts_configured_domain(self):
        self.assertEqual(self.login(Member.objects.get(mb_number="DEMO-2")).status_code, 200)


class InstitutionSettingsTests(SimpleTestCase):
    settings = DeploymentSettingsTests.settings

    def test_domain_is_normalized_and_name_is_read(self):
        cfg = self.settings(VOTRIA_ALLOWED_EMAIL_DOMAIN=" @Example.ORG ", VOTRIA_INSTITUTION_NAME=" Example Association ")
        self.assertEqual(cfg["VOTRIA_ALLOWED_EMAIL_DOMAIN"], "example.org")
        self.assertEqual(cfg["VOTRIA_INSTITUTION_NAME"], "Example Association")

    def test_invalid_domain_stops_startup(self):
        for domain in ("example", "a@example.org", "example.org,other.org", "exa mple.org", "-bad.example.org"):
            with self.assertRaises(ImproperlyConfigured):
                self.settings(VOTRIA_ALLOWED_EMAIL_DOMAIN=domain)
