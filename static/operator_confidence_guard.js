/* Fail closed on lost production state; never display a stale source as live. */
(function(root){const api=(function guardFactory(){
  function sources(snapshot,production){
    if(!snapshot||!production||!Array.isArray(snapshot.sources))return [null,null];
    const known=new Set(snapshot.sources.map(s=>s.id));
    const blackout=production.blackout===true||Number(production.panic_seq||0)>Number(production.blackout_seq||0);
    return [!blackout&&known.has(snapshot.program)?snapshot.program:null,!production.preview_bars&&known.has(snapshot.preview)?snapshot.preview:null];
  }
  function create(viewer,readSnapshot){
    let production=null,busy=false,closed=false,revision=0,controller=null,lastReceipt=0,holds=0;
    function apply(){if(!closed)viewer?.setSources(...sources(readSnapshot(),!holds&&Date.now()-lastReceipt<2500?production:null));}
    async function poll(){
      apply();
      if(busy||closed||holds)return;
      const generation=revision;busy=true;
      controller=new AbortController();
      const timer=setTimeout(()=>controller?.abort(),1800);
      try{
        const res=await fetch("/api/state/production",{cache:"no-store",signal:controller.signal});
        if(!res.ok)throw Error("HTTP "+res.status);
        const data=await res.json();
        if(!data||typeof data!=="object"||Array.isArray(data))throw Error("Invalid production state");
        if(!closed&&generation===revision&&!holds){production=data;lastReceipt=Date.now();}
      }catch(_){if(generation===revision)production=null;}
      finally{clearTimeout(timer);controller=null;busy=false;apply();}
    }
    function invalidate(){revision++;production=null;lastReceipt=0;controller?.abort();apply();}
    function hold(){holds++;invalidate();let released=false;return ()=>{if(released)return;released=true;holds--;invalidate();if(!holds)poll();};}
    return {apply,poll,invalidate,hold,stop(){closed=true;controller?.abort();viewer?.stop();}};
  }
  return {sources,create};
})();if(typeof module==="object"&&module.exports)module.exports=api;else root.PubCastConfidenceGuard=api;})(globalThis);
