import test from 'node:test';
import assert from 'node:assert/strict';
import { ExpenseSubmission } from '../src/lib/expenseSubmission.js';
const METHOD = 'submit_expense_claim';
function fixture(call, backing = new Map()) {
  let counter = 0;
  const store = { get: async key => structuredClone(backing.get(key)), put: async (key,value) => backing.set(key,structuredClone(value)), remove: async key => backing.delete(key) };
  return new ExpenseSubmission({ slot: 'employee:single', call, store, uuid: () => 'reference-' + ++counter });
}
test('lost success response is recovered and retry never resends it', async () => {
  let writes = 0;
  const submission = fixture(async (method) => {
    if (method === METHOD) { writes++; throw new TypeError('Failed to fetch'); }
    return { found: true, result: { name: 'CLAIM-1' } };
  });
  assert.deepEqual(await submission.submit(METHOD,{payload:{receipt_content:'private-bytes'}},{}),{name:'CLAIM-1'});
  assert.deepEqual(await submission.submit(METHOD,{payload:{}},{}),{name:'CLAIM-1'});
  assert.equal(writes,1);
  assert.equal(submission.pending.args,undefined);
});
test('unknown outcome survives reload with receipts, and changed details cannot start a new request', async () => {
  const backing = new Map(); let writes = 0;
  const offline = async method => { if(method === METHOD) writes++; throw new TypeError('Network unavailable'); };
  const first = fixture(offline,backing);
  await assert.rejects(first.submit(METHOD,{payload:{receipt_content:'private-bytes'}},{project:'saved-project'}));
  const key = first.pending.key;
  const reopened = fixture(offline,backing);
  assert.equal(await reopened.restore(),null);
  assert.equal(reopened.pending.args.payload.receipt_content,'private-bytes');
  await assert.rejects(reopened.submit(METHOD,{payload:{amount:900}},{}));
  assert.equal(reopened.pending.key,key);
  assert.equal(writes,1);
});
test('retry after confirmed rollback uses the same reference and saved receipt', async () => {
  let keys = [], online = false;
  const submission = fixture(async(method,args) => {
    if(method !== METHOD) return {found:false};
    keys.push(args.request_key);
    if(!online) throw new TypeError('Disconnected');
    assert.equal(args.payload.receipt_content,'receipt');
    return {name:'CLAIM-2'};
  });
  await assert.rejects(submission.submit(METHOD,{payload:{receipt_content:'receipt'}},{}));
  online=true;
  assert.deepEqual(await submission.retry(),{name:'CLAIM-2'});
  assert.equal(keys[0],keys[1]);
});
test('validation failures allow corrected details and storage failures send nothing', async () => {
  let writes=0;
  const submission=fixture(async()=>{writes++;throw Object.assign(new Error('Invalid project'),{status:417});});
  await assert.rejects(submission.submit(METHOD,{},{}),/Invalid project/);
  assert.equal(submission.pending,null);
  submission.store.put=async()=>{throw new Error('Storage full');};
  await assert.rejects(submission.submit(METHOD,{},{}),/Storage full/);
  await assert.rejects(submission.submit(METHOD,{},{}),/Storage full/);
  assert.equal(submission.pending,null);
  assert.equal(writes,1);
});
test('simultaneous UI submissions are suppressed and saved results restore after refresh', async () => {
  let resolve, writes=0; const backing=new Map();
  const first=fixture(async()=>{writes++;return new Promise(r=>resolve=r);},backing);
  const saving=first.submit(METHOD,{},{});
  while(!resolve) await new Promise(r=>setImmediate(r));
  await assert.rejects(first.submit(METHOD,{},{}),/already/);
  resolve({name:'CLAIM-3'});await saving;
  const restored=fixture(async()=>{throw new Error('must not send');},backing);
  assert.deepEqual(await restored.restore(),{name:'CLAIM-3'});
  assert.equal(writes,1);
});
