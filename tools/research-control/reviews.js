'use strict';
(()=>{
  const el=id=>document.getElementById(id);
  let findings=[],owner=null,limit=10;
  function node(tag,text,className){const n=document.createElement(tag);if(text)n.textContent=text;if(className)n.className=className;return n;}
  function field(parent,title,text){if(!text)return;parent.append(node('h4',title),node('p',text));}
  async function refresh(){
    el('review-message').textContent='Loading private findings…';
    try{
      const r=await fetch('findings');
      if(r.status===404)throw new Error('This panel server predates review findings. Reopen Research-Control.cmd and use the newly opened tab. Your research and saved findings are unaffected.');
      const data=await r.json();if(!r.ok)throw new Error(data.error||'Could not load findings');
      findings=data.findings;owner=data.reviewer;limit=10;
      el('review-identity').textContent=owner?`Reviewing as ${owner} · Decisions are recorded locally with evidence hashes.`:'Read-only: this account is not an authorized reviewer.';
      el('log-integrity-banner').hidden=!data.unreadable_events;
      if(data.unreadable_events)el('log-integrity-banner').textContent=`${data.unreadable_events} unreadable audit-log line(s) detected. Run "python scripts/editorial_review.py --verify-log" to inspect; decisions before the tear are unaffected.`;
      draw();drawCatalog(data);buildFindingFeed();
      let msg=`${findings.length} discovery finding${findings.length===1?'':'s'} on file.`;if(data.invalid_files)msg+=` ${data.invalid_files} unreadable records need maintenance.`;
      el('review-message').textContent=msg;
    }catch(e){el('review-message').textContent=e.message;}
    window.renderDecisionFeed();
  }
  function findingForm(f){
    const form=node('form',null,'finding-review');
    const label=node('label','Decision'),select=node('select');select.setAttribute('aria-label','Decision for '+f.finding.subject);
    for(const [value,text] of [['investigate','Investigate'],['deferred','Defer'],['rejected','Reject']]){const option=node('option',text);option.value=value;select.append(option);}label.append(select);
    const reasonLabel=node('label','Reason for your decision'),reason=node('textarea');reason.required=true;reason.maxLength=1200;reason.rows=3;reasonLabel.append(reason);
    const confirmLabel=node('label',null,'toggle'),confirm=node('input');confirm.type='checkbox';confirm.required=true;confirmLabel.append(confirm,node('span','I reviewed this finding and its evidence. This records triage, not permission to publish.'));
    const save=node('button','Record review');save.type='submit';save.disabled=!owner;
    const message=node('p',null,'hint');message.setAttribute('role','status');
    form.append(label,reasonLabel,confirmLabel,save,message);
    form.onsubmit=async event=>{
      event.preventDefault();save.disabled=true;
      try{
        const r=await fetch('review',{method:'POST',headers:{'Content-Type':'application/json','X-Session-Key':sessionKey()},body:JSON.stringify({id:f.id,decision:select.value,rationale:reason.value,proposal_hash:f.proposal_hash,review_hash:f.review_hash,confirmed:confirm.checked})});
        const data=await r.json();if(!r.ok)throw new Error(data.error||'Review could not be recorded');
        await refresh();el('review-message').textContent=`Saved ${data.status} as ${data.reviewer}. Nothing published. `+el('review-message').textContent;
      }catch(e){message.textContent=e.message;save.disabled=!owner;}
    };
    return form;
  }
  function buildFindingCard(f){
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
    card.append(findingForm(f));
    return card;
  }
  function buildFindingFeed(){
    window.__pending.findings=findings.filter(f=>f.status==='pending_review').map(f=>({rank:15,created_at:f.created_at,el:buildFindingCard(f)}));
  }
  function draw(){
    const selected=findings.filter(f=>(el('review-layer').value==='all'||f.layer===el('review-layer').value)&&(el('review-status').value==='all'||f.status===el('review-status').value));
    el('findings-list').replaceChildren();
    if(!selected.length)el('findings-list').append(node('p','No findings match these filters. Discovery proposals appear here after a research batch finishes.','empty-inbox'));
    for(const f of selected.slice(0,limit))el('findings-list').append(buildFindingCard(f));
    el('more-findings').hidden=selected.length<=limit;
  }
  function ensureStatusShown(status){let shown;try{shown=JSON.parse(localStorage.getItem('catalog-status-filter')||'null');}catch(e){shown=null;}if(!Array.isArray(shown))shown=['pending_review','deferred','deployment_pending'];if(!shown.includes(status)){shown.push(status);try{localStorage.setItem('catalog-status-filter',JSON.stringify(shown));}catch(e){}}}
  async function catalogPost(route,body){
    const r=await fetch(route,{method:'POST',headers:{'Content-Type':'application/json','X-Session-Key':sessionKey()},body:JSON.stringify(body)});
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
  const STATUS_LABELS={pending_review:'Needs review',deferred:'Deferred',approved:'Approved, not yet applied',deployment_pending:'Pushed · awaiting deployment check',rejected:'Rejected',applied:'Applied'};
  function openPackagePreview(p,path,frameButton,slot){
    const src='preview/'+p.id+'/'+path,title='Site preview: '+p.title;
    if(window.isPhoneWidth&&window.isPhoneWidth()){window.openPreview(src,title);return;}
    if(slot.firstChild){slot.replaceChildren();frameButton.textContent='Show in site preview';return;}
    const f=document.createElement('iframe');f.className='preview-frame';f.title=title;f.loading='lazy';f.src=src;slot.append(f);frameButton.textContent='Hide site preview';
  }
  function buildCatalogCard(p,{selectable,boxes,selected,count}={}){
    const card=node('article',null,'finding-card');
    const display=p.display_status||p.status;
    card.append(node('h3',p.title),node('p',`${p.author} · ${STATUS_LABELS[display]||display} · ${p.changes.length} object changes`));
    if(p.auto_apply_eligible!==null&&p.auto_apply_eligible!==undefined)
      card.append(node('p',`Auto-apply eligible: ${p.auto_apply_eligible?'Yes':'No'}${p.auto_apply_reasons&&p.auto_apply_reasons.length?' — '+p.auto_apply_reasons[0]:''}`,'hint'));
    if(selectable&&p.status!=='applied'){const sel=node('label',null,'toggle-chip select-chip'),sb=node('input');sb.type='checkbox';sb.value=p.id;sb.setAttribute('aria-label','Select '+p.title);sb.onchange=()=>{if(sb.checked)selected.add(p.id);else selected.delete(p.id);count();};boxes.push(sb);sel.append(sb,node('span','Select'));card.append(sel);}
    if(p.last_review&&p.status!=='applied')card.append(node('p',`Last decision: ${p.last_review.status.replaceAll('_',' ')} · ${new Date(p.last_review.at).toLocaleString()} · ${p.last_review.reviewer||''}${p.last_review.rationale?' — '+p.last_review.rationale:''}`,'hint'));
    for(const change of p.changes){
      const detail=node('details');detail.append(node('summary',`${change.target}: ${change.id} — ${change.before?'update':'new entry'}`));
      // Readable summary of the proposed object first; raw JSON stays available below it.
      const dl=node('dl',null,'change-summary');const a=change.after||{};
      const fields={project:['name','owner','location','category','stage','ai_relationship','grid','horizon','next_evidence','company_ids'],company:['name','layers','role','region_book','revenue_kind'],product:['name','layers','description','status','gap'],source:['publisher','title','url','published','layers','license'],note:['title','summary','layer','kind','date'],observation:['metric','year','period','value','upper','status','precision','note'],metric:['title','unit','geography','scope','allowed_statuses','period_basis']}[change.target]||Object.keys(a);
      for(const k of fields){if(a[k]===undefined||a[k]===null||a[k]==='')continue;const v=Array.isArray(a[k])?a[k].join(', '):(typeof a[k]==='object'?JSON.stringify(a[k]):String(a[k]));const dt=node('dt',k.replaceAll('_',' '));const dd=node('dd',v);if(change.before&&JSON.stringify(change.before[k])!==JSON.stringify(a[k]))dd.className='changed';dl.append(dt,dd);}
      if(change.target==='project'&&Array.isArray(a.milestones))for(const m of a.milestones){dl.append(node('dt','milestone'+(m.date?' '+m.date:'')),node('dd',m.summary+' [source '+m.source+']'));}
      detail.append(dl);
      // Inline site preview at the exact place this object appears (60vh frame on desktop, full-screen overlay on phones).
      const [path,label]=placeOf(change);
      if(path){const frameButton=node('button',p.validation?.passed?'Show in site preview':'Validate preview first, then show in site preview','secondary');frameButton.disabled=!p.validation?.passed;const slot=node('div',null,'preview-slot');
        frameButton.onclick=()=>openPackagePreview(p,path,frameButton,slot);
        detail.append(frameButton,slot);}
      const raw=node('details');raw.append(node('summary','Raw JSON (before / after)'),node('h4','Before'),node('pre',JSON.stringify(change.before,null,2)),node('h4','After'),node('pre',JSON.stringify(change.after,null,2)));detail.append(raw);
      card.append(detail);
    }
    for(const evidence of p.evidence){const detail=node('details');detail.append(node('summary','Evidence: '+evidence.id),node('p',evidence.summary),node('p',`Published: ${evidence.published_at||'unknown'} · Retrieved: ${evidence.retrieved_at} · Registered source rank: ${evidence.source_rank??'unregistered'}`));try{const u=new URL(evidence.url);if(u.protocol==='https:'&&!u.username&&!u.password){const a=node('a','Read source ↗');a.href=u.href;a.target='_blank';a.rel='noopener noreferrer';detail.append(a);}}catch(e){}card.append(detail);}
    const failing=p.validation&&!p.validation.passed?(p.validation.checks||[]).find(c=>!c.passed):null;
    const msg=node('p',p.validation?(p.validation.passed?'Preview validated: validate, build, tests and editorial checks passed. Ready to approve.':`Preview failed: ${failing?failing.command:'a check'} did not pass; open the checks below.`):'Step 1: validate the preview (about a minute).','card-status '+(p.validation?(p.validation.passed?'ok':'error'):''));msg.setAttribute('role','status');card.append(msg);
    if(p.validation?.passed){
      const a=node('a','Open site preview ↗');a.href='preview/'+p.id+'/';a.target='_blank';a.rel='noopener';card.append(a);
      // Where each changed object appears in the previewed site, so the reviewer is not left on the homepage.
      const where=node('details');where.append(node('summary','Where to look in the preview'));const list=node('ul');
      for(const c of p.changes){const [path,label]=placeOf(c);const li=node('li');if(path){const l=node('a',label+' ↗');l.href='preview/'+p.id+'/'+path;l.target='_blank';l.rel='noopener';li.append(l);}else li.textContent=c.target+': '+c.id;list.append(li);}
      where.append(list);card.append(where);
    }
    if(p.validation){const d=node('details');d.append(node('summary','Validation results'),node('pre',JSON.stringify(p.validation.checks,null,2)));card.append(d);}
    if(p.publication_receipt&&display==='deployment_pending')card.append(node('p','Pushed as commit '+(p.publication_receipt.commit||'').slice(0,10)+'; the live site has not yet confirmed the update. This resolves automatically on the next check.','hint'));
    if(p.status==='applied'){
      // Finished packages: the objects are live (or declined); validating would only report that they changed since proposal.
      const when=p.last_review?.at?new Date(p.last_review.at).toLocaleString():'';
      card.append(node('p','Applied'+(when?' '+when:'')+(p.last_review?.reviewer?' by '+p.last_review.reviewer:'')+'. These objects are live in the catalog; no further action from here.','hint'));
      return card;
    }
    const preview=node('button','Validate preview');preview.disabled=!owner;preview.onclick=async()=>{preview.disabled=true;msg.className='card-status';msg.textContent='Building and testing the isolated preview (about a minute)…';notify(`Validating "${p.title}"…`,'ok');try{const result=await catalogPost('catalog-preview',{id:p.id});const bad=(result.checks||[]).find(c=>!c.passed);notify(result.passed?`Preview validated for "${p.title}". You can approve it now.`:`Preview failed for "${p.title}": ${bad?bad.command:'a check'} did not pass. Open the card's checks for details.`,result.passed?'ok':'error');await refresh();}catch(e){msg.className='card-status error';msg.textContent=e.message;notify(e.message,'error');preview.disabled=false;}};card.append(preview);
    const form=node('form',null,'finding-review'),decision=node('select');for(const [v,label] of [['approved','Approve this package'],['deferred','Defer'],['rejected','Reject']]){const o=node('option',label);o.value=v;decision.append(o);}const reason=node('textarea');reason.placeholder='Reason for this decision';reason.required=true;reason.maxLength=1200;const flabel=node('label',null,'toggle'),confirm=node('input');confirm.type='checkbox';confirm.required=true;flabel.append(confirm,node('span','I reviewed the exact changes and supporting sources.'));const submit=node('button','Record catalog decision');submit.disabled=!owner;form.append(decision,reason,flabel,submit);form.noValidate=true;form.onsubmit=async event=>{event.preventDefault();if(!reason.value.trim()||!confirm.checked){msg.className='card-status error';msg.textContent='Add a one-line reason and tick the confirmation, then record again.';notify(msg.textContent,'error');return;}submit.disabled=true;try{await catalogPost('catalog-review',{id:p.id,decision:decision.value,rationale:reason.value,proposal_hash:p.proposal_hash,review_hash:p.review_hash,confirmed:confirm.checked});ensureStatusShown(decision.value);notify(`Recorded "${decision.value}" for "${p.title}" as ${owner}.${decision.value==='approved'?' It stays listed under Approved; next step is Apply and publish.':''}`,'ok');await refresh();}catch(e){msg.className='card-status error';msg.textContent=e.message;notify(e.message,'error');submit.disabled=false;}};card.append(form);
    if(p.status==='approved'){const alabel=node('label',null,'toggle'),aconfirm=node('input');aconfirm.type='checkbox';alabel.append(aconfirm,node('span','Apply this approved package, commit, push and verify the live site.'));const button=node('button','Apply and publish');button.disabled=!owner;button.onclick=async()=>{if(!aconfirm.checked){msg.textContent='Confirm publication first.';return;}button.disabled=true;msg.textContent='Applying approved changes; validation and deployment may take a few minutes…';try{const result=await catalogPost('catalog-publish',{id:p.id,proposal_hash:p.proposal_hash,review_hash:p.review_hash,confirmed:true});ensureStatusShown('applied');await refresh();notify('Catalog publication: '+result.status+(result.commit?' · commit '+String(result.commit).slice(0,10):'')+(result.status==='deployed'?' · live on the site':' · the nightly check confirms deployment'),'ok');}catch(e){msg.className='card-status error';msg.textContent=e.message;notify(e.message,'error');button.disabled=false;}};card.append(alabel,button);}
    return card;
  }
  function drawCatalog(data){
   let box=el('catalog-packages');if(!box){box=node('section');box.id='catalog-packages';el('review-panel').append(box);}box.replaceChildren(node('h2','Catalog updates'),node('p','Review exact changes, validate their preview, then approve and publish. Research and model screening never count as approval.'));
   // Status toggles: default to what needs a decision; approved (retractable), rejected (reconsiderable) and applied are opt-in.
   const STATUSES=[['pending_review','Needs review'],['deferred','Deferred'],['approved','Approved, not yet applied'],['deployment_pending','Pushed · awaiting deployment check'],['rejected','Rejected'],['applied','Applied']];
   let shown;try{shown=JSON.parse(localStorage.getItem('catalog-status-filter')||'null');}catch(e){shown=null;}
   if(!Array.isArray(shown))shown=['pending_review','deferred','deployment_pending'];
   const all=data.catalog_packages||[];const counts={};for(const p of all)counts[p.display_status||p.status]=(counts[p.display_status||p.status]||0)+1;
   const filters=node('div',null,'catalog-filters');filters.setAttribute('role','group');filters.setAttribute('aria-label','Show catalog packages by status');
   for(const [value,label] of STATUSES){const l=node('label',null,'toggle-chip'),c=node('input');c.type='checkbox';c.checked=shown.includes(value);c.onchange=()=>{shown=c.checked?[...new Set([...shown,value])]:shown.filter(v=>v!==value);try{localStorage.setItem('catalog-status-filter',JSON.stringify(shown));}catch(e){}drawCatalog(data);};l.append(c,node('span',`${label} (${counts[value]||0})`));filters.append(l);}
   box.append(filters);
   const visible=all.filter(p=>shown.includes(p.display_status||p.status));
   box.append(node('p',`${visible.length} of ${all.length} packages shown.`,'hint'));
   // Bulk actions: one decision for many packages, executed one package at a time so previews and
   // publications never overlap. Decisions are safe at any moment; preview and apply queue behind a running job.
   const selected=new Set();
   const bulk=node('div',null,'bulk-bar');bulk.hidden=!visible.some(p=>p.status!=='applied');
   const selectAll=node('label',null,'toggle-chip'),selectAllBox=node('input');selectAllBox.type='checkbox';selectAll.append(selectAllBox,node('span','Select all shown'));
   const decision=node('select');for(const [v,label] of [['approved','Approve'],['deferred','Defer'],['rejected','Reject']]){const o=node('option',label);o.value=v;decision.append(o);}
   const reason=node('textarea');reason.placeholder='One reason, recorded on every selected package';reason.rows=2;reason.maxLength=1200;
   const confirmLabel=node('label',null,'toggle'),confirm=node('input');confirm.type='checkbox';confirmLabel.append(confirm,node('span','I reviewed the exact changes and supporting sources of every selected package.'));
   const progress=node('p',null,'hint');progress.setAttribute('role','status');
   const bValidate=node('button','Validate selected previews','secondary'),bRecord=node('button','Record decision for selected'),bApply=node('button','Apply selected approved packages','secondary');
   for(const b of [bValidate,bRecord,bApply])b.disabled=!owner;
   const count=()=>{progress.textContent=`${selected.size} selected.`;};
   async function latest(id){const r=await fetch('findings');const d=await r.json();return (d.catalog_packages||[]).find(q=>q.id===id);}
   async function runBulk(kind){
     if(!selected.size){progress.textContent='Select at least one package.';return;}
     for(const b of [bValidate,bRecord,bApply])b.disabled=true;
     const ids=[...selected];let done=0;
     try{
       for(const id of ids){
         let q=await latest(id);if(!q){throw new Error(`${id} is no longer in the queue`);}
         progress.textContent=`${kind} ${done+1}/${ids.length}: ${q.title}`;
         if(kind==='validate'||(kind==='record'&&decision.value==='approved'&&!q.validation?.passed)){await catalogPost('catalog-preview',{id});q=await latest(id);if(!q.validation?.passed)throw new Error(`Preview failed for ${q.title}; left for individual review`);}
         if(kind==='record'){if(!reason.value.trim()||!confirm.checked)throw new Error('A reason and the confirmation are required.');await catalogPost('catalog-review',{id,decision:decision.value,rationale:reason.value,proposal_hash:q.proposal_hash,review_hash:q.review_hash,confirmed:confirm.checked});}
         if(kind==='apply'){if(q.status!=='approved')throw new Error(`${q.title} is ${q.status}, not approved`);if(!confirm.checked)throw new Error('Tick the confirmation to apply.');await catalogPost('catalog-publish',{id,proposal_hash:q.proposal_hash,review_hash:q.review_hash,confirmed:true});}
         done++;
       }
       progress.textContent=`${kind}: ${done}/${ids.length} completed.`;await refresh();el('review-message').textContent=`Bulk ${kind}: ${done} package${done===1?'':'s'}. `+el('review-message').textContent;
     }catch(e){progress.textContent=`Stopped after ${done}/${ids.length}: ${e.message}`;notify(progress.textContent,'error');for(const b of [bValidate,bRecord,bApply])b.disabled=!owner;}
   }
   bValidate.onclick=()=>runBulk('validate');bRecord.onclick=()=>runBulk('record');bApply.onclick=()=>runBulk('apply');
   const row=node('div',null,'bulk-actions');row.append(bValidate,bRecord,bApply);
   bulk.append(node('h3','Bulk actions for selected packages'),selectAll,decision,reason,confirmLabel,row,progress);box.append(bulk);
   const boxes=[];
   selectAllBox.onchange=()=>{for(const b of boxes){b.checked=selectAllBox.checked;if(b.checked)selected.add(b.value);else selected.delete(b.value);}count();};
   for(const p of visible)box.append(buildCatalogCard(p,{selectable:true,boxes,selected,count}));
   if(!all.length)box.append(node('p','No catalog packages prepared yet. Findings need complete evidence-backed object changes before approval.'));else if(!visible.length)box.append(node('p','Nothing matches the selected statuses. Turn on a status above to see decided packages.','hint'));
   const handoffs=node('details');handoffs.append(node('summary',`${(data.handoffs||[]).length} research-note follow-ups`));for(const h of data.handoffs||[]){handoffs.append(node('h4',h.title),node('p',h.summary),node('p',h.reason));}box.append(handoffs);
   const feedable=all.filter(p=>p.status==='pending_review'||p.status==='approved');
   window.__pending.catalog=feedable.map(p=>({rank:(p.display_status==='deployment_pending'?40:p.status==='approved'?30:20),created_at:p.created_at,el:buildCatalogCard(p,{})}));
  }
  el('refresh-findings').onclick=refresh;
  el('decisions-tab').onclick=()=>{showPanel('decisions-panel');refresh();};
  for(const id of ['review-layer','review-status'])el(id).onchange=()=>{limit=10;draw();};
  el('more-findings').onclick=()=>{limit+=10;draw();};
  refresh();
})();
