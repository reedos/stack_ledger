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
      draw();drawCatalog(data);drawPublishingStrip(data);buildFindingFeed();
      let msg=`${findings.length} discovery finding${findings.length===1?'':'s'} on file.`;if(data.invalid_files)msg+=` ${data.invalid_files} unreadable records need maintenance.`;
      el('review-message').textContent=msg;
    }catch(e){el('review-message').textContent=e.message;}
    window.renderDecisionFeed();
  }
  // Automatic validation and the Publishing strip need no tap to move forward, so poll for them --
  // skipped while the reviewer is actively typing in an open card so a redraw never eats their draft.
  setInterval(()=>{
    const active=document.activeElement;
    if(active&&(el('decision-feed').contains(active)||el('catalog-packages')?.contains(active)))return;
    refresh();
  },5000);
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
  const LIVE_SITE='https://reedos.github.io/stack_ledger/';
  // The exact landing element for a change, so "Show" opens the changed graphic itself, never the
  // homepage: a real per-object anchor on the built pages (site/assets/*.js renders every one of these).
  function placeOf(c){const id=encodeURIComponent(c.id);switch(c.target){
    case 'project':return ['projects/#project-'+id,'Projects page, card "'+(c.after.name||c.id)+'" (stage '+(c.after.stage||'?')+')'];
    case 'company':return ['companies/'+id+'/','Company page '+(c.after.name||c.id)];
    case 'product':{const layer=(c.after.layers||['models'])[0],anchor=(layer==='models'?'agent-':'product-')+id;return [layer+'/#'+anchor,'Layer page '+layer+', product '+(c.after.name||c.id)];}
    case 'note':return ['ledger/#'+id,'Ledger, research note "'+(c.after.title||c.id)+'"'];
    case 'observation':return ['ledger/#'+id,'Ledger, record '+c.id];
    case 'metric':{const layer=c.after.layer;return [layer?layer+'/#metric-'+id:'ledger/','Layer page, metric '+(c.after.title||c.id)];}
    case 'source':return ['methodology/#source-'+id,'Methodology, source library: '+(c.after.title||c.id)];
    default:return ['',''];}}
  // Open the exact place a change lives: the validated preview when one exists, else the live site
  // (only correct once published). Full-screen overlay on phones, a new tab on desktop.
  function showChange(p,path,title){
    if(!path)return;
    const validated=p.validation&&p.validation.passed&&p.validation.proposal_hash===p.proposal_hash;
    const src=validated?('preview/'+p.id+'/'+path):(LIVE_SITE+path);
    if(window.isPhoneWidth&&window.isPhoneWidth()){window.openPreview(src,title);return;}
    window.open(src,'_blank','noopener');
  }
  function fmtValue(v){if(v===null||v===undefined)return '—';if(Array.isArray(v))return v.join(', ');if(typeof v==='object')return JSON.stringify(v);return String(v);}
  const CHANGE_FIELDS={project:['name','stage','next_evidence'],company:['name','role'],product:['name','stage'],
    source:['title','publisher','url'],metric:['title','unit'],note:['title','summary'],
    observation:['period','year','value','upper','status','note','retrieved_at']};
  function objectLabel(c,siblings){
    const a=c.after||{};
    if(c.target==='observation'){
      const metricChange=siblings.find(x=>x.target==='metric'&&x.id===a.metric);
      const projectChange=siblings.find(x=>x.target==='project'&&((x.after||{}).observations||[]).includes(c.id));
      return (metricChange?metricChange.after.title:a.metric||c.id)+(projectChange?' · '+(projectChange.after.name||projectChange.id):'');
    }
    return a.name||a.title||c.id;
  }
  function changeRows(c){
    const b=c.before,a=c.after||{},rows=[];
    for(const f of (CHANGE_FIELDS[c.target]||Object.keys(a))){
      if(a[f]===undefined)continue;
      const before=b?b[f]:undefined,unchanged=b&&JSON.stringify(before)===JSON.stringify(a[f]);
      if(unchanged)rows.push({unchanged:true,text:`${f.replaceAll('_',' ')} ${fmtValue(a[f])} unchanged`});
      else rows.push({unchanged:false,text:`${f.replaceAll('_',' ')}: ${b?fmtValue(before):'new'} → ${fmtValue(a[f])}`});
    }
    return rows;
  }
  // Compact before/after table at the top of every card: read the exact change in seconds, no
  // hunting through the built site for the changed graphic. Large same-source relabel batches
  // (10+ observation-only changes) collapse into one line per metric with an expander.
  function buildChangeTable(p){
    const box=node('div',null,'change-table'),changes=p.changes;
    const allRelabel=changes.length>8&&changes.every(c=>c.target==='observation'&&c.before);
    const row=c=>{
      const r=node('div',null,'change-row');
      r.append(node('strong',objectLabel(c,changes)));
      for(const line of changeRows(c))r.append(node('p',line.text,line.unchanged?'unchanged':'changed'));
      const [path,label]=placeOf(c);
      if(path){const l=node('a','Show');l.href='#';l.onclick=e=>{e.preventDefault();showChange(p,path,label);};r.append(l);}
      return r;
    };
    if(allRelabel){
      const groups=new Map();
      for(const c of changes){const key=c.after.metric||c.id;if(!groups.has(key))groups.set(key,[]);groups.get(key).push(c);}
      for(const [metric,group] of groups){
        const periods=group.map(c=>c.after.period).sort();
        box.append(node('p',`${group.length} record${group.length===1?'':'s'} · metric ${metric} · period ${periods[0]} → ${periods.at(-1)}; values unchanged`,'change-row-summary'));
        const details=node('details');details.append(node('summary',`Show all ${group.length} records`));
        for(const c of group)details.append(row(c));
        box.append(details);
      }
      return box;
    }
    for(const c of changes)box.append(row(c));
    return box;
  }
  const STATUS_LABELS={pending_review:'Needs review',deferred:'Deferred',approved:'Approved, not yet applied',deployment_pending:'Pushed · awaiting deployment check',rejected:'Rejected',applied:'Applied'};
  async function latestPackage(id){const r=await fetch('findings');const d=await r.json();return (d.catalog_packages||[]).find(q=>q.id===id);}
  // Everything from validPreview to buildCatalogCard is DOM-free: the bulk bar and the Publishing
  // strip decide here, and tests/control_decisions.cjs evaluates exactly this span.
  function validPreview(p){return !!(p.validation&&p.validation.passed&&p.validation.proposal_hash===p.proposal_hash);}
  function activeJob(p,kind){return p.job&&p.job.kind===kind&&(p.job.status==='queued'||p.job.status==='running')?p.job:null;}
  function publishState(p){
    const job=p.job&&p.job.kind==='publish'?p.job:null;
    if(job&&(job.status==='queued'||job.status==='running'))return job.status;
    // An applied package is the success case: catalog_review.mark_deployed records 'applied' the
    // moment the live data matches the pushed commit, and that is the only confirmation there is.
    if(p.status==='applied')return 'deployed';
    if(job&&job.status==='failed')return 'failed';
    if(p.display_status==='deployment_pending')return 'pending';
    if(job&&job.status==='done')return (job.result&&job.result.status==='deployed')?'deployed':'pending';
    return 'unpublished';
  }
  function publishStatusText(p,state){
    const job=p.job,commit=((job&&job.result&&job.result.commit)||(p.publication_receipt&&p.publication_receipt.commit)||'').slice(0,10);
    return {queued:'queued',running:(job&&job.step)||'applying',failed:'failed: '+((job&&job.error)||'unknown error'),
      deployed:'live ✓'+(commit?' · commit '+commit:''),pending:'pushed, waiting for the live site'+(commit?' · commit '+commit:''),
      unpublished:'approved, not yet published'}[state];
  }
  // An applied package used to drop out of this strip on the very poll that proved publication had
  // worked, so 'live' was unreachable and a published package vanished from every surface. It now
  // stays for as long as its publish job is retained (catalog_jobs keeps 24h), then leaves on its own.
  function publishingPackages(all){
    return (all||[]).filter(p=>{
      const published=!!(p.job&&p.job.kind==='publish');
      if(p.status==='rejected')return false;
      if(p.status==='applied')return published;
      return p.status==='approved'||p.display_status==='deployment_pending'||published;
    });
  }
  function bulkSummary(kind,done,queued,total){
    if(kind==='validate')return `Validation queued for ${queued} of ${total} packages; each card updates when its preview finishes.`;
    if(kind==='record')return `Decision recorded for ${done} of ${total} packages.`;
    return `Approved and queued publication for ${done} of ${total}.`+(queued?` ${queued} had no validated preview yet and ${queued===1?'is':'are'} queued for validation now; approve once the card shows a passing preview.`:'');
  }
  // Bulk actions enqueue and stop there; they never read job state back to decide. Reading it back
  // one request later always found the job it had just created still 'queued', so every bulk tap died
  // on a false "Preview failed" before touching a single package (2026-09-11). Defer/Reject need no
  // preview at all, so they run first and are never diverted into validation.
  async function runBulk(kind,ctx){
    const {ids,post,latest,report}=ctx;
    if(!ids.length){report('Select at least one package.');return {done:0,queued:0,error:'No package selected'};}
    if(kind==='record'&&(!ctx.rationale.trim()||!ctx.confirmed)){const m='A reason and the confirmation are required.';report(m);return {done:0,queued:0,error:m};}
    let done=0,queued=0;
    try{
      for(const id of ids){
        let q=await latest(id);
        if(!q)throw new Error(`${id} is no longer in the queue`);
        report(`${done+queued+1}/${ids.length}: ${q.title}`);
        if(kind==='record'){await post('catalog-review',{id,decision:ctx.decision,rationale:ctx.rationale,proposal_hash:q.proposal_hash,review_hash:q.review_hash,confirmed:true});done++;continue;}
        if(kind==='validate'||!validPreview(q)){await post('catalog-preview',{id});queued++;continue;}
        await post('catalog-review',{id,decision:'approved',rationale:ctx.rationale.trim()||q.title,proposal_hash:q.proposal_hash,review_hash:q.review_hash,confirmed:true});
        q=await latest(id);
        await post('catalog-publish',{id,proposal_hash:q.proposal_hash,review_hash:q.review_hash,confirmed:true});
        done++;
      }
    }catch(e){report(`Stopped after ${done+queued} of ${ids.length}: ${e.message}`);return {done,queued,error:e.message};}
    report(bulkSummary(kind,done,queued,ids.length));
    return {done,queued};
  }
  function buildCatalogCard(p,{selectable,boxes,selected,count}={}){
    const card=node('article',null,'finding-card');
    const display=p.display_status||p.status;
    card.append(node('h3',p.title),node('p',`${p.author} · ${STATUS_LABELS[display]||display} · ${p.changes.length} object changes`));
    if(p.auto_apply_eligible!==null&&p.auto_apply_eligible!==undefined)
      card.append(node('p',`Auto-apply eligible: ${p.auto_apply_eligible?'Yes':'No'}${p.auto_apply_reasons&&p.auto_apply_reasons.length?' — '+p.auto_apply_reasons[0]:''}`,'hint'));
    if(selectable&&p.status!=='applied'){const sel=node('label',null,'toggle-chip select-chip'),sb=node('input');sb.type='checkbox';sb.value=p.id;sb.setAttribute('aria-label','Select '+p.title);sb.onchange=()=>{if(sb.checked)selected.add(p.id);else selected.delete(p.id);count();};boxes.push(sb);sel.append(sb,node('span','Select'));card.append(sel);}
    if(p.last_review&&p.status!=='applied')card.append(node('p',`Last decision: ${p.last_review.status.replaceAll('_',' ')} · ${new Date(p.last_review.at).toLocaleString()} · ${p.last_review.reviewer||''}${p.last_review.rationale?' — '+p.last_review.rationale:''}`,'hint'));
    card.append(buildChangeTable(p));
    for(const change of p.changes){
      const detail=node('details');detail.append(node('summary',`${change.target}: ${change.id} — ${change.before?'update':'new entry'}`));
      // Readable summary of the proposed object first; raw JSON stays available below it.
      const dl=node('dl',null,'change-summary');const a=change.after||{};
      const fields={project:['name','owner','location','category','stage','ai_relationship','grid','horizon','next_evidence','company_ids'],company:['name','layers','role','region_book','revenue_kind'],product:['name','layers','description','status','gap'],source:['publisher','title','url','published','layers','license'],note:['title','summary','layer','kind','date'],observation:['metric','year','period','value','upper','status','precision','note'],metric:['title','unit','geography','scope','allowed_statuses','period_basis']}[change.target]||Object.keys(a);
      for(const k of fields){if(a[k]===undefined||a[k]===null||a[k]==='')continue;const v=Array.isArray(a[k])?a[k].join(', '):(typeof a[k]==='object'?JSON.stringify(a[k]):String(a[k]));const dt=node('dt',k.replaceAll('_',' '));const dd=node('dd',v);if(change.before&&JSON.stringify(change.before[k])!==JSON.stringify(a[k]))dd.className='changed';dl.append(dt,dd);}
      if(change.target==='project'&&Array.isArray(a.milestones))for(const m of a.milestones){dl.append(node('dt','milestone'+(m.date?' '+m.date:'')),node('dd',m.summary+' [source '+m.source+']'));}
      detail.append(dl);
      const raw=node('details');raw.append(node('summary','Raw JSON (before / after)'),node('h4','Before'),node('pre',JSON.stringify(change.before,null,2)),node('h4','After'),node('pre',JSON.stringify(change.after,null,2)));detail.append(raw);
      card.append(detail);
    }
    for(const evidence of p.evidence){const detail=node('details');detail.append(node('summary','Evidence: '+evidence.id),node('p',evidence.summary),node('p',`Published: ${evidence.published_at||'unknown'} · Retrieved: ${evidence.retrieved_at} · Registered source rank: ${evidence.source_rank??'unregistered'}`));try{const u=new URL(evidence.url);if(u.protocol==='https:'&&!u.username&&!u.password){const a=node('a','Read source ↗');a.href=u.href;a.target='_blank';a.rel='noopener noreferrer';detail.append(a);}}catch(e){}card.append(detail);}
    const failing=p.validation&&!p.validation.passed?(p.validation.checks||[]).find(c=>!c.passed):null;
    const msg=node('p',p.validation?(p.validation.passed?'Preview validated: validate, build, tests and editorial checks passed. Ready to approve.':`Preview failed: ${failing?failing.command:'a check'} did not pass; open the checks below.`):'Not yet validated.','card-status '+(p.validation?(p.validation.passed?'ok':'error'):''));msg.setAttribute('role','status');card.append(msg);
    if(p.validation){const d=node('details');d.append(node('summary','Validation results'),node('pre',JSON.stringify(p.validation.checks,null,2)));card.append(d);}
    if(p.publication_receipt&&display==='deployment_pending')card.append(node('p','Pushed as commit '+(p.publication_receipt.commit||'').slice(0,10)+'; the live site has not yet confirmed the update. This resolves automatically on the next check.','hint'));
    if(p.status==='applied'){
      // Finished packages: the objects are live (or declined); validating would only report that they changed since proposal.
      const when=p.last_review?.at?new Date(p.last_review.at).toLocaleString():'';
      card.append(node('p','Applied'+(when?' '+when:'')+(p.last_review?.reviewer?' by '+p.last_review.reviewer:'')+'. These objects are live in the catalog; no further action from here.','hint'));
      return card;
    }
    const needsDecision=p.status!=='applied';   // pending_review/deferred are the common case; a rejected or
    const validating=activeJob(p,'validate');   // already-approved package can still be reconsidered at any time.
    // Defer and Reject need no preview, so a queued or running validation hides only the button that
    // would start a second one -- it used to return early and strip the card of every control.
    if(validating){msg.className='card-status';msg.textContent='Validating…'+(validating.step?' '+validating.step:'');}
    else if(!validPreview(p)){
      const preview=node('button','Validate preview');preview.disabled=!owner;preview.onclick=async()=>{preview.disabled=true;msg.className='card-status';msg.textContent='Building and testing the isolated preview (about a minute)…';notify(`Validating "${p.title}"…`,'ok');try{await catalogPost('catalog-preview',{id:p.id});await refresh();notify(`Validating "${p.title}"; the card updates once it finishes.`,'ok');}catch(e){msg.className='card-status error';msg.textContent=e.message;notify(e.message,'error');preview.disabled=false;}};card.append(preview);
    }
    if(!needsDecision)return card;
    // One tap: Approve and publish records the approval, then queues publication in the background
    // (tracked in the Publishing strip) so the reviewer never waits for a preview or a push mid-review.
    const primary=node('form',null,'finding-review one-tap-form');
    const reason=node('textarea');reason.value=p.title;reason.required=true;reason.maxLength=1200;reason.setAttribute('aria-label','Reason for approving this package');
    const confirmLabel=node('label',null,'toggle'),confirm=node('input');confirm.type='checkbox';confirm.required=true;confirmLabel.append(confirm,node('span','I reviewed the exact changes and supporting sources.'));
    const approve=node('button','Approve and publish');approve.className='primary-action';approve.disabled=!owner||!validPreview(p);
    primary.append(reason,confirmLabel,approve);
    primary.onsubmit=async event=>{
      event.preventDefault();
      if(!reason.value.trim()||!confirm.checked){msg.className='card-status error';msg.textContent='Add a one-line reason and tick the confirmation, then try again.';notify(msg.textContent,'error');return;}
      approve.disabled=true;
      try{
        await catalogPost('catalog-review',{id:p.id,decision:'approved',rationale:reason.value,proposal_hash:p.proposal_hash,review_hash:p.review_hash,confirmed:true});
        const fresh=await latestPackage(p.id);
        await catalogPost('catalog-publish',{id:p.id,proposal_hash:fresh.proposal_hash,review_hash:fresh.review_hash,confirmed:true});
        ensureStatusShown('approved');await refresh();
        notify(`Approved "${p.title}". Publishing in the background — track it in the Publishing strip.`,'ok');
      }catch(e){msg.className='card-status error';msg.textContent=e.message;notify(e.message,'error');approve.disabled=false;}
    };
    card.append(primary);
    const secondary=node('details',null,'secondary-decision');secondary.append(node('summary','Defer, reject or approve only'));
    const form=node('form',null,'finding-review'),decision=node('select');for(const [v,label] of [['deferred','Defer'],['rejected','Reject'],['approved','Approve only (publish later from the Publishing strip)']]){const o=node('option',label);o.value=v;decision.append(o);}
    const reason2=node('textarea');reason2.placeholder='Reason for this decision';reason2.required=true;reason2.maxLength=1200;
    const flabel=node('label',null,'toggle'),confirm2=node('input');confirm2.type='checkbox';confirm2.required=true;flabel.append(confirm2,node('span','I reviewed the exact changes and supporting sources.'));
    const submit=node('button','Record decision','secondary');submit.disabled=!owner;
    form.append(decision,reason2,flabel,submit);form.noValidate=true;
    form.onsubmit=async event=>{event.preventDefault();if(!reason2.value.trim()||!confirm2.checked){msg.className='card-status error';msg.textContent='Add a one-line reason and tick the confirmation, then record again.';notify(msg.textContent,'error');return;}submit.disabled=true;try{await catalogPost('catalog-review',{id:p.id,decision:decision.value,rationale:reason2.value,proposal_hash:p.proposal_hash,review_hash:p.review_hash,confirmed:confirm2.checked});ensureStatusShown(decision.value);notify(`Recorded "${decision.value}" for "${p.title}" as ${owner}.`,'ok');await refresh();}catch(e){msg.className='card-status error';msg.textContent=e.message;notify(e.message,'error');submit.disabled=false;}};
    secondary.append(form);card.append(secondary);
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
   const decision=node('select');for(const [v,label] of [['deferred','Defer'],['rejected','Reject'],['approved','Approve only (publish later)']]){const o=node('option',label);o.value=v;decision.append(o);}
   const reason=node('textarea');reason.placeholder='One reason, recorded on every selected package';reason.rows=2;reason.maxLength=1200;
   const confirmLabel=node('label',null,'toggle'),confirm=node('input');confirm.type='checkbox';confirmLabel.append(confirm,node('span','I reviewed the exact changes and supporting sources of every selected package.'));
   const progress=node('p',null,'hint');progress.setAttribute('role','status');
   const bValidate=node('button','Validate selected previews','secondary'),bApprovePublish=node('button','Approve and publish selected'),bRecord=node('button','Record decision for selected','secondary');
   for(const b of [bValidate,bApprovePublish,bRecord])b.disabled=!owner;
   const count=()=>{progress.textContent=`${selected.size} selected.`;};
   const buttons=[bValidate,bApprovePublish,bRecord];
   async function runSelected(kind){
     for(const b of buttons)b.disabled=true;
     const outcome=await runBulk(kind,{ids:[...selected],post:catalogPost,latest:latestPackage,report:text=>{progress.textContent=text;},
       rationale:reason.value,confirmed:confirm.checked,decision:decision.value});
     notify(progress.textContent,outcome.error?'error':'ok');
     for(const b of buttons)b.disabled=!owner;
     if(outcome.done||outcome.queued)await refresh();
   }
   bValidate.onclick=()=>runSelected('validate');bApprovePublish.onclick=()=>runSelected('approve_publish');bRecord.onclick=()=>runSelected('record');
   const row=node('div',null,'bulk-actions');row.append(bApprovePublish,bValidate,decision,bRecord);
   bulk.append(node('h3','Bulk actions for selected packages'),selectAll,
     node('p','One reason, used by "Approve and publish selected" (falls back to each package\'s own title) and by "Record decision for selected" with the status chosen alongside it.','hint'),
     reason,confirmLabel,row,progress);box.append(bulk);
   const boxes=[];
   selectAllBox.onchange=()=>{for(const b of boxes){b.checked=selectAllBox.checked;if(b.checked)selected.add(b.value);else selected.delete(b.value);}count();};
   for(const p of visible)box.append(buildCatalogCard(p,{selectable:true,boxes,selected,count}));
   if(!all.length)box.append(node('p','No catalog packages prepared yet. Findings need complete evidence-backed object changes before approval.'));else if(!visible.length)box.append(node('p','Nothing matches the selected statuses. Turn on a status above to see decided packages.','hint'));
   const handoffs=node('details');handoffs.append(node('summary',`${(data.handoffs||[]).length} research-note follow-ups`));for(const h of data.handoffs||[]){handoffs.append(node('h4',h.title),node('p',h.summary),node('p',h.reason));}box.append(handoffs);
   const feedable=all.filter(p=>p.status==='pending_review'||p.status==='deferred');
   window.__pending.catalog=feedable.map(p=>({rank:20,created_at:p.created_at,el:buildCatalogCard(p,{})}));
  }
  // Publishing strip: approved-but-not-published, pushed-but-unconfirmed and just-published packages,
  // with live status. See publishingPackages for when a finished one stops matching.
  function buildStripItem(p){
    const state=publishState(p);
    const item=node('article',null,'strip-item');
    item.append(node('h4',p.title),node('p',publishStatusText(p,state),'hint'));
    if(state==='failed'||state==='unpublished'){
      const button=node('button',state==='failed'?'Retry publication':'Publish now','secondary');button.disabled=!owner;
      button.onclick=async()=>{button.disabled=true;try{await catalogPost('catalog-publish',{id:p.id,proposal_hash:p.proposal_hash,review_hash:p.review_hash,confirmed:true});await refresh();notify((state==='failed'?'Retrying publication for "':'Publishing "')+p.title+'"…','ok');}catch(e){notify(e.message,'error');button.disabled=false;}};
      item.append(button);
    }
    return item;
  }
  function drawPublishingStrip(data){
    const box=el('publishing-strip');if(!box)return;
    const items=publishingPackages(data.catalog_packages);
    box.replaceChildren();
    if(!items.length){box.hidden=true;return;}
    box.hidden=false;
    box.append(node('h3','Publishing'));
    for(const p of items)box.append(buildStripItem(p));
  }
  el('refresh-findings').onclick=refresh;
  el('decisions-tab').onclick=()=>{showPanel('decisions-panel');refresh();};
  for(const id of ['review-layer','review-status'])el(id).onchange=()=>{limit=10;draw();};
  el('more-findings').onclick=()=>{limit+=10;draw();};
  refresh();
})();
