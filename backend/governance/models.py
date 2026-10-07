import uuid
from django.conf import settings
from django.db import models
from django.db.models import Q,F
class UUIDModel(models.Model):
    id = models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    class Meta:
        abstract = True
class Member(UUIDModel):
    user = models.OneToOneField(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    mb_number = models.CharField(max_length=32,unique=True)
    full_name = models.CharField(max_length=200)
    email = models.EmailField(unique=True)
    issuer = models.CharField(max_length=500,blank=True)
    subject = models.CharField(max_length=200,blank=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['issuer','subject'],condition=~Q(subject=''),name='unique_oidc_identity')]
class Assembly(UUIDModel):
    code = models.CharField(max_length=40,unique=True)
    title = models.CharField(max_length=250)
    state = models.CharField(max_length=20,default='PUBLISHED')
    is_demo = models.BooleanField(default=True)
    president = models.ForeignKey(Member,on_delete=models.PROTECT,related_name='+')
    secretary = models.ForeignKey(Member,on_delete=models.PROTECT,related_name='+')
    first_call_at = models.DateTimeField()
    second_call_at = models.DateTimeField()
    installed_at = models.DateTimeField(null=True)
    closed_at = models.DateTimeField(null=True)
    installation = models.JSONField(default=dict)
    snapshot_hash = models.CharField(max_length=64)
    class Meta:
        constraints = [models.CheckConstraint(condition=~Q(president=F('secretary')),name='distinct_officers'),models.CheckConstraint(condition=Q(second_call_at__gt=F('first_call_at')),name='call_order')]
class Elector(UUIDModel):
    assembly = models.ForeignKey(Assembly,on_delete=models.PROTECT,related_name='electors')
    member = models.ForeignKey(Member,on_delete=models.PROTECT)
    name = models.CharField(max_length=200)
    mb_number = models.CharField(max_length=32)
    is_regular = models.BooleanField(default=True)
    can_vote = models.BooleanField(default=True)
    can_speak = models.BooleanField(default=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['assembly','member'],name='unique_elector')]
class ParticipationSession(UUIDModel):
    assembly = models.ForeignKey(Assembly,on_delete=models.PROTECT)
    member = models.ForeignKey(Member,on_delete=models.PROTECT)
    auth_session_key = models.CharField(max_length=64)
    entered_at = models.DateTimeField()
    last_seen_at = models.DateTimeField()
    lease_until = models.DateTimeField()
    ended_at = models.DateTimeField(null=True)
    end_reason = models.CharField(max_length=30,blank=True)
    declaration_hash = models.CharField(max_length=64)
    protocol = models.CharField(max_length=80,unique=True)
    class Meta:
        indexes = [models.Index(fields=['assembly','member','lease_until'])]
        constraints = [models.UniqueConstraint(fields=['assembly','member','auth_session_key'],condition=Q(ended_at__isnull=True),name='unique_live_session')]
class PresenceInterval(UUIDModel):
    assembly = models.ForeignKey(Assembly,on_delete=models.PROTECT)
    member = models.ForeignKey(Member,on_delete=models.PROTECT)
    entered_at = models.DateTimeField()
    exited_at = models.DateTimeField(null=True)
    reason = models.CharField(max_length=30,blank=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['assembly','member'],condition=Q(exited_at__isnull=True),name='one_open_interval')]
class AgendaItem(UUIDModel):
    assembly = models.ForeignKey(Assembly,on_delete=models.PROTECT,related_name='agenda')
    position = models.PositiveIntegerField()
    title = models.CharField(max_length=250)
    body = models.TextField()
    proposal_hash = models.CharField(max_length=64)
    rule_kind = models.CharField(max_length=30,default='SIMPLE')
    class Meta:
        ordering = ['position']
        constraints = [models.UniqueConstraint(fields=['assembly','position'],name='unique_agenda_position')]
class Proxy(UUIDModel):
    assembly = models.ForeignKey(Assembly,on_delete=models.PROTECT)
    grantor = models.ForeignKey(Member,on_delete=models.PROTECT,related_name='+')
    representative = models.ForeignKey(Member,on_delete=models.PROTECT,related_name='+')
    status = models.CharField(max_length=20,default='ISSUED')
    scope = models.ManyToManyField(AgendaItem)
    token_hmac = models.CharField(max_length=64,unique=True)
    token_expires_at = models.DateTimeField()
    issued_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True)
    revoked_at = models.DateTimeField(null=True)
    slot = models.PositiveSmallIntegerField(null=True)
    instrument = models.JSONField()
    instrument_hash = models.CharField(max_length=64)
    class Meta:
        constraints = [
            models.CheckConstraint(condition=~Q(grantor=F('representative')),name='no_self_proxy'),
            models.CheckConstraint(condition=Q(slot__isnull=True)|Q(slot__in=[1,2]),name='proxy_slot_range'),
            models.CheckConstraint(condition=~Q(status='ACCEPTED')|Q(slot__in=[1,2]),name='accepted_proxy_slot'),
            models.UniqueConstraint(fields=['assembly','grantor'],condition=Q(status__in=['ISSUED','ACCEPTED']),name='one_active_proxy_per_grantor'),
            models.UniqueConstraint(fields=['assembly','representative','slot'],condition=Q(status='ACCEPTED'),name='unique_proxy_slot')]
class MailboxMessage(UUIDModel):
    recipient = models.ForeignKey(Member,on_delete=models.PROTECT)
    assembly = models.ForeignKey(Assembly,on_delete=models.PROTECT)
    subject = models.CharField(max_length=200)
    ciphertext = models.TextField()
    created_at = models.DateTimeField()
    expires_at = models.DateTimeField()
class ClaimFailure(UUIDModel):
    member = models.ForeignKey(Member,on_delete=models.PROTECT)
    occurred_at = models.DateTimeField()
class Round(UUIDModel):
    assembly = models.ForeignKey(Assembly,on_delete=models.PROTECT)
    agenda_item = models.ForeignKey(AgendaItem,on_delete=models.PROTECT)
    state = models.CharField(max_length=20,default='OPEN')
    proposal_text = models.TextField()
    proposal_hash = models.CharField(max_length=64)
    opened_at = models.DateTimeField()
    closes_at = models.DateTimeField()
    closed_at = models.DateTimeField(null=True)
    result = models.JSONField(default=dict)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['assembly'],condition=Q(state='OPEN'),name='one_open_round')]
class Ballot(UUIDModel):
    round = models.ForeignKey(Round,on_delete=models.PROTECT,related_name='ballots')
    owner = models.ForeignKey(Member,on_delete=models.PROTECT,related_name='+')
    cast_by = models.ForeignKey(Member,on_delete=models.PROTECT,related_name='+')
    owner_name = models.CharField(max_length=200)
    executor_name = models.CharField(max_length=200)
    choice = models.CharField(max_length=10)
    proxy = models.ForeignKey(Proxy,null=True,on_delete=models.PROTECT)
    accepted_at = models.DateTimeField()
    proposal_hash = models.CharField(max_length=64)
    protocol = models.CharField(max_length=80,unique=True)
    receipt_hash = models.CharField(max_length=64)
    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['round','owner'],name='one_ballot_per_owner'),
            models.CheckConstraint(condition=Q(choice__in=['YES','NO','ABSTAIN']),name='valid_choice'),
            models.CheckConstraint(condition=(Q(owner=F('cast_by'))&Q(proxy__isnull=True))|(~Q(owner=F('cast_by'))&Q(proxy__isnull=False)),name='ballot_execution_mode')]
class FloorRequest(UUIDModel):
    assembly = models.ForeignKey(Assembly,on_delete=models.PROTECT)
    member = models.ForeignKey(Member,on_delete=models.PROTECT)
    kind = models.CharField(max_length=20)
    state = models.CharField(max_length=20,default='WAITING')
    requested_at = models.DateTimeField()
    reason = models.CharField(max_length=500,blank=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['assembly','member'],condition=Q(state__in=['WAITING','GRANTED']),name='one_floor_request')]
class AuditEvent(UUIDModel):
    assembly = models.ForeignKey(Assembly,on_delete=models.PROTECT,related_name='events')
    actor = models.ForeignKey(Member,null=True,on_delete=models.PROTECT)
    sequence = models.PositiveIntegerField()
    action = models.CharField(max_length=80)
    payload = models.JSONField()
    occurred_at = models.DateTimeField()
    previous_hash = models.CharField(max_length=64,blank=True)
    event_hash = models.CharField(max_length=64)
    class Meta:
        ordering = ['sequence']
        constraints = [models.UniqueConstraint(fields=['assembly','sequence'],name='unique_audit_sequence')]
class CommandReceipt(UUIDModel):
    assembly = models.ForeignKey(Assembly,on_delete=models.PROTECT)
    actor = models.ForeignKey(Member,on_delete=models.PROTECT)
    action = models.CharField(max_length=100)
    key = models.CharField(max_length=100)
    request_hash = models.CharField(max_length=64)
    response = models.JSONField()
    class Meta:
        constraints = [models.UniqueConstraint(fields=['assembly','actor','action','key'],name='unique_command_key')]
