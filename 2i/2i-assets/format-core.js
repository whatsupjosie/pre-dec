/* Native manuscript format metadata; presentation is independent of text. */
function makeFormatCore(){
  const clone=x=>JSON.parse(JSON.stringify(x));
  const scripts=["scene","action","character","dialogue","parenthetical","transition","shot","act","cast","cue","sound","music","general"];
  const prose=["body","heading1","heading2","heading3","quote","list","title","subtitle","caption","general"];
  const pitch=["title","subtitle","logline","heading1","heading2","body","quote","list","summary","character_profile","episode","audience","general"];
  const profiles={
    manuscript:{label:"Novel / manuscript",group:"Prose",roles:prose,kind:"prose"},
    story:{label:"Short story",group:"Prose",roles:prose,kind:"prose"},
    general:{label:"General document",group:"Prose",roles:prose,kind:"prose"},
    cinema:{label:"Feature film screenplay",group:"Screen & stage",roles:scripts,kind:"script"},
    shortfilm:{label:"Short film screenplay",group:"Screen & stage",roles:scripts,kind:"script"},
    tv_drama:{label:"Television drama / single-camera",group:"Screen & stage",roles:scripts,kind:"script"},
    tv_comedy:{label:"Single-camera comedy",group:"Screen & stage",roles:scripts,kind:"script"},
    multicam:{label:"Multi-camera sitcom",group:"Screen & stage",roles:scripts,kind:"multi"},
    threecam:{label:"Three-camera studio sitcom",group:"Screen & stage",roles:scripts,kind:"multi"},
    sketch:{label:"Sketch / variety show",group:"Screen & stage",roles:scripts,kind:"multi"},
    stage:{label:"Stage play",group:"Screen & stage",roles:scripts,kind:"script"},
    documentary:{label:"Documentary / two-column audio-video",group:"Production",roles:["segment","visual","audio","voiceover","interview","sound","music","cue","general"],kind:"av"},
    broadcast:{label:"Live television / news / rundown",group:"Production",roles:["segment","visual","audio","voiceover","interview","sound","music","cue","general"],kind:"av"},
    commercial:{label:"Commercial / promotional video",group:"Production",roles:["segment","visual","audio","voiceover","sound","music","cue","general"],kind:"av"},
    podcast:{label:"Podcast / radio drama",group:"Production",roles:["segment","character","dialogue","voiceover","sound","music","cue","general"],kind:"script"},
    pitch:{label:"One-page pitch / one-sheet",group:"Development",roles:pitch,kind:"prose"},
    treatment:{label:"Film / TV treatment",group:"Development",roles:pitch,kind:"prose"},
    synopsis:{label:"Synopsis / summary",group:"Development",roles:pitch,kind:"prose"},
    bible:{label:"Series bible",group:"Development",roles:pitch,kind:"prose"},
    outline:{label:"Story outline / scene breakdown",group:"Development",roles:pitch,kind:"prose"}
  };
  const guidance={"manuscript":"Use chapter structure, narrative voice, point of view, paragraph rhythm and interiority.","story":"Maintain compression, a focused arc and a purposeful ending.","general":"Use descriptive headings and paragraphs appropriate for the audience.","cinema":"Scene headings establish location and time; use present-tense visible/audible action, character cues and dialogue. Avoid unnecessary camera direction in spec drafts.","shortfilm":"Use film script conventions and an economical arc; length depends on the project.","tv_drama":"Single-camera scene/action/dialogue. Teaser, act and tag conventions vary by network and distribution.","tv_comedy":"Film-like dialogue and action with attention to comic beats; do not force multicamera action formatting.","multicam":"Studio sitcom: acts, scene cast, stage action and dialogue. Many house styles capitalize action and double-space speech.","threecam":"Studio multicamera format with optional numbered camera and live production cues, following the show's house style.","sketch":"Separate sketches, entrances and performers; preserve visual and verbal punchlines and cue timing.","stage":"Stage directions, dialogue, cast and acts/scenes; theatre submission formats vary.","documentary":"Separate what viewers see from what they hear. Label interviews, narration, archive imagery and actual sound; never invent recorded quotations.","broadcast":"Separate video and audio cues, identify segments, timing and production cues; distinguish rundown from dramatic script.","commercial":"Separate image/action and sound/voice-over; identify duration, message, call to action and required disclaimers.","podcast":"Write for the ear: speaker labels, narration, sound and music cues; estimates are not recorded durations.","pitch":"Use title, logline, audience, concept, distinctive hook and story engine as appropriate; not a rigid deck.","treatment":"Write a readable prose account of narrative and emotional turns rather than a screenplay.","synopsis":"Summarize actual narrative, including key turns and ending when required; distinguish marketing copy.","bible":"Define premise, tone, world, cast and ongoing story engine; include episode examples and continuity.","outline":"Represent beats, scenes and dependencies without treating plans as confirmed facts."};
  for(const [id,p] of Object.entries(profiles))p.guidance=guidance[id];
  const names={body:"Body text",heading1:"Heading 1",heading2:"Heading 2",heading3:"Heading 3",quote:"Block quote",list:"List paragraph",title:"Title",subtitle:"Subtitle",caption:"Caption",general:"General",scene:"Scene heading",action:"Action",character:"Character cue",dialogue:"Dialogue",parenthetical:"Parenthetical",transition:"Transition",shot:"Shot",act:"Act / teaser",cast:"Scene cast",cue:"Production cue",sound:"Sound effect",music:"Music",segment:"Segment",visual:"Video / image",audio:"Audio",voiceover:"Voice-over",interview:"Interview",logline:"Logline",summary:"Summary",character_profile:"Character profile",episode:"Episode outline",audience:"Audience / positioning"};
  const allRoles=new Set(Object.keys(names)), fonts=["default","serif","sans","mono"], aligns=["default","left","center","right","justify"];
  const fresh=()=>({version:1,profile:"manuscript",page:{size:"letter",orientation:"portrait",margin:1},rows:[],unmapped:[],annotations:[],inline:[],inlineUnmapped:[]});
  // A bulleted or numbered paragraph. Optional, so a document saved before lists
  // existed still opens; absent means "none".
  const lists=["none","bullet","number"];
  function validStyle(s){
    if(!s||!allRoles.has(s.role)||!aligns.includes(s.align)||!fonts.includes(s.font)||!Number.isFinite(s.indent)||s.indent<0||s.indent>4||!Number.isFinite(s.size)||s.size<0||s.size>48||![0,1,1.15,1.5,2].includes(s.spacing)||["bold","italic","underline"].some(k=>typeof s[k]!=="boolean"))throw Error("Invalid paragraph format.");
    if(s.list!==undefined&&!lists.includes(s.list))throw Error("Invalid list style.");
    return clone(s);
  }
  const defaultStyle=role=>({role,align:"default",font:"default",indent:0,size:0,spacing:0,bold:false,italic:false,underline:false,list:"none"});
  const listKind=style=>style&&lists.includes(style.list)&&style.list!=="none"?style.list:null;
  // Paragraph-anchored private author annotations reuse the native document's
  // existing snapshot, recovery, revision and undo state. Never guess a new
  // anchor from text similarity. Detached notes retain the author's exact text.
  function validAnnotation(a){
    if(!a||typeof a.id!=="string"||!/^[a-zA-Z0-9_-]{1,100}$/.test(a.id)||!["bookmark","comment"].includes(a.kind)||!["open","resolved","archived"].includes(a.status)||a.kind==="bookmark"&&a.status==="resolved"||typeof a.label!=="string"||!a.label.trim()||a.label.length>160||typeof a.body!=="string"||a.body.length>8000||a.kind==="comment"&&!a.body.trim()||!Number.isInteger(a.index)||a.index<0||typeof a.text!=="string"||a.text.length>50000||typeof a.createdAt!=="string"||a.createdAt.length>80||a.detachedReason!==null&&typeof a.detachedReason!=="string"||!Array.isArray(a.priorAnchors)||a.priorAnchors.length>100)throw Error("Invalid document annotation; retain the original source.");
    for(const p of a.priorAnchors)if(!p||!Number.isInteger(p.index)||p.index<0||typeof p.text!=="string"||p.text.length>50000||p.reason!==null&&typeof p.reason!=="string")throw Error("Invalid prior annotation anchor.");
    if(a.statusBeforeArchive!==undefined&&!["open","resolved"].includes(a.statusBeforeArchive))throw Error("Invalid archived annotation state.");
    return a;
  }
  function restoreAnnotations(items,lines){
    if(items===undefined)return [];
    if(!Array.isArray(items)||items.length>500)throw Error("Invalid annotation collection.");
    const ids=new Set();
    return items.map(a=>{validAnnotation(a);if(ids.has(a.id))throw Error("Duplicate annotation identity.");ids.add(a.id);const b=clone(a);if(b.detachedReason===null&&lines[b.index]!==b.text)b.detachedReason="Saved anchor no longer matches committed text.";return b;});
  }
  function reconcileAnnotations(state,before,after,first,last){
    const items=state.annotations||[];if(!items.length)return;
    const end=before.length-last,delta=after.length-before.length;
    const beforeChanged=new Set(before.slice(first,end)),afterChanged=new Set(after.slice(first,after.length-last));
    const count=lines=>{const result=new Map();for(const s of lines)result.set(s,(result.get(s)||0)+1);return result;};
    const oldCount=count(before),newCount=count(after);
    for(const a of items){
      if(a.detachedReason!==null)continue;
      let index=null;
      if(before[a.index]===a.text){
        if(a.index<first)index=a.index;
        else if(a.index>=end)index=a.index+delta;
      }
      const ambiguous=(oldCount.get(a.text)>1||newCount.get(a.text)>1)&&(beforeChanged.has(a.text)||afterChanged.has(a.text)||oldCount.get(a.text)!==newCount.get(a.text));
      if(!ambiguous&&index!==null&&after[index]===a.text)a.index=index;
      else a.detachedReason=ambiguous?"Repeated paragraph became ambiguous; choose its location explicitly.":"Anchored paragraph was edited or removed; annotation retained.";
    }
  }
  function addAnnotation(state,lines,data){
    const items=state.annotations||(state.annotations=[]);
    if(items.length>=500)throw Error("Annotation limit reached; retain this document and export a copy before adding more.");
    if(!Number.isInteger(data.index)||data.index<0||data.index>=lines.length)throw Error("Select a committed paragraph.");
    const item={id:data.id,kind:data.kind,label:data.label,body:data.body??"",index:data.index,text:lines[data.index],createdAt:data.createdAt,status:"open",detachedReason:null,priorAnchors:[]};
    validAnnotation(item);if(items.some(a=>a.id===item.id))throw Error("Annotation identity already exists.");
    items.push(item);return item;
  }
  function changeAnnotation(state,lines,id,action,index){
    const a=(state.annotations||[]).find(x=>x.id===id);if(!a)throw Error("Annotation no longer exists.");
    if(action==="resolve"&&a.kind==="comment"&&a.status==="open")a.status="resolved";
    else if(action==="reopen"&&a.kind==="comment"&&a.status==="resolved")a.status="open";
    else if(action==="archive"&&a.status!=="archived"){a.statusBeforeArchive=a.status;a.status="archived";}
    else if(action==="restore"&&a.status==="archived"){a.status=a.kind==="comment"&&a.statusBeforeArchive==="resolved"?"resolved":"open";delete a.statusBeforeArchive;}
    else if(action==="reattach"&&a.status!=="archived"&&a.detachedReason!==null){
      if(!Number.isInteger(index)||index<0||index>=lines.length)throw Error("Select a valid committed paragraph.");
      if(typeof lines[index]!=="string"||lines[index].length>50000||a.priorAnchors.length>=100)throw Error("Cannot retain another full annotation anchor within its limits.");
      a.priorAnchors.push({index:a.index,text:a.text,reason:a.detachedReason});a.index=index;a.text=lines[index];a.detachedReason=null;
    }else throw Error("Annotation action is not available.");
    validAnnotation(a);return a;
  }

  // ---------------------------------------------------------------------------
  // Character-range formatting ("runs").
  //
  // A paragraph role styles a whole paragraph. A run styles part of one: the two
  // words in the middle of a sentence that are italic, the single bolded name.
  // Runs are presentation metadata and nothing else. No function here ever
  // changes a character of the author's text; every one of them takes the text
  // as given and only moves offsets around it.
  //
  // A run row is anchored exactly the way a format row is: by paragraph index
  // AND by that paragraph's exact text. If the text no longer matches, the row
  // is detached into inlineUnmapped rather than guessed at, for the same reason
  // annotations are never re-anchored by similarity.
  //
  //   {index: 4, text: "the whole paragraph", runs: [{start, end, ...marks}]}
  //
  // Offsets are UTF-16 code units, counted from the start of the paragraph, with
  // end exclusive -- the same units textarea.setSelectionRange uses, so a caret
  // position can be handed straight to these functions without conversion.
  // Runs within a row are sorted, non-empty and never overlap.
  const inlineFonts=["default","serif","sans","mono","Times New Roman","Georgia","Garamond","Palatino","Book Antiqua","Cambria","Century Schoolbook","Arial","Helvetica","Calibri","Verdana","Tahoma","Trebuchet MS","Impact","Comic Sans MS","Courier New","Consolas","DM Sans","DM Mono","Cormorant Garamond"];
  const inlineFontCss={"default":"","serif":"Georgia,serif","sans":"Arial,sans-serif","mono":"'Courier New',monospace"};
  // Only these keys may appear on a run, and only when they are doing something.
  // A run carrying no mark at all is not stored; that is what clearing produces.
  const inlineFlags=["bold","italic","underline","strike","sup","sub"];
  const MAX_RUNS_PER_PARAGRAPH=400, MAX_INLINE_ROWS=5000;
  const hexColor=v=>typeof v==="string"&&/^#[0-9a-fA-F]{6}$/.test(v);
  function validMarks(m){
    if(!m||typeof m!=="object")throw Error("Invalid character formatting.");
    for(const key of Object.keys(m))if(!["start","end",...inlineFlags,"font","size","color","highlight"].includes(key))throw Error("Unknown character formatting property: "+key);
    for(const key of inlineFlags)if(m[key]!==undefined&&m[key]!==true)throw Error("Character formatting flags are present only when set.");
    if(m.sup&&m.sub)throw Error("Text cannot be superscript and subscript at once.");
    if(m.font!==undefined&&!inlineFonts.includes(m.font))throw Error("That font is not one of 2i's available fonts.");
    if(m.size!==undefined&&(!Number.isFinite(m.size)||m.size<6||m.size>96))throw Error("Point size must be between 6 and 96.");
    if(m.color!==undefined&&!hexColor(m.color))throw Error("Text colour must be a #rrggbb value.");
    if(m.highlight!==undefined&&!hexColor(m.highlight))throw Error("Highlight colour must be a #rrggbb value.");
    return m;
  }
  // The marks of a run, without its offsets. Used for comparison and merging.
  const marksOf=r=>{const m={};for(const k of [...inlineFlags,"font","size","color","highlight"])if(r[k]!==undefined)m[k]=r[k];return m;};
  const marksEqual=(a,b)=>{const x=marksOf(a),y=marksOf(b),kx=Object.keys(x).sort(),ky=Object.keys(y).sort();return kx.length===ky.length&&kx.every((k,i)=>k===ky[i]&&x[k]===y[k]);};
  const marksEmpty=r=>!Object.keys(marksOf(r)).length;
  // Adjacent runs carrying identical marks are one run. Merging on every write
  // is what keeps a heavily edited paragraph from accumulating hundreds of
  // one-character runs, and keeps the saved .2i file small.
  function normalizeRuns(runs,length){
    const clean=[];
    for(const r of runs.slice().sort((a,b)=>a.start-b.start||a.end-b.end)){
      const start=Math.max(0,Math.min(r.start,length)),end=Math.max(0,Math.min(r.end,length));
      if(!(end>start)||marksEmpty(r))continue;
      const last=clean[clean.length-1];
      if(last&&last.end>=start&&marksEqual(last,r)){last.end=Math.max(last.end,end);continue;}
      clean.push({start,end,...marksOf(r)});
    }
    if(clean.length>MAX_RUNS_PER_PARAGRAPH)throw Error("This paragraph has more separate formatting changes than 2i stores ("+MAX_RUNS_PER_PARAGRAPH+"). Simplify its formatting; no text was changed.");
    for(let i=1;i<clean.length;i++)if(clean[i].start<clean[i-1].end)throw Error("Character formatting ranges overlap.");
    return clean;
  }
  function validInlineRow(row,strict=true){
    if(!row||!Number.isInteger(row.index)||row.index<0||typeof row.text!=="string"||row.text.length>50000||!Array.isArray(row.runs))throw Error("Invalid character-formatting anchor.");
    for(const r of row.runs){
      validMarks(r);
      if(!Number.isInteger(r.start)||!Number.isInteger(r.end)||r.start<0||r.end<=r.start)throw Error("Invalid character range.");
      if(strict&&r.end>row.text.length)throw Error("A character range falls outside its paragraph.");
    }
    return row;
  }
  function restoreInline(items,lines){
    if(items===undefined)return [];
    if(!Array.isArray(items)||items.length>MAX_INLINE_ROWS)throw Error("Invalid character-formatting collection.");
    const seen=new Set();
    return items.map(row=>{
      validInlineRow(row);
      if(seen.has(row.index))throw Error("Duplicate character-formatting anchor.");
      seen.add(row.index);
      return {index:row.index,text:row.text,runs:normalizeRuns(row.runs,row.text.length)};
    });
  }
  // Move run offsets across an edit made to one paragraph's text.
  //
  // The common prefix and suffix are found first, so the untouched ends of the
  // paragraph keep their formatting exactly. Text typed inside a formatted span
  // inherits that span's marks, which is what every word processor does and what
  // a writer expects: type into the middle of a bold phrase and it stays bold.
  // Text typed at a boundary inherits from the character to its left, if that
  // character was formatted, and is otherwise plain.
  function remapRuns(runs,before,after){
    if(before===after)return runs.map(r=>({...r}));
    let p=0,sfx=0;
    const max=Math.min(before.length,after.length);
    while(p<max&&before[p]===after[p])p++;
    while(sfx<max-p&&before[before.length-1-sfx]===after[after.length-1-sfx])sfx++;
    const oldEnd=before.length-sfx,newEnd=after.length-sfx,delta=after.length-before.length;
    const moved=[];
    for(const r of runs){
      const tailStart=Math.max(r.start,oldEnd),tailEnd=Math.max(r.end,oldEnd);
      // the part of this run before the edit
      if(r.start<p)moved.push({...r,start:r.start,end:Math.min(r.end,p)});
      // the part after the edit, shifted
      if(r.end>oldEnd)moved.push({...r,start:tailStart+delta,end:tailEnd+delta});
      // the inserted text, when this run covered the point it was typed into
      if(newEnd>p&&r.start<=p&&r.end>=p&&!(r.end===p&&r.start===p))
        moved.push({...r,start:p,end:newEnd});
    }
    return normalizeRuns(moved,after.length);
  }
  function reconcileInline(state,before,after,first,last){
    const rows=state.inline||[];
    if(!rows.length)return;
    const end=before.length-last,newEnd=after.length-last,delta=after.length-before.length;
    const detached=state.inlineUnmapped||(state.inlineUnmapped=[]);
    const kept=[];
    for(const row of rows){
      let index=null;
      if(before[row.index]===row.text){
        if(row.index<first)index=row.index;                       // above the edit
        else if(row.index>=end)index=row.index+delta;             // below it, shifted
        else if(end-first===1&&newEnd-first===1)index=first;      // this paragraph was retyped
      }
      if(index===null||index<0||index>=after.length){detached.push({...row,reason:"edit changed paragraph structure"});continue;}
      const text=after[index];
      const runs=text===row.text?row.runs.map(r=>({...r})):remapRuns(row.runs,row.text,text);
      if(runs.length)kept.push({index,text,runs});
    }
    state.inline=kept.sort((a,b)=>a.index-b.index);
  }
  // Read the runs for one paragraph, or [] when it has none or its anchor is stale.
  function inlineRuns(state,lines,index){
    const row=(state.inline||[]).find(r=>r.index===index);
    return row&&lines[index]===row.text?row.runs.map(r=>({...r})):[];
  }
  // What the toolbar should light up for the current selection: a mark is
  // reported only when it covers the whole selection, so pressing Bold on a
  // partly bold selection bolds all of it rather than clearing it.
  function inlineStateAt(state,lines,index,start,end){
    const runs=inlineRuns(state,lines,index),span=Math.max(0,end-start);
    const result={};
    const covering=pos=>runs.find(r=>r.start<=pos&&r.end>pos);
    if(!span){
      // A caret, not a selection: report the character to its LEFT, as a word
      // processor does, so typing continues the formatting you just left. At the
      // very start of a paragraph there is nothing to the left, so it is plain --
      // putting the caret before a bold word and typing does not bold what you type.
      const at=start>0?covering(start-1):null;
      return at?marksOf(at):{};
    }
    for(const key of [...inlineFlags,"font","size","color","highlight"]){
      let value,all=true;
      for(let pos=start;pos<end;pos++){
        const run=covering(pos),mark=run?run[key]:undefined;
        if(mark===undefined){all=false;break;}
        if(value===undefined)value=mark;
        else if(value!==mark){all=false;break;}
      }
      if(all&&value!==undefined)result[key]=value;
    }
    return result;
  }
  // Set marks on a character range. marks:{bold:true} sets, {bold:false} clears,
  // {font:"default"} / {size:0} return that property to the paragraph's own style.
  //
  // Nothing is written until every resulting run has been validated. A refused
  // request must leave the document exactly as it was: a half-applied run would
  // sit in the saved .2i file and make the next, valid request fail too.
  function applyInline(state,lines,index,start,end,marks,locks=[]){
    if(!Number.isInteger(index)||index<0||index>=lines.length)throw Error("Select a committed paragraph.");
    if(new Set(locks).has(index))throw Error("Unlock this paragraph before changing its character formatting.");
    const text=lines[index];
    if(!Number.isInteger(start)||!Number.isInteger(end)||start<0||end>text.length||end<=start)throw Error("Select some text in the paragraph first.");
    if(!marks||typeof marks!=="object"||!Object.keys(marks).length)throw Error("No character formatting was requested.");
    for(const key of Object.keys(marks))if(![...inlineFlags,"font","size","color","highlight"].includes(key))throw Error("Unknown character formatting property: "+key);
    if(marks.sup&&marks.sub)throw Error("Text cannot be superscript and subscript at once.");
    const existing=inlineRuns(state,lines,index),pieces=[];
    for(const r of existing){
      if(r.end<=start||r.start>=end){pieces.push({...r});continue;}        // outside the selection
      if(r.start<start)pieces.push({...r,end:start});                      // the head keeps its marks
      if(r.end>end)pieces.push({...r,start:end});                          // so does the tail
      // The overlapped middle is rebuilt from offsets and the new marks only.
      // Spreading the old run here would let a mark being cleared survive,
      // because deleting a key cannot override an earlier spread of it.
      pieces.push({start:Math.max(r.start,start),end:Math.min(r.end,end),...nextMarks(r,marks)});
    }
    let pos=start;                                                         // parts of the selection with no run yet
    for(const r of existing.filter(r=>r.start<end&&r.end>start).sort((a,b)=>a.start-b.start)){
      if(r.start>pos)pieces.push({start:pos,end:Math.min(r.start,end),...nextMarks({},marks)});
      pos=Math.max(pos,r.end);
    }
    if(pos<end)pieces.push({start:pos,end,...nextMarks({},marks)});
    const runs=normalizeRuns(pieces,text.length);
    for(const r of runs)validMarks(r);
    const rows=state.inline||(state.inline=[]);
    const row=rows.find(r=>r.index===index);
    if(!runs.length){if(row)state.inline=rows.filter(r=>r!==row);return state;}
    if(row){row.text=text;row.runs=runs;return state;}
    if(rows.length>=MAX_INLINE_ROWS)throw Error("More paragraphs carry character formatting than 2i stores. Export a copy; no text was changed.");
    rows.push({index,text,runs});rows.sort((a,b)=>a.index-b.index);
    return state;
  }
  // Applying a mark to a run that already carries conflicting marks: setting
  // superscript clears subscript, and false / "default" / 0 remove a property
  // instead of storing a falsy one.
  function nextMarks(run,marks){
    const next=marksOf(run);
    for(const [key,value] of Object.entries(marks)){
      if(key==="start"||key==="end")continue;
      const off=value===false||value===undefined||value===null||(key==="font"&&value==="default")||(key==="size"&&!value);
      if(off)delete next[key];
      else next[key]=key==="size"?Number(value):value;
    }
    if(marks.sup)delete next.sub;
    if(marks.sub)delete next.sup;
    return next;
  }
  function clearInline(state,lines,index,start,end,locks=[]){
    if(!Number.isInteger(index)||index<0||index>=lines.length)throw Error("Select a committed paragraph.");
    if(new Set(locks).has(index))throw Error("Unlock this paragraph before clearing its character formatting.");
    const row=(state.inline||[]).find(r=>r.index===index);
    if(!row)return state;
    const text=lines[index];
    const whole=!Number.isInteger(start)||!Number.isInteger(end);
    const from=whole?0:start,to=whole?text.length:end;
    const pieces=[];
    for(const r of row.runs){
      if(r.end<=from||r.start>=to){pieces.push({...r});continue;}
      if(r.start<from)pieces.push({...r,end:from});
      if(r.end>to)pieces.push({...r,start:to});
    }
    row.runs=normalizeRuns(pieces,text.length);
    if(!row.runs.length)state.inline=state.inline.filter(r=>r!==row);
    return state;
  }
  function runCss(r){
    const css=[];
    if(r.bold)css.push("font-weight:bold");
    if(r.italic)css.push("font-style:italic");
    const lines=[];
    if(r.underline)lines.push("underline");
    if(r.strike)lines.push("line-through");
    if(lines.length)css.push("text-decoration:"+lines.join(" "));
    if(r.font!==undefined&&r.font!=="default")css.push("font-family:"+(inlineFontCss[r.font]||"'"+r.font+"',serif"));
    if(r.size)css.push("font-size:"+r.size+"pt");
    if(r.color)css.push("color:"+r.color);
    if(r.highlight)css.push("background-color:"+r.highlight);
    if(r.sup||r.sub)css.push("font-size:"+(r.size?Math.max(6,Math.round(r.size*0.75)):9)+"pt");
    return css.join(";");
  }
  // One paragraph as HTML, with its runs. Text is escaped first and never
  // altered; a run only wraps a slice of it. Returns escaped plain text when
  // there are no runs, so an unformatted document exports byte-for-byte as before.
  function inlineHtml(text,runs){
    if(!runs||!runs.length)return esc(text);
    let out="",pos=0;
    for(const r of runs.slice().sort((a,b)=>a.start-b.start)){
      if(r.start>pos)out+=esc(text.slice(pos,r.start));
      const tag=r.sup?"sup":r.sub?"sub":"span",css=runCss(r);
      out+="<"+tag+(css?' style="'+esc(css)+'"':"")+">"+esc(text.slice(r.start,r.end))+"</"+tag+">";
      pos=r.end;
    }
    if(pos<text.length)out+=esc(text.slice(pos));
    return out;
  }
  function restore(raw,lines=[]){
    if(raw===undefined||raw===null)return fresh();
    if(raw.version!==1||!Object.hasOwn(profiles,raw.profile)||!raw.page||!["letter","a4","legal"].includes(raw.page.size)||!["portrait","landscape"].includes(raw.page.orientation)||![0.5,0.75,1,1.25,1.5].includes(raw.page.margin)||!Array.isArray(raw.rows)||!Array.isArray(raw.unmapped))throw Error("Invalid document formatting.");
    const out=clone(raw),ids=new Set();out.annotations=restoreAnnotations(out.annotations,lines);
    // Character formatting restores the same way paragraph formatting does: an
    // anchor whose paragraph text no longer matches is detached, never guessed.
    out.inlineUnmapped=Array.isArray(out.inlineUnmapped)?out.inlineUnmapped:[];
    out.inline=restoreInline(out.inline,lines).filter(row=>{
      if(lines[row.index]===row.text)return true;
      out.inlineUnmapped.push({...row,reason:"source text no longer matches"});return false;
    });
    for(const r of [...out.rows,...out.unmapped]){
      if(!r||!Number.isInteger(r.index)||r.index<0||typeof r.text!=="string")throw Error("Invalid format anchor.");
      validStyle(r.style);
    }
    for(const r of out.rows){if(ids.has(r.index))throw Error("Duplicate format anchor.");ids.add(r.index);}
    out.rows=out.rows.filter(r=>{if(lines[r.index]===r.text)return true;out.unmapped.push({...r,reason:"source text no longer matches"});return false;});
    return out;
  }
  function reconcile(state,before,after){
    if(before.length===after.length&&before.every((x,i)=>x===after[i]))return state;
    let first=0,last=0;
    while(first<before.length&&first<after.length&&before[first]===after[first])first++;
    while(last<before.length-first&&last<after.length-first&&before[before.length-last-1]===after[after.length-last-1])last++;
    const end=before.length-last,newEnd=after.length-last,delta=after.length-before.length;
    const kept=[];
    for(const r of state.rows){
      let index=null;
      if(before[r.index]===r.text){
        if(r.index<first)index=r.index;
        else if(r.index>=end)index=r.index+delta;
        else if(end-first===1&&newEnd-first===1)index=first;
      }
      if(index!==null&&index>=0&&index<after.length)kept.push({...r,index,text:after[index]});
      else state.unmapped.push({...r,reason:"edit changed paragraph structure"});
    }
    state.rows=kept;reconcileAnnotations(state,before,after,first,last);reconcileInline(state,before,after,first,last);return state;
  }
  function apply(state,lines,indices,style,locks=[]){
    const clean=validStyle(style),locked=new Set(locks),selected=new Set(indices);
    if(!selected.size||[...selected].some(i=>!Number.isInteger(i)||i<0||i>=lines.length))throw Error("Select a valid committed paragraph.");
    if([...selected].some(i=>locked.has(i)))throw Error("Unlock protected paragraphs before changing their individual formatting.");
    if(!profiles[state.profile].roles.includes(clean.role))throw Error("That paragraph role does not belong to the current template.");
    state.rows=state.rows.filter(r=>!selected.has(r.index));
    for(const i of selected)state.rows.push({index:i,text:lines[i],style:clone(clean)});
    state.rows.sort((a,b)=>a.index-b.index);return state;
  }
  function clear(state,indices,locks=[]){const selected=new Set(indices),locked=new Set(locks);if([...selected].some(i=>locked.has(i)))throw Error("Unlock protected paragraphs before clearing their formatting.");state.rows=state.rows.filter(r=>!selected.has(r.index));return state;}
  const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  function roleCss(role,kind){
    const script=kind==="script"||kind==="multi";
    const table={title:"text-align:center;font-size:20pt;font-weight:bold;margin-bottom:18pt",subtitle:"text-align:center;font-style:italic",heading1:"font-size:18pt;font-weight:bold;break-after:avoid",heading2:"font-size:15pt;font-weight:bold;break-after:avoid",heading3:"font-size:13pt;font-weight:bold;break-after:avoid",quote:"margin-left:0.5in;margin-right:0.5in;font-style:italic",list:"margin-left:0.35in",caption:"font-size:10pt;font-style:italic",logline:"font-weight:bold",scene:"text-transform:uppercase;break-after:avoid;margin-top:12pt",shot:"text-transform:uppercase;break-after:avoid",character:"text-transform:uppercase;margin-left:2.1in;break-after:avoid",dialogue:"margin-left:1in;margin-right:1.5in;margin-bottom:6pt",parenthetical:"margin-left:1.6in;margin-right:2in;break-after:avoid",transition:"text-align:right;text-transform:uppercase",act:"text-align:center;text-transform:uppercase;text-decoration:underline;break-after:avoid",cast:"font-style:italic;break-after:avoid",cue:"text-transform:uppercase;font-weight:bold",segment:"font-weight:bold;break-after:avoid"};
    let css=table[role]||"";
    if(kind==="multi"&&role==="action")css+=";text-transform:uppercase";
    if(kind==="multi"&&role==="dialogue")css+=";line-height:2";
    if(!script&&role==="body")css+=";text-indent:0.5in";
    return css;
  }
  function styleCss(s,kind){
    const css=[roleCss(s.role,kind)];
    if(s.align!=="default")css.push("text-align:"+s.align);
    if(s.font!=="default")css.push("font-family:"+({serif:"Georgia,serif",sans:"Arial,sans-serif",mono:"'Courier New',monospace"}[s.font]));
    if(s.indent)css.push("margin-left:"+s.indent+"in");
    if(listKind(s)&&!s.indent)css.push("margin-left:0.25in");
    if(s.size)css.push("font-size:"+s.size+"pt");
    if(s.spacing)css.push("line-height:"+s.spacing);
    if(s.bold)css.push("font-weight:bold");if(s.italic)css.push("font-style:italic");if(s.underline)css.push("text-decoration:underline");
    return css.join(";");
  }
  function profileContext(state){const p=profiles[state.profile];return {documentType:state.profile,label:p.label,kind:p.kind,guidance:p.guidance,allowedParagraphRoles:[...p.roles],instruction:"Use this document convention; never insert formatting markup or change the author's text without approval. Paragraph roles are a presentation layer."};}
  function exportHtml(title,lines,state,chapters=[]){
    const p=profiles[state.profile],by=new Map(state.rows.map(r=>[r.index,r])),av=p.kind==="av",script=p.kind==="script"||p.kind==="multi";
    const page=state.page,dimensions={letter:["8.5in","11in"],a4:["210mm","297mm"],legal:["8.5in","14in"]}[page.size],width=dimensions[page.orientation==="portrait"?0:1],height=dimensions[page.orientation==="portrait"?1:0];
    const inlineBy=new Map((state.inline||[]).map(r=>[r.index,r]));
    const entries=lines.map((text,i)=>{const row=by.get(i);const style=row&&row.text===text?row.style:defaultStyle(script?"action":"general");const marks=inlineBy.get(i);return {text,style,runs:marks&&marks.text===text?marks.runs:null};});
    const element=(e)=>'<p class="paragraph" style="'+esc(styleCss(e.style,p.kind))+'">'+(e.text?inlineHtml(e.text,e.runs):"&nbsp;")+'</p>';
    let body="";
    if(av){
      body='<table><thead><tr><th>VIDEO / VISUAL</th><th>AUDIO / SOUND</th></tr></thead><tbody>';
      const visual=new Set(["visual"]),audio=new Set(["audio","voiceover","interview","sound","music"]);
      for(let i=0;i<entries.length;i++){
        const e=entries[i],next=entries[i+1];
        if(visual.has(e.style.role)){const paired=next&&audio.has(next.style.role);body+="<tr><td>"+element(e)+"</td><td>"+(paired?element(next):"")+"</td></tr>";if(paired)i++;}
        else if(audio.has(e.style.role))body+="<tr><td></td><td>"+element(e)+"</td></tr>";
        else body+='<tr><td colspan="2">'+element(e)+"</td></tr>";
      }body+="</tbody></table>";
    }else{
      const heading=i=>(state.profile==="manuscript"||state.profile==="story")?chapters.filter(c=>c.startLine===i&&typeof c.title==="string").map(c=>'<h2 class="chapter">'+esc(c.title)+'</h2>'+(c.subtitle?'<p class="chapter-subtitle">'+esc(c.subtitle)+'</p>':"")).join(""):"";
      const item=(e)=>'<li style="'+esc(styleCss(e.style,p.kind))+'">'+(e.text?inlineHtml(e.text,e.runs):"&nbsp;")+'</li>';
      const parts=[];
      let open=null;
      const close=()=>{if(open){parts.push(open==="bullet"?"</ul>":"</ol>");open=null;}};
      entries.forEach((e,i)=>{
        const kind=listKind(e.style),head=heading(i);
        // A chapter heading always ends a list; a list never runs through one.
        if(head||kind!==open)close();
        if(head)parts.push(head);
        if(kind&&kind!==open){parts.push(kind==="bullet"?"<ul>":"<ol>");open=kind;}
        parts.push(kind?item(e):element(e));
      });
      close();
      body=parts.join("\n");
    }
    const defaultFont=script?"'Courier New',monospace":"Georgia,serif",defaultSpacing=script?1:1.5;
    return '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+esc(title)+'</title><style>@page{size:'+width+" "+height+";margin:"+page.margin+'in}*{box-sizing:border-box}html{background:#e8e5df}body{max-width:'+width+';min-height:'+height+';margin:16px auto;padding:'+page.margin+'in;background:white;color:#191919;font:12pt/'+defaultSpacing+' '+defaultFont+'}.chapter{text-align:center;break-after:avoid;margin:22pt 0 8pt}.chapter-subtitle{text-align:center;font-style:italic;break-after:avoid}.paragraph{white-space:pre-wrap;overflow-wrap:anywhere;margin-top:0;margin-bottom:6pt;orphans:2;widows:2}ul,ol{margin:0 0 6pt;padding-left:0.4in}li{margin-bottom:2pt}table{border-collapse:collapse;width:100%;table-layout:fixed}td,th{width:50%;border:1px solid #555;padding:8pt;vertical-align:top}tr{break-inside:avoid}@media print{html{background:white}body{margin:0;padding:0;max-width:none;min-height:0}}</style><body>'+body+'</body></html>';
  }

  // ---------------------------------------------------------------------------
  // RTF export.
  //
  // WordPad's own format, and the one most word processors will open without
  // argument. Everything 2i can say about a character -- bold, italic,
  // underline, strikethrough, superscript, subscript, font, size, colour,
  // highlight -- has an RTF equivalent, so a formatted manuscript arrives
  // formatted rather than as plain text.
  //
  // Lists are written as a marker and a hanging indent rather than as RTF list
  // tables. A list table is a large, fragile structure that several readers
  // disagree about; a bullet and a tab render correctly everywhere, and the
  // words are identical either way.
  const RTF_FONTS={"default":"Georgia","serif":"Georgia","sans":"Arial","mono":"Courier New"};
  function rtfText(value){
    let out="";
    for(const char of String(value)){
      if(char==="\\"||char==="{"||char==="}"){out+="\\"+char;continue;}
      if(char==="\t"){out+="\\tab ";continue;}
      const cp=char.codePointAt(0);
      if(cp<128){out+=char;continue;}
      // RTF takes signed 16-bit words, so anything past the basic plane goes out
      // as its surrogate pair, each with an ASCII fallback character after it.
      for(let i=0;i<char.length;i++){
        let unit=char.charCodeAt(i);
        if(unit>32767)unit-=65536;
        out+="\\u"+unit+"?";
      }
    }
    return out;
  }
  function exportRtf(title,lines,state,chapters=[]){
    const profile=profiles[state.profile],script=["script","multi"].includes(profile.kind);
    const byRow=new Map(state.rows.map(r=>[r.index,r]));
    const byInline=new Map((state.inline||[]).map(r=>[r.index,r]));
    const fontNames=[script?"Courier New":"Georgia"];
    const colours=["#000000"];
    const fontIndex=name=>{const value=RTF_FONTS[name]||name;const at=fontNames.indexOf(value);if(at>=0)return at;fontNames.push(value);return fontNames.length-1;};
    const colourIndex=hex=>{const value=String(hex).toLowerCase();const at=colours.indexOf(value);if(at>=0)return at;colours.push(value);return colours.length-1;};
    const headings=new Map();
    for(const chapter of chapters)
      if(Number.isInteger(chapter?.startLine)&&typeof chapter.title==="string")
        headings.set(chapter.startLine,chapter);
    const align={left:"\\ql",center:"\\qc",right:"\\qr",justify:"\\qj",default:""};
    const body=[];
    let ordinal=0;
    lines.forEach((text,index)=>{
      const row=byRow.get(index),style=row&&row.text===text?row.style:defaultStyle(script?"action":"general");
      const list=listKind(style);
      ordinal=list==="number"?ordinal+1:0;
      const chapter=headings.get(index);
      if(chapter){
        body.push("\\pard\\plain\\qc\\sb240\\sa120\\b\\fs32 "+rtfText(chapter.title)+"\\b0\\fs24\\par");
        if(chapter.subtitle)body.push("\\pard\\plain\\qc\\i "+rtfText(chapter.subtitle)+"\\i0\\par");
      }
      // \pard resets paragraph properties; \plain resets character ones. Without
      // \plain a bold paragraph makes every paragraph after it bold, because RTF
      // character state runs on until something turns it off. Verified by opening
      // the result in LibreOffice, which is how this was caught.
      const control=["\\pard\\plain"];
      if(align[style.align])control.push(align[style.align]);
      const indent=Math.round((style.indent||0)*1440)+(list?360:0);
      if(indent)control.push("\\li"+indent);
      if(list)control.push("\\fi-360");                       // hang the marker
      if(style.spacing)control.push("\\sl"+Math.round(style.spacing*240)+"\\slmult1");
      control.push("\\sa120");
      if(style.font&&style.font!=="default")control.push("\\f"+fontIndex(style.font));
      if(style.size)control.push("\\fs"+Math.round(style.size*2));
      if(style.bold)control.push("\\b");
      if(style.italic)control.push("\\i");
      if(style.underline)control.push("\\ul");
      let line=control.join("")+" ";
      if(list)line+=(list==="bullet"?"\\u8226?":rtfText(ordinal+"."))+"\\tab ";
      const inline=byInline.get(index);
      const runs=inline&&inline.text===text?inline.runs:[];
      const emit=(slice,marks)=>{
        if(!slice)return;
        if(!marks){line+=rtfText(slice);return;}
        const on=[],off=[];
        if(marks.bold){on.push("\\b");off.push("\\b0");}
        if(marks.italic){on.push("\\i");off.push("\\i0");}
        if(marks.underline){on.push("\\ul");off.push("\\ulnone");}
        if(marks.strike){on.push("\\strike");off.push("\\strike0");}
        if(marks.sup){on.push("\\super");off.push("\\nosupersub");}
        if(marks.sub){on.push("\\sub");off.push("\\nosupersub");}
        if(marks.font&&marks.font!=="default"){on.push("\\f"+fontIndex(marks.font));off.push("\\f0");}
        if(marks.size){on.push("\\fs"+Math.round(marks.size*2));off.push(style.size?"\\fs"+Math.round(style.size*2):"\\fs24");}
        if(marks.color){on.push("\\cf"+colourIndex(marks.color));off.push("\\cf0");}
        if(marks.highlight){on.push("\\highlight"+colourIndex(marks.highlight));off.push("\\highlight0");}
        line+="{"+on.join("")+" "+rtfText(slice)+off.join("")+"}";
      };
      let at=0;
      for(const run of runs.slice().sort((a,b)=>a.start-b.start)){
        if(run.start>at)emit(text.slice(at,run.start),null);
        emit(text.slice(run.start,run.end),marksOf(run));
        at=run.end;
      }
      emit(text.slice(at),null);
      body.push(line+"\\par");
    });
    const fontTable="{\\fonttbl"+fontNames.map((name,i)=>"{\\f"+i+"\\fnil\\fcharset0 "+name+";}").join("")+"}";
    const colourTable="{\\colortbl;"+colours.slice(1).map(hex=>
      "\\red"+parseInt(hex.slice(1,3),16)+"\\green"+parseInt(hex.slice(3,5),16)+"\\blue"+parseInt(hex.slice(5,7),16)+";"
    ).join("")+"}";
    const info="{\\info{\\title "+rtfText(String(title||"Untitled"))+"}}";
    return "{\\rtf1\\ansi\\ansicpg1252\\deff0\\uc1"+fontTable+colourTable+info+
      "\\f0\\fs24\n"+body.join("\n")+"\n}";
  }
  function scriptRows(lines,state){
    const map=new Map((state.rows||[]).map(r=>[r.index,r]));
    return lines.map((text,index)=>{const row=map.get(index),explicit=row?.text===text;return {index,text,role:explicit?row.style.role:"action",explicit};});
  }
  function xmlText(s){
    for(const char of s){const cp=char.codePointAt(0);if(!(cp===9||cp===10||cp===13||cp>=32&&cp<=0xD7FF||cp>=0xE000&&cp<=0xFFFD||cp>=0x10000&&cp<=0x10FFFF))throw Error("The manuscript contains a character XML 1.0 cannot represent. Export native .2i or text; no words were changed.");}
    return esc(s).replace(/\r/g,"&#13;");
  }
  function exportFdx(lines,state){
    if(!["script","multi"].includes(profiles[state.profile]?.kind))throw Error("Choose a screenplay or stage/script preset before exporting FDX.");
    if(!lines.length)throw Error("There is no committed manuscript to export.");
    const map={scene:"Scene Heading",action:"Action",character:"Character",dialogue:"Dialogue",parenthetical:"Parenthetical",transition:"Transition",shot:"Shot",general:"General"};
    const rows=scriptRows(lines,state),fallback=new Set(),untyped=rows.filter(r=>!r.explicit&&r.text.trim()).length;
    const content=rows.map(r=>{if(r.explicit&&!Object.hasOwn(map,r.role))fallback.add(r.role);const type=Object.hasOwn(map,r.role)?map[r.role]:"General";return '<Paragraph Type="'+type+'"><Text xml:space="preserve">'+xmlText(r.text)+'</Text></Paragraph>';}).join("\n");
    return {xml:'<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n<FinalDraft DocumentType="Script" Template="No" Version="5">\n<Content>\n'+content+'\n</Content>\n</FinalDraft>\n',untyped,fallbackRoles:[...fallback].sort(),paragraphs:rows.length};
  }
  function dialogueIndex(lines,state){
    const rows=scriptRows(lines,state),speakers=new Map(),scenes=[],unassigned=[],untagged=rows.filter(r=>!r.explicit&&r.text.trim()).length;
    let scene=null,cue=null;
    for(const r of rows){
      if(!r.explicit){if(r.text.trim())cue=null;continue;}
      if(r.role==="scene"||r.role==="act"||r.role==="segment"){
        scene={index:r.index,title:r.text,kind:r.role,cues:0,dialogue:0};scenes.push(scene);cue=null;
      }else if(r.role==="character"){
        if(!r.text.trim()){cue=null;continue;}
        if(!speakers.has(r.text))speakers.set(r.text,{name:r.text,cues:[],dialogue:[]});
        cue=speakers.get(r.text);cue.cues.push(r.index);if(scene)scene.cues++;
      }else if(r.role==="dialogue"||r.role==="parenthetical"){
        if(!cue)unassigned.push({index:r.index,role:r.role,text:r.text});
        else{cue.dialogue.push({index:r.index,role:r.role,text:r.text,sceneIndex:scene?.index??null});if(scene&&r.role==="dialogue")scene.dialogue++;}
      }else cue=null;
    }
    return {speakers:[...speakers.values()],scenes,unassigned,untagged};
  }
  // Read-only paragraph comparison. The common prefix and suffix are removed
  // first. Large changed regions fall back to a lossless coarse replacement
  // rather than allocating an unbounded quadratic matrix on modest hardware.
  function compareLines(oldLines,newLines){
    if(!Array.isArray(oldLines)||!Array.isArray(newLines)||oldLines.some(x=>typeof x!=="string")||newLines.some(x=>typeof x!=="string"))throw Error("Invalid revision text.");
    let prefix=0,suffix=0;
    while(prefix<oldLines.length&&prefix<newLines.length&&oldLines[prefix]===newLines[prefix])prefix++;
    while(suffix<oldLines.length-prefix&&suffix<newLines.length-prefix&&oldLines[oldLines.length-1-suffix]===newLines[newLines.length-1-suffix])suffix++;
    const oldEnd=oldLines.length-suffix,newEnd=newLines.length-suffix,n=oldEnd-prefix,m=newEnd-prefix;
    const blocks=[];let method="line-lcs";
    if(n||m){
      if(!n||!m){blocks.push({oldStart:prefix,newStart:prefix,removed:oldLines.slice(prefix,oldEnd),added:newLines.slice(prefix,newEnd)});}
      else if((n+1)*(m+1)>250000){method="coarse-region";blocks.push({oldStart:prefix,newStart:prefix,removed:oldLines.slice(prefix,oldEnd),added:newLines.slice(prefix,newEnd)});}
      else{
        const width=m+1,dp=new Uint32Array((n+1)*width);
        for(let i=n-1;i>=0;i--)for(let j=m-1;j>=0;j--)dp[i*width+j]=oldLines[prefix+i]===newLines[prefix+j]?1+dp[(i+1)*width+j+1]:Math.max(dp[(i+1)*width+j],dp[i*width+j+1]);
        let i=0,j=0,block=null;
        const push=()=>{if(block){blocks.push(block);block=null;}};
        while(i<n||j<m){
          if(i<n&&j<m&&oldLines[prefix+i]===newLines[prefix+j]){push();i++;j++;continue;}
          if(!block)block={oldStart:prefix+i,newStart:prefix+j,removed:[],added:[]};
          if(i<n&&(j===m||dp[(i+1)*width+j]>=dp[i*width+j+1]))block.removed.push(oldLines[prefix+i++]);
          else block.added.push(newLines[prefix+j++]);
        }
        push();
      }
    }
    return {method,oldCount:oldLines.length,newCount:newLines.length,blocks,removedCount:blocks.reduce((n,b)=>n+b.removed.length,0),addedCount:blocks.reduce((n,b)=>n+b.added.length,0)};
  }
  return {profiles,names,fresh,restore,reconcile,apply,clear,defaultStyle,styleCss,exportHtml,profileContext,clone,scriptRows,exportFdx,dialogueIndex,compareLines,addAnnotation,changeAnnotation,
    inlineFonts,inlineFlags,inlineRuns,inlineStateAt,applyInline,clearInline,inlineHtml,runCss,remapRuns,normalizeRuns,marksOf,
    lists,listKind,aligns,exportRtf};
}
const TwoiFormatCore=makeFormatCore();
if(typeof module!=="undefined"&&module.exports)module.exports=TwoiFormatCore;
