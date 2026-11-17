"""Pure admission reducer. Callers must atomically persist state before effects.

Policy/event observations are trusted collector inputs, never PR-controlled JSON.
One PR state slot plus compare-and-swap is required; this module is not a lock.
"""
import copy
import re
from pullfrog_standalone_contract import (ContractError, binding, digest,
    validate_binding, validate_request, _int, _require, _sha)

STATE_SCHEMA = 'pullfrog-standalone-state.v1'

def _authorized(actor, policy, request):
    return (type(actor) is dict and digest(actor) == digest(request['initiator'])
            and any(digest(actor) == digest(item) for item in policy.get('initiators', []))
            and 'pullfrog' not in actor.get('login', '').casefold()
            and request['repository_slug'] in policy.get('repositories', [])
            and request['policy_mode'] in policy.get('policy_modes', []))

def evaluate(request, event, policy, state=None, *, now):
    r = validate_request(request)
    _require(_int(now, 0), 'invalid_now')
    _require(type(event) is dict and type(policy) is dict, 'invalid_input')
    s = copy.deepcopy(state)
    def result(status, action, reason):
        return {'status': status, 'action': action, 'reason': reason, 'state': s,
                'binding': binding(r, head_sha=s['current_head'] if s else None)}
    if s is not None:
        _require(type(s) is dict and s.get('schema') == STATE_SCHEMA, 'invalid_state')
        _require(set(s) == {'schema', 'request', 'current_head', 'attempts', 'started_at', 'seconds', 'cost_microusd', 'deliveries', 'events', 'terminal', 'reason', 'in_flight', 'finding_digests', 'evidence_digest'}, 'invalid_state_shape')
        if digest(s.get('request')) != digest(r):
            raise ContractError('request_conflict')
        _require(_sha(s.get('current_head')) and _int(s.get('attempts'), 0, 3)
                 and _int(s.get('started_at'), 0) and _int(s.get('cost_microusd'), 0)
                 and type(s.get('deliveries')) is list and type(s.get('events')) is list
                 and type(s.get('terminal')) is bool
                 and type(s.get('in_flight')) is bool
                 and type(s.get('reason')) is str
                 and type(s.get('finding_digests')) is list
                 and all(type(v) is str and re.fullmatch('[0-9a-f]{64}', v) for v in s['finding_digests'])
                 and all(type(v) is str for v in s['deliveries'] + s['events'])
                 and len(s['deliveries']) == len(s['events']) <= 256
                 and s['attempts'] <= r['budget']['max_attempts']
                 and _int(s.get('seconds'), 0)
                 and (s.get('evidence_digest') is None or type(s.get('evidence_digest')) is str), 'invalid_state')
        _require(not s['in_flight'] or s['attempts'] > 0, 'invalid_attempt_state')
        # Only a retained event-limit stop with an unresolved writer may record
        # its trusted publication effect. This never reopens work or cancellation.
        capacity_reconciliation = (s['reason'] == 'event_limit' and s['in_flight']
                                   and len(s['deliveries']) == 256
                                   and event.get('kind') == 'publication_completed')
        if s['terminal'] and not capacity_reconciliation:
            return result('terminal', 'none', s['reason'])
    publication = s is not None and event.get('kind') == 'publication_completed'
    # Reconciliation records an already-observed effect, never authorizes work.
    # Validate and bind that effect before applying wall-clock stop gates.
    if not publication and not r['issued_at'] <= now < r['expires_at']:
        if s:
            s.update(terminal=True, reason='request_expired')
        return result('blocked', 'none', 'request_expired')
    delivery = event.get('delivery_id')
    _require(type(delivery) is str and re.fullmatch('[A-Za-z0-9._:-]{1,200}', delivery), 'invalid_delivery')
    kind = event.get('kind')
    if s is None:
        if not _authorized(event.get('actor'), policy, r):
            return result('ignored', 'none', 'unauthorized_initiator')
        explicit = kind == 'issue_comment' and event.get('command') == '/pr-automation run'
        manual = kind == 'workflow_dispatch' and event.get('task') == r['task']
        if not (explicit or manual):
            return result('ignored', 'none', 'explicit_request_required')
        if event.get('head_sha') != r['head_sha']:
            return result('blocked', 'none', 'stale_head')
        s = dict(schema=STATE_SCHEMA, request=r, current_head=r['head_sha'], attempts=0,
                 started_at=now, seconds=0, cost_microusd=0, deliveries=[], events=[],
                 terminal=False, reason='', in_flight=False, finding_digests=[],
                 evidence_digest=None)
    if kind in ('issue_comment', 'workflow_dispatch') and not _authorized(event.get('actor'), policy, r):
        return result('ignored', 'none', 'unauthorized_initiator')
    fingerprint = digest({k: v for k, v in event.items() if k != 'delivery_id'})
    if delivery in s['deliveries'] or fingerprint in s['events']:
        return result('ignored', 'none', 'duplicate_event')
    at_capacity = len(s['deliveries']) >= 256
    if at_capacity and not publication:
        s.update(terminal=True, reason='event_limit')
        return result('terminal', 'none', s['reason'])
    # Preserve the bounded audit prefix unchanged at capacity. The controller
    # journals the exact receipt; in_flight=False prevents another application.
    if not at_capacity:
        s['deliveries'].append(delivery)
        s['events'].append(fingerprint)
    if not publication and (now < s['started_at'] or now - s['started_at'] >= r['budget']['max_seconds']):
        s.update(terminal=True, reason='time_exhausted')
        return result('terminal', 'none', s['reason'])
    if kind in ('decision_completed', 'worker_failed'):
        observation = event.get('observation', {})
        _require(type(observation) is dict, 'invalid_observation')
        validate_binding(observation.get('binding'), r, head_sha=s['current_head'])
        if not s['in_flight']:
            return result('ignored', 'none', 'no_active_attempt')
        if kind == 'decision_completed' and observation.get('status') == 'ok' and observation.get('outcome') == 'implement':
            return result('admitted', 'implement', 'decision_implement')
        s.update(terminal=True, reason='worker_failed' if kind == 'worker_failed' else 'decision_paused')
        return result('terminal', 'reconcile' if kind == 'worker_failed' else 'none', s['reason'])
    if kind == 'publication_completed':
        # Receipt must be obtained/reconciled by trusted C publisher, not webhook text.
        receipt = event.get('observation', {})
        _require(type(receipt) is dict, 'invalid_receipt')
        validate_binding(receipt.get('binding'), r, head_sha=s['current_head'])
        if not s['in_flight'] or receipt.get('status') != 'published' or not _sha(receipt.get('result_head_sha')) or not re.fullmatch('[0-9a-f]{64}', str(receipt.get('publication_plan_digest', ''))):
            return result('blocked', 'reconcile', 'invalid_publication_receipt')
        usage = receipt.get('usage')
        if (type(usage) is not dict or not all(_int(usage.get(k), 0) for k in ('attempts', 'seconds', 'cost_microusd'))
                or usage['attempts'] != s['attempts'] or usage['seconds'] < s['seconds']
                or usage['cost_microusd'] < s['cost_microusd']):
            return result('blocked', 'reconcile', 'usage_unknown_or_regressed')
        s['cost_microusd'] = usage['cost_microusd']
        s['seconds'] = max(usage['seconds'], now - s['started_at'])
        s.update(current_head=receipt['result_head_sha'], in_flight=False, evidence_digest=None)
        stop = ('event_limit' if at_capacity or s['terminal'] else
                'request_expired' if not r['issued_at'] <= now < r['expires_at'] else
                'time_exhausted' if now < s['started_at'] or s['seconds'] >= r['budget']['max_seconds'] else
                'cost_exhausted' if s['cost_microusd'] > r['budget']['max_cost_microusd'] else None)
        if stop:
            s.update(terminal=True, reason=stop)
            return result('terminal', 'none', s['reason'])
        return result('waiting', 'review', 'successor_head_bound')
    if event.get('head_sha') != s['current_head']:
        return result('blocked', 'reconcile', 'unapproved_head_change')
    if kind == 'cancel':
        if not _authorized(event.get('actor'), policy, r):
            return result('ignored', 'none', 'unauthorized_cancel')
        s.update(terminal=True, reason='cancelled')
        return result('terminal', 'reconcile' if s['in_flight'] else 'none', 'cancelled')
    if s['in_flight']:
        return result('waiting', 'reconcile', 'writer_in_flight')
    if kind in ('issue_comment', 'workflow_dispatch'):
        if s['attempts']:
            return result('ignored', 'none', 'already_admitted')
    elif kind == 'pullfrog_review_completed':
        evidence = event.get('observation', {})
        _require(type(evidence) is dict, 'invalid_review_evidence')
        validate_binding(evidence.get('binding'), r, head_sha=s['current_head'])
        # Collector must use D.normalize; raw webhook/check text is not evidence.
        body = {k: v for k, v in evidence.items() if k != 'evidence_digest'}
        if evidence.get('status') not in ('clean', 'findings') or evidence.get('evidence_digest') != digest(body):
            return result('blocked', 'none', 'invalid_review_evidence')
        findings = evidence.get('findings')
        if type(findings) is not list:
            return result('blocked', 'none', 'invalid_findings')
        s['evidence_digest'] = evidence['evidence_digest']
        if not findings and evidence.get('status') != 'clean':
            return result('blocked', 'none', 'invalid_clean_evidence')
        if not findings:
            checks = event.get('checks', {})
            required = ['ci', 'destination-guard'] + (['speculoos'] if r['policy_mode'] == 'speculoos' else [])
            if any(checks.get(k) != 'success' for k in required):
                return result('blocked', 'none', 'required_evidence_missing')
            s.update(terminal=True, reason='ready_for_human')
            return result('terminal', 'none', s['reason'])
        findings_digest = digest(sorted(findings, key=digest))
        if findings_digest in s['finding_digests']:
            s.update(terminal=True, reason='no_progress')
            return result('terminal', 'none', s['reason'])
        s['finding_digests'].append(findings_digest)
    else:
        return result('ignored', 'none', 'non_advancing_event')
    if s['attempts'] >= r['budget']['max_attempts'] or (s['attempts'] and (s['cost_microusd'] > r['budget']['max_cost_microusd'] or
            0 < r['budget']['max_cost_microusd'] == s['cost_microusd'])):
        s.update(terminal=True, reason='budget_exhausted')
        return result('terminal', 'none', s['reason'])
    s['attempts'] += 1
    s['in_flight'] = True
    return result('admitted', 'decide', 'attempt_reserved')
