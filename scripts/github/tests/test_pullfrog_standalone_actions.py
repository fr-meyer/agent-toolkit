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
    def get(self, path, **bounds):
        if bounds.get("before_send"):
            bounds["before_send"]()
        if '/jobs?' in path:
            return {'total_count':1,'jobs':[{'id':9,'run_id':7,'head_sha':self.head,'steps':getattr(self,'steps',[]),'conclusion':getattr(self,'job_conclusion','skipped')}]}
        if '/pulls/' in path:
            return dict(number=self.r['pr_number'], state='open',
                        head=dict(sha=self.head, ref=self.r['head_ref'], repo={'full_name':self.r['repository_slug']}),
                        base=dict(sha=self.r['base_sha'], ref=self.r['base_ref'], repo={'full_name':self.r['repository_slug']}))
        return dict(id=7, workflow_id=8, head_sha=self.head, repository={'full_name':self.r['repository_slug']},
                    head_repository={'full_name':self.r['repository_slug']}, event='pull_request',
                    run_attempt=self.attempt, status=self.status, conclusion=self.conclusion)
    def graphql(self, query, variables, **bounds):
        raise AssertionError('unused GraphQL')
    def paginated(self, path):
        return [{'id': 9, 'conclusion': 'timed_out'}]
    def post(self, path, payload, **bounds):
        if bounds.get("before_send"):
            bounds["before_send"]()
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
        port=self.port(); self.client.status='completed'; self.client.conclusion='startup_failure'
        first=self.admit(); routed=self.route(first['journal_digest'],port,'retry_ci')
        self.client.lost=True
        started=ctl.dispatch_action(self.journal,self.policy,port,expected_digest=routed['journal_digest'],now=112)
        self.assertEqual(started['status'],'reconcile_required')
        with self.assertRaises(k.ContractError):
            ctl.dispatch_action(self.journal,self.policy,port,expected_digest=started['journal_digest'],now=113)
        observed=ctl.reconcile_action(self.journal,port,expected_digest=started['journal_digest'],now=113,policy=self.policy)
        self.assertEqual(observed['output']['status'],'observed')
        self.assertEqual(len(self.client.posts),1)
        self.assertTrue(self.client.posts[0][0].endswith('/actions/runs/7/rerun-failed-jobs'))
    def test_stale_and_revoked_dispatch_no_write(self):
        port=self.port(); self.client.status='completed'; self.client.conclusion='startup_failure'
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
        port=self.port(); self.client.status='completed'; self.client.conclusion='startup_failure'; self.client.attempt=2
        observed=port.ci(self.request,self.request['head_sha'],7)
        self.assertNotIn('retry_ci',port.eligible(self.request,self.request['head_sha'],observed,False))

    def test_budget_blocks_dispatch_before_write(self):
        port=self.port(); self.client.status='completed'; self.client.conclusion='startup_failure'
        first=self.admit(); routed=self.route(first['journal_digest'],port,'retry_ci')
        with self.assertRaises(k.ContractError):
            ctl.dispatch_action(self.journal,self.policy,port,expected_digest=routed['journal_digest'],now=2000)
        self.assertEqual(self.client.posts,[])

    def test_review_request_uses_fixed_action_and_independent_readback(self):
        port=self.port(); self.client.status='completed'; self.client.conclusion='success'
        calls=[]
        original=self.client.get
        self.client.get=lambda path, **bounds: ({'object':{'type':'commit','sha':'a'*40}} if '/git/ref/' in path else dict(id=42,path='.github/workflows/pullfrog.yml',state='active') if '/workflows/' in path else original(path,**bounds))
        self.client.post=lambda path,payload,**bounds: calls.append((path,payload))
        port.review_runner=actions.PullfrogWorkflowRunner(self.client,trusted_ref='tags/qualified-source',trusted_sha='a'*40,repository_slug='fr-meyer/agent-toolkit',workflow_id=42)
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
        self.assertTrue(calls[0][0].endswith('/workflows/42/dispatches'))
        self.assertIn(self.request['head_sha'],calls[0][1]['inputs']['prompt'])
        prior.update(status='clean',evidence_digest='new',review_identity={'review_id':11})
        receipt=ctl.reconcile_action(self.journal,port,expected_digest=result['journal_digest'],now=113,policy=self.policy)
        self.assertEqual(receipt['output']['status'],'observed')
        with self.assertRaises(k.ContractError):
            ctl.dispatch_action(self.journal,self.policy,port,expected_digest=receipt['journal_digest'],now=114)
        self.assertEqual(len(calls),1)

    def test_concrete_review_adapter_dispatches_existing_fixed_interface(self):
        port=self.port(); posts=[]
        client=self.client
        original=client.get
        client.get=lambda path, **bounds: ({'object':{'type':'commit','sha':'a'*40}} if '/git/ref/' in path else dict(id=42,path='.github/workflows/pullfrog.yml',state='active') if '/workflows/' in path else original(path))
        client.post=lambda path,payload,**bounds:posts.append((path,payload))
        from pullfrog_standalone_effect_guard import EffectGuard, BoundedClient
        first=self.admit()
        state=self.load()['state']
        guard=EffectGuard(self.request,state,k.binding(self.request),policy_loader=lambda:self.policy,now=111,clock=lambda:0)
        client=BoundedClient(client,guard)
        runner=actions.PullfrogWorkflowRunner(client,trusted_ref='tags/qualified-source',trusted_sha='a'*40,repository_slug='fr-meyer/agent-toolkit',workflow_id=42)
        runner(action=actions.PULLFROG_ACTION,request=self.request,head_sha=self.request['head_sha'],effect_id='e'*64,
               push='disabled',shell='restricted',progress_comments='disabled')
        self.assertTrue(posts[0][0].endswith('/actions/workflows/42/dispatches'))
        self.assertEqual(posts[0][1]['ref'],'qualified-source')
        self.assertEqual(set(posts[0][1]['inputs']),{'prompt','name'})
        self.assertIn(self.request['head_sha'],posts[0][1]['inputs']['prompt'])
        self.assertNotIn(self.request['task'],posts[0][1]['inputs']['prompt'])

    def test_ambiguous_attempt_jump_cannot_confirm_retry(self):
        port=self.port(); self.client.status='completed'; self.client.conclusion='startup_failure'
        observed=port.ci(self.request,self.request['head_sha'],7)
        intent=dict(action='retry_ci',binding=k.binding(self.request),ci=observed)
        self.client.attempt=3
        self.assertIsNone(port.readback(self.request,intent))

    def test_changed_evidence_same_review_id_is_not_new_review(self):
        port=self.port()
        port.review=lambda r,h:dict(status='clean',evidence_digest='changed',review_identity={'review_id':10})
        intent=dict(action='request_review',binding=k.binding(self.request),prior_review_digest='old',prior_review_id=10)
        self.assertIsNone(port.readback(self.request,intent))

    def retry_intent(self):
        port=self.port(); self.client.status='completed'; self.client.conclusion='startup_failure'
        first=self.admit()
        routed=self.route(first['journal_digest'],port,'retry_ci')
        return port,routed

    def test_revoked_during_last_read_never_posts(self):
        port,routed=self.retry_intent()
        raw=self.client.get
        reads=[0]
        def get(path,**bounds):
            result=raw(path,**bounds)
            if '/pulls/' in path:
                reads[0]+=1
                if reads[0] == 4:
                    self.policy['initiators']=[]
            return result
        self.client.get=get
        result=ctl.dispatch_action(self.journal,self.policy,port,expected_digest=routed['journal_digest'],now=112)
        self.assertEqual(self.client.posts,[])
        self.assertEqual(result['status'],'reconcile_required')
        self.assertEqual(self.load()['phase'],'action_started')

    def test_deadline_consumed_by_prerequisite_reads_no_post_and_charged(self):
        port,routed=self.retry_intent(); tick=[0.0]
        raw=self.client.get
        def get(path,**bounds):
            result=raw(path,**bounds)
            if '/jobs?' in path:
                tick[0]=2000.0
            return result
        self.client.get=get
        result=ctl.dispatch_action(self.journal,self.policy,port,expected_digest=routed['journal_digest'],now=112,clock=lambda:tick[0])
        self.assertEqual(self.client.posts,[])
        self.assertEqual(result['status'],'reconcile_required')
        self.assertGreaterEqual(self.load()['state']['seconds'],2002)

    def test_repository_test_timeout_is_not_infrastructure(self):
        port=self.port();self.client.status='completed';self.client.conclusion='timed_out'
        self.client.job_conclusion='timed_out'
        self.client.steps=[dict(number=1,name='Run repository tests',status='completed',conclusion='timed_out')]
        observed=port.ci(self.request,self.request['head_sha'],7)
        self.assertFalse(observed['transient'])
        self.assertEqual(observed['jobs'][0]['steps'][0]['name'],'Run repository tests')
        first=self.admit();result=self.route(first['journal_digest'],port,'retry_ci')
        self.assertEqual(result['output']['decision']['status'],'error')
        self.assertEqual(self.client.posts,[])

    def test_equal_sha_base_and_head_ref_drift_blocked(self):
        port=self.port();raw=self.client.get
        for side in ('base','head'):
            def get(path,**bounds):
                result=raw(path,**bounds)
                if '/pulls/' in path:
                    result[side]['ref']='unexpected-ref'
                return result
            self.client.get=get
            with self.assertRaisesRegex(k.ContractError,'live_destination_drift'):
                port.current(self.request,self.request['head_sha'])
        self.assertEqual(self.client.posts,[])

    def test_timeout_unsupported_transport_refused_before_effect(self):
        port,routed=self.retry_intent()
        self.client.post=lambda path,payload: self.fail('unsupported transport must not be invoked')
        with self.assertRaisesRegex(k.ContractError,'bounded_github_transport_required'):
            ctl.dispatch_action(self.journal,self.policy,port,expected_digest=routed['journal_digest'],now=112)
        self.assertEqual(self.load()['phase'],'action_pending')

    def test_existing_github_client_propagates_timeout_and_pre_send_revocation(self):
        from unittest.mock import patch
        from pullfrog_review_fallback import GitHubClient
        client=GitHubClient('https://api.github.com','boundary-only','fr-meyer/agent-toolkit')
        class Response:
            def __enter__(self): return self
            def __exit__(self,*args): pass
            def read(self,limit): return b'{}'
        with patch('urllib.request.urlopen',return_value=Response()) as http:
            client.post('/repos/fr-meyer/agent-toolkit/actions/runs/7/rerun-failed-jobs',{},timeout=3,before_send=lambda:2)
            self.assertEqual(http.call_args.kwargs['timeout'],2)
        def revoke(): raise k.ContractError('authority_revoked')
        with patch('urllib.request.urlopen') as http:
            with self.assertRaises(k.ContractError):
                client.post('/repos/fr-meyer/agent-toolkit/actions/runs/7/rerun-failed-jobs',{},timeout=3,before_send=revoke)
            http.assert_not_called()

    def test_ci_job_identity_rejects_wrong_run(self):
        port=self.port();raw=self.client.get
        def get(path,**bounds):
            result=raw(path,**bounds)
            if '/jobs?' in path: result['jobs'][0]['run_id']=999
            return result
        self.client.get=get
        with self.assertRaisesRegex(k.ContractError,'ci_job_identity_mismatch'):
            port.ci(self.request,self.request['head_sha'],7)

    def test_ci_job_collection_count_drift_rejected(self):
        port=self.port();raw=self.client.get;pages=[0]
        def get(path,**bounds):
            result=raw(path,**bounds)
            if '/jobs?' in path:
                pages[0]+=1
                result['total_count']=2 if pages[0]==1 else 1
            return result
        self.client.get=get
        with self.assertRaisesRegex(k.ContractError,'incomplete_ci_jobs'):
            port.ci(self.request,self.request['head_sha'],7)

    def test_post_and_readback_elapsed_time_is_conserved(self):
        port,routed=self.retry_intent();tick=[0.0];raw=self.client.post
        def post(path,payload,**bounds):
            result=raw(path,payload,**bounds);tick[0]=4.5;return result
        self.client.post=post
        result=ctl.dispatch_action(self.journal,self.policy,port,expected_digest=routed['journal_digest'],now=112,clock=lambda:tick[0])
        self.assertEqual(result['output']['status'],'observed')
        self.assertGreaterEqual(self.load()['state']['seconds'],7)
