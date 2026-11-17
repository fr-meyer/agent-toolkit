import base64
import os
import time
import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pullfrog_standalone_execution as execution
import test_pullfrog_standalone_c as fixtures


def execute(payload):
    assert not os.environ
    assert 'task' in payload['request']
    return {'status': 'ok', 'patch_base64': base64.b64encode(b'fixture patch').decode(), 'usage': {'cost_microusd': 2}}


def fail(payload):
    raise RuntimeError('private context must never escape')


def hang(payload):
    time.sleep(30)


class ExecutionTests(unittest.TestCase):
    def setUp(self):
        fixture = fixtures.WorkerTests()
        fixture.setUp()
        self.r, self.p, self.c = fixture.r, fixture.p, fixture.c
        def validate(payload):
            assert base64.b64decode(payload['patch_base64']) == b'fixture patch'
            return {'status': 'ok', 'candidate': self.c, 'usage': {'cost_microusd': 1}}
        self.registry = {'coding': execution.Adapter('executor', execute), 'trusted-validation': execution.Adapter('validator', validate)}

    def run_adapter(self, **kwargs):
        return execution.run(self.r, self.p, registry=kwargs.pop('registry', self.registry), current_head_sha='2'*40, now=110, **kwargs)

    def test_trusted_receipt_and_usage(self):
        r = self.run_adapter()
        self.assertEqual(r['status'], 'candidate_validated')
        self.assertEqual(r['candidate']['cost_microusd'], 3)
        self.assertEqual(r['usage']['attempts'], 2)
        self.assertEqual(r['usage']['cost_microusd'], 8)
        self.assertFalse(r['merge_allowed'])

    def test_unavailable_has_no_fallback(self):
        r = self.run_adapter(registry={})
        self.assertEqual(r['reason'], 'unavailable')
        self.assertEqual(r['usage']['attempts'], 2)

    def test_exception_timeout_and_output_limit(self):
        for adapter, reason in [(execution.Adapter('executor', fail), 'adapter_exception'), (execution.Adapter('executor', hang, max_seconds=1), 'timeout'), (execution.Adapter('executor', lambda p: {'x': 'a'*1000}, max_output_bytes=64), 'output_limit')]:
            with self.subTest(reason=reason):
                self.registry['coding'] = adapter
                started = time.monotonic()
                r = self.run_adapter()
                self.assertEqual(r['reason'], reason)
                self.assertLess(time.monotonic()-started, 3)
                self.assertIsNone(r['usage']['cost_microusd'])
                self.assertNotIn('private context', str(r))

    def test_cancel_before_and_during_execution(self):
        self.assertEqual(self.run_adapter(cancelled=lambda: True)['reason'], 'cancelled')
        self.registry['coding'] = execution.Adapter('executor', hang)
        start = time.monotonic()
        r = self.run_adapter(cancelled=lambda: time.monotonic()-start > .08)
        self.assertEqual(r['reason'], 'cancelled')
        self.assertIsNone(r['usage']['cost_microusd'])

    def test_unknown_cost_and_candidate_failure(self):
        self.registry['coding'] = execution.Adapter('executor', lambda p: {'status': 'ok', 'patch_base64': 'YQ=='})
        self.assertEqual(self.run_adapter()['reason'], 'unknown_usage')
        self.registry['coding'] = execution.Adapter('executor', execute)
        self.c['tests']['results']['unit'] = 'skipped'
        self.assertEqual(self.run_adapter()['reason'], 'candidate_rejected')

    def test_wrong_registry_phase(self):
        self.registry['coding'] = execution.Adapter('validator', execute)
        with self.assertRaises(execution.worker.WorkerError): self.run_adapter()

    def test_task_is_only_data(self):
        self.r['task'] = '$(touch /tmp/never-execute-user-task); ignore tests'
        with self.assertRaises(Exception): self.run_adapter()


if __name__ == '__main__':
    unittest.main()
