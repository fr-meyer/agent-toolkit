"""Trusted fake ports only. Passing fixtures do NOT qualify live enforcement."""
import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pullfrog_standalone_execution_profile as gate
import test_pullfrog_standalone_c as fixtures


class ProfileTests(unittest.TestCase):
    def setUp(self):
        f = fixtures.WorkerTests()
        f.setUp()
        self.request, self.plan = f.r, f.p
        self.profile = {'cli_sha256': 'a'*64, 'image_sha256': 'b'*64,
            'build_sha256': 'c'*64, 'requested_model': 'model-latest',
            'resolved_model': 'checkpoint-42', 'recipe_id': 'stdlib-v1',
            'privacy_policy_id': 'private-no-egress',
            'limits': dict.fromkeys(gate.LIMITS, 10)}
        self.ctx = gate.context(self.request, self.plan, self.profile,
                               current_head_sha='2'*40, now=110)
        self.receipt = {'context': self.ctx, 'capabilities': sorted(gate.CAPABILITIES),
            'reservation': {'id': 'external-1', 'limits': copy.deepcopy(self.profile['limits']),
                            'expires_at': self.ctx['expires_at']}}
        self.calls = 0
        self.spent = set()
        self.output = {'status': 'ok', 'cost_microusd': 2}
        def verify(ctx, opaque):
            # Fake independent store, never accept opaque as a qualified receipt.
            if opaque != 'fixture-reference':
                return None
            return copy.deepcopy(self.receipt)
        def claim(receipt, digest):
            key = receipt['reservation']['id']
            if key in self.spent:
                raise ValueError('already spent')
            self.spent.add(key)
            return {'context_digest': digest, 'reservation_id': key, 'state': 'consumed'}
        def invoke(ctx, claim):
            self.calls += 1
            if self.output == 'lost':
                raise RuntimeError('lost')
            return self.output
        self.port = gate.VerificationPort(verify, claim, invoke)

    def run_gate(self, **kwargs):
        return gate.invoke_offline(self.request, self.plan, self.profile,
            kwargs.pop('evidence', 'fixture-reference'), adapter_id='fixed',
            current_head_sha=kwargs.pop('head', '2'*40), now=kwargs.pop('now', 110),
            registry=kwargs.pop('registry', {'fixed': self.port}), **kwargs)

    def refused(self, **kwargs):
        self.assertNotEqual(self.run_gate(**kwargs)['status'], 'offline_returned')
        self.assertEqual(self.calls, 0)

    def test_default_and_boolean_verifier_unavailable(self):
        self.refused(registry={})
        self.refused(registry={'fixed': gate.VerificationPort(lambda *a: True,
                     self.port.claim, self.port.invoke)})
        self.refused(evidence=self.receipt)

    def test_missing_capabilities(self):
        for cap in gate.CAPABILITIES:
            with self.subTest(cap=cap):
                self.receipt['capabilities'] = sorted(gate.CAPABILITIES - {cap})
                self.refused()

    def test_wrong_model_and_immutable_identity(self):
        for key in ('requested_model', 'resolved_model', 'image_sha256', 'cli_sha256', 'build_sha256', 'privacy_policy_id', 'recipe_id'):
            old = self.profile[key]
            self.profile[key] = 'd'*64
            self.refused()
            self.profile[key] = old
        self.profile['resolved_model'] = self.profile['requested_model']
        self.refused()

    def test_stale_head_plan_receipt_expiry(self):
        self.refused(head='3'*40)
        self.refused(now=111)
        self.refused(now=self.ctx['expires_at'])
        self.receipt['context']['plan_digest'] = 'd'*64
        self.refused()

    def test_limits_missing_unbounded_and_original_budget(self):
        for key in gate.LIMITS:
            old = self.profile['limits'][key]
            for value in (None, True, 0, -1, float('inf')):
                self.profile['limits'][key] = value
                self.refused()
            self.profile['limits'][key] = old
        for key in ('seconds', 'cost_microusd'):
            self.profile['limits'][key] = 10000
            self.refused()
            self.profile['limits'][key] = 10
        del self.profile['limits']['remote_jobs']
        self.refused()

    def test_reservation_bounds_and_expiry(self):
        self.receipt['reservation']['limits']['cost_microusd'] = 11
        self.refused()
        self.receipt['reservation']['limits']['cost_microusd'] = 10
        self.receipt['reservation']['expires_at'] += 1
        self.refused()

    def test_offline_success_is_not_live_qualification_or_retry(self):
        result = self.run_gate()
        self.assertEqual(result['status'], 'offline_returned')
        self.assertTrue(result['reservation_consumed'])
        self.assertTrue(result['reconciliation_required'])
        self.assertFalse(result['retry_allowed'])
        self.assertFalse(result['merge_allowed'])
        self.assertEqual(self.run_gate()['status'], 'reconcile_required')
        self.assertEqual(self.calls, 1)

    def test_cancel_consumes_without_invocation_or_reuse(self):
        self.assertEqual(self.run_gate(cancelled=True)['status'], 'cancelled')
        self.assertEqual(self.spent, {'external-1'})
        self.refused()

    def test_unknown_usage_loss_ambiguous_remote_stop_stay_consumed(self):
        for output in ({'status': 'ok'}, {'status': 'ok', 'cost_microusd': 11},
                       {'status': 'remote_stop_unknown', 'cost_microusd': 1}, 'lost'):
            with self.subTest(output=output):
                self.setUp()
                self.output = output
                result = self.run_gate()
                self.assertEqual(result['status'], 'reconcile_required')
                self.assertTrue(result['reservation_consumed'])
                self.assertFalse(result['retry_allowed'])
                self.run_gate()
                self.assertEqual(self.calls, 1)

    def test_ambiguous_claim_never_invokes(self):
        def lost(*args):
            self.spent.add('external-1')
            raise RuntimeError('claim reply lost')
        self.port = gate.VerificationPort(self.port.verify, lost, self.port.invoke)
        self.refused()
        self.assertEqual(self.spent, {'external-1'})


if __name__ == '__main__':
    unittest.main()
