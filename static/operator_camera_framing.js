/* Local stage camera framing; canonical camera identity remains unchanged. */
(function(root){const api=(function framingFactory(){
 "use strict";
 const clamp=(n,a,b)=>Math.max(a,Math.min(b,n));
 const round=n=>Math.round(n*100000)/100000;
 function adjust(shot,action){
   if(!shot||!Array.isArray(shot.center)||shot.center.length!==2||!shot.center.every(Number.isFinite)||!Number.isFinite(shot.zoom))throw Error("Invalid camera framing");
   let [x,y]=shot.center,z=clamp(shot.zoom,1,4);
   const step=.07/z;
   switch(action){case "left":x-=step;break;case "right":x+=step;break;case "up":y-=step;break;case "down":y+=step;break;case "in":z+=.2;break;case "out":z-=.2;break;default:throw Error("Unknown camera adjustment");}
   z=round(clamp(z,1,4));
   const edge=.5/z;
   return {...shot,center:[round(clamp(x,edge,1-edge)),round(clamp(y,edge,1-edge))],zoom:z};
 }
 function mount({panel,current,change,reset,allowed}){
   const target=panel.querySelector("[data-framing-target]"),keys=panel.querySelector("[data-framing-keys]"),readout=panel.querySelector("[data-framing-status]");
   const buttons=[...panel.querySelectorAll("[data-framing-action]")];
   function refresh(){
     const role=target.value,shot=current(role),reason=allowed(role);
     buttons.forEach(b=>b.disabled=!!reason||!shot);
     readout.textContent=reason||(shot?`${role.toUpperCase()} | ${shot.label} | ${shot.zoom.toFixed(2)}× | ${shot.center.map(n=>Math.round(n*100)+"%").join(", ")}`:"No local camera selected");
   }
   function invoke(action){
     const role=target.value;
     if(allowed(role)||!current(role)){refresh();return;}
     try{if(action==="reset")reset(role);else change(role,action);refresh();}
     catch(error){readout.textContent="Framing failed: "+error.message;}
   }
   buttons.forEach(b=>b.addEventListener("click",()=>invoke(b.dataset.framingAction)));
   target.addEventListener("change",refresh);
   const map={w:"up",a:"left",s:"down",d:"right","+":"in","=":"in","-":"out","0":"reset"};
   function key(event){
     if(!keys.checked||event.repeat||event.ctrlKey||event.altKey||event.metaKey||event.target?.closest?.("input,textarea,select,button,[contenteditable]"))return;
     const action=map[event.key.toLowerCase()];if(!action)return;
     event.preventDefault();invoke(action);
   }
   document.addEventListener("keydown",key);
   window.addEventListener("pagehide",()=>document.removeEventListener("keydown",key),{once:true});
   refresh();return {refresh};
 }
 return {adjust,mount};
})();if(typeof module==="object"&&module.exports)module.exports=api;else root.PubCastCameraFraming=api;})(globalThis);
