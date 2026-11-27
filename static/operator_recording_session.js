/* Server-reconciled operator take ownership; never adopt another station automatically. */
(function(root){const api=(function factory(){
 "use strict";
 const activeStates=new Set(["requested","countdown","active","paused"]),closedStates=new Set(["stopped","archived"]);
 function classify(s,id){return s?.session_id===id&&(activeStates.has(s.state)||closedStates.has(s.state))?s.state:"unknown";}
 function create({key,adapter,prepare,onState,onError=()=>{},fetcher=globalThis.fetch?.bind(globalThis),storage,makeId=()=>key+"_"+crypto.randomUUID(),timeout=ms=>globalThis.AbortSignal?.timeout?.(ms)}){
   let id="",last="",state="idle",record=null,busy=false,polling=false,verified=false,disposed=false,revision=0,missing=false,panicEpoch=0;
   try{storage=storage||globalThis.sessionStorage;id=storage?.getItem(key)||"";last=storage?.getItem(key+"_last")||"";if(id)state="unknown";}catch(_){}
   function save(value){id=value;try{if(value)storage?.setItem(key,value);else storage?.removeItem(key);}catch(e){onError("Session persistence unavailable: "+e.message);}}
   function remember(value){last=value;try{storage?.setItem(key+"_last",value);}catch(_){}}
   function view(){return {id,last,state,record,busy,verified,missing,live:activeStates.has(state),closed:closedStates.has(state),locked:busy||!!id,canStop:!!id&&verified&&activeStates.has(state)&&!busy,canPause:!!id&&verified&&["active","paused"].includes(state)&&!busy};}
   function publish(){if(!disposed)onState(view());}
   function unknown(message){state="unknown";verified=false;missing=false;onError(message);publish();}
   function accept(result,expected){
     const next=classify(result,expected);if(next==="unknown")throw Error("Server did not confirm the named recording state");
     record=result;state=next;verified=true;missing=false;
     if(closedStates.has(next)){remember(expected);save("");}publish();
   }
   async function list(){
     const response=await fetcher("/api/recording/sessions",{cache:"no-store",signal:timeout(5000)});
     if(!response.ok)throw Error("Recording status HTTP "+response.status);
     const data=await response.json();if(!Array.isArray(data))throw Error("Invalid recording list");return data;
   }
   async function refresh(){
     if(disposed||busy||polling||!id)return;polling=true;const rev=revision,expected=id;
     try{
       const rows=await list();if(disposed||rev!==revision||id!==expected)return;
       const match=rows.find(x=>x?.session_id===expected);
       if(!match){state="unknown";verified=false;missing=true;publish();return;}
       accept(match,expected);
     }catch(e){if(!disposed&&rev===revision&&id===expected)unknown(e.message);}
     finally{polling=false;}
   }
   async function action(fn){
     if(disposed||busy)return false;busy=true;revision++;const epoch=panicEpoch;publish();
     try{return await fn(epoch);}
     catch(e){if(id)unknown(e.message);else onError(e.message);return false;}
     finally{busy=false;publish();if(id)await refresh();}
   }
   function checkPanic(epoch){if(epoch!==panicEpoch)throw Error("PANIC interrupted the command; check take state");}
   async function start(){
     if(id)return false;
     return action(async epoch=>{
       if(!adapter)throw Error("Studio action adapter unavailable");
       const payload=await prepare();checkPanic(epoch);
       const expected=makeId();save(expected);record=null;state="unknown";verified=false;publish();
       const response=await adapter.executeConfirmed("recording.start",{...payload,session_id:expected},{spec:{safety:"confirm",label:"Start recording ("+payload.mode+")"}});
       if(response?.canceled){if(id===expected){save("");state="idle";publish();}return false;}
       checkPanic(epoch);
       if(response?.ok!==true)throw Error("Start not acknowledged; check recording status before retrying");
       accept(response.result,expected);return true;
     });
   }
   async function stop(){
     if(!view().canStop)return false;
     return action(async epoch=>{
       const expected=id;
       const response=await adapter.executeConfirmed("recording.stop",{session_id:expected},{spec:{safety:"confirm",label:"Stop recording"}});
       if(response?.canceled)return false;
       checkPanic(epoch);
       if(response?.ok!==true||!closedStates.has(classify(response.result,expected)))throw Error("Stop not confirmed; retained session ID");
       accept(response.result,expected);return true;
     });
   }
   async function pause(){
     if(!view().canPause)return false;
     return action(async epoch=>{
       const expected=id,desired=state!=="paused";
       const response=await fetcher("/api/recording/"+encodeURIComponent(expected)+"/pause",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({paused:desired})});
       const data=await response.json().catch(()=>null);checkPanic(epoch);
       if(!response.ok)throw Error(typeof data?.detail==="string"?data.detail:"Pause HTTP "+response.status);
       if(classify(data,expected)!==(desired?"paused":"active"))throw Error("Pause state not confirmed");
       accept(data,expected);return true;
     });
   }
   async function releaseMissing(confirm){
     if(!id||!missing||busy)return false;
     return action(async()=>{
       const expected=id;
       if((await list()).some(x=>x?.session_id===expected))throw Error("Take exists; local claim retained");
       if(!await confirm(expected))return false;
       if((await list()).some(x=>x?.session_id===expected))throw Error("Take appeared during confirmation; local claim retained");
       save("");state="idle";record=null;verified=true;missing=false;return true;
     });
   }
   function panicResult(result){panicEpoch++;revision++;if(id&&result?.sessions_stopped?.includes(id)){remember(id);save("");state="stopped";verified=true;missing=false;publish();}else if(id){unknown("PANIC outcome for this take unconfirmed");refresh();}}
   function dispose(){disposed=true;revision++;}
   return {view,refresh,start,stop,pause,releaseMissing,panicResult,dispose,publish};
 }
 return {classify,create};
})();if(typeof module==="object"&&module.exports)module.exports=api;else root.PubCastRecordingSession=api;})(globalThis);
