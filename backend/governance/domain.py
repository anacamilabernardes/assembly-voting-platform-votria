import hashlib
import hmac
import json
import re
from dataclasses import dataclass


@dataclass
class RuleError(Exception):
    code: str
    detail: str
    status: int = 409


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()
    ).hexdigest()


def institutional_email(email, allowed_domain):
    value = email.strip().lower()
    domain = allowed_domain.strip().lower().lstrip('@')
    if value.count('@') != 1 or not domain or value.split('@')[1] != domain:
        raise RuleError(
            'DOMAIN_NOT_ALLOWED', 'Use an account from the configured institutional email domain.', 403
        )
    return value


DEFAULT_DEMO_EMAIL_DOMAIN = 'demo.votria.test'


def demo_email_domain(configured_domain):
    # Fictional demo accounts follow the deployment's institutional domain when one is configured.
    return configured_domain.strip().lower().lstrip('@') or DEFAULT_DEMO_EMAIL_DOMAIN


def demo_email(number, configured_domain):
    return f'demo-participant-{number}@{demo_email_domain(configured_domain)}'


def token_hash(code, secret):
    return hmac.new(secret.encode(), code.strip().encode(), hashlib.sha256).hexdigest()


def ordinary_result(choices):
    s, n, a = (choices.count(c) for c in ('YES', 'NO', 'ABSTAIN'))
    return {
        'yes': s,
        'no': n,
        'abstain': a,
        'denominator': s + n,
        'outcome': 'APPROVED' if s > n else 'NOT_APPROVED',
        'tie': s == n,
        'rule': 'SIM > NÃO',
    }


SIMPLE_CHOICES = ('YES', 'NO', 'ABSTAIN')
BLANK = 'BLANK'
DOMAIN_PATTERN = re.compile(r'(?=.{4,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z][a-z0-9-]{1,62}')


def valid_domain(domain):
    return bool(DOMAIN_PATTERN.fullmatch(domain or ''))


def valid_choice(rule_kind, choice, options):
    """A choice is valid when it fits the item: SIM/NÃO/ABSTENÇÃO, or an option or blank in an election."""
    if rule_kind == 'ELECTION':
        return choice == BLANK or choice in {o['id'] for o in options}
    return choice in SIMPLE_CHOICES


def election_result(choices, options):
    """Plurality: the option with the most votes wins; a tie at the top elects no one."""
    counts = [{'id': o['id'], 'label': o['label'], 'votes': choices.count(o['id'])} for o in options]
    blank = choices.count(BLANK)
    top = max((c['votes'] for c in counts), default=0)
    leaders = [c for c in counts if c['votes'] == top]
    if top == 0:
        outcome, winner = 'NO_VALID_VOTES', None
    elif len(leaders) > 1:
        outcome, winner = 'TIE', None
    else:
        outcome, winner = 'ELECTED', leaders[0]
    return {
        'options': counts,
        'blank': blank,
        'valid': sum(c['votes'] for c in counts),
        'outcome': outcome,
        'winner': winner,
        'tie': outcome == 'TIE',
        'rule': 'Maioria relativa: mais votos válidos',
    }


def quorum_required(n):
    if n < 1:
        raise RuleError('EMPTY_ELECTORATE', 'Colégio eleitoral vazio.', 422)
    return (2 * n + 2) // 3
