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

    def publish_attempt(self, admitted, head, result_head, now):
        import copy
        import test_pullfrog_standalone_decision as bf
        self.f.context['binding'] = self.contract.binding(self.f.request, head_sha=head)
        self.f.destination['head_sha'] = head
        calls = []
        def provider(payload):
            calls.append(payload)
            return bf.response(payload)
        decided = self.adapter.decide(self.f.policy, self.f.context, self.f.execution,
            self.f.destination, expected_digest=admitted['journal_digest'], now=now,
            provider=provider, clock=lambda: 0.0)
        self.assertEqual(len(calls), 1)
        plan = decided['output']['worker_plan']
        candidate = copy.deepcopy(self.f.f.c)
        candidate.update(binding=plan['binding'], plan_digest=plan['plan_digest'],
                         evidence_digest=plan['evidence_digest'], cost_microusd=0,
                         parent_sha=head, result_head_sha=result_head)
        candidate['observed_destination']['head_sha'] = head
        candidate['seal']['source_head_sha'] = head
        candidate['tests']['source_head_sha'] = head
        intent = self.adapter.bind_publication(candidate,
            expected_digest=decided['journal_digest'], now=now + 2)
        publication = intent['output']['publication_plan']
        observation = dict(binding=publication['binding'], plan_digest=publication['plan_digest'],
            read_status='ok', repository_slug=self.f.request['repository_slug'],
            head_ref=self.f.request['head_ref'], head_sha=result_head,
            parent_sha=head, patch_digest=publication['patch_digest'])
        return intent, observation

    def successor(self):
        import copy
        import pullfrog_standalone_contract as contract
        import pullfrog_standalone_review as review
        import test_pullfrog_standalone_review as df
        self.contract = contract
        self.f.request['budget'].update(max_attempts=2, max_cost_microusd=0)
        intent, observation = self.publish_attempt(self.admit(), '2'*40, '3'*40, 111)
        first = self.adapter.reconcile(observation, self.f.policy,
            expected_digest=intent['journal_digest'], now=114)
        df.ReviewTests.setUpClass()
        _, snapshot = df.ReviewTests().fixture()
        snapshot['binding'] = contract.binding(self.f.request, head_sha='3'*40)
        for key in ('expected_identity', 'observed_identity'):
            snapshot[key] = copy.deepcopy(self.f.destination)
            snapshot[key]['head_sha'] = '3'*40
        snapshot['reviews'][0]['commit_id'] = '3'*40
        for check in snapshot['check_runs']:
            check['head_sha'] = '3'*40
        snapshot['reviews'][0]['body'] = snapshot['reviews'][0]['body'].replace('No new issues found', 'One issue')
        snapshot['check_runs'][1]['conclusion'] = 'failure'
        snapshot['review_comments'] = [dict(id=701, pull_request_review_id=601,
            commit_id='3'*40, path='src/a.py', line=12, body='Fix comparison.',
            user=dict(id=456, login='pullfrog[bot]', type='Bot'))]
        snapshot['review_threads'][0]['isResolved'] = False
        normalized = review.normalize(self.f.request, snapshot, current_head_sha='3'*40)
        self.assertEqual(normalized['status'], 'findings', normalized)
        event = dict(kind='pullfrog_review_completed', delivery_id='second-review',
                     head_sha='3'*40, observation=normalized)
        second = self.adapter.advance(self.f.request, event, self.f.policy,
            expected_digest=first['journal_digest'], now=115)
        self.assertEqual(second['output']['reason'], 'attempt_reserved')
        return second

    def test_two_real_controller_attempts_zero_cost(self):
        import copy
        second = self.successor()
        history = copy.deepcopy(self.backend.records)
        intent, observation = self.publish_attempt(second, '3'*40, '4'*40, 116)
        result = self.adapter.reconcile(observation, self.f.policy,
            expected_digest=intent['journal_digest'], now=119)
        document = self.backend.read()['document']
        self.assertEqual(self.backend.records[:len(history)], history)
        self.assertEqual(document['state']['attempts'], 2)
        self.assertEqual(document['state']['started_at'], 110)
        self.assertEqual(document['state']['cost_microusd'], 0)
        self.assertGreaterEqual(document['state']['seconds'], 9)
        self.assertEqual(document['state']['current_head'], '4'*40)
        self.assertFalse(document['state']['in_flight'])
        self.assertEqual(document['artifacts']['worker_plan']['attempt'], 2)
        self.assertEqual(document['artifacts']['publication_receipt']['usage']['attempts'], 2)
        self.assertFalse(result['hosted_effect_allowed'])

    def test_second_pending_evidence_and_arbitrary_reducer_cannot_erase(self):
        import copy
        second = self.successor()
        self.f.context['binding'] = self.contract.binding(self.f.request, head_sha='3'*40)
        self.f.destination['head_sha'] = '3'*40
        def crash(payload):
            raise KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):
            self.adapter.decide(self.f.policy, self.f.context, self.f.execution,
                self.f.destination, expected_digest=second['journal_digest'], now=116,
                provider=crash, clock=lambda: 0.0)
        record = self.backend.read()
        original = copy.deepcopy(self.backend.records)
        for scope in (None, (s._CONTROLLER, 'decide'), (s._CONTROLLER, 'reconcile')):
            for key in record['document']['artifacts']:
                for delete in (True, False):
                    def finish(prior):
                        prior['phase'] = 'worker_ready'
                        if delete:
                            del prior['artifacts'][key]
                        else:
                            prior['artifacts'][key] = {'tampered': True}
                        return prior, {}
                    # Names and module strings confer no controller authenticity.
                    finish.__module__ = 'pullfrog_standalone_controller'
                    store = s.Store(self.backend, trusted_reducers=(finish,))
                    store._controller_scope = scope
                    with self.subTest(scope=scope, key=key, delete=delete):
                        with self.assertRaisesRegex(s.StoreError, 'effect_evidence_lost'):
                            store.transaction(record['digest'], finish)
        self.assertEqual(self.backend.records, original)
        calls = []
        with self.assertRaisesRegex(Exception, 'already_started'):
            self.adapter.decide(self.f.policy, self.f.context, self.f.execution,
                self.f.destination, expected_digest=record['digest'], now=117,
                provider=lambda p: calls.append(p), clock=lambda: 0.0)
        self.assertEqual(calls, [])

    def test_second_completion_ack_loss_never_replays_provider(self):
        import test_pullfrog_standalone_decision as bf
        second = self.successor()
        self.f.context['binding'] = self.contract.binding(self.f.request, head_sha='3'*40)
        self.f.destination['head_sha'] = '3'*40
        calls = []
        def provider(payload):
            calls.append(payload)
            self.backend.lose_next_ack = True
            return bf.response(payload)
        with self.assertRaisesRegex(s.StoreError, 'ambiguous_ack'):
            self.adapter.decide(self.f.policy, self.f.context, self.f.execution,
                self.f.destination, expected_digest=second['journal_digest'], now=116,
                provider=provider, clock=lambda: 0.0)
        record = self.backend.read()
        self.assertEqual(record['document']['phase'], 'worker_ready')
        self.assertEqual(record['document']['artifacts']['worker_plan']['attempt'], 2)
        with self.assertRaisesRegex(Exception, 'already_started'):
            self.adapter.decide(self.f.policy, self.f.context, self.f.execution,
                self.f.destination, expected_digest=record['digest'], now=117,
                provider=provider, clock=lambda: 0.0)
        self.assertEqual(len(calls), 1)

    def test_second_attempt_identity_mismatch_and_lost_ack_hold(self):
        second = self.successor()
        self.f.context['binding'] = self.contract.binding(self.f.request, head_sha='3'*40)
        calls = []
        # Destination is still the first attempt's head.
        with self.assertRaisesRegex(Exception, 'destination_mismatch'):
            self.adapter.decide(self.f.policy, self.f.context, self.f.execution,
                self.f.destination, expected_digest=second['journal_digest'], now=116,
                provider=lambda p: calls.append(p), clock=lambda: 0.0)
        self.f.destination['head_sha'] = '3'*40
        self.backend.lose_next_ack = True
        with self.assertRaisesRegex(s.StoreError, 'ambiguous_ack'):
            self.adapter.decide(self.f.policy, self.f.context, self.f.execution,
                self.f.destination, expected_digest=second['journal_digest'], now=116,
                provider=lambda p: calls.append(p), clock=lambda: 0.0)
        record = self.backend.read()
        self.assertEqual(record['document']['state']['attempts'], 2)
        self.assertEqual(record['document']['state']['started_at'], 110)
        self.assertTrue(record['document']['state']['in_flight'])
        with self.assertRaisesRegex(Exception, 'already_started'):
            self.adapter.decide(self.f.policy, self.f.context, self.f.execution,
                self.f.destination, expected_digest=record['digest'], now=117,
                provider=lambda p: calls.append(p), clock=lambda: 0.0)
        self.assertEqual(calls, [])

    def test_second_publication_unknown_mismatch_and_retention(self):
        import copy
        second = self.successor()
        intent, observation = self.publish_attempt(second, '3'*40, '4'*40, 116)
        record = self.backend.read()
        unknown = dict(observation, read_status='unavailable')
        result = self.adapter.reconcile(unknown, self.f.policy,
            expected_digest=intent['journal_digest'], now=119)
        self.assertFalse(result['changed'])
        self.assertFalse(result['output']['receipt']['retry_allowed'])
        with self.assertRaisesRegex(Exception, 'reconciliation'):
            self.adapter.advance(self.f.request, self.f.event, self.f.policy,
                expected_digest=record['digest'], now=119)
        wrong = copy.deepcopy(observation)
        wrong['binding']['request_id'] = 'other'
        with self.assertRaises(Exception):
            self.adapter.reconcile(wrong, self.f.policy, expected_digest=record['digest'], now=119)
        for key in record['document']['artifacts']:
            def erase(prior):
                del prior['artifacts'][key]
                return prior, {}
            store = s.Store(self.backend, trusted_reducers=(erase,))
            store._controller_scope = (s._CONTROLLER, 'reconcile')
            with self.assertRaisesRegex(s.StoreError, 'effect_evidence_lost'):
                store.transaction(record['digest'], erase)
        for field, value in [('attempts', 1), ('seconds', 0), ('started_at', 115)]:
            def reset(prior):
                prior['state'][field] = value
                return prior, {}
            with self.assertRaises(s.StoreError):
                s.Store(self.backend, trusted_reducers=(reset,)).transaction(record['digest'], reset)
        # A higher-fence committed observation invalidates the old adapter.
        def tick(prior):
            prior['state']['seconds'] += 1
            return prior, {}
        takeover = s.Store(self.backend, trusted_reducers=(tick,), generation=2).transaction(record['digest'], tick)
        with self.assertRaisesRegex(s.StoreError, 'stale_fence'):
            self.adapter.reconcile(observation, self.f.policy,
                expected_digest=takeover['journal_digest'], now=119)
        self.assertEqual(self.backend.read()['document']['phase'], 'publication_pending')

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
