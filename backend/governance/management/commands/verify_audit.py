from django.core.management.base import BaseCommand, CommandError

from governance.models import Assembly
from governance.services import verify_chain


class Command(BaseCommand):
    help = 'Recalcula a cadeia de hashes da auditoria e falha se algum evento tiver sido alterado.'

    def add_arguments(self, parser):
        parser.add_argument('--assembly', help='Código da assembleia; sem ele, verifica todas.')

    def handle(self, *args, **options):
        assemblies = Assembly.objects.order_by('code')
        if options['assembly']:
            assemblies = assemblies.filter(code=options['assembly'])
            if not assemblies.exists():
                raise CommandError(f'Assembleia {options["assembly"]} não encontrada.')
        failed = 0
        for a in assemblies:
            events = list(a.events.order_by('sequence'))
            problems = verify_chain(a.id, events)
            if problems:
                failed += 1
                self.stdout.write(self.style.ERROR(f'{a.code}: {len(problems)} problema(s)'))
                for problem in problems:
                    self.stdout.write(f'  - {problem}')
            else:
                root = events[-1].event_hash if events else '-'
                self.stdout.write(
                    self.style.SUCCESS(f'{a.code}: {len(events)} eventos íntegros, raiz {root}')
                )
        if failed:
            raise CommandError(f'{failed} assembleia(s) com auditoria inconsistente.')
