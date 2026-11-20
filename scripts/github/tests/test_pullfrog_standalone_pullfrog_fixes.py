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

    def saturated(self):
        state = self.admitted()
        state['deliveries'] = ['delivery:'+str(i) for i in range(256)]
        state['events'] = [contract.digest({'event': i}) for i in range(256)]
        return state

    def test_capacity_receipt_binds_before_terminal_without_audit_growth(self):
        for now in (102, 1000):
            state = self.saturated()
            event = self.receipt(state, seconds=899 if now == 1000 else 5)
            result = self.run_event(event, state, now=now)
            bound = result['state']
            self.assertEqual(bound['current_head'], 'c'*40)
            self.assertEqual(result['binding']['head_sha'], 'c'*40)
            self.assertEqual(bound['seconds'], event['observation']['usage']['seconds'])
            self.assertFalse(bound['in_flight'])
            self.assertTrue(bound['terminal'])
            self.assertEqual(result['action'], 'none')
            self.assertEqual(result['reason'], 'event_limit')
            self.assertEqual(bound['deliveries'], state['deliveries'])
            self.assertEqual(bound['events'], state['events'])
            self.assertEqual(bound['attempts'], 1)
            self.assertEqual(self.run_event(event, bound, now=now+1)['state'], bound)

    def test_capacity_nonpublication_stops_without_new_reservation(self):
        state = self.saturated()
        result = self.run_event(self.e | dict(delivery_id='overflow'), state)
        self.assertEqual(result['reason'], 'event_limit')
        self.assertEqual(result['state']['attempts'], 1)
        self.assertEqual(result['state']['deliveries'], state['deliveries'])
        self.assertEqual(result['state']['events'], state['events'])

    def test_capacity_invalid_receipts_refuse_without_effect(self):
        for terminal in (False, True):
            state = self.saturated()
            state.update(terminal=terminal, reason='event_limit' if terminal else '')
            for field, value in [('status', 'unknown'), ('usage', None), ('publication_plan_digest', 'forged')]:
                event = self.receipt(state)
                event['observation'][field] = value
                result = self.run_event(event, state, now=1000)
                self.assertEqual(result['status'], 'blocked')
                self.assertEqual(result['action'], 'reconcile')
                self.assertEqual(result['state'], state)
            for field, value in [('head_sha', 'f'*40), ('request_digest', 'f'*64)]:
                event = self.receipt(state)
                event['observation']['binding'][field] = value
                with self.assertRaises(contract.ContractError):
                    self.run_event(event, state, now=1000)

    def test_capacity_retains_dedup(self):
        state = self.saturated()
        event = self.receipt(state)
        for key, value in [('deliveries', event['delivery_id']),
                           ('events', contract.digest({k:v for k,v in event.items() if k != 'delivery_id'}))]:
            duplicate = copy.deepcopy(state)
            duplicate[key][0] = value
            result = self.run_event(event, duplicate, now=1000)
            self.assertEqual(result['reason'], 'duplicate_event')
            self.assertEqual(result['state'], duplicate)

    def test_only_event_limit_terminal_can_record_pending_receipt(self):
        state = self.saturated()
        stopped = self.run_event(self.e | dict(delivery_id='overflow'), state)['state']
        result = self.run_event(self.receipt(stopped), stopped)
        self.assertEqual(result['state']['current_head'], 'c'*40)
        self.assertEqual(result['reason'], 'event_limit')
        self.assertEqual(result['action'], 'none')
        for reason in ('cancelled', 'worker_failed', 'request_expired', 'time_exhausted', 'ready_for_human'):
            terminal = copy.deepcopy(state)
            terminal.update(terminal=True, reason=reason)
            result = self.run_event(self.receipt(terminal), terminal)
            self.assertEqual(result['state'], terminal)
            self.assertEqual(result['action'], 'none')
        stopped['in_flight'] = False
        self.assertEqual(self.run_event(self.receipt(stopped), stopped)['state'], stopped)

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

    def test_controller_capacity_receipt_updates_canonical_journal(self):
        intent = self.publish()
        def saturate(prior):
            prior['state']['deliveries'] = ['delivery:'+str(i) for i in range(256)]
            prior['state']['events'] = [contract.digest({'event': i}) for i in range(256)]
            return prior, {}
        saturated = self.journal.transaction(intent['journal_digest'], saturate)
        before = self.load()
        plan = intent['output']['publication_plan']
        observation = dict(binding=plan['binding'], plan_digest=plan['plan_digest'],
            read_status='ok', repository_slug=self.request['repository_slug'],
            head_ref=self.request['head_ref'], head_sha=plan['result_head_sha'],
            parent_sha=plan['parent_sha'], patch_digest=plan['patch_digest'])
        for field, value in [('read_status', 'unavailable'), ('head_sha', plan['parent_sha']),
                             ('head_sha', 'f'*40)]:
            refused = ctl.reconcile(self.journal, observation | {field: value}, self.policy,
                expected_digest=saturated['journal_digest'], now=1000)
            self.assertFalse(refused['changed'])
            self.assertEqual(self.load(), before)
        for field, value in [('plan_digest', 'f'*64), ('patch_digest', 'f'*64)]:
            with self.assertRaises(ctl.worker.WorkerError):
                ctl.reconcile(self.journal, observation | {field: value}, self.policy,
                    expected_digest=saturated['journal_digest'], now=1000)
            self.assertEqual(self.load(), before)
        result = ctl.reconcile(self.journal, observation, self.policy,
            expected_digest=saturated['journal_digest'], now=1000)
        stored = self.load()
        self.assertEqual(stored['binding']['head_sha'], plan['result_head_sha'])
        self.assertEqual(stored['state']['current_head'], plan['result_head_sha'])
        self.assertEqual(stored['state']['cost_microusd'], 7)
        self.assertEqual(stored['state']['seconds'], 890)
        self.assertEqual(stored['state']['attempts'], 1)
        self.assertFalse(stored['state']['in_flight'])
        self.assertEqual(stored['state']['reason'], 'event_limit')
        self.assertEqual(stored['phase'], 'terminal')
        self.assertEqual(stored['artifacts']['publication_receipt'], result['output']['receipt'])
        for key in ('deliveries', 'events'):
            self.assertEqual(stored['state'][key], before['state'][key])
        with self.assertRaises(contract.ContractError):
            ctl.reconcile(self.journal, observation, self.policy,
                expected_digest=result['journal_digest'], now=1001)
        self.assertEqual(self.load(), stored)

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
