"use strict";const assert=require("node:assert/strict");const api=require("../static/operator_recording_library.js");
assert.equal(api.closed({state:"active"}),false);
assert.equal(api.closed({state:"stopped"}),true);
assert.equal(api.closed({state:"archived"}),true);
assert.equal(api.closed({state:"paused"}),false);
assert.deepEqual(api.ordered([{session_id:"a",started_at:1},{session_id:"b",started_at:2},null]).map(x=>x.session_id),["b","a"]);
assert.equal(api.filename("../a/b"),".._a_b.zip");
assert.equal(api.formatBytes(1048576),"1.0 MiB");
assert.ok(api.reportLines({state:"stopped",mode:"data_only",capture_errors:[{source_id:"cam",error:"offline"}]},null).some(x=>x.includes("CAPTURE ERROR: cam")));
assert.ok(api.reportLines({state:"stopped",mode:"data_only"},{show_data:{events:42,complete:false}}).some(x=>x.includes("not confirmed complete")));
console.log("Recording library: 9 assertions passed");

// Structural integrity checks: a prefix alone must never authorize committing a file.
const zipApi = require("../static/operator_recording_library.js");
const fixture = new Uint8Array(100), zipView = new DataView(fixture.buffer);
zipView.setUint32(0,0x04034b50,true);zipView.setUint32(32,0x02014b50,true);
zipView.setUint32(78,0x06054b50,true);zipView.setUint16(86,1,true);zipView.setUint16(88,1,true);
zipView.setUint32(90,46,true);zipView.setUint32(94,32,true);
require("node:assert/strict").equal(zipApi.validateZipTail(fixture,100),true);
require("node:assert/strict").throws(()=>zipApi.validateZipTail(fixture.slice(0,-1),99));
require("node:assert/strict").throws(()=>zipApi.validateZipTail(fixture.slice(0,40),40));
const badOffset=fixture.slice();new DataView(badOffset.buffer).setUint32(94,33,true);
require("node:assert/strict").throws(()=>zipApi.validateZipTail(badOffset,100));
require("node:assert/strict").deepEqual([...zipApi.appendTail(new Uint8Array([1,2,3]),new Uint8Array([4,5]),4)],[2,3,4,5]);
require("node:assert/strict").throws(()=>zipApi.validateZipTail(new Uint8Array(22),22));
console.log("ZIP structural integrity: six additional assertions passed");
