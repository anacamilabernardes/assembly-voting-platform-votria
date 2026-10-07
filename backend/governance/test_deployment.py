import os
import runpy
import tempfile
from pathlib import Path
from unittest.mock import patch
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.test import TestCase, SimpleTestCase, Client, override_settings
from .models import Member, Assembly
from . import services
from .domain import RuleError

PASSWORD = "teste-online-com-senha-longa"

@override_settings(DEBUG=False, DEMO_MODE=True, DEMO_ACCESS_PASSWORD=PASSWORD,
                   SECURE_SSL_REDIRECT=True, SESSION_COOKIE_SECURE=True,
                   CSRF_COOKIE_SECURE=True, SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO", "https"),
                   ALLOWED_HOSTS=["demo.onrender.com"], CSRF_TRUSTED_ORIGINS=["https://demo.onrender.com"])
class OnlineDemoTests(TestCase):
    def setUp(self):
        cache.clear()
        call_command("seed_demo", verbosity=0)
        self.member=Member.objects.get(mb_number="DEMO-1")
        self.client=Client(enforce_csrf_checks=True)
        self.headers={"HTTP_HOST":"demo.onrender.com", "HTTP_X_FORWARDED_PROTO":"https",
                      "HTTP_ORIGIN":"https://demo.onrender.com", "REMOTE_ADDR":"203.0.113.10"}
        self.client.get("/api/v1/config", **self.headers)

    def login(self, password=None, member=None):
        body={"member_id":str((member or self.member).id)}
        if password is not None:
            body["access_password"]=password
        return self.client.post("/api/v1/auth/demo", data=body, content_type="application/json",
            HTTP_X_CSRFTOKEN=self.client.cookies["csrftoken"].value, **self.headers)

    def test_missing_and_wrong_password_rejected(self):
        for password in (None, "incorreta"):
            self.assertEqual(self.login(password).status_code,403)
        self.assertNotIn("_auth_user_id",self.client.session)

    def test_online_login_and_session_switch_with_secure_cookies(self):
        result=self.login(PASSWORD)
        self.assertEqual(result.status_code,200)
        self.assertTrue(self.client.cookies["sessionid"]["secure"])
        self.assertTrue(self.client.cookies["csrftoken"]["secure"])
        second=Member.objects.get(mb_number="DEMO-2")
        self.assertEqual(self.login(member=second).status_code,200)
        self.assertEqual(self.client.get("/api/v1/me",**self.headers).json()["id"],str(second.id))
        self.assertEqual(self.client.get("/api/v1/demo/inbox",**self.headers).status_code,200)

    def test_config_never_exposes_password(self):
        data=self.client.get("/api/v1/config",**self.headers).json()
        self.assertTrue(data["demo"])
        self.assertTrue(data["demo_password_required"])
        self.assertNotIn(PASSWORD,str(data))
        self.assertFalse(data["official_ready"])

    def test_csrf_is_required_online(self):
        self.assertEqual(self.client.post("/api/v1/auth/demo",
            data={"member_id":str(self.member.id),"access_password":PASSWORD},
            content_type="application/json",**self.headers).status_code,403)

    def test_failed_logins_are_limited(self):
        for _ in range(10):
            self.assertEqual(self.login("errada").status_code,403)
        self.assertEqual(self.login(PASSWORD).status_code,429)

    def test_logout_requires_password_again(self):
        self.assertEqual(self.login(PASSWORD).status_code,200)
        self.client.post("/api/v1/auth/logout",data={},content_type="application/json",
            HTTP_X_CSRFTOKEN=self.client.cookies["csrftoken"].value,**self.headers)
        self.assertEqual(self.login().status_code,403)

    @override_settings(DEMO_MODE=False)
    def test_demo_disabled_remains_disabled(self):
        self.assertEqual(self.login(PASSWORD).status_code,403)

    def test_official_assembly_stays_blocked(self):
        assembly=Assembly.objects.get(code="SIM-001")
        assembly.is_demo=False
        assembly.save()
        with self.assertRaisesRegex(RuleError,"OFFICIAL_NOT_READY"):
            services.ensure_demo(assembly)

    def test_seed_preserves_existing_assembly(self):
        initial=list(Assembly.objects.values_list("id",flat=True))
        call_command("seed_demo",verbosity=0)
        self.assertEqual(initial,list(Assembly.objects.values_list("id",flat=True)))

    def test_serves_interface_and_readiness(self):
        with tempfile.TemporaryDirectory() as folder:
            dist=Path(folder)
            (dist/"index.html").write_text("<html>Simulado</html>",encoding="utf-8")
            with override_settings(FRONTEND_DIST=dist):
                response=self.client.get("/",**self.headers)
                self.assertEqual(response.status_code,200)
                self.assertIn(b"Simulado",b"".join(response.streaming_content))
                self.assertEqual(response["Cache-Control"],"no-store")
                self.assertEqual(self.client.get("/health/ready",**self.headers).status_code,200)
                (dist/"index.html").unlink()
                self.assertEqual(self.client.get("/health/ready",**self.headers).status_code,503)

    def test_http_redirects_to_https(self):
        self.assertEqual(self.client.get("/api/v1/config",HTTP_HOST="demo.onrender.com").status_code,301)

class DeploymentSettingsTests(SimpleTestCase):
    def settings(self, **extra):
        env={"DJANGO_DEBUG":"false","DJANGO_SECRET_KEY":"config-test-secret",
             "MENSA_DEMO_MODE":"true","MENSA_DEMO_ACCESS_PASSWORD":PASSWORD,
             "DATABASE_URL":"postgresql://mensa:p%40ss@db.internal:5432/mensa?sslmode=require",
             "RENDER_EXTERNAL_HOSTNAME":"demo.onrender.com"}
        env.update(extra)
        with patch.dict(os.environ,env,clear=True):
            return runpy.run_path(str(Path(__file__).resolve().parents[1]/"config/settings.py"))

    def test_online_settings_and_database_url(self):
        cfg=self.settings()
        self.assertFalse(cfg["DEBUG"])
        self.assertTrue(cfg["SESSION_COOKIE_SECURE"])
        self.assertIn("demo.onrender.com",cfg["ALLOWED_HOSTS"])
        self.assertIn("https://demo.onrender.com",cfg["CSRF_TRUSTED_ORIGINS"])
        self.assertEqual(cfg["SECURE_PROXY_SSL_HEADER"],("HTTP_X_FORWARDED_PROTO","https"))
        self.assertEqual(cfg["DATABASES"]["default"]["PASSWORD"],"p@ss")
        self.assertEqual(cfg["DATABASES"]["default"]["OPTIONS"]["sslmode"],"require")

    def test_missing_or_short_online_password_fails_closed(self):
        for password in ("","curta"):
            with self.assertRaises(ImproperlyConfigured):
                self.settings(MENSA_DEMO_ACCESS_PASSWORD=password)

    def test_online_requires_postgresql(self):
        with self.assertRaises(ImproperlyConfigured):
            self.settings(DATABASE_URL="sqlite:///db.sqlite3")
        with self.assertRaises(ImproperlyConfigured):
            self.settings(DATABASE_URL="")

    def test_no_proxy_header_trust_outside_render(self):
        self.assertIsNone(self.settings(RENDER_EXTERNAL_HOSTNAME="")["SECURE_PROXY_SSL_HEADER"])
