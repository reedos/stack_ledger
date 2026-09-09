/* Maintained interaction over reviewed snapshots. No live third-party data or model HTML. */
'use strict';
const explorerSnapshots=[...document.querySelectorAll('[data-explorer-snapshot]')];
let updateProjectMap=null;
function mapProjectEvidence(p){
 const ids=new Set(p.observations),records=data.observations.filter(o=>!o.superseded_by&&(ids.has(o.id)||metricOf(o.metric).project===p.id));
 return records.length?`<details><summary>Capacity, investment &amp; jobs evidence (${records.length})</summary><p>Separate periods and measurement bases; these values are not added together.</p>${records.map(quantityEvidence).join('')}</details>`:'<p class="chart-footnote">No reviewed quantitative disclosure attached. Unknown is not zero.</p>';
}
function projectMapFilter(p){
 const owner=document.getElementById('map-company')?.value||'all',coverage=document.getElementById('map-coverage')?.value||'all';
 return (owner==='all'||p.owner===owner)&&(coverage==='all'||(coverage==='mapped'?!!p.map_location:!p.map_location));
}
function enhanceExplorers(){
 for(const section of explorerSnapshots){
  if(section.isConnected)continue;
  if(section.id==='project-map')document.getElementById('project-count')?.after(section);
  else if(section.id==='model-capabilities')document.getElementById('layer-diagram')?.after(section);
  else if(section.id==='capital-buildout')document.querySelector('#main .detail-layout')?.after(section);
 }
 document.querySelectorAll('[data-enhanced-controls]').forEach(el=>el.hidden=false);
 if(document.getElementById('project-map'))setupProjectMap();
 if(document.getElementById('model-capabilities'))setupCapabilities();
}
function setupProjectMap(){
 const host=document.getElementById('project-map'),svg=host.querySelector('svg'),points=svg.querySelector('.map-points'),selection=host.querySelector('#map-selection');
 const owners=host.querySelector('#map-company');
 [...new Set(delivery.projects.map(p=>p.owner))].sort().forEach(owner=>{const option=document.createElement('option');option.value=owner;option.textContent=owner;owners.append(option);});
 let view=[155,108,200,95],groups=[],selected=null;
 const ns='http://www.w3.org/2000/svg';
 function setView(v){
  const width=Math.max(12,Math.min(1080,v[2])),height=width*(svg.clientHeight/Math.max(1,svg.clientWidth));
  view=[Math.max(0,Math.min(1080-width,v[0])),Math.max(0,Math.min(540-height,v[1])),width,height];
  svg.setAttribute('viewBox',view.join(' '));draw();
 }
 function inspect(key){
  const group=groups.find(g=>g.key===key);if(!group)return;selected=key;
  selection.innerHTML=`<h3>${esc(group.location.label)}</h3><p>Approximate ${esc(group.location.precision)} location · ${sourceLink(group.location.source)}. These records may share a locality without sharing a facility.</p>`+group.projects.map(p=>`<div class="map-project"><a href="#project-${esc(p.id)}"><strong>${esc(p.name)} ↗</strong></a><p>${esc(layerOf(p.layer).name)} · ${esc(stageNames[p.stage])}</p><p>${esc(p.owner)}</p><p>${esc(p.milestones.at(-1).summary)}</p><p class="chart-footnote">${sourceLink(p.milestones.at(-1).source)} · ${dateLabel(p.milestones.at(-1).date)}</p>${mapProjectEvidence(p)}</div>`).join('');
 }
 function draw(){
  points.replaceChildren();
  const radius=view[2]/100;
  for(const group of groups){
   const g=group.location,node=document.createElementNS(ns,'g'),circle=document.createElementNS(ns,'circle');
   node.classList.add('map-marker');node.dataset.location=group.key;node.setAttribute('transform',`translate(${(g.longitude+180)*3} ${(90-g.latitude)*3})`);
   node.setAttribute('role','button');node.setAttribute('tabindex','0');node.setAttribute('aria-label',`${g.label}: ${group.projects.length} project records`);
   circle.setAttribute('r',radius);circle.setAttribute('fill',new Set(group.projects.map(p=>p.layer)).size>1?'#edf0e4':layerOf(group.projects[0].layer).color);circle.setAttribute('stroke','#0d1512');circle.setAttribute('stroke-width',radius*.2);node.append(circle);
   if(group.projects.length>1){const text=document.createElementNS(ns,'text');text.textContent=group.projects.length;text.setAttribute('text-anchor','middle');text.setAttribute('dy','.35em');text.style.fontSize=`${radius*1.1}px`;node.append(text);}
   node.addEventListener('click',()=>inspect(group.key));node.addEventListener('keydown',event=>{if(['Enter',' '].includes(event.key)){event.preventDefault();inspect(group.key);}});points.append(node);
  }
 }
 updateProjectMap=ps=>{
  const grouped=new Map();
  for(const p of ps){const g=p.map_location;if(!g)continue;const key=`${g.latitude},${g.longitude}`;if(!grouped.has(key))grouped.set(key,{key,location:g,projects:[]});grouped.get(key).projects.push(p);}
  groups=[...grouped.values()];const mapped=ps.filter(p=>p.map_location).length;
  host.querySelector('#map-count').textContent=`${mapped} mapped of ${ps.length} matching records · ${ps.length-mapped} not mapped · ${groups.length} shared locations. Use World to see international locations.`;
  draw();if(selected&&groups.some(g=>g.key===selected))inspect(selected);else{selected=null;selection.textContent=ps.length?'Select a marker to inspect projects. Place/county points are approximate; sizes do not represent capacity or jobs.':'No projects match these filters.';}
 };
 document.addEventListener('stack:projects',event=>updateProjectMap(event.detail));
 for(const id of ['map-company','map-coverage'])host.querySelector('#'+id).addEventListener('change',()=>document.getElementById('project-search').dispatchEvent(new Event('input',{bubbles:true})));
 host.querySelector('#map-us').addEventListener('click',()=>setView([155,100,205,100]));
 host.querySelector('#map-world').addEventListener('click',()=>setView([0,0,1080,540]));
 const zoom=factor=>{const width=view[2]*factor;setView([view[0]+(view[2]-width)/2,view[1]+(view[3]-view[3]*factor)/2,width,view[3]*factor]);};
 host.querySelector('#map-zoom-in').addEventListener('click',()=>zoom(.65));host.querySelector('#map-zoom-out').addEventListener('click',()=>zoom(1/.65));
 svg.dataset.interactive='true';svg.setAttribute('tabindex','0');svg.setAttribute('role','group');svg.setAttribute('aria-label','Project map. Arrow keys pan. Use the zoom buttons or drag to explore.');
 let drag=null;
 svg.addEventListener('pointerdown',event=>{if(event.target.closest('.map-marker'))return;drag={x:event.clientX,y:event.clientY,view:[...view]};svg.setPointerCapture(event.pointerId);});
 svg.addEventListener('pointermove',event=>{if(!drag)return;setView([drag.view[0]-(event.clientX-drag.x)*drag.view[2]/svg.clientWidth,drag.view[1]-(event.clientY-drag.y)*drag.view[3]/svg.clientHeight,drag.view[2],drag.view[3]]);});
 for(const name of ['pointerup','pointercancel','lostpointercapture'])svg.addEventListener(name,()=>{drag=null;});
 svg.addEventListener('keydown',event=>{if(event.target!==svg)return;const moves={ArrowLeft:[-1,0],ArrowRight:[1,0],ArrowUp:[0,-1],ArrowDown:[0,1]};if(moves[event.key]){event.preventDefault();const [dx,dy]=moves[event.key];setView([view[0]+dx*view[2]*.15,view[1]+dy*view[3]*.15,view[2],view[3]]);}});
 setView(view);document.getElementById('project-search').dispatchEvent(new Event('input',{bubbles:true}));
}
function setupCapabilities(){
 const host=document.getElementById('model-capabilities'),c=expansion.capabilities,svg=host.querySelector('svg'),select=host.querySelector('#eci-model'),developer=host.querySelector('#eci-developer'),access=host.querySelector('#eci-access'),frontierOnly=host.querySelector('#eci-frontier-only'),selection=host.querySelector('#eci-selection');
 if(!c)return;
 const all=c.rows;[...new Set(all.map(r=>r.organization))].sort().forEach(name=>{const opt=document.createElement('option');opt.value=name;opt.textContent=name;developer.append(opt);});
 const day=value=>Math.floor(Date.parse(value+'T00:00:00Z')/86400000)+719163;
 const xp=value=>48+(day(value)-Number(svg.dataset.start))/(Number(svg.dataset.end)-Number(svg.dataset.start))*550;
 const yp=value=>260-(value-Number(svg.dataset.floor))/(Number(svg.dataset.ceiling)-Number(svg.dataset.floor))*220;
 const tableRows=[...host.querySelectorAll('#eci-table tr')];let shown=[];
 function inspect(id){
  const r=shown.find(r=>r.id===id);if(!r)return;select.value=id;
  svg.querySelector('.eci-uncertainty')?.remove();
  if(r.low!==null){const line=document.createElementNS('http://www.w3.org/2000/svg','path');line.classList.add('eci-uncertainty');const x=xp(r.released),a=yp(r.low),b=yp(r.high);line.setAttribute('d',`M${x} ${a}V${b}M${x-5} ${a}H${x+5}M${x-5} ${b}H${x+5}`);svg.append(line);}
  selection.innerHTML=`<strong>${esc(r.name)} · ECI ${number(r.score)}</strong><p>${esc(r.organization)} · Released ${esc(r.released)} · ${esc(r.access)}</p><p>${r.low===null?'Calibration anchor; Epoch supplies no uncertainty interval.':`90% confidence interval: ${number(r.low)}–${number(r.high)}. The white whisker marks this model’s interval.`}</p><p class="chart-footnote">${shown.length} models match the controls. All scores use the snapshot retrieved ${dateLabel(c.retrieved_at)}; a release date is not the evaluation date.</p>`;
 }
 function update(){
  const filtered=all.filter(r=>(developer.value==='all'||r.organization===developer.value)&&(access.value==='all'||r.access===access.value));
  let best=-Infinity;const frontier=[];
  for(const r of [...filtered].sort((a,b)=>a.released.localeCompare(b.released)||b.score-a.score)){if(r.score>best){frontier.push(r);best=r.score;}}
  const ids=new Set(frontier.map(r=>r.id));shown=filtered.filter(r=>!frontierOnly.checked||ids.has(r.id));const visible=new Set(shown.map(r=>r.id));
  svg.querySelectorAll('.eci-point').forEach(p=>{p.style.display=visible.has(p.dataset.model)?'':'none';});
  let path='';frontier.forEach((r,i)=>{path+=`${i?'H':'M'}${xp(r.released)}${i?'V':' '}${yp(r.score)}`;});svg.querySelector('.eci-frontier').setAttribute('d',path);
  select.replaceChildren();for(const r of [...shown].sort((a,b)=>b.score-a.score)){const opt=document.createElement('option');opt.value=r.id;opt.textContent=`${r.name} · ${number(r.score)}`;select.append(opt);}
  // Keep the accessible table synchronized, without modifying the accepted snapshot.
  const tbody=host.querySelector('#eci-table');tbody.replaceChildren(...tableRows.filter(row=>visible.has(row.dataset.model)));
  if(shown.length)inspect(select.value);else{selection.textContent='No models match these filters. Missing results are not zero capability.';svg.querySelector('.eci-uncertainty')?.remove();}
 }
 svg.querySelectorAll('.eci-point').forEach(p=>{p.dataset.interactive='true';p.addEventListener('click',()=>inspect(p.dataset.model));});
 for(const el of [developer,access,frontierOnly])el.addEventListener('change',update);
 select.addEventListener('change',()=>inspect(select.value));update();
}
