import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pullfrog_standalone_contract import *
from pullfrog_standalone_admission import evaluate

def request():
    return dict(schema=SCHEMA, repository_slug='owner/repo', pr_number=1,
                request_id='req-1', initiator=dict(account_id=123, login='owner', type='User'),
                base_ref='dev', head_ref='fix', base_sha='a'*40, head_sha='b'*40,
                task='Fix tests', allowed_paths=['src/'], issued_at=100, expires_at=1000,
                policy_mode='standalone', budget=dict(max_attempts=2, max_seconds=500, max_cost_microusd=100))

class Tests(unittest.TestCase):
    def setUp(self):
        self.r=request()
        self.p=dict(initiators=[self.r['initiator']], repositories=['owner/repo'], policy_modes=['standalone','speculoos'])
        self.e=dict(kind='issue_comment', delivery_id='one', actor=self.r['initiator'], command='/pr-automation run', head_sha='b'*40)
    def run_event(self,e=None,s=None,now=101):
        return evaluate(self.r,e or self.e,self.p,s,now=now)
    def admitted(self):
        return self.run_event()['state']
    def published(self,s):
        receipt=dict(binding=binding(self.r,head_sha=s['current_head']),status='published',result_head_sha='c'*40,publication_plan_digest='d'*64,usage=dict(attempts=s['attempts'],seconds=5,cost_microusd=1))
        return self.run_event(dict(kind='publication_completed',delivery_id='pub',observation=receipt),s)['state']
    def review(self,s,findings=None,checks=None):
        evidence=dict(binding=binding(self.r,head_sha=s['current_head']),status='findings' if findings else 'clean', findings=findings or [])
        evidence['evidence_digest']=digest(evidence)
        return self.run_event(dict(kind='pullfrog_review_completed',delivery_id='review'+str(s['attempts']),head_sha=s['current_head'],observation=evidence,checks=checks or {}),s)
    def test_contract_copy(self):
        r=validate_request(self.r);r['budget']['max_attempts']=3
        self.assertEqual(self.r['budget']['max_attempts'],2)
    def test_bool_request(self):
        for key in ('pr_number','issued_at','expires_at'):
            r=copy.deepcopy(self.r);r[key]=True
            with self.assertRaises(ContractError):validate_request(r)
    def test_bool_binding(self):
        b=binding(self.r);b['pr_number']=True
        with self.assertRaises(ContractError):validate_binding(b,self.r)
    def test_paths(self):
        for path in ('../x','/x','src/../x','./x','src//x','.git/config','x:*'):
            r=copy.deepcopy(self.r);r['allowed_paths']=[path]
            with self.assertRaises(ContractError):validate_request(r)
    def test_freshness(self):
        validate_request(self.r)
        with self.assertRaises(ContractError):validate_request(self.r,now=1000)
    def test_explicit(self):
        for command in ('hello','/pr-automation run now',' /pr-automation run'):
            e=self.e|dict(command=command)
            self.assertIsNone(self.run_event(e)['state'])
    def test_spoof(self):
        e=self.e|dict(actor=self.r['initiator']|dict(account_id=999))
        self.assertIsNone(self.run_event(e)['state'])
    def test_pullfrog(self):
        self.r['initiator']['login']='pullfrog[bot]'
        self.assertIsNone(self.run_event()['state'])
    def test_manual(self):
        e=self.e|dict(kind='workflow_dispatch',task=self.r['task'])
        self.assertEqual(self.run_event(e)['status'],'admitted')
    def test_duplicate(self):
        s=self.admitted()
        for e in (self.e,self.e|dict(delivery_id='two')):
            self.assertEqual(self.run_event(e,s)['reason'],'duplicate_event')
            self.assertEqual(s['attempts'],1)
    def test_external_push(self):
        s=self.admitted()
        self.assertEqual(self.run_event(self.e|dict(delivery_id='push',kind='pull_request_synchronize',head_sha='c'*40),s)['action'],'reconcile')
    def test_successor(self):
        s=self.published(self.admitted())
        self.assertEqual(s['attempts'],1);self.assertEqual(s['request']['head_sha'],'b'*40)
        self.assertEqual(s['current_head'],'c'*40)
    def test_real_checks(self):
        s=self.published(self.admitted())
        self.assertEqual(self.review(s)['reason'],'required_evidence_missing')
        self.assertEqual(self.review(s,checks={'ci':'success','destination-guard':'success'})['reason'],'ready_for_human')
    def test_speculoos(self):
        self.r['policy_mode']='speculoos'
        s=self.published(self.admitted())
        self.assertEqual(self.review(s,checks={'ci':'success','destination-guard':'success'})['reason'],'required_evidence_missing')
    def test_findings_budget(self):
        s=self.published(self.admitted());res=self.review(s,[{'id':'one'}])
        self.assertEqual(res['state']['attempts'],2)
    def test_decision_stop(self):
        for status in ('unavailable','error','cancelled','ok'):
            s=self.admitted();e=dict(kind='decision_completed',delivery_id=status,observation=dict(binding=binding(self.r),status=status,outcome='skip'))
            res=self.run_event(e,s)
            self.assertTrue(res['state']['terminal']);self.assertEqual(res['state']['attempts'],1)
            self.assertEqual(self.run_event(self.e,res['state'])['status'],'terminal')
    def test_worker_failure(self):
        s=self.admitted();res=self.run_event(dict(kind='worker_failed',delivery_id='fail',observation=dict(binding=binding(self.r))),s)
        self.assertEqual(res['action'],'reconcile')
    def test_state_corruption(self):
        for k,v in [('attempts',True),('seconds',-1),('finding_digests',None),('extra',1)]:
            s=self.admitted();s[k]=v
            with self.assertRaises(ContractError):self.run_event(self.e,s)
    def test_conflict(self):
        s=self.admitted();self.r['request_id']='new'
        with self.assertRaises(ContractError):self.run_event(self.e,s)
    def test_timeout(self):
        s=self.admitted()
        self.assertEqual(self.run_event(self.e|dict(delivery_id='late',command='other'),s,now=700)['reason'],'time_exhausted')

if __name__=='__main__':unittest.main()
