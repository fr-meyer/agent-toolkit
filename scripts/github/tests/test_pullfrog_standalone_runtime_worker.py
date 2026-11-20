import copy
import unittest
import sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import test_pullfrog_standalone_execution_profile as fixtures

import pullfrog_standalone_runtime_worker as runtime


class RuntimeQualificationTests(unittest.TestCase):
    def test_real_profile_context_still_refuses_and_preserves_usage(self):
        f = fixtures.ProfileTests()
        f.setUp()
        before = copy.deepcopy((f.request, f.plan, f.profile))
        result = runtime.admit(f.request, f.plan, f.profile,
                              current_head_sha='2' * 40, now=110)
        self.assertEqual(result['reason'], 'runtime_unqualified')
        self.assertEqual((f.request, f.plan, f.profile), before)
        self.assertIsNone(result['cost_microusd'])
        self.assertIsNone(result['reservation_consumed'])
        for head, now in (('3' * 40, 110), ('2' * 40, 999999)):
            result = runtime.admit(f.request, f.plan, f.profile,
                                  current_head_sha=head, now=now)
            self.assertEqual(result['reason'], 'profile_or_binding_rejected')
        self.assertEqual(f.spent, set())
        self.assertEqual(f.calls, 0)

    def test_actual_inventory_is_bounded_status_only(self):
        observed = runtime.inventory()
        self.assertEqual(set(observed), {'binaries_present', 'cgroup_v2_present',
                                        'cgroup_subtree_writable'})
        self.assertEqual(set(observed['binaries_present']), set(runtime.BINARIES))
        self.assertTrue(all(type(x) is bool for x in observed['binaries_present'].values()))

    def test_missing_primitives_report_exact_blockers(self):
        with patch.object(runtime, 'inventory', return_value={
                'binaries_present': dict.fromkeys(runtime.BINARIES, False),
                'cgroup_v2_present': False, 'cgroup_subtree_writable': False}):
            report = runtime.qualification()
        self.assertFalse(report['live_execution_allowed'])
        for code in ('codex_binary_unavailable', 'isolated_runtime_binary_unavailable',
                     'delegated_cgroup_limits_unavailable') + runtime.UNVERIFIED:
            self.assertIn(code, report['blockers'])

    def test_binary_presence_never_qualifies_subscription_or_sandbox(self):
        with patch.object(runtime, 'inventory', return_value={
                'binaries_present': dict.fromkeys(runtime.BINARIES, True),
                'cgroup_v2_present': True, 'cgroup_subtree_writable': True}):
            report = runtime.qualification()
        self.assertEqual(report['status'], 'unavailable')
        self.assertFalse(report['live_execution_allowed'])
        self.assertEqual(report['blockers'], list(runtime.UNVERIFIED))
        self.assertEqual(set(report['required_capabilities']), runtime.profiles.CAPABILITIES)

    def test_invalid_context_refuses_without_leaking_exception(self):
        with patch.object(runtime.profiles, 'context', side_effect=ValueError('secret')):
            result = runtime.admit({}, {}, {}, current_head_sha='bad', now=0)
        self.assertEqual(result['reason'], 'profile_or_binding_rejected')
        self.assertNotIn('secret', str(result))
        self.assertIsNone(result['cost_microusd'])

    def test_valid_context_and_cancel_never_consume_or_claim_cleanup(self):
        for cancelled in (False, True):
            request, plan, profile = {'a': 1}, {'b': 2}, {'c': 3}
            before = copy.deepcopy((request, plan, profile))
            with patch.object(runtime.profiles, 'context', return_value={}) as context:
                result = runtime.admit(request, plan, profile,
                    current_head_sha='a' * 40, now=123, cancelled=cancelled)
            context.assert_called_once()
            self.assertEqual((request, plan, profile), before)
            self.assertFalse(result['new_reservation_consumed'])
            self.assertIsNone(result['reservation_consumed'])
            self.assertIsNone(result['usage'])
            for field in ('effects_started', 'cleanup_verified', 'retry_allowed',
                          'merge_allowed', 'live_execution_allowed'):
                self.assertIs(result[field], False)
            self.assertTrue(result['reconciliation_required'])
            self.assertEqual(result['reason'], 'cancelled_before_admission' if cancelled
                             else 'runtime_unqualified')
        self.assertEqual(dict(runtime.profiles.DEFAULT_REGISTRY), {})
