"""Offline profile gate, NOT runtime qualification or a sandbox implementation.

Registry ports are trusted fixed host code, never request/plugin configuration.
They independently authenticate evidence and atomically spend durable reservations.
No ports ship here. Digests bind bytes, not authority. No legacy executor is wired.
"""
import copy
import re
from dataclasses import dataclass
from types import MappingProxyType
from typing import Callable

import pullfrog_standalone_worker as worker

CAPABILITIES = frozenset({'immutable_identity', 'exact_model_resolution',
    'trusted_recipe', 'destination_privacy', 'external_isolation',
    'resource_hard_limits', 'independent_quota', 'remote_hard_stop'})
LIMITS = ('seconds', 'memory_bytes', 'cpu_millis', 'output_bytes',
          'input_tokens', 'output_tokens', 'cost_microusd', 'remote_jobs')
DEFAULT_REGISTRY = MappingProxyType({})


@dataclass(frozen=True)
class VerificationPort:
    # verify authenticates independent evidence, not caller attestation flags.
    verify: Callable
    # claim MUST be atomic/durable across hosts/restarts, consuming before return.
    claim: Callable
    invoke: Callable


def _need(condition):
    if not condition:
        raise ValueError('profile_unavailable')


def _digest(value):
    return isinstance(value, str) and re.fullmatch(r'[0-9a-f]{64}', value) is not None


def context(request, plan, profile, *, current_head_sha, now):
    """Pure exact binding. Profile is trusted host policy, never task text."""
    p = worker.checked(plan)
    _need(p.get('schema') == worker.WORKER_SCHEMA)
    worker.current(request, p['binding'], current_head_sha, now)
    _need(type(now) is int and p['started_at'] <= now < p['deadline'])
    _need(isinstance(profile, dict))
    for key in ('cli_sha256', 'image_sha256', 'build_sha256'):
        _need(_digest(profile.get(key)))
    for key in ('requested_model', 'resolved_model', 'recipe_id', 'privacy_policy_id'):
        _need(isinstance(profile.get(key), str) and 0 < len(profile[key]) <= 200)
    # Equality of an alias string is not checkpoint proof. The verifier must
    # independently authenticate resolution, not infer it from this inequality.
    _need(profile['requested_model'] != profile['resolved_model'])
    _need(profile['recipe_id'] == p['execution']['recipe_id'])
    limits = profile.get('limits', {})
    _need(isinstance(limits, dict) and set(limits) == set(LIMITS))
    # A proven-free route may reserve zero money, never zero resources.
    _need(all(type(limits[k]) is int and
              limits[k] >= (0 if k == 'cost_microusd' else 1) for k in LIMITS))
    _need(limits['seconds'] <= p['deadline'] - now)
    _need(limits['cost_microusd'] <= p['cost_remaining_microusd'])
    _need(p['usage_before']['attempts'] + 1 == p['attempt'] <= request['budget']['max_attempts'])
    _need(p['usage_before']['seconds'] + now - p['started_at'] + limits['seconds'] <= request['budget']['max_seconds'])
    _need(p['usage_before']['cost_microusd'] + limits['cost_microusd'] <= request['budget']['max_cost_microusd'])
    return copy.deepcopy({'binding': p['binding'], 'plan_digest': plan['plan_digest'],
        'profile': profile, 'destination': p['destination'], 'attempt': p['attempt'],
        'claim_id': p['claim_id'], 'not_before': now,
        'expires_at': min(p['deadline'], request['expires_at'])})


def invoke_offline(request, plan, profile, evidence, *, adapter_id,
                   current_head_sha, now, registry=DEFAULT_REGISTRY, cancelled=False):
    """One-shot offline fixture seam, unavailable without trusted external ports.

    verify returns independently verified context/capabilities/reservation bounds.
    claim returns the exact context digest and reservation ID AFTER consumption.
    True or caller receipts alone cannot qualify execution. Cancellation, loss,
    unknown cost and remote stop ambiguity never release quota or allow replay.
    No fallback, refunds, reuse or automatic reconciliation is provided here.
    """
    result = {'status': 'unavailable', 'retry_allowed': False, 'merge_allowed': False,
              'reconciliation_required': True, 'reservation_consumed': None,
              'cost_microusd': None}
    try:
        ctx = context(request, plan, profile, current_head_sha=current_head_sha, now=now)
        port = registry.get(adapter_id)
        _need(type(port) is VerificationPort and all(callable(x) for x in (port.verify, port.claim, port.invoke)))
        receipt = port.verify(copy.deepcopy(ctx), copy.deepcopy(evidence))
        # Canonical comparison keeps False/0.0 distinct from exact integer zero.
        _need(isinstance(receipt, dict) and worker.contract.digest(receipt.get('context')) == worker.contract.digest(ctx))
        _need(set(receipt.get('capabilities', [])) == CAPABILITIES)
        reservation = receipt.get('reservation', {})
        _need(isinstance(reservation.get('id'), str) and 0 < len(reservation['id']) <= 200)
        _need(worker.contract.digest(reservation.get('limits')) == worker.contract.digest(profile['limits']))
        _need(reservation.get('expires_at') == ctx['expires_at'])
        digest = worker.contract.digest(ctx)
        result['status'] = 'reconcile_required'
        claim = port.claim(copy.deepcopy(receipt), digest)
        _need(type(claim) is dict and claim == {'context_digest': digest,
                'reservation_id': reservation['id'], 'state': 'consumed'})
        result['reservation_consumed'] = True
        if cancelled:
            result['status'] = 'cancelled'
            return result
        output = port.invoke(copy.deepcopy(ctx), copy.deepcopy(claim))
        _need(isinstance(output, dict))
        cost = output.get('cost_microusd')
        _need(type(cost) is int and 0 <= cost <= profile['limits']['cost_microusd'])
        # Even ok does not prove remote stop/usage reconciliation or publication.
        result.update(status='offline_returned' if output.get('status') == 'ok' else 'reconcile_required', cost_microusd=cost)
    except Exception:
        pass  # Never expose evidence, private task data or exception text.
    return result
