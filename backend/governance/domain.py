import hashlib, hmac, json
from dataclasses import dataclass
@dataclass
class RuleError(Exception):
    code: str
    detail: str
    status: int = 409
def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def institutional_email(email):
    value = email.strip().lower()
    if value.count('@') != 1 or value.split('@')[1] != 'mensa.org.br':
        raise RuleError('DOMAIN_NOT_ALLOWED','Use sua conta pessoal @mensa.org.br.',403)
    return value
def token_hash(code,secret):
    return hmac.new(secret.encode(),code.strip().encode(),hashlib.sha256).hexdigest()
def ordinary_result(choices):
    s,n,a = (choices.count(c) for c in ('YES','NO','ABSTAIN'))
    return {'yes':s,'no':n,'abstain':a,'denominator':s+n,'outcome':'APPROVED' if s>n else 'NOT_APPROVED','tie':s==n,'rule':'SIM > NÃO'}
def quorum_required(n):
    if n < 1:
        raise RuleError('EMPTY_ELECTORATE','Colégio eleitoral vazio.',422)
    return (2*n+2)//3
