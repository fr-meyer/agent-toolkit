"""Standalone controller seam; no provider/publisher is enabled by the CLI.

All inputs are trusted collector/policy data, not files supplied by a PR. The local
journal is atomic/CAS and restart-safe, but is NOT a hosted durable claim store.
Hosted adapters must commit/upload a checkpoint before any external effect.
"""
from __future__ import annotations
import argparse
import copy
import fcntl
import json
import math
import os
from pathlib import Path
import tempfile
import time

import pullfrog_standalone_contract as contract
import pullfrog_standalone_admission as admission
import pullfrog_standalone_decision as decision
import pullfrog_standalone_review as review
import pullfrog_standalone_worker as worker

SCHEMA = 'pullfrog-standalone-journal.v1'
MAX_BYTES = 2 * 1024 * 1024


def require(condition, code):
    if not condition:
        raise contract.ContractError(code)


def _read(path):
    require(not path.is_symlink(), 'journal_symlink_forbidden')
    with path.open('rb') as stream:
        data = stream.read(MAX_BYTES + 1)
    require(len(data) <= MAX_BYTES, 'journal_too_large')
    return json.loads(data)


class Journal:
    """One repository/PR slot; native POSIX lock + atomic fsync, no daemon."""
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def transaction(self, expected, transform):
        lock_path = self.path.with_suffix(self.path.suffix + '.lock')
        flags = os.O_RDWR | os.O_CREAT | getattr(os, 'O_NOFOLLOW', 0)
        fd = os.open(lock_path, flags, 0o600)
        with os.fdopen(fd, 'r+') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            prior = _read(self.path) if self.path.exists() else None
            actual = contract.digest(prior) if prior is not None else None
            require(expected == actual, 'state_compare_and_swap_failed')
            if prior is not None:
                require(prior.get('schema') == SCHEMA and type(prior.get('sequence')) is int
                        and prior['sequence'] > 0, 'invalid_journal')
            updated, output = transform(copy.deepcopy(prior))
            if updated == prior:
                return {'journal_digest': actual, 'output': output, 'changed': False}
            updated['schema'] = SCHEMA
            updated['sequence'] = 1 if prior is None else prior['sequence'] + 1
            updated['previous_digest'] = actual
            require(contract.digest(updated['request']) == updated['binding']['request_digest'], 'journal_request_mismatch')
            encoded = json.dumps(updated, sort_keys=True, separators=(',', ':')).encode()
            require(len(encoded) <= MAX_BYTES, 'journal_too_large')
            temp_name = None
            try:
                with tempfile.NamedTemporaryFile(dir=self.path.parent, delete=False) as temp:
                    temp_name = temp.name
                    os.fchmod(temp.fileno(), 0o600)
                    temp.write(encoded)
                    temp.flush()
                    os.fsync(temp.fileno())
                os.replace(temp_name, self.path)
                directory_fd = os.open(self.path.parent, os.O_DIRECTORY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
            finally:
                if temp_name and os.path.exists(temp_name):
                    os.unlink(temp_name)
            return {'journal_digest': contract.digest(updated), 'output': output, 'changed': True}


def advance(journal, request, event, policy, *, expected_digest, now):
    """Persist a reducer transition before returning a possibly actionable plan."""
    def transform(prior):
        if prior is not None:
            require(contract.digest(prior['request']) == contract.digest(request), 'request_conflict')
            require(prior.get('phase') not in ('decision_started', 'publication_pending', 'action_pending', 'action_started'), 'effect_requires_reconciliation')
            if prior.get('phase') == 'waiting_dependency':
                require(event.get('kind') in ('pullfrog_review_completed', 'cancel'), 'completion_event_required')
        state = prior['state'] if prior else None
        result = admission.evaluate(request, event, policy, state, now=now)
        if result['state'] is None:
            return prior, result
        updated = prior or {'request': copy.deepcopy(request), 'artifacts': {}, 'phase': 'admitted'}
        updated.update(state=result['state'], binding=result['binding'])
        if result.get('action') == 'decide':
            updated['phase'] = 'admitted'
        if result['state']['terminal']:
            updated['phase'] = 'terminal'
        return updated, result
    return journal.transaction(expected_digest, transform)


def prepare_evidence(request, state, context, execution, destination, *, now):
    """Join trusted A/D observations with C's reserved-attempt convention."""
    require(state['in_flight'] and not state['terminal'] and state['attempts'] > 0, 'no_active_attempt')
    head = state['current_head']
    deadline = min(request['expires_at'], state['started_at'] + request['budget']['max_seconds'])
    require(type(now) is int and state['started_at'] <= now < deadline, 'aggregate_time_exhausted')
    expected = {'slug': request['repository_slug'], 'head_repository_slug': request['repository_slug'],
                'pr_number': request['pr_number'], 'base_ref': request['base_ref'],
                'base_sha': request['base_sha'], 'head_ref': request['head_ref'], 'head_sha': head}
    require(type(destination) is dict and all(type(destination.get(k)) is type(v) and destination.get(k) == v
            for k, v in expected.items()), 'destination_mismatch')
    bound = contract.binding(request, head_sha=head)
    contract.validate_binding(context.get('binding'), request, head_sha=head)
    payload = copy.deepcopy(context)
    supplied = payload.pop('evidence_digest', None)
    require(supplied is None or supplied == contract.digest(payload), 'evidence_digest_mismatch')
    require('worker' not in payload, 'untrusted_worker_envelope')
    require(worker.guard.evaluate_destination(destination)['status'] == 'destination_allowed', 'destination_blocked')
    payload['worker'] = {'admitted_binding': bound, 'claim_status': 'active',
        'claim_id': contract.digest({'binding': bound, 'attempt': state['attempts']}),
        'observed_at': now, 'deadline': deadline,
        'usage': {'attempts': state['attempts'] - 1, 'seconds': max(state['seconds'], now - state['started_at']),
                  'cost_microusd': state['cost_microusd']},
        'execution': copy.deepcopy(execution), 'destination': copy.deepcopy(destination)}
    payload['evidence_digest'] = contract.digest(payload)
    return payload


def decide(journal, policy, context, execution, destination, *, expected_digest, now, provider=None, clock=None):
    """Reserve decision invocation; crashes never silently retry a provider call.

    A supplied provider is trusted injected code for fixtures/qualified adapters.
    The CLI never supplies one. No arbitrary import/command/config provider exists.
    """
    clock = clock or time.monotonic
    start = clock()
    def reserve(prior):
        require(prior is not None, 'missing_admission')
        require(prior['phase'] == 'admitted', 'decision_already_started')
        request, state = prior['request'], prior['state']
        contract.validate_request(request, now=now)
        evidence = prepare_evidence(request, state, context, execution, destination, now=now)
        state['seconds'] = max(state['seconds'], now - state['started_at'])
        prior['phase'] = 'decision_started'
        prior['artifacts']['evidence'] = evidence
        return prior, {'request': request, 'evidence': evidence}
    reservation = journal.transaction(expected_digest, reserve)
    request, evidence = reservation['output']['request'], reservation['output']['evidence']
    invocation_elapsed = clock() - start
    require(math.isfinite(invocation_elapsed) and invocation_elapsed >= 0, 'decision_clock_invalid')
    invocation_now = now + math.ceil(invocation_elapsed)
    result = decision.evaluate(request, evidence,
        provider=provider if invocation_now < evidence['worker']['deadline'] else None, now=invocation_now)
    elapsed = clock() - start
    require(math.isfinite(elapsed) and elapsed >= invocation_elapsed, 'decision_clock_invalid')
    completed_now = now + math.ceil(elapsed)
    plan = None
    if result['status'] == 'ok' and result['outcome'] == 'implement' and completed_now < evidence['worker']['deadline']:
        plan = worker.prepare(request, evidence, result, current_head_sha=evidence['binding']['head_sha'], now=completed_now)
    def finish(prior):
        require(prior['phase'] == 'decision_started', 'decision_phase_changed')
        event = {'kind': 'decision_completed', 'delivery_id': 'decision:' + evidence['evidence_digest'], 'observation': result}
        prior['state']['seconds'] = max(prior['state']['seconds'], completed_now - prior['state']['started_at'])
        reduced = admission.evaluate(request, event, policy, prior['state'], now=completed_now)
        prior.update(state=reduced['state'], binding=reduced['binding'], phase='worker_ready' if plan and not reduced['state']['terminal'] else 'terminal')
        prior['artifacts']['decision'] = result
        if plan:
            prior['artifacts']['worker_plan'] = plan
        return prior, {'admission': reduced, 'decision': result, 'worker_plan': plan, 'merge_allowed': False}
    return journal.transaction(reservation['journal_digest'], finish)


def bind_publication(journal, candidate, *, expected_digest, now):
    """Journal validated publication intent; this function never publishes."""
    def transform(prior):
        require(prior is not None and prior['phase'] == 'worker_ready', 'worker_not_ready')
        plan = worker.validate_candidate(prior['request'], prior['artifacts']['worker_plan'], candidate,
            current_head_sha=prior['state']['current_head'], now=now)
        prior['artifacts']['publication_plan'] = plan
        prior['phase'] = 'publication_pending'
        return prior, {'publication_plan': plan, 'merge_allowed': False}
    return journal.transaction(expected_digest, transform)


def reconcile(journal, observation, policy, *, expected_digest, now):
    """Bind C reconciliation to the exact persisted plan, then advance A."""
    def transform(prior):
        require(prior is not None and prior['phase'] == 'publication_pending', 'no_pending_publication')
        plan = prior['artifacts']['publication_plan']
        receipt = worker.reconcile_publication(prior['request'], plan, observation)
        receipt['usage']['seconds'] = max(receipt['usage']['seconds'], now - prior['state']['started_at'])
        if receipt['status'] != 'published':
            return prior, {'receipt': receipt, 'merge_allowed': False}
        event = {'kind': 'publication_completed', 'delivery_id': 'publication:' + plan['plan_digest'], 'observation': receipt}
        reduced = admission.evaluate(prior['request'], event, policy, prior['state'], now=now)
        prior.update(state=reduced['state'], binding=reduced['binding'], phase='terminal' if reduced['state']['terminal'] else 'admitted')
        prior['artifacts']['publication_receipt'] = receipt
        return prior, {'receipt': receipt, 'admission': reduced, 'merge_allowed': False}
    return journal.transaction(expected_digest, transform)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('advance', 'decide-unavailable', 'route-unavailable'))
    parser.add_argument('--bundle', required=True, help='Trusted controller input, never a PR artifact')
    parser.add_argument('--journal', required=True)
    parser.add_argument('--expected-digest', default='absent')
    args = parser.parse_args()
    try:
        bundle = _read(Path(args.bundle))
        expected = None if args.expected_digest == 'absent' else args.expected_digest
        now = int(time.time())
        journal = Journal(args.journal)
        if args.operation == 'advance':
            output = advance(journal, bundle['request'], bundle['event'], bundle['policy'], expected_digest=expected, now=now)
        else:
            evaluate = route if args.operation == 'route-unavailable' else decide
            output = evaluate(journal, bundle['policy'], bundle['context'], bundle['execution'], bundle['destination'], expected_digest=expected, now=now)
        print(json.dumps(output, sort_keys=True))
        return 0
    except (contract.ContractError, worker.WorkerError) as exc:
        print(json.dumps({'status': 'stopped', 'reason': exc.code, 'merge_allowed': False}))
        return 2
    except (KeyError, TypeError, ValueError, OSError):
        print(json.dumps({'status': 'stopped', 'reason': 'invalid_or_unavailable_trusted_input', 'merge_allowed': False}))
        return 2


def route(journal, policy, context, execution, destination, *, expected_digest, now,
          provider=None, clock=None, actions_port=None):
    """Opt-in v2, using the existing admission, journal and worker capability.

    No CI/reviewer executor is installed here: those choices are not offered.
    A pending call is a reconciliation hold, never a fresh provider attempt.
    """
    clock = clock or time.monotonic
    start = clock()
    def reserve(prior):
        require(prior is not None and prior['phase'] == 'admitted', 'decision_already_started')
        request, state = prior['request'], prior['state']
        require(admission._authorized(request['initiator'], policy, request), 'authority_revoked')
        require(state['cost_microusd'] <= request['budget']['max_cost_microusd']
                and not (0 < request['budget']['max_cost_microusd'] == state['cost_microusd']), 'cost_exhausted')
        evidence = prepare_evidence(request, state, context, execution, destination, now=now)
        # Facts stay in code. A running dependency requires its completion event,
        # not a provider judgment, polling tick or new scheduler.
        ci = None
        if actions_port is not None:
            actions_port.current(request, state['current_head'])
            run_id = actions_port.policy.get('ci_run_id')
            ci = actions_port.ci(request, state['current_head'], run_id) if run_id else None
            published = prior['artifacts'].get('publication_receipt', {}).get('result_head_sha') == state['current_head']
            actions = actions_port.eligible(request, state['current_head'], ci, published)
        else:
            require(context.get('dependency_running') is not True, 'typed_dependency_required')
            actions = ['implement_fix', 'no_action', 'ask_human']
        prior_review = None
        if 'request_review' in actions:
            prior_review = actions_port.review(request, state['current_head'])
            prior['artifacts']['review_digest'] = prior_review.get('evidence_digest')
            prior['artifacts']['prior_review_id'] = prior_review.get('review_identity', {}).get('review_id', 0)
        if ci:
            evidence['ci_observation'] = ci
            evidence.pop('evidence_digest')
            evidence['evidence_digest'] = contract.digest(evidence)
            prior['artifacts']['ci_dependency'] = ci
        prior['phase'] = 'decision_started'
        prior['artifacts']['evidence'] = evidence
        prior['artifacts']['eligible_actions'] = actions
        return prior, dict(request=request, evidence=evidence, actions=actions)
    reserved = journal.transaction(expected_digest, reserve)
    data = reserved['output']
    request, evidence, actions = data['request'], data['evidence'], data['actions']
    invocation_elapsed = clock() - start
    require(math.isfinite(invocation_elapsed) and invocation_elapsed >= 0, 'decision_clock_invalid')
    invocation_now = now + math.ceil(invocation_elapsed)
    if actions == ['wait']:
        result = dict(schema=decision.V2_SCHEMA, status='ok', next_action='wait',
                      reason='dependency_running', binding=evidence['binding'],
                      evidence_digest=evidence['evidence_digest'], provenance={'source': 'deterministic'})
    else:
        result = decision.evaluate_v2(request, evidence, eligible_actions=actions, provider=provider if invocation_now < evidence['worker']['deadline'] else None, now=invocation_now)
    elapsed = clock() - start
    require(math.isfinite(elapsed) and elapsed >= invocation_elapsed, 'decision_clock_invalid')
    completed = now + math.ceil(elapsed)
    def finish(prior):
        require(prior['phase'] == 'decision_started', 'decision_phase_changed')
        state = prior['state']
        state['seconds'] = max(state['seconds'], completed - state['started_at'])
        require(prior['binding'] == evidence['binding'], 'stale_decision_binding')
        authorized = admission._authorized(request['initiator'], policy, request)
        active = authorized and completed < evidence['worker']['deadline'] and not state['terminal']
        action = result.get('next_action') if result['status'] == 'ok' and active else None
        prior['artifacts']['decision_v2'] = result
        plan = None
        if actions_port is not None and active:
            actions_port.current(request, state['current_head'])
        if action in ('retry_ci', 'request_review'):
            require(actions_port is not None, 'action_port_unavailable')
            ci = evidence.get('ci_observation')
            intent = dict(action=action, binding=result['binding'], ci=ci,
                          prior_review_digest=prior['artifacts'].get('review_digest'),
                          prior_review_id=prior['artifacts'].get('prior_review_id', 0),
                          decision_digest=contract.digest(result))
            intent['effect_id'] = contract.digest(intent)
            prior['artifacts']['action_intent'] = intent
            prior['phase'] = 'action_pending'
        elif action == 'implement_fix':
            # Explicit, narrowly lossless compatibility bridge, not v1 repurposing.
            legacy = dict(schema=decision.SCHEMA, status='ok', outcome='implement',
                          reason='actionable_work', binding=result['binding'],
                          evidence_digest=result['evidence_digest'], provenance=result['provenance'])
            plan = worker.prepare(request, evidence, legacy,
                                  current_head_sha=state['current_head'], now=completed)
            prior['artifacts']['worker_plan'] = plan
            prior['phase'] = 'worker_ready'
        elif action == 'wait':
            prior['phase'] = 'waiting_dependency'
            state['in_flight'] = False
        else:
            prior['phase'] = 'terminal'
            state.update(terminal=True, in_flight=False,
                         reason=('decision_' + (action or result['status'])) if active else 'decision_expired_or_revoked')
        return prior, dict(decision=result, worker_plan=plan, merge_allowed=False,
                           capability_gaps=[] if actions_port is not None else ['actions_port_unavailable'])
    return journal.transaction(reserved['journal_digest'], finish)



def dispatch_action(journal, policy, port, *, expected_digest, now, clock=None, policy_loader=None):
    """Trusted loader is host-owned live policy, never an event boolean."""
    from pullfrog_standalone_effect_guard import EffectGuard
    clock = clock or time.monotonic
    started = clock()
    loader = policy_loader or (lambda: policy)
    owned = {}
    def reserve(prior):
        require(prior is not None and prior['phase'] == 'action_pending', 'action_requires_reconciliation')
        guard = EffectGuard(prior['request'], prior['state'], prior['binding'],
                            policy_loader=loader, now=now, clock=clock)
        guard.start = started
        guard.check()
        require(prior['artifacts']['action_intent']['binding'] == prior['binding'], 'stale_action_binding')
        bounded = port.bounded(guard)
        # All blocking destination/source reads run after this durable intent,
        # so even failed prerequisite collection is charged and held.
        prior['phase'] = 'action_started'
        owned.update(guard=guard, port=bounded)
        return prior, dict(request=prior['request'], intent=prior['artifacts']['action_intent'])
    reserved = journal.transaction(expected_digest, reserve)
    receipt = None
    reason = None
    try:
        owned['port'].execute(reserved['output']['request'], reserved['output']['intent'])
        receipt = owned['port'].readback(reserved['output']['request'], reserved['output']['intent'])
    except Exception as error:
        reason = getattr(error, 'code', 'effect_unknown')
    return _finish_action(journal, receipt, owned['guard'], expected_digest=reserved['journal_digest'], reason=reason)


def _finish_action(journal, receipt, guard, *, expected_digest, reason=None):
    elapsed = guard.elapsed()
    def finish(prior):
        require(prior is not None and prior['phase'] == 'action_started', 'no_started_action')
        prior['state']['seconds'] = max(prior['state']['seconds'],
            guard.now + math.ceil(elapsed) - prior['state']['started_at'])
        if receipt is None:
            return prior, {'status': 'reconcile_required', 'reason': reason}
        prior['artifacts']['action_receipt'] = receipt
        prior['phase'] = 'waiting_dependency'
        prior['state']['in_flight'] = False
        if prior['artifacts']['action_intent']['action'] == 'retry_ci':
            prior['artifacts']['ci_dependency'] = receipt
        return prior, {'status': 'observed', 'receipt': receipt}
    result = journal.transaction(expected_digest, finish)
    # Preserve the previous public top-level unknown-effect status for callers.
    if result['output']['status'] == 'reconcile_required':
        result['status'] = 'reconcile_required'
    return result


def reconcile_action(journal, port, *, expected_digest, now, policy=None, policy_loader=None, clock=None):
    from pullfrog_standalone_effect_guard import EffectGuard
    require(policy is not None or policy_loader is not None, 'live_policy_required')
    clock = clock or time.monotonic
    # No POST exists in reconciliation; nevertheless all reads need bounded
    # elapsed/deadline accounting and authoritative policy custody.
    prior = _read(journal.path)
    require(contract.digest(prior) == expected_digest and prior['phase'] == 'action_started', 'no_started_action')
    guard = EffectGuard(prior['request'], prior['state'], prior['binding'],
                        policy_loader=policy_loader or (lambda: policy), now=now, clock=clock)
    receipt = None
    reason = None
    try:
        bounded = port.bounded(guard)
        receipt = bounded.readback(prior['request'], prior['artifacts']['action_intent'])
    except Exception as error:
        reason = getattr(error, 'code', 'effect_unknown')
    return _finish_action(journal, receipt, guard, expected_digest=expected_digest, reason=reason)


def complete_ci(journal, policy, port, *, expected_digest, now):
    """Trusted GET collector, no webhook-provided conclusions or run identities."""
    def finish(prior):
        require(prior is not None and prior['phase'] == 'waiting_dependency', 'ci_completion_required')
        r, s = prior['request'], prior['state']
        require(admission._authorized(r['initiator'], policy, r), 'authority_revoked')
        dependency = prior['artifacts']['ci_dependency']
        observed = port.ci(r, s['current_head'], dependency['run_id'])
        require(observed['workflow_id'] == dependency['workflow_id']
                and observed['run_attempt'] == dependency['run_attempt'], 'ci_attempt_drift')
        if observed['status'] != 'completed':
            return prior, {'status': 'waiting'}
        event = dict(kind='ci_completed', delivery_id='ci:' + observed['digest'],
                     head_sha=s['current_head'], observation=observed)
        reduced = admission.evaluate(r, event, policy, s, now=now)
        prior.update(state=reduced['state'], binding=reduced['binding'])
        if reduced['action'] == 'decide':
            prior['phase'] = 'admitted'
        elif reduced['state']['terminal']:
            prior['phase'] = 'terminal'
        prior['artifacts']['ci_completed'] = observed
        return prior, reduced
    return journal.transaction(expected_digest, finish)


if __name__ == '__main__':
    raise SystemExit(main())
