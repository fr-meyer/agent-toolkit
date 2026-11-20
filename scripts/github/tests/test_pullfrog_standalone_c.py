import copy
import hashlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pullfrog_standalone_worker as w


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.r = {'schema': 'pullfrog-standalone-request.v1', 'repository_slug': 'fr-meyer/agent-toolkit', 'pr_number': 1, 'request_id': 'fixture-1', 'initiator': {'account_id': 1, 'login': 'owner', 'type': 'User'}, 'base_ref': 'dev', 'base_sha': '1'*40, 'head_ref': 'fix/example', 'head_sha': '2'*40, 'task': 'Untrusted task, not commands', 'allowed_paths': ['src'], 'issued_at': 100, 'expires_at': 1000, 'policy_mode': 'standalone', 'budget': {'max_attempts': 3, 'max_seconds': 100, 'max_cost_microusd': 100}}
        self.b = w.contract.binding(self.r)
        self.dest = {'slug': self.r['repository_slug'], 'head_repository_slug': self.r['repository_slug'], 'pr_number': 1, 'base_ref': 'dev', 'base_sha': '1'*40, 'head_ref': 'fix/example', 'head_sha': '2'*40, 'default_branch': 'main', 'protected_refs': ['dev', 'main']}
        self.e = {'binding': self.b, 'worker': {'admitted_binding': self.b, 'claim_id': 'claim-1', 'claim_status': 'active', 'usage': {'attempts': 1, 'seconds': 10, 'cost_microusd': 5}, 'execution': {'executor_id': 'coding', 'validator_id': 'trusted-validation', 'publisher_id': 'broker', 'recipe_id': 'stdlib-v1', 'required_tests': ['unit'], 'worker_write_credentials': False}, 'destination': self.dest}}
        self.refresh()
        self.p = self.prepare()
        self.c = {'binding': self.b, 'plan_digest': self.p['plan_digest'], 'evidence_digest': self.p['evidence_digest'], 'validator_id': 'trusted-validation', 'recipe_id': 'stdlib-v1', 'seal': {'schema': 'pullfrog-standalone-patch-seal.v1', 'source_head_sha': '2'*40, 'patch_digest': 'a'*64, 'patch_bytes': 10, 'changed_paths': ['src/a.py'], 'changed_paths_digest': w.contract.digest(['src/a.py'])}, 'observed_destination': self.dest, 'tests': {'patch_digest': 'a'*64, 'source_head_sha': '2'*40, 'recipe_id': 'stdlib-v1', 'results': {'unit': 'passed'}}, 'cost_microusd': 7, 'parent_sha': '2'*40, 'result_head_sha': '3'*40}

    def refresh(self):
        self.d = {'binding': self.b, 'status': 'ok', 'outcome': 'implement', 'evidence_digest': w.contract.digest(self.e), 'provenance': {'provider': 'fixture'}}

    def prepare(self):
        return w.prepare(self.r, self.e, self.d, current_head_sha='2'*40, now=110)

    def validate(self, **kwargs):
        return w.validate_candidate(self.r, self.p, self.c, current_head_sha=kwargs.get('head', '2'*40), now=kwargs.get('now', 120))

    def test_success_and_conserved_usage(self):
        p = self.validate()
        self.assertEqual(p['usage_after'], {'attempts': 2, 'seconds': 20, 'cost_microusd': 12})
        self.assertFalse(p['merge_allowed'])
        self.assertEqual(self.r['head_sha'], '2'*40)

    def test_prepare_rejections(self):
        for field, value in [('attempts', 3), ('seconds', 100), ('cost_microusd', None), ('attempts', True)]:
            with self.subTest(field=field, value=value):
                old = copy.deepcopy(self.e)
                self.e['worker']['usage'][field] = value
                self.refresh()
                with self.assertRaises(w.WorkerError): self.prepare()
                self.e = old
        self.refresh()
        self.d['outcome'] = 'skip'
        with self.assertRaises(w.WorkerError): self.prepare()

    def test_candidate_rejections(self):
        mutations = [lambda c: c.update(cost_microusd=None), lambda c: c.update(cost_microusd=100), lambda c: c.update(validator_id='coding'), lambda c: c.update(parent_sha='4'*40), lambda c: c['tests']['results'].update(unit='skipped'), lambda c: c['tests'].update(patch_digest='b'*64), lambda c: c.update(evidence_digest='b'*64), lambda c: c['observed_destination'].update(head_repository_slug='other/repo')]
        for mutate in mutations:
            original = copy.deepcopy(self.c)
            mutate(self.c)
            with self.assertRaises(w.WorkerError): self.validate()
            self.c = original

    def test_scope_and_authority_paths(self):
        for path in ['src2/a.py', '.github/workflows/a.yml', '../src/a.py', 'scripts/github/pullfrog_standalone_worker.py']:
            self.c['seal']['changed_paths'] = [path]
            self.c['seal']['changed_paths_digest'] = w.contract.digest([path])
            with self.assertRaises(w.WorkerError): self.validate()

    def test_expiry_stale_head_and_plan_substitution(self):
        with self.assertRaises(Exception): self.validate(head='4'*40)
        with self.assertRaises(w.WorkerError): self.validate(now=200)
        self.p['attempt'] = 1
        with self.assertRaises(w.WorkerError): self.validate()

    def test_reconciliation_never_blind_retries(self):
        p = self.validate()
        o = {'binding': self.b, 'plan_digest': p['plan_digest'], 'read_status': 'ok', 'repository_slug': self.r['repository_slug'], 'head_ref': self.r['head_ref'], 'head_sha': '2'*40}
        def status():
            receipt = w.reconcile_publication(self.r, p, o)
            self.assertFalse(receipt['retry_allowed'])
            self.assertEqual(receipt['usage']['attempts'], 2)
            return receipt['status']
        self.assertEqual(status(), 'reconcile_required')
        o.update(publisher_quiescent=True, effect_absent=True)
        self.assertEqual(status(), 'not_published')
        o.update(head_sha='3'*40, parent_sha='2'*40, patch_digest='a'*64)
        self.assertEqual(status(), 'published')
        self.assertEqual(status(), 'published')
        o['head_sha'] = '4'*40
        self.assertEqual(status(), 'conflict')
        o['read_status'] = 'unavailable'
        self.assertEqual(status(), 'reconcile_required')


class PatchSealTests(unittest.TestCase):
    def test_real_git_patch_rebuilt_and_dirty_checkout_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            def git(*args):
                return subprocess.check_output(['git', '-C', directory, *args], stderr=subprocess.DEVNULL)
            git('init'); git('config', 'user.name', 'Fixture'); git('config', 'user.email', 'fixture@example.invalid')
            (root/'a.txt').write_text('before')
            git('add', '.'); git('commit', '-m', 'fixture')
            head = git('rev-parse', 'HEAD').decode().strip()
            (root/'a.txt').write_text('after')
            patch = git('diff', '--binary', '--full-index')
            git('checkout', '--', 'a.txt')
            seal, canonical = w.remediation.seal_standalone_patch(workspace=root, raw_patch=patch, source_head_sha=head)
            self.assertEqual(seal['patch_digest'], hashlib.sha256(canonical).hexdigest())
            self.assertEqual(seal['changed_paths'], ['a.txt'])
            with self.assertRaises(w.remediation.RemediationError):
                w.remediation.seal_standalone_patch(workspace=root, raw_patch=patch, source_head_sha=head)

    def test_real_git_forbidden_and_symlink_patches(self):
        for name, symlink in [(".github/workflows/evil.yml", False), ("link", True)]:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                def git(*args):
                    return subprocess.check_output(['git', '-C', directory, *args], stderr=subprocess.DEVNULL)
                git('init'); git('config', 'user.name', 'Fixture'); git('config', 'user.email', 'fixture@example.invalid')
                git('commit', '--allow-empty', '-m', 'fixture')
                head = git('rev-parse', 'HEAD').decode().strip()
                target = root/name
                target.parent.mkdir(parents=True, exist_ok=True)
                if symlink: target.symlink_to('/tmp/outside')
                else: target.write_text('untrusted')
                git('add', '.')
                patch = git('diff', '--cached', '--binary', '--full-index')
                git('reset', '--hard', head)
                with self.assertRaises(w.remediation.RemediationError):
                    w.remediation.seal_standalone_patch(workspace=root, raw_patch=patch, source_head_sha=head)


if __name__ == '__main__':
    unittest.main()
