#!/usr/bin/env python3
"""Pure standalone plans, never providers or remote writes.

Admission/config, validator seals and observations MUST come from trusted jobs.
Digests bind data; they are not authentication or durable writer locks.
"""
import copy
import pullfrog_standalone_contract as contract
import pullfrog_cloud_remediation as remediation
import pullfrog_destination_guard as guard

WORKER_SCHEMA = 'pullfrog-standalone-worker-plan.v1'
PUBLICATION_SCHEMA = 'pullfrog-standalone-publication-plan.v1'


class WorkerError(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def require(condition, code):
    if not condition:
        raise WorkerError(code)


def integer(value):
    return type(value) is int and value >= 0


def checked(value):
    require(isinstance(value, dict), 'invalid_plan')
    body = {k: v for k, v in value.items() if k != 'plan_digest'}
    require(value.get('plan_digest') == contract.digest(body), 'plan_digest_mismatch')
    return body


def seal(value):
    value = copy.deepcopy(value)
    value['plan_digest'] = contract.digest(value)
    return value


def current(request, binding, head, now):
    contract.validate_request(request, now=now)
    require(type(now) is int and request['issued_at'] <= now < request['expires_at'], 'request_expired')
    contract.validate_binding(binding, request, head_sha=head)


def prepare(request, evidence, decision, *, current_head_sha, now):
    """Caller atomically persists reserved attempt before execution, via admission."""
    b = contract.binding(request, head_sha=current_head_sha)
    current(request, b, current_head_sha, now)
    contract.validate_binding(evidence.get('binding'), request, head_sha=current_head_sha)
    contract.validate_binding(decision.get('binding'), request, head_sha=current_head_sha)
    ed = contract.digest({k: v for k, v in evidence.items() if k != 'evidence_digest'})
    require(evidence.get('evidence_digest', ed) == ed, 'evidence_digest_mismatch')
    require(decision.get('evidence_digest') == ed, 'decision_evidence_mismatch')
    require(decision.get('status') == 'ok' and decision.get('outcome') == 'implement', 'decision_not_implement')
    require(isinstance(decision.get('provenance'), dict) and bool(decision['provenance']), 'missing_decision_provenance')
    w = evidence.get('worker', {})
    require(w.get('admitted_binding') == b and w.get('claim_status') == 'active', 'missing_admission')
    require(isinstance(w.get('claim_id'), str) and 0 < len(w['claim_id']) <= 200, 'missing_claim')
    usage = w.get('usage', {})
    require(all(integer(usage.get(k)) for k in ('attempts', 'seconds', 'cost_microusd')), 'unknown_usage')
    budget = request['budget']
    observed_at = w.get('observed_at', now)
    require(type(observed_at) is int and 0 <= observed_at <= now, 'invalid_usage_observation_time')
    usage = {**usage, 'seconds': usage['seconds'] + now - observed_at}
    absolute_deadline = w.get('deadline', min(request['expires_at'], now + budget['max_seconds'] - usage['seconds']))
    require(type(absolute_deadline) is int and now < absolute_deadline <= request['expires_at'], 'budget_exhausted')
    require(usage['attempts'] < budget['max_attempts'] and usage['seconds'] < budget['max_seconds'] and usage['cost_microusd'] <= budget['max_cost_microusd'], 'budget_exhausted')
    config = w.get('execution', {})
    require(all(isinstance(config.get(k), str) and 0 < len(config[k]) <= 200 for k in ('executor_id', 'validator_id', 'publisher_id', 'recipe_id')), 'missing_trusted_execution')
    require(config['executor_id'] != config['publisher_id'] and config['validator_id'] != config['executor_id'], 'credential_separation_required')
    require(config.get('worker_write_credentials') is False, 'worker_credentials_forbidden')
    tests = config.get('required_tests')
    require(isinstance(tests, list) and bool(tests) and all(isinstance(t, str) and t for t in tests) and len(set(tests)) == len(tests), 'missing_trusted_tests')
    identity = copy.deepcopy(w.get('destination', {}))
    require(guard.evaluate_destination(identity)['status'] == 'destination_allowed', 'destination_blocked')
    require(identity.get('slug') == request['repository_slug'] and identity.get('pr_number') == request['pr_number'] and all(identity.get(k) == request[k] for k in ('base_ref', 'base_sha', 'head_ref')) and identity.get('head_sha') == current_head_sha, 'destination_mismatch')
    return seal({'schema': WORKER_SCHEMA, 'binding': b, 'evidence_digest': ed,
                 'decision_digest': contract.digest(decision), 'claim_id': w['claim_id'],
                 'attempt': usage['attempts'] + 1, 'usage_before': usage,
                 'started_at': now, 'deadline': min(absolute_deadline, request['expires_at'], now + budget['max_seconds'] - usage['seconds']),
                 'cost_remaining_microusd': budget['max_cost_microusd'] - usage['cost_microusd'],
                 'execution': config, 'destination': identity,
                 'allowed_paths': request['allowed_paths'], 'merge_allowed': False})


def validate_candidate(request, plan, candidate, *, current_head_sha, now):
    p = checked(plan)
    require(p.get('schema') == WORKER_SCHEMA, 'invalid_worker_plan')
    current(request, p['binding'], current_head_sha, now)
    require(p['started_at'] <= now < p['deadline'], 'budget_exhausted')
    contract.validate_binding(candidate.get('binding'), request, head_sha=current_head_sha)
    require(candidate.get('plan_digest') == plan['plan_digest'] and candidate.get('evidence_digest') == p['evidence_digest'], 'candidate_plan_mismatch')
    require(candidate.get('validator_id') == p['execution']['validator_id'] and candidate.get('recipe_id') == p['execution']['recipe_id'], 'artifact_provenance_mismatch')
    s = candidate.get('seal', {})
    require(s.get('schema') == 'pullfrog-standalone-patch-seal.v1' and s.get('source_head_sha') == current_head_sha, 'invalid_patch_seal')
    require(isinstance(s.get('patch_digest'), str) and remediation.DIGEST_RE.fullmatch(s['patch_digest']) and type(s.get('patch_bytes')) is int and 0 < s['patch_bytes'] <= remediation.MAX_PATCH_BYTES, 'invalid_patch_seal')
    paths = s.get('changed_paths')
    require(isinstance(paths, list) and paths and all(isinstance(x, str) and guard._valid_path(x) for x in paths) and paths == sorted(set(paths)), 'invalid_changed_paths')
    require(s.get('changed_paths_digest') == contract.digest(paths), 'paths_digest_mismatch')
    require(all(any(path == prefix.rstrip('/') or path.startswith(prefix.rstrip('/') + '/') for prefix in request['allowed_paths']) for path in paths), 'scope_violation')
    require(not any(path.startswith('scripts/github/pullfrog_standalone_') for path in paths), 'authority_path_forbidden')
    destination = {'destination_repository_slug': request['repository_slug'], 'destination_ref': request['head_ref'], 'destination_sha': current_head_sha}
    receipt = guard.evaluate_guard({'schema': guard.INPUT_SCHEMA, 'expected': p['destination'], 'observed': candidate.get('observed_destination'), 'request': {**destination, 'changed_paths': paths, 'attempt': p['attempt']}, 'first_attempt': destination})
    require(receipt['status'] == 'allowed', 'destination_blocked')
    tests = candidate.get('tests', {})
    require(tests.get('patch_digest') == s['patch_digest'] and tests.get('source_head_sha') == current_head_sha and tests.get('recipe_id') == p['execution']['recipe_id'], 'test_binding_mismatch')
    require(isinstance(tests.get('results'), dict) and all(tests['results'].get(t) == 'passed' for t in p['execution']['required_tests']), 'tests_not_passed')
    cost = candidate.get('cost_microusd')
    require(integer(cost) and cost <= p['cost_remaining_microusd'], 'unknown_or_excess_cost')
    result = candidate.get('result_head_sha')
    require(isinstance(result, str) and remediation.SHA_RE.fullmatch(result) and result != current_head_sha and candidate.get('parent_sha') == current_head_sha, 'invalid_commit_parent')
    return seal({'schema': PUBLICATION_SCHEMA, 'binding': p['binding'], 'evidence_digest': p['evidence_digest'], 'worker_plan_digest': plan['plan_digest'], 'claim_id': p['claim_id'], 'attempt': p['attempt'], 'candidate_digest': contract.digest(candidate), 'patch_digest': s['patch_digest'], 'changed_paths_digest': s['changed_paths_digest'], 'result_head_sha': result, 'parent_sha': current_head_sha, 'destination': destination, 'destination_guard': receipt, 'publisher_id': p['execution']['publisher_id'], 'usage_after': {'attempts': p['attempt'], 'seconds': p['usage_before']['seconds'] + now - p['started_at'], 'cost_microusd': p['usage_before']['cost_microusd'] + cost}, 'merge_allowed': False, 'retry_requires_reconciliation': True})


def reconcile_publication(request, plan, observation):
    """Unknown/absent effects never authorize blind retry, even after runner loss."""
    p = checked(plan)
    require(p.get('schema') == PUBLICATION_SCHEMA, 'invalid_publication_plan')
    contract.validate_request(request)
    contract.validate_binding(p['binding'], request, head_sha=p['parent_sha'])
    contract.validate_binding(observation.get('binding'), request, head_sha=p['parent_sha'])
    require(observation.get('plan_digest') == plan['plan_digest'], 'observation_plan_mismatch')
    status = 'reconcile_required'
    if observation.get('read_status') == 'ok':
        require(observation.get('repository_slug') == request['repository_slug'] and observation.get('head_ref') == request['head_ref'], 'observation_destination_mismatch')
        if observation.get('head_sha') == p['result_head_sha']:
            require(observation.get('parent_sha') == p['parent_sha'] and observation.get('patch_digest') == p['patch_digest'], 'publication_effect_mismatch')
            status = 'published'
        elif observation.get('head_sha') == p['parent_sha']:
            if observation.get('publisher_quiescent') is True and observation.get('effect_absent') is True:
                status = 'not_published'
        else:
            status = 'conflict'
    return {'schema': 'pullfrog-standalone-publication-receipt.v1', 'status': status, 'binding': p['binding'], 'evidence_digest': p['evidence_digest'], 'publication_plan_digest': plan['plan_digest'], 'result_head_sha': p['result_head_sha'] if status == 'published' else None, 'usage': copy.deepcopy(p['usage_after']), 'retry_allowed': False, 'merge_allowed': False}
