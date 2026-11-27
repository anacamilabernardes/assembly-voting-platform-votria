from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from governance.models import ClaimFailure, CommandReceipt, MailboxMessage, ParticipationSession


class Command(BaseCommand):
    help = (
        'Apaga dados operacionais que não fazem parte do registro da assembleia: códigos de procuração, '
        'tentativas falhas, recibos de idempotência e identificadores de sessão. Votos, presenças e '
        'auditoria são mantidos, pois formam o registro da deliberação.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=settings.VOTRIA_RETENTION_DAYS)
        parser.add_argument('--dry-run', action='store_true')

    @transaction.atomic
    def handle(self, *args, **options):
        now = timezone.now()
        cutoff = now - timedelta(days=options['days'])
        closed = {'assembly__state': 'CLOSED', 'assembly__closed_at__lt': cutoff}
        targets = {
            'códigos de procuração expirados': MailboxMessage.objects.filter(expires_at__lt=now),
            'tentativas de código falhas': ClaimFailure.objects.filter(occurred_at__lt=cutoff),
            'recibos de idempotência': CommandReceipt.objects.filter(**closed),
        }
        for label, rows in targets.items():
            count = rows.count()
            if not options['dry_run']:
                rows.delete()
            self.stdout.write(f'{label}: {count}')
        sessions = ParticipationSession.objects.filter(**closed).exclude(auth_session_key='')
        count = sessions.count()
        if not options['dry_run']:
            sessions.update(auth_session_key='')
        self.stdout.write(f'identificadores de sessão anonimizados: {count}')
        if options['dry_run']:
            transaction.set_rollback(True)
            self.stdout.write('Simulação: nada foi alterado.')
