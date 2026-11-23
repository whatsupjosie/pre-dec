'use strict';
/**
 * Browser recovery: Josie's decision of 2026-11-21 -- a recovery copy reopens
 * the SAME manuscript, and two backups are kept per manuscript.
 * Run: node --test tests/test_2i_recovery_backups_node.js
 *
 * These drive the real writeRecovery, browserManuscripts and
 * uniqueEditorRecoveries out of reach.js in a vm with a localStorage stand-in.
 */
const {test}=require('node:test');
const a=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');

const reach=fs.readFileSync(path.join(__dirname,'../2i/2i-assets/reach.js'),'utf8');
function slice(from,to){
  const start=reach.indexOf(from),end=reach.indexOf(to,start);
  a.ok(start>=0&&end>start,'missing served implementation: '+from);
  return reach.slice(start,end);
}
const source=
  slice('function uniqueEditorRecoveries(','function chooseEditorRecovery(')+
  // the one-line helper only: the lines after it declare documentId, revision
  // and the rest, which this fixture supplies itself.
  slice('function stored(key, fallback)','let workspace = stored(')+
  slice('function recoveryWriterKey(','function rememberStudioResume(')+
  slice('function writeRecovery()','function markDirty()')+
  slice('function browserManuscripts()','function downloadFile(');

function fixture({networked=true}={}){
  const store=new Map();
  const localStorage={
    get length(){return store.size;},
    key:i=>[...store.keys()][i],
    getItem:k=>store.has(k)?store.get(k):null,
    setItem:(k,v)=>{store.set(k,String(v));},
    removeItem:k=>{store.delete(k);}
  };
  const context={
    localStorage,
    RECOVERY_KEY:'rec', editorWriter:'tab-one',
    reachFileMode:false, networked, serverReady:true,
    documentId:'doc-1', revision:0, mutation:1,
    documentTitle:'My manuscript', documentDirty:false,
    conversations:{}, partnerId:'alex', chatHistory:[],
    recoverySafe:true, unsavedNoticeShown:false,
    state:{committed:['']},
    getDocState(){return context.state;},
    rememberWorkspace(){}, pinEditorDocument(){}, setSaveStatus(){},
    JSON, Date, console
  };
  vm.createContext(context);
  vm.runInContext(source,context);
  context.write=(text,{dirty=false,revision=null,id=null}={})=>{
    if(id!==null)context.documentId=id;
    if(revision!==null)context.revision=revision;
    context.state={committed:[text]};
    context.documentDirty=dirty;
    context.mutation++;
    context.writeRecovery();
  };
  context.keys=()=>[...store.keys()].sort();
  // Values built inside the vm carry that realm's prototypes, and
  // deepStrictEqual rejects them on prototype alone. Round-tripping through
  // JSON brings them into this realm so the comparison is about the contents.
  const here=value=>JSON.parse(JSON.stringify(value));
  context.records=()=>here(context.browserManuscripts().map(r=>({id:r.id,dirty:!!r.dirty,slot:r.slot||'current',first:(r.state.committed||[])[0]})));
  return context;
}

test('a second clean save keeps the copy it replaces as the earlier backup',()=>{
  const c=fixture();
  c.write('first version',{revision:1});
  c.write('second version',{revision:2});
  const rows=c.records().filter(r=>r.id==='doc-1');
  a.deepEqual(rows.map(r=>r.slot).sort(),['current','previous']);
  a.equal(rows.find(r=>r.slot==='current').first,'second version');
  a.equal(rows.find(r=>r.slot==='previous').first,'first version');
});

test('only two are kept; a third save pushes the oldest out',()=>{
  const c=fixture();
  c.write('one',{revision:1});
  c.write('two',{revision:2});
  c.write('three',{revision:3});
  const rows=c.records().filter(r=>r.id==='doc-1');
  a.equal(rows.length,2,'two backups, not a growing pile');
  a.deepEqual(rows.map(r=>r.first).sort(),['three','two']);
});

test('the two backups belong to one manuscript and keep its id',()=>{
  const c=fixture();
  c.write('v1',{revision:1});
  c.write('v2',{revision:2});
  for(const row of c.records())a.equal(row.id,'doc-1','a backup is the same manuscript, not a new one');
});

test('each manuscript gets its own pair; one cannot push another out',()=>{
  const c=fixture();
  c.write('A one',{revision:1,id:'doc-a'});
  c.write('A two',{revision:2,id:'doc-a'});
  c.write('B one',{revision:1,id:'doc-b'});
  c.write('B two',{revision:2,id:'doc-b'});
  const byDoc=id=>c.records().filter(r=>r.id===id).map(r=>r.first).sort();
  a.deepEqual(byDoc('doc-a'),['A one','A two']);
  a.deepEqual(byDoc('doc-b'),['B one','B two']);
});

test('a full storage loses the spare, never the current copy',()=>{
  const c=fixture();
  c.write('safe version',{revision:1});
  const real=c.localStorage.setItem;
  // Reject only the earlier-backup write, as a quota would when space runs out.
  c.localStorage.setItem=(key,value)=>{
    if(key.includes(':prev:'))throw Error('QuotaExceededError');
    return real(key,value);
  };
  c.write('newest version',{revision:2});
  c.localStorage.setItem=real;
  const rows=c.records().filter(r=>r.id==='doc-1');
  a.equal(rows.length,1);
  a.equal(rows[0].first,'newest version','the current copy survives a full disk');
  a.equal(c.recoverySafe,true,'and recovery is not declared broken over a lost spare');
});

test('unsaved work in this tab is not cleared because the server has A revision',()=>{
  // The regression this guards: the buffer used to be removed whenever there was
  // any server revision, on the assumption the server held the work. After a
  // failed save it does not, and reopening a clean copy of the same manuscript
  // then took the unsaved writing with it.
  const c=fixture({networked:true});
  c.write('saved to the server',{revision:3});
  c.write('typed after the save failed',{dirty:true,revision:3});
  a.ok(c.keys().some(k=>k.includes(':writer:')),'the unsaved copy exists');
  // Now a clean write of the older, saved content happens -- what reopening the
  // saved copy does.
  c.write('saved to the server',{revision:3});
  const rows=c.records().filter(r=>r.id==='doc-1');
  a.ok(rows.some(r=>r.dirty&&r.first==='typed after the save failed'),
    'the unsaved copy must still be there: '+JSON.stringify(rows));
});

test('a redundant buffer is still tidied away',()=>{
  const c=fixture({networked:true});
  c.write('same words',{dirty:true,revision:2});
  a.ok(c.keys().some(k=>k.includes(':writer:')));
  c.write('same words',{revision:2});
  a.ok(!c.keys().some(k=>k.includes(':writer:')),
    'a buffer holding nothing new is removed, as it always was');
});

test('both backups reach the shelf instead of hiding each other',()=>{
  const c=fixture();
  c.write('older',{revision:1});
  c.write('newer',{revision:2});
  const shown=c.browserManuscripts().filter(r=>r.id==='doc-1');
  a.equal(shown.length,2,'the de-duplicator must keep the pair apart');
});
