/* Maintained presentation only. Filtering, evidence, exports and research roles are unchanged. */
'use strict';
const browsingPagers=[];
function revealResearchAnchor(){
 let id;try{id=decodeURIComponent(location.hash.slice(1));}catch{return;}
 if(!id)return;
 const target=document.getElementById(id);if(!target)return;
 for(const pager of browsingPagers)pager.reveal(target);
 for(let node=target;node;node=node.parentElement)if(node.tagName==='DETAILS')node.open=true;
 requestAnimationFrame(()=>target.scrollIntoView({block:'start'}));
}
function paginateResearch(container,selector,size,label,{search=false}={}){
 if(!container||container.dataset.paged)return;
 container.dataset.paged='true';
 const shell=container.closest('.table-scroll')||container;
 const controls=document.createElement('div');controls.className='browse-controls';
 const caption=document.createElement('span');caption.className='browse-count';caption.setAttribute('role','status');
 const previous=document.createElement('button'),next=document.createElement('button');
 for(const [button,text] of [[previous,'Previous'],[next,'Next']]){button.type='button';button.textContent=text;button.setAttribute('aria-label',`${text} ${label.toLowerCase()}`);}
 const buttons=document.createElement('div');buttons.className='browse-buttons';buttons.append(previous,next);
 controls.append(caption,buttons);shell.before(controls);
 let index=0,query='';
 const all=()=>[...container.querySelectorAll(selector)];
 const matches=()=>all().filter(el=>!query||el.textContent.toLowerCase().includes(query));
 const paint=()=>{const items=matches();index=Math.max(0,Math.min(index,Math.ceil(items.length/size)-1));
  const shown=new Set(items.slice(index*size,(index+1)*size));all().forEach(el=>el.hidden=!shown.has(el));
  caption.textContent=items.length?`${label}: ${index*size+1}–${Math.min((index+1)*size,items.length)} of ${items.length}`:`${label}: no matches`;
  previous.disabled=index===0;next.disabled=(index+1)*size>=items.length;
 };
 const change=delta=>{index+=delta;paint();controls.scrollIntoView({block:'start'});(delta>0&&next.disabled?previous:delta<0&&previous.disabled?next:delta>0?next:previous).focus({preventScroll:true});};
 previous.addEventListener('click',()=>change(-1));next.addEventListener('click',()=>change(1));
 if(search){const input=document.createElement('input');input.type='search';input.className='search';input.placeholder=`Search ${label.toLowerCase()}`;input.setAttribute('aria-label',input.placeholder);controls.prepend(input);input.addEventListener('input',()=>{query=input.value.trim().toLowerCase();index=0;paint();});}
 new MutationObserver(()=>{index=0;paint();}).observe(container,{childList:true});
 browsingPagers.push({reveal(target){const position=matches().findIndex(el=>el===target||el.contains(target));if(position>=0){index=Math.floor(position/size);paint();}}});
 paint();
}
function disclosureAround(nodes,title){
 const list=nodes.filter(Boolean);if(!list.length)return;
 const details=document.createElement('details');details.className='browse-disclosure';
 const summary=document.createElement('summary');summary.textContent=title;details.append(summary);
 list[0].before(details);list.forEach(el=>details.append(el));return details;
}
function compactCompanies(){
 document.querySelectorAll('#company-results .company-card:not([data-compact])').forEach(card=>{
  card.dataset.compact='true';
  disclosureAround([...card.children].filter(el=>el.matches('.company-scope,.chart-footnote,.company-source,.company-measures')),'Evidence, scope & additional measures');
 });
}
function compactProjects(){
 document.querySelectorAll('#project-results .delivery-card:not([data-compact])').forEach(card=>{
  card.dataset.compact='true';
  const quantities=card.querySelector('.delivery-quantities');
  const extra=document.createElement('div');extra.className='delivery-quantities';
  [...quantities.children].slice(1).forEach(el=>extra.append(el));
  const nodes=[...card.children].filter(el=>el.matches('.delivery-facts,.project-measures,.power-basis-note'));
  if(extra.children.length){quantities.after(extra);nodes.unshift(extra);}
  disclosureAround(nodes,'Additional quantities, power & project scope');
 });
}
function sectionContents(root){
 if(!['energy','chips','infrastructure','models','applications','industry','claims','ledger','projects','companies'].includes(document.body.dataset.page))return;
 const sections=[...root.querySelectorAll(':scope > section,:scope > .detail-layout,:scope > h2,:scope > .browse-disclosure,:scope > #company-results,:scope > #project-results')].filter(el=>!el.matches('.page-hero,#layer-diagram'));
 const entries=[];
 for(const [i,el] of sections.entries()){
  const heading=el.matches('h2')?el:el.querySelector('h2');
  const title=el.id==='company-results'?'Browse companies':el.id==='project-results'?'Browse projects':el.matches('.detail-layout')?'Tracked indicators':heading?.textContent.trim();if(!title)continue;
  if(!el.id){const stem='section-'+title.toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'');let id=stem,suffix=2;while(document.getElementById(id))id=stem+'-'+suffix++;el.id=id;}
  entries.push([el.id,title]);
 }
 if(!entries.length)return;
 const nav=document.createElement('nav');nav.className='page-contents';nav.setAttribute('aria-label','On this page');
 const select=document.createElement('select');select.className='select-control';select.setAttribute('aria-label','Jump to a section');
 select.add(new Option('On this page…',''));for(const [id,title] of entries)select.add(new Option(title,'#'+id));
 select.addEventListener('change',()=>{if(select.value){location.hash=select.value;revealResearchAnchor();}});
 const links=document.createElement('details');const summary=document.createElement('summary');summary.textContent='On this page';links.append(summary);
 for(const [id,title] of entries){const link=document.createElement('a');link.href='#'+id;link.textContent=title;links.append(link);}
 nav.append(select,links);(root.querySelector('#layer-diagram')||root.querySelector('.page-hero')).after(nav);
}
function organizeResearch(){
 const main=document.getElementById('main'),page=document.body.dataset.page;
 if(main.dataset.organized)return;main.dataset.organized='true';
 compactCompanies();compactProjects();
 for(const [id,compact] of [['company-results',compactCompanies],['project-results',compactProjects]]){
  const el=document.getElementById(id);if(el)new MutationObserver(compact).observe(el,{childList:true});
 }
 paginateResearch(document.getElementById('company-results'),':scope > .company-card',12,'Companies');
 paginateResearch(document.getElementById('project-results'),':scope > .delivery-card',8,'Projects');
 paginateResearch(document.getElementById('research-results'),':scope > .signal-row',8,'Research notes');
 paginateResearch(document.getElementById('record-results'),':scope > .record-row',12,'Observations');
 paginateResearch(document.querySelector('.run-table tbody'),':scope > tr',8,'Research runs');
 paginateResearch(document.getElementById('eci-table'),':scope > tr',12,'Model scores');
 if(page==='methodology'){
  const first=main.querySelector('.source-card');if(first){const sources=document.createElement('div');first.before(sources);main.querySelectorAll('.source-card').forEach(el=>sources.append(el));paginateResearch(sources,':scope > .source-card',12,'Sources',{search:true});}
 }
 if(page==='companies')paginateResearch(main.querySelector('table tbody'),':scope > tr',10,'Company source books',{search:true});
 if(page==='claims')main.querySelectorAll('.claim-card').forEach(card=>{
  const start=card.querySelector('h4');if(start){const nodes=[];for(let el=start;el;el=el.nextElementSibling)nodes.push(el);disclosureAround(nodes,'Evidence, future projects & sources');}
 });
 // Preserve every source and topic; prioritize measured evidence over repeated introductions.
 if(['energy','chips','infrastructure','models','applications'].includes(page)){
  const metric=main.querySelector('.detail-layout');if(metric){metric.id='tracked-indicators';main.querySelector('#layer-diagram').after(metric);}
  const priority={models:['model-capabilities','frontier-models','open-model-ecosystem','premium-model-plans'],applications:['alphafold-medicine']}[page]||[];
  let anchor=metric||main.querySelector('#layer-diagram');for(const id of priority){const section=document.getElementById(id);if(section&&section.parentElement===main){anchor.after(section);anchor=section;}}
  const repeated=main.querySelector('#ai-factories,#useful-systems,#productive-intelligence');
  if(repeated)disclosureAround([repeated],'Context: how this layer connects to useful work');
  main.querySelectorAll('.signal-list').forEach(el=>paginateResearch(el,':scope > .signal-row',5,'Layer research notes'));
  main.querySelectorAll('.builder-group').forEach((group,i)=>{
   const details=disclosureAround([group],group.querySelector('h3').textContent.trim());details.classList.add('builder-disclosure');details.open=i===0;
  });
  // Detailed topic cards remain addressable; headline evidence stays expanded.
  main.querySelectorAll(':scope > .agenda-section').forEach(section=>{
   if(priority.includes(section.id)||section.querySelector('.agenda-chart'))return;
   disclosureAround([section],section.querySelector('h2').textContent.trim());
  });
 }
 if(page==='industry'){
  let anchor=main.querySelector('#industry-momentum')||main.querySelector('.page-hero');
  for(const title of ['The trades behind the buildout','The people building the AI factories.','Which jobs are in the record?']){
   const h=[...main.querySelectorAll('h2')].find(el=>el.textContent.trim()===title);const section=h?.closest('section');
   if(section&&section.parentElement===main){anchor.after(section);anchor=section;}
  }
 }
 sectionContents(main);revealResearchAnchor();
 document.querySelectorAll('#main-navigation a.active').forEach(link=>link.setAttribute('aria-current','page'));
}
function setupResearchNavigation(){
 const button=document.querySelector('.menu-toggle'),nav=document.getElementById('main-navigation');
 const media=matchMedia('(max-width: 800px)');
 const close=()=>{nav.hidden=media.matches;button.setAttribute('aria-expanded','false');};
 const sync=()=>{button.hidden=!media.matches;close();};sync();media.addEventListener('change',sync);
 button.addEventListener('click',()=>{const open=button.getAttribute('aria-expanded')!=='true';button.setAttribute('aria-expanded',String(open));nav.hidden=!open;});
 document.addEventListener('keydown',event=>{if(event.key==='Escape'&&media.matches&&button.getAttribute('aria-expanded')==='true'){close();button.focus();}});
 document.addEventListener('click',event=>{if(media.matches&&!nav.contains(event.target)&&event.target!==button)close();});
 nav.addEventListener('click',event=>{if(event.target.closest('a')&&media.matches)close();});
 if(document.body.dataset.enhanced==='true')organizeResearch();
 else new MutationObserver((_,observer)=>{if(document.body.dataset.enhanced==='true'){observer.disconnect();organizeResearch();}}).observe(document.body,{attributes:true,attributeFilter:['data-enhanced']});
 window.addEventListener('hashchange',revealResearchAnchor);
}
setupResearchNavigation();
