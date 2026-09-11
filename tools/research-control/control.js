'use strict';
const $=id=>document.getElementById(id);
// The session token is the last path segment of the page URL: '/<token>/' on loopback and
// '/<mount>/<token>/' when the panel is reached through the Tailscale Serve mount.
function sessionKeyFromPath(pathname){const parts=String(pathname||'').split('/').filter(Boolean);return parts.length?parts[parts.length-1]:'';}
const sessionKey=()=>sessionKeyFromPath(location.pathname);
const key=sessionKey();
if(typeof module!=='undefined')module.exports={sessionKeyFromPath};
// Visible feedback for every action: the review status line plus a toast above the phone tab bar.
function notify(text,kind){
  const line=document.getElementById('review-message');if(line)line.textContent=text;
  let t=document.getElementById('toast');if(!t){t=document.createElement('div');t.id='toast';t.setAttribute('role','alert');document.body.append(t);}
  t.textContent=text;t.className='toast '+(kind||'ok');t.hidden=false;clearTimeout(notify.timer);notify.timer=setTimeout(()=>{t.hidden=true;},kind==='error'?14000:8000);
}
const PANELS=['decisions-panel','session-panel','activity-panel'];
const TABS={'decisions-tab':'decisions-panel','session-tab':'session-panel','activity-tab':'activity-panel'};
function showPanel(id){
  for(const p of PANELS)$(p).hidden=(p!==id);
  for(const [tab,panel] of Object.entries(TABS))$(tab).setAttribute('aria-pressed',String(panel===id));
}
function watchStale(el,loadingText,staleText,ms){
  el.textContent=loadingText;
  setTimeout(()=>{if(el.textContent===loadingText)el.textContent=staleText;},ms||4000);
}
// Fallback bindings: reviews.js/visuals.js/activity.js overwrite these once they load successfully.
// If a script 404s on a stale already-running server, these keep the panel usable and explain why.
$('decisions-tab').onclick=()=>showPanel('decisions-panel');
$('session-tab').onclick=()=>showPanel('session-panel');
$('activity-tab').onclick=()=>{showPanel('activity-panel');watchStale($('activity-message'),'Loading…','Activity could not load. Reopen Research-Control.cmd and use the newly opened tab. Opening the panel does not start or stop research.');};
if(!$('decisions-panel').hidden)watchStale($('review-message'),'Loading…','Decisions could not load. Reopen Research-Control.cmd and use the newly opened tab. Opening the panel does not start or stop research.');

// Shared "needs your decision" feed: reviews.js contributes findings+catalog groups, visuals.js contributes
// visual proposals. Each group is an array of {rank,created_at,el}; higher rank and newer sort first.
window.__pending={};
function node(tag,text,className){const n=document.createElement(tag);if(text!==undefined&&text!==null)n.textContent=text;if(className)n.className=className;return n;}
window.renderDecisionFeed=function(){
  const box=$('decision-feed');if(!box)return;
  const groups=window.__pending||{};
  const items=[].concat(groups.catalog||[],groups.findings||[],groups.visuals||[]);
  items.sort((a,b)=>(b.rank-a.rank)||String(b.created_at||'').localeCompare(String(a.created_at||'')));
  box.replaceChildren();
  if(!items.length){box.append(node('p','Nothing needs a decision right now.','empty-inbox'));return;}
  for(const it of items)box.append(it.el);
};

// Full-screen preview overlay on phones (<720px); desktop keeps the inline 60vh frame.
window.isPhoneWidth=()=>window.matchMedia('(max-width:719px)').matches;
window.openPreview=function(src,title){
  const overlay=$('preview-overlay'),body=$('preview-overlay-body');
  body.replaceChildren();
  const f=document.createElement('iframe');f.src=src;f.title=title||'Site preview';f.loading='lazy';f.className='preview-frame';
  body.append(f);overlay.hidden=false;
};
$('preview-overlay-close').onclick=()=>{$('preview-overlay').hidden=true;$('preview-overlay-body').replaceChildren();};

// GPU charts default closed on phones; the toggle button (CSS-shown only under 720px) flips them open.
$('gpu-toggle').onclick=()=>{
  const shown=$('gpu-charts').classList.toggle('shown');
  $('gpu-toggle').textContent=shown?'Hide GPU charts':'Show GPU charts';
};
// Live batch output starts open on desktop, closed on phones; stays in sync if the window is resized
// across the breakpoint, unless the operator has already toggled it by hand.
let logUserToggled=false;
$('log-details').querySelector('summary').addEventListener('click',()=>{logUserToggled=true;});
function syncLogDetails(){if(!logUserToggled)$('log-details').open=window.matchMedia('(min-width:720px)').matches;}
syncLogDetails();
window.addEventListener('resize',syncLogDetails);

async function send(action,value){
  const r=await fetch(action,{method:'POST',headers:{'Content-Type':'application/json','X-Session-Key':key},body:JSON.stringify(value)});
  const data=await r.json();if(!r.ok)throw new Error(data.error||'Request failed');return data;
}
// Starting and stopping a session are mutations like any other, so they report through the toast as
// well as the form line: on a phone the form line is off-screen behind the tab bar (2026-09-11).
function sessionReport(text,kind){$('message').textContent=text;notify(text,kind);}
$('session-form').addEventListener('submit',async event=>{
  event.preventDefault();$('start').disabled=true;
  const checked=name=>Array.from(document.querySelectorAll(`input[name="${name}"]:checked`),e=>e.value);
  try{await send('start',{minutes:Number($('minutes').value),direction:$('direction').value,layers:checked('layers'),source_kinds:checked('source_kinds'),publish:$('publish').checked,idle_only:$('idle').checked,keep_awake:$('awake').checked});sessionReport('Session requested. The controller will report startup below.','ok');}
  catch(e){sessionReport(e.message,'error');$('start').disabled=false;}
});
$('stop').addEventListener('click',async()=>{try{await send('stop',{});sessionReport('Stop requested. Current work will finish safely.','ok');}catch(e){sessionReport(e.message,'error');}});
async function poll(){
  try{
    const r=await fetch('status');if(!r.ok)throw new Error();const d=await r.json(),s=d.session||{};
    $('connection').textContent='Connected locally';$('start').disabled=d.active||d.launching;$('stop').disabled=!d.active;
    $('state').textContent=s.state?((!d.active&&!['completed','stopped','cycle limit reached','interrupted','blocked','failed'].includes(s.state))?'Controller inactive — inspect diagnostics':s.state):'Ready when you are.';
    if(s.failure_reason)$('state').textContent+=' — '+s.failure_reason;
    $('elapsed').textContent=s.duration_seconds?`${Math.floor((s.elapsed_seconds||0)/60)} / ${Math.round(s.duration_seconds/60)} min`:'—';
    $('batches').textContent=`${s.batches||0} / ${s.failed_batches||0}`;
    $('progress').value=s.duration_seconds?Math.min(100,100*s.elapsed_seconds/s.duration_seconds):0;
    if(s.options)$('mode').textContent=`${s.options.direction} · ${s.options.publish?'Eligible monitoring publication enabled':'Private proposals'} · Layers: ${(s.options.layers||['all']).join(', ')}`;
    if($('log').textContent!==d.log){$('log').textContent=d.log||'No session output yet.';$('log').scrollTop=$('log').scrollHeight;}
    $('diagnostics').textContent=d.controller_log||'No controller diagnostics.';
    const q=d.discovery||{};$('discovery').textContent=q.id?`Latest discovery batch: ${q.status}; ${q.documents_screened||0} documents screened; ${q.proposals_queued||0} proposals. ${q.started_at||''}`:'';
    $('schedule-notice').textContent=d.schedule_notice?`${d.schedule_notice.at}: ${d.schedule_notice.reason}`:'';
    if(d.notification)$('schedule-notice').textContent+=` Telegram completion summary: ${d.notification.status}.`;
    if(d.visual_assessment)$('schedule-notice').textContent+=` Visual recommendations: ${d.visual_assessment.state}${d.visual_assessment.state==='assessing'?' (private review, graphics unchanged)':''}.`;
  }catch(e){$('connection').textContent='Connection unavailable';}
  setTimeout(poll,document.hidden?10000:2000);
}
poll();

function gpuPlot(id,samples,field,end,max,unit){
  const svg=$(id),ns='http://www.w3.org/2000/svg',begin=end-600000;
  const points=samples.filter(s=>s.timestamp_ms>=begin&&s.timestamp_ms<=end);
  svg.replaceChildren();
  function el(tag,attrs,text){const n=document.createElementNS(ns,tag);for(const [k,v] of Object.entries(attrs))n.setAttribute(k,v);if(text)n.textContent=text;svg.append(n);return n;}
  const y=v=>92-76*v/max,x=t=>38+470*(t-begin)/600000;
  for(const v of [0,max/2,max]){
    el('path',{d:`M38 ${y(v)}H508`,class:'gpu-grid'});
    el('text',{x:30,y:y(v)+4,'text-anchor':'end'},`${v}${unit}`);
  }
  el('text',{x:38,y:118},'10 min ago');el('text',{x:508,y:118,'text-anchor':'end'},'Now');
  let path='',previous=null;
  for(const s of points){
    const value=s[field];
    if(!Number.isFinite(value)){previous=null;continue;}
    path+=`${previous&&s.timestamp_ms-previous.timestamp_ms<=6000?'L':'M'}${x(s.timestamp_ms).toFixed(1)} ${y(value).toFixed(1)} `;
    // Individual points remain visible even before a line can be drawn.
    el('circle',{cx:x(s.timestamp_ms),cy:y(value),r:1.8,class:'gpu-point'});
    previous=s;
  }
  el('path',{d:path,class:'gpu-line'});
}
async function pollGpu(){
  try{
    if(!document.hidden){
      const response=await fetch('gpu');if(!response.ok)throw new Error();
      const data=await response.json(),last=data.latest,samples=data.samples;
      $('gpu-status').textContent=last.status==='live'?'Live · 2 s':last.status==='partial'?'Some readings unavailable':'Telemetry unavailable';
      $('gpu-name').textContent=`${last.name||'GPU 0'} · Device-wide readings`;
      $('gpu-usage').textContent=last.utilization===null?'Unavailable':`${last.utilization}%`;
      $('gpu-temperature').textContent=last.temperature===null?'Unavailable':`${last.temperature} °C`;
      const end=Math.max(Date.now(),last.timestamp_ms);
      gpuPlot('gpu-usage-chart',samples,'utilization',end,100,'%');
      const peak=Math.max(100,...samples.filter(s=>s.timestamp_ms>=end-600000).map(s=>s.temperature||0));
      gpuPlot('gpu-temperature-chart',samples,'temperature',end,Math.ceil(peak/20)*20,'°');
    }
  }catch(e){$('gpu-status').textContent='Telemetry unavailable';$('gpu-usage').textContent='Unavailable';$('gpu-temperature').textContent='Unavailable';}
  setTimeout(pollGpu,document.hidden?10000:2000);
}
pollGpu();
