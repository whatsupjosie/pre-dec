/* Shared server recording review and authenticated ZIP export. */
(function(root){const api=(function libraryFactory(){
  "use strict";
  const modes={camcorder:"Normal camcorder",data_only:"Data only",main_camera:"Main camera only"};
  const closed=s=>!!s&&["stopped","archived"].includes(s.state);
  const route=id=>"/api/recording/"+encodeURIComponent(id);
  function ordered(items){if(!Array.isArray(items))throw Error("Invalid recording list");return items.filter(x=>x&&typeof x.session_id==="string"&&x.session_id).sort((a,b)=>Number(b.started_at||0)-Number(a.started_at||0));}
  function filename(id){return (String(id).replace(/[^a-zA-Z0-9_.-]/g,"_").slice(0,120)||"recording")+".zip";}
  function formatBytes(bytes){const n=Number(bytes);if(!Number.isFinite(n)||n<0)return "unknown size";return n>=1048576?(n/1048576).toFixed(1)+" MiB":Math.round(n/1024)+" KiB";}
  function reportLines(s,m){
    const artifacts=Array.isArray(s.artifacts)?s.artifacts:[];
    const errors=Array.isArray(s.capture_errors)?s.capture_errors:[];
    const out=[(modes[s.mode]||s.mode||"Mode unknown")+" | "+String(s.state||"unknown"),"Sources: "+(Array.isArray(s.sources)?s.sources.join(", "):"unknown"),"Media artifacts: "+artifacts.length];
    for(const a of artifacts)out.push("  "+String(a.name||a.source_key||"Unnamed artifact")+" | "+formatBytes(a.size_bytes)+(a.synthetic?" | SYNTHETIC":""));
    for(const f of s.data_files||[])out.push("  Data: "+String(f));
    for(const e of errors)out.push("CAPTURE ERROR: "+String(e.source_id||"source")+" | "+String(e.error||"Unspecified error"));
    if(m){out.push("Mode report: "+String(m.state||"unknown"));if(m.show_data)out.push("Show data: "+String(m.show_data.events??"unknown")+" events; "+(m.show_data.complete===true?"complete":"not confirmed complete"));if(m.assembly)out.push("Program assembly: "+String(m.assembly.state||m.assembly.status||"see mode report"));for(const note of m.notes||[])out.push("Note: "+String(note));}
    return out;
  }
  async function failure(response){let data;try{data=await response.json();}catch(_){}return Error(typeof data?.detail==="string"?data.detail:"HTTP "+response.status);}
  async function json(url,options={}){const response=await fetch(url,{cache:"no-store",...options});if(!response.ok)throw await failure(response);return response.json();}
  async function download(id,format,progress=()=>{}){
    if(!id)throw Error("Select a recording");
    const name=filename(id);
    let writable=null,reader=null,blobURL=null;
    const maxBuffer=256*1024*1024;
    // Ask for a destination during the user gesture, before awaiting server work.
    if(typeof window.showSaveFilePicker==="function"){
      try{const handle=await window.showSaveFilePicker({suggestedName:name,types:[{description:"Recording bundle",accept:{"application/zip":[".zip"]}}]});writable=await handle.createWritable();}
      catch(error){if(error.name==="AbortError")return {canceled:true};if(error.name!=="SecurityError"&&error.name!=="NotSupportedError")throw error;}
    }
    try{
      progress("Preparing server export...");
      const response=await fetch(route(id)+"/export",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({format})});
      if(!response.ok)throw await failure(response);
      if(!/^application\/(?:zip|x-zip-compressed)(?:;|$)/i.test(response.headers.get("content-type")||""))throw Error("Server did not return a ZIP bundle");
      if(!response.body?.getReader)throw Error("Streaming download is unavailable in this browser");
      const raw=response.headers.get("content-length"),expected=raw===null?null:Number(raw);
      if(!writable&&expected!==null&&expected>maxBuffer)throw Error("Bundle exceeds safe in-memory download size; use a desktop browser with streaming Save As");
      reader=response.body.getReader();
      let total=0,chunks=[],prefix=[],verified=false,lastReport=0;
      for(;;){
        const {value,done}=await reader.read();if(done)break;
        if(!value?.length)continue;total+=value.length;
        if(!writable&&total>maxBuffer)throw Error("Bundle exceeds safe in-memory download size; use streaming Save As");
        if(!verified){
          for(let i=0;i<value.length&&prefix.length<4;i++)prefix.push(value[i]);
          if(prefix.length===4){if(prefix[0]!==80||prefix[1]!==75||!((prefix[2]===3&&prefix[3]===4)||(prefix[2]===5&&prefix[3]===6)))throw Error("Invalid ZIP signature");verified=true;}
        }
        if(writable)await writable.write(value);else chunks.push(value);
        if(Date.now()-lastReport>250){progress("Received "+formatBytes(total)+(expected!==null?" / "+formatBytes(expected):""));lastReport=Date.now();}
      }
      if(!verified||expected!==null&&total!==expected)throw Error("Incomplete or invalid export");
      if(writable){await writable.close();writable=null;return {saved:true,bytes:total};}
      blobURL=URL.createObjectURL(new Blob(chunks,{type:"application/zip"}));
      const anchor=document.createElement("a");anchor.href=blobURL;anchor.download=name;document.body.append(anchor);anchor.click();anchor.remove();
      const release=blobURL;setTimeout(()=>URL.revokeObjectURL(release),60000);blobURL=null;
      return {saved:false,bytes:total};
    }catch(error){try{await reader?.cancel();}catch(_){}try{await writable?.abort();}catch(_){}throw error;}
    finally{try{reader?.releaseLock();}catch(_){}if(blobURL)URL.revokeObjectURL(blobURL);}
  }
  function mount(panel){
    let sessions=[],selected=null,modeReport=null,busy=false,revision=0;
    const select=document.createElement("select");select.setAttribute("aria-label","Recording session");select.style.maxWidth="100%";
    const status=document.createElement("output");status.setAttribute("role","status");status.style.display="block";
    const details=document.createElement("pre");details.style.cssText="white-space:pre-wrap;overflow-wrap:anywhere;max-height:240px;overflow:auto;font-size:11px";
    const format=document.createElement("select");format.setAttribute("aria-label","Export format");for(const type of ["mp4","webm","wav","mov"]){const opt=document.createElement("option");opt.value=type;opt.textContent=type.toUpperCase()+" bundle";format.append(opt);}
    function button(label,fn){const b=document.createElement("button");b.type="button";b.textContent=label;b.addEventListener("click",fn);return b;}
    const refreshButton=button("REFRESH TAKES",()=>refresh()),exportButton=button("EXPORT ZIP",()=>work(async()=>{const out=await download(selected.session_id,format.value,s=>status.textContent=s);status.textContent=out.canceled?"Export canceled":out.saved?"Bundle saved ("+formatBytes(out.bytes)+")":"Bundle handed to browser downloads ("+formatBytes(out.bytes)+")";})),assembleButton=button("ASSEMBLE PROGRAM",()=>work(async()=>{modeReport=await json(route(selected.session_id)+"/mode/assemble",{method:"POST"});details.textContent=reportLines(selected,modeReport).join("\n");status.textContent="Assembly response received; refresh to check resulting files.";}));
    panel.append(select,refreshButton,format,exportButton,assembleButton,status,details);
    function controls(){select.disabled=busy;refreshButton.disabled=busy;format.disabled=busy;exportButton.disabled=busy||!closed(selected);assembleButton.disabled=busy||!closed(selected)||selected?.mode!=="main_camera";}
    async function work(fn){if(busy)return;busy=true;controls();try{await fn();}catch(e){status.textContent="Failed: "+e.message;}finally{busy=false;controls();}}
    async function inspect(){const generation=++revision;selected=sessions.find(x=>x.session_id===select.value)||null;modeReport=null;details.textContent=selected?reportLines(selected,null).join("\n"):"No take selected";controls();if(!selected)return;const id=selected.session_id;try{const report=await json(route(id)+"/mode");if(generation===revision){modeReport=report;details.textContent=reportLines(selected,report).join("\n");}}catch(e){if(generation===revision)status.textContent="Take metadata available; mode report unavailable: "+e.message;}}
    async function refresh(preferred){await work(async()=>{const previous=preferred||select.value;sessions=ordered(await json("/api/recording/sessions"));select.replaceChildren();for(const session of sessions){const opt=document.createElement("option");opt.value=session.session_id;opt.textContent=session.session_id+" | "+(modes[session.mode]||session.mode||"unknown")+" | "+session.state;select.append(opt);}if(sessions.some(x=>x.session_id===previous))select.value=previous;status.textContent=sessions.length?sessions.length+" server recording(s)":"No recordings returned by server";await inspect();});}
    select.addEventListener("change",inspect);controls();
    return {refresh,select(id){return refresh(id);}};
  }
  return {closed,ordered,filename,formatBytes,reportLines,download,mount};
})();if(typeof module==="object"&&module.exports)module.exports=api;else root.PubCastRecordingLibrary=api;})(globalThis);
