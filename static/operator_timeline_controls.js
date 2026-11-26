/* Operator timeline transport. Reads the shared timeline player; never fabricates state. */
(function(){
"use strict";
async function request(path,body){
 const options={cache:"no-store",credentials:"same-origin"};
 if(body!==undefined)Object.assign(options,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
 const response=await fetch("/api/timeline/"+path,options);
 const data=await response.json().catch(()=>null);
 if(!response.ok)throw Error(typeof data?.detail==="string"?data.detail:"HTTP "+response.status);
 if(!data)throw Error("Missing timeline response");
 return data;
}
function mount(panel){
 let state=null,busy=false,polling=false,active=true;
 const select=document.createElement("select");select.setAttribute("aria-label","Timeline");
 const first=document.createElement("option");first.value="";first.textContent="Select timeline";select.append(first);
 const position=document.createElement("input");position.type="number";position.min="0";position.step="0.1";position.placeholder="Seconds";position.setAttribute("aria-label","Seek to seconds");
 const status=document.createElement("output");status.style.display="block";status.setAttribute("role","status");status.textContent="Timeline status unavailable";
 const feedback=document.createElement("output");feedback.style.display="block";feedback.setAttribute("role","status");
 const buttons={};
 function button(label,action){const b=document.createElement("button");b.type="button";b.textContent=label;buttons[action]=b;b.addEventListener("click",()=>command(action));return b;}
 panel.append(select,button("LOAD","load"),button("PLAY","play"),button("PAUSE","pause"),button("RESUME","resume"),button("STOP","stop"),position,button("SEEK","seek"),status,feedback);
 function update(){
   const valid=!!state, running=state?.state==="running",paused=state?.state==="paused",loaded=!!state?.timeline_name;
   buttons.load.disabled=busy||!select.value||!valid||running||paused;
   buttons.play.disabled=busy||!valid||!loaded||running||paused;
   buttons.pause.disabled=busy||!running;
   buttons.resume.disabled=busy||!paused;
   buttons.stop.disabled=busy||!valid||(!running&&!paused);
   const duration=Number(state?.duration);
   position.disabled=busy||!valid||!loaded;position.max=Number.isFinite(duration)?String(duration):"";
   buttons.seek.disabled=position.disabled;
   select.disabled=busy;
 }
 async function refresh(){
   if(polling||!active)return;
   polling=true;
   try{
     const next=await request("status");
     if(!active)return;
     if(typeof next.state!=="string")throw Error("Invalid timeline state");
     state=next;
     status.textContent=(next.timeline_name||"No timeline")+" | "+next.state.toUpperCase()+" | "+Number(next.elapsed||0).toFixed(1)+" s"+(next.duration!=null?" / "+Number(next.duration).toFixed(1)+" s":"");
   }catch(e){state=null;status.textContent="Timeline unavailable: "+e.message;}
   finally{polling=false;update();}
 }
 async function loadList(){
   try{
     const data=await request("list");
     if(!Array.isArray(data.timelines))throw Error("Invalid timeline list");
     for(const item of data.timelines){if(!item.filename)continue;const o=document.createElement("option");o.value=item.filename;o.textContent=item.name||item.filename;select.append(o);}
   }catch(e){feedback.textContent="Timeline list unavailable: "+e.message;}
   update();
 }
 async function command(action){
   if(busy||buttons[action].disabled)return;
   let path=action,body={};
   if(action==="load")body={name:select.value};
   if(action==="seek"){
     const seconds=Number(position.value),duration=Number(state?.duration);
     if(!position.value.trim()||!Number.isFinite(seconds)||seconds<0||!Number.isFinite(duration)||seconds>duration){feedback.textContent="Enter a valid seek position within the timeline.";return;}
     path+="?time="+encodeURIComponent(seconds);
   }
   busy=true;update();feedback.textContent="Sending "+action+"...";
   try{await request(path,body);feedback.textContent=action.toUpperCase()+" acknowledged; checking shared state.";}
   catch(e){feedback.textContent=action.toUpperCase()+" failed: "+e.message;}
   finally{busy=false;await refresh();update();}
 }
 select.addEventListener("change",update);
 update();loadList();refresh();
 const timer=setInterval(refresh,1000);
 window.addEventListener("pagehide",()=>{active=false;clearInterval(timer);},{once:true});
}
document.querySelectorAll("[data-operator-timeline]").forEach(mount);
})();
