from django.db import migrations
def install(apps,schema_editor):
    tables=['governance_ballot','governance_auditevent']
    if schema_editor.connection.vendor=='sqlite':
        for table in tables:
            for action in ('UPDATE','DELETE'):
                schema_editor.execute(f"CREATE TRIGGER {table}_deny_{action.lower()} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT, 'immutable assembly fact'); END")
    elif schema_editor.connection.vendor=='postgresql':
        schema_editor.execute("CREATE FUNCTION mensa_reject_fact_mutation() RETURNS trigger LANGUAGE plpgsql AS $ BEGIN RAISE EXCEPTION 'immutable assembly fact'; END; $")
        for table in tables:
            schema_editor.execute(f'CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION mensa_reject_fact_mutation()')
def uninstall(apps,schema_editor):
    tables=['governance_ballot','governance_auditevent']
    if schema_editor.connection.vendor=='sqlite':
        for table in tables:
            for action in ('update','delete'):
                schema_editor.execute(f'DROP TRIGGER IF EXISTS {table}_deny_{action}')
    elif schema_editor.connection.vendor=='postgresql':
        for table in tables:
            schema_editor.execute(f'DROP TRIGGER IF EXISTS {table}_immutable ON {table}')
        schema_editor.execute('DROP FUNCTION IF EXISTS mensa_reject_fact_mutation()')
class Migration(migrations.Migration):
    dependencies=[('governance','0001_initial')]
    operations=[migrations.RunPython(install,uninstall)]
