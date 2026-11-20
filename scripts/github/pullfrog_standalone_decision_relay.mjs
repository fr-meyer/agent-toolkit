/** Fixed operation relay. No CLI entrypoint, model discovery, or implicit qualification. */
import net from 'node:net';
import fs from 'node:fs/promises';
import path from 'node:path';
import {createHmac, timingSafeEqual} from 'node:crypto';
import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';

const MAX = 131072;
const PIN = '30786562e236aab6a924981c62aa61b920132c76';
const OP = 'pullfrog.standalone.decision.v1';
const ROOT = path.dirname(fileURLToPath(import.meta.url));
const requireThat = x => { if (!x) throw Error('relay_refused'); };
const exact = (x, keys) => x && typeof x === 'object' && !Array.isArray(x) &&
  Object.keys(x).sort().join(',') === [...keys].sort().join(',');

// Python is an explicit trusted, absolute stdlib interpreter, never a shell.
// The existing codec owns canonical hashing (Python escaping/integer semantics),
// duplicate/nonfinite JSON rejection and full payload + typed outcome validation.
const VALIDATE = String.raw`
import sys,json
sys.path.insert(0,sys.argv[1])
import pullfrog_standalone_decision_codec as c
import pullfrog_standalone_contract as k
from pullfrog_standalone_decision_transport import _json
v=_json(sys.stdin.buffer.read(131073))
r=_json(v['raw'].encode()); now=v['now']; deadline=r['deadline']
assert type(r) is dict and set(r)=={'operation','nonce','deadline','payload_digest','batch','options'}
assert r['operation']=='pullfrog.standalone.decision.v1'
assert type(r['nonce']) is str and len(r['nonce'])==64 and all(x in '0123456789abcdef' for x in r['nonce'])
p=r['batch']['state']
a=dict(now=now,deadline=deadline,destination_authorized=True)
b,o=c.encode(p,**a)
assert b==r['batch']
options=r['options']
assert type(options) is dict and set(options)==set(o)
assert all(type(options[x]) is type(o[x]) for x in o)
# timeoutMs is a duration recorded at client encoding, not server receipt time.
# Validate its original epoch-second origin, without weakening current freshness.
timeout=options['timeoutMs']
assert 1000 <= timeout <= 30000 and timeout % 1000 == 0
encoded_at=deadline-timeout//1000
assert encoded_at <= now
_,original=c.encode(p,now=encoded_at,deadline=deadline,destination_authorized=True)
assert options==original
assert r['payload_digest']==k.digest(p)
assert c.SOURCE_PIN==sys.argv[2]
if 'outcome' in v:
 outcome=v['outcome']
 receipt=dict(source_pin=c.SOURCE_PIN,agent_id=c.AGENT_ID,purpose=c.PURPOSE,payload_digest=k.digest(p),outcome_digest=k.digest(outcome))
 c.decode(p,outcome,trusted_receipt=receipt,**a)
 print(json.dumps(receipt,separators=(',',':')))
else:
 print('{}')
`;

function validate(python, value, signal) {
  // Refuse serialization failures before acquiring a subprocess.
  const input = JSON.stringify(value, (key,item) => {
    requireThat(typeof item !== 'number' || (Number.isFinite(item) && (!Number.isInteger(item) || Number.isSafeInteger(item))));
    return item;
  });
  requireThat(Buffer.byteLength(input) <= MAX);
  return new Promise((resolve, reject) => {
    const child = spawn(python, ['-I', '-B', '-c', VALIDATE, ROOT, PIN], {
      env: {PATH: '/usr/bin:/bin', PYTHONDONTWRITEBYTECODE: '1'},
      stdio: ['pipe','pipe','ignore'], signal, killSignal: 'SIGKILL'});
    let data = Buffer.alloc(0), failure;
    // AbortError precedes close; keep the handler owned until the child is reaped.
    child.on('error', error => { failure = error; });
    child.stdout.on('data', chunk => {
      data = Buffer.concat([data,chunk]);
      if (data.length > MAX) child.kill('SIGKILL');
    });
    child.on('close', code => {
      if (failure || code !== 0 || data.length > MAX) reject(failure ?? Error('codec_refused'));
      else { try { resolve(JSON.parse(data)); } catch { reject(Error('codec_refused')); } }
    });
    child.stdin.on('error', () => {});
    child.stdin.end(input);
  });
}

export async function startDecisionRelay({socketPath, relaySecret, api, owningSignal,
  qualifyBinding, pythonExecutable, maxConnections=4, replayCapacity=1024} = {}) {
  requireThat(process.platform === 'linux' && typeof socketPath === 'string' &&
    path.isAbsolute(socketPath) && path.normalize(socketPath) === socketPath);
  requireThat(typeof relaySecret === 'string' && /^[\x20-\x7e]{32,256}$/.test(relaySecret));
  requireThat(typeof pythonExecutable === 'string' && path.isAbsolute(pythonExecutable));
  requireThat(api && typeof api.runtime?.decisions?.evaluate === 'function');
  requireThat(owningSignal instanceof AbortSignal && !owningSignal.aborted && typeof qualifyBinding === 'function');
  requireThat(Number.isInteger(maxConnections) && maxConnections >= 1 && maxConnections <= 4);
  requireThat(Number.isInteger(replayCapacity) && replayCapacity >= 1 && replayCapacity <= 4096);
  const evaluate = api.runtime.decisions.evaluate.bind(api.runtime.decisions);
  // The owning host verifies actual SDK/runtime identity and provider admission.
  // No boolean configuration flag or caller source-pin is accepted as proof.
  const binding = await qualifyBinding({api, evaluate: api.runtime.decisions.evaluate,
    agentId:'franck', purpose:'pullfrog.standalone.recommendation', sourcePin:PIN,
    signal:owningSignal});
  const peers = new Set(), seen = new Map(), inFlight = new Set();
  let server, identity, closePromise;
  let ready = false, closing = false, active = 0;
  const onOwnerAbort = () => { void close().catch(() => {}); };
  // Every caller observes the same cleanup, including failures and unresolved holds.
  const close = () => {
    if (closePromise) return closePromise;
    closing = true; ready = false;
    owningSignal.removeEventListener('abort',onOwnerAbort);
    closePromise = (async () => {
      for (const peer of peers) peer.destroy();
      if (server?.listening) await new Promise((resolve,reject) =>
        server.close(error => error ? reject(error) : resolve()));
      // Socket shutdown/AbortSignal delivery is not owned SDK settlement.
      // A noncooperative call keeps this promise pending and the binding held.
      await Promise.allSettled([...inFlight]);
      let cleanupError;
      try {
        if (identity) {
          const current = await fs.lstat(socketPath);
          if (current.dev === identity.dev && current.ino === identity.ino) await fs.unlink(socketPath);
        }
      } catch (error) { if (error.code !== 'ENOENT') cleanupError = error; }
      try { if (typeof binding?.release === 'function') await binding.release(); }
      catch (error) {
        if (cleanupError) throw new AggregateError([cleanupError,error],'relay_cleanup_failed');
        throw error;
      }
      if (cleanupError) throw cleanupError;
    })();
    return closePromise;
  };
  try {
    requireThat(binding && typeof binding.assertAdmissible === 'function' && typeof binding.release === 'function');
    const parent = path.dirname(socketPath);
    let current = '/';
    for (const part of parent.split('/').slice(1)) {
      current = path.join(current,part);
      requireThat(!(await fs.lstat(current)).isSymbolicLink());
    }
    const directory = await fs.stat(parent);
    requireThat(directory.uid === process.geteuid() && (directory.mode & 0o077) === 0);
    try { await fs.lstat(socketPath); throw Error('existing_path_refused'); }
    catch (error) { if (error.code !== 'ENOENT') throw error; }
    requireThat(!owningSignal.aborted);
    server = net.createServer(socket => {
      if (!ready || closing || active >= maxConnections || peers.size >= maxConnections || owningSignal.aborted) return socket.destroy();
      peers.add(socket);
      const controller = new AbortController();
      const abort = () => {controller.abort(); socket.destroy();};
      const timer = setTimeout(abort,30000);
      owningSignal.addEventListener('abort',abort,{once:true});
      socket.once('close', () => {
        controller.abort(); clearTimeout(timer); peers.delete(socket);
        owningSignal.removeEventListener('abort',abort);
      });
      socket.on('error',abort);
      let data = Buffer.alloc(0), dispatched = false;
      const handleData = async chunk => {
        let ownsSlot = false;
        try {
          requireThat(!dispatched && active < maxConnections);
          data = Buffer.concat([data,chunk]);
          requireThat(data.length <= MAX);
          if (!data.includes(10)) return;
          requireThat(data.at(-1) === 10 && data.indexOf(10) === data.length-1);
          dispatched = true;
          active++; ownsSlot = true;
          // Python parser catches duplicates in both JSON layers before SDK call.
          // Envelope contains only two strings; enforce unique keys lexically by
          // exact reserialization shape after parsing, allowing normal whitespace.
          const text = new TextDecoder('utf-8',{fatal:true}).decode(data);
          const envelope = JSON.parse(text);
          requireThat(!duplicateKeys(text));
          requireThat(exact(envelope,['body','mac']) && typeof envelope.body === 'string' &&
            typeof envelope.mac === 'string' && /^[0-9a-f]{64}$/.test(envelope.mac));
          const expected = createHmac('sha256',relaySecret).update(envelope.body).digest();
          requireThat(timingSafeEqual(expected,Buffer.from(envelope.mac,'hex')));
          const request = JSON.parse(envelope.body);
          safeNumbers(request);
          const now = Math.floor(Date.now()/1000);
          await validate(pythonExecutable,{raw:envelope.body,now},controller.signal);
          // Validate original body too: JSON.parse alone would erase duplicate keys.
          requireThat(!duplicateKeys(envelope.body));
          const left = request.deadline*1000-Date.now();
          requireThat(left > 0 && left <= 30000);
          clearTimeout(timer);
          const deadlineTimer = setTimeout(abort,left);
          socket.once('close',()=>clearTimeout(deadlineTimer));
          for (const [nonce,expires] of seen) if (expires <= Date.now()) seen.delete(nonce);
          requireThat(!seen.has(request.nonce) && seen.size < replayCapacity);
          seen.set(request.nonce,request.deadline*1000);
          await binding.assertAdmissible({api,sourcePin:PIN,agentId:'franck',signal:controller.signal});
          requireThat(!controller.signal.aborted && Date.now() < request.deadline*1000);
          const outcome = await evaluate(request.batch, {...request.options,
            timeoutMs:Math.max(1,request.deadline*1000-Date.now()),signal:controller.signal});
          requireThat(!controller.signal.aborted && Date.now() < request.deadline*1000);
          const trusted_receipt = await validate(pythonExecutable,{raw:envelope.body,now,outcome},controller.signal);
          requireThat(!controller.signal.aborted && Date.now() < request.deadline*1000);
          const reply = {operation:OP,nonce:request.nonce,deadline:request.deadline,
            payload_digest:request.payload_digest,outcome,trusted_receipt};
          const body = JSON.stringify(reply);
          const wire = JSON.stringify({body,mac:createHmac('sha256',relaySecret).update(body).digest('hex')})+'\n';
          requireThat(Buffer.byteLength(wire) <= MAX);
          socket.end(wire);
        } catch { abort(); }
        finally { if (ownsSlot) active--; }
      };
      socket.on('data', chunk => {
        const task = handleData(chunk);
        inFlight.add(task);
        task.then(() => inFlight.delete(task), () => inFlight.delete(task));
      });
    });
    await new Promise((resolve,reject) => {
      server.once('error',reject);
      server.listen(socketPath,resolve);
    });
    // Record ownership before chmod so post-listen failures still clean up.
    identity = await fs.lstat(socketPath);
    await fs.chmod(socketPath,0o600);
    owningSignal.addEventListener('abort',onOwnerAbort,{once:true});
    requireThat(!owningSignal.aborted);
    ready = true;
    return {close};
  } catch (startupError) {
    try { await close(); }
    catch (cleanupError) {
      throw new AggregateError([startupError,cleanupError],'relay_startup_cleanup_failed');
    }
    throw startupError;
  }
}

// Tokenizer tracks object key sets; JSON.parse validates the actual grammar.
function duplicateKeys(text) {
  const stack=[];
  for(let i=0;i<text.length;i++) {
    const ch=text[i];
    if(ch==='{') stack.push(new Set());
    else if(ch==='[') stack.push(null);
    else if(ch==='}' || ch===']') stack.pop();
    else if(ch==='"') {
      const begin=i++;
      while(i<text.length && text[i]!=='"') {
        if(text.charCodeAt(i)===92) i++;
        i++;
      }
      const key=JSON.parse(text.slice(begin,i+1));
      let j=i+1; while(j<text.length && text[j].trim()==='') j++;
      if(text[j]===':') {
        const set=stack.at(-1);
        if(!set || set.has(key)) return true;
        set.add(key);
      }
    }
  }
  return false;
}


// Fail before SDK dispatch rather than evaluate rounded evidence while signing
// its original Python digest. Python's codec applies the identical integer cap.
function safeNumbers(value) {
  if (typeof value === 'number') {
    requireThat(Number.isFinite(value) && (!Number.isInteger(value) || Number.isSafeInteger(value)));
  } else if (Array.isArray(value)) {
    for (const item of value) safeNumbers(item);
  } else if (value && typeof value === 'object') {
    for (const item of Object.values(value)) safeNumbers(item);
  }
}
