/* Server-reconciled take ownership, cumulative capture evidence and identity checks. */
(function(root){const api=(function factory(){
 "use strict";
 const activeStates=new Set(["requested","countdown","active","paused"]),closedStates=new Set(["stopped","archived"]);
 const array=v=>Array.isArray(v)?v:[];
 function classify(s,id){return s?.session_id===id&&(activeStates.has(s.state)||closedStates.has(s.state))?s.state:"unknown";}
 function randomId(key){
   const bytes=new Uint8Array(16);globalThis.crypto.getRandomValues(bytes);
   return key+"_"+Array.from(bytes,n=>n.toString(16).padStart(2,"0")).join("");
 }
 function mergeRecord(previous,next){
   const same=previous?.session_id===next?.session_id?previous:null;
   const errors=new Map();
   for(const item of [...array(same?.capture_errors),...array(same?.pause_problems),...array(next?.capture_errors),...array(next?.pause_problems)]){
     if(!item||typeof item!=="object")continue;
     const source_id=String(item.source_id||item.source||"a source"),error=String(item.error||item.message||"Capture problem"),phase=String(item.phase||"");
     errors.set(JSON.stringify([source_id,error,phase]),{...item,source_id,error,phase});
   }
   const reports=new Map();
   for(const item of [...array(same?.capture_report),...array(next?.capture_report)]){
     if(!item||typeof item!=="object")continue;
     const source_id=String(item.source_id||"a source"),old=reports.get(source_id);
     reports.set(source_id,{...old,...item,source_id,warnings:[...new Set([...array(old?.warnings),...array(item.warnings)].map(String))]});
   }
   return {...same,...next,capture_errors:[...errors.values()],capture_report:[...reports.values()]};
 }
 function create({key,adapter,prepare,onState,onError=()=>{},fetcher=globalThis.fetch?.bind(globalThis),storage,makeId=()=>randomId(key),timeout=ms=>globalThis.AbortSignal?.timeout?.(ms),identity=()=>{const user=globalThis.ReachAuth?.getUser?.();return String(user?.user_id||user?.username||"");},now=()=>Date.now()}){
   let id="",last="",state="idle",record=null,busy=false,polling=false,verified=false,disposed=false,revision=0,missing=false,panicEpoch=0,panicPending=false,error="",identityBlocked=false,submittedAt=0,lastVerified=false;
   const principal=identity(),scope=key+"_owner";
   try{
     storage=storage||globalThis.sessionStorage;
     id=storage?.getItem(key)||"";last=storage?.getItem(key+"_last")||"";
     submittedAt=Number(storage?.getItem(key+"_submitted")||0);
     const owner=storage?.getItem(scope);
     if((id||last)&&owner!==null&&owner!==undefined&&owner!==principal)identityBlocked=true;
     if(id)state="unknown";
   }catch(e){error="Session storage unavailable: "+e.message;}
   function ensureIdentity(){
     if(identityBlocked||identity()!==principal){identityBlocked=true;throw Error("Sign-in changed. Return to the original operator before recovering or controlling this take.");}
   }
   function ensureOwner(result){
     ensureIdentity();
     // The server binds recording.operator to the authenticated user ID.
     if(principal&&result?.operator&&String(result.operator)!==principal)throw Error("Take belongs to a different operator; no control granted.");
   }
   function save(value){
     if(value){
       if(!storage)throw Error("Session persistence unavailable; cannot safely start recording");
       storage.setItem(scope,principal);
       storage.setItem(key,value); // persist before network dispatch
       id=value;
     }else{
       // If removal fails, leave the exact claim in memory, rather than enable a duplicate start.
       storage?.removeItem(key);id="";submittedAt=0;
       try{storage?.removeItem(key+"_submitted");}catch(_){}
     }
   }
   function remember(value){last=value;lastVerified=true;try{storage?.setItem(scope,principal);storage?.setItem(key+"_last",value);}catch(_){}}
   function view(){
     if(identity()!==principal)identityBlocked=true;
     return {id,last,state,record,busy,verified,missing,error,lastVerified,identityBlocked,
       live:activeStates.has(state),closed:closedStates.has(state),locked:busy||!!id||panicPending||identityBlocked,
       canStop:!!id&&verified&&activeStates.has(state)&&!busy&&!panicPending&&!identityBlocked,
       canPause:!!id&&verified&&["active","paused"].includes(state)&&!busy&&!panicPending&&!identityBlocked,
       canRelease:!!id&&missing&&!busy&&!panicPending&&!identityBlocked,panicPending};
   }
   function publish(){if(!disposed)onState(view());}
   function report(message){error=String(message||"");if(error)onError(error);}
   function unknown(message){state="unknown";verified=false;missing=false;report(message);publish();}
   function accept(result,expected){
     const next=classify(result,expected);if(next==="unknown")throw Error("Server did not confirm the named recording state");
     ensureOwner(result);
     record=mergeRecord(record,result);state=next;verified=true;missing=false;error="";
     if(closedStates.has(next)){remember(expected);if(id===expected)save("");}
     publish();
   }
   async function list(){
     ensureIdentity();
     const response=await fetcher("/api/recording/sessions",{cache:"no-store",signal:timeout(5000)});
     if(!response.ok)throw Error("Recording status HTTP "+response.status);
     const data=await response.json();if(!Array.isArray(data))throw Error("Invalid recording list");ensureIdentity();return data;
   }
   async function refresh(){
     if(disposed||busy||polling||panicPending||identityBlocked||(!id&&(!last||lastVerified)))return;
     polling=true;const rev=revision,expected=id||last,wasActive=!!id;
     try{
       const rows=await list();if(disposed||rev!==revision||(id||last)!==expected)return;
       const match=rows.find(x=>x?.session_id===expected);
       if(!match){
         if(wasActive){state="unknown";verified=false;missing=true;report("Take not present in the server list. A lost start may still be pending.");}
         else{lastVerified=false;report("Previous take not present in the server list.");}
         publish();return;
       }
       if(!wasActive&&!closedStates.has(classify(match,expected))){report("Previously closed take is not confirmed closed; use the recording library to review.");lastVerified=false;publish();return;}
       accept(match,expected);
     }catch(e){if(!disposed&&rev===revision&&(id||last)===expected){if(wasActive)unknown(e.message);else{lastVerified=false;report(e.message);publish();}}}
     finally{polling=false;}
   }
   async function action(fn){
     if(disposed||busy||panicPending||identityBlocked)return false;
     busy=true;revision++;const epoch=panicEpoch;error="";publish();
     try{ensureIdentity();return await fn(epoch);}
     catch(e){if(id)unknown(e.message);else report(e.message);return false;}
     finally{busy=false;publish();if(id||last&&!lastVerified)await refresh();}
   }
   function checkPanic(epoch){ensureIdentity();if(epoch!==panicEpoch||panicPending)throw Error("PANIC interrupted the command; check take state");}
   async function start(){
     if(id)return false;
     return action(async epoch=>{
       if(!adapter)throw Error("Studio action adapter unavailable");
       const payload=await prepare();checkPanic(epoch);
       const expected=makeId();save(expected);record=null;state="unknown";verified=false;missing=false;publish();
       const response=await adapter.executeConfirmed("recording.start",{...payload,session_id:expected},{spec:{safety:"confirm",label:"Start recording ("+payload.mode+")"},beforeExecute:async()=>{
         checkPanic(epoch);const current=await prepare();checkPanic(epoch);
         if(JSON.stringify(current)!==JSON.stringify(payload))throw Error("Recording setup changed during confirmation; review the sources again");
         submittedAt=now();storage.setItem(key+"_submitted",String(submittedAt));
       }});
       if(response?.canceled||response?.notSent){if(id===expected){save("");state="idle";verified=false;lastVerified=false;}if(response?.reason)report(response.reason);publish();return false;}
       checkPanic(epoch);
       if(response?.ok!==true)throw Error("Start not acknowledged; check recording status before retrying");
       accept(response.result,expected);return true;
     });
   }
   async function stop(){
     if(!view().canStop)return false;
     return action(async epoch=>{
       const expected=id;
       const response=await adapter.executeConfirmed("recording.stop",{session_id:expected},{spec:{safety:"confirm",label:"Stop recording"},beforeExecute:()=>checkPanic(epoch)});
       if(response?.canceled||response?.notSent){if(response?.reason)report(response.reason);return false;}
       checkPanic(epoch);
       if(response?.ok!==true||!closedStates.has(classify(response.result,expected)))throw Error("Stop not confirmed; retained session ID");
       accept(response.result,expected);return true;
     });
   }
   async function pause(){
     if(!view().canPause)return false;
     return action(async epoch=>{
       const expected=id,desired=state!=="paused";
       const response=await fetcher("/api/recording/"+encodeURIComponent(expected)+"/pause",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({paused:desired}),signal:timeout(120000)});
       const data=await response.json().catch(()=>null);checkPanic(epoch);
       if(!response.ok)throw Error(typeof data?.detail==="string"?data.detail:"Pause HTTP "+response.status);
       if(classify(data,expected)!==(desired?"paused":"active"))throw Error("Pause state not confirmed");
       accept(data,expected);return true;
     });
   }
   async function releaseMissing(confirm){
     if(!view().canRelease)return false;
     return action(async epoch=>{
       const expected=id;
       // An aborted request can outlive the client. Do not abandon a recent dispatch.
       if(submittedAt&&now()-submittedAt<120000)throw Error("Wait until two minutes after the start dispatch, then check the host for pending capture before releasing.");
       if((await list()).some(x=>x?.session_id===expected))throw Error("Take exists; local claim retained");
       if(!await confirm(expected))return false;
       checkPanic(epoch);
       if((await list()).some(x=>x?.session_id===expected))throw Error("Take appeared during confirmation; local claim retained");
       checkPanic(epoch);save("");state="idle";record=null;verified=true;missing=false;return true;
     });
   }
   function panicBegin(){panicPending=true;panicEpoch++;revision++;if(id){state="unknown";verified=false;missing=false;}publish();}
   function panicResult(result){
     panicPending=false;panicEpoch++;revision++;
     if(id&&result?.sessions_stopped?.includes(id)){
       // A named stop is meaningful, but retain the ID until the actual session metadata confirms closure.
       unknown("PANIC reported a stop; reconciling take metadata.");refresh();
     }else if(id){unknown("PANIC outcome for this take unconfirmed");refresh();}else publish();
   }
   function dispose(){disposed=true;revision++;}
   return {view,refresh,start,stop,pause,releaseMissing,panicBegin,panicResult,dispose,publish};
 }
 return {classify,mergeRecord,randomId,create};
})();if(typeof module==="object"&&module.exports)module.exports=api;else root.PubCastRecordingSession=api;})(globalThis);
