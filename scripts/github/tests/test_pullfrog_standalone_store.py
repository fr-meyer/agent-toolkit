from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pullfrog_standalone_store as s


def initial(_):
    request = {'repository_slug': 'fr-meyer/agent-toolkit', 'pr_number': 113, 'request_id': 'one'}
    state = dict(request=request, attempts=1, seconds=10, cost_microusd=20,
                 started_at=1, terminal=False, in_flight=True,
                 deliveries=['first'], events=['fingerprint'], finding_digests=[])
    return dict(request=request, binding={'request_digest': s.digest(request)},
                state=state, phase='decision_started', artifacts={'reservation': 'held'}), {'action': 'fixture'}


def noop(prior):
    return prior, {'action': 'none'}


class Conformance(unittest.TestCase):
    def setUp(self):
        self.backend = s.FixtureBackend('fr-meyer/agent-toolkit', 113)

    def store(self, *reducers, generation=1):
        return s.Store(self.backend, trusted_reducers=reducers, generation=generation)

    def seed(self):
        return self.store(initial).transaction(None, initial)

    def change(self, expected, change, generation=1):
        def reducer(prior):
            change(prior)
            return prior, {'action': 'none'}
        return self.store(reducer, generation=generation).transaction(expected, reducer)

    def test_local_only_and_hosted_denied(self):
        result = self.seed()
        self.assertEqual(result['durability'], 'local_fixture_only')
        self.assertFalse(result['hosted_effect_allowed'])
        with self.assertRaisesRegex(s.StoreError, 'hosted_store_unqualified'):
            self.store().authorize_hosted_effect(result['ack'])

    def test_cas_contention_and_replay(self):
        first = self.seed()
        with self.assertRaisesRegex(s.StoreError, 'compare_and_swap'):
            self.seed()
        second = self.change(first['journal_digest'], lambda p: p['state'].update(seconds=11))
        self.assertEqual(second['ack']['sequence'], 2)
        self.assertEqual(second['ack']['previous_digest'], first['journal_digest'])
        with self.assertRaisesRegex(s.StoreError, 'compare_and_swap'):
            self.store(noop).transaction(first['journal_digest'], noop)

    def test_missing_not_empty(self):
        for fault in ('missing', 'expired', 'corrupt', 'unavailable', 'present'):
            with self.subTest(fault=fault):
                self.backend.status = fault
                with self.assertRaises(s.StoreError):
                    self.seed()
        self.assertEqual(self.backend.records, [])

    def test_ack_loss_commits_without_output(self):
        self.backend.lose_next_ack = True
        with self.assertRaisesRegex(s.StoreError, 'ambiguous_ack'):
            self.seed()
        self.assertEqual(len(self.backend.records), 1)
        with self.assertRaisesRegex(s.StoreError, 'compare_and_swap'):
            self.seed()
        record = self.backend.read()
        result = self.store(noop).transaction(record['digest'], noop)
        self.assertFalse(result['changed'])
        self.assertEqual(result['ack']['ack_id'], record['ack_id'])

    def test_no_ack_on_empty_noop(self):
        with self.assertRaisesRegex(s.StoreError, 'missing_durable_ack'):
            self.store(noop).transaction(None, noop)

    def test_missing_ack_blocks_before_reducer(self):
        first = self.seed()
        self.backend.records[0].pop('ack_id')
        called = []
        def effect(prior):
            called.append(True)
            return prior, {}
        with self.assertRaisesRegex(s.StoreError, 'missing_or_corrupt_ack'):
            self.store(effect).transaction(first['journal_digest'], effect)
        self.assertEqual(called, [])

    def test_stale_fence(self):
        first = self.seed()
        second = self.change(first['journal_digest'], lambda p: p['state'].update(seconds=11), generation=2)
        with self.assertRaisesRegex(s.StoreError, 'stale_fence'):
            self.store(noop).transaction(second['journal_digest'], noop)

    def test_cancel_and_terminal_retention(self):
        first = self.seed()
        cancelled = self.change(first['journal_digest'], lambda p: p['state'].update(terminal=True))
        state = self.backend.read()['document']['state']
        self.assertEqual((state['attempts'], state['cost_microusd'], state['in_flight']), (1, 20, True))
        self.assertFalse(self.store(noop).transaction(cancelled['journal_digest'], noop)['changed'])
        with self.assertRaisesRegex(s.StoreError, 'terminal_retained'):
            self.change(cancelled['journal_digest'], lambda p: p['state'].update(terminal=False))

    def test_accounting_claim_and_dedup_rollback(self):
        first = self.seed()
        for key, value in [('attempts', 0), ('seconds', 0), ('cost_microusd', 0),
                           ('started_at', 2), ('in_flight', False), ('deliveries', []), ('events', [])]:
            with self.subTest(key=key), self.assertRaises(s.StoreError):
                self.change(first['journal_digest'], lambda p: p['state'].update({key: value}))
        self.assertEqual(len(self.backend.records), 1)

    def test_rebound_and_corrupt(self):
        first = self.seed()
        def rebound(p):
            p['request']['request_id'] = 'two'
            p['binding']['request_digest'] = s.digest(p['request'])
        with self.assertRaisesRegex(s.StoreError, 'request_rebound'):
            self.change(first['journal_digest'], rebound)
        self.backend.records[0]['document']['state']['seconds'] = 0
        with self.assertRaisesRegex(s.StoreError, 'history_corrupt'):
            self.backend.read()

    def test_untrusted_transforms_and_strict_json(self):
        for transform in (initial, {'op': 'reset'}, 'lambda x: x'):
            with self.assertRaisesRegex(s.StoreError, 'untrusted_reducer'):
                self.store().transaction(None, transform)
        for data in (b'{"a":1,"a":2}', b'NaN', b'1.5', b'1e999'):
            with self.assertRaises(s.StoreError):
                s.parse(data)
        with self.assertRaises(s.StoreError):
            s.canonical({'a': 'x' * s.MAX_BYTES})
        nested = None
        for _ in range(50):
            nested = [nested]
        with self.assertRaises(s.StoreError):
            s.canonical(nested)


class ControllerAdapterTests(unittest.TestCase):
    def setUp(self):
        import test_pullfrog_standalone_controller as fixture
        self.f = fixture.ControllerTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.backend = s.FixtureBackend(self.f.request['repository_slug'], self.f.request['pr_number'])
        self.adapter = s.ControllerAdapter(self.backend)

    def admit(self):
        return self.adapter.advance(self.f.request, self.f.event, self.f.policy,
                                    expected_digest=None, now=110)

    def test_real_controller_complete_flow(self):
        import copy
        import test_pullfrog_standalone_decision as bf
        first = self.admit()
        decided = self.adapter.decide(self.f.policy, self.f.context, self.f.execution,
            self.f.destination, expected_digest=first['journal_digest'], now=111,
            provider=bf.response, clock=lambda: 0.0)
        plan = decided['output']['worker_plan']
        candidate = copy.deepcopy(self.f.f.c)
        candidate.update(binding=plan['binding'], plan_digest=plan['plan_digest'],
                         evidence_digest=plan['evidence_digest'])
        intent = self.adapter.bind_publication(candidate,
            expected_digest=decided['journal_digest'], now=120)
        publication = intent['output']['publication_plan']
        observation = dict(binding=publication['binding'], plan_digest=publication['plan_digest'],
            read_status='ok', repository_slug=self.f.request['repository_slug'],
            head_ref=self.f.request['head_ref'], head_sha=publication['result_head_sha'],
            parent_sha=publication['parent_sha'], patch_digest=publication['patch_digest'])
        result = self.adapter.reconcile(observation, self.f.policy,
            expected_digest=intent['journal_digest'], now=121)
        state = self.backend.read()['document']['state']
        self.assertEqual(state['attempts'], 1)
        self.assertEqual(state['cost_microusd'], 7)
        self.assertFalse(state['in_flight'])
        self.assertFalse(result['hosted_effect_allowed'])
        self.assertEqual(state['current_head'], publication['result_head_sha'])

    def test_no_public_transaction_or_unknown_operation(self):
        self.assertFalse(hasattr(self.adapter, 'transaction'))
        with self.assertRaises(AttributeError):
            self.adapter.reset()
        with self.assertRaisesRegex(s.StoreError, 'untrusted_reducer'):
            s.Store(self.backend).transaction(None, initial)

    def test_lost_ack_does_not_invoke_fixture_provider_or_refund(self):
        first = self.admit()
        self.backend.lose_next_ack = True
        calls = []
        with self.assertRaisesRegex(s.StoreError, 'ambiguous_ack'):
            self.adapter.decide(self.f.policy, self.f.context, self.f.execution,
                self.f.destination, expected_digest=first['journal_digest'], now=111,
                provider=lambda payload: calls.append(payload), clock=lambda: 0.0)
        record = self.backend.read()
        self.assertEqual(record['document']['phase'], 'decision_started')
        self.assertEqual(record['document']['state']['attempts'], 1)
        self.assertEqual(calls, [])
        with self.assertRaisesRegex(Exception, 'already_started'):
            self.adapter.decide(self.f.policy, self.f.context, self.f.execution,
                self.f.destination, expected_digest=record['digest'], now=112,
                provider=lambda payload: calls.append(payload), clock=lambda: 0.0)
        self.assertEqual(calls, [])

    def test_fence_takeover_preserves_budget_and_denies_old_adapter(self):
        first = self.admit()
        newer = s.ControllerAdapter(self.backend, generation=2)
        cancel = dict(kind='cancel', delivery_id='cancel', actor=self.f.request['initiator'],
                      head_sha=self.f.request['head_sha'])
        second = newer.advance(self.f.request, cancel, self.f.policy,
                              expected_digest=first['journal_digest'], now=112)
        with self.assertRaisesRegex(s.StoreError, 'stale_fence'):
            self.adapter.advance(self.f.request, cancel, self.f.policy,
                                 expected_digest=second['journal_digest'], now=113)
        state = self.backend.read()['document']['state']
        self.assertTrue(state['terminal'])
        self.assertTrue(state['in_flight'])
        self.assertEqual(state['attempts'], 1)
        self.assertEqual(state['started_at'], 110)


if __name__ == '__main__':
    unittest.main()
