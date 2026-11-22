/* The SAME canonical PubCast vision switcher controls both production environments.
 * 2.5D shot sources are registered with CameraManager on a running PubCast host.
 * Offline static previews remain honest LOCAL ONLY; they do not fabricate a server link.
 * Node-testable: supply fetch, setInterval and clearInterval in create({ ... }).
 */
(function (root,factory) {
 const api=factory();
 if(typeof module==="object"&&module.exports)module.exports=api;
 else root.PubCast25DSharedSwitcher=api;
})(typeof globalThis!=="undefined"?globalThis:this,function(){
 "use strict";
 const SOURCE_PREFIX="p25d_";
 const encode=id=>encodeURIComponent(id);
 function sourceId(pkgId,shotId) {
   if(!/^[a-z][a-z0-9_]{0,39}$/.test(pkgId)||!/^[a-z][a-z0-9_]{0,39}$/.test(shotId))throw Error("Invalid studio camera ID");
   return SOURCE_PREFIX+pkgId+"_"+shotId;
 }
 function create(options={}) {
   const requestFetch=options.fetch||globalThis.fetch?.bind(globalThis);
   const schedule=options.setInterval||globalThis.setInterval?.bind(globalThis);
   const unschedule=options.clearInterval||globalThis.clearInterval?.bind(globalThis);
   const onState=typeof options.onState==="function"?options.onState:()=>{};
   const onError=typeof options.onError==="function"?options.onError:()=>{};
   let pkg=null,joined=false,timer=null,poll=null,mutation=null,last=null;
   let version=0,failed=false;
   function shotId(camera) {
     if(!pkg||!camera)return null;
     const found=pkg.cameras.find(c=>sourceId(pkg.id,c.id)===camera);
     return found?found.id:null;
   }
   function normalize(data) {
     if(!data||!Array.isArray(data.sources)||!("program" in data)||!("preview" in data))throw Error("Switcher state is malformed");
     return {program:shotId(data.program),preview:shotId(data.preview),
       remoteProgram:data.program&&!shotId(data.program)?data.program:null,
       remotePreview:data.preview&&!shotId(data.preview)?data.preview:null,
       transition:data.transition||{type:"cut",duration_ms:0},online:true};
   }
   async function request(path,method="GET",body) {
     if(!requestFetch)throw Error("Fetch is unavailable");
     const response=await requestFetch(path,{method,credentials:"same-origin",
       headers:body?{"Content-Type":"application/json"}:undefined,
       body:body?JSON.stringify(body):undefined,cache:method==="GET"?"no-store":undefined,
       signal:globalThis.AbortSignal?.timeout?.(6000)});
     if(!response.ok)throw Error("Shared switcher "+method+" "+path+" HTTP "+response.status);
     const result=await response.json();
     if(!result||typeof result!=="object")throw Error("Shared switcher returned invalid JSON");
     return result;
   }
   function publish(data) {
     const next=normalize(data), signature=JSON.stringify(next);
     if(failed||signature!==last){failed=false;last=signature;onState(next);}
     return next;
   }
   async function refresh() {
     if(!joined||poll||mutation)return null;
     const ticket={version};poll=ticket;
     try {
       const data=await request("/api/switcher/state");
       return joined&&ticket.version===version?publish(data):null;
     } catch(e) {
       if(!joined||ticket.version!==version)return null;
       if(!failed){failed=true;onError("Shared video switcher unavailable: "+e.message);}
       throw e;
     } finally {
       if(poll===ticket)poll=null;
     }
   }
   async function attach(packageConfig) {
     detach();
     if(!packageConfig?.cameras?.length)throw Error("Production package has no cameras");
     const attaching=version;
     const cancelled=()=>({shared:false,reason:"Switcher attachment ended"});
     pkg=packageConfig;
     // Read before writing. Missing backend or insufficient role means LOCAL ONLY,
     // never a fake connection. Registration is explicitly authorized by Start Production.
     let state;
     try{state=await request("/api/switcher/state");}
     catch(e){return {shared:false,reason:e.message};}
     if(attaching!==version)return cancelled();
     if(!Array.isArray(state.sources))return {shared:false,reason:"Malformed shared switcher response"};
     const existing=new Set(state.sources.map(s=>s.id));
     try {
       for(const shot of packageConfig.cameras) {
         if(attaching!==version)return cancelled();
         const id=sourceId(packageConfig.id,shot.id);
         if(existing.has(id))continue;
         await request("/api/cameras/register","POST",{
           source_id:id,name:pkg.title+" / "+shot.label,
           location:"studio25d",transport:"virtual",endpoint:"virtual://"+id,
           description:"2.5D television stage camera; frames rendered in active studio browser",
           position:[0,1.6,4],rotation:[0,0,0],fov:60,
           tags:["virtual","studio25d",pkg.id]
         });
       }
       // Activation selects BOTH sources in one canonical server transaction;
       // a failed Preview may not leave Program silently on the new stage.
       if(attaching!==version)return cancelled();
       await request("/api/switcher/select","POST",{
         program:sourceId(pkg.id,pkg.cameras[0].id),
         preview:sourceId(pkg.id,pkg.cameras[1].id)
       });
     } catch(e){return {shared:false,reason:"Could not register/select production cameras: "+e.message};}
     if(attaching!==version)return cancelled();
     joined=true;last=null;
     try{await refresh();}
     catch(e){if(attaching===version)joined=false;return {shared:false,reason:e.message};}
     if(attaching!==version)return cancelled();
     if(schedule)timer=schedule(()=>refresh().catch(()=>{}),750);
     return {shared:true,sourceCount:pkg.cameras.length};
   }
   async function change(path,body) {
     if(!joined)throw Error("Shared switcher is not connected");
     if(mutation)throw Error("Wait for the current switcher command to finish");
     const ticket=++version;mutation=ticket;poll=null;
     try {
       const data=await request(path,"POST",body);
       if(!joined||ticket!==version)throw new DOMException("Switcher command ended","AbortError");
       return publish(data);
     } finally {
       if(mutation===ticket)mutation=null;
     }
   }
   function choosePreview(localShotId) {
     if(!pkg?.cameras.some(c=>c.id===localShotId))throw Error("Unknown package camera");
     return change("/api/switcher/preview/"+encode(sourceId(pkg.id,localShotId)));
   }
   function take(dissolve=false) {
     return dissolve
       ?change("/api/switcher/transition",{type:"dissolve",duration_ms:600})
       :change("/api/switcher/cut");
   }
   function detach() {
     if(timer!=null&&unschedule)unschedule(timer);
     version++;timer=null;joined=false;pkg=null;last=null;poll=null;mutation=null;failed=false;
   }
   return {attach,detach,refresh,choosePreview,take,connected:()=>joined,sourceId};
 }
 return {create,sourceId};
});
