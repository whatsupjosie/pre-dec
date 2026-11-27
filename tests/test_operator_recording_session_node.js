"use strict";
const assert=require("node:assert/strict");
const {create,classify}=require("../static/operator_recording_session.js");
(async()=>{
 const data=new Map();let mode="lost",calls=0,rows=[],last,errors=[];
 const storage={getItem:k=>data.get(k),setItem:(k,v)=>data.set(k,v),removeItem:k=>data.delete(k)};
 const adapter={async executeConfirmed(action,payload){
   calls++;
   if(mode==="cancel")return {canceled:true};
   if(action==="recording.start"){
     if(mode==="missing")throw Error("connection lost");
     rows=[{session_id:payload.session_id,state:"active"}];
     if(mode==="lost")throw Error("connection lost");
     return {ok:true,result:rows[0]};
   }
   rows=[{session_id:payload.session_id,state:"stopped"}];
   if(mode==="lost-stop")throw Error("stop reply lost");
   return {ok:true,result:rows[0]};
 }};
 const opts={key:"test",adapter,prepare:async()=>({mode:"camcorder"}),onState:s=>last=s,onError:e=>errors.push(e),storage,makeId:()=>"test_id",fetcher:async()=>({ok:true,json:async()=>rows}),timeout:()=>undefined};
 let tracker=create(opts);
 await tracker.start();
 assert.equal(last.state,"active");
 assert.equal(last.id,"test_id");
 await tracker.start();assert.equal(calls,1);
 tracker.dispose();tracker=create(opts);await tracker.refresh();
 assert.equal(last.state,"active");
 assert.equal(last.id,"test_id");
 mode="lost-stop";await tracker.stop();
 assert.equal(last.state,"stopped");assert.equal(last.id,"");assert.equal(last.last,"test_id");
 mode="cancel";await tracker.start();assert.equal(last.id,"");assert.equal(last.state,"idle");
 rows=[];mode="missing";await tracker.start();assert.equal(last.state,"unknown");assert.equal(last.missing,true);
 await tracker.start();assert.equal(calls,4);
 await tracker.releaseMissing(()=>false);assert.equal(last.id,"test_id");
 await tracker.releaseMissing(()=>true);assert.equal(last.id,"");
 assert.equal(classify({session_id:"other",state:"active"},"test_id"),"unknown");
 console.log("Recording session recovery: 16 assertions passed");
})().catch(e=>{console.error(e);process.exitCode=1;});
