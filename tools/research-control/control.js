'use strict';
const $=id=>document.getElementById(id);
const key=location.pathname.split('/')[1];
// An already-running Python server may serve new HTML without the new review route.
// reviews.js replaces these fallbacks once it loads successfully.
function reviewFallback(review){
  $('session-panel').hidden=review;$('review-panel').hidden=!review;
  $('session-tab').setAttribute('aria-pressed',String(!review));$('review-tab').setAttribute('aria-pressed',String(review));
  if(review)$('review-message').textContent='Review controls could not load. Reopen Research-Control.cmd and use the newly opened tab to load the current panel server. Opening the panel does not start or stop research.';
}
$('session-tab').onclick=()=>reviewFallback(false);
$('review-tab').onclick=()=>reviewFallback(true);
async function send(action,value){
  const r=await fetch(action,{method:'POST',headers:{'Content-Type':'application/json','X-Session-Key':key},body:JSON.stringify(value)});
  const data=await r.json();if(!r.ok)throw new Error(data.error||'Request failed');return data;
}
$('session-form').addEventListener('submit',async event=>{
  event.preventDefault();$('start').disabled=true;
  const checked=name=>Array.from(document.querySelectorAll(`input[name="${name}"]:checked`),e=>e.value);
  try{await send('start',{minutes:Number($('minutes').value),direction:$('direction').value,layers:checked('layers'),source_kinds:checked('source_kinds'),publish:$('publish').checked,idle_only:$('idle').checked,keep_awake:$('awake').checked});$('message').textContent='Session requested. The controller will report startup below.';}
  catch(e){$('message').textContent=e.message;$('start').disabled=false;}
});
$('stop').addEventListener('click',async()=>{try{await send('stop',{});$('message').textContent='Stop requested. Current work will finish safely.';}catch(e){$('message').textContent=e.message;}});
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
  setTimeout(poll,2000);
}
poll();

function gpuPlot(id,samples,field,end,max,unit){
  const svg=$(id),ns='http://www.w3.org/2000/svg',begin=end-600000;
  const points=samples.filter(s=>s.timestamp_ms>=begin&&s.timestamp_ms<=end);
  svg.replaceChildren();
  function node(tag,attrs,text){const n=document.createElementNS(ns,tag);for(const [k,v] of Object.entries(attrs))n.setAttribute(k,v);if(text)n.textContent=text;svg.append(n);return n;}
  const y=v=>92-76*v/max,x=t=>38+470*(t-begin)/600000;
  for(const v of [0,max/2,max]){
    node('path',{d:`M38 ${y(v)}H508`,class:'gpu-grid'});
    node('text',{x:30,y:y(v)+4,'text-anchor':'end'},`${v}${unit}`);
  }
  node('text',{x:38,y:118},'10 min ago');node('text',{x:508,y:118,'text-anchor':'end'},'Now');
  let path='',previous=null;
  for(const s of points){
    const value=s[field];
    if(!Number.isFinite(value)){previous=null;continue;}
    path+=`${previous&&s.timestamp_ms-previous.timestamp_ms<=6000?'L':'M'}${x(s.timestamp_ms).toFixed(1)} ${y(value).toFixed(1)} `;
    // Individual points remain visible even before a line can be drawn.
    node('circle',{cx:x(s.timestamp_ms),cy:y(value),r:1.8,class:'gpu-point'});
    previous=s;
  }
  node('path',{d:path,class:'gpu-line'});
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
  setTimeout(pollGpu,2000);
}
pollGpu();
