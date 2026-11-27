from django.conf import settings
from django.db import migrations

from governance.domain import demo_email_domain

SECRET_TABLES = ['governance_secretparticipation', 'governance_secretballot']


def assign_default_organization(apps, schema_editor):
    Organization = apps.get_model('governance', 'Organization')
    Member = apps.get_model('governance', 'Member')
    Assembly = apps.get_model('governance', 'Assembly')
    if not (
        Member.objects.filter(organization__isnull=True).exists()
        or Assembly.objects.filter(organization__isnull=True).exists()
    ):
        return
    organization, _ = Organization.objects.get_or_create(
        slug='default',
        defaults={
            'name': settings.VOTRIA_INSTITUTION_NAME or 'Demo institution',
            'email_domain': demo_email_domain(settings.VOTRIA_ALLOWED_EMAIL_DOMAIN),
            'required_acr': settings.OIDC_REQUIRED_ACR,
        },
    )
    Member.objects.filter(organization__isnull=True).update(organization=organization)
    Assembly.objects.filter(organization__isnull=True).update(organization=organization)


def install_triggers(apps, schema_editor):
    vendor = schema_editor.connection.vendor
    for table in SECRET_TABLES:
        if vendor == 'sqlite':
            for action in ('UPDATE', 'DELETE'):
                schema_editor.execute(
                    f'CREATE TRIGGER {table}_deny_{action.lower()} BEFORE {action} ON {table} '
                    "BEGIN SELECT RAISE(ABORT, 'immutable assembly fact'); END"
                )
        elif vendor == 'postgresql':
            schema_editor.execute(
                f'CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} '
                'FOR EACH ROW EXECUTE FUNCTION votria_reject_fact_mutation()'
            )


def remove_triggers(apps, schema_editor):
    vendor = schema_editor.connection.vendor
    for table in SECRET_TABLES:
        if vendor == 'sqlite':
            for action in ('update', 'delete'):
                schema_editor.execute(f'DROP TRIGGER IF EXISTS {table}_deny_{action}')
        elif vendor == 'postgresql':
            schema_editor.execute(f'DROP TRIGGER IF EXISTS {table}_immutable ON {table}')


class Migration(migrations.Migration):
    dependencies = [('governance', '0003_organizations_and_secret_voting')]
    operations = [
        migrations.RunPython(assign_default_organization, migrations.RunPython.noop),
        migrations.RunPython(install_triggers, remove_triggers),
    ]
