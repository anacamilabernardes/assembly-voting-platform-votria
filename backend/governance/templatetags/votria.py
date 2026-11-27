from django import template
from django.utils import timezone
from django.utils.dateparse import parse_datetime

register = template.Library()

OUTCOMES = {
    'APPROVED': 'Aprovada',
    'NOT_APPROVED': 'Não aprovada',
    'ELECTED': 'Eleita',
    'TIE': 'Empate: ninguém eleito',
    'NO_VALID_VOTES': 'Sem votos válidos',
}
CHOICES = {'YES': 'SIM', 'NO': 'NÃO', 'ABSTAIN': 'ABSTENÇÃO'}


@register.filter
def moment(value):
    parsed = parse_datetime(value or '')
    return timezone.localtime(parsed).strftime('%d/%m/%Y %H:%M:%S') if parsed else '—'


@register.filter
def outcome(value):
    return OUTCOMES.get(value, value)


@register.filter
def choice(value):
    return CHOICES.get(value, value)
