import './style.css';
import { createModel } from './model.js';

const branches={can0:'Left leg',can1:'Waist · right leg',can2:'Left arm',can3:'Right arm'};
let state, token, selected, model, pending=false, connected=false, localError=null;
const lastActive={};
const escape = text => String(text ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
document.querySelector('#app').innerHTML=`
<header><div class="brand"><span class="brandmark">r.</span><div>ROBOTO ORIGIN<small>MOTOR COMMS VERIFIER</small></div></div><span id="connection" class="badge">Connecting</span></header>
<main><div class="visual-stack"><section id="details" class="branch-details" aria-label="Current motor per branch"></section><section class="viewer"><div class="view-title"><span>Joint topology</span><span class="muted">23 motors · 4 branches</span></div><div id="model"><div id="model-loading">Loading supplied robot model…</div></div><div class="legend"><span><i class="idle"></i>Unchecked</span><span><i class="waiting"></i>Awaiting reply</span><span><i class="ok"></i>Reply received</span><span><i class="error"></i>Failed</span></div><div class="view-footer">Drag to orbit · scroll to zoom · click a joint<span>Static reference pose</span></div></section></div>
<aside><div class="eyebrow">PARALLEL BRANCH CHECK</div><div class="controls"><button id="start">Start cycle <span>↗</span></button><button id="stop" disabled>Stop & disable</button></div><p class="support">Support the robot and keep the E-stop ready. Stop other motor-control programs. Enabling may produce torque.</p><div id="error" role="alert"></div><div class="branch-heading">BRANCH ORDER <span>SELECT TO INCLUDE</span></div><div id="branches"></div></aside></main>
<section class="activity"><div class="activity-head"><span>Activity</span><span class="muted">Newest first</span></div><div id="events"></div></section>`;
for (const [bus,name] of Object.entries(branches)) {
  document.querySelector('#branches').insertAdjacentHTML('beforeend',`<section class="branch" id="${bus}"><label><input type="checkbox" value="${bus}" checked><strong>${bus}</strong><span>${name}</span></label><div class="motor-row"></div></section>`);
}
async function post(path, body={}) {
  const response=await fetch('/api/'+path,{method:'POST',headers:{'Content-Type':'application/json','X-Control-Token':token},body:JSON.stringify(body)});
  const result=await response.json(); if (!response.ok) throw Error(result.error || 'Request failed'); return result;
}
function render() {
  const live=state.mode==='Live';
  document.querySelector('#connection').textContent=connected ? `${state.mode} · ${state.running?'Cycling':'Idle'}` : 'Connection lost';
  document.querySelector('#connection').className='badge '+(live?'live':'');
  document.querySelector('#start').disabled=!connected || pending || state.running;
  document.querySelector('#stop').disabled=!connected || pending || !state.running;
  document.querySelectorAll('input').forEach(input=>input.disabled=state.running || pending);
  document.querySelector('#error').textContent=localError || state.error || '';
  const activeIds=Object.values(state.active).filter(Boolean);
  for (const [bus,id] of Object.entries(state.active)) if(id)lastActive[bus]=id;
  document.querySelector('#details').innerHTML=Object.entries(branches).map(([bus,name])=>{
    const chosen=state.motors[String(selected)];
    const motor=state.motors[String(state.active[bus] || (chosen?.bus===bus?selected:null) || lastActive[bus])];
    const branch=state.branches[bus];
    return `<article class="branch-detail"><div class="detail-top"><b>${bus}</b><span>${name}</span><small>${branch.selected?'Cycle '+branch.cycle:'Not selected'}</small></div>
      <div class="detail-header"><span class="dot ${motor?.color || 'idle'}"></span><b>${escape(motor?.name || 'Waiting to start')}</b></div>
      <p title="${escape(motor?.phase || branch.phase)}">${escape(motor?.phase || branch.phase)}</p>
      <div class="detail-data"><span>Motor <b>${motor?motor.id+' / 0x'+motor.id.toString(16).padStart(2,'0'):'—'}</b></span><span>Master <b>${motor?'0x'+motor.master.toString(16):'—'}</b></span><span>${motor?.model || '—'}</span><span>${motor?.latency_ms==null?'—':motor.latency_ms+' ms'}</span></div>
      <code>${motor?.raw || '—'}</code></article>`;
  }).join('');
  for (const bus of Object.keys(branches)) {
    document.querySelector(`#${bus} .motor-row`).innerHTML=Object.values(state.motors).filter(m=>m.bus===bus).sort((a,b)=>{if(bus==='can1'){if(a.id===13)return -1;if(b.id===13)return 1;}return a.id-b.id;}).map(m=>`<div class="motor-cell"><button class="motor ${m.color} ${activeIds.includes(m.id)?'active':''} ${m.id===selected?'selected':''}" data-id="${m.id}" title="${escape(m.name+' · '+m.phase)}" aria-label="${escape(m.name+' · ID '+m.id+' · '+m.phase)}">${m.id}</button><small>${escape(m.name.replace(/^(Left|Right) /,''))}</small></div>`).join('<span class="arrow">›</span>');
  }
  document.querySelector('#events').innerHTML=state.events.length?state.events.slice(0,12).map(e=>`<div><time>${e.time}</time><span>${escape(e.text)}</span></div>`).join(''):'<div class="muted">Waiting for the first cycle.</div>';
  model?.update(state.motors,activeIds,selected);
}
document.querySelector('#branches').addEventListener('click',e=>{ const button=e.target.closest('[data-id]'); if(button){selected=Number(button.dataset.id);render();} });
document.querySelector('#start').onclick=async()=>{
  pending=true; localError=null; render();
  try { await post('start',{branches:[...document.querySelectorAll('input:checked')].map(x=>x.value)}); selected=null; }
  catch(e){localError=e.message;} finally {pending=false; await poll();}
};
document.querySelector('#stop').onclick=async()=>{pending=true;localError=null;render();try{await post('stop');}catch(e){localError=e.message;}finally{pending=false;await poll();}};
async function poll() {
  try {
    const response=await fetch('/api/state',{cache:'no-store'}); if(!response.ok)throw Error('Server unavailable');
    state=await response.json();token=state.token;connected=true; render();
  }catch(e){connected=false;document.querySelector('#connection').textContent='Connection lost';document.querySelector('#start').disabled=true;document.querySelector('#stop').disabled=true;document.querySelector('#error').textContent='Backend connection lost. Browser heartbeat will stop cycling; verify motor LEDs.';}
}
await poll();
setInterval(poll,120);
setInterval(()=>{if(token && connected)post('heartbeat').catch(()=>{});},700);
createModel(document.querySelector('#model'),id=>{selected=id;if(state)render();}).then(value=>{
  model=value;document.querySelector('#model-loading').remove();if(state)render();
}).catch(error=>{document.querySelector('#model-loading').textContent='3D unavailable: '+error.message+'. Branch controls still work.';});
