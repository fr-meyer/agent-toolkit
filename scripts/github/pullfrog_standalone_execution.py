"""Bounded local adapter boundary, not a provider or publisher.

Registry and adapters are trusted fixed code. Host MUST be credential-free and
network/sandbox restricted externally. Process isolation here enforces lifetime
and JSON/output limits, not a security sandbox. Only Linux fork is supported.
"""
import base64
import copy
import json
import math
import multiprocessing
import os
import signal
import time
from dataclasses import dataclass
from typing import Callable

import pullfrog_standalone_worker as worker

MAX_OUTPUT_BYTES = 6 * 1024 * 1024


@dataclass(frozen=True)
class Adapter:
    phase: str
    invoke: Callable
    max_seconds: int = 120
    max_output_bytes: int = MAX_OUTPUT_BYTES


def _child(connection, adapter, payload):
    try:
        os.setsid()
        os.environ.clear()
        # Adapter result and incidental output cannot flood the runner/logs.
        null = os.open(os.devnull, os.O_WRONLY)
        os.dup2(null, 1)
        os.dup2(null, 2)
        os.close(null)
        value = adapter.invoke(payload)
        encoded = json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
        if len(encoded) > adapter.max_output_bytes:
            encoded = b'{"status":"output_limit"}'
        connection.send_bytes(encoded)
    except BaseException:
        connection.send_bytes(b'{"status":"adapter_exception"}')
    finally:
        connection.close()


def _stop(process):
    if process.pid:
        try:
            # Kill the entire adapter session, including ordinary descendants.
            if os.getpgid(process.pid) == process.pid:
                os.killpg(process.pid, signal.SIGKILL)
            elif process.is_alive():
                process.kill()
        except ProcessLookupError:
            pass
    process.join(timeout=1)


def _invoke(adapter, payload, seconds, cancelled):
    context = multiprocessing.get_context('fork')
    receiver, sender = context.Pipe(duplex=False)
    process = context.Process(target=_child, args=(sender, adapter, payload))
    try:
        process.start()
    except Exception:
        sender.close()
        receiver.close()
        raise
    sender.close()
    deadline = time.monotonic() + min(seconds, adapter.max_seconds)
    try:
        while True:
            if cancelled():
                return {'status': 'cancelled'}
            if time.monotonic() >= deadline:
                return {'status': 'timeout'}
            if receiver.poll(min(.02, max(0, deadline-time.monotonic()))):
                try:
                    raw = receiver.recv_bytes(adapter.max_output_bytes)
                    result = json.loads(raw)
                    return result if isinstance(result, dict) else {'status': 'malformed_output'}
                except (EOFError, OSError, ValueError):
                    return {'status': 'malformed_output'}
            if not process.is_alive():
                return {'status': 'runner_lost'}
    finally:
        _stop(process)
        receiver.close()


def run(request, plan, *, registry, current_head_sha, now, cancelled=None):
    """Execute and validate one already-journaled reservation using fixed IDs.

    Executor returns status/patch_base64/usage.cost_microusd. Validator receives
    that bounded patch and returns status/candidate/usage.cost_microusd. Only the
    trusted validator constructs seal/test/commit evidence. Unknown usage stops.
    Registry must not be derived from task text; no fallback adapter is selected.
    """
    started = time.monotonic()
    cancelled = cancelled or (lambda: False)
    p = worker.checked(plan)
    worker.require(p.get('schema') == worker.WORKER_SCHEMA, 'invalid_worker_plan')
    worker.current(request, p['binding'], current_head_sha, now)
    worker.require(p['started_at'] <= now < p['deadline'], 'budget_exhausted')
    config = p['execution']
    budget_seconds = p['deadline'] - now
    cost = 0
    usage_known = True

    def stopped(reason):
        return {'schema': 'pullfrog-standalone-execution-result.v1', 'status': 'stopped',
                'reason': reason, 'binding': copy.deepcopy(p['binding']),
                'evidence_digest': p['evidence_digest'], 'plan_digest': plan['plan_digest'],
                'usage': {'attempts': p['attempt'],
                          'seconds': p['usage_before']['seconds'] + max(0, now-p['started_at']) + math.ceil(time.monotonic()-started),
                          'cost_microusd': p['usage_before']['cost_microusd'] + cost if usage_known else None},
                'retry_requires_reconciliation': True, 'merge_allowed': False}

    def select(key, phase):
        adapter = registry.get(config[key])
        if adapter is None:
            return None
        worker.require(isinstance(adapter, Adapter) and adapter.phase == phase and callable(adapter.invoke)
                       and type(adapter.max_seconds) is int and 1 <= adapter.max_seconds <= 1800
                       and type(adapter.max_output_bytes) is int and 64 <= adapter.max_output_bytes <= MAX_OUTPUT_BYTES,
                       'invalid_trusted_adapter')
        return adapter

    executor = select('executor_id', 'executor')
    validator = select('validator_id', 'validator')
    if executor is None or validator is None:
        return stopped('unavailable')
    if cancelled():
        return stopped('cancelled')
    payload = {'request': copy.deepcopy(request), 'plan': copy.deepcopy(plan)}
    result = None
    for adapter, phase in ((executor, 'executor'), (validator, 'validator')):
        remaining = budget_seconds - (time.monotonic()-started)
        if remaining <= 0:
            return stopped('timeout')
        try:
            result = _invoke(adapter, payload, remaining, cancelled)
        except Exception:
            usage_known = False
            return stopped('runner_lost')
        measured = result.get('usage', {}).get('cost_microusd') if isinstance(result.get('usage'), dict) else None
        if not worker.integer(measured):
            usage_known = False
        else:
            cost += measured
        if result.get('status') != 'ok':
            reason = result.get('status')
            return stopped(reason if reason in {'cancelled', 'timeout', 'adapter_exception', 'output_limit', 'runner_lost', 'malformed_output'} else 'adapter_failed')
        if not usage_known:
            return stopped('unknown_usage')
        if cost > p['cost_remaining_microusd']:
            return stopped('budget_exhausted')
        if phase == 'executor':
            patch = result.get('patch_base64')
            try:
                worker.require(isinstance(patch, str), 'invalid_patch')
                decoded = base64.b64decode(patch, validate=True)
                worker.require(0 < len(decoded) <= worker.remediation.MAX_PATCH_BYTES, 'invalid_patch')
            except (ValueError, worker.WorkerError):
                return stopped('invalid_patch')
            payload['patch_base64'] = patch
    if cancelled():
        return stopped('cancelled')
    candidate = result.get('candidate')
    if not isinstance(candidate, dict):
        return stopped('malformed_candidate')
    # Stamp runner-owned values after trusted validation; worker output never
    # controls the receipt identity or cumulative billing fields.
    candidate = copy.deepcopy(candidate)
    candidate.update(binding=p['binding'], plan_digest=plan['plan_digest'],
                     evidence_digest=p['evidence_digest'], validator_id=config['validator_id'],
                     recipe_id=config['recipe_id'], cost_microusd=cost)
    try:
        publication = worker.validate_candidate(request, plan, candidate,
            current_head_sha=current_head_sha, now=now+math.ceil(time.monotonic()-started))
    except (worker.WorkerError, worker.contract.ContractError, ValueError, KeyError, TypeError, AttributeError):
        return stopped('candidate_rejected')
    return {'schema': 'pullfrog-standalone-execution-result.v1', 'status': 'candidate_validated',
            'binding': copy.deepcopy(p['binding']), 'evidence_digest': p['evidence_digest'],
            'plan_digest': plan['plan_digest'], 'candidate': candidate,
            'publication_plan': publication, 'usage': publication['usage_after'],
            'merge_allowed': False}
