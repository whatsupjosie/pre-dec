/* Shared server recording review and authenticated ZIP export. */
(function(root){const api=(function libraryFactory(){
  "use strict";
  const modes={camcorder:"Normal camcorder",data_only:"Data only",main_camera:"Main camera only"};
  const closed=s=>!!s&&["stopped","archived"].includes(s.state);
  const route=id=>"/api/recording/"+encodeURIComponent(id);
  function ordered(items){if(!Array.isArray(items))throw Error("Invalid recording list");return items.filter(x=>x&&typeof x.session_id==="string"&&x.session_id).sort((a,b)=>Number(b.started_at||0)-Number(a.started_at||0));}
  function filename(id){return (String(id).replace(/[^a-zA-Z0-9_.-]/g,"_").slice(0,120)||"recording")+".zip";}
  function formatBytes(bytes){if(bytes===null||bytes===undefined||bytes==="")return "unknown size";const n=Number(bytes);if(!Number.isFinite(n)||n<0)return "unknown size";return n>=1048576?(n/1048576).toFixed(1)+" MiB":Math.round(n/1024)+" KiB";}
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
  async function json(url,options={}){const response=await fetch(url,{cache:"no-store",signal:AbortSignal.timeout(options.method==="POST"?120000:8000),...options});if(!response.ok)throw await failure(response);return response.json();}
  function appendTail(tail,chunk,limit=65664){
    if(chunk.length>=limit)return chunk.slice(chunk.length-limit);
    const keep=Math.min(tail.length,limit-chunk.length),next=new Uint8Array(keep+chunk.length);
    next.set(tail.subarray(tail.length-keep));next.set(chunk,keep);return next;
  }
  // Verify the end-of-central-directory record, including a ZIP64 locator when present.
  // This is a structural completeness check, not a CRC check of each member.
  function validateZipTail(tail,total){
    if(!Number.isSafeInteger(total)||total<22||tail.length>total||tail.length<22)throw Error("ZIP archive incomplete");
    const view=new DataView(tail.buffer,tail.byteOffset,tail.byteLength),base=total-tail.length;
    for(let i=tail.length-22;i>=Math.max(0,tail.length-65557);i--){
      if(view.getUint32(i,true)!==0x06054b50||i+22+view.getUint16(i+20,true)!==tail.length)continue;
      const disk=view.getUint16(i+4,true),directoryDisk=view.getUint16(i+6,true),entries=view.getUint16(i+8,true),all=view.getUint16(i+10,true),size=view.getUint32(i+12,true),offset=view.getUint32(i+16,true);
      if(disk!==0||directoryDisk!==0||entries!==all)throw Error("Multi-volume ZIP is not supported");
      if(all===65535||size===0xffffffff||offset===0xffffffff){
        if(i<20||view.getUint32(i-20,true)!==0x07064b50||view.getUint32(i-16,true)!==0||view.getUint32(i-4,true)!==1)throw Error("Missing ZIP64 directory locator");
        const recordOffset=view.getBigUint64(i-12,true),relative=recordOffset-BigInt(base);
        if(relative<0n||relative>BigInt(i-76))throw Error("Invalid or unsupported ZIP64 directory extent");
        const z=Number(relative);
        if(view.getUint32(z,true)!==0x06064b50||view.getBigUint64(z+4,true)<44n||recordOffset+12n+view.getBigUint64(z+4,true)!==BigInt(base+i-20))throw Error("Invalid ZIP64 directory record");
        if(view.getUint32(z+16,true)!==0||view.getUint32(z+20,true)!==0||view.getBigUint64(z+24,true)!==view.getBigUint64(z+32,true))throw Error("Multi-volume ZIP64 is not supported");
        const count=view.getBigUint64(z+32,true),directorySize=view.getBigUint64(z+40,true),directoryOffset=view.getBigUint64(z+48,true);
        if(count===0n||directorySize<46n*count||directoryOffset+directorySize!==recordOffset)throw Error("Invalid ZIP64 central directory");
      }else if(all===0||size<46*all||offset+size!==base+i)throw Error("Empty or invalid ZIP central directory");
      return true;
    }
    throw Error("ZIP end-of-directory record missing; export incomplete");
  }
  async function download(id,format,progress=()=>{},options={}){
    if(!id)throw Error("Select a recording");
    if(!["mp4","webm","wav","mov"].includes(format))throw Error("Unsupported export format");
    const signal=options.signal;
    if(signal?.aborted)return {canceled:true};
    const name=filename(id);
    let writable=null,reader=null,blobURL=null;
    const maxBuffer=256*1024*1024;
    // Ask for a destination during the user gesture, before awaiting server work.
    if(typeof window.showSaveFilePicker==="function"){
      try{const handle=await window.showSaveFilePicker({suggestedName:name,types:[{description:"Recording bundle",accept:{"application/zip":[".zip"]}}]});writable=await handle.createWritable();}
      catch(error){if(error.name==="AbortError")return {canceled:true};if(error.name!=="SecurityError"&&error.name!=="NotSupportedError")throw error;}
    }
    try{
      if(signal?.aborted){await writable?.abort();return {canceled:true};}
      progress("Preparing server export...");
      const response=await fetch(route(id)+"/export",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({format}),signal});
      if(!response.ok)throw await failure(response);
      if(!/^application\/(?:zip|x-zip-compressed)(?:;|$)/i.test(response.headers.get("content-type")||""))throw Error("Server did not return a ZIP bundle");
      if(!response.body?.getReader)throw Error("Streaming download is unavailable in this browser");
      const raw=response.headers.get("content-length"),encoding=response.headers.get("content-encoding"),expected=raw===null||encoding&&encoding!=="identity"?null:Number(raw);
      if(expected!==null&&(!Number.isSafeInteger(expected)||expected<0))throw Error("Invalid export length");
      if(!writable&&expected!==null&&expected>maxBuffer)throw Error("Bundle exceeds safe in-memory download size; use a desktop browser with streaming Save As");
      reader=response.body.getReader();
      let total=0,chunks=[],prefix=[],tail=new Uint8Array(0),verified=false,lastReport=0;
      for(;;){
        if(signal?.aborted)throw Error("Export canceled");
        const {value,done}=await reader.read();if(done)break;
        if(!value?.length)continue;total+=value.length;
        if(!writable&&total>maxBuffer)throw Error("Bundle exceeds safe in-memory download size; use streaming Save As");
        if(!verified){
          for(let i=0;i<value.length&&prefix.length<4;i++)prefix.push(value[i]);
          if(prefix.length===4){if(prefix[0]!==80||prefix[1]!==75||!((prefix[2]===3&&prefix[3]===4)||(prefix[2]===5&&prefix[3]===6)))throw Error("Invalid ZIP signature");verified=true;}
        }
        tail=appendTail(tail,value);
        if(writable)await writable.write(value);else chunks.push(value);
        if(Date.now()-lastReport>250){progress("Received "+formatBytes(total)+(expected!==null?" / "+formatBytes(expected):""));lastReport=Date.now();}
      }
      if(signal?.aborted)throw Error("Export canceled");
      if(!verified||expected!==null&&total!==expected)throw Error("Incomplete or invalid export");
      validateZipTail(tail,total);
      if(writable){await writable.close();writable=null;return {saved:true,bytes:total};}
      blobURL=URL.createObjectURL(new Blob(chunks,{type:"application/zip"}));
      const anchor=document.createElement("a");anchor.href=blobURL;anchor.download=name;document.body.append(anchor);anchor.click();anchor.remove();
      const release=blobURL;setTimeout(()=>URL.revokeObjectURL(release),60000);blobURL=null;
      return {saved:false,bytes:total};
    }catch(error){try{await reader?.cancel();}catch(_){}try{await writable?.abort();}catch(_){}if(signal?.aborted||error.name==="AbortError")return {canceled:true};throw error;}
    finally{try{reader?.releaseLock();}catch(_){}if(blobURL)URL.revokeObjectURL(blobURL);}
  }
  function mount(panel){
    let sessions=[],selected=null,modeReport=null,busy=false,revision=0,exportController=null;
    const select=document.createElement("select");select.setAttribute("aria-label","Recording session");select.style.maxWidth="100%";
    const status=document.createElement("output");status.setAttribute("role","status");status.style.display="block";
    const details=document.createElement("pre");details.style.cssText="white-space:pre-wrap;overflow-wrap:anywhere;max-height:240px;overflow:auto;font-size:11px";
    const format=document.createElement("select");format.setAttribute("aria-label","Export format");for(const type of ["mp4","webm","wav","mov"]){const opt=document.createElement("option");opt.value=type;opt.textContent=type.toUpperCase()+" bundle";format.append(opt);}
    function button(label,fn){const b=document.createElement("button");b.type="button";b.textContent=label;b.addEventListener("click",fn);return b;}
    const refreshButton=button("REFRESH TAKES",()=>refresh()),exportButton=button("EXPORT ZIP",()=>work(async()=>{exportController=new AbortController();controls();try{const out=await download(selected.session_id,format.value,s=>status.textContent=s,{signal:exportController.signal});status.textContent=out.canceled?"Export canceled":out.saved?"Bundle saved ("+formatBytes(out.bytes)+")":"Bundle handed to browser downloads ("+formatBytes(out.bytes)+")";}finally{exportController=null;}})),assembleButton=button("ASSEMBLE PROGRAM",()=>work(async()=>{modeReport=await json(route(selected.session_id)+"/mode/assemble",{method:"POST"});details.textContent=reportLines(selected,modeReport).join("\n");status.textContent="Assembly response received; refresh to check resulting files.";}));
    const cancelButton=button("CANCEL EXPORT",()=>exportController?.abort());
    panel.append(select,refreshButton,format,exportButton,cancelButton,assembleButton,status,details);
    function controls(){cancelButton.hidden=!exportController;select.disabled=busy;refreshButton.disabled=busy;format.disabled=busy;exportButton.disabled=busy||!closed(selected);assembleButton.disabled=busy||!closed(selected)||selected?.mode!=="main_camera";}
    async function work(fn){if(busy)return;busy=true;controls();try{await fn();}catch(e){status.textContent="Failed: "+e.message;}finally{busy=false;controls();}}
    async function inspect(){const generation=++revision;selected=sessions.find(x=>x.session_id===select.value)||null;modeReport=null;details.textContent=selected?reportLines(selected,null).join("\n"):"No take selected";controls();if(!selected)return;const id=selected.session_id;try{const report=await json(route(id)+"/mode");if(generation===revision){modeReport=report;details.textContent=reportLines(selected,report).join("\n");}}catch(e){if(generation===revision)status.textContent="Take metadata available; mode report unavailable: "+e.message;}}
    async function refresh(preferred){await work(async()=>{const previous=preferred||select.value;revision++;selected=null;modeReport=null;details.textContent="Refreshing takes...";controls();sessions=ordered(await json("/api/recording/sessions"));select.replaceChildren();for(const session of sessions){const opt=document.createElement("option");opt.value=session.session_id;opt.textContent=session.session_id+" | "+(modes[session.mode]||session.mode||"unknown")+" | "+session.state;select.append(opt);}if(sessions.some(x=>x.session_id===previous))select.value=previous;status.textContent=sessions.length?sessions.length+" server recording(s)":"No recordings returned by server";await inspect();});}
    select.addEventListener("change",inspect);controls();
    return {refresh,select(id){return refresh(id);}};
  }
  return {closed,ordered,filename,formatBytes,reportLines,appendTail,validateZipTail,download,mount};
})();if(typeof module==="object"&&module.exports)module.exports=api;else root.PubCastRecordingLibrary=api;})(globalThis);
