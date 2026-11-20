"""Real file/independent connection tests; no hosted qualification claim."""
import concurrent.futures
import copy
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pullfrog_standalone_sqlite as sql
import pullfrog_standalone_store as core
import test_pullfrog_standalone_store as fixtures


class SQLiteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'journal.sqlite'
        self.b = sql.SQLiteBackend(self.path, 'fr-meyer/agent-toolkit', 113, create=True)

    def reopen(self):
        return sql.SQLiteBackend(self.path, 'fr-meyer/agent-toolkit', 113)

    def store(self, *reducers, generation=1):
        return sql.Store(self.b, trusted_reducers=reducers, generation=generation)

    def seed(self):
        return self.store(fixtures.initial).transaction(None, fixtures.initial)

    def test_durable_canonical_and_fences(self):
        first = self.seed()
        original = copy.deepcopy(self.b.records)
        self.b = self.reopen()
        self.assertEqual(self.b.records, original)
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute('SELECT receipt FROM journal').fetchone()[0], core.canonical(original[0]))
        def change(p):
            p['state']['seconds'] += 1
            return p, {}
        second = self.store(change, generation=2).transaction(first['journal_digest'], change)
        with self.assertRaisesRegex(core.StoreError, 'stale_fence'):
            self.store(fixtures.noop).transaction(second['journal_digest'], fixtures.noop)
        self.assertFalse(first['hosted_effect_allowed'])
        with self.assertRaisesRegex(core.StoreError, 'hosted_store_unqualified'):
            self.store().authorize_hosted_effect(first['ack'])
        with self.assertRaisesRegex(core.StoreError, 'unqualified_backend'):
            core.Store(self.b)

    def test_independent_connection_cas(self):
        def run(_):
            b = self.reopen()
            try:
                sql.Store(b, trusted_reducers=(fixtures.initial,)).transaction(None, fixtures.initial)
                return 'ok'
            except core.StoreError as exc:
                return str(exc)
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            self.assertCountEqual(pool.map(run, range(2)), ['ok', 'state_compare_and_swap_failed'])
        self.assertEqual(len(self.b.records), 1)

    def test_missing_wrong_identity_and_reprovision(self):
        for repository, pr in [('other/repo', 113), ('fr-meyer/agent-toolkit', 114)]:
            with self.assertRaisesRegex(core.StoreError, 'slot_mismatch'):
                sql.SQLiteBackend(self.path, repository, pr)
        with self.assertRaises(FileExistsError):
            sql.SQLiteBackend(self.path, 'fr-meyer/agent-toolkit', 113, create=True)
        with self.assertRaises(core.StoreError):
            sql.SQLiteBackend(self.path.with_name('missing'), 'fr-meyer/agent-toolkit', 113)
        def wrong(_):
            p, output = fixtures.initial(None)
            p['request']['pr_number'] = 114
            return p, output
        with self.assertRaisesRegex(core.StoreError, 'slot_mismatch'):
            self.store(wrong).transaction(None, wrong)
        self.assertIsNone(self.b.read())

    def test_ack_loss_is_committed_without_output(self):
        self.b.lose_next_ack = True
        with self.assertRaisesRegex(core.StoreError, 'ambiguous_ack'):
            self.seed()
        self.b = self.reopen()
        record = self.b.read()
        with self.assertRaisesRegex(core.StoreError, 'compare_and_swap'):
            self.seed()
        result = self.store(fixtures.noop).transaction(record['digest'], fixtures.noop)
        self.assertFalse(result['changed'])
        self.assertEqual(result['ack']['ack_id'], record['ack_id'])

    def test_reducer_rollback_and_corrupt_truncation(self):
        first = self.seed()
        original = self.b.records
        def rollback(p):
            p['state']['cost_microusd'] = 0
            return p, {}
        with self.assertRaisesRegex(core.StoreError, 'accounting_rollback'):
            self.store(rollback).transaction(first['journal_digest'], rollback)
        self.assertEqual(self.reopen().records, original)
        with sqlite3.connect(self.path) as db:
            db.execute('DELETE FROM journal')
        with self.assertRaisesRegex(core.StoreError, 'history_head_mismatch'):
            self.reopen()

    def test_corrupt_bytes(self):
        self.seed()
        with sqlite3.connect(self.path) as db:
            db.execute('UPDATE journal SET receipt=?', (b'{}',))
        with self.assertRaises(core.StoreError):
            self.b.read()

    def test_process_crash_rolls_back_and_reopen_keeps_commit(self):
        self.seed()
        before = self.b.records
        code = "import sqlite3,os,sys; d=sqlite3.connect(sys.argv[1]); d.execute('BEGIN IMMEDIATE'); d.execute('DELETE FROM journal'); os._exit(17)"
        proc = subprocess.run([sys.executable, '-c', code, str(self.path)], check=False)
        self.assertEqual(proc.returncode, 17)
        self.assertEqual(self.reopen().records, before)

    def test_empty_noop_and_untrusted_reducer(self):
        with self.assertRaisesRegex(core.StoreError, 'missing_durable_ack'):
            self.store(fixtures.noop).transaction(None, fixtures.noop)
        with self.assertRaisesRegex(core.StoreError, 'untrusted_reducer'):
            self.store().transaction(None, fixtures.initial)
        self.assertIsNone(self.reopen().read())

    def test_insert_and_head_update_are_atomic(self):
        first = self.seed()
        before = self.b.records
        with sqlite3.connect(self.path) as db:
            db.execute("CREATE TRIGGER reject_head BEFORE UPDATE ON metadata BEGIN SELECT RAISE(ABORT, 'failure'); END")
        def tick(p):
            p['state']['seconds'] += 1
            return p, {}
        with self.assertRaises(core.StoreError):
            self.store(tick).transaction(first['journal_digest'], tick)
        self.assertEqual(self.reopen().records, before)

    def test_process_exit_after_real_store_commit(self):
        path = self.path.with_name('child.sqlite')
        code = """import os, sys
sys.path[:0] = [sys.argv[2], sys.argv[3]]
import pullfrog_standalone_sqlite as sql
from test_pullfrog_standalone_store import initial
b = sql.SQLiteBackend(sys.argv[1], 'fr-meyer/agent-toolkit', 113, create=True)
sql.Store(b, trusted_reducers=(initial,)).transaction(None, initial)
os._exit(19)
"""
        proc = subprocess.run([sys.executable, '-c', code, str(path),
                               str(Path(__file__).resolve().parents[1]),
                               str(Path(__file__).resolve().parent)], check=False)
        self.assertEqual(proc.returncode, 19)
        b = sql.SQLiteBackend(path, 'fr-meyer/agent-toolkit', 113)
        self.assertEqual(b.read()['sequence'], 1)
        with self.assertRaisesRegex(core.StoreError, 'compare_and_swap'):
            sql.Store(b, trusted_reducers=(fixtures.initial,)).transaction(None, fixtures.initial)


class ControllerSQLiteTests(fixtures.ControllerAdapterTests):
    def setUp(self):
        super().setUp()
        api = dict(vars(core), Store=sql.Store, ControllerAdapter=sql.ControllerAdapter)
        self.enterContext(patch.object(fixtures, "s", SimpleNamespace(**api)))
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / 'controller.sqlite'
        self.backend = sql.SQLiteBackend(self.path, self.f.request['repository_slug'], self.f.request['pr_number'], create=True)
        self.adapter = sql.ControllerAdapter(self.backend)

    def test_restart_second_attempt_artifacts(self):
        second = self.successor()
        before = self.backend.records
        self.backend = sql.SQLiteBackend(self.path, self.f.request['repository_slug'], self.f.request['pr_number'])
        self.adapter = sql.ControllerAdapter(self.backend)
        intent, observation = self.publish_attempt(second, '3'*40, '4'*40, 116)
        self.adapter.reconcile(observation, self.f.policy, expected_digest=intent['journal_digest'], now=119)
        self.assertEqual(self.backend.records[:len(before)], before)
        doc = self.backend.read()['document']
        self.assertEqual(doc['state']['started_at'], 110)
        self.assertEqual(doc['state']['attempts'], 2)
        self.assertEqual(doc['artifacts']['worker_plan']['attempt'], 2)
        self.assertEqual(doc['request']['budget']['max_attempts'], 2)


if __name__ == '__main__':
    unittest.main()
