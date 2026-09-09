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
 return (owner==='all'||p.owner===owner)&&(coverage==='all'||(coverage==='mapped'?hasMapLocation(p):!hasMapLocation(p)));
}
function enhanceExplorers(){
 for(const section of explorerSnapshots){
  if(section.isConnected)continue;
  if(section.id==='project-map')document.getElementById('project-count')?.after(section);
  else if(section.id==='model-capabilities')document.getElementById('layer-diagram')?.after(section);
  else if(section.id==='capital-buildout')document.querySelector('#main .detail-layout')?.after(section);
  else if(section.id==='industry-momentum')document.querySelector('#main .page-hero')?.after(section);
 }
 document.querySelectorAll('[data-enhanced-controls]').forEach(el=>el.hidden=false);
 if(document.getElementById('project-map'))setupProjectMap();
 if(document.getElementById('model-capabilities'))setupCapabilities();
}
function hasMapLocation(p){return !!p.map_location||!!p.map_locations?.length;}
function mapProjectRecords(ps){return ps.flatMap(p=>p.map_locations?p.map_locations.map(g=>({...p,map_location:g.location,stage:g.stage,map_note:g.note,map_source:g.source,multi_location:true})):p.map_location?[p]:[]);}
function mapPhase(stage){return stage==='status-unverified'?'unverified':stage==='office'?'office':stage==='operating'?'operating':['announced','permitting','site-selected'].includes(stage)?'planned':stage==='pilot'?'pilot':stage==='delayed'?'delayed':'delivery';}
function mapSymbol(records,r){
 const total=records.length,segments=new Map();for(const p of records){const key=p.layer+'|'+mapPhase(p.stage);segments.set(key,(segments.get(key)||0)+1);}
 let html=`<circle class="map-hit" r="${r*1.35}" fill="transparent"/><circle class="map-core" r="${r}" fill="#101d18"/>`,angle=-Math.PI/2;
 for(const [key,count] of segments){
  const [layer,phase]=key.split('|'),color=layerOf(layer).color,span=count/total*Math.PI*2,gap=segments.size>1?.045:0;
  const a=angle+gap,b=angle+span-gap;angle+=span;
  const cls=`map-segment phase-${phase}`,attrs=`class="${cls}" stroke="${color}" stroke-width="${r*.18}" fill="none"`;
  if(segments.size===1)html+=`<circle r="${r*.88}" ${attrs}/>`;
  else html+=`<path d="M${Math.cos(a)*r*.88} ${Math.sin(a)*r*.88} A${r*.88} ${r*.88} 0 ${span>Math.PI?1:0} 1 ${Math.cos(b)*r*.88} ${Math.sin(b)*r*.88}" ${attrs}/>`;
  if(total===1){
   if(phase==='office')html+=`<path class="map-office-glyph" d="M0 ${-r*.52}L${r*.52} 0 0 ${r*.52} ${-r*.52} 0Z" fill="${color}"/>`;
   else html+=`<circle class="map-stage-fill phase-${phase}" r="${r*.60}" fill="${color}"/>`;
  }
 }
 if(total>1)html+=`<text text-anchor="middle" dy=".35em" style="font-size:${r*.9}px">${total}</text>`;
 html+=`<circle class="map-focus-ring" r="${r*1.28}" fill="none"/>`;return html;
}
function setupProjectMap(){
 const host=document.getElementById('project-map'),svg=host.querySelector('svg'),points=svg.querySelector('.map-points'),selection=host.querySelector('#map-selection'),owners=host.querySelector('#map-company');
 // Move the original controls so map and list keep one state and one event path.
 const layerFilters=document.querySelector('[aria-label="Filter projects by layer"]'),projectTools=document.getElementById('project-search').closest('.directory-tools');
 layerFilters.classList.add('map-layer-filters','capital-legend');host.querySelector('.map-overview .capital-legend').replaceWith(layerFilters);
 layerFilters.querySelector('[data-project-layer="all"]').textContent='All layers';
 host.querySelector('.explorer-controls').prepend(projectTools);
 const searchLabel=projectTools.querySelector('label[for="project-search"]'),searchInput=projectTools.querySelector('#project-search');
 searchLabel.classList.remove('sr-only');searchLabel.textContent='Search Projects:';searchLabel.append(searchInput);
 searchInput.placeholder='Wisconsin, grid, geothermal, Meta…';
 layerFilters.querySelectorAll('[data-project-layer]').forEach(button=>{const layer=layerOf(button.dataset.projectLayer);if(layer)button.style.setProperty('--layer-color',layer.color);});
 const offices=ecosystem.companies.flatMap(c=>(c.map_offices||[]).map(o=>({id:c.id,name:o.name,owner:c.name,layer:'models',stage:'office',office_kind:o.kind,map_location:o.location,map_note:o.note,map_source:o.source})));
 [...new Set([...delivery.projects.map(p=>p.owner),...offices.map(p=>p.owner)])].sort().forEach(owner=>{const option=document.createElement('option');option.value=owner;option.textContent=owner;owners.append(option);});
 let view=[155,112,205,98],groups=[],displayGroups=[],selected=null;
 const ns='http://www.w3.org/2000/svg';
 function setView(v){
  const width=Math.max(12,Math.min(1080,v[2])),height=width*(svg.clientHeight/Math.max(1,svg.clientWidth));
  const centeredY=v[1]+(v[3]-height)/2;
  view=[Math.max(0,Math.min(1080-width,v[0])),Math.max(0,Math.min(540-height,centeredY)),width,height];svg.setAttribute('viewBox',view.join(' '));draw();
 }
 function inspect(key){
  const group=displayGroups.find(g=>g.key===key);if(!group)return;selected=key;selection.classList.add('has-selection');
  points.querySelectorAll('.map-marker').forEach(n=>n.classList.toggle('is-selected',n.dataset.location===key));
  const projectCount=new Set(group.projects.filter(p=>!p.office_kind).map(p=>p.id)).size,officeCount=group.projects.filter(p=>p.office_kind).length;
  selection.innerHTML=`<h3>${esc(group.location.label)}</h3><p>${projectCount} project/program records · ${officeCount} developer office locations</p><p class="chart-footnote">${group.cluster?'Nearby locations grouped at this zoom; the marker center is not a facility. Zoom in to separate them.':`Approximate ${esc(group.location.precision)} location · ${sourceLink(group.location.source)}.`}</p>`+group.projects.map(p=>{
   const stage=p.office_kind?p.office_kind.replaceAll('-',' '):stageNames[p.stage];
   const title=p.office_kind?companyLink(p.id):`<a href="#project-${esc(p.id)}">${esc(p.name)} ↗</a>`;
   return `<div class="map-project" style="--map-accent:${layerOf(p.layer).color}"><strong>${title}</strong><p><span class="map-stage-label">${esc(stage)}</span> · ${esc(layerOf(p.layer).name)}</p><p>${esc(p.owner)}</p><p class="chart-footnote">${esc(p.map_location.label)} · ${esc(p.map_location.precision)} point · ${sourceLink(p.map_location.source)}</p><p>${esc(p.map_note||p.milestones.at(-1).summary)}</p><p class="chart-footnote">${sourceLink(p.map_source||p.milestones.at(-1).source)}</p>${p.office_kind?'':mapProjectEvidence(p)}</div>`;
  }).join('');
 }
 function draw(){
  points.replaceChildren();const unit=view[2]/Math.max(1,svg.clientWidth),markerScale=svg.clientWidth<600?.7:1,radius=n=>Math.min(22,7*Math.sqrt(n))*unit*markerScale;
  const clusters=[];
  for(const group of groups){
   const near=clusters.find(c=>Math.hypot((c.location.longitude-group.location.longitude)*3,(c.location.latitude-group.location.latitude)*3)<radius(c.projects.length)+radius(group.projects.length)+3*unit);
   if(!near){clusters.push({...group,projects:[...group.projects],members:[group.key]});continue;}
   const n=near.members.length;near.members.push(group.key);near.projects.push(...group.projects);near.cluster=true;
   near.location={latitude:(near.location.latitude*n+group.location.latitude)/(n+1),longitude:(near.location.longitude*n+group.location.longitude)/(n+1),label:`${n+1} nearby locations`};near.key=near.members.join('|');
  }
  displayGroups=clusters;
  for(const group of displayGroups){
   const g=group.location,node=document.createElementNS(ns,'g'),r=radius(group.projects.length);node.classList.add('map-marker');node.classList.toggle('is-selected',group.key===selected);node.dataset.location=group.key;
   node.setAttribute('transform',`translate(${(g.longitude+180)*3} ${(90-g.latitude)*3})`);node.setAttribute('role','button');node.setAttribute('tabindex','0');
   node.setAttribute('aria-label',`${g.label}: ${group.projects.length} mapped records; ${[...new Set(group.projects.map(p=>layerOf(p.layer).name))].join(', ')}`);
   node.innerHTML=mapSymbol(group.projects,r);node.addEventListener('click',()=>inspect(group.key));node.addEventListener('keydown',event=>{if(['Enter',' '].includes(event.key)){event.preventDefault();inspect(group.key);}});points.append(node);
  }
 }
 updateProjectMap=ps=>{
  const layer=new URLSearchParams(location.search).get('layer')||'all',stage=document.getElementById('project-stage').value,q=document.getElementById('project-search').value.toLowerCase();
  const officeRows=host.querySelector('#map-offices').checked&&['all','models'].includes(layer)&&stage==='all'&&host.querySelector('#map-coverage').value!=='unmapped'?offices.filter(p=>(owners.value==='all'||p.owner===owners.value)&&`${p.name} ${p.owner} ${p.map_location.label}`.toLowerCase().includes(q)):[];
  const projectRows=mapProjectRecords(ps).filter(p=>(stage==='all'||p.stage===stage)&&`${p.name} ${p.owner} ${p.category} ${p.grid} ${p.multi_location?'':p.location} ${p.map_location.label} ${p.map_note||''}`.toLowerCase().includes(q)),grouped=new Map();
  for(const p of [...projectRows,...officeRows]){const g=p.map_location,key=`${g.latitude},${g.longitude}`;if(!grouped.has(key))grouped.set(key,{key,location:g,projects:[]});grouped.get(key).projects.push(p);}
  groups=[...grouped.values()];const mapped=new Set(projectRows.map(p=>p.id)).size;
  host.querySelector('#map-count').textContent=`${mapped} mapped of ${ps.length} matching project records · ${projectRows.length} project locality markers · ${officeRows.length} developer office locations (separate) · ${groups.length} distinct localities. Use World to see international locations.`;
  draw();if(selected&&displayGroups.some(g=>g.key===selected))inspect(selected);else{selected=null;selection.classList.remove('has-selection');selection.innerHTML='<p>Select a marker for its projects, delivery stages and location evidence. City/county points provide orientation; they are not facility boundaries or service-area outlines.</p>';}
 };
 document.addEventListener('stack:projects',event=>updateProjectMap(event.detail));
 for(const id of ['map-company','map-coverage','map-offices'])host.querySelector('#'+id).addEventListener('change',()=>document.getElementById('project-search').dispatchEvent(new Event('input',{bubbles:true})));
 host.querySelector('#map-us').addEventListener('click',()=>setView([155,112,205,98]));host.querySelector('#map-world').addEventListener('click',()=>setView([0,0,1080,540]));
 const zoom=factor=>{const width=view[2]*factor;setView([view[0]+(view[2]-width)/2,view[1]+(view[3]-view[3]*factor)/2,width,view[3]*factor]);};
 host.querySelector('#map-zoom-in').addEventListener('click',()=>zoom(.65));host.querySelector('#map-zoom-out').addEventListener('click',()=>zoom(1/.65));
 svg.dataset.interactive='true';svg.setAttribute('tabindex','0');svg.setAttribute('role','group');svg.setAttribute('aria-label','Project map. Arrow keys pan. Use zoom buttons or drag to explore.');
 let drag=null;
 svg.addEventListener('pointerdown',event=>{if(event.target.closest('.map-marker'))return;drag={x:event.clientX,y:event.clientY,view:[...view]};svg.setPointerCapture(event.pointerId);});
 svg.addEventListener('pointermove',event=>{if(!drag)return;setView([drag.view[0]-(event.clientX-drag.x)*drag.view[2]/svg.clientWidth,drag.view[1]-(event.clientY-drag.y)*drag.view[3]/svg.clientHeight,drag.view[2],drag.view[3]]);});
 for(const name of ['pointerup','pointercancel','lostpointercapture'])svg.addEventListener(name,()=>{drag=null;});
 svg.addEventListener('keydown',event=>{if(event.target!==svg)return;const moves={ArrowLeft:[-1,0],ArrowRight:[1,0],ArrowUp:[0,-1],ArrowDown:[0,1]};if(moves[event.key]){event.preventDefault();const [dx,dy]=moves[event.key];setView([view[0]+dx*view[2]*.15,view[1]+dy*view[3]*.15,view[2],view[3]]);}});
 let resizeWidth=svg.clientWidth;new ResizeObserver(()=>{if(svg.clientWidth!==resizeWidth){resizeWidth=svg.clientWidth;setView(view);}}).observe(svg);
 setView(view);document.getElementById('project-search').dispatchEvent(new Event('input',{bubbles:true}));
}
function setupCapabilities(){
 const host=document.getElementById('model-capabilities'),c=expansion.capabilities,svg=host.querySelector('svg'),select=host.querySelector('#eci-model'),colorBy=host.querySelector('#eci-color'),search=host.querySelector('#eci-search'),small=host.querySelector('#eci-small'),access=host.querySelector('#eci-access'),frontierOnly=host.querySelector('#eci-frontier-only'),selection=host.querySelector('#eci-selection'),legend=host.querySelector('#eci-legend');
 if(!c)return;
 const all=c.rows,counts=new Map();for(const r of all)counts.set(r.organization,(counts.get(r.organization)||0)+1);
 const palette=['#70c9ff','#f09b68','#cc9cf5','#f4d06f','#65d6ad','#ff8ea1','#9aa9ff','#c8df75','#c5a68d','#75d5dc','#f49cce','#a8b8c4','#ffa95e','#a4d89a','#d8b5f0','#e9c2ac'];
 const developers=[...counts.keys()].sort((a,b)=>counts.get(b)-counts.get(a)||a.localeCompare(b));
 const colors={organization:new Map(developers.map((name,i)=>[name,palette[i%palette.length]])),country:new Map([...new Set(all.map(r=>r.country))].sort().map((name,i)=>[name,palette[i%palette.length]])),access:new Map([['Open weights','#65d6ad'],['Closed weights','#cc9cf5'],['Other','#a8b8c4']])};
 colors.organization.set('Not listed by Epoch','#a8b8c4');colors.country.set('Not listed by Epoch','#a8b8c4');
 let hiddenGroups=new Set(),shown=[];
 const day=value=>Math.floor(Date.parse(value+'T00:00:00Z')/86400000)+719163;
 const xp=value=>48+(day(value)-Number(svg.dataset.start))/Math.max(1,Number(svg.dataset.end)-Number(svg.dataset.start))*550;
 const yp=value=>260-(value-Number(svg.dataset.floor))/Math.max(1,Number(svg.dataset.ceiling)-Number(svg.dataset.floor))*220;
 const tableRows=[...host.querySelectorAll('#eci-table tr')];
 function clearInspection(){
  select.value='';selection.hidden=true;selection.replaceChildren();
  svg.querySelector('.eci-uncertainty')?.remove();
  svg.querySelectorAll('.eci-point.is-selected').forEach(p=>p.classList.remove('is-selected'));
 }
 function inspect(id){
  clearInspection();const r=shown.find(r=>r.id===id);if(!r)return;select.value=id;selection.hidden=false;
  svg.querySelectorAll('.eci-point').forEach(p=>p.classList.toggle('is-selected',p.dataset.model===id));
  if(r.low!==null){const line=document.createElementNS('http://www.w3.org/2000/svg','path');line.classList.add('eci-uncertainty');const x=xp(r.released),a=yp(r.low),b=yp(r.high);line.setAttribute('d',`M${x} ${a}V${b}M${x-5} ${a}H${x+5}M${x-5} ${b}H${x+5}`);svg.append(line);}
  selection.innerHTML=`<strong>${esc(r.name)} · ECI ${number(r.score)}</strong><p>${esc(r.organization)} · ${esc(r.country)} (organization) · Released ${esc(r.released)} · ${esc(r.access)}</p><p>${r.low===null?'Calibration anchor; Epoch supplies no uncertainty interval.':`90% confidence interval: ${number(r.low)}–${number(r.high)}. The white whisker marks this model’s interval.`}</p><p class="chart-footnote">Snapshot retrieved ${dateLabel(c.retrieved_at)}; release dates are not evaluation dates. Country attribution follows Epoch, not training location.</p>`;
 }
 function candidates(){return all.filter(r=>(small.checked||(counts.get(r.organization)>3&&r.organization!=='Not listed by Epoch'))&&(access.value==='all'||r.access===access.value)&&`${r.name} ${r.organization} ${r.country}`.toLowerCase().includes(search.value.trim().toLowerCase()));}
 function update(){
  const key=colorBy.value,eligible=candidates(),groupCounts=new Map();for(const r of eligible)groupCounts.set(r[key],(groupCounts.get(r[key])||0)+1);
  const filtered=eligible.filter(r=>!hiddenGroups.has(r[key]));
  let best=-Infinity;const frontier=[];
  for(const r of [...filtered].sort((a,b)=>a.released.localeCompare(b.released)||b.score-a.score)){if(r.score>best){frontier.push(r);best=r.score;}}
  const ids=new Set(frontier.map(r=>r.id));shown=filtered.filter(r=>!frontierOnly.checked||ids.has(r.id));const visible=new Set(shown.map(r=>r.id)),byId=new Map(all.map(r=>[r.id,r]));
  svg.querySelectorAll('.eci-point').forEach(p=>{p.style.display=visible.has(p.dataset.model)?'':'none';p.setAttribute('fill',colors[key].get(byId.get(p.dataset.model)[key]));});
  let path='';frontier.forEach((r,i)=>{path+=`${i?'H':'M'}${xp(r.released)}${i?'V':' '}${yp(r.score)}`;});svg.querySelector('.eci-frontier').setAttribute('d',path);
  legend.replaceChildren();for(const [name,count] of [...groupCounts].sort((a,b)=>b[1]-a[1]||a[0].localeCompare(b[0]))){
   const button=document.createElement('button');button.type='button';button.dataset.group=name;button.style.setProperty('--series',colors[key].get(name));button.setAttribute('aria-pressed',String(!hiddenGroups.has(name)));button.title=`Toggle ${name}. Shift-click to show only this group.`;const swatch=document.createElement('i');button.append(swatch,document.createTextNode(`${name} · ${count}`));
   button.addEventListener('click',event=>{if(event.shiftKey)hiddenGroups=new Set([...groupCounts.keys()].filter(g=>g!==name));else if(hiddenGroups.has(name))hiddenGroups.delete(name);else hiddenGroups.add(name);update();[...legend.children].find(b=>b.dataset.group===name)?.focus({preventScroll:true});});legend.append(button);
  }
  const previous=select.value;const placeholder=document.createElement('option');placeholder.value='';placeholder.textContent='No model selected';select.replaceChildren(placeholder);for(const r of [...shown].sort((a,b)=>b.score-a.score)){const opt=document.createElement('option');opt.value=r.id;opt.textContent=`${r.name} · ${number(r.score)}`;select.append(opt);}select.disabled=!shown.length;
  const tbody=host.querySelector('#eci-table');tbody.replaceChildren(...tableRows.filter(row=>visible.has(row.dataset.model)));
  host.querySelector('#eci-filter-summary').textContent=`${shown.length} of ${all.length} models shown. ${small.checked?'All developer sizes eligible.':'Developers with 4+ models; smaller and unlisted developers hidden.'} Legend counts reflect matching models before group/frontier filtering. Click to toggle; Shift-click to isolate.`;
  if(shown.some(r=>r.id===previous))inspect(previous);else clearInspection();
  if(!shown.length){selection.hidden=false;selection.textContent='No models match these filters. Use Show all groups, change the search, or include smaller developers.';}
 }
 svg.querySelectorAll('.eci-point').forEach(p=>{p.dataset.interactive='true';});
 // Keep small marks readable while accepting clicks near their centers.
 svg.addEventListener('click',event=>{
  let closest=null,distance=event.pointerType==='touch'?18:10;
  svg.querySelectorAll('.eci-point').forEach(p=>{
   if(p.style.display==='none')return;
   const box=p.getBoundingClientRect(),d=Math.hypot(event.clientX-box.x-box.width/2,event.clientY-box.y-box.height/2);
   if(d<distance){distance=d;closest=p.dataset.model;}
  });
  if(closest)inspect(closest);
 });
 for(const el of [small,access,frontierOnly])el.addEventListener('change',update);
 search.addEventListener('input',update);colorBy.addEventListener('change',()=>{hiddenGroups.clear();update();});
 host.querySelector('#eci-show-all').addEventListener('click',()=>{hiddenGroups.clear();update();});
 host.querySelector('#eci-hide-all').addEventListener('click',()=>{hiddenGroups=new Set(candidates().map(r=>r[colorBy.value]));update();});
 host.querySelector('#eci-reset').addEventListener('click',()=>{clearInspection();hiddenGroups.clear();colorBy.value='organization';small.checked=false;search.value='';access.value='all';frontierOnly.checked=false;update();});
 select.addEventListener('change',()=>inspect(select.value));update();
}
