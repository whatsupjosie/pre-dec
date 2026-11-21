'use strict';
/**
 * RTF export: WordPad's own format, so a formatted 2i manuscript can be handed
 * to WordPad, Word, Pages or LibreOffice and arrive formatted.
 * Run: node --test tests/test_2i_rtf_export_node.js
 */
const {test}=require('node:test');
const a=require('node:assert/strict');
const C=require('../2i/2i-assets/format-core.js');

// Braces that are not escaped must balance, or the file will not open at all.
function balanced(rtf){
  let depth=0;
  for(let i=0;i<rtf.length;i++){
    if(rtf[i]==='\\'){i++;continue;}
    if(rtf[i]==='{')depth++;
    else if(rtf[i]==='}'){depth--;if(depth<0)return false;}
  }
  return depth===0;
}

test('a plain manuscript produces a document that opens',()=>{
  const state=C.fresh(),lines=['First line.','Second line.'];
  const rtf=C.exportRtf('Title',lines,state);
  a.ok(rtf.startsWith('{\\rtf1\\ansi'));
  a.ok(rtf.endsWith('}'));
  a.ok(balanced(rtf),'unescaped braces must balance');
  a.ok(rtf.includes('First line.'));
  a.ok(rtf.includes('\\par'));
});

test('character formatting is carried, not flattened',()=>{
  const state=C.fresh(),lines=['The quick brown fox'];
  C.applyInline(state,lines,0,4,9,{bold:true,italic:true,underline:true,strike:true});
  const rtf=C.exportRtf('T',lines,state);
  a.match(rtf,/\{\\b\\i\\ul\\strike quick\\b0\\i0\\ulnone\\strike0\}/);
  a.ok(balanced(rtf));
});

test('colour and highlight build a colour table and reference it',()=>{
  const state=C.fresh(),lines=['coloured'];
  C.applyInline(state,lines,0,0,8,{color:'#8b0000',highlight:'#ffff00'});
  const rtf=C.exportRtf('T',lines,state);
  a.ok(rtf.includes('\\red139\\green0\\blue0;'),'the text colour is in the table');
  a.ok(rtf.includes('\\red255\\green255\\blue0;'),'the highlight is in the table');
  a.match(rtf,/\\cf1/);
  a.match(rtf,/\\highlight2/);
});

test('point size and font reach the run',()=>{
  const state=C.fresh(),lines=['sized text'];
  C.applyInline(state,lines,0,0,5,{size:18,font:'Arial'});
  const rtf=C.exportRtf('T',lines,state);
  a.match(rtf,/\\fs36/,'RTF measures in half-points');
  a.ok(rtf.includes('Arial;'),'the font is declared in the font table');
});

test('superscript and subscript are closed properly',()=>{
  const state=C.fresh(),lines=['x2 and H2O'];
  C.applyInline(state,lines,0,1,2,{sup:true});
  C.applyInline(state,lines,0,8,9,{sub:true});
  const rtf=C.exportRtf('T',lines,state);
  a.match(rtf,/\\super 2\\nosupersub/);
  a.match(rtf,/\\sub 2\\nosupersub/);
});

test('a bulleted list gets a bullet and a hanging indent',()=>{
  const state=C.fresh(),lines=['Shopping','milk','eggs'];
  for(const i of [1,2])C.apply(state,lines,[i],{...C.defaultStyle('list'),list:'bullet'});
  const rtf=C.exportRtf('T',lines,state);
  a.equal((rtf.match(/\\u8226\?/g)||[]).length,2,'one bullet per list paragraph');
  a.match(rtf,/\\fi-360/);
});

test('a numbered list counts, and starts again after a paragraph that is not in it',()=>{
  const state=C.fresh(),lines=['one','two','break','three'];
  for(const i of [0,1,3])C.apply(state,lines,[i],{...C.defaultStyle('list'),list:'number'});
  const rtf=C.exportRtf('T',lines,state);
  const markers=[...rtf.matchAll(/ (\d)\.\\tab /g)].map(m=>m[1]);
  a.deepEqual(markers,['1','2','1']);
});

test('alignment and indent are written',()=>{
  const state=C.fresh(),lines=['centre','indented'];
  C.apply(state,lines,[0],{...C.defaultStyle('body'),align:'center'});
  C.apply(state,lines,[1],{...C.defaultStyle('body'),indent:0.5});
  const rtf=C.exportRtf('T',lines,state);
  a.match(rtf,/\\qc/);
  a.match(rtf,/\\li720/,'half an inch is 720 twips');
});

test('chapter headings are written above their paragraph',()=>{
  const state=C.fresh(),lines=['Opening words'];
  const rtf=C.exportRtf('T',lines,state,[{title:'Chapter One',subtitle:'In which it begins',startLine:0}]);
  a.ok(rtf.indexOf('Chapter One')<rtf.indexOf('Opening words'));
  a.ok(rtf.includes('In which it begins'));
});

test('the author’s characters survive exactly, including the ones RTF reserves',()=>{
  const state=C.fresh();
  const lines=['Braces {here} and a backslash \\ and a tab\tstop','A café — naïve — “quoted”','emoji \u{1F4D6} too'];
  const rtf=C.exportRtf('T',lines,state);
  a.ok(rtf.includes('Braces \\{here\\} and a backslash \\\\ and a tab\\tab stop'));
  a.ok(rtf.includes('\\u233?'),'e-acute');
  a.ok(rtf.includes('\\u8212?'),'em dash');
  a.ok(rtf.includes('\\u8220?'),'opening curly quote');
  // An astral character goes out as its surrogate pair.
  a.ok(rtf.includes('\\u-10179?')||rtf.includes('\\u55357?'),'surrogate pair for the emoji');
  a.ok(balanced(rtf));
});

test('an empty manuscript is still a valid document',()=>{
  const rtf=C.exportRtf('T',[],C.fresh());
  a.ok(rtf.startsWith('{\\rtf1'));
  a.ok(balanced(rtf));
});

test('a stale formatting anchor is ignored rather than applied to the wrong words',()=>{
  const state=C.fresh(),lines=['original text'];
  C.applyInline(state,lines,0,0,8,{bold:true});
  const rtf=C.exportRtf('T',['different text entirely'],state);
  a.ok(!rtf.includes('\\b '),'no bold is carried onto text it was not applied to');
  a.ok(rtf.includes('different text entirely'));
});

test('a bold paragraph does not make every paragraph after it bold',()=>{
  // RTF character state runs on until something turns it off, and \pard does not.
  // Found by opening an export in LibreOffice and seeing the whole page in bold.
  const state=C.fresh(),lines=['Bold heading','Plain body text','More plain text'];
  C.apply(state,lines,[0],{...C.defaultStyle('title'),bold:true,italic:true,underline:true});
  const rtf=C.exportRtf('T',lines,state);
  // Split on the paragraph mark itself, not on the \pard that starts the next one.
  const paragraphs=rtf.split(/\\par\n/).filter(x=>x.includes('Plain body text')||x.includes('More plain text'));
  a.equal(paragraphs.length,2);
  for(const part of paragraphs)a.ok(part.includes('\\pard\\plain'),'each paragraph resets character state');
});
