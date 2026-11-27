/* Operator timeline transport. Reads the shared timeline player; never fabricates state. */
(function(){
"use strict";
async function request(path,body){
 const options={cache:"no-store",credentials:"same-origin",signal:AbortSignal.timeout(body===undefined?4000:15000)};
 if(body!==undefined)Object.assign(options,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
 const response=await fetch("/api/timeline/"+path,options);
 const data=await response.json().catch(()=>null);
 if(!response.ok)throw Error(typeof data?.detail==="string"?data.detail:"HTTP "+response.status);
 if(!data||typeof data!=="object"||Array.isArray(data))throw Error("Invalid timeline response");
 return data;
}
function mount(panel){
 let state=null,busy=false,polling=null,active=true,revision=0;
 const select=document.createElement("select");select.setAttribute("aria-label","Timeline");
 const first=document.createElement("option");first.value="";first.textContent="Select timeline";select.append(first);
 const position=document.createElement("input");position.type="number";position.min="0";position.step="0.1";position.placeholder="Seconds";position.setAttribute("aria-label","Seek to seconds");
 const status=document.createElement("output");status.style.display="block";status.setAttribute("role","status");status.textContent="Timeline status unavailable";
 const feedback=document.createElement("output");feedback.style.display="block";feedback.setAttribute("role","status");
 const buttons={};
 function button(label,action){const b=document.createElement("button");b.type="button";b.textContent=label;buttons[action]=b;b.addEventListener("click",()=>command(action));return b;}
 panel.append(select,button("REFRESH LIST","list"),button("LOAD","load"),button("PLAY","play"),button("PAUSE","pause"),button("RESUME","resume"),button("STOP","stop"),position,button("SEEK","seek"),status,feedback);
 function update(){
   buttons.list.disabled=busy;
   const valid=!!state, running=state?.state==="running",paused=state?.state==="paused",loaded=!!state?.timeline_name;
   buttons.load.disabled=busy||!select.value||!valid||running||paused;
   buttons.play.disabled=busy||!valid||!loaded||running||paused;
   buttons.pause.disabled=busy||!running;
   buttons.resume.disabled=busy||!paused;
   buttons.stop.disabled=busy||!valid||(!running&&!paused);
   const duration=state?.duration==null?NaN:Number(state.duration);
   position.disabled=busy||!valid||!loaded||!Number.isFinite(duration);position.max=Number.isFinite(duration)?String(duration):"";
   buttons.seek.disabled=position.disabled;
   select.disabled=busy;
 }
 async function refresh(){
   if(!active||busy)return;
   if(polling)return polling;
   const current=revision;
   polling=(async()=>{
     try{
       const next=await request("status");
       if(!active||current!==revision)return;
       if(!["idle","running","paused","complete","failed"].includes(next.state)||!Number.isFinite(next.elapsed)||next.elapsed<0)throw Error("Invalid timeline state");
       state=next;
       status.textContent=(next.timeline_name||"No timeline")+" | "+next.state.toUpperCase()+" | "+next.elapsed.toFixed(1)+" s"+(Number.isFinite(next.duration)?" / "+next.duration.toFixed(1)+" s":"");
     }catch(e){if(active&&current===revision){state=null;status.textContent="Timeline unavailable: "+e.message;}}
     finally{polling=null;update();}
   })();
   return polling;
 }
 async function loadList(){
   try{
     const data=await request("list");
     if(!Array.isArray(data.timelines))throw Error("Invalid timeline list");
     const previous=select.value;select.replaceChildren(first);
     const seen=new Set();
     for(const item of data.timelines){if(typeof item?.filename!=="string"||!item.filename||seen.has(item.filename))continue;seen.add(item.filename);const o=document.createElement("option");o.value=item.filename;o.textContent=item.name||item.filename;select.append(o);}if(seen.has(previous))select.value=previous;
   }catch(e){feedback.textContent="Timeline list unavailable: "+e.message;}
   update();
 }
 async function command(action){
   if(busy||buttons[action].disabled)return;
   if(action==="list"){busy=true;update();try{await loadList();}finally{busy=false;update();}return;}
   let path=action,body={};
   if(action==="load")body={name:select.value};
   if(action==="seek"){
     const seconds=Number(position.value),duration=Number(state?.duration);
     if(!position.value.trim()||!Number.isFinite(seconds)||seconds<0||!Number.isFinite(duration)||seconds>duration){feedback.textContent="Enter a valid seek position within the timeline.";return;}
     path+="?time="+encodeURIComponent(seconds);
   }
   busy=true;revision++;state=null;update();status.textContent="Checking timeline after command";feedback.textContent="Sending "+action+"...";
   window.dispatchEvent(new Event("pubcast:timeline-changing"));
   try{await request(path,body);feedback.textContent=action.toUpperCase()+" acknowledged; checking shared state.";}
   catch(e){feedback.textContent=action.toUpperCase()+" failed: "+e.message;}
   finally{if(polling)await polling;busy=false;await refresh();update();window.dispatchEvent(new Event("pubcast:timeline-changed"));}
 }
 select.addEventListener("change",update);
 update();loadList();refresh();
 let timer=setInterval(refresh,1000);
 window.addEventListener("pagehide",()=>{active=false;revision++;clearInterval(timer);});
 window.addEventListener("pageshow",()=>{if(active)return;active=true;refresh();timer=setInterval(refresh,1000);});
}
document.querySelectorAll("[data-operator-timeline]").forEach(mount);
})();
