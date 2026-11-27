/* Operator-side recording options. The server remains authoritative. */
(function(root){const api=(function factory(){
  "use strict";
  const labels={camcorder:"Normal camcorder",data_only:"Data only",main_camera:"Main camera only"};
  function buildPayload(snapshot,mode,selected){
    if(!snapshot || !Array.isArray(snapshot.sources)) throw Error("Camera registry unavailable");
    if(!Object.prototype.hasOwnProperty.call(labels,mode)) throw Error("Unknown recording mode");
    const known=new Set(snapshot.sources.map(s=>String(s.id)));
    const sources=[...new Set(selected.map(String))];
    if(!sources.length) throw Error("Select at least one source");
    if(sources.some(id=>!known.has(id))) throw Error("A selected camera is no longer registered");
    if(mode==="main_camera"&&(!snapshot.program||!sources.includes(String(snapshot.program)))) throw Error("Select the current Program camera for main-camera recording");
    return {mode,sources,profile_id:"broadcast_mp4",record_data:true,countdown_seconds:0};
  }
  function errorText(body,status){
    const detail=body?.detail;
    return typeof detail==="string"?detail:Array.isArray(detail)?detail.map(x=>x?.msg||String(x)).join("; "):`HTTP ${status}`;
  }
  async function request(path,body){
    const options={cache:"no-store",signal:AbortSignal.timeout(8000)};
    if(body!==undefined)Object.assign(options,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
    const res=await fetch(path,options);
    const data=await res.json().catch(()=>null);
    if(!res.ok)throw Error(errorText(data,res.status));
    if(!data)throw Error("Missing server response");
    return data;
  }
  function mount(id){
    const panel=document.getElementById(id);
    if(!panel)throw Error("Missing recording options mount");
    const mode=document.createElement("select"),modeLabel=document.createElement("label");
    mode.setAttribute("aria-label","Recording mode");
    modeLabel.textContent="Recording mode ";
    for(const [value,label] of Object.entries(labels)){const opt=document.createElement("option");opt.value=value;opt.textContent=label;mode.append(opt);}
    modeLabel.append(mode);
    const sourceList=document.createElement("div"),legend=document.createElement("div");
    legend.textContent="Recording sources (select all required angles and audio sources)";
    const status=document.createElement("output");status.setAttribute("role","status");status.style.display="block";
    const check=document.createElement("button");check.type="button";check.textContent="CHECK READINESS";
    panel.append(modeLabel,legend,sourceList,check,status);
    let snapshot=null,selection=new Set(),explicit=false,signature="",locked=false,checking=false,revision=0;
    function setSnapshot(next){
      if(!next||!Array.isArray(next.sources))return;
      snapshot=next;
      const key=JSON.stringify([next.program,next.sources.map(s=>[s.id,s.name])]);
      if(key===signature)return;
      signature=key;revision++;status.textContent="Registry changed; readiness must be rechecked.";
      if(!explicit)selection=new Set(next.program?[String(next.program)]:[]);
      sourceList.replaceChildren();
      for(const src of next.sources){
        const label=document.createElement("label"),input=document.createElement("input"),sid=String(src.id);
        label.style.display="block";input.type="checkbox";input.checked=selection.has(sid);
        input.addEventListener("change",()=>{explicit=true;revision++;input.checked?selection.add(sid):selection.delete(sid);status.textContent="Selection changed; check readiness again.";});
        label.append(input,document.createTextNode(" "+(src.name||sid)+(sid===String(next.program)?" (Program)":"")));
        sourceList.append(label);
      }
      // Keep a stale explicit selection visible rather than silently removing a requested angle.
      const known=new Set(next.sources.map(s=>String(s.id)));
      for(const sid of selection)if(!known.has(sid)){
        const label=document.createElement("label"),input=document.createElement("input");
        label.style.display="block";input.type="checkbox";input.checked=true;
        input.addEventListener("change",()=>{if(!input.checked){selection.delete(sid);revision++;label.remove();status.textContent="Selection changed; check readiness again.";}});
        label.append(input,document.createTextNode(" "+sid+" (unavailable; deselect to continue)"));sourceList.append(label);
      }
      setLocked(locked);
    }
    function setLocked(value){locked=!!value;const disabled=locked||checking;mode.disabled=disabled;check.disabled=disabled;sourceList.querySelectorAll("input").forEach(x=>x.disabled=disabled);}
    async function prepare(){
      if(checking)throw Error("Readiness check already in progress");checking=true;setLocked(locked);
      try{
      setSnapshot(await request("/api/switcher/state"));
      const payload=buildPayload(snapshot,mode.value,[...selection]);const checkedRevision=revision;
      status.textContent="Checking selected sources and recording profile...";
      const report=await request("/api/recording/preflight",{sources:payload.sources,profile_id:payload.profile_id,host_override:false});
      if(checkedRevision!==revision)throw Error("Camera registry or selection changed during readiness check");
      if(typeof report.ready!=="boolean"||!Array.isArray(report.issues))throw Error("Invalid readiness report");
      // Existing preflight is video-oriented. Data-only intentionally writes no pictures.
      const issues=report.issues.filter(x=>!(payload.mode==="data_only"&&x.code==="source_not_recordable"));
      if(issues.length||(!report.ready&&report.issues.length===0))throw Error(issues.map(x=>x.message||x.code).join("; ")||"Recording preflight not ready");
      const warnings=(report.warnings||[]).map(x=>x.message||x.code).filter(Boolean);
      status.textContent=(report.ready?"Source/profile checks passed; actual capture must still be confirmed.":"Data-only: video readiness not confirmed; server must validate the data recording.")+(warnings.length?" Warnings: "+warnings.join("; "):"");
      return payload;
      }finally{checking=false;setLocked(locked);}
    }
    mode.addEventListener("change",()=>{revision++;status.textContent="Mode changed; check readiness again.";});
    check.addEventListener("click",async()=>{check.disabled=true;try{await prepare();}catch(e){status.textContent="Not ready: "+e.message;}finally{setLocked(locked);}});
    status.textContent="Waiting for verified camera registry.";
    return {setSnapshot,setLocked,prepare};
  }
  return {labels,buildPayload,errorText,mount};
})();if(typeof module==="object"&&module.exports)module.exports=api;else root.PubCastRecordingControls=api;})(typeof globalThis!=="undefined"?globalThis:this);
