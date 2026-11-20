"""Offline HTTP-boundary tests of production action and journal logic."""
import copy
import unittest
import test_pullfrog_standalone_controller as fixtures
import pullfrog_standalone_actions as actions
import pullfrog_standalone_controller as ctl
import pullfrog_standalone_contract as k
import pullfrog_standalone_decision as decision


class Client:
    def __init__(self, request):
        self.r = request
        self.attempt = 1
        self.status = 'in_progress'
        self.conclusion = None
        self.posts = []
        self.lost = False
        self.head = request['head_sha']
    def get(self, path):
        if '/jobs?' in path:
            return {'total_count':1,'jobs':[{'id':9,'conclusion':getattr(self,'job_conclusion','timed_out')}]}
        if '/pulls/' in path:
            return dict(number=self.r['pr_number'], state='open',
                        head=dict(sha=self.head, repo={'full_name':self.r['repository_slug']}),
                        base=dict(sha=self.r['base_sha'], repo={'full_name':self.r['repository_slug']}))
        return dict(id=7, workflow_id=8, head_sha=self.head, repository={'full_name':self.r['repository_slug']},
                    head_repository={'full_name':self.r['repository_slug']}, event='pull_request',
                    run_attempt=self.attempt, status=self.status, conclusion=self.conclusion)
    def paginated(self, path):
        return [{'id': 9, 'conclusion': 'timed_out'}]
    def post(self, path, payload):
        self.posts.append((path,payload)); self.attempt += 1; self.status='in_progress'
        if self.lost:
            raise TimeoutError()


class ActionTests(unittest.TestCase):
    setUp = fixtures.ControllerTests.setUp
    load = fixtures.ControllerTests.load
    admit = fixtures.ControllerTests.admit
    def port(self):
        self.client = Client(self.request)
        return actions.Actions(self.client, dict(ci_run_id=7, ci_workflow_id=8, max_ci_retries=1))
    def route(self, digest, port, action=None):
        def provider(p):
            value={key:copy.deepcopy(p[key]) for key in ('binding','evidence_digest','rubric_version')}
            value.update(schema=decision.V2_PROVIDER_SCHEMA,status='ok',next_action=action,
                         provenance={'provider':'isolated','model':'boundary'})
            return value
        return ctl.route(self.journal,self.policy,self.context,self.execution,self.destination,
                         expected_digest=digest,now=111,provider=provider,clock=lambda:0,actions_port=port)
    def test_ci_completion_required_regression_resumes_same_request_once(self):
        port=self.port(); first=self.admit(); waiting=self.route(first['journal_digest'],port)
        self.client.status='completed'; self.client.conclusion='success'
        complete=ctl.complete_ci(self.journal,self.policy,port,expected_digest=waiting['journal_digest'],now=112)
        self.assertEqual(complete['output']['action'],'decide')
        self.assertEqual(self.load()['phase'],'admitted')
        self.assertEqual(self.load()['state']['attempts'],2)
        with self.assertRaises(k.ContractError):
            ctl.complete_ci(self.journal,self.policy,port,expected_digest=complete['journal_digest'],now=113)
        decided=self.route(complete['journal_digest'],port,'no_action')
        self.assertIsNone(decided['output']['worker_plan'])
        self.assertEqual(self.load()['state']['reason'],'decision_no_action')
    def test_unknown_retry_effect_readback_no_duplicate(self):
        port=self.port(); self.client.status='completed'; self.client.conclusion='timed_out'
        first=self.admit(); routed=self.route(first['journal_digest'],port,'retry_ci')
        self.client.lost=True
        started=ctl.dispatch_action(self.journal,self.policy,port,expected_digest=routed['journal_digest'],now=112)
        self.assertEqual(started['status'],'reconcile_required')
        with self.assertRaises(k.ContractError):
            ctl.dispatch_action(self.journal,self.policy,port,expected_digest=started['journal_digest'],now=113)
        observed=ctl.reconcile_action(self.journal,port,expected_digest=started['journal_digest'],now=113)
        self.assertEqual(observed['output']['status'],'observed')
        self.assertEqual(len(self.client.posts),1)
        self.assertTrue(self.client.posts[0][0].endswith('/actions/runs/7/rerun-failed-jobs'))
    def test_stale_and_revoked_dispatch_no_write(self):
        port=self.port(); self.client.status='completed'; self.client.conclusion='timed_out'
        first=self.admit(); routed=self.route(first['journal_digest'],port,'retry_ci')
        self.client.head='f'*40
        with self.assertRaises(k.ContractError):
            ctl.dispatch_action(self.journal,self.policy,port,expected_digest=routed['journal_digest'],now=112)
        self.client.head=self.request['head_sha']; self.policy['initiators']=[]
        with self.assertRaises(k.ContractError):
            ctl.dispatch_action(self.journal,self.policy,port,expected_digest=routed['journal_digest'],now=112)
        self.assertEqual(self.client.posts,[])
    def test_code_failure_never_eligible_for_infra_retry(self):
        port=self.port(); self.client.status='completed'; self.client.conclusion='failure'
        self.client.job_conclusion='failure'
        observed=port.ci(self.request,self.request['head_sha'],7)
        self.assertNotIn('retry_ci',port.eligible(self.request,self.request['head_sha'],observed,False))
    def test_retry_allowance_exhausted(self):
        port=self.port(); self.client.status='completed'; self.client.conclusion='timed_out'; self.client.attempt=2
        observed=port.ci(self.request,self.request['head_sha'],7)
        self.assertNotIn('retry_ci',port.eligible(self.request,self.request['head_sha'],observed,False))

    def test_budget_blocks_dispatch_before_write(self):
        port=self.port(); self.client.status='completed'; self.client.conclusion='timed_out'
        first=self.admit(); routed=self.route(first['journal_digest'],port,'retry_ci')
        with self.assertRaises(k.ContractError):
            ctl.dispatch_action(self.journal,self.policy,port,expected_digest=routed['journal_digest'],now=2000)
        self.assertEqual(self.client.posts,[])

    def test_review_request_uses_fixed_action_and_independent_readback(self):
        port=self.port(); self.client.status='completed'; self.client.conclusion='success'
        calls=[]; port.review_runner=lambda **kwargs:calls.append(kwargs)
        prior={'status':'incomplete','evidence_digest':'old','review_identity':{'review_id':10}}
        port.review=lambda r,h:copy.deepcopy(prior)
        first=self.admit()
        def published(state):
            state['artifacts']['publication_receipt']={'result_head_sha':self.request['head_sha']}
            return state, {}
        marked=self.journal.transaction(first['journal_digest'],published)
        routed=self.route(marked['journal_digest'],port,'request_review')
        result=ctl.dispatch_action(self.journal,self.policy,port,expected_digest=routed['journal_digest'],now=112)
        self.assertEqual(result['output']['status'],'reconcile_required')
        self.assertEqual(calls[0]['action'],actions.PULLFROG_ACTION)
        self.assertEqual(calls[0]['head_sha'],self.request['head_sha'])
        prior.update(status='clean',evidence_digest='new',review_identity={'review_id':11})
        receipt=ctl.reconcile_action(self.journal,port,expected_digest=result['journal_digest'],now=113)
        self.assertEqual(receipt['output']['status'],'observed')
        with self.assertRaises(k.ContractError):
            ctl.dispatch_action(self.journal,self.policy,port,expected_digest=receipt['journal_digest'],now=114)
        self.assertEqual(len(calls),1)

    def test_concrete_review_adapter_dispatches_existing_fixed_interface(self):
        port=self.port(); posts=[]
        client=self.client
        original=client.get
        client.get=lambda path: ({'object':{'type':'commit','sha':'a'*40}} if '/git/ref/' in path else dict(id=42,path='.github/workflows/pullfrog.yml',state='active') if '/workflows/' in path else original(path))
        client.post=lambda path,payload:posts.append((path,payload))
        runner=actions.PullfrogWorkflowRunner(client,trusted_ref='tags/qualified-source',trusted_sha='a'*40,repository_slug='fr-meyer/agent-toolkit',workflow_id=42)
        runner(action=actions.PULLFROG_ACTION,request=self.request,head_sha=self.request['head_sha'],effect_id='e'*64,
               push='disabled',shell='restricted',progress_comments='disabled')
        self.assertTrue(posts[0][0].endswith('/actions/workflows/42/dispatches'))
        self.assertEqual(posts[0][1]['ref'],'qualified-source')
        self.assertEqual(set(posts[0][1]['inputs']),{'prompt','name'})
        self.assertIn(self.request['head_sha'],posts[0][1]['inputs']['prompt'])
        self.assertNotIn(self.request['task'],posts[0][1]['inputs']['prompt'])

    def test_ambiguous_attempt_jump_cannot_confirm_retry(self):
        port=self.port(); self.client.status='completed'; self.client.conclusion='timed_out'
        observed=port.ci(self.request,self.request['head_sha'],7)
        intent=dict(action='retry_ci',binding=k.binding(self.request),ci=observed)
        self.client.attempt=3
        self.assertIsNone(port.readback(self.request,intent))

    def test_changed_evidence_same_review_id_is_not_new_review(self):
        port=self.port()
        port.review=lambda r,h:dict(status='clean',evidence_digest='changed',review_identity={'review_id':10})
        intent=dict(action='request_review',binding=k.binding(self.request),prior_review_digest='old',prior_review_id=10)
        self.assertIsNone(port.readback(self.request,intent))
