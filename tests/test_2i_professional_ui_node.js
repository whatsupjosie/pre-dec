const {test}=require("node:test");const assert=require("node:assert/strict");const fs=require("node:fs");const path=require("node:path");const vm=require("node:vm");
const base=path.join(__dirname,"../2i/2i-assets");
// Extract a named function by matching its braces, not by a trailing source
// anchor. The old end anchors were literal neighbouring lines ("\n  if(reachFileMode)",
// "\n  function canPresent"), so any edit beside the function under test broke the
// test rather than the code. Strings, template literals and comments are skipped;
// a brace inside a regex literal would still confuse it, and none of these have one.
function readFunction(src,name){
  const open=src.indexOf("function "+name+"(");
  assert.ok(open>=0,"no function "+name+" in source");
  let i=src.indexOf("{",open);
  assert.ok(i>open,"no body for "+name);
  let depth=0,last="";
  for(;i<src.length;i++){
    const ch=src[i],two=src.slice(i,i+2);
    if(two==="//"){i=src.indexOf("\n",i);if(i<0)break;continue;}
    if(two==="/*"){i=src.indexOf("*/",i)+1;continue;}
    if(ch==="'"||ch==='"'||ch==="`"){
      for(i++;i<src.length&&src[i]!==ch;i++)if(src[i]==="\\")i++;
      last=ch;continue;
    }
    if(ch==="/"&&(last===""||"(,=:[!&|?{};+-*%~^".includes(last))){
      for(i++;i<src.length&&src[i]!=="/";i++)if(src[i]==="\\")i++;
      last="/";continue;
    }
    if(ch==="{")depth++;
    else if(ch==="}"){depth--;if(!depth)return src.slice(open,i+1);}
    if(!/\s/.test(ch))last=ch;
  }
  assert.fail("unbalanced braces reading "+name);
}
function extract(file,name){
  const src=fs.readFileSync(path.join(base,file),"utf8");
  return vm.runInNewContext("("+readFunction(src,name)+")");
}
const rank=extract("format-menu.js","rankCommands");
const mode=extract("studio-desk.js","presentationMode");
const allowed=extract("studio-desk.js","canPresent");
test("command search literal terms, stable ordering, and exact first",()=>{const c=[{group:"File",label:"Save"},{group:"File",label:"Save a copy"},{group:"Edit",label:"Find & replace"},{group:"Layout",label:"Formatted preview"}];assert.equal(rank(c,"SAVE")[0],c[0]);assert.equal(rank(c,"file copy")[0],c[1]);assert.equal(rank(c,"layout formatted")[0],c[3]);assert.equal(rank(c,"save preview").length,0);assert.equal(rank(c,"[").length,0);assert.equal(rank(c,"").map(x=>x.label).join("|"),c.map(x=>x.label).join("|"));});
test("presentation is selected from host context without a format dependency",()=>{assert.equal(mode({room:null,seated:false},false),"standard");assert.equal(mode({room:"writers_room",seated:false},false),"notebook");assert.equal(mode({room:"dressing_room",seated:true},false),"typewriter");assert.equal(mode({room:"dressing_room",seated:true},true),"standard");assert.equal(allowed("standard",false),true);assert.equal(allowed("notebook",false),true);assert.equal(allowed("typewriter",false),true);assert.equal(allowed("typewriter",true),true);assert.equal(allowed("invalid",true),false);});
