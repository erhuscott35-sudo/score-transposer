import './music.test.mjs';
import assert from 'node:assert/strict';
import fs from 'node:fs';
const {reviewPages,paginateSystems}=await import('../test-output/review.mjs');
const {recognizeLocal}=await import('../test-output/recognition.mjs');
const sample=JSON.parse(fs.readFileSync('lib/sample.json'));
sample.measures.forEach((m,i)=>m.sourcePage=i<14?1:2);
const before=reviewPages(sample);
sample.measures[3].notes[0].lyric='修正';
const after=reviewPages(sample);
assert.notEqual(before[0].fingerprint,after[0].fingerprint);
assert.equal(before[1].fingerprint,after[1].fingerprint);
sample.measures[13].notes.at(-1).tie=true;
const boundary=reviewPages(sample);
assert.notEqual(after[0].fingerprint,boundary[0].fingerprint);
assert.notEqual(after[1].fingerprint,boundary[1].fingerprint);
const placements=paginateSystems(Array.from({length:30},()=>({width:810,height:180})));
assert.ok(placements.at(-1).page>1);
assert.equal(placements.length,30);
for(const p of placements){assert.ok(p.y>=12&&p.y+p.height<=277);assert.ok(p.width<=186);}
assert.equal(paginateSystems([{width:810,height:9000}])[0].page,1);
assert.throws(()=>paginateSystems([{width:0,height:100}]));

const originalFetch=globalThis.fetch;
const response=(body,status=200)=>({ok:status<400,json:async()=>body});
const id='a'.repeat(32);
try{
  let deleted=0,polled=0;
  globalThis.fetch=async(url,options={})=>{
    if(url.endsWith('/health'))return response({apiVersion:3,ready:true});
    if(options.method==='POST')return response({id},202);
    if(options.method==='DELETE'){deleted++;return response({});}
    polled++;return response({state:'succeeded',result:{xml:'<score/>',pageCount:2}});
  };
  const result=await recognizeLocal(new ArrayBuffer(1),'application/pdf',new AbortController().signal,()=>{});
  assert.equal(result.pageCount,2);assert.equal(polled,1);assert.equal(deleted,1);
  const cancel=new AbortController();
  deleted=0;
  globalThis.fetch=async(url,options={})=>{
    if(url.endsWith('/health'))return response({apiVersion:3,ready:true});
    if(options.method==='POST'){cancel.abort();return response({id},202);}
    if(options.method==='DELETE'){deleted++;return response({});}
    return response({state:'cancelled'});
  };
  await assert.rejects(recognizeLocal(new ArrayBuffer(1),'application/pdf',cancel.signal,()=>{}),{name:'AbortError'});
  assert.ok(deleted>=1,'cancel during creation must reach server');
  globalThis.fetch=async()=>response({apiVersion:2,ready:true});
  await assert.rejects(recognizeLocal(new ArrayBuffer(1),'image/png',new AbortController().signal,()=>{}),/最新版/);
}finally{globalThis.fetch=originalFetch;}
console.log('PASS: page review invalidation, cross-page edits, PDF pagination, job polling and cancellation race');
