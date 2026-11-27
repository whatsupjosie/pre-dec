"use strict";
const assert=require("node:assert/strict");
const {create,mergeRecord,classify}=require("../static/operator_recording_session.js");
(async()=>{
 const data=new Map();let rows=[],mode="lost",calls=0,last,who="operator",clock=1000000;
 const storage={getItem:k=>data.get(k)??null,setItem:(k,v)=>data.set(k,v),removeItem:k=>data.delete(k)};
 const adapter={async executeConfirmed(action,payload,ctx){calls++;if(mode==="cancel")return {canceled:true};
   if(ctx.beforeExecute){try{await ctx.beforeExecute()}catch(e){return{notSent:true,reason:e.message}}}
   if(action==="recording.start"){
     if(mode==="missing")throw Error("connection lost");
     rows=[{session_id:payload.session_id,state:"active",operator:who}];
     if(mode==="lost")throw Error("connection lost");
     return {ok:true,result:{...rows[0],capture_errors:[{source_id:"camA",error:"offline"}]}};
   }
   rows=[{session_id:payload.session_id,state:"stopped",operator:who}];
   if(mode==="lost-stop")throw Error("stop reply lost");
   return {ok:true,result:{...rows[0],capture_report:[{source_id:"camB",warnings:["short"]}]}};
 }};
 const opts={key:"test",adapter,prepare:async()=>({mode:"camcorder"}),onState:s=>last=s,storage,makeId:()=>"test_id",identity:()=>who,now:()=>clock,fetcher:async()=>({ok:true,json:async()=>rows}),timeout:()=>undefined};
 let tracker=create(opts);
 await tracker.start();assert.equal(last.state,"active");assert.equal(last.id,"test_id");
 await tracker.start();assert.equal(calls,1);
 tracker.dispose();tracker=create(opts);await tracker.refresh();assert.equal(last.state,"active");
 mode="lost-stop";await tracker.stop();assert.equal(last.state,"stopped");assert.equal(last.id,"");assert.equal(last.last,"test_id");
 mode="clean";await tracker.start();assert.equal(last.record.capture_errors[0].source_id,"camA");
 await tracker.refresh();assert.equal(last.record.capture_errors[0].source_id,"camA");
 await tracker.stop();assert.equal(last.record.capture_errors[0].source_id,"camA");assert.deepEqual(last.record.capture_report[0].warnings,["short"]);
 mode="cancel";await tracker.start();assert.equal(last.id,"");assert.equal(last.lastVerified,true);
 mode="missing";rows=[];await tracker.start();assert.equal(last.missing,true);
 await tracker.releaseMissing(()=>true);assert.equal(last.id,"test_id");
 clock+=120001;await tracker.releaseMissing(()=>true);assert.equal(last.id,"");
 mode="clean";await tracker.start();who="other";await tracker.refresh();assert.equal(last.identityBlocked,true);assert.equal(last.canStop,false);
 tracker.dispose();tracker=create(opts);tracker.publish();assert.equal(last.identityBlocked,true);
 const failing=create({...opts,key:"other",storage:{getItem:()=>null,setItem:()=>{throw Error("quota")},removeItem:()=>{}}});
 const previous=calls;await failing.start();assert.equal(calls,previous);
 assert.deepEqual(mergeRecord({session_id:"a",capture_errors:[{source_id:"x"}]},{session_id:"b",capture_errors:[]}).capture_errors,[]);
 assert.equal(classify({session_id:"other",state:"active"},"test_id"),"unknown");
 console.log("Recording ownership and recovery assertions passed");
})().catch(e=>{console.error(e);process.exitCode=1;});
