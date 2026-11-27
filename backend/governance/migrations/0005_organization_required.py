import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('governance', '0004_default_organization_and_secret_triggers')]
    operations = [
        migrations.AlterField(
            model_name='member',
            name='organization',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='members',
                to='governance.organization',
            ),
        ),
        migrations.AlterField(
            model_name='assembly',
            name='organization',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='assemblies',
                to='governance.organization',
            ),
        ),
    ]
