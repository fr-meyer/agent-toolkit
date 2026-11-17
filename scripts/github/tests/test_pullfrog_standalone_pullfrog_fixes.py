"""Offline regressions for review5937645899, trusted local fixtures only."""
import copy
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pullfrog_standalone_execution as execution
import pullfrog_standalone_controller as ctl
import pullfrog_standalone_contract as contract
import test_pullfrog_standalone_a as af
import test_pullfrog_standalone_controller as cf


class ReceiptTests(af.Tests):
    def receipt(self, state, **usage):
        return dict(kind='publication_completed', delivery_id='pub', observation=dict(
            binding=contract.binding(self.r, head_sha=state['current_head']), status='published',
            result_head_sha='c'*40, publication_plan_digest='d'*64,
            usage=dict(attempts=state['attempts'], seconds=5, cost_microusd=0) | usage))

    def test_free_second_attempt(self):
        self.r['budget']['max_cost_microusd'] = 0
        state = self.admitted()
        state = self.run_event(self.receipt(state), state)['state']
        result = self.review(state, [{'id': 'new'}])
        self.assertEqual(result['action'], 'decide')
        self.assertEqual(result['state']['attempts'], 2)
        self.assertEqual(result['state']['cost_microusd'], 0)

    def test_late_receipts_apply_before_stop(self):
        for now, reason in [(601, 'time_exhausted'), (1000, 'request_expired')]:
            state = self.admitted()
            event = self.receipt(state, seconds=now-101)
            result = self.run_event(event, state, now=now)
            self.assertEqual(result['state']['current_head'], 'c'*40)
            self.assertFalse(result['state']['in_flight'])
            self.assertTrue(result['state']['terminal'])
            self.assertEqual(result['reason'], reason)
            repeat = self.run_event(event, result['state'], now=now+1)
            self.assertEqual(repeat['state'], result['state'])

    def test_late_invalid_receipts_never_bind(self):
        state = self.admitted()
        for field, value in [('status', 'unknown'), ('usage', None)]:
            event = self.receipt(state)
            event['observation'][field] = value
            result = self.run_event(event, state, now=1000)
            self.assertEqual(result['state']['current_head'], state['current_head'])
            self.assertTrue(result['state']['in_flight'])
        event = self.receipt(state)
        event['observation']['binding']['head_sha'] = 'f'*40
        with self.assertRaises(contract.ContractError):
            self.run_event(event, state, now=1000)

    def test_zero_cap_paid_unknown_and_terminal_refuse(self):
        self.r['budget']['max_cost_microusd'] = 0
        state = self.admitted()
        for cost in (None, 1):
            result = self.run_event(self.receipt(state, cost_microusd=cost), state)
            self.assertNotEqual(result['action'], 'review')
            self.assertEqual(result['state']['attempts'], 1)
        terminal = copy.deepcopy(state)
        terminal.update(terminal=True, reason='cancelled')
        result = self.run_event(self.receipt(state), terminal, now=1000)
        self.assertEqual(result['state'], terminal)

    def test_positive_cap_still_refuses(self):
        state = self.admitted()
        state = self.run_event(self.receipt(state, cost_microusd=100), state)['state']
        self.assertEqual(self.review(state, [{'id':'new'}])['reason'], 'budget_exhausted')


class LateControllerTests(cf.ControllerTests):
    def test_late_unknown_effect_retains_claim_and_canonical_state(self):
        intent = self.publish()
        before = self.load()
        plan = intent['output']['publication_plan']
        observation = dict(binding=plan['binding'], plan_digest=plan['plan_digest'], read_status='unavailable')
        result = ctl.reconcile(self.journal, observation, self.policy,
            expected_digest=intent['journal_digest'], now=10000)
        self.assertFalse(result['changed'])
        self.assertEqual(self.load(), before)
        self.assertEqual(result['output']['receipt']['status'], 'reconcile_required')

    def test_late_exact_effect_is_canonical(self):
        for expiry in ('seconds', 'request'):
            with self.subTest(expiry=expiry):
                self.path = Path(self.temp.name) / (expiry+'.json')
                self.journal = ctl.Journal(self.path)
                if expiry == 'request':
                    self.request['expires_at'] = 130
                    self.context['binding'] = contract.binding(self.request)
                intent = self.publish()
                plan = intent['output']['publication_plan']
                observation = dict(binding=plan['binding'], plan_digest=plan['plan_digest'],
                    read_status='ok', repository_slug=self.request['repository_slug'],
                    head_ref=self.request['head_ref'], head_sha=plan['result_head_sha'],
                    parent_sha=plan['parent_sha'], patch_digest=plan['patch_digest'])
                now = 211 if expiry == 'seconds' else 131
                result = ctl.reconcile(self.journal, observation, self.policy,
                    expected_digest=intent['journal_digest'], now=now)
                stored = self.load()
                self.assertEqual(stored['state']['current_head'], plan['result_head_sha'])
                self.assertEqual(stored['binding']['head_sha'], plan['result_head_sha'])
                self.assertFalse(stored['state']['in_flight'])
                self.assertEqual(stored['state']['cost_microusd'], 7)
                self.assertEqual(stored['state']['seconds'], now-110)
                self.assertEqual(stored['phase'], 'terminal')
                with self.assertRaises(contract.ContractError):
                    ctl.reconcile(self.journal, observation, self.policy,
                        expected_digest=result['journal_digest'], now=now+1)


class DescendantTests(unittest.TestCase):
    def test_exited_leader_cleanup_retains_owned_group(self):
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory)/'pid'
            def adapter(payload):
                # Preserve the result pipe as ordinary descendants can do.
                fds = []
                for name in os.listdir('/proc/self/fd'):
                    fd = int(name)
                    try: os.fstat(fd)
                    except OSError: continue
                    if fd > 2: fds.append(fd)
                child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'], pass_fds=fds)
                marker.write_text(str(child.pid))
                os._exit(0)
            pid = None
            try:
                result = execution._invoke(execution.Adapter('executor', adapter), {}, 2, lambda: False)
                pid = int(marker.read_text())
                self.assertEqual(result['status'], 'runner_lost')
                deadline = time.monotonic()+2
                while time.monotonic() < deadline:
                    stat = Path('/proc')/str(pid)/'stat'
                    if not stat.exists() or stat.read_text().split()[2] == 'Z':
                        break
                    time.sleep(.02)
                else:
                    self.fail('ordinary trusted subprocess survived exited leader cleanup')
            finally:
                if pid:
                    try: os.kill(pid, signal.SIGKILL)
                    except ProcessLookupError: pass

if __name__ == '__main__':
    unittest.main()
