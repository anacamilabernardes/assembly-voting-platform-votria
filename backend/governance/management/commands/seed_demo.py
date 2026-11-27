from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from governance.domain import demo_email, demo_email_domain, digest
from governance.models import AgendaItem, AgendaOption, Assembly, Elector, Member, Organization

NAMES = [
    'Ana Presidente',
    'Bruno Secretário',
    'Carla Associada',
    'Diego Associado',
    'Elisa Associada',
    'Felipe Associado',
    'Gabriela Associada',
]
AGENDA = [
    (
        'Aprovação do plano de atividades',
        'Aprovar o plano de atividades apresentado para este simulado, com encontros, debates e prestação de contas.',
        'SIMPLE',
        'NOMINAL',
        [],
    ),
    (
        'Aprovação do relatório da diretoria',
        'Aprovar o relatório de atividades da diretoria apresentado nesta assembleia de demonstração.',
        'SIMPLE',
        'NOMINAL',
        [],
    ),
    (
        'Matéria especial de demonstração',
        'Esta matéria permanecerá bloqueada até receber uma regra estatutária específica.',
        'SPECIAL',
        'NOMINAL',
        [],
    ),
    (
        'Reajuste da contribuição anual',
        'Aprovar, em votação secreta, o reajuste da contribuição anual proposto pela diretoria.',
        'SIMPLE',
        'SECRET',
        [],
    ),
    (
        'Eleição da diretoria',
        'Eleger, em votação secreta, a chapa que conduzirá a diretoria no próximo mandato.',
        'ELECTION',
        'SECRET',
        ['Chapa 1 — Continuidade', 'Chapa 2 — Renovação'],
    ),
]


class Command(BaseCommand):
    help = 'Cria a organização padrão e um simulado com sete associados fictícios; não apaga dados.'

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEMO_MODE:
            raise CommandError('Dados fictícios exigem modo de simulação explícito.')
        org = self.default_organization()
        self.sync_demo_emails(org)
        if Assembly.objects.filter(code='SIM-001').exists():
            self.stdout.write('Simulado já existe; histórico preservado.')
            return
        members = []
        for i, name in enumerate(NAMES, 1):
            email = demo_email(i, org.email_domain)
            user, created = User.objects.get_or_create(username=email, defaults={'email': email})
            if created:
                user.set_unusable_password()
                user.save()
            member, _ = Member.objects.get_or_create(
                user=user,
                defaults={
                    'organization': org,
                    'email': email,
                    'full_name': name,
                    'mb_number': 'DEMO-' + str(i),
                    'issuer': 'demo:local',
                    'subject': str(i),
                    'is_admin': i == 1,
                },
            )
            members.append(member)
        now = timezone.now()
        a = Assembly.objects.create(
            organization=org,
            code='SIM-001',
            title='Assembleia de demonstração',
            president=members[0],
            secretary=members[1],
            first_call_at=now - timedelta(minutes=40),
            second_call_at=now - timedelta(minutes=10),
            snapshot_hash=digest([{'id': str(m.id), 'name': m.full_name} for m in members]),
        )
        for m in members:
            Elector.objects.create(assembly=a, member=m, name=m.full_name, mb_number=m.mb_number)
        for position, (title, body, kind, mode, options) in enumerate(AGENDA, 1):
            item = AgendaItem.objects.create(
                assembly=a,
                position=position,
                title=title,
                body=body,
                proposal_hash=digest({'text': body, 'options': options} if options else {'text': body}),
                rule_kind=kind,
                voting_mode=mode,
            )
            for i, label in enumerate(options, 1):
                AgendaOption.objects.create(item=item, position=i, label=label)
        self.stdout.write('Simulado criado com sete associados fictícios.')

    def default_organization(self):
        """The deployment's institution, named and scoped by its environment settings."""
        name = settings.VOTRIA_INSTITUTION_NAME or 'Instituição de demonstração'
        domain = demo_email_domain(settings.VOTRIA_ALLOWED_EMAIL_DOMAIN)
        org, created = Organization.objects.get_or_create(
            slug='default',
            defaults={'name': name, 'email_domain': domain, 'required_acr': settings.OIDC_REQUIRED_ACR},
        )
        if created:
            return org
        if Organization.objects.filter(email_domain=domain).exclude(pk=org.pk).exists():
            raise CommandError(f'O domínio {domain} já pertence a outra organização.')
        if org.email_domain != domain and org.members.exclude(issuer='demo:local').exists():
            raise CommandError('O domínio não pode mudar depois que associados reais foram cadastrados.')
        org.name, org.email_domain = name, domain
        org.required_acr = settings.OIDC_REQUIRED_ACR or org.required_acr
        org.save(update_fields=['name', 'email_domain', 'required_acr'])
        return org

    def sync_demo_emails(self, org):
        # Keeps fictional accounts on the institution's domain after the deployment setting changes.
        for m in org.members.filter(issuer='demo:local').select_related('user'):
            local = m.email.split('@')[0]
            email = (
                demo_email(m.subject, org.email_domain)
                if m.subject.isdigit()
                else f'{local}@{org.email_domain}'
            )
            if m.email == email:
                continue
            if (
                Member.objects.filter(email=email).exclude(pk=m.pk).exists()
                or User.objects.filter(username=email).exclude(pk=m.user_id).exists()
            ):
                raise CommandError(f'O endereço fictício {email} já pertence a outra conta.')
            m.email = email
            m.save(update_fields=['email'])
            m.user.username = email
            m.user.email = email
            m.user.save(update_fields=['username', 'email'])
