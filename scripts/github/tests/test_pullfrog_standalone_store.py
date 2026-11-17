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


if __name__ == '__main__':
    unittest.main()
