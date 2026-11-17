"""Cross-lane fixtures, not hosted/provider/credential qualification."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pullfrog_standalone_controller as ctl
import pullfrog_standalone_contract as contract
import pullfrog_standalone_review as review
import test_pullfrog_standalone_c as cf
import test_pullfrog_standalone_decision as bf
import test_pullfrog_standalone_review as df


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'pr.json'
        self.journal = ctl.Journal(self.path)
        self.f = cf.WorkerTests(); self.f.setUp()
        self.request = copy.deepcopy(self.f.r)
        self.policy = {'initiators': [self.request['initiator']], 'repositories': [self.request['repository_slug']], 'policy_modes': ['standalone']}
        self.event = {'kind': 'issue_comment', 'delivery_id': 'one', 'actor': self.request['initiator'], 'command': '/pr-automation run', 'head_sha': self.request['head_sha']}
        self.context = {'binding': contract.binding(self.request), 'context': 'Fixture request'}
        self.execution = copy.deepcopy(self.f.e['worker']['execution'])
        self.destination = copy.deepcopy(self.f.dest)

    def load(self):
        return json.loads(self.path.read_text())

    def admit(self):
        return ctl.advance(self.journal, self.request, self.event, self.policy, expected_digest=None, now=110)

    def decide(self, digest, provider=None):
        return ctl.decide(self.journal, self.policy, self.context, self.execution, self.destination, expected_digest=digest, now=111, provider=provider, clock=lambda: 0.0)

    def publish(self):
        first = self.admit()
        decided = self.decide(first['journal_digest'], bf.response)
        plan = decided['output']['worker_plan']
        self.assertEqual(plan['attempt'], 1)
        candidate = copy.deepcopy(self.f.c)
        candidate.update(binding=plan['binding'], plan_digest=plan['plan_digest'], evidence_digest=plan['evidence_digest'])
        published = ctl.bind_publication(self.journal, candidate, expected_digest=decided['journal_digest'], now=120)
        return published

    def test_reservation_restart_cas_duplicate(self):
        first = self.admit()
        self.assertTrue(self.load()['state']['in_flight'])
        self.assertEqual(self.load()['state']['attempts'], 1)
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        journal = ctl.Journal(self.path)
        repeat = ctl.advance(journal, self.request, self.event, self.policy, expected_digest=first['journal_digest'], now=110)
        self.assertFalse(repeat['changed'])
        with self.assertRaisesRegex(contract.ContractError, 'compare_and_swap'):
            self.admit()

    def test_ordinary_unauthorized_comment_does_not_create_slot(self):
        self.event['command'] = 'ordinary discussion'
        result = self.admit()
        self.assertFalse(self.path.exists())
        self.assertEqual(result['output']['reason'], 'explicit_request_required')

    def test_no_provider_is_explicit_terminal_not_green(self):
        first = self.admit()
        result = self.decide(first['journal_digest'])
        self.assertEqual(result['output']['decision']['status'], 'unavailable')
        self.assertIsNone(result['output']['worker_plan'])
        self.assertTrue(self.load()['state']['terminal'])
        self.assertEqual(self.load()['state']['attempts'], 1)

    def test_decision_started_survives_crash_and_never_reinvokes(self):
        first = self.admit()
        def crash(payload):
            raise KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):
            self.decide(first['journal_digest'], crash)
        prior = self.load()
        self.assertEqual(prior['phase'], 'decision_started')
        calls = []
        with self.assertRaisesRegex(contract.ContractError, 'already_started'):
            self.decide(contract.digest(prior), lambda p: calls.append(p))
        self.assertEqual(calls, [])

    def test_publication_intent_then_unknown_effect_keeps_claim(self):
        intent = self.publish()
        plan = intent['output']['publication_plan']
        self.assertEqual(self.load()['phase'], 'publication_pending')
        observation = {'binding': plan['binding'], 'plan_digest': plan['plan_digest'], 'read_status': 'unavailable'}
        result = ctl.reconcile(self.journal, observation, self.policy, expected_digest=intent['journal_digest'], now=121)
        self.assertFalse(result['changed'])
        self.assertEqual(result['output']['receipt']['status'], 'reconcile_required')
        with self.assertRaisesRegex(contract.ContractError, 'reconciliation'):
            ctl.advance(self.journal, self.request, self.event, self.policy, expected_digest=intent['journal_digest'], now=122)

    def test_real_abcd_flow_publication_restart_same_head_review(self):
        intent = self.publish()
        plan = intent['output']['publication_plan']
        observation = {'binding': plan['binding'], 'plan_digest': plan['plan_digest'], 'read_status': 'ok', 'repository_slug': self.request['repository_slug'], 'head_ref': self.request['head_ref'], 'head_sha': plan['result_head_sha'], 'parent_sha': plan['parent_sha'], 'patch_digest': plan['patch_digest']}
        published = ctl.reconcile(self.journal, observation, self.policy, expected_digest=intent['journal_digest'], now=121)
        self.assertEqual(self.load()['state']['attempts'], 1)
        self.assertEqual(self.load()['state']['cost_microusd'], 7)
        self.assertEqual(self.request['head_sha'], '2'*40)
        # Rebind genuine D fixture to this request and current successor head.
        df.ReviewTests.setUpClass()
        _, snapshot = df.ReviewTests().fixture()
        bound = contract.binding(self.request, head_sha=plan['result_head_sha'])
        snapshot['binding'] = bound
        for key in ('expected_identity', 'observed_identity'):
            snapshot[key] = copy.deepcopy(self.destination)
            snapshot[key]['head_sha'] = plan['result_head_sha']
        snapshot['reviews'][0]['commit_id'] = plan['result_head_sha']
        for check in snapshot['check_runs']:
            check['head_sha'] = plan['result_head_sha']
        normalized = review.normalize(self.request, snapshot, current_head_sha=plan['result_head_sha'])
        self.assertEqual(normalized['status'], 'clean')
        event = {'kind': 'pullfrog_review_completed', 'delivery_id': 'fresh-review', 'head_sha': plan['result_head_sha'], 'observation': normalized, 'checks': {'ci': 'success', 'destination-guard': 'success'}}
        result = ctl.advance(ctl.Journal(self.path), self.request, event, self.policy, expected_digest=published['journal_digest'], now=122)
        self.assertEqual(result['output']['reason'], 'ready_for_human')
        self.assertEqual(self.load()['state']['attempts'], 1)
        self.assertEqual(self.load()['binding']['request_digest'], contract.digest(self.request))
        self.assertNotIn('merge', result['output']['action'])

    def test_real_d_evidence_into_b_and_c_preserves_digest(self):
        df.ReviewTests.setUpClass()
        request, snapshot = df.ReviewTests().fixture()
        self.request = request
        self.policy = {'initiators': [request['initiator']], 'repositories': [request['repository_slug']], 'policy_modes': ['standalone']}
        self.event.update(actor=request['initiator'], head_sha=request['head_sha'])
        self.destination = copy.deepcopy(snapshot['expected_identity'])
        self.destination.update(slug=request['repository_slug'], default_branch='main', protected_refs=['dev', 'main'])
        self.context = review.normalize(request, snapshot)
        result = self.decide(self.admit()['journal_digest'], bf.response)
        decision = result['output']['decision']
        plan = result['output']['worker_plan']
        self.assertEqual(plan['evidence_digest'], decision['evidence_digest'])
        self.assertEqual(plan['binding']['request_digest'], contract.digest(request))

    def test_tampered_publication_cannot_advance_head(self):
        intent = self.publish()
        plan = intent['output']['publication_plan']
        with self.assertRaisesRegex(Exception, 'plan_mismatch'):
            ctl.reconcile(self.journal, {'binding': plan['binding'], 'plan_digest': 'f'*64}, self.policy, expected_digest=intent['journal_digest'], now=121)
        self.assertEqual(self.load()['state']['current_head'], self.request['head_sha'])

    def test_aggregate_original_deadline_clamps_worker_and_publication(self):
        self.request['budget']['max_seconds'] = 100
        first = self.admit()
        result = ctl.decide(self.journal, self.policy, self.context, self.execution, self.destination,
            expected_digest=first['journal_digest'], now=205, provider=bf.response, clock=lambda: 0.0)
        plan = result['output']['worker_plan']
        self.assertEqual(plan['deadline'], 210)
        self.assertEqual(plan['usage_before']['seconds'], 95)
        candidate = copy.deepcopy(self.f.c)
        candidate.update(binding=plan['binding'], plan_digest=plan['plan_digest'], evidence_digest=plan['evidence_digest'])
        with self.assertRaisesRegex(Exception, 'budget_exhausted'):
            ctl.bind_publication(self.journal, candidate, expected_digest=result['journal_digest'], now=220)
        self.assertEqual(self.load()['phase'], 'worker_ready')

    def test_decision_elapsed_time_charged_and_cannot_extend_deadline(self):
        first = self.admit()
        ticks = iter([0.0, 0.0, 9.2])
        result = ctl.decide(self.journal, self.policy, self.context, self.execution, self.destination,
            expected_digest=first['journal_digest'], now=111, provider=bf.response, clock=lambda: next(ticks))
        plan = result['output']['worker_plan']
        self.assertEqual(plan['started_at'], 121)
        self.assertEqual(plan['usage_before']['seconds'], 11)
        self.assertEqual(plan['deadline'], 210)
        self.assertEqual(self.load()['state']['seconds'], 11)

    def test_decision_returning_after_deadline_stops_without_worker(self):
        self.request['budget']['max_seconds'] = 100
        first = self.admit()
        ticks = iter([0.0, 0.0, 8.0])
        result = ctl.decide(self.journal, self.policy, self.context, self.execution, self.destination,
            expected_digest=first['journal_digest'], now=205, provider=bf.response, clock=lambda: next(ticks))
        self.assertIsNone(result['output']['worker_plan'])
        self.assertEqual(result['output']['admission']['reason'], 'time_exhausted')
        self.assertEqual(self.load()['state']['seconds'], 103)
        self.assertTrue(self.load()['state']['terminal'])

    def test_budget_spent_waiting_for_lock_never_invokes_provider(self):
        self.request['budget']['max_seconds'] = 100
        first = self.admit()
        ticks = iter([0.0, 6.0, 6.0]); calls = []
        result = ctl.decide(self.journal, self.policy, self.context, self.execution, self.destination,
            expected_digest=first['journal_digest'], now=205,
            provider=lambda p: calls.append(p), clock=lambda: next(ticks))
        self.assertEqual(calls, [])
        self.assertIsNone(result['output']['worker_plan'])
        self.assertEqual(self.load()['state']['reason'], 'time_exhausted')

    def test_expired_admission_never_reserves_or_invokes_decision(self):
        self.request['budget']['max_seconds'] = 100
        first = self.admit(); calls = []
        with self.assertRaisesRegex(contract.ContractError, 'aggregate_time_exhausted'):
            ctl.decide(self.journal, self.policy, self.context, self.execution, self.destination,
                expected_digest=first['journal_digest'], now=210, provider=lambda p: calls.append(p))
        self.assertEqual(calls, [])
        self.assertEqual(self.load()['phase'], 'admitted')
        self.assertEqual(contract.digest(self.load()), first['journal_digest'])

    def test_destination_mismatch_never_reaches_provider(self):
        first = self.admit(); calls = []
        for field, changed in (('pr_number', 99), ('slug', 'different/repo'), ('base_sha', '7'*40),
                               ('base_ref', 'main'), ('head_ref', 'feat/other'), ('head_sha', '8'*40),
                               ('head_repository_slug', 'fork/repo')):
            destination = {**self.destination, field: changed}
            with self.subTest(field=field), self.assertRaisesRegex(contract.ContractError, 'destination_mismatch'):
                ctl.decide(self.journal, self.policy, self.context, self.execution, destination,
                    expected_digest=first['journal_digest'], now=111, provider=lambda p: calls.append(p))
            self.assertEqual(contract.digest(self.load()), first['journal_digest'])
        self.assertEqual(calls, [])

    def test_multiline_task_is_data_and_control_escapes_rejected(self):
        self.request['task'] = 'Fix scoped issue\n\nPreserve behavior\tand tests.'
        self.assertEqual(contract.validate_request(self.request)['task'], self.request['task'])
        self.request['task'] += '\x1b'
        with self.assertRaisesRegex(contract.ContractError, 'invalid_task'):
            contract.validate_request(self.request)

    def test_new_automation_authority_paths_are_blocked(self):
        from pullfrog_destination_guard import FORBIDDEN_PATH_PREFIXES
        for path in ('scripts/github/pullfrog_standalone_controller.py',
                     'scripts/github/tests/test_pullfrog_standalone_controller.py'):
            self.assertTrue(any(path.startswith(prefix) for prefix in FORBIDDEN_PATH_PREFIXES))

    def test_symlink_journal_rejected(self):
        other = Path(self.temp.name)/'other.json'; other.write_text('{}')
        self.path.symlink_to(other)
        with self.assertRaisesRegex(contract.ContractError, 'symlink'):
            self.admit()
        self.assertEqual(other.read_text(), '{}')


if __name__ == '__main__':
    unittest.main()
