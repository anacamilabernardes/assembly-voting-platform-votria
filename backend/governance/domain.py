import hashlib, hmac, json
from dataclasses import dataclass
@dataclass
class RuleError(Exception):
    code: str
    detail: str
    status: int = 409
def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def institutional_email(email, allowed_domain):
    value = email.strip().lower()
    domain = allowed_domain.strip().lower().lstrip('@')
    if value.count('@') != 1 or not domain or value.split('@')[1] != domain:
        raise RuleError('DOMAIN_NOT_ALLOWED','Use an account from the configured institutional email domain.',403)
    return value
DEFAULT_DEMO_EMAIL_DOMAIN = 'demo.votria.test'
def demo_email_domain(configured_domain):
    # Fictional demo accounts follow the deployment's institutional domain when one is configured.
    return configured_domain.strip().lower().lstrip('@') or DEFAULT_DEMO_EMAIL_DOMAIN
def demo_email(number, configured_domain):
    return f'demo-participant-{number}@{demo_email_domain(configured_domain)}'
def token_hash(code,secret):
    return hmac.new(secret.encode(),code.strip().encode(),hashlib.sha256).hexdigest()
def ordinary_result(choices):
    s,n,a = (choices.count(c) for c in ('YES','NO','ABSTAIN'))
    return {'yes':s,'no':n,'abstain':a,'denominator':s+n,'outcome':'APPROVED' if s>n else 'NOT_APPROVED','tie':s==n,'rule':'SIM > NÃO'}
def quorum_required(n):
    if n < 1:
        raise RuleError('EMPTY_ELECTORATE','Colégio eleitoral vazio.',422)
    return (2*n+2)//3
