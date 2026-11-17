"""Provider-free immutable standalone request and exact-head bindings."""
import copy
import hashlib
import json
import re
from pullfrog_cycle_contract import _canonical_slug, _valid_branch

SCHEMA = "pullfrog-standalone-request.v1"

class ContractError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

def _require(ok, code):
    if not ok:
        raise ContractError(code)

def _int(value, low, high=2**63-1):
    return type(value) is int and low <= value <= high

def _text(value, limit):
    return type(value) is str and 0 < len(value) <= limit and not any(ord(c) < 32 for c in value)

def _sha(value):
    return type(value) is str and re.fullmatch('[0-9a-f]{40}', value) is not None

def validate_request(request, *, now=None):
    _require(type(request) is dict, 'invalid_request')
    r = request
    _require(r.get('schema') == SCHEMA, 'invalid_schema')
    slug = r.get('repository_slug')
    _require(type(slug) is str and _canonical_slug(slug) == slug and bool(slug), 'invalid_repository')
    _require(_int(r.get('pr_number'), 1), 'invalid_pr_number')
    _require(type(r.get('request_id')) is str and re.fullmatch('[A-Za-z0-9._:-]{1,128}', r['request_id']), 'invalid_request_id')
    actor = r.get('initiator')
    _require(type(actor) is dict and _int(actor.get('account_id'), 1) and _text(actor.get('login'), 100) and actor.get('type') in ('User', 'Bot'), 'invalid_initiator')
    for key in ('base_sha', 'head_sha'):
        _require(_sha(r.get(key)), 'invalid_' + key)
    for key in ('base_ref', 'head_ref'):
        _require(type(r.get(key)) is str and len(r[key]) <= 255 and _valid_branch(r[key]), 'invalid_' + key)
    task = r.get('task')
    _require(type(task) is str and 0 < len(task) <= 16000 and bool(task.strip())
             and not any(ord(c) < 32 and c not in '\t\r\n' for c in task), 'invalid_task')
    paths = r.get('allowed_paths')
    _require(type(paths) is list and 0 < len(paths) <= 100, 'invalid_allowed_paths')
    for path in paths:
        _require(_text(path, 500) and not path.startswith('/') and not any(c in path for c in ('\\', ':', '*', '?', '[')) and all(p not in ('', '.', '..', '.git') for p in path.rstrip('/').split('/')), 'invalid_allowed_path')
    _require(_int(r.get('issued_at'), 0) and _int(r.get('expires_at'), 1) and r['issued_at'] < r['expires_at'], 'invalid_expiry')
    _require(r.get('policy_mode') in ('standalone', 'speculoos'), 'invalid_policy_mode')
    budget = r.get('budget')
    _require(type(budget) is dict and _int(budget.get('max_attempts'), 1, 3) and _int(budget.get('max_seconds'), 1, 1800) and _int(budget.get('max_cost_microusd'), 0), 'invalid_budget')
    if now is not None:
        _require(_int(now, 0), 'invalid_now')
        _require(r['issued_at'] <= now < r['expires_at'], 'request_not_fresh')
    return copy.deepcopy(r)

def binding(request, *, head_sha=None):
    r = validate_request(request)
    head = r['head_sha'] if head_sha is None else head_sha
    _require(_sha(head), 'invalid_head_sha')
    return {k: r[k] for k in ('repository_slug', 'pr_number', 'request_id')} | {'request_digest': digest(r), 'head_sha': head}

def validate_binding(value, request, *, head_sha=None):
    expected = binding(request, head_sha=head_sha)
    _require(type(value) is dict and set(value) == set(expected) and all(type(value[k]) is type(expected[k]) and value[k] == expected[k] for k in expected), 'binding_mismatch')
    return copy.deepcopy(expected)
