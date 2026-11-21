'use strict';
/**
 * Character-range formatting in format-core.js: the runs behind "bold this word".
 * Run: node --test tests/test_2i_inline_runs_node.js
 *
 * Every test here also checks that the author's text came back identical. That
 * is the point of the design: runs are offsets beside the text, never edits to it.
 */
const {test}=require('node:test');
const a=require('node:assert/strict');
const C=require('../2i/2i-assets/format-core.js');

const doc=(...lines)=>({state:C.fresh(),lines});

test('bold on a word stores one run and leaves the text alone',()=>{
  const {state,lines}=doc('The quick brown fox');
  C.applyInline(state,lines,0,4,9,{bold:true});
  a.deepEqual(lines,['The quick brown fox'],'text must be untouched');
  a.deepEqual(C.inlineRuns(state,lines,0),[{start:4,end:9,bold:true}]);
  a.ok(C.exportHtml('T',lines,state).includes('<span style="font-weight:bold">quick</span>'));
});

test('a selection with no text, a backwards range or an unknown mark is refused',()=>{
  const {state,lines}=doc('Hello');
  a.throws(()=>C.applyInline(state,lines,0,2,2,{bold:true}),/Select some text/);
  a.throws(()=>C.applyInline(state,lines,0,4,2,{bold:true}),/Select some text/);
  a.throws(()=>C.applyInline(state,lines,0,0,5,{bold:true,wobble:true}),/Unknown character formatting/);
  a.throws(()=>C.applyInline(state,lines,0,0,99,{bold:true}),/Select some text/);
  a.throws(()=>C.applyInline(state,lines,7,0,1,{bold:true}),/committed paragraph/);
  a.deepEqual(C.inlineRuns(state,lines,0),[],'a refused request stores nothing');
});

test('a locked paragraph refuses character formatting, like paragraph formatting',()=>{
  const {state,lines}=doc('Locked line');
  a.throws(()=>C.applyInline(state,lines,0,0,6,{bold:true},[0]),/Unlock/);
  a.throws(()=>C.clearInline(state,lines,0,0,6,[0]),/Unlock/);
});

test('overlapping applies split cleanly and keep each mark where it belongs',()=>{
  const {state,lines}=doc('abcdefghij');
  C.applyInline(state,lines,0,0,6,{bold:true});
  C.applyInline(state,lines,0,3,9,{italic:true});
  a.deepEqual(C.inlineRuns(state,lines,0),[
    {start:0,end:3,bold:true},
    {start:3,end:6,bold:true,italic:true},
    {start:6,end:9,italic:true}
  ]);
  a.deepEqual(lines,['abcdefghij']);
});

test('adjacent runs carrying the same marks are merged into one',()=>{
  const {state,lines}=doc('abcdef');
  C.applyInline(state,lines,0,0,3,{bold:true});
  C.applyInline(state,lines,0,3,6,{bold:true});
  a.deepEqual(C.inlineRuns(state,lines,0),[{start:0,end:6,bold:true}]);
});

test('clearing removes marks from a range, or from the whole paragraph',()=>{
  const {state,lines}=doc('abcdefghij');
  C.applyInline(state,lines,0,0,10,{bold:true});
  C.clearInline(state,lines,0,3,6);
  a.deepEqual(C.inlineRuns(state,lines,0),[{start:0,end:3,bold:true},{start:6,end:10,bold:true}]);
  C.clearInline(state,lines,0);
  a.deepEqual(C.inlineRuns(state,lines,0),[]);
  a.deepEqual(lines,['abcdefghij']);
});

test('false, "default" and 0 remove a property rather than storing a falsy one',()=>{
  const {state,lines}=doc('abcdef');
  C.applyInline(state,lines,0,0,6,{bold:true,italic:true,font:'Georgia',size:18,color:'#8b0000'});
  C.applyInline(state,lines,0,0,6,{italic:false,font:'default',size:0});
  a.deepEqual(C.inlineRuns(state,lines,0),[{start:0,end:6,bold:true,color:'#8b0000'}]);
});

test('superscript and subscript cannot both hold, and clear each other',()=>{
  const {state,lines}=doc('x2');
  C.applyInline(state,lines,0,1,2,{sup:true});
  C.applyInline(state,lines,0,1,2,{sub:true});
  a.deepEqual(C.inlineRuns(state,lines,0),[{start:1,end:2,sub:true}]);
  a.throws(()=>C.applyInline(state,lines,0,0,1,{sup:true,sub:true}),/superscript and subscript/);
  a.ok(C.exportHtml('T',lines,state).includes('<sub'));
});

test('a font, colour or size that is not offered is refused, so no CSS can be smuggled in',()=>{
  const {state,lines}=doc('text');
  a.throws(()=>C.applyInline(state,lines,0,0,4,{font:'x;behavior:url(evil)'}),/not one of/);
  a.throws(()=>C.applyInline(state,lines,0,0,4,{color:'red;position:fixed'}),/#rrggbb/);
  a.throws(()=>C.applyInline(state,lines,0,0,4,{highlight:'url(x)'}),/#rrggbb/);
  a.throws(()=>C.applyInline(state,lines,0,0,4,{size:400}),/between 6 and 96/);
  a.deepEqual(C.inlineRuns(state,lines,0),[]);
});

test('formatted text is still escaped on export',()=>{
  const {state,lines}=doc('<img onerror=x> & "quoted"');
  C.applyInline(state,lines,0,0,15,{bold:true});
  const html=C.exportHtml('<script>',lines,state);
  a.ok(html.includes('&lt;img'),'markup is escaped inside a run');
  a.ok(!html.includes('<img'));
  a.ok(!html.includes('<script>'));
  a.ok(html.includes('&amp;'));
});

test('an unformatted document exports exactly as it did before runs existed',()=>{
  const {state,lines}=doc('One','Two');
  const plain=C.exportHtml('T',lines,state);
  C.applyInline(state,lines,0,0,3,{bold:true});
  C.clearInline(state,lines,0);
  a.equal(C.exportHtml('T',lines,state),plain);
});

// -------------------------------------------------------------- text edits
test('typing inside a bold phrase keeps it bold',()=>{
  const runs=[{start:4,end:9,bold:true}];
  a.deepEqual(C.remapRuns(runs,'The quick fox','The quiiick fox'),[{start:4,end:11,bold:true}]);
});

test('typing before a run shifts it; typing after it does not move it',()=>{
  const runs=[{start:4,end:9,bold:true}];
  a.deepEqual(C.remapRuns(runs,'The quick fox','Oh. The quick fox'),[{start:8,end:13,bold:true}]);
  a.deepEqual(C.remapRuns(runs,'The quick fox','The quick fox indeed'),[{start:4,end:9,bold:true}]);
});

test('deleting part of a run keeps the surviving part formatted',()=>{
  const runs=[{start:0,end:10,bold:true}];
  a.deepEqual(C.remapRuns(runs,'abcdefghij tail','abcde tail'),[{start:0,end:5,bold:true}]);
});

test('deleting a run entirely leaves no run behind',()=>{
  const runs=[{start:4,end:9,bold:true}];
  a.deepEqual(C.remapRuns(runs,'The quick fox','The  fox'),[]);
});

test('text typed past the end of a run is not swept into it',()=>{
  const runs=[{start:0,end:4,bold:true}];
  a.deepEqual(C.remapRuns(runs,'Bold plain','Bold plain and more'),[{start:0,end:4,bold:true}]);
});

// ------------------------------------------------- paragraph-structure edits
test('a paragraph inserted above moves the run down with its paragraph',()=>{
  const {state}=doc('a','b');
  const lines=['a','b'];
  C.applyInline(state,lines,1,0,1,{bold:true});
  C.reconcile(state,lines,['new','a','b']);
  a.deepEqual(state.inline,[{index:2,text:'b',runs:[{start:0,end:1,bold:true}]}]);
});

test('retyping a paragraph remaps its runs instead of dropping them',()=>{
  const state=C.fresh(),lines=['The quick fox'];
  C.applyInline(state,lines,0,4,9,{bold:true});
  C.reconcile(state,lines,['The quick red fox']);
  a.deepEqual(state.inline,[{index:0,text:'The quick red fox',runs:[{start:4,end:9,bold:true}]}]);
});

test('an edit that changes paragraph structure detaches the run and says so',()=>{
  const state=C.fresh(),lines=['one','two'];
  C.applyInline(state,lines,1,0,3,{bold:true});
  C.reconcile(state,lines,['one','tw','o']);
  a.equal(state.inline.length,0);
  a.equal(state.inlineUnmapped.length,1);
  a.equal(state.inlineUnmapped[0].text,'two');
  a.match(state.inlineUnmapped[0].reason,/paragraph structure/);
});

// ------------------------------------------------------------- save / reopen
test('runs survive a save and reopen, and a stale anchor is detached not guessed',()=>{
  const state=C.fresh(),lines=['The quick fox','second'];
  C.applyInline(state,lines,0,4,9,{bold:true,color:'#8b0000'});
  const saved=JSON.parse(JSON.stringify(state));
  const back=C.restore(saved,lines);
  a.deepEqual(back.inline,state.inline);
  const moved=C.restore(saved,['something else entirely','second']);
  a.equal(moved.inline.length,0);
  a.equal(moved.inlineUnmapped.length,1);
  a.match(moved.inlineUnmapped[0].reason,/no longer matches/);
});

test('a document saved before runs existed still opens',()=>{
  const old={version:1,profile:'manuscript',page:{size:'letter',orientation:'portrait',margin:1},rows:[],unmapped:[]};
  const back=C.restore(old,['text']);
  a.deepEqual(back.inline,[]);
  a.deepEqual(back.inlineUnmapped,[]);
});

test('a corrupted run collection is refused rather than half-loaded',()=>{
  const base=()=>({version:1,profile:'manuscript',page:{size:'letter',orientation:'portrait',margin:1},rows:[],unmapped:[]});
  for(const inline of [
    [{index:0,text:'text',runs:[{start:0,end:99,bold:true}]}],
    [{index:0,text:'text',runs:[{start:2,end:1,bold:true}]}],
    [{index:0,text:'text',runs:[{start:0,end:2,bold:'yes'}]}],
    [{index:0,text:'text',runs:[{start:0,end:2,sup:true,sub:true}]}],
    [{index:0,text:'text',runs:[{start:0,end:2}]},{index:0,text:'text',runs:[]}],
    [{index:-1,text:'text',runs:[]}],
    'not an array'
  ]) a.throws(()=>C.restore({...base(),inline},['text']),undefined,'accepted bad runs: '+JSON.stringify(inline));
});

// ------------------------------------------------------------ toolbar state
test('the toolbar reports a mark only when it covers the whole selection',()=>{
  const state=C.fresh(),lines=['abcdefghij'];
  C.applyInline(state,lines,0,0,5,{bold:true});
  a.deepEqual(C.inlineStateAt(state,lines,0,0,5),{bold:true});
  a.deepEqual(C.inlineStateAt(state,lines,0,0,8),{},'half-bold reports nothing, so Bold bolds it all');
  a.deepEqual(C.inlineStateAt(state,lines,0,6,9),{});
});

test('a caret reports the formatting to its left, so typing continues it',()=>{
  const state=C.fresh(),lines=['abcdef'];
  C.applyInline(state,lines,0,0,3,{italic:true});
  a.deepEqual(C.inlineStateAt(state,lines,0,2,2),{italic:true});
  a.deepEqual(C.inlineStateAt(state,lines,0,3,3),{italic:true},'at the trailing edge, inherit from the left');
  a.deepEqual(C.inlineStateAt(state,lines,0,5,5),{});
  a.deepEqual(C.inlineStateAt(state,lines,0,0,0),{});
});

test('runs are ignored when the paragraph they were anchored to has changed',()=>{
  const state=C.fresh(),lines=['original'];
  C.applyInline(state,lines,0,0,8,{bold:true});
  a.deepEqual(C.inlineRuns(state,['edited'],0),[]);
});

test('too many separate runs in one paragraph is refused with the text intact',()=>{
  const text='x'.repeat(1200),lines=[text],state=C.fresh();
  a.throws(()=>{
    for(let i=0;i<1200;i+=2)C.applyInline(state,lines,0,i,i+1,{bold:true});
  },/more separate formatting changes/);
  a.deepEqual(lines,[text]);
});
