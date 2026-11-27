from datetime import timedelta
from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand,CommandError
from django.db import transaction
from django.utils import timezone
from governance.models import Member,Assembly,Elector,AgendaItem
from governance.domain import digest
class Command(BaseCommand):
    help='Cria um simulado com sete associados fictícios; não apaga dados.'
    @transaction.atomic
    def handle(self,*args,**options):
        if not settings.DEMO_MODE:
            raise CommandError('Dados fictícios exigem modo de simulação explícito.')
        if Assembly.objects.filter(code='SIM-001').exists():
            self.stdout.write('Simulado já existe; histórico preservado.')
            return
        names=['Ana Presidente','Bruno Secretário','Carla Associada','Diego Associado','Elisa Associada','Felipe Associado','Gabriela Associada']
        members=[]
        for i,name in enumerate(names):
            email='participant'+str(i+1)+'@demo.votria.test'
            u,created=User.objects.get_or_create(username=email,defaults={'email':email})
            if created:
                u.set_unusable_password();u.save()
            m,_=Member.objects.get_or_create(user=u,defaults={'email':email,'full_name':name,'mb_number':'DEMO-'+str(i+1),'issuer':'demo:local','subject':str(i+1)})
            members.append(m)
        now=timezone.now()
        a=Assembly.objects.create(code='SIM-001',title='Assembleia de demonstração',president=members[0],secretary=members[1],first_call_at=now-timedelta(minutes=40),second_call_at=now-timedelta(minutes=10),snapshot_hash=digest([{'id':str(m.id),'name':m.full_name} for m in members]))
        for m in members:
            Elector.objects.create(assembly=a,member=m,name=m.full_name,mb_number=m.mb_number)
        proposals=[('Aprovação do plano de atividades','Aprovar o plano de atividades apresentado para este simulado, com encontros, debates e prestação de contas.'),('Aprovação do relatório da diretoria','Aprovar o relatório de atividades da diretoria apresentado nesta assembleia de demonstração.'),('Matéria especial de demonstração','Esta matéria permanecerá bloqueada até receber uma regra estatutária específica.')]
        for i,(title,body) in enumerate(proposals,1):
            AgendaItem.objects.create(assembly=a,position=i,title=title,body=body,proposal_hash=digest({'text':body}),rule_kind='SPECIAL' if i==3 else 'SIMPLE')
        self.stdout.write('Simulado criado com sete associados fictícios.')
