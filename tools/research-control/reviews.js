'use strict';
(()=>{
  const el=id=>document.getElementById(id);
  let findings=[],owner=null,limit=10;
  function node(tag,text,className){const n=document.createElement(tag);if(text)n.textContent=text;if(className)n.className=className;return n;}
  function field(parent,title,text){if(!text)return;parent.append(node('h4',title),node('p',text));}
  function toggle(review){
    el('session-panel').hidden=review;el('review-panel').hidden=!review;
    el('session-tab').setAttribute('aria-pressed',String(!review));el('review-tab').setAttribute('aria-pressed',String(review));
    if(review)refresh();
  }
  el('session-tab').onclick=()=>toggle(false);el('review-tab').onclick=()=>toggle(true);
  async function refresh(){
    el('review-message').textContent='Loading private findings…';
    try{
      const r=await fetch('findings');
      if(r.status===404)throw new Error('This panel server predates review findings. Reopen Research-Control.cmd and use the newly opened tab. Your research and saved findings are unaffected.');
      const data=await r.json();if(!r.ok)throw new Error(data.error||'Could not load findings');
      findings=data.findings;owner=data.reviewer;limit=10;
      el('review-identity').textContent=owner?`Reviewing as ${owner} · Decisions are recorded locally with evidence hashes.`:'Read-only: this local account is not an authorized reviewer.';
      draw();drawCatalog(data);if(data.invalid_files)el('review-message').textContent+=` ${data.invalid_files} unreadable records need maintenance.`;
    }catch(e){el('review-message').textContent=e.message;}
  }
  function draw(){
    const selected=findings.filter(f=>(el('review-layer').value==='all'||f.layer===el('review-layer').value)&&(el('review-status').value==='all'||f.status===el('review-status').value));
    el('findings-list').replaceChildren();
    el('review-message').textContent=`${selected.length} findings match · showing ${Math.min(limit,selected.length)}.`;
    if(!selected.length)el('findings-list').append(node('p','No findings match these filters. Discovery proposals appear here after a research batch finishes.','empty-inbox'));
    for(const f of selected.slice(0,limit)){
      const card=node('article',null,'finding-card'),v=f.finding;
      card.append(node('p',`${f.layer} · ${v.kind} · ${f.status.replaceAll('_',' ')}`,'eyebrow'),node('h3',v.subject));
      card.append(node('p',v.claim,'finding-claim'),node('p',`Evidence basis: ${v.basis}`,'hint'));
      try{const u=new URL(f.url);if(u.protocol==='https:'&&!u.username&&!u.password){const a=node('a','Read original source ↗','finding-source');a.href=u.href;a.target='_blank';a.rel='noopener noreferrer';card.append(a);}}catch(e){}
      card.append(node('p',`Source published: ${f.published_at||'unknown'} · Retrieved: ${f.retrieved_at||'unknown'} · Proposal created: ${f.created_at}`,'hint'));
      field(card,'Supporting excerpt',v.evidence);field(card,'Why consider it?',v.why_track);field(card,'Next evidence to seek',v.next_question);
      const details=node('details');details.append(node('summary','Screening, uncertainty & review history'));
      field(details,'Source authority',f.authority||'Unverified');field(details,'Novelty',f.novelty||'Unassessed');
      field(details,'Model screening (not human approval)',f.screening?.reason||'No screening explanation recorded');
      field(details,'Latest recorded decision',f.last_review?`${f.last_review.status} · ${f.last_review.at} · ${f.last_review.reviewer||'queue'}\n${f.last_review.rationale||''}`:'No decision recorded');
      details.append(node('p',`Finding ID: ${f.id}`,'hint'));card.append(details);
      const form=node('form',null,'finding-review');
      const label=node('label','Decision'),select=node('select');select.setAttribute('aria-label','Decision for '+v.subject);
      for(const [value,text] of [['investigate','Investigate'],['deferred','Defer'],['rejected','Reject']]){const option=node('option',text);option.value=value;select.append(option);}label.append(select);
      const reasonLabel=node('label','Reason for your decision'),reason=node('textarea');reason.required=true;reason.maxLength=1200;reason.rows=3;reasonLabel.append(reason);
      const confirmLabel=node('label',null,'toggle'),confirm=node('input');confirm.type='checkbox';confirm.required=true;confirmLabel.append(confirm,node('span','I reviewed this finding and its evidence. This records triage, not permission to publish.'));
      const save=node('button','Record review');save.type='submit';save.disabled=!owner;
      const message=node('p',null,'hint');message.setAttribute('role','status');
      form.append(label,reasonLabel,confirmLabel,save,message);card.append(form);
      form.onsubmit=async event=>{
        event.preventDefault();save.disabled=true;
        try{
          const r=await fetch('review',{method:'POST',headers:{'Content-Type':'application/json','X-Session-Key':location.pathname.split('/')[1]},body:JSON.stringify({id:f.id,decision:select.value,rationale:reason.value,proposal_hash:f.proposal_hash,review_hash:f.review_hash,confirmed:confirm.checked})});
          const data=await r.json();if(!r.ok)throw new Error(data.error||'Review could not be recorded');
          await refresh();el('review-message').textContent=`Saved ${data.status} as ${data.reviewer}. Nothing published. `+el('review-message').textContent;
        }catch(e){message.textContent=e.message;save.disabled=!owner;}
      };
      el('findings-list').append(card);
    }
    el('more-findings').hidden=selected.length<=limit;
  }
  async function catalogPost(route,body){
    const r=await fetch(route,{method:'POST',headers:{'Content-Type':'application/json','X-Session-Key':location.pathname.split('/')[1]},body:JSON.stringify(body)});
    let data={};try{data=await r.json();}catch(e){}
    // A panel server started before catalog review existed answers "Unknown action" or 404; say so instead of failing quietly.
    if(r.status===404||(r.status===400&&data.error==='Unknown action'))throw new Error('This panel server predates catalog review. Close this tab, reopen Research-Control.cmd and use the newly opened tab; the queue and your decisions are unaffected.');
    if(!r.ok)throw new Error(data.error||'Catalog action failed');
    return data;
  }
  function placeOf(c){const id=encodeURIComponent(c.id);switch(c.target){
    case 'project':return ['projects/#project-'+id,'Projects page, card "'+(c.after.name||c.id)+'" (stage '+(c.after.stage||'?')+')'];
    case 'company':return ['companies/'+id+'/','Company page '+(c.after.name||c.id)];
    case 'product':return [((c.after.layers||['models'])[0])+'/','Layer page '+((c.after.layers||['models'])[0])+', product '+(c.after.name||c.id)];
    case 'note':return ['ledger/#'+id,'Ledger, research note "'+(c.after.title||c.id)+'"'];
    case 'observation':return ['ledger/#'+id,'Ledger, record '+c.id];
    case 'metric':return ['ledger/','Ledger, metric '+(c.after.title||c.id)];
    case 'source':return ['methodology/#sources','Methodology, source library: '+(c.after.title||c.id)];
    default:return ['',''];}}
  function drawCatalog(data){
   let box=el('catalog-packages');if(!box){box=node('section');box.id='catalog-packages';el('review-panel').append(box);}box.replaceChildren(node('h2','Catalog updates'),node('p','Review exact changes, validate their preview, then approve and publish. Research and model screening never count as approval.'));
   // Status toggles: default to what needs a decision; approved (retractable), rejected (reconsiderable) and applied are opt-in.
   const STATUSES=[['pending_review','Needs review'],['deferred','Deferred'],['approved','Approved, not yet applied'],['rejected','Rejected'],['applied','Applied']];
   let shown;try{shown=JSON.parse(localStorage.getItem('catalog-status-filter')||'null');}catch(e){shown=null;}
   if(!Array.isArray(shown))shown=['pending_review','deferred'];
   const all=data.catalog_packages||[];const counts={};for(const p of all)counts[p.status]=(counts[p.status]||0)+1;
   const filters=node('div',null,'catalog-filters');filters.setAttribute('role','group');filters.setAttribute('aria-label','Show catalog packages by status');
   for(const [value,label] of STATUSES){const l=node('label',null,'toggle-chip'),c=node('input');c.type='checkbox';c.checked=shown.includes(value);c.onchange=()=>{shown=c.checked?[...new Set([...shown,value])]:shown.filter(v=>v!==value);try{localStorage.setItem('catalog-status-filter',JSON.stringify(shown));}catch(e){}drawCatalog(data);};l.append(c,node('span',`${label} (${counts[value]||0})`));filters.append(l);}
   box.append(filters);
   const visible=all.filter(p=>shown.includes(p.status));
   box.append(node('p',`${visible.length} of ${all.length} packages shown.`,'hint'));
   for(const p of visible){
    const card=node('article',null,'finding-card');card.append(node('h3',p.title),node('p',`${p.author} · ${p.status} · ${p.changes.length} object changes`));
    if(p.last_review&&p.status!=='applied')card.append(node('p',`Last decision: ${p.last_review.status.replaceAll('_',' ')} · ${new Date(p.last_review.at).toLocaleString()} · ${p.last_review.reviewer||''}${p.last_review.rationale?' — '+p.last_review.rationale:''}`,'hint'));
    for(const change of p.changes){
      const detail=node('details');detail.append(node('summary',`${change.target}: ${change.id} — ${change.before?'update':'new entry'}`));
      // Readable summary of the proposed object first; raw JSON stays available below it.
      const dl=node('dl',null,'change-summary');const a=change.after||{};
      const fields={project:['name','owner','location','category','stage','ai_relationship','grid','horizon','next_evidence','company_ids'],company:['name','layers','role','region_book','revenue_kind'],product:['name','layers','description','status','gap'],source:['publisher','title','url','published','layers','license'],note:['title','summary','layer','kind','date'],observation:['metric','year','period','value','upper','status','precision','note'],metric:['title','unit','geography','scope','allowed_statuses','period_basis']}[change.target]||Object.keys(a);
      for(const k of fields){if(a[k]===undefined||a[k]===null||a[k]==='')continue;const v=Array.isArray(a[k])?a[k].join(', '):(typeof a[k]==='object'?JSON.stringify(a[k]):String(a[k]));const dt=node('dt',k.replaceAll('_',' '));const dd=node('dd',v);if(change.before&&JSON.stringify(change.before[k])!==JSON.stringify(a[k]))dd.className='changed';dl.append(dt,dd);}
      if(change.target==='project'&&Array.isArray(a.milestones))for(const m of a.milestones){dl.append(node('dt','milestone'+(m.date?' '+m.date:'')),node('dd',m.summary+' [source '+m.source+']'));}
      detail.append(dl);
      // Inline site preview at the exact place this object appears, loaded only on request.
      const [path,label]=placeOf(change);
      if(path){const frameButton=node('button',p.validation?.passed?'Show in site preview':'Validate preview first, then show in site preview','secondary');frameButton.disabled=!p.validation?.passed;const slot=node('div',null,'preview-slot');
        frameButton.onclick=()=>{if(slot.firstChild){slot.replaceChildren();frameButton.textContent='Show in site preview';return;}const f=document.createElement('iframe');f.className='preview-frame';f.title='Site preview: '+label;f.loading='lazy';f.src='preview/'+p.id+'/'+path;slot.append(f);frameButton.textContent='Hide site preview';};
        detail.append(frameButton,slot);}
      const raw=node('details');raw.append(node('summary','Raw JSON (before / after)'),node('h4','Before'),node('pre',JSON.stringify(change.before,null,2)),node('h4','After'),node('pre',JSON.stringify(change.after,null,2)));detail.append(raw);
      card.append(detail);
    }
    for(const evidence of p.evidence){const detail=node('details');detail.append(node('summary','Evidence: '+evidence.id),node('p',evidence.summary),node('p',`Published: ${evidence.published_at||'unknown'} · Retrieved: ${evidence.retrieved_at}`));try{const u=new URL(evidence.url);if(u.protocol==='https:'&&!u.username&&!u.password){const a=node('a','Read source ↗');a.href=u.href;a.target='_blank';a.rel='noopener noreferrer';detail.append(a);}}catch(e){}card.append(detail);}
    const msg=node('p',p.validation?(p.validation.passed?'Preview validation passed.':'Preview validation failed; inspect the checks below.'):'Preview has not been validated.','hint');msg.setAttribute('role','status');card.append(msg);
    if(p.validation?.passed){
      const a=node('a','Open site preview ↗');a.href='preview/'+p.id+'/';a.target='_blank';a.rel='noopener';card.append(a);
      // Where each changed object appears in the previewed site, so the reviewer is not left on the homepage.
      const where=node('details');where.append(node('summary','Where to look in the preview'));const list=node('ul');
      const place=placeOf;
      for(const c of p.changes){const [path,label]=place(c);const li=node('li');if(path){const l=node('a',label+' ↗');l.href='preview/'+p.id+'/'+path;l.target='_blank';l.rel='noopener';li.append(l);}else li.textContent=c.target+': '+c.id;list.append(li);}
      where.append(list);card.append(where);
    }
    if(p.validation){const d=node('details');d.append(node('summary','Validation results'),node('pre',JSON.stringify(p.validation.checks,null,2)));card.append(d);}
    if(p.status==='applied'){
      // Finished packages: the objects are live (or declined); validating would only report that they changed since proposal.
      const when=p.last_review?.at?new Date(p.last_review.at).toLocaleString():'';
      card.append(node('p','Applied'+(when?' '+when:'')+(p.last_review?.reviewer?' by '+p.last_review.reviewer:'')+'. These objects are live in the catalog; no further action from here.','hint'));
      box.append(card);continue;
    }
    const preview=node('button','Validate preview');preview.disabled=!owner;preview.onclick=async()=>{preview.disabled=true;msg.textContent='Building and testing isolated preview…';try{await catalogPost('catalog-preview',{id:p.id});await refresh();}catch(e){msg.textContent=e.message;preview.disabled=false;}};card.append(preview);
    const form=node('form',null,'finding-review'),decision=node('select');for(const [v,label] of [['approved','Approve this package'],['deferred','Defer'],['rejected','Reject']]){const o=node('option',label);o.value=v;decision.append(o);}const reason=node('textarea');reason.placeholder='Reason for this decision';reason.required=true;reason.maxLength=1200;const label=node('label',null,'toggle'),confirm=node('input');confirm.type='checkbox';confirm.required=true;label.append(confirm,node('span','I reviewed the exact changes and supporting sources.'));const submit=node('button','Record catalog decision');submit.disabled=!owner;form.append(decision,reason,label,submit);form.onsubmit=async event=>{event.preventDefault();submit.disabled=true;try{await catalogPost('catalog-review',{id:p.id,decision:decision.value,rationale:reason.value,proposal_hash:p.proposal_hash,review_hash:p.review_hash,confirmed:confirm.checked});await refresh();}catch(e){msg.textContent=e.message;submit.disabled=false;}};card.append(form);
    if(p.status==='approved'){const label=node('label',null,'toggle'),confirm=node('input');confirm.type='checkbox';label.append(confirm,node('span','Apply this approved package, commit, push and verify the live site.'));const button=node('button','Apply and publish');button.disabled=!owner;button.onclick=async()=>{if(!confirm.checked){msg.textContent='Confirm publication first.';return;}button.disabled=true;msg.textContent='Applying approved changes; validation and deployment may take a few minutes…';try{const result=await catalogPost('catalog-publish',{id:p.id,proposal_hash:p.proposal_hash,review_hash:p.review_hash,confirmed:true});await refresh();el('review-message').textContent='Catalog publication: '+result.status;}catch(e){msg.textContent=e.message;button.disabled=false;}};card.append(label,button);}
    box.append(card);
   }
   if(!all.length)box.append(node('p','No catalog packages prepared yet. Findings need complete evidence-backed object changes before approval.'));else if(!visible.length)box.append(node('p','Nothing matches the selected statuses. Turn on a status above to see decided packages.','hint'));
   const handoffs=node('details');handoffs.append(node('summary',`${(data.handoffs||[]).length} research-note follow-ups`));for(const h of data.handoffs||[]){handoffs.append(node('h4',h.title),node('p',h.summary),node('p',h.reason));}box.append(handoffs);
  }
  el('refresh-findings').onclick=refresh;
  for(const id of ['review-layer','review-status'])el(id).onchange=()=>{limit=10;draw();};
  el('more-findings').onclick=()=>{limit+=10;draw();};
})();
