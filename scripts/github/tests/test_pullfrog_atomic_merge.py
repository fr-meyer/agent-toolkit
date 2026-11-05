import concurrent.futures
import copy
import hashlib
import importlib.util
import io
import json
import os
import sys
import types
import subprocess
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
import urllib.response
from email.message import Message
from unittest import mock
from pathlib import Path

SCRIPT=Path(__file__).resolve().parents[1]/'pullfrog_atomic_merge.py'
SPEC=importlib.util.spec_from_file_location('dualref_candidate',SCRIPT)
M=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(M)
ENV=dict(os.environ,GIT_CONFIG_NOSYSTEM='1',GIT_CONFIG_GLOBAL='/dev/null',GIT_TERMINAL_PROMPT='0',
 GIT_AUTHOR_NAME='Offline Fixture',GIT_AUTHOR_EMAIL='fixture@example.invalid',
 GIT_COMMITTER_NAME='Offline Fixture',GIT_COMMITTER_EMAIL='fixture@example.invalid')
ENV.pop('GITHUB_TOKEN',None)

def git(directory,*args,input=None):
 r=subprocess.run(['git',*args],cwd=directory,input=input,text=not isinstance(input,bytes),capture_output=True,env=ENV,timeout=12)
 if r.returncode:raise AssertionError('offline git command failed: '+str(args)+' '+str(r.stderr)[-300:])
 return r.stdout.strip() if isinstance(r.stdout,str) else r.stdout


class FakeDurableCustodian:
 def __init__(self):self.plans={};self.lock=threading.Lock()
 def reserve(self,plan):
  with self.lock:
   exists=plan['operation_id'] in self.plans
   if not exists:self.plans[plan['operation_id']]=copy.deepcopy(plan)
  return {'schema':'pullfrog-merge-operation-custody.v1','operation_id':plan['operation_id'],
   'record_digest':M._digest(plan),'durable':True,'exclusive_reservation':True,
   'existing_operation':exists,'artifact_id':1}


class Fixture:
 def __init__(self,root,repository_slug='fr-meyer/agent-toolkit',policy=None):
  self.root=Path(root);self.seed=self.root/'seed';self.remote=self.root/'remote.git'
  self.seed.mkdir();git(self.seed,'init','--quiet','--initial-branch=dev')
  (self.seed/'base.txt').write_text('base\n');git(self.seed,'add','.');git(self.seed,'commit','--quiet','-m','base')
  self.base=git(self.seed,'rev-parse','HEAD')
  git(self.seed,'checkout','--quiet','-b','feat/dualref')
  (self.seed/'feature.txt').write_text('feature\n');git(self.seed,'add','.');git(self.seed,'commit','--quiet','-m','feature')
  self.head=git(self.seed,'rev-parse','HEAD')
  self.head1=git(self.seed,'commit-tree','HEAD^{tree}','-p',self.head,'-m','head-race')
  self.base1=git(self.seed,'commit-tree',self.base+'^{tree}','-p',self.base,'-m','base-race')
  git(self.seed,'init','--quiet','--bare',str(self.remote))
  git(self.seed,'remote','add','origin',str(self.remote))
  git(self.seed,'push','--quiet','origin',self.base+':refs/heads/dev',self.head+':refs/heads/feat/dualref',
    self.head1+':refs/heads/test/head-race',self.base1+':refs/heads/test/base-race')
  policy=M.trusted_author_policy.parse_policy(policy or M.trusted_author_policy.load_policy(repository_slug),repository_slug)
  self.policy=policy
  self.identity={'repository_slug':repository_slug,'pr_number':119,'base_ref':'dev','base_sha':self.base,
   'head_ref':'feat/dualref','head_sha':self.head,'base_repository_slug':repository_slug,
   'head_repository_slug':repository_slug,'author_login':'fr-meyer','author_account_id':26621962,
   'author_type':'User','trusted_author_policy_schema':policy['schema'],
   'trusted_author_policy_digest':M.trusted_author_policy.policy_digest(policy)}
  self.custodian=FakeDurableCustodian()
  self.ledger=self.root/'ledger';self.ledger.mkdir(mode=0o700)
  self.path=M.merge_operation_path(self.ledger,self.identity)
 def ref(self,name):return git(self.remote,'rev-parse','refs/heads/'+name)
 def admission(self,identity):return {'schema':'pullfrog-final-merge-admission.v1','identity':copy.deepcopy(identity),
   'allowed':True,'observed_at':time.time(),'snapshot_digest':'b'*64}


class LocalClient(M.GitHubMergeClient):
 def __init__(self,fixture,mode='normal'):
  super().__init__('https://api.github.com','FAKE_OFFLINE_TOKEN',fixture.identity['repository_slug'],trusted_policy_loader=lambda slug:copy.deepcopy(fixture.policy))
  self.fixture=fixture;self.mode=mode;self.events=[];self.posts=0;self.pending=None;self.submit_hook=None
 def _repository_remote(self):return str(self.fixture.remote)
 def get(self,path):
  if path!=self.allowed_prefix+'/pulls/'+str(self.fixture.identity['pr_number']):raise AssertionError('unapproved metadata read')
  i=self.fixture.identity
  return {'state':'open','draft':False,'mergeable':True,'mergeable_state':'clean','number':i['pr_number'],'title':'Offline exact merge',
   'user':{'login':i['author_login'],'id':i['author_account_id'],'type':i['author_type']},
   'base':{'ref':i['base_ref'],'sha':i['base_sha'],'repo':{'full_name':i['base_repository_slug']}},
   'head':{'ref':i['head_ref'],'sha':i['head_sha'],'repo':{'full_name':i['head_repository_slug']}}}
 def _receive_pack_advertisement(self,remote,token):
  self.events.append('advertisement')
  result=super()._receive_pack_advertisement(remote,token)
  if self.mode in {'no_atomic','v2_only','no_ofs'}:
   packets=[]
   for p in self._pkt_payloads(result):
    if p is None:packets.append(b'0000');continue
    if b'\0' in p:
     first,caps=p.split(b'\0',1)
     remove=b'atomic' if self.mode=='no_atomic' else b'ofs-delta' if self.mode=='no_ofs' else b'report-status'
     p=first+b'\0'+b' '.join(x for x in caps.strip().split() if x!=remove)+b'\n'
    packets.append(self._pkt_line(p))
   return b''.join(packets)
  return result
 def _submit_receive_pack(self,remote,token,body):
  self.posts+=1;self.events.append('submit');self.pending=(remote,token,body)
  if self.submit_hook:self.submit_hook()
  if self.mode=='head_race':git(self.fixture.remote,'update-ref','refs/heads/feat/dualref',self.fixture.head1,self.fixture.head)
  if self.mode=='base_race':git(self.fixture.remote,'update-ref','refs/heads/dev',self.fixture.base1,self.fixture.base)
  if self.mode=='timeout_before_server':raise M.AutoMergeError('simulated_transport_timeout')
  response=super()._submit_receive_pack(remote,token,body)
  if self.mode=='timeout_after_server':raise M.AutoMergeError('simulated_lost_response')
  if self.mode=='mixed_response_after_server':
   return b''.join(self._pkt_line(x.encode()+b'\n') for x in ['unpack ok','ok refs/heads/dev','ng refs/heads/'+self.fixture.identity['head_ref']+' contradictory'])+b'0000'
  return response
 def finish_delayed_server(self):
  if self.pending is None:raise AssertionError('missing delayed body')
  remote,token,body=self.pending
  return super()._submit_receive_pack(remote,token,body)
 def invoke(self,*,admission=None,custody=None,path=None):
  def final(identity):self.events.append('admission');return (admission or self.fixture.admission)(identity)
  def reserve(plan):self.events.append('custody');return (custody or self.fixture.custodian.reserve)(plan)
  return self.push_exact_merge(self.fixture.identity,'Offline exact merge',operation_path=path or self.fixture.path,
   final_admission=final,custody_barrier=reserve)


class DualRefProtocolTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.fixture=Fixture(self.tmp.name)
 def test_success_uses_real_pack_atomic_two_refs_and_ordered_parents(self):
  client=LocalClient(self.fixture);result=client.invoke()
  self.assertEqual(result['ref_outcome'],'confirmed');self.assertFalse(result['pr_projection_verified'])
  self.assertTrue(result['atomic_status_verified'])
  self.assertEqual(client.posts,1);self.assertEqual(self.fixture.ref('dev'),result['sha'])
  self.assertEqual(self.fixture.ref('feat/dualref'),self.fixture.head)
  parents=git(self.fixture.remote,'rev-list','--parents','-n','1',result['sha']).split()
  self.assertEqual(parents,[result['sha'],self.fixture.base,self.fixture.head])
  body=client.pending[2];self.assertIn(b' atomic ',body)
  self.assertIn((self.fixture.head+' '+self.fixture.head+' refs/heads/feat/dualref\n').encode(),body)
  self.assertIn(b'PACK',body);self.assertLess(client.events.index('custody'),client.events.index('admission'))
  self.assertEqual(client.events[client.events.index('admission')+1],'submit')
 def test_real_server_rejects_head_race_and_leaves_base_unchanged(self):
  client=LocalClient(self.fixture,'head_race')
  with self.assertRaises(M.AutoMergeError):client.invoke()
  self.assertEqual(self.fixture.ref('dev'),self.fixture.base)
  self.assertEqual(self.fixture.ref('feat/dualref'),self.fixture.head1)
  self.assertEqual(client.posts,1)
 def test_real_server_rejects_base_race_without_reverting_raced_base(self):
  client=LocalClient(self.fixture,'base_race')
  with self.assertRaises(M.AutoMergeError):client.invoke()
  self.assertEqual(self.fixture.ref('dev'),self.fixture.base1)
  self.assertEqual(self.fixture.ref('feat/dualref'),self.fixture.head)
 def test_missing_atomic_or_supported_report_capability_never_submits(self):
  for mode in ['no_atomic','v2_only','no_ofs']:
   client=LocalClient(self.fixture,mode)
   with self.subTest(mode=mode),self.assertRaises(M.AutoMergeError):client.invoke()
   self.assertEqual(client.posts,0)
 def test_final_admission_failures_and_human_veto_prevent_submission(self):
  for value in [True,{},dict(self.fixture.admission(self.fixture.identity),allowed=False),
    dict(self.fixture.admission(self.fixture.identity),observed_at=time.time()-60),
    dict(self.fixture.admission(self.fixture.identity),observed_at=float('nan'))]:
   # Each attempt has its own fixture; reusing a reserved identity is deliberately
   # reconcile-only, never an implicit second submission authorization.
   with tempfile.TemporaryDirectory() as directory:
    fixture=Fixture(directory);client=LocalClient(fixture)
    with self.assertRaises(M.AutoMergeError):client.invoke(admission=lambda _:value)
    self.assertEqual(client.posts,0)
 def test_custody_missing_or_existing_reservation_prevents_submission(self):
  for response in [{}, {'durable':True}]:
   with tempfile.TemporaryDirectory() as directory:
    client=LocalClient(Fixture(directory))
    with self.assertRaises(M.AutoMergeError):client.invoke(custody=lambda _:response)
    self.assertEqual(client.posts,0)
 def test_old_refs_after_timeout_stay_ambiguous_until_delayed_completion_no_replay(self):
  client=LocalClient(self.fixture,'timeout_before_server')
  for attempt in range(2):
   with self.assertRaisesRegex(M.AutoMergeError,'ambiguous_no_replay'):client.invoke()
   self.assertEqual(client.posts,1);self.assertEqual(self.fixture.ref('dev'),self.fixture.base)
  self.assertEqual(json.loads(self.fixture.path.read_text())['state'],'ambiguous')
  client.finish_delayed_server()
  recovered=client.invoke();self.assertTrue(recovered['recovered']);self.assertFalse(recovered['post_attempted'])
  self.assertFalse(recovered['pr_projection_verified']);self.assertEqual(client.posts,1)
  client.invoke();self.assertEqual(client.posts,1)
 def test_lost_success_response_is_recovered_by_exact_pair_without_second_post(self):
  client=LocalClient(self.fixture,'timeout_after_server');result=client.invoke()
  self.assertTrue(result['recovered']);self.assertEqual(client.posts,1)
  self.assertFalse(result['atomic_status_verified'])
  again=client.invoke();self.assertTrue(again['recovered']);self.assertFalse(again['post_attempted'])
  self.assertEqual(client.posts,1);self.assertFalse(again['downstream_actions_performed'])
 def test_lost_runner_cannot_reserve_same_operation_in_a_new_local_directory(self):
  client=LocalClient(self.fixture,'timeout_before_server')
  with self.assertRaises(M.AutoMergeError):client.invoke()
  second=self.fixture.root/'lost-runner';second.mkdir(mode=0o700)
  second_path=M.merge_operation_path(second,self.fixture.identity)
  replacement=LocalClient(self.fixture)
  with self.assertRaises(M.AutoMergeError):replacement.invoke(path=second_path)
  self.assertEqual(client.posts,1);self.assertEqual(replacement.posts,0)
 def test_same_operation_concurrency_cannot_submit_twice(self):
  entered,release=threading.Event(),threading.Event()
  first=LocalClient(self.fixture);second=LocalClient(self.fixture)
  def hold():entered.set();self.assertTrue(release.wait(5))
  first.submit_hook=hold
  with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
   future=pool.submit(first.invoke);self.assertTrue(entered.wait(5))
   try:
    with self.assertRaisesRegex(M.AutoMergeError,'in_progress'):second.invoke()
   finally:release.set()
   self.assertEqual(future.result(timeout=10)['ref_outcome'],'confirmed')
  self.assertEqual(first.posts,1);self.assertEqual(second.posts,0)
  second.invoke();self.assertEqual(second.posts,0)
 def test_missing_execution_controls_fail_before_any_git_or_metadata(self):
  client=LocalClient(self.fixture)
  with self.assertRaisesRegex(M.AutoMergeError,'execution_controls_required'):
   client.push_exact_merge(self.fixture.identity,'Unsafe legacy caller')
  self.assertEqual(client.posts,0);self.assertEqual(client.events,[])
 def test_callback_cannot_rebind_prepared_identity_or_custodied_plan(self):
  def mutate(identity):
   identity['head_sha']='e'*40
   return self.fixture.admission(identity)
  client=LocalClient(self.fixture)
  with self.assertRaises(M.AutoMergeError):client.invoke(admission=mutate)
  self.assertEqual(client.posts,0)
  with tempfile.TemporaryDirectory() as directory:
   other=LocalClient(Fixture(directory))
   def corrupt(plan):
    plan['merge_sha']='f'*40
    return other.fixture.custodian.reserve(plan)
   with self.assertRaises(M.AutoMergeError):other.invoke(custody=corrupt)
   self.assertEqual(other.posts,0)
 def test_policy_or_actor_change_cannot_mint_another_operation_slot(self):
  changed=copy.deepcopy(self.fixture.identity)
  changed['trusted_author_policy_digest']='f'*64
  changed['author_login']='different'
  self.assertEqual(M.merge_operation_id(changed),M.merge_operation_id(self.fixture.identity))
 def test_independent_prs_prepare_in_parallel_but_one_base_transaction_wins(self):
  other=copy.copy(self.fixture);other.identity=copy.deepcopy(self.fixture.identity)
  other.identity.update(pr_number=120,head_ref='feat/second')
  other.path=M.merge_operation_path(other.ledger,other.identity)
  git(self.fixture.remote,'update-ref','refs/heads/feat/second',self.fixture.head)
  first,second=LocalClient(self.fixture),LocalClient(other)
  barrier=threading.Barrier(2)
  first.submit_hook=lambda:barrier.wait(timeout=5)
  second.submit_hook=lambda:barrier.wait(timeout=5)
  results=[]
  with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
   futures=[pool.submit(client.invoke) for client in [first,second]]
   for future in futures:
    try:results.append(future.result(timeout=12))
    except M.AutoMergeError:results.append(None)
  winners=[value for value in results if value and value.get('ref_outcome')=='confirmed']
  self.assertEqual(len(winners),1)
  self.assertEqual(self.fixture.ref('dev'),winners[0]['sha'])
  self.assertEqual(self.fixture.ref('feat/dualref'),self.fixture.head)
  self.assertEqual(self.fixture.ref('feat/second'),self.fixture.head)
  self.assertEqual([first.posts,second.posts],[1,1])
 def test_strict_status_parser_rejects_missing_duplicate_unexpected_fatal_or_truncated(self):
  refs={'refs/heads/dev','refs/heads/feat/dualref'}
  def response(lines):return b''.join(M.GitHubMergeClient._pkt_line(x.encode()+b'\n') for x in lines)+b'0000'
  good=response(['unpack ok','ok refs/heads/dev','ok refs/heads/feat/dualref'])
  M.GitHubMergeClient._assert_receive_pack_success(good,refs)
  bad=[good[:-1],response(['unpack ok','ok refs/heads/dev']),
   response(['unpack ok','ok refs/heads/dev','ok refs/heads/dev']),
   response(['unpack ok','ok refs/heads/dev','ok refs/heads/evil']),
   response(['unpack ok','ok refs/heads/dev','ok refs/heads/feat/dualref','option forced-update']),
   M.GitHubMergeClient._pkt_line(b'\x03fatal')+b'0000',
   response(['unpack ok','ng refs/heads/dev error\nok refs/heads/evil','ng refs/heads/feat/dualref atomic rejection'])]
  for data in bad:
   with self.subTest(data=data),self.assertRaises(M.AutoMergeError):M.GitHubMergeClient._assert_receive_pack_success(data,refs)
 def test_zero_oids_or_same_ref_cannot_build_transaction(self):
  for values in [{'old_oid':'0'*40},{'head_oid':'0'*40},{'head_ref':'refs/heads/dev'}]:
   args={'old_oid':self.fixture.base,'new_oid':self.fixture.head1,'ref':'refs/heads/dev',
    'head_oid':self.fixture.head,'head_ref':'refs/heads/feat/dualref','capabilities':{'atomic','report-status'},'pack':b'PACKfake'}
   args.update(values)
   with self.subTest(values=values),self.assertRaises(M.AutoMergeError):M.GitHubMergeClient._receive_pack_body(**args)
 def test_http_rpc_never_redirects_authorization_or_retries_a_post(self):
  seen=[]
  class FakeHTTPS(urllib.request.HTTPSHandler):
   def https_open(self,request):
    seen.append((request.full_url,request.get_method()))
    if request.host!='github.com':raise AssertionError('redirect leaked authorization')
    headers=Message();headers['Location']='https://attacker.invalid/secret'
    response=urllib.response.addinfourl(io.BytesIO(b''),headers,request.full_url,302);response.msg='Found';return response
  original=urllib.request.build_opener
  client=M.GitHubMergeClient('https://api.github.com','FAKE_OFFLINE_TOKEN','fr-meyer/agent-toolkit')
  with mock.patch.object(M.urllib.request,'build_opener',side_effect=lambda *handlers:original(*handlers,FakeHTTPS())):
   with self.assertRaisesRegex(M.AutoMergeError,'response_uncertain'):
    client._submit_receive_pack('https://github.com/fr-meyer/agent-toolkit.git','FAKE_OFFLINE_TOKEN',b'fake-pack')
  self.assertEqual(seen,[('https://github.com/fr-meyer/agent-toolkit.git/git-receive-pack','POST')])
 def test_http_rpc_rejects_other_origins_before_transport(self):
  client=M.GitHubMergeClient('https://api.github.com','FAKE_OFFLINE_TOKEN','fr-meyer/agent-toolkit')
  with mock.patch.object(M.urllib.request,'build_opener',side_effect=AssertionError('must not open')):
   for remote in ['http://github.com/fr-meyer/agent-toolkit.git','https://attacker.invalid/repo.git','https://github.com/evil/fork.git']:
    with self.subTest(remote=remote),self.assertRaisesRegex(M.AutoMergeError,'untrusted_git_rpc_origin'):
     client._submit_receive_pack(remote,'FAKE_OFFLINE_TOKEN',b'fake')
 def test_mixed_or_bad_unpack_status_is_uncertain_not_definite_rejection(self):
  refs={'refs/heads/dev','refs/heads/feat/dualref'}
  for lines in [['unpack ok','ok refs/heads/dev','ng refs/heads/feat/dualref denied'],
                ['unpack invalid','ng refs/heads/dev denied','ng refs/heads/feat/dualref denied']]:
   response=b''.join(M.GitHubMergeClient._pkt_line(x.encode()+b'\n') for x in lines)+b'0000'
   with self.subTest(lines=lines),self.assertRaises(M.AutoMergeError) as caught:
    M.GitHubMergeClient._assert_receive_pack_success(response,refs)
   self.assertNotIsInstance(caught.exception,M.AtomicReceivePackRejected)
 def test_corrupted_mixed_response_after_real_commit_recovers_without_replay(self):
  client=LocalClient(self.fixture,'mixed_response_after_server')
  result=client.invoke()
  self.assertTrue(result['recovered']);self.assertFalse(result['atomic_status_verified'])
  self.assertEqual(self.fixture.ref('dev'),result['sha'])
  self.assertEqual(json.loads(self.fixture.path.read_text())['state'],'confirmed')
  client.invoke();self.assertEqual(client.posts,1)


class AtomicIdentityIsolationTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.fixture=Fixture(self.tmp.name)
 def test_only_exact_three_trusted_author_tuples_can_submit(self):
  for account_id,login,kind in [(26621962,'fr-meyer','User'),(285669409,'mergeguez[bot]','Bot'),(325213916,'le-commis[bot]','Bot')]:
   path=Path(self.tmp.name)/str(account_id);path.mkdir();fixture=Fixture(path)
   fixture.identity.update(author_login=login,author_account_id=account_id,author_type=kind)
   client=LocalClient(fixture);self.assertEqual(client.invoke()['ref_outcome'],'confirmed');self.assertEqual(client.posts,1)
 def test_spoofed_or_untrusted_author_tuple_never_submits(self):
  for changes in [{'author_account_id':1},{'author_login':'imposter'},{'author_login':'mergeguez[bot]','author_type':'Bot','author_account_id':1},{'author_type':'Bot'}]:
   client=LocalClient(self.fixture);self.fixture.identity.update(author_login='fr-meyer',author_account_id=26621962,author_type='User');self.fixture.identity.update(changes)
   with self.subTest(changes=changes),self.assertRaises(M.AutoMergeError):client.invoke()
   self.assertEqual(client.posts,0)
 def test_old_partial_identity_and_non_dev_destination_are_rejected(self):
  initial=copy.deepcopy(self.fixture.identity)
  for identity in [{k:initial[k] for k in ['repository_slug','pr_number','base_ref','base_sha','head_ref','head_sha','head_repository_slug']},dict(initial,base_ref='staging'),dict(initial,base_ref='main'),dict(initial,head_repository_slug='another/repo')]:
   self.fixture.identity=identity;client=LocalClient(self.fixture)
   with self.assertRaises(M.AutoMergeError):client.invoke()
   self.assertEqual(client.posts,0)
 def test_final_policy_and_author_changes_block_after_pack_and_custody(self):
  for change in ['policy','author']:
   path=Path(self.tmp.name)/change;path.mkdir();fixture=Fixture(path);client=LocalClient(fixture)
   def final(identity):
    admission=fixture.admission(identity)
    if change=='policy':fixture.policy['trusted_authors']=[a for a in fixture.policy['trusted_authors'] if a['login']!='fr-meyer']
    else:fixture.identity['author_account_id']=1
    return admission
   with self.subTest(change=change),self.assertRaisesRegex(M.AutoMergeError,'merge_pre_submission_controls_failed'):client.invoke(admission=final)
   self.assertIn('admission',client.events);self.assertEqual(client.posts,0);self.assertEqual(fixture.ref('dev'),fixture.base)
 def test_workspace_policy_is_explicit_and_default_toolkit_policy_cannot_be_reused(self):
  path=Path(self.tmp.name)/'workspace';path.mkdir();policy=copy.deepcopy(self.fixture.policy);policy['repository_slug']='example/workspace'
  fixture=Fixture(path,repository_slug=policy['repository_slug'],policy=policy);client=LocalClient(fixture)
  client._trusted_policy_loader=M.trusted_author_policy.load_policy
  with self.assertRaises(M.AutoMergeError):client.invoke()
  self.assertEqual(client.posts,0)
  client._trusted_policy_loader=lambda slug:copy.deepcopy(fixture.policy)
  self.assertEqual(client.invoke()['ref_outcome'],'confirmed')
 def test_foreign_canonical_modules_are_neither_reused_nor_replaced(self):
  names=['pullfrog_trusted_author_policy','pullfrog_cloud_coordinator','pullfrog_cycle_contract','pullfrog_destination_guard','pullfrog_review_contract']
  foreign={name:types.ModuleType(name) for name in names}
  with mock.patch.dict(sys.modules,foreign):
   spec=importlib.util.spec_from_file_location('isolated_atomic_again',SCRIPT);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
   self.assertIsNot(module.trusted_author_policy,foreign['pullfrog_trusted_author_policy'])
   self.assertEqual(module.trusted_author_policy.load_policy()['repository_slug'],'fr-meyer/agent-toolkit')
   for name in names:self.assertIs(sys.modules[name],foreign[name])
 def test_modified_sibling_helper_is_rejected_before_execution(self):
  path=Path(self.tmp.name)/'tampered';path.mkdir()
  engine=path/SCRIPT.name;engine.write_bytes(SCRIPT.read_bytes())
  helper=path/'pullfrog_trusted_author_policy.py';marker=path/'executed'
  helper.write_text('from pathlib import Path\nPath('+repr(str(marker))+').touch()\n')
  spec=importlib.util.spec_from_file_location('tampered_atomic',engine);module=importlib.util.module_from_spec(spec)
  with self.assertRaisesRegex(Exception,'untrusted_policy_helper'):spec.loader.exec_module(module)
  self.assertFalse(marker.exists())
 def test_missing_trusted_read_client_fails_before_git_or_post(self):
  client=M.GitHubMergeClient('https://api.github.com','FAKE_OFFLINE_TOKEN',self.fixture.identity['repository_slug'])
  with mock.patch.object(client,'_git') as git_call,mock.patch.object(client,'_submit_receive_pack') as post:
   with self.assertRaisesRegex(M.AutoMergeError,'trusted_read_client_required'):client.push_exact_merge(self.fixture.identity,'Offline',operation_path=self.fixture.path,final_admission=self.fixture.admission,custody_barrier=self.fixture.custodian.reserve)
  git_call.assert_not_called();post.assert_not_called()

if __name__=='__main__':unittest.main()
