"""Organization administration: member registry, assembly drafts, agenda and publication."""

import csv
import io
import secrets
import uuid

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction

from .domain import RuleError, digest
from .models import AgendaItem, AgendaOption, Assembly, Elector, Member
from .services import audit, server_time

MAX_IMPORT_ROWS = 10000
MAX_IMPORT_BYTES = 2 * 1024 * 1024
MAX_OPTIONS = 20
TRUE_WORDS = {'1', 'true', 'yes', 'y', 'sim', 's', 'x'}
FALSE_WORDS = {'0', 'false', 'no', 'n', 'nao', 'não'}


def require_admin(actor):
    if not actor.is_admin:
        raise RuleError('ADMIN_REQUIRED', 'Esta ação é reservada à administração da organização.', 403)
    return actor.organization


def member_row(m):
    return {
        'id': str(m.id),
        'name': m.full_name,
        'email': m.email,
        'number': m.mb_number,
        'can_vote': m.can_vote,
        'can_speak': m.can_speak,
        'is_admin': m.is_admin,
        'simulation': m.issuer == 'demo:local',
        'identity_linked': bool(m.subject) and m.issuer != 'demo:local',
    }


def organization_overview(actor):
    org = require_admin(actor)
    return {
        'id': str(org.id),
        'name': org.name,
        'email_domain': org.email_domain,
        'members': [member_row(m) for m in org.members.order_by('full_name')],
        'assemblies': [
            {'id': str(a.id), 'code': a.code, 'title': a.title, 'state': a.state}
            for a in org.assemblies.order_by('-first_call_at')
        ],
    }


def parse_flag(value, default, line, column, errors):
    word = (value or '').strip().lower()
    if not word:
        return default
    if word in TRUE_WORDS:
        return True
    if word in FALSE_WORDS:
        return False
    errors.append({'line': line, 'error': f'Valor inválido em {column}: use sim ou não.'})
    return default


def import_members(actor, text, simulation):
    """Creates or updates members from CSV. Any error rejects the whole file and names the line."""
    org = require_admin(actor)
    if len(text.encode()) > MAX_IMPORT_BYTES:
        raise RuleError('IMPORT_TOO_LARGE', 'O arquivo excede 2 MB.', 413)
    reader = csv.DictReader(io.StringIO(text.lstrip('﻿')))
    columns = {c.strip().lower() for c in (reader.fieldnames or [])}
    missing = {'name', 'email', 'member_number'} - columns
    if missing:
        raise RuleError(
            'IMPORT_COLUMNS', 'Colunas obrigatórias ausentes: ' + ', '.join(sorted(missing)) + '.', 422
        )
    rows, errors, seen_numbers, seen_emails = [], [], set(), set()
    for line, raw in enumerate(reader, start=2):
        if line - 1 > MAX_IMPORT_ROWS:
            raise RuleError('IMPORT_TOO_LARGE', f'O arquivo excede {MAX_IMPORT_ROWS} associados.', 413)
        row = {(k or '').strip().lower(): (v or '').strip() for k, v in raw.items()}
        name, email, number = row.get('name', ''), row.get('email', '').lower(), row.get('member_number', '')
        if not name or len(name) > 200:
            errors.append({'line': line, 'error': 'Nome ausente ou com mais de 200 caracteres.'})
        if not number or len(number) > 32:
            errors.append(
                {'line': line, 'error': 'Número de associado ausente ou com mais de 32 caracteres.'}
            )
        try:
            validate_email(email)
            if email.split('@')[1] != org.email_domain:
                errors.append({'line': line, 'error': f'O e-mail deve terminar em @{org.email_domain}.'})
        except ValidationError:
            errors.append({'line': line, 'error': 'E-mail inválido.'})
        if number in seen_numbers:
            errors.append({'line': line, 'error': 'Número de associado repetido no arquivo.'})
        if email in seen_emails:
            errors.append({'line': line, 'error': 'E-mail repetido no arquivo.'})
        seen_numbers.add(number)
        seen_emails.add(email)
        rows.append(
            {
                'line': line,
                'name': name,
                'email': email,
                'number': number,
                'can_vote': parse_flag(row.get('can_vote'), True, line, 'can_vote', errors),
                'can_speak': parse_flag(row.get('can_speak'), True, line, 'can_speak', errors),
                'is_admin': parse_flag(row.get('is_admin'), False, line, 'is_admin', errors),
            }
        )
    if not rows and not errors:
        raise RuleError('IMPORT_EMPTY', 'O arquivo não tem associados.', 422)
    with transaction.atomic():
        existing = {m.mb_number: m for m in org.members.select_for_update().select_related('user')}
        for r in rows:
            current = existing.get(r['number'])
            owner = (
                Member.objects.filter(email=r['email']).exclude(pk=current.pk if current else None).first()
            )
            if owner:
                errors.append({'line': r['line'], 'error': 'E-mail já pertence a outro associado.'})
            if current and current.email != r['email'] and current.subject and current.issuer != 'demo:local':
                errors.append(
                    {
                        'line': r['line'],
                        'error': 'Não é possível trocar o e-mail de uma identidade já vinculada.',
                    }
                )
        if errors:
            errors.sort(key=lambda e: e['line'])
            raise RuleError('IMPORT_INVALID', errors, 422)
        created = updated = 0
        for r in rows:
            current = existing.get(r['number'])
            if current:
                current.full_name = r['name']
                current.can_vote, current.can_speak, current.is_admin = (
                    r['can_vote'],
                    r['can_speak'],
                    r['is_admin'],
                )
                if current.email != r['email']:
                    current.email = r['email']
                    current.user.username = current.user.email = r['email']
                    current.user.save(update_fields=['username', 'email'])
                current.save(update_fields=['full_name', 'can_vote', 'can_speak', 'is_admin', 'email'])
                updated += 1
                continue
            user = User.objects.create(username=r['email'], email=r['email'])
            user.set_unusable_password()
            user.save(update_fields=['password'])
            Member.objects.create(
                organization=org,
                user=user,
                mb_number=r['number'],
                full_name=r['name'],
                email=r['email'],
                issuer='demo:local' if simulation else '',
                subject='import-' + uuid.uuid4().hex if simulation else '',
                can_vote=r['can_vote'],
                can_speak=r['can_speak'],
                is_admin=r['is_admin'],
            )
            created += 1
    return {'created': created, 'updated': updated, 'simulation': simulation}


def org_member(org, member_id, role):
    member = Member.objects.filter(pk=member_id, organization=org).first()
    if not member:
        raise RuleError('INVALID_OFFICER', f'{role} deve ser associado desta organização.', 422)
    return member


def draft(actor, assembly_id):
    org = require_admin(actor)
    a = Assembly.objects.select_for_update().filter(pk=assembly_id, organization=org).first()
    if not a:
        raise RuleError('NOT_FOUND', 'Assembleia não encontrada.', 404)
    if a.state != 'DRAFT':
        raise RuleError('NOT_DRAFT', 'Só é possível editar uma assembleia em rascunho.')
    return a


def draft_detail(actor, assembly_id):
    org = require_admin(actor)
    a = (
        Assembly.objects.filter(pk=assembly_id, organization=org)
        .select_related('president', 'secretary')
        .first()
    )
    if not a:
        raise RuleError('NOT_FOUND', 'Assembleia não encontrada.', 404)
    return {
        'id': str(a.id),
        'code': a.code,
        'title': a.title,
        'state': a.state,
        'first_call_at': a.first_call_at.isoformat(),
        'second_call_at': a.second_call_at.isoformat(),
        'president': {'id': str(a.president_id), 'name': a.president.full_name},
        'secretary': {'id': str(a.secretary_id), 'name': a.secretary.full_name},
        'agenda': [
            {
                'id': str(i.id),
                'position': i.position,
                'title': i.title,
                'body': i.body,
                'rule': i.rule_kind,
                'voting_mode': i.voting_mode,
                'options': [o.label for o in i.options.all()],
            }
            for i in a.agenda.prefetch_related('options')
        ],
    }


@transaction.atomic
def create_assembly(actor, title, first_call_at, second_call_at, president_id, secretary_id):
    org = require_admin(actor)
    president = org_member(org, president_id, 'A presidência')
    secretary = org_member(org, secretary_id, 'A secretaria')
    if president.id == secretary.id:
        raise RuleError('INVALID_OFFICER', 'Presidência e secretaria devem ser pessoas diferentes.', 422)
    if second_call_at <= first_call_at:
        raise RuleError('CALL_ORDER', 'A segunda convocação deve ser posterior à primeira.', 422)
    a = Assembly.objects.create(
        organization=org,
        code='ASM-' + secrets.token_hex(4).upper(),
        title=title,
        state='DRAFT',
        is_demo=True,
        president=president,
        secretary=secretary,
        first_call_at=first_call_at,
        second_call_at=second_call_at,
        snapshot_hash='',
    )
    return {'id': str(a.id), 'code': a.code}


@transaction.atomic
def add_agenda_item(actor, assembly_id, title, body, rule_kind, voting_mode, options):
    a = draft(actor, assembly_id)
    labels = [o.strip() for o in options if o.strip()]
    if rule_kind == 'ELECTION':
        if voting_mode != 'SECRET':
            raise RuleError('ELECTION_IS_SECRET', 'Eleições usam sempre voto secreto.', 422)
        if not 2 <= len(labels) <= MAX_OPTIONS or len(set(labels)) != len(labels):
            raise RuleError(
                'ELECTION_OPTIONS_REQUIRED', f'Informe de 2 a {MAX_OPTIONS} opções diferentes.', 422
            )
    elif labels:
        raise RuleError('OPTIONS_NOT_ALLOWED', 'Só eleições têm opções de candidatos ou chapas.', 422)
    position = (a.agenda.order_by('-position').values_list('position', flat=True).first() or 0) + 1
    item = AgendaItem.objects.create(
        assembly=a,
        position=position,
        title=title,
        body=body,
        proposal_hash=digest({'text': body, 'options': labels} if labels else {'text': body}),
        rule_kind=rule_kind,
        voting_mode=voting_mode,
    )
    for i, label in enumerate(labels, 1):
        AgendaOption.objects.create(item=item, position=i, label=label)
    return {'id': str(item.id), 'position': position}


@transaction.atomic
def remove_agenda_item(actor, assembly_id, item_id):
    a = draft(actor, assembly_id)
    item = AgendaItem.objects.filter(pk=item_id, assembly=a).first()
    if not item:
        raise RuleError('NOT_FOUND', 'Pauta não encontrada.', 404)
    item.delete()
    for position, remaining in enumerate(a.agenda.order_by('position'), 1):
        if remaining.position != position:
            AgendaItem.objects.filter(pk=remaining.pk).update(position=position)
    return {'removed': str(item_id)}


@transaction.atomic
def publish_assembly(actor, assembly_id):
    """Freezes the electorate from the member registry and opens the assembly to its members."""
    a = draft(actor, assembly_id)
    if not a.agenda.exists():
        raise RuleError('AGENDA_REQUIRED', 'Inclua pelo menos uma pauta antes de publicar.', 422)
    members = list(a.organization.members.order_by('mb_number'))
    for m in members:
        Elector.objects.create(
            assembly=a,
            member=m,
            name=m.full_name,
            mb_number=m.mb_number,
            can_vote=m.can_vote,
            can_speak=m.can_speak,
        )
    snapshot = [
        {'id': str(m.id), 'name': m.full_name, 'number': m.mb_number, 'vote': m.can_vote} for m in members
    ]
    a.snapshot_hash = digest(snapshot)
    a.state = 'PUBLISHED'
    a.save(update_fields=['snapshot_hash', 'state'])
    audit(
        a,
        actor,
        'assembly.published',
        {
            'snapshot_hash': a.snapshot_hash,
            'electors': len(members),
            'agenda': [{'position': i.position, 'proposal_hash': i.proposal_hash} for i in a.agenda.all()],
        },
        server_time(),
    )
    return {'id': str(a.id), 'state': a.state, 'electors': len(members)}
