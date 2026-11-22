(function(){
'use strict';
const $=id=>document.getElementById(id),query=new URLSearchParams(location.search),mode=query.get('mode')||'join';
const message=value=>{$('status').textContent=value;};
let prepared=null,popup=null,homeOrigin=null,pollTimer=null,polling=false,waitingHost=null,arrivalTimer=null,staffTimer=null,canIssuePass=false;
const consent={tos:true,recording:true,ai_disclosure:true,data_processing:true};
async function api(path,body){
 const response=await fetch('/api/guests/'+path.replace(/^\//,''),{method:body===undefined?'GET':'POST',headers:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body),signal:AbortSignal.timeout(20000),cache:'no-store'});
 const data=await response.json();if(!response.ok)throw Error(typeof data.detail==='string'?data.detail:'The visit request failed ('+response.status+')');
 return {data,response};
}
function origin(value){const u=new URL(value);if(!['https:','http:'].includes(u.protocol)||u.username||u.password||u.pathname!=='/'||u.search||u.hash)throw Error('Use your PubCast address without a page path');return u.origin;}
function restorePrepared(){try{prepared=JSON.parse(sessionStorage.getItem('pubcast.visit.pending')||'null');if(prepared){$('challengeOut').value=JSON.stringify(prepared.challenge);$('prepared').hidden=false;}}catch(_){prepared=null;}}
async function poll(){
 if(!prepared||polling)return;polling=true;clearTimeout(pollTimer);
 try{const {data}=await api('/status',{poll_token:prepared.poll_token});
  if(data.access_token){waitingHost?.show('approved');ReachAuth.saveSession(data);sessionStorage.removeItem('pubcast.visit.pending');prepared=null;$('enter').hidden=false;message('Your host approved your visit. You can enter the studio.');}
  else if(['denied','expired'].includes(data.status)){if(data.status==='denied')waitingHost?.show('denied');sessionStorage.removeItem('pubcast.visit.pending');prepared=null;message(data.status==='denied'?'Your host declined this visit.':'This visit expired. Ask for a new invitation.');}
  else {waitingHost?.show('pending');message('Your card is verified. Waiting for your host to open the door.');pollTimer=setTimeout(poll,2000);}
 }catch(e){message(e.message+' You can retry by sending your card again.');}
 finally{polling=false;}
}
async function submit(proof){
 if(!prepared)throw Error('Prepare your visit first');
 const received=proof?.payload?.challenge;
 if(!received||Object.keys(received).length!==Object.keys(prepared.challenge).length||Object.keys(prepared.challenge).some(key=>received[key]!==prepared.challenge[key]))throw Error('This card belongs to a different visit request');
 await api('/request',proof);prepared.submitted=true;sessionStorage.setItem('pubcast.visit.pending',JSON.stringify(prepared));await poll();
}
async function prepareVisit(code){
 const {data}=await api('/challenge',{invite_code:code});
 prepared=data;sessionStorage.setItem('pubcast.visit.pending',JSON.stringify(data));
 $('challengeOut').value=JSON.stringify(data.challenge);$('prepared').hidden=false;$('enter').hidden=true;
 $('knock').hidden=true;
 message('Open your own copy to review the contract and sign your visiting card.');
}
$('prepare').onsubmit=async event=>{
 event.preventDefault();$('prepareButton').disabled=true;
 try{await prepareVisit($('invite').value.trim());}
 catch(e){message(e.message);}finally{$('prepareButton').disabled=false;}
};
const arrivalKey='pubcast.airlock.ticket';
async function pollArrival(ticket){
 clearTimeout(arrivalTimer);
 try{
  const {data}=await api('/arrival/status',{ticket});
  if(data.status==='waiting'){
   $('arrival-status').textContent='The door staff have been paged. Please wait here.';
   arrivalTimer=setTimeout(()=>pollArrival(ticket),2500);
  }else if(data.status==='session_pass' && data.access_token){
   ReachAuth.saveSession(data);
   sessionStorage.removeItem(arrivalKey);
   $('knock').hidden=$('prepare').hidden=$('prepared').hidden=true;
   $('enter').hidden=false;
   waitingHost?.show('approved');
   $('arrival-status').textContent='The owner issued you a pass for this session. You can enter the studio.';
  }else if(data.status==='invited'){
   await prepareVisit(data.invite_code);
   sessionStorage.removeItem(arrivalKey);
   $('arrival-status').textContent='Door staff invited you to sign in and present your card.';
  }else{
   sessionStorage.removeItem(arrivalKey);$('knock-button').disabled=false;
   $('arrival-status').textContent=data.status==='denied'?'Door staff declined this arrival.':'This arrival ticket expired.';
  }
 }catch(error){
  $('arrival-status').textContent=error.message+' Retrying…';
  arrivalTimer=setTimeout(()=>pollArrival(ticket),5000);
 }
}
$('knock').onsubmit=async event=>{
 event.preventDefault();$('knock-button').disabled=true;
 try{
  let ticket=sessionStorage.getItem(arrivalKey);
  if(!ticket){
   ticket=Array.from(crypto.getRandomValues(new Uint8Array(32)),byte=>byte.toString(16).padStart(2,'0')).join('');
   sessionStorage.setItem(arrivalKey,ticket);
  }
  await api('/arrival',{screen_name:$('arrival-name').value,ticket});
  await pollArrival(ticket);
 }catch(error){$('arrival-status').textContent=error.message;$('knock-button').disabled=false;}
};
$('openHome').onclick=()=>{try{
 if(!prepared)throw Error('Prepare your visit first');homeOrigin=origin($('homeOrigin').value.trim());
 popup=window.open(homeOrigin+'/static/human_visits.html?mode=sign&challenge='+encodeURIComponent(JSON.stringify(prepared.challenge)),'pubcast-visit-home');
 if(!popup)message('The browser blocked the new window. Use the manual exchange below.');
}catch(e){message(e.message);}};
window.addEventListener('message',event=>{
 if(!popup||event.source!==popup||event.origin!==homeOrigin||event.data?.type!=='pubcast.visiting-card')return;
 submit(event.data.proof).catch(e=>message(e.message));
});
$('submitProof').onclick=async()=>{try{await submit(JSON.parse($('proofIn').value));}catch(e){message(e.message);}};
function showTarget(){
 try{const challenge=JSON.parse($('challengeIn').value);const target=origin(challenge.origin);
 $('target').textContent='Visiting '+target+' · Host '+challenge.host_id;$('terms').href=target+'/static/human_visits.html?mode=join#entry-contract';$('terms').hidden=false;
 }catch(_){$('target').textContent='Paste a valid visit request to see its host.';$('terms').hidden=true;}
}
$('challengeIn').oninput=showTarget;
$('signCard').onclick=async()=>{if(!$('consent').checked){message('Review and accept this visit’s production consents first.');return;}$('signCard').disabled=true;
 try{const challenge=JSON.parse($('challengeIn').value);const target=origin(challenge.origin);
  const {data,response}=await api('/sign',{challenge,consents:consent});$('proofOut').value=JSON.stringify(data);$('fingerprint').textContent=response.headers.get('X-PubCast-Identity-Fingerprint');$('signed').hidden=false;
  if(window.opener){window.opener.postMessage({type:'pubcast.visiting-card',proof:data},target);$('sentMessage').textContent='Card sent to your visit window. Return there to wait for admission.';}
  else $('sentMessage').textContent='Copy this signed card back into your visit window.';
  message('Your visiting card is ready.');
 }catch(e){message(e.message);}finally{$('signCard').disabled=false;}
};
async function pending(){
 const [{data}, arrivals]=await Promise.all([api('/pending'),api('/arrivals')]);
 const identity=JSON.stringify([data.pending,arrivals.data.arrivals]);
 if(pending.snapshot===identity)return;
 pending.snapshot=identity;
 $('pending').replaceChildren();$('arrivals').replaceChildren();
 for(const guest of arrivals.data.arrivals){
  const box=document.createElement('article'), heading=document.createElement('h3');
  heading.textContent=guest.name+' · Unverified arrival';box.append(heading);
  for(const allow of [true,false]){
   const button=document.createElement('button');button.type='button';
   button.textContent=allow?'Invite to sign in':'Decline arrival';
   button.onclick=async()=>{button.disabled=true;try{
    await api('/arrivals/'+encodeURIComponent(guest.arrival_id)+'/decision',{allow});
    await pending();message(allow?'Invitation sent to the visitor in the Airlock.':'Arrival declined.');
   }catch(error){message(error.message);button.disabled=false;}};
   box.append(button);
  }
  if(canIssuePass){
   const pass=document.createElement('button');pass.type='button';pass.textContent='Issue session pass';
   pass.onclick=async()=>{
    if(!window.confirm('Let '+guest.name+' enter this session without a signed contract?'))return;
    pass.disabled=true;
    try{
     await api('/arrivals/'+encodeURIComponent(guest.arrival_id)+'/session-pass',{});
     await Promise.all([pending(),loadPassSession()]);
     message('Temporary pass issued to '+guest.name+'.');
    }catch(error){message(error.message);pass.disabled=false;}
   };
   box.append(pass);
  }
  $('arrivals').append(box);
 }
 if(!arrivals.data.arrivals.length)$('arrivals').textContent='No unverified arrivals are waiting.';
 for(const person of data.pending){
  const box=document.createElement('article'),heading=document.createElement('h3');heading.textContent=person.card.display_name+' · Human';box.append(heading);
  const id=document.createElement('p');id.className='key';id.textContent=person.card.user_id+' · Visit '+person.entry_id;box.append(id);
  const trust=document.createElement('p');trust.textContent=person.known_key?'Returning identity: the key matches.':'First visit: compare this key with the person you invited.';box.append(trust);
  const key=document.createElement('p');key.className='key';key.textContent=person.fingerprint;box.append(key);
  for(const action of ['approve','deny']){const button=document.createElement('button');button.type='button';button.textContent=action==='approve'?'Approve visit':'Decline';button.onclick=async()=>{button.disabled=true;try{
   await api('/entries/'+encodeURIComponent(person.entry_id)+'/'+action,action==='approve'?{fingerprint:person.fingerprint}:{});await pending();message(action==='approve'?'Visit approved.':'Visit declined.');
  }catch(e){message(e.message);button.disabled=false;}};box.append(button);}
  $('pending').append(box);
 }
 if(!data.pending.length)$('pending').textContent='No verified guests are waiting.';
}
$('refresh').onclick=()=>pending().catch(e=>message(e.message));
$('createInvite').onclick=async()=>{try{const {data}=await api('/invites',{returning_auto:$('returning-auto').checked});$('inviteOut').value=data.invite_code;$('inviteLabel').hidden=false;message('Share this invitation with the person you want to invite.');}catch(e){message(e.message);}};
async function settings(){const {data}=await api('/settings');$('doorState').textContent=(data.locked?'Airlock closed · Door staff review new visitors.':'Airlock open · Verified invitations may enter.')+' Host '+data.host_id;}
for(const [id,locked]of [['lockDoor',true],['unlockDoor',false]])$(id).onclick=async()=>{try{await api('/door',{locked});await settings();message(locked?'New guests will wait for approval.':'Verified guests with valid invitations can enter.');}catch(e){message(e.message);}};
$('revoke').onsubmit=async e=>{e.preventDefault();try{await api('/entries/'+encodeURIComponent($('revokeId').value.trim())+'/revoke',{});message('Visit access revoked.');}catch(error){message(error.message);}};
async function loadPassSession(){
 const {data}=await api('/pass-session');
 const list=$('active-passes');
 list.replaceChildren();
 const timing=document.createElement('p');
 timing.textContent=data.expires?'Passes expire no later than '+new Date(data.expires*1000).toLocaleString()+'.':'No active temporary-pass session.';
 list.append(timing);
 $('end-pass-session').disabled=!data.expires;
 for(const pass of data.passes){
  const row=document.createElement('p');row.textContent=pass.name+' ';
  const revoke=document.createElement('button');revoke.type='button';revoke.textContent='Revoke pass';
  revoke.onclick=async()=>{revoke.disabled=true;try{
   await api('/entries/'+encodeURIComponent(pass.pass_id)+'/revoke',{});
   await loadPassSession();message('Pass revoked for '+pass.name+'.');
  }catch(error){message(error.message);revoke.disabled=false;}};
  row.append(revoke);list.append(row);
 }
}
$('end-pass-session').onclick=async()=>{
 if(!window.confirm('End access for every guest using a temporary session pass?'))return;
 $('end-pass-session').disabled=true;
 try{await api('/pass-session/end',{});await loadPassSession();message('Temporary-pass session ended.');}
 catch(error){message(error.message);$('end-pass-session').disabled=false;}
};
async function loadEvent(){
 const {data}=await api('/event');
 $('event-description').value=data.description;
 $('event-description').disabled=$('event-save').disabled=false;
}
$('event-form').onsubmit=async event=>{
 event.preventDefault();
 const field=$('event-description'), button=$('event-save');
 if(button.disabled)return;
 field.disabled=button.disabled=true;
 try{
  const {data}=await api('/event',{description:field.value});
  field.value=data.description;
  message(data.description?'Tonight’s answer is published.':'Sir Purfluous’s usual answer is restored.');
 }catch(error){message(error.message);}
 finally{field.disabled=button.disabled=false;}
};
window.addEventListener('pagehide',()=>{clearTimeout(pollTimer);clearTimeout(arrivalTimer);clearInterval(staffTimer);});
if(mode==='sign'){
 $('sign').hidden=false;$('challengeIn').value=query.get('challenge')||'';showTarget();
 ReachAuth.requireSession(location.pathname+location.search).catch(e=>message(e.message));
}else if(mode==='host'){
 $('host').hidden=false;
 ReachAuth.requireSession(location.pathname+location.search).then(async session=>{
  if(!session)return;
  canIssuePass=ReachAuth.getUser()?.role==='owner';
  $('owner-door-controls').hidden=$('revoke').hidden=!canIssuePass;
  await pending();
  staffTimer=setInterval(()=>{if(!document.hidden)pending().catch(e=>message(e.message));},3000);
  if(canIssuePass)await Promise.all([settings(),loadEvent(),loadPassSession()]);
 }).catch(e=>message(e.message));
}else{
 $('join').hidden=false;$('visit-nav').hidden=true;
 const recoveredToken=ReachAuth.getToken();
 if(recoveredToken)ReachAuth.verify().then(identity=>{if(!identity && ReachAuth.getToken()===recoveredToken)ReachAuth.clearSession();}).catch(()=>{});
 if(location.hash==='#entry-contract')$('entry-contract').open=true;
 waitingHost=window.PubcastWaitingRoomHost.mount({
  line:$('guest-host-line'),terms:$('guest-contract'),
  faq:{container:$('guest-faq'),contract:$('entry-contract'),invited:true}
 });
 restorePrepared();if(prepared){$('knock').hidden=true;if(prepared.submitted)poll();}
 else if(sessionStorage.getItem(arrivalKey)){$('knock-button').disabled=true;pollArrival(sessionStorage.getItem(arrivalKey));}
}
})();
