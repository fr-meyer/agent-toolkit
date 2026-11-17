import {test} from 'node:test';
import assert from 'node:assert/strict';
import fs, {mkdtemp,rm} from 'node:fs/promises';
import {spawn} from 'node:child_process';
import {createHmac} from 'node:crypto';
import net from 'node:net';
import {startDecisionRelay} from '../pullfrog_standalone_decision_relay.mjs';
const secret='fixture-only-secret-not-live-000000';
const root=new URL('../',import.meta.url).pathname;
const python='/usr/bin/python3';
function run(code,args=[]) {return new Promise((resolve,reject)=>{
 const p=spawn(python,['-B','-c',code,...args],{env:{PATH:'/usr/bin:/bin',PYTHONDONTWRITEBYTECODE:'1'}});
 let out='',err='';p.stdout.on('data',x=>out+=x);p.stderr.on('data',x=>err+=x);
 p.on('error',reject);p.on('close',c=>c?reject(Error(err)):resolve(out));
});}
const fixtureCode = "import sys,json,time;sys.path.insert(0,sys.argv[1]);sys.path.insert(0,sys.argv[1]+'/tests');from test_pullfrog_standalone_decision_codec import CodecTests;import pullfrog_standalone_decision_codec as c;import pullfrog_standalone_contract as k;t=CodecTests();t.setUp();p=t.payload;n=int(time.time());p['request'].update(issued_at=n-1,expires_at=n+60);p['binding']=k.binding(p['request']);p['evidence']['binding']=p['binding'];p['evidence_digest']=k.digest(p['evidence']);b,o=c.encode(p,now=n,deadline=n+20,destination_authorized=True);print(json.dumps(dict(operation='pullfrog.standalone.decision.v1',nonce='a'*64,deadline=n+20,payload_digest=k.digest(p),batch=b,options=o)))";
async function setup(t,evaluate=async()=>({status:'unavailable',reason:'not-configured'}),extra={}) {
 const dir=await mkdtemp('/tmp/relay-node-');const owner=new AbortController();
 let calls=0;const api={runtime:{decisions:{evaluate:async(...a)=>{calls++;return evaluate(...a);}}}};
 const service=await startDecisionRelay({socketPath:dir+'/s',relaySecret:secret,api,owningSignal:owner.signal,
 pythonExecutable:python,qualifyBinding:async()=>({assertAdmissible:async()=>{},release:async()=>{}}),...extra});
 t.after(async()=>{await service.close();await rm(dir,{recursive:true,force:true});});
 return {path:dir+'/s',owner,api,service,calls:()=>calls};
}
function wire(body) {return JSON.stringify({body,mac:createHmac('sha256',secret).update(body).digest('hex')})+'\n';}
function exchange(path,data) {return new Promise(resolve=>{const s=net.connect(path);let out='';s.on('connect',()=>s.write(data));s.on('data',x=>out+=x);s.on('error',()=>{});s.on('close',()=>resolve(out));});}
test('missing owned binding refuses',async()=>{await assert.rejects(startDecisionRelay({}));});
test('Python client to Node fake SDK roundtrip',async t=>{
 const r=await setup(t);
 const code="import sys,json,time;sys.path.insert(0,sys.argv[1]);import pullfrog_standalone_decision_transport as t;p=json.loads(sys.argv[4])['batch']['state'];x=t.DecisionTransport(sys.argv[2],relay_secret=sys.argv[3],destination_authorized=True);print(json.dumps(x(p)));assert x.last_receipt['cost_known'] is False";
 const payload=await run(fixtureCode,[root]);
 const result=JSON.parse(await run(code,[root,r.path,secret,payload]));assert.equal(result.status,'unavailable');assert.equal(r.calls(),1);
});
test('replay and overrides and duplicate keys fail closed',async t=>{
 const r=await setup(t);const body=await run(fixtureCode,[root]);
 assert.ok(await exchange(r.path,wire(body)));assert.equal(await exchange(r.path,wire(body)),'');
 for(const mutate of [x=>x.options.agentId='other',x=>x.options.purpose='exec',x=>x.options.rubricVersion='wrong',x=>x.batch.state.rubric='wrong',x=>x.deadline=1]) {
  const x=JSON.parse(body);x.nonce='b'.repeat(64);mutate(x);assert.equal(await exchange(r.path,wire(JSON.stringify(x))),'');
 }
 assert.equal(await exchange(r.path,wire(body.replace('"operation":','"operation":"wrong","operation":'))),'');
 assert.equal(await exchange(r.path,'{"body":"{}","body":"{}","mac":"'+'0'.repeat(64)+'"}\n'),'');
 assert.equal(await exchange(r.path,wire('{"x":NaN}')),'');
 assert.equal(r.calls(),1);
});
test('disconnect aborts owned call',async t=>{
 let started;const ready=new Promise(r=>started=r);let aborted;const done=new Promise(r=>aborted=r);
 const r=await setup(t,async(b,o)=>{started();await new Promise(resolve=>o.signal.addEventListener('abort',()=>{aborted();resolve();},{once:true}));throw Error('cancelled');});
 const body=await run(fixtureCode,[root]);const socket=net.connect(r.path);await new Promise(res=>socket.once('connect',res));socket.write(wire(body));await ready;socket.destroy();await done;assert.equal(r.calls(),1);
});
test('unknown provider outcome is not receipted',async t=>{
 const r=await setup(t,async()=>({status:'mystery'}));
 assert.equal(await exchange(r.path,wire(await run(fixtureCode,[root]))),'');assert.equal(r.calls(),1);
});
test('owner abort cancels call and capacity refuses second connection',async t=>{
 let started;const ready=new Promise(r=>started=r);let aborted;const done=new Promise(r=>aborted=r);
 const r=await setup(t,async(b,o)=>{started();await new Promise(resolve=>o.signal.addEventListener('abort',()=>{aborted();resolve();},{once:true}));throw Error('cancelled');},{maxConnections:1});
 const body=await run(fixtureCode,[root]);const socket=net.connect(r.path);await new Promise(res=>socket.once('connect',res));socket.write(wire(body));await ready;
 assert.equal(await exchange(r.path,wire(body)),'');r.owner.abort();await done;assert.equal(r.calls(),1);
});
test('oversize and wrong MAC never dispatch',async t=>{
 const r=await setup(t);assert.equal(await exchange(r.path,'x'.repeat(131073)+String.fromCharCode(10)),'');
 assert.equal(await exchange(r.path,JSON.stringify({body:'{}',mac:'0'.repeat(64)})+String.fromCharCode(10)),'');assert.equal(r.calls(),0);
});

async function startupOptions(socketPath,released) {
 return {socketPath,relaySecret:secret,api:{runtime:{decisions:{evaluate:async()=>{throw Error('must_not_dispatch');}}}},
  owningSignal:new AbortController().signal,pythonExecutable:python,
  qualifyBinding:async()=>({assertAdmissible:async()=>{},release:async()=>released()})};
}
test('failed startup releases binding and preserves an existing unrelated path',async t=>{
 const dir=await mkdtemp('/tmp/relay-startup-');t.after(()=>rm(dir,{recursive:true,force:true}));
 let releases=0;const released=()=>releases++;
 await assert.rejects(startDecisionRelay(await startupOptions(dir+'/missing/s',released)));
 assert.equal(releases,1);
 const existing=dir+'/existing';await fs.writeFile(existing,'unrelated');
 await assert.rejects(startDecisionRelay(await startupOptions(existing,released)));
 assert.equal(releases,2);assert.equal(await fs.readFile(existing,'utf8'),'unrelated');
});
test('post-listen startup failure removes only owned socket and releases binding',async t=>{
 const dir=await mkdtemp('/tmp/relay-startup-');t.after(()=>rm(dir,{recursive:true,force:true}));
 const socketPath=dir+'/s';let releases=0;const chmod=fs.chmod;
 t.mock.method(fs,'chmod',async(p,...args)=>{if(p===socketPath) throw Error('fixture_chmod_failure');return chmod(p,...args);});
 await assert.rejects(startDecisionRelay(await startupOptions(socketPath,()=>releases++)),/fixture_chmod_failure/);
 assert.equal(releases,1);await assert.rejects(fs.lstat(socketPath),{code:'ENOENT'});
});
test('close shares cleanup promise and retains binding until aborted SDK settles',async t=>{
 let started,observeAbort,finish;let releases=0;
 const ready=new Promise(resolve=>started=resolve);const aborted=new Promise(resolve=>observeAbort=resolve);
 const pending=new Promise(resolve=>finish=resolve);
 const r=await setup(t,async(b,o)=>{started();o.signal.addEventListener('abort',observeAbort,{once:true});await pending;return {status:'unavailable',reason:'not-configured'};},
  {qualifyBinding:async()=>({assertAdmissible:async()=>{},release:async()=>{releases++;}})});
 const socket=net.connect(r.path);await new Promise(resolve=>socket.once('connect',resolve));
 socket.write(wire(await run(fixtureCode,[root])));await ready;
 const first=r.service.close(),second=r.service.close();let finished=false;first.then(()=>finished=true);
 try {
  assert.equal(first,second);await aborted;await new Promise(resolve=>setImmediate(resolve));
  assert.equal(releases,0);assert.equal(finished,false);
 } finally {finish();}
 await Promise.all([first,second]);assert.equal(releases,1);
 await r.service.close();assert.equal(releases,1);
});

test('release failure is shared and never retried',async t=>{
 let releases=0;const failure=Error('fixture_release_failure');const dir=await mkdtemp('/tmp/relay-release-');
 t.after(()=>rm(dir,{recursive:true,force:true}));
 const options=await startupOptions(dir+'/s',()=>{releases++;throw failure;});
 const service=await startDecisionRelay(options);const first=service.close(),second=service.close();
 assert.equal(first,second);await assert.rejects(first,error=>error===failure);
 await assert.rejects(second,error=>error===failure);assert.equal(releases,1);
 await assert.rejects(service.close(),error=>error===failure);assert.equal(releases,1);
});
test('nonfinite SDK outcome refuses without leaving validator work',async t=>{
 const r=await setup(t,async()=>({status:'unavailable',reason:'not-configured',invalid:NaN}));
 assert.equal(await exchange(r.path,wire(await run(fixtureCode,[root]))),'');
 await r.service.close();assert.equal(r.calls(),1);
});
test('missing codec interpreter fails closed and shutdown completes',async t=>{
 const r=await setup(t,undefined,{pythonExecutable:'/nonexistent-fixture-python-relay'});
 assert.equal(await exchange(r.path,wire(await run(fixtureCode,[root]))),'');
 await r.service.close();assert.equal(r.calls(),0);
});
