/* Same-device, one-time script transfer. No script text in a URL or server request. */
(function(root){const api=(function transferFactory(){
 "use strict";
 const max=200000,valid=id=>/^[a-f0-9]{32}$/.test(id||"");
 function send(script,report){
  script=String(script||"");
  if(!script.trim())return report("Enter a script first",true);
  if(script.length>max)return report("Script exceeds 200,000 characters",true);
  if(typeof BroadcastChannel!=="function"||!globalThis.crypto?.getRandomValues)return report("Secure local script handoff unavailable",true);
  const id=Array.from(crypto.getRandomValues(new Uint8Array(16)),n=>n.toString(16).padStart(2,"0")).join("");
  const channel=new BroadcastChannel("pubcast-prompter-"+id);
  let done=false,timeout;
  function finish(message,failed){if(done)return;done=true;clearTimeout(timeout);channel.close();report(message,failed);}
  channel.onmessage=({data})=>{if(data?.type==="ready")channel.postMessage({type:"script",script});else if(data?.type==="received")finish("Script received by full teleprompter",false);};
  const child=window.open("/static/pubcast_teleprompter.html#handoff="+id,"_blank");
  if(!child)return finish("Popup blocked. Allow popups and try again.",true);
  try{child.opener=null;}catch(_){}
  report("Sending script to the full teleprompter...",false);
  timeout=setTimeout(()=>finish("Transfer not acknowledged. The source script is unchanged.",true),12000);
 }
 function receive(onScript){
  const id=new URLSearchParams(location.hash.slice(1)).get("handoff");
  if(!valid(id)||typeof BroadcastChannel!=="function")return false;
  const channel=new BroadcastChannel("pubcast-prompter-"+id);
  let finished=false;
  function close(){if(finished)return;finished=true;clearTimeout(timeout);channel.close();}
  const timeout=setTimeout(close,10000);
  channel.onmessage=({data})=>{
   if(finished||data?.type!=="script"||typeof data.script!=="string"||!data.script.trim()||data.script.length>max)return;
   onScript(data.script);channel.postMessage({type:"received"});close();
   history.replaceState(null,"",location.pathname+location.search);
  };
  channel.postMessage({type:"ready"});return true;
 }
 return {send,receive,valid};
})();if(typeof module==="object"&&module.exports)module.exports=api;else root.PubCastPrompterHandoff=api;})(globalThis);
