"""Hosted adapter fake-client and static workflow tests, never network calls."""
import copy
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pullfrog_standalone_github as gh
import pullfrog_standalone_contract as contract

ROOT = Path(__file__).resolve().parents[3]

class GitHubAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.actor = {'id': 123, 'login': 'fixture', 'type': 'User'}
        self.policy = {'enabled': True, 'repository_slug': 'owner/repo',
            'initiators': [{'account_id': 123, 'login': 'fixture', 'type': 'User'}],
            'allowed_paths': ['src'], 'protected_refs': ['dev', 'main'],
            'budget': {'max_attempts': 2, 'max_seconds': 500, 'max_cost_microusd': 0}}
        self.pr = {'number': 1, 'state': 'open', 'title': 'Fix fixture', 'body': 'Scoped task',
            'base': {'ref': 'dev', 'sha': 'a'*40, 'repo': {'full_name': 'owner/repo'}},
            'head': {'ref': 'fix/example', 'sha': 'b'*40, 'repo': {'full_name': 'owner/repo'}}}
        self.event = {'action': 'created', 'sender': self.actor, 'repository': {'full_name': 'owner/repo'},
            'issue': {'number': 1, 'pull_request': {}},
            'comment': {'id': 44, 'created_at': '1970-01-01T00:01:40Z', 'body': '/pr-automation run'}}
        self.calls = []
        owner = self
        class Client:
            def get(self, path):
                owner.calls.append(path)
                if path == '/repos/owner/repo': return {'full_name': 'owner/repo', 'default_branch': 'main'}
                if path == '/repos/owner/repo/pulls/1': return copy.deepcopy(owner.pr)
                if path == '/repos/owner/repo/actions/runs/99': return {'id': 99, 'event': 'workflow_dispatch', 'path': '.github/workflows/pullfrog-standalone-admission.yml', 'created_at': '1970-01-01T00:01:40Z'}
                raise RuntimeError('unexpected request')
        self.client = Client()

    def build(self, kind='issue_comment', now=110):
        return gh.build_bundle(self.event, kind, self.policy, self.client, run_id=99, now=now)

    def test_exact_authorized_comment_stable_scope(self):
        a, b = self.build(), self.build(now=120)
        self.assertEqual(a['request'], b['request'])
        self.assertEqual(a['request']['request_id'], 'comment:44')
        self.assertEqual(a['request']['expires_at'], 600)
        self.assertNotIn('speculoos', a['policy']['policy_modes'])
        self.assertEqual(a['request']['allowed_paths'], ['src'])

    def test_ordinary_or_spoofed_comment_stops_before_network(self):
        self.event['comment']['body'] = 'ordinary discussion'
        with self.assertRaises(contract.ContractError): self.build()
        self.assertEqual(self.calls, [])
        self.event['comment']['body'] = '/pr-automation run'
        self.actor['id'] = 124
        with self.assertRaises(contract.ContractError): self.build()
        self.assertEqual(self.calls, [])

    def test_disabled_and_missing_exact_repository(self):
        self.policy['enabled'] = False
        with self.assertRaises(contract.ContractError): self.build()
        self.assertEqual(self.calls, [])
        self.policy['enabled'] = True
        self.event['repository']['full_name'] = 'other/repo'
        with self.assertRaises(contract.ContractError): self.build()

    def test_fork_closed_and_protected_destination(self):
        for mutate in (lambda p: p['head']['repo'].update(full_name='fork/repo'),
                       lambda p: p.update(state='closed'), lambda p: p['head'].update(ref='main')):
            original = copy.deepcopy(self.pr); mutate(self.pr)
            with self.assertRaises(contract.ContractError): self.build()
            self.pr = original

    def test_manual_uses_original_authenticated_run_creation(self):
        self.event['inputs'] = {'pr_number': '1', 'task': 'Explicit task'}
        a, b = self.build('workflow_dispatch'), self.build('workflow_dispatch', now=120)
        self.assertEqual(a['request'], b['request'])
        self.assertEqual(a['request']['issued_at'], 100)
        self.assertEqual(a['request']['request_id'], 'dispatch:99')
        self.assertEqual(a['request']['task'], 'Explicit task')

    def test_expired_replay_never_remints_authority(self):
        with self.assertRaisesRegex(contract.ContractError, 'fresh'):
            self.build(now=601)

    def test_incomplete_protection_and_bool_identity(self):
        self.policy['protected_refs'] = ['dev']
        with self.assertRaises(contract.ContractError): self.build()
        self.policy['protected_refs'] = ['dev', 'main']
        self.event['issue']['number'] = True
        with self.assertRaises(contract.ContractError): self.build()


class HostedWorkflowPolicyTests(unittest.TestCase):
    def setUp(self):
        self.source = ROOT/'templates/starter-workflows/pullfrog-standalone-admission.yml'
        self.text = self.source.read_text()

    def test_manifest_owns_byte_identical_materialization(self):
        self.assertEqual(self.source.read_bytes(), (ROOT/'.github/workflows/pullfrog-standalone-admission.yml').read_bytes())
        manifest = json.loads((ROOT/'templates/repo-workflow-materialization-manifest.json').read_text())
        self.assertIn({'source': str(self.source.relative_to(ROOT)), 'target': '.github/workflows/pullfrog-standalone-admission.yml'}, manifest['workflows'])

    def test_read_only_immutable_disabled_no_provider_or_publication(self):
        self.assertIn("vars.STANDALONE_PR_ADMISSION_DIAGNOSTIC == 'true'", self.text)
        self.assertIn('ref: \u0024{{ vars.STANDALONE_PR_CONTROLLER_SHA }}'.replace('\u0024', '$'), self.text)
        self.assertIn('persist-credentials: false', self.text)
        self.assertIn('cancel-in-progress: false', self.text)
        self.assertNotIn(': write', self.text)
        self.assertNotIn('secrets.', self.text)
        self.assertNotIn('pull_request_target:', self.text)
        self.assertNotIn('pull_request:', self.text)
        self.assertNotIn('inputs.task }}', self.text)
        config = json.loads((ROOT/'scripts/github/pullfrog_standalone_policy.json').read_text())
        self.assertFalse(config['enabled']); self.assertEqual(config['initiators'], [])
        self.assertEqual(config['budget']['max_cost_microusd'], 0)

    def test_actions_pinned_and_no_pr_checkout(self):
        import re
        uses = re.findall(r'uses: ([^\s#]+)', self.text)
        self.assertTrue(uses)
        for action in uses:
            self.assertRegex(action, r'^[\w/-]+@[0-9a-f]{40}$')
        self.assertNotIn('ref: \u0024{{ github.event.pull_request'.replace('\u0024', '$'), self.text)


if __name__ == '__main__': unittest.main()
