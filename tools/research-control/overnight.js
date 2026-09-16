'use strict';
(()=>{
  const el=id=>document.getElementById(id);
  const make=(tag,text,cls)=>{const n=document.createElement(tag);if(text!=null)n.textContent=text;if(cls)n.className=cls;return n;};
  const date=v=>v?new Intl.DateTimeFormat('en-US',{dateStyle:'long',timeZone:'UTC'}).format(new Date(v+'T12:00:00Z')):'Date unlisted';
  function link(text,url){const a=make('a',text);try{const u=new URL(url,location.href);if(!['https:','http:'].includes(u.protocol))return make('span',text);a.href=u.href;}catch{return make('span',text);}a.rel='noopener noreferrer';return a;}
  let selected='latest',requestId=0,fingerprint='';
  function render(d){
    const box=el('night-review');box.replaceChildren();
    const hero=make('article',null,'night-hero '+d.outcome);
    hero.append(make('p',d.date_label,'eyebrow'),make('h3',d.takeaway));
    if(d.active)hero.append(make('p',d.live_stage?'Current step: '+d.live_stage:'Research in progress','hint'));
    const stats=make('div',null,'night-stats');
    for(const [label,value] of [['Document versions listed',d.documents.length],['Monitoring findings accepted',d.sessions.length?d.totals.accepted:'—'],['Discovery proposals',d.sessions.length?d.totals.discovery_proposals:'—']]){
      const stat=make('div');stat.append(make('strong',value??'—'),make('span',label));stats.append(stat);
    }
    hero.append(stats);
    const actions=make('div',null,'night-links');actions.append(link('Latest on the full site ↗',d.links.latest));
    const review=make('button',d.pending.length?'Review waiting decisions':'View decisions & history');review.type='button';review.onclick=()=>{location.hash='decisions';el('decisions-tab').click();};actions.append(review);hero.append(actions);box.append(hero);
    const grid=make('div',null,'night-grid');
    const findings=make('section',null,'night-card');findings.append(make('h3','What came out of it'));
    if(!d.highlights.length)findings.append(make('p',d.sessions.length?'No published article summaries matched this night’s document receipts. Dataset changes and private findings are listed separately below.':'No matched research session is recorded.'));
    for(const h of d.highlights){const row=make('article',null,'night-finding');row.append(make('p',`${h.retracted?'Retracted · ':''}${h.kind||'Finding'} · ${h.layer||'General'} · Grade ${h.grade||'not recorded'}`,'eyebrow'),link(h.title,h.url),make('p',h.summary),make('p','Source date: '+date(h.date)+(h.confirmation?' · '+h.confirmation:''),'hint'));findings.append(row);}
    const imports=d.applied.filter(x=>x.kind==='import');if(imports.length)findings.append(make('p','Dataset updates: '+imports.map(x=>x.id).join(', ')+'.'));
    const pub=d.published_observations||{};if(pub.new_observations)findings.append(make('p',`${pub.new_observations} newly recorded numbers: `+Object.entries(pub.by_grade||{}).map(([g,n])=>`${n} grade ${g}`).join(', ')));
    const tasks=make('section',null,'night-card');tasks.append(make('h3','Your next step'));
    if(d.pending.length){const list=make('ul');for(const p of d.pending)list.append(make('li',`${p.count} ${p.label}`));tasks.append(list,make('p','Current Decisions inbox, updated from your saved reviews.','hint'));}
    else tasks.append(make('p','You’re caught up. No reviews are awaiting a decision.'));
    if(d.question_backlog){const backlog=make('details');backlog.append(make('summary',`${d.question_backlog} proposed research questions in a separate backlog`),make('p','These older research proposals have no recorded decision and are not supported in this review page. They are separate from your completed finding and catalog reviews.','hint'));tasks.append(backlog);}
    const errors=(d.totals.source_failures||0)+(d.totals.discovery_errors||0);
    if(errors)tasks.append(make('h4','Collection needs attention'),make('p',`${errors} collection errors (including possible retries). Some sources could not be read. Eli handles workflow failures; the technical receipts are below.`));
    if(d.inventory_errors)tasks.append(make('p',`${d.inventory_errors} receipt read errors. This inventory may be incomplete.`));
    if(d.publication.unpushed_commits&&!(d.publication.final_push||{}).pushed)tasks.append(make('p','Some changes have not been confirmed pushed to the site.'));
    grid.append(findings,tasks);box.append(grid);
    const stages=make('details',null,'night-card');stages.append(make('summary','How the night ran'));
    for(const s of d.stages){const row=make('div',null,'night-stage');row.append(make('strong',s.name),make('span',s.status));if(s.reason)row.append(make('p',s.reason));stages.append(row);}
    const raw=make('details');raw.append(make('summary','Technical counts'),make('pre',JSON.stringify(d.totals,null,2)));stages.append(raw);box.append(stages);
    const library=make('section',null,'night-card');library.append(make('h3','What it read'),make('p','Documents recorded as fetched, including older publications revisited overnight. Fetching does not establish that every passage was reviewed.','hint'));
    const search=make('input');search.type='search';search.placeholder='Search title, publisher or topic';search.setAttribute('aria-label','Search documents read');const count=make('p',null,'hint'),list=make('div'),more=make('button','Show more documents');more.type='button';let shown=20;
    function draw(){const q=search.value.toLowerCase();const docs=d.documents.filter(x=>[x.title,x.publisher,(x.layers||[]).join(' ')].join(' ').toLowerCase().includes(q));list.replaceChildren();count.textContent=`${docs.length} document versions · showing ${Math.min(shown,docs.length)}`;for(const x of docs.slice(0,shown)){const row=make('article',null,'night-document');row.append(link(x.title||x.url,x.url),make('p',`${x.publisher||x.lane} · ${(x.layers||[]).join(', ')} · ${date(x.published)}`,'hint'));if(x.outcome)row.append(make('p',x.outcome.replaceAll('_',' '),'hint'));list.append(row);}more.hidden=shown>=docs.length;}
    search.oninput=()=>{shown=20;draw();};more.onclick=()=>{shown+=40;draw();};draw();library.append(search,count,list,more);box.append(library);
  }
  async function load(){const id=++requestId;try{const response=await fetch('night/'+encodeURIComponent(selected));if(!response.ok)throw new Error('Overnight receipts could not load. Try reopening the dashboard.');const d=await response.json();if(id!==requestId)return;const select=el('night-date');select.replaceChildren();for(const v of [...new Set([d.date,...d.dates])]){const o=make('option',date(v));o.value=v;o.selected=v===d.date;select.append(o);}const next=JSON.stringify({...d,updated_at:null});if(next!==fingerprint){render(d);fingerprint=next;}el('night-message').textContent=d.active?'Live · refreshes every 15 seconds':'Recorded results · refreshed '+new Date(d.updated_at).toLocaleTimeString();}catch(e){el('night-message').textContent=e.message;}}
  el('night-date').onchange=e=>{selected=e.target.value;location.hash='run='+selected;};
  el('overnight-tab').onclick=()=>{showPanel('overnight-panel');selected='latest';location.hash='overnight';load();};
  function navigate(){const hash=location.hash;const m=/^#run=(\d{4}-\d{2}-\d{2})$/.exec(hash);if(m||hash==='#overnight'||!hash){selected=m?m[1]:'latest';showPanel('overnight-panel');load();}else if(hash==='#decisions'){showPanel('decisions-panel');}}
  addEventListener('hashchange',navigate);navigate();
  setInterval(()=>{if(!document.hidden&&!el('overnight-panel').hidden)load();},15000);
})();
