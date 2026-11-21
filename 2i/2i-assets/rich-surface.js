/* 2i's live writing surface: the manuscript page with its formatting showing.
 *
 * WHY THIS EXISTS
 * 2i wrote into a <textarea>, so formatting could only ever be applied to a
 * whole paragraph and could only be seen in preview or export. The paragraph
 * dialog said so itself: "Whole-paragraph styling only. For character-range
 * formatting, use the future rich-document editor integration." This is that,
 * and it is what lets a single word be bold while you are looking at it.
 *
 * WHAT IT DOES NOT DO
 * It does not replace the manuscript. `committed` -- the array of paragraph
 * strings -- stays the one source of truth, exactly as the textarea left it, so
 * locks, annotations, chapters, find and replace, revision compare, autosave,
 * recovery, .2i save and every existing test keep working untouched. This file
 * adds a second way to look at and edit the same array, and character runs in
 * manuscriptFormat.inline beside it. Turn it off and the textarea is still
 * there with the same words in it.
 *
 * CARET SAFETY
 * Typing never re-renders. The input handler reads the DOM into the model and
 * stops; rebuilding the page under a writer's cursor is how editors lose a
 * caret mid-sentence. The page is rebuilt only when the model changes from
 * somewhere else -- opening a document, undo, find and replace, a formatting
 * command -- and then the caret is put back by paragraph and character offset.
 */
(function installRichSurface(){
  'use strict';
  // File-tray documents are owned by ForesightFiles and have no native format
  // state, which is the same condition the format menu checks.
  if(typeof nativeFormatting==='undefined'||!nativeFormatting)return;
  const C=typeof TwoiFormatCore!=='undefined'?TwoiFormatCore:null;
  if(!C||typeof C.applyInline!=='function')return;
  const editorHost=$('soloEditor'),zone=$('manuscriptZone');
  if(!editorHost||!zone||typeof soloTextarea==='undefined'||!soloTextarea)return;

  const el=(tag,text,parent)=>{const n=document.createElement(tag);if(text!=null)n.textContent=text;if(parent)parent.append(n);return n;};
  const notice=message=>{try{addChat('notice',message);}catch{/* no chat log in a bare host */}};

  // ---------------------------------------------------------------- surface
  const surface=el('div',null,null);
  surface.id='twoiRichSurface';
  surface.className='twoi-rich-surface';
  surface.contentEditable='true';
  surface.spellcheck=true;
  surface.setAttribute('role','textbox');
  surface.setAttribute('aria-multiline','true');
  surface.setAttribute('aria-label','Manuscript, with formatting shown');
  editorHost.append(surface);

  let active=false, writing=false;

  const lockedSet=()=>typeof lockedLines!=='undefined'&&lockedLines?lockedLines:new Set();
  const paragraphs=()=>[...surface.children].filter(n=>n.tagName==='P');

  // ------------------------------------------------------ model -> the page
  function paragraphNode(index,text,runs,locked){
    const p=el('p',null,null);
    p.dataset.index=String(index);
    if(locked){p.dataset.locked='true';p.contentEditable='false';p.title='This paragraph is locked. Unlock it to edit.';}
    if(!text){el('br',null,p);return p;}
    if(!runs||!runs.length){p.append(document.createTextNode(text));return p;}
    let pos=0;
    for(const r of runs.slice().sort((a,b)=>a.start-b.start)){
      if(r.start>pos)p.append(document.createTextNode(text.slice(pos,r.start)));
      const tag=r.sup?'sup':r.sub?'sub':'span',node=el(tag,text.slice(r.start,r.end),p);
      const css=C.runCss(r);
      if(css)node.setAttribute('style',css);
      // The marks are kept on the element as data, so reading the page back does
      // not have to parse CSS text to learn what the author asked for.
      node.dataset.marks=JSON.stringify(C.marksOf(r));
      pos=r.end;
    }
    if(pos<text.length)p.append(document.createTextNode(text.slice(pos)));
    return p;
  }
  function renderSurface(){
    const state=syncManuscriptFormat(),locks=lockedSet();
    const next=document.createDocumentFragment();
    const lines=committed.length?committed:[''];
    lines.forEach((text,i)=>next.append(paragraphNode(i,text,C.inlineRuns(state,committed,i),locks.has(i))));
    surface.replaceChildren(next);
  }
  function renderParagraph(index){
    const p=paragraphs().find(n=>Number(n.dataset.index)===index);
    if(!p)return;
    p.replaceWith(paragraphNode(index,committed[index]??'',C.inlineRuns(syncManuscriptFormat(),committed,index),lockedSet().has(index)));
  }

  // ------------------------------------------------------ the page -> model
  // Marks are read from data-marks where this file wrote it, and otherwise
  // inferred from the tags a browser produces on its own (typing inside a bold
  // span, or an input method that wraps text in <b>). Anything unrecognised
  // contributes its text and no formatting, which loses a mark but never a word.
  const TAG_MARKS={B:{bold:true},STRONG:{bold:true},I:{italic:true},EM:{italic:true},
    U:{underline:true},INS:{underline:true},S:{strike:true},STRIKE:{strike:true},DEL:{strike:true},
    SUP:{sup:true},SUB:{sub:true}};
  function marksForElement(node){
    let marks={};
    if(node.dataset&&node.dataset.marks){
      try{const parsed=JSON.parse(node.dataset.marks);if(parsed&&typeof parsed==='object')marks={...parsed};}catch{/* fall through to the tag */}
    }
    const byTag=TAG_MARKS[node.tagName];
    if(byTag)marks={...marks,...byTag};
    const style=node.style;
    if(style){
      if(style.fontWeight==='bold'||Number(style.fontWeight)>=600)marks.bold=true;
      if(style.fontStyle==='italic')marks.italic=true;
      if(style.textDecorationLine&&style.textDecorationLine.includes('underline'))marks.underline=true;
      if(style.textDecorationLine&&style.textDecorationLine.includes('line-through'))marks.strike=true;
    }
    return marks;
  }
  function readParagraph(p){
    let text='';
    const runs=[];
    const walk=(node,inherited)=>{
      for(const child of node.childNodes){
        if(child.nodeType===Node.TEXT_NODE){
          const value=child.nodeValue||'';
          if(!value)continue;
          if(Object.keys(inherited).length)runs.push({start:text.length,end:text.length+value.length,...inherited});
          text+=value;
          continue;
        }
        if(child.nodeType!==Node.ELEMENT_NODE)continue;
        if(child.tagName==='BR'){
          // A <br> inside a paragraph is the browser's empty-line filler. Only a
          // real one in the middle of text means a line the writer asked for.
          if(text&&child.nextSibling)text+='\n';
          continue;
        }
        walk(child,{...inherited,...marksForElement(child)});
      }
    };
    walk(p,{});
    return {text,runs};
  }
  function readSurface(){
    const rows=paragraphs().map(readParagraph);
    if(!rows.length)rows.push({text:'',runs:[]});
    // A browser may put a newline inside one paragraph element; it becomes two
    // manuscript paragraphs, as pressing Enter in the textarea always did.
    const lines=[],runsByLine=[];
    for(const row of rows){
      const parts=row.text.split('\n');
      let base=0;
      parts.forEach((part,i)=>{
        const from=base,to=base+part.length;
        runsByLine.push(row.runs.filter(r=>r.end>from&&r.start<to).map(r=>({...r,start:Math.max(0,r.start-from),end:Math.min(part.length,r.end-from)})));
        lines.push(part);
        base=to+1;
      });
    }
    return {lines,runsByLine};
  }
  // Put the runs just read back into the document's format state, keeping every
  // other part of that state exactly as it was.
  function storeRuns(lines,runsByLine){
    const state=manuscriptFormat;
    const rows=[];
    runsByLine.forEach((runs,index)=>{
      if(!runs||!runs.length)return;
      let normalized;
      try{normalized=C.normalizeRuns(runs,lines[index].length);}
      catch(error){notice(error.message);return;}
      if(normalized.length)rows.push({index,text:lines[index],runs:normalized});
    });
    state.inline=rows;
  }

  // ------------------------------------------------------------- the mirror
  // The textarea stays loaded with the same words while it is hidden.
  //
  // This is deliberate and it is what keeps the rest of 2i working unchanged.
  // Word count, find and replace, read-aloud, the chapter navigator, the
  // paragraph dialog and the exports all read soloTextarea.value or its
  // selection directly, and they are correct code -- there is no reason to
  // rewrite a dozen working callers to teach them about a second surface.
  // Keeping the hidden textarea in step is one assignment and makes every one
  // of them right for free. It is never read back while the surface is active:
  // the model is the authority, and this only ever copies out of it.
  function mirror(){
    const text=committed.join('\n');
    if(soloTextarea.value!==text)soloTextarea.value=text;
  }
  function paragraphStart(index){
    let at=0;
    for(let i=0;i<index&&i<committed.length;i++)at+=(committed[i]||'').length+1;
    return at;
  }
  function mirrorCaret(){
    const range=selectionRange();
    if(!range)return;
    try{soloTextarea.setSelectionRange(paragraphStart(range.first)+range.start,paragraphStart(range.last)+range.end);}
    catch{/* an out-of-range mirror is not worth an error */}
  }

  // ------------------------------------------------------------- selection
  function paragraphOf(node){
    let at=node;
    while(at&&at!==surface){if(at.tagName==='P'&&at.dataset.index!==undefined)return at;at=at.parentNode;}
    return null;
  }
  function offsetWithin(p,node,offset){
    if(node===p){
      // The caret is between children; count everything before that child.
      let total=0;
      for(let i=0;i<offset&&i<p.childNodes.length;i++)total+=(p.childNodes[i].textContent||'').length;
      return total;
    }
    let total=0,found=false;
    const walk=n=>{
      if(found)return;
      if(n===node){total+=offset;found=true;return;}
      if(n.nodeType===Node.TEXT_NODE){total+=(n.nodeValue||'').length;return;}
      for(const child of n.childNodes){walk(child);if(found)return;}
    };
    walk(p);
    return total;
  }
  // The current selection as the model sees it: which paragraphs, and where in
  // the first and last of them.
  function selectionRange(){
    const sel=document.getSelection();
    if(!sel||!sel.rangeCount)return null;
    const range=sel.getRangeAt(0);
    if(!surface.contains(range.startContainer)||!surface.contains(range.endContainer))return null;
    const startP=paragraphOf(range.startContainer),endP=paragraphOf(range.endContainer);
    if(!startP||!endP)return null;
    const first=Number(startP.dataset.index),last=Number(endP.dataset.index);
    const start=offsetWithin(startP,range.startContainer,range.startOffset);
    const end=offsetWithin(endP,range.endContainer,range.endOffset);
    return first<=last?{first,last,start,end}:{first:last,last:first,start:end,end:start};
  }
  function placeCaret(index,start,end=start){
    const p=paragraphs().find(n=>Number(n.dataset.index)===index);
    if(!p)return;
    const locate=target=>{
      let remaining=target,node=null,offset=0,done=false;
      const walk=n=>{
        if(done)return;
        if(n.nodeType===Node.TEXT_NODE){
          const length=(n.nodeValue||'').length;
          if(remaining<=length){node=n;offset=remaining;done=true;return;}
          remaining-=length;return;
        }
        for(const child of n.childNodes){walk(child);if(done)return;}
      };
      walk(p);
      return node?{node,offset}:{node:p,offset:0};
    };
    const from=locate(start),to=start===end?from:locate(end);
    const range=document.createRange();
    range.setStart(from.node,from.offset);
    range.setEnd(to.node,to.offset);
    const sel=document.getSelection();
    sel.removeAllRanges();sel.addRange(range);
  }

  // ---------------------------------------------------------------- editing
  function busy(){
    return (typeof initializing!=='undefined'&&initializing)||
           (typeof generating!=='undefined'&&generating)||
           (typeof chatSending!=='undefined'&&chatSending)||
           (typeof editingIdx!=='undefined'&&editingIdx!==null);
  }
  // Typing. Reads the page into the model and stops -- no re-render, so the
  // caret stays exactly where the writer left it.
  surface.addEventListener('input',event=>{
    if(!active)return;
    writing=true;
    const before=committed.join('\n');
    const {lines,runsByLine}=readSurface();
    if(window.twoiNarrativeHistory){
      try{
        const target=lines.join('\n');
        const mapped=NarrativeCore.remapProtected(committed,lines,lockedSet());
        if(typeof keepChapterPositions==='function'&&before!==target)keepChapterPositions(before,target);
        lockedLines=new Set(mapped);
      }catch(error){
        // A locked paragraph was about to change. Put the page back as the model
        // has it; the words in the model are the ones that were protected.
        notice(error.message);renderSurface();writing=false;return;
      }
    }
    const previous=committed.slice();
    committed=lines;
    C.reconcile(manuscriptFormat,previous,committed);
    storeRuns(lines,runsByLine);
    if(typeof formatPrevious!=='undefined')formatPrevious=committed.slice();
    window.twoiCreativeSession?.observeEdit({surface:'committed',before,after:lines.join('\n'),
      inputType:typeof creativeInputType==='function'?creativeInputType(event):'insertText'});
    mirror();
    markDirty();
    if(typeof countWordsSoon==='function')countWordsSoon();
    writing=false;
  });

  // Pasting. Only the text is taken, deliberately: accepting arbitrary markup
  // from the clipboard would put styling in the document that 2i cannot
  // validate, and in the worst case markup the author never saw. Paste, then
  // format -- the words arrive intact, which is the part that matters.
  surface.addEventListener('paste',event=>{
    if(!active)return;
    const text=event.clipboardData?.getData('text/plain');
    if(text===undefined)return;
    event.preventDefault();
    document.execCommand('insertText',false,text);
  });

  // ------------------------------------------------------------- commands
  function applyMarks(marks){
    if(!active)return;
    if(busy()){notice('Finish the active request or edit before changing formatting.');return;}
    const range=selectionRange();
    if(!range){notice('Select some text in the manuscript first.');return;}
    const locks=[...lockedSet()];
    const state=syncManuscriptFormat();
    const targets=[];
    for(let index=range.first;index<=range.last;index++){
      const text=committed[index]??'';
      const from=index===range.first?range.start:0;
      const to=index===range.last?range.end:text.length;
      if(to>from)targets.push({index,from,to});
    }
    if(!targets.length){notice('Select some text in the manuscript first.');return;}
    if(targets.some(t=>locks.includes(t.index))){notice('Unlock the protected paragraphs before changing their formatting.');return;}
    // Decide set-or-clear once, from the whole selection, so pressing Bold on a
    // partly bold selection bolds all of it instead of clearing the bold part.
    const resolved={...marks};
    for(const key of Object.keys(marks)){
      if(marks[key]!=='toggle')continue;
      const everywhere=targets.every(t=>C.inlineStateAt(state,committed,t.index,t.from,t.to)[key]===true);
      resolved[key]=!everywhere;
    }
    const backup=C.clone(state);
    snapshot();
    try{
      for(const t of targets)C.applyInline(manuscriptFormat,committed,t.index,t.from,t.to,resolved,locks);
    }catch(error){
      // Leave the document exactly as it was, including the undo point.
      manuscriptFormat=backup;
      if(typeof undoStack!=='undefined')undoStack.pop();
      notice(error.message);
      return;
    }
    for(const t of targets)renderParagraph(t.index);
    placeCaret(range.first,range.start,range.first===range.last?range.end:range.start);
    if(range.first!==range.last)selectAcross(range);
    markDirty();
    if(typeof writeRecovery==='function')writeRecovery();
    refreshBar();
  }
  function selectAcross(range){
    const first=paragraphs().find(n=>Number(n.dataset.index)===range.first);
    const last=paragraphs().find(n=>Number(n.dataset.index)===range.last);
    if(!first||!last)return;
    try{
      const sel=document.getSelection(),r=document.createRange();
      r.selectNodeContents(first);r.setEnd(last,last.childNodes.length);
      sel.removeAllRanges();sel.addRange(r);
    }catch{/* a selection that cannot be restored is not worth an error */}
  }
  function clearMarks(){
    if(!active)return;
    const range=selectionRange();
    if(!range){notice('Select some text in the manuscript first.');return;}
    const locks=[...lockedSet()];
    if(locks.some(i=>i>=range.first&&i<=range.last)){notice('Unlock the protected paragraphs before clearing their formatting.');return;}
    snapshot();
    try{
      for(let index=range.first;index<=range.last;index++){
        const text=committed[index]??'';
        const from=index===range.first?range.start:0;
        const to=index===range.last?range.end:text.length;
        if(to>from)C.clearInline(manuscriptFormat,committed,index,from,to,locks);
      }
    }catch(error){notice(error.message);return;}
    for(let index=range.first;index<=range.last;index++)renderParagraph(index);
    placeCaret(range.first,range.start);
    markDirty();
    if(typeof writeRecovery==='function')writeRecovery();
    refreshBar();
  }
  function insertText(text){
    if(!active)return;
    surface.focus();
    document.execCommand('insertText',false,text);
  }

  // ------------------------------------------------------------- the bar
  const bar=el('div',null,null);
  bar.id='twoiFormatBar';
  bar.setAttribute('role','toolbar');
  bar.setAttribute('aria-label','Text formatting');
  const row=zone.querySelector('.zone-label-row');
  if(row)row.after(bar);else zone.prepend(bar);

  const marked=[];
  function group(optional){
    const g=el('div',null,bar);g.className='fb-group'+(optional?' fb-optional':'');
    return g;
  }
  function mark(host,label,title,key,className){
    const b=el('button',label,host);
    b.type='button';b.title=title;b.setAttribute('aria-label',title);
    b.setAttribute('aria-pressed','false');
    if(className)b.className=className;
    b.addEventListener('pointerdown',e=>e.preventDefault()); // keep the selection
    b.onclick=()=>applyMarks({[key]:'toggle'});
    marked.push([b,key]);
    return b;
  }
  const basics=group(false);
  mark(basics,'B','Bold (Ctrl+B)','bold','fb-b');
  mark(basics,'I','Italic (Ctrl+I)','italic','fb-i');
  mark(basics,'U','Underline (Ctrl+U)','underline','fb-u');
  mark(basics,'S','Strikethrough','strike','fb-s');
  const scripts=group(true);
  mark(scripts,'x²','Superscript','sup');
  mark(scripts,'x₂','Subscript','sub');
  el('div',null,bar).className='fb-sep';

  const typeGroup=group(true);
  const fontSelect=el('select',null,typeGroup);
  fontSelect.setAttribute('aria-label','Font');fontSelect.title='Font';
  for(const font of C.inlineFonts){
    const option=el('option',font==='default'?'Document font':font,fontSelect);
    option.value=font;
    if(font!=='default'&&!['serif','sans','mono'].includes(font))option.style.fontFamily="'"+font+"'";
  }
  fontSelect.addEventListener('pointerdown',()=>{pendingRange=selectionRange();});
  fontSelect.onchange=()=>{restoreRange();applyMarks({font:fontSelect.value});};
  const sizeSelect=el('select',null,typeGroup);
  sizeSelect.setAttribute('aria-label','Point size');sizeSelect.title='Point size';
  el('option','Size',sizeSelect).value='0';
  for(const size of [8,9,10,11,12,14,16,18,20,22,24,28,32,36,48,72])el('option',String(size),sizeSelect).value=String(size);
  sizeSelect.addEventListener('pointerdown',()=>{pendingRange=selectionRange();});
  sizeSelect.onchange=()=>{restoreRange();applyMarks({size:Number(sizeSelect.value)});};

  // A <select> or a colour picker takes the focus, and with it the selection.
  // The range is remembered when the control is pressed and put back before the
  // command runs, so formatting still lands on the text that was selected.
  let pendingRange=null;
  function restoreRange(){
    if(!pendingRange)return;
    const {first,last,start,end}=pendingRange;
    surface.focus();
    if(first===last)placeCaret(first,start,end);else selectAcross(pendingRange);
    pendingRange=null;
  }

  const colourGroup=group(true);
  const textColour=el('input',null,colourGroup);
  textColour.type='color';textColour.value='#241c12';
  textColour.title='Text colour';textColour.setAttribute('aria-label','Text colour');
  textColour.addEventListener('pointerdown',()=>{pendingRange=selectionRange();});
  textColour.addEventListener('change',()=>{restoreRange();applyMarks({color:textColour.value});});
  const highlight=el('input',null,colourGroup);
  highlight.type='color';highlight.value='#fff3a3';
  highlight.title='Highlight colour';highlight.setAttribute('aria-label','Highlight colour');
  highlight.addEventListener('pointerdown',()=>{pendingRange=selectionRange();});
  highlight.addEventListener('change',()=>{restoreRange();applyMarks({highlight:highlight.value});});
  const noColour=el('button','A̶',colourGroup);
  noColour.type='button';noColour.title='Remove colour and highlight';noColour.setAttribute('aria-label','Remove colour and highlight');
  noColour.addEventListener('pointerdown',e=>e.preventDefault());
  noColour.onclick=()=>applyMarks({color:false,highlight:false});
  el('div',null,bar).className='fb-sep';

  const tools=group(false);
  const clearButton=el('button','Clear',tools);
  clearButton.type='button';clearButton.title='Remove all formatting from the selection';clearButton.setAttribute('aria-label','Remove all formatting from the selection');
  clearButton.addEventListener('pointerdown',e=>e.preventDefault());
  clearButton.onclick=clearMarks;
  const dateButton=el('button','Date',tools);
  dateButton.type='button';dateButton.title='Insert today’s date and the time';dateButton.setAttribute('aria-label','Insert the date and time');
  dateButton.addEventListener('pointerdown',e=>e.preventDefault());
  dateButton.onclick=()=>insertText(new Date().toLocaleString());

  function refreshBar(){
    if(!active)return;
    const range=selectionRange();
    const state=range?C.inlineStateAt(syncManuscriptFormat(),committed,range.first,
      range.first===range.last?range.start:range.start,
      range.first===range.last?range.end:(committed[range.first]??'').length):{};
    for(const [button,key] of marked)button.setAttribute('aria-pressed',state[key]===true?'true':'false');
    fontSelect.value=C.inlineFonts.includes(state.font)?state.font:'default';
    sizeSelect.value=state.size?String(state.size):'0';
    if(state.color)textColour.value=state.color;
    if(state.highlight)highlight.value=state.highlight;
  }
  document.addEventListener('selectionchange',()=>{
    if(!active)return;
    const sel=document.getSelection();
    if(!sel||!sel.rangeCount||!surface.contains(sel.getRangeAt(0).startContainer))return;
    refreshBar();
    mirrorCaret();
  });

  // ------------------------------------------------------------- shortcuts
  surface.addEventListener('keydown',event=>{
    if(!active||event.isComposing)return;
    if(!(event.ctrlKey||event.metaKey)||event.altKey)return;
    const key=String(event.key||'').toLowerCase();
    const marks={b:'bold',i:'italic',u:'underline'}[key];
    if(!marks||event.shiftKey)return;
    event.preventDefault();event.stopPropagation();
    applyMarks({[marks]:'toggle'});
  });

  // --------------------------------------------------------------- toggle
  const toggle=el('button','Formatting',null);
  toggle.id='twoiRichToggle';toggle.type='button';toggle.className='zoom-btn';
  toggle.title='Show bold, italic and colour while you write';
  toggle.setAttribute('aria-pressed','false');
  if(row)row.append(toggle);else bar.prepend(toggle);

  function setActive(on){
    const next=!!on&&!coWriting;
    if(next===active)return active;
    if(next){
      renderSurface();
      mirror();
      document.body.dataset.twoiRich='on';
      active=true;
      refreshBar();
    }else{
      active=false;
      delete document.body.dataset.twoiRich;
      // Hand the words back to the textarea exactly as the model holds them.
      soloTextarea.value=committed.join('\n');
      if(typeof updateLineNumbers==='function')updateLineNumbers();
    }
    toggle.setAttribute('aria-pressed',String(active));
    return active;
  }
  toggle.onclick=()=>{
    if(coWriting){notice('The formatting surface is for Write mode. Collab writes into the draft page.');return;}
    setActive(!active);
    if(active)surface.focus();else soloTextarea.focus();
  };

  // Collab owns the two-page spread and its own line editor, so the surface
  // steps aside for it and comes back when Write mode does.
  let wasActive=false;
  document.addEventListener('twoi:mode-change',()=>{
    if(coWriting){wasActive=active;setActive(false);}
    else if(wasActive)setActive(true);
  });

  // The page is rebuilt when the model changed somewhere else -- opening a
  // document, undo, redo, find and replace. It is NOT rebuilt while the writer
  // is typing into it, and not when the page already matches the model.
  function refreshFromModel(){
    if(!active||writing)return;
    const {lines}=readSurface();
    const same=lines.length===committed.length&&lines.every((text,i)=>text===committed[i]);
    const focused=surface.contains(document.activeElement)||
      (document.getSelection()?.rangeCount&&surface.contains(document.getSelection().getRangeAt(0).startContainer));
    if(same&&focused)return;
    renderSurface();
  }
  if(typeof render==='function'){
    const previousRender=render;
    render=function(){previousRender.apply(this,arguments);refreshFromModel();};
  }

  // Exposed so the menus and the rest of 2i can reach it without reading
  // anything private: window.twoiRichSurface.active() etc.
  window.twoiRichSurface={
    active:()=>active,
    set:setActive,
    apply:applyMarks,
    clear:clearMarks,
    insert:insertText,
    refresh:renderSurface,
    selection:selectionRange,
    node:surface
  };
})();
