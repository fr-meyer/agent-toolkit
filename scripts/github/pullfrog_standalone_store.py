"""Offline conformance seam, NOT a hosted store or effect authorization.

Only trusted in-process reducers may be supplied. No wire transform, endpoint,
credentials, clock, lease expiry, garbage collection or runtime adapter exists.
A provisioned empty fixture is positive evidence, never inferred from absence.
History and terminal/dedup records are retained for the fixture's lifetime.
"""
import copy
import hashlib
import json
import threading

MAX_BYTES = 2 * 1024 * 1024
MAX_DEPTH = 48
MAX_RECORDS = 1024

# In-process capability only, never a sandbox against hostile Python.
_CONTROLLER = object()


class StoreError(ValueError):
    pass


def require(ok, code):
    if not ok:
        raise StoreError(code)


def canonical(value):
    def check(v, depth):
        require(depth <= MAX_DEPTH, 'json_depth')
        if type(v) is dict:
            require(all(type(k) is str for k in v), 'json_key')
            for item in v.values():
                check(item, depth + 1)
        elif type(v) is list:
            for item in v:
                check(item, depth + 1)
        else:
            require(v is None or type(v) in (str, bool, int), 'strict_json')
            if type(v) is int:
                require(abs(v) <= 2**63 - 1, 'json_integer')
    check(value, 0)
    data = json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()
    require(len(data) <= MAX_BYTES, 'json_size')
    return data


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def parse(data):
    require(type(data) is bytes and len(data) <= MAX_BYTES, 'json_size')
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'duplicate_key')
            result[key] = value
        return result
    try:
        value = json.loads(data, object_pairs_hook=pairs)
        canonical(value)
        return value
    except (ValueError, RecursionError, UnicodeError) as exc:
        raise StoreError('invalid_json') from exc


class FixtureBackend:
    """Deterministic memory-only backend; all acknowledgements are LOCAL ONLY.

    Retains records without expiry. 'missing', 'expired', 'corrupt' and
    'unavailable' are fail-closed fault fixtures, not empty-slot evidence.
    """
    def __init__(self, repository, pr_number):
        require(type(repository) is str and repository.count('/') == 1
                and type(pr_number) is int and pr_number > 0, 'invalid_slot')
        self.slot = {'repository_slug': repository, 'pr_number': pr_number}
        self.status = 'new_empty'
        self.records = []
        self.lock = threading.Lock()
        self.lose_next_ack = False

    def read(self):
        require(self.status in ('new_empty', 'present'), 'history_' + self.status)
        if self.status == 'new_empty':
            require(not self.records, 'empty_history_conflict')
            return None
        require(bool(self.records), 'history_missing')
        previous = None
        for index, record in enumerate(self.records, 1):
            require(record['sequence'] == index and record['previous_digest'] == previous,
                    'history_chain')
            require(record['digest'] == digest(record['document']), 'history_corrupt')
            require(record['document'].get('sequence') == index
                    and record['document'].get('previous_digest') == previous, 'history_chain')
            expected_ack = digest({'slot': self.slot, 'sequence': index,
                                   'digest': record['digest'], 'generation': record['generation']})
            require(record.get('ack_id') == expected_ack, 'missing_or_corrupt_ack')
            previous = record['digest']
        return copy.deepcopy(self.records[-1])


class Store:
    """Controller-compatible transaction(expected_digest, transform).

    The caller must explicitly register exact trusted reducer identities. This
    registration is a code trust boundary, not sandboxing. Returned output is
    withheld on missing/ambiguous acknowledgement, even after a committed write.
    No result from this fixture can authorize a hosted effect.
    """
    def __init__(self, backend, *, trusted_reducers=(), generation=1):
        require(type(backend) is FixtureBackend, 'unqualified_backend')
        require(type(generation) is int and generation > 0, 'invalid_fence')
        self.backend = backend
        self.reducers = tuple(trusted_reducers)
        require(all(callable(fn) for fn in self.reducers), 'untrusted_reducer')
        self.generation = generation
        self._controller_scope = None

    def transaction(self, expected_digest, transform):
        require(any(transform is fn for fn in self.reducers), 'untrusted_reducer')
        b = self.backend
        with b.lock:
            record = b.read()
            prior = record['document'] if record else None
            actual = record['digest'] if record else None
            require(expected_digest == actual, 'state_compare_and_swap_failed')
            require(record is None or self.generation >= record['generation'], 'stale_fence')
            updated, output = transform(copy.deepcopy(prior))
            canonical(output)
            if updated == prior:
                require(record is not None, 'missing_durable_ack')
                require(self.generation == record['generation'], 'fence_not_committed')
                return self._result(record, output, False)
            require(type(updated) is dict, 'invalid_document')
            updated = copy.deepcopy(updated)
            self._validate(prior, updated)
            updated.update(schema='pullfrog-standalone-journal.v1',
                           sequence=1 if record is None else record['sequence'] + 1,
                           previous_digest=actual)
            canonical(updated)
            sequence = updated['sequence']
            receipt = dict(document=updated, digest=digest(updated), sequence=sequence,
                           previous_digest=actual, generation=self.generation)
            receipt['ack_id'] = digest({'slot': b.slot, 'sequence': sequence,
                                       'digest': receipt['digest'], 'generation': self.generation})
            require(len(b.records) < MAX_RECORDS, 'history_capacity_retained')
            b.records.append(receipt)
            b.status = 'present'
            if b.lose_next_ack:
                b.lose_next_ack = False
                raise StoreError('ambiguous_ack_reconcile_required')
            return self._result(receipt, output, True)

    def _validate(self, prior, updated):
        b = self.backend
        request = updated.get('request')
        require(type(request) is dict and all(request.get(k) == v for k, v in b.slot.items()), 'slot_mismatch')
        require(updated.get('binding', {}).get('request_digest') == digest(request), 'request_binding')
        state = updated.get('state')
        require(type(state) is dict and state.get('request') == request, 'state_request_binding')
        for key in ('attempts', 'seconds', 'cost_microusd', 'started_at'):
            require(type(state.get(key)) is int and state[key] >= 0, 'invalid_accounting')
        require(type(state.get('terminal')) is bool and type(state.get('in_flight')) is bool, 'invalid_claim')
        for key in ('deliveries', 'events', 'finding_digests'):
            require(type(state.get(key)) is list, 'invalid_retention')
        if prior is None:
            return
        require(request == prior['request'], 'request_rebound')
        old = prior['state']
        require(state['started_at'] == old['started_at'], 'time_origin_reset')
        for key in ('attempts', 'seconds', 'cost_microusd'):
            require(state[key] >= old[key], 'accounting_rollback')
        for key in ('deliveries', 'events', 'finding_digests'):
            require(state[key][:len(old[key])] == old[key], 'retention_rollback')
        require(not old['terminal'] or updated == prior, 'terminal_retained')
        if old['in_flight'] and not state['in_flight']:
            receipt = updated.get('artifacts', {}).get('publication_receipt', {})
            require(receipt.get('status') == 'published'
                    and receipt.get('binding') == prior['binding'], 'unknown_effect_hold')
        if prior.get('phase') in ('decision_started', 'publication_pending'):
            before, after = prior.get('artifacts', {}), updated.get('artifacts', {})
            replaceable = set()
            # Fixed controller transitions alone may advance prior-attempt slots.
            # The complete earlier documents remain in the immutable chain.
            scope = self._controller_scope
            if (scope == (_CONTROLLER, 'decide')
                    and prior['phase'] == 'decision_started'
                    and updated.get('phase') in ('worker_ready', 'terminal')):
                evidence = before.get('evidence', {})
                previous_plan = before.get('worker_plan', {})
                if (evidence.get('binding') == prior['binding']
                        and evidence.get('worker', {}).get('usage', {}).get('attempts') == old['attempts'] - 1
                        and previous_plan.get('attempt') == old['attempts'] - 1
                        and before.get('publication_receipt', {}).get('status') == 'published'
                        and before.get('publication_receipt', {}).get('result_head_sha') == prior['binding'].get('head_sha')
                        and previous_plan.get('binding') != prior['binding']
                        and before.get('decision', {}).get('binding') == previous_plan.get('binding')
                        and before.get('decision', {}).get('evidence_digest') == previous_plan.get('evidence_digest')):
                    for key in ('decision', 'worker_plan'):
                        value = after.get(key)
                        if (type(value) is dict and value.get('binding') == prior['binding']
                                and value.get('evidence_digest') == evidence.get('evidence_digest')
                                and (key != 'worker_plan' or value.get('attempt') == old['attempts'])):
                            replaceable.add(key)
            if (scope == (_CONTROLLER, 'reconcile')
                    and prior['phase'] == 'publication_pending'
                    and updated.get('phase') in ('admitted', 'terminal')):
                plan = before.get('publication_plan', {})
                receipt = after.get('publication_receipt', {})
                previous_receipt = before.get('publication_receipt', {})
                if (plan.get('attempt') == old['attempts']
                        and previous_receipt.get('usage', {}).get('attempts') == old['attempts'] - 1
                        and previous_receipt.get('result_head_sha') == plan.get('parent_sha')
                        and previous_receipt.get('status') == 'published'
                        and previous_receipt.get('binding') != prior['binding']
                        and receipt.get('status') == 'published'
                        and receipt.get('binding') == plan.get('binding') == prior['binding']
                        and receipt.get('publication_plan_digest') == plan.get('plan_digest')):
                    replaceable.add('publication_receipt')
            require(all(k in replaceable or (k in after and after[k] == v)
                        for k, v in before.items()), 'effect_evidence_lost')

    def _result(self, record, output, changed):
        require(bool(record.get('ack_id')), 'missing_durable_ack')
        return {'journal_digest': record['digest'], 'output': copy.deepcopy(output),
                'changed': changed, 'ack': {k: record[k] for k in
                    ('ack_id', 'sequence', 'previous_digest', 'generation')},
                'durability': 'local_fixture_only', 'hosted_effect_allowed': False}

    def authorize_hosted_effect(self, acknowledgement):
        raise StoreError('hosted_store_unqualified')


class _ControllerTransaction:
    """Private, synchronous, operation-scoped reducer registration."""
    def __init__(self, backend, generation, operation):
        self.backend = backend
        self.generation = generation
        self.operation = operation
        self.active = True

    def transaction(self, expected_digest, transform):
        require(self.active, 'controller_operation_closed')
        store = Store(self.backend, trusted_reducers=(transform,), generation=self.generation)
        store._controller_scope = (_CONTROLLER, self.operation)
        return store.transaction(expected_digest, transform)


class ControllerAdapter:
    """Fixed trusted Python entrypoints, not a wire dispatcher or sandbox.

    The private proxy exists only during a synchronous call into the imported
    controller function and is revoked even on failure. No public transaction or
    arbitrary callable operation argument exists. Injected provider/clock code
    is trusted fixture code, never a wire-selected plugin or hosted authority.
    """
    def __init__(self, backend, *, generation=1):
        Store(backend, generation=generation)  # Validate without registering reducers.
        self._backend = backend
        self._generation = generation

    def advance(self, request, event, policy, *, expected_digest, now):
        import pullfrog_standalone_controller as controller
        proxy = _ControllerTransaction(self._backend, self._generation, 'advance')
        try:
            return controller.advance(proxy, request, event, policy,
                                      expected_digest=expected_digest, now=now)
        finally:
            proxy.active = False

    def decide(self, policy, context, execution, destination, *, expected_digest,
               now, provider=None, clock=None):
        import pullfrog_standalone_controller as controller
        proxy = _ControllerTransaction(self._backend, self._generation, 'decide')
        try:
            return controller.decide(proxy, policy, context, execution, destination,
                                     expected_digest=expected_digest, now=now,
                                     provider=provider, clock=clock)
        finally:
            proxy.active = False

    def bind_publication(self, candidate, *, expected_digest, now):
        import pullfrog_standalone_controller as controller
        proxy = _ControllerTransaction(self._backend, self._generation, 'bind_publication')
        try:
            return controller.bind_publication(proxy, candidate,
                                               expected_digest=expected_digest, now=now)
        finally:
            proxy.active = False

    def reconcile(self, observation, policy, *, expected_digest, now):
        import pullfrog_standalone_controller as controller
        proxy = _ControllerTransaction(self._backend, self._generation, 'reconcile')
        try:
            return controller.reconcile(proxy, observation, policy,
                                        expected_digest=expected_digest, now=now)
        finally:
            proxy.active = False
