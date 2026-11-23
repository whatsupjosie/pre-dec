/* Native 2i studio presentation and shared production notes. */
(function installStudioDesk(){
  function presentationMode(config,fileMode){return fileMode?"standard":config.seated?"typewriter":config.room?"notebook":"standard";}
  /* Josie: "In any open 2i window she can switch between the notebook, the typewriter and the single-page notebook
     from the menu." A studio seat decides which look 2i OPENS in; it no longer decides which looks may be chosen. */
  function canPresent(mode){return mode==="standard"||mode==="notebook"||mode==="typewriter";}
  // Foresight file trays use the same 2i editor. Keep their native file
  // adapter as storage authority, but do not disconnect the presentation UI.
  const filePresentation=!!reachFileMode;
  const q=new URLSearchParams(location.search),config=TwoiStudioBridge.presentation(q.get("studio_room"),q.get("studio_view"),q.get("desk"));
  document.body.dataset.twoiDesk=presentationMode(config,filePresentation);
  window.twoiCanPresent=mode=>canPresent(mode,config.seated);
  window.twoiSetPresentation=mode=>{
    if(!window.twoiCanPresent(mode))throw Error("This presentation requires a designated writing station.");
    document.body.dataset.twoiDesk=mode;
    document.dispatchEvent(new CustomEvent("twoi:presentation-change",{detail:{mode}}));
  };
  const el=(tag,text,parent)=>{const n=document.createElement(tag);if(text!==null)n.textContent=text;if(parent)parent.append(n);return n;};
  if(filePresentation){
    // The full format menu is intentionally absent for Foresight file trays.
    // Give file documents a working view selector rather than a hidden API.
    const target=document.querySelector(".top-bar");
    const label=el("label","View ",target);
    label.className="twoi-file-presentation-label";
    const chooser=el("select",null,label);
    chooser.id="twoiFilePresentation";
    chooser.setAttribute("aria-label","Writing presentation");
    for(const [mode,name] of [["standard","Document"],["notebook","Notebook"],["typewriter","Typewriter"]]){
      const option=el("option",name,chooser);option.value=mode;
    }
    chooser.value=document.body.dataset.twoiDesk;
    chooser.onchange=()=>window.twoiSetPresentation(chooser.value);
  }
  // Production notes belong to a studio seat, not a Foresight file tray.
  if(!filePresentation){
  const controls=el("div",null,$("mcSection").querySelector(".section-body"));controls.id="twoiStudioControls";
  const button=(label,action)=>{const b=el("button",label,controls);b.type="button";b.className="mc-btn";b.onclick=action;return b;};
  let loading=null,opening=false;
  async function ensureNotes(){
    if(!window.PubCastNotes){
      if(!loading)loading=new Promise((resolve,reject)=>{const script=el('script',null,document.head);script.src='/static/production_notes.js';script.onload=resolve;script.onerror=()=>{script.remove();loading=null;reject(Error('Production notes could not load.'));};});
      await loading;
      if(config.room)window.PubCastNotes.onView(config.room+'/'+q.get('studio_view'));
    }
    return window.PubCastNotes;
  }
  async function notes(action){
    if(initializing||!networked||!serverReady){addChat("notice","Connect and sign in to Bella Faux Pas before opening production notes.");return;}
    if(opening)return;opening=true;
    try{
      const service=await ensureNotes();
      // Reuse the actual room menu, not a parallel message composer.
      await service.open();
      if(action==="compose")await service.compose({});
      if(action==="place")await service.place();
    }catch(error){addChat("notice",error.message);}
    finally{opening=false;}
  }
  const inbox=button("Studio notes",()=>notes("inbox"));inbox.id="twoiNotesInbox";
  button("Write a note",()=>notes("compose")).id="twoiWriteNote";
  button("Place sticky note",()=>notes("place")).id="twoiPlaceNote";
  document.addEventListener("pubcast:notes-unread",e=>{const n=e.detail?.count;inbox.textContent=Number.isInteger(n)&&n>0?"Studio notes ("+n+" unread)":"Studio notes";});
  // Start the shared inbox poll only after the authenticated native editor is ready.
  window.reachStarted?.then(()=>{if(networked&&serverReady)ensureNotes().catch(()=>{});}).catch(()=>{});
  if(config.returnPath)button(config.seated?"Stand up · return to room":"Return to studio",async()=>{
    try{
      if(initializing){addChat("notice","Wait for the manuscript to open before leaving.");return;}
      if(!await preserveBeforeSwitch())return;
      if(!rememberStudioResume()){
        addChat("notice","Unable to retain this tab's manuscript handoff. Save or export your work before leaving.");
        return;
      }
      location.assign(config.returnPath);
    }catch(error){addChat("notice",error.message);}
  });
  }
  // Claude's original /typewriter-console remains the source of the key mapping,
  // key animations, keyboard support and sound. The 2i editor owns the words.
  const figure=el("figure",null,$("notebookFrame"));figure.id="twoiDeskScene";
  const typewriter=el("iframe",null,figure);
  typewriter.id="twoiTypewriterConsole";
  typewriter.title="Interactive blue and brass typewriter";
  const diskConsole = location.protocol === "file:";
  const diskToken = diskConsole ? crypto.randomUUID() : null;
  let diskPaperPort;
  typewriter.src = diskConsole
    ? "../static/typewriter_console.html?embedded=2i#" + diskToken
    : "/typewriter-console?embedded=2i";
  typewriter.loading="lazy";
  const expand=el("button","Expand keys",figure);
  expand.id="twoiTypewriterExpand";expand.type="button";
  expand.setAttribute("aria-expanded","false");
  expand.setAttribute("aria-controls","twoiTypewriterConsole");
  function setExpanded(on){
    figure.classList.toggle("is-expanded",on);
    expand.textContent=on?"Collapse keys":"Expand keys";
    expand.setAttribute("aria-expanded",String(on));
  }
  expand.onclick=()=>setExpanded(!figure.classList.contains("is-expanded"));
  document.addEventListener("keydown",e=>{
    if(e.key==="Escape"&&figure.classList.contains("is-expanded")){setExpanded(false);e.preventDefault();}
  });
  el("figcaption",config.seated?"Type on the machine or in the manuscript":"Typewriter view · keys edit this manuscript",figure);

  // ---- page zoom: the full-length sheet, standing in the machine ----------
  // Josie, 2026-11-21: "at the bottom of the screen, you can still have the
  // roller and the bay where the letter stamps are... and then just above that
  // is the full page."
  //
  // So this is not a separate look. It is the typewriter view with the page
  // given the whole column and the machine cropped to the band that holds the
  // platen, the paper bail and the bank of type hammers, sitting along the
  // bottom so the sheet rises out of it. Staying inside the typewriter view is
  // what keeps the sidebars, the menus and the typing sound exactly as they
  // are -- none of them has to learn about a fourth mode.
  //
  // The strip is the still image rather than the live console: the keys are
  // below the band and would be cut in half, and in this view the writing is
  // done on the real keyboard at the full page. The interactive keys stay in
  // the ordinary typewriter view, where they are whole.
  const machineStrip=el("div",null,$("notebookFrame"));
  machineStrip.id="twoiPageMachine";
  machineStrip.setAttribute("aria-hidden","true");
  const pageZoom=el("button","Page zoom",null);
  pageZoom.id="twoiTypewriterPage";pageZoom.type="button";
  pageZoom.className="twoi-rich-toggle";
  pageZoom.title="Give the page the full column, with the roller and type bars along the bottom";
  pageZoom.setAttribute("aria-pressed","false");
  const labelRow=$("manuscriptZone")?.querySelector(".zone-label-row");
  const zoneLabel=labelRow?.querySelector(".zone-label");
  if(zoneLabel)labelRow.insertBefore(pageZoom,zoneLabel);
  else if(labelRow)labelRow.append(pageZoom);
  function setPageZoom(on){
    const zoomed=!!on&&document.body.dataset.twoiDesk==="typewriter";
    if(zoomed)document.body.dataset.twoiTypewriterPage="on";
    else delete document.body.dataset.twoiTypewriterPage;
    pageZoom.setAttribute("aria-pressed",String(zoomed));
    pageZoom.textContent=zoomed?"Page zoom · on":"Page zoom";
    // One set of sound switches, moved to whichever piece of the machine is
    // showing, rather than a second set that could disagree with the first.
    (zoomed?machineStrip:figure).append(audioOptions);
    if(zoomed)setExpanded(false);
  }
  pageZoom.onclick=()=>setPageZoom(document.body.dataset.twoiTypewriterPage!=="on");

  // ---- the machine's own sounds -------------------------------------------
  // Josie: "audio effects must be optional". Both are off until she turns them
  // on, and her choice is kept. The controls live on the typewriter itself, so
  // they are in front of her only in the view that makes a sound.
  //
  // The cue logic is TwoiStudioBridge.cue, shared with preview-standalone.html
  // and tested in tests/test_2i_studio_bridge_node.js: it refuses to fire on a
  // paste, a drop, a replacement or a composition, so dictation and pasted text
  // do not rattle. The tones are synthesised, so this needs no audio files and
  // works with no network -- which is the point, since the dressing room is
  // somewhere she may be sitting offline.
  const audioOptions=el("div",null,figure);
  audioOptions.id="twoiAudioOptions";
  const audioKey="twoi.typewriter.audio.v1";
  let audioPrefs={click:false,bell:false};
  try{
    const saved=JSON.parse(localStorage.getItem(audioKey)||"null");
    if(saved){if(typeof saved.click==="boolean")audioPrefs.click=saved.click;if(typeof saved.bell==="boolean")audioPrefs.bell=saved.bell;}
  }catch{/* a browser that refuses storage still gets working sound, just not remembered */}
  function audioToggle(name,label){
    const wrap=el("label",null,audioOptions),box=el("input",null,wrap);
    box.type="checkbox";box.checked=audioPrefs[name];
    el("span",label,wrap);
    box.onchange=()=>{audioPrefs[name]=box.checked;try{localStorage.setItem(audioKey,JSON.stringify(audioPrefs));}catch{}};
    return box;
  }
  audioToggle("click","Key clicks");
  audioToggle("bell","Line-end bell");
  let audioContext=null,lastClickAt=0,relayingConsoleKey=false;
  function sound(kind){
    if(document.body.dataset.twoiDesk!=="typewriter"||!audioPrefs[kind])return;
    // Private interface effects only; never production or broadcast audio.
    try{
      const AC=window.AudioContext||window.webkitAudioContext;if(!AC)return;
      if(!audioContext)audioContext=new AC();
      if(audioContext.state==="suspended")audioContext.resume().catch(()=>{});
      const t=audioContext.currentTime;
      // Held keys and key repeat must not stack into a buzz.
      if(kind==="click"&&lastClickAt!==0&&t-lastClickAt<0.022)return;
      if(kind==="click")lastClickAt=t;
      const osc=audioContext.createOscillator(),gain=audioContext.createGain();
      osc.type=kind==="bell"?"sine":"triangle";
      osc.frequency.setValueAtTime(kind==="bell"?1450:940,t);
      if(kind==="click")osc.frequency.exponentialRampToValueAtTime(190,t+0.027);
      gain.gain.setValueAtTime(kind==="bell"?0.075:0.045,t);
      gain.gain.exponentialRampToValueAtTime(0.001,t+(kind==="bell"?0.22:0.042));
      osc.connect(gain);gain.connect(audioContext.destination);
      osc.start(t);osc.stop(t+(kind==="bell"?0.23:0.05));
      osc.onended=()=>{osc.disconnect();gain.disconnect();};
    }catch{/* no audio device, or the browser refused one */}
  }
  function play(cue){
    if(relayingConsoleKey)return; // the console already made that noise
    if(cue.click)sound("click");
    if(cue.bell)sound("bell");
  }
  // The plain writing fields report themselves through their own values.
  const typedBefore=new WeakMap();
  const isWritingField=node=>node===soloTextarea||node===draftArea||!!node?.matches?.(".m-line-edit textarea");
  document.addEventListener("beforeinput",event=>{
    if(event.isTrusted&&isWritingField(event.target)&&!event.isComposing)typedBefore.set(event.target,event.target.value);
  },true);
  document.addEventListener("input",event=>{
    if(!event.isTrusted||!isWritingField(event.target)||event.isComposing||!typedBefore.has(event.target))return;
    const before=typedBefore.get(event.target);typedBefore.delete(event.target);
    play(TwoiStudioBridge.cue(before,event.target.value,event.target.selectionStart,event.inputType,event.data));
  });
  // The live formatting surface is a contenteditable with no value of its own,
  // so it reports its own paragraph through twoi:typed (rich-surface.js).
  document.addEventListener("twoi:typed",event=>{
    const d=event.detail;
    if(!d)return;
    play(TwoiStudioBridge.cue(d.before,d.after,d.position,d.inputType,d.data));
  });
  window.addEventListener("pagehide",()=>{if(audioContext){audioContext.close().catch(()=>{});audioContext=null;}});

  function currentText(){
    return coWriting ? [committed.join("\n"),buffer.join("\n")].filter(Boolean).join("\n") : soloTextarea.value;
  }
  function syncPaper(){
    if(typewriter.dataset.ready!=="true" || !typewriter.contentWindow)return;
    const message = {
      type:"pubcast:2i-manuscript",
      // Only a decorative excerpt goes into the frame. Saving uses the actual editor.
      text:currentText().slice(-2000)
    };
    if (diskConsole) diskPaperPort?.postMessage(message);
    else typewriter.contentWindow.postMessage(message,location.origin);
  }
  typewriter.addEventListener("load",syncPaper); // child also sends its own ready handshake
  window.addEventListener("message",event=>{
    // Do not accept commands from another frame, domain, or an inactive view.
    if(event.source!==typewriter.contentWindow || event.origin!==(diskConsole?"null":location.origin))return;
    const data=event.data;
    // file: documents have opaque origins. Bind the paper to the port
    // supplied by this particular local console, including after reload.
    if (diskConsole && data?.token !== diskToken) return;
    if(data?.type==="pubcast:2i-ready"){
      if (diskConsole) {
        if (!event.ports[0]) return;
        diskPaperPort?.close();
        diskPaperPort = event.ports[0];
      }
      typewriter.dataset.ready="true";syncPaper();return;
    }
    if(data?.type==="pubcast:2i-collapse"){setExpanded(false);return;}
    if(data?.type!=="pubcast:2i-key" || document.body.dataset.twoiDesk!=="typewriter")return;
    // Foresight files are not writable until the real file session has mounted.
    // The chooser may render earlier, but typing must never bypass its save path.
    if(filePresentation&&!window.foresightFileSession){
      addChat("notice","Finish opening this Foresight file before using the typewriter.");
      return;
    }
    if(initializing || generating || chatSending || editingIdx!==null){
      addChat("notice","Finish the active edit or request before using the typewriter keys.");
      return;
    }
    if(!window.TwoiTypewriterInput){
      addChat("notice","Typewriter input is unavailable; write in the manuscript instead.");
      return;
    }
    // The console plays its own key sound through static/typewriter_sound.js, so
    // 2i must not add a second click on top of it for the same keystroke. One
    // key, one sound, whichever way the writer typed it.
    relayingConsoleKey=true;
    try{
      const surface=window.twoiRichSurface;
      const onSurface=!coWriting&&typeof surface?.active==="function"&&surface.active();
      // The live formatting surface is where the words are when it is on; the
      // hidden textarea behind it would lose them at the next model update.
      if(!onSurface||!surface.key(data.key))
        window.TwoiTypewriterInput.apply(coWriting?draftArea:soloTextarea,data.key);
    }finally{relayingConsoleKey=false;}
    // Existing input handlers enforce locked lines and synchronize Save Now.
    syncPaper();
  });
  document.addEventListener("foresight:work-change",syncPaper);
  for(const input of [soloTextarea,draftArea])input.addEventListener("input",syncPaper);
  const oldRender=render;
  render=function(){oldRender();syncPaper();};
  const syncPresentation=()=>{
    const active=document.body.dataset.twoiDesk==="typewriter";
    figure.hidden=!active;
    audioOptions.style.display=active?"":"none";
    pageZoom.hidden=!active;
    if(!active)setPageZoom(false);
    if(!active)setExpanded(false);
    if(active)syncPaper();
  };
  document.addEventListener("twoi:presentation-change",syncPresentation);
  syncPresentation();
})();
