'use strict';
(()=>{
  const el=id=>document.getElementById(id);
  const node=(tag,text)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;return n;};
  const box=node('section');box.id='visual-recommendations';box.className='visual-review-section';
  box.append(node('h2','Visual recommendations'),node('p','Muse recommends; you choose. Approving a preview does not apply or publish it. New designs can be endorsed for implementation, then reviewed again.'));
  const refresh=node('button','Refresh recommendations'),assess=node('button','Check accepted data (no model)'),status=node('p'),filter=node('select'),list=node('div'),digest=node('details');
  status.setAttribute('role','status');filter.setAttribute('aria-label','Visual recommendation status');
  for(const [v,t] of [['pending_review','Pending review'],['all','All decisions'],['approved','Accepted previews'],['endorsed','Endorsed directions'],['rejected','Declined'],['deferred','Deferred'],['changes_requested','Changes requested']]){const o=node('option',t);o.value=v;filter.append(o);}
  const tools=node('div');tools.className='visual-toolbar';tools.append(refresh,assess,filter);box.append(tools,status,list,digest);el('review-panel').prepend(box);
  let rows=[],owner=null,limit=10;
  async function post(route,value){const r=await fetch(route,{method:'POST',headers:{'Content-Type':'application/json','X-Session-Key':location.pathname.split('/')[1]},body:JSON.stringify(value)});const d=await r.json();if(!r.ok)throw Error(d.error||'Visual review failed');return d;}
  function link(text,path){const a=node('a',text);a.href=path;a.target='_blank';a.rel='noopener noreferrer';return a;}
  function draw(){
    list.replaceChildren();const selected=rows.filter(p=>filter.value==='all'||p.status===filter.value);
    if(!selected.length)list.append(node('p','No recommendations match. KEEP, evidence gaps and unassessed displays are in the assessment below.'));
    for(const p of selected.slice(0,limit)){
      const card=node('article');card.className='finding-card visual-proposal';
      card.append(node('p',p.display.layer+' · '+p.response.action+' · '+p.status),node('h3',p.display.title));
      card.append(node('p',p.implementation_required?'Specification: needs implementation and a final preview before application.':'Supported preview: accepting approves this exact proposal for a separate maintainer application.'));
      card.append(link('Compare current and proposed ↗','visual-preview/'+p.id));
      const halves=node('div');halves.className='visual-comparison';
      for(const [title,text] of [['Current / keep case',p.response.keep_case.text],['Proposed change',p.response.what_changes.text]]){const part=node('section');part.append(node('h4',title),node('p',text));halves.append(part);}card.append(halves);
      for(const [key,title] of [['why','Why it matters'],['what_we_lose','What we lose'],['limitations','Limitations'],['next_evidence','Next evidence']])card.append(node('h4',title),node('p',p.response[key].text));
      const details=node('details');details.append(node('summary','Evidence, calculations and decision history'));
      details.append(node('p','Frozen: '+p.created_at+'. Scores are advisory judgments, not factual verification. This is a bounded candidate review, not an exhaustive comparison.'));
      for(const o of p.packet.observations){const m=p.packet.metrics.find(m=>m.id===o.metric);details.append(node('p',`${o.id} · ${o.period} · ${o.precision} ${o.value}${o.upper===null?'':' to '+o.upper} ${m.unit} · ${o.status} · ${m.scope}`));}
      for(const s of p.packet.sources){try{const u=new URL(s.url);if(u.protocol==='https:'&&!u.username&&!u.password)details.append(link(`${s.publisher} · published ${s.published||'unknown'} ↗`,u.href));}catch{}}
      details.append(node('pre',JSON.stringify({calculation:p.packet.calculation,inputs_needing_interpretation:p.packet.current_evidence_needing_interpretation,scores:p.scores,coverage:p.packet.coverage,decision:p.last_review,config_after:p.config_after,catalog_sample:p.packet.catalog_sample},null,2)));card.append(details);
      const form=node('form');form.className='finding-review';const decision=node('select');decision.setAttribute('aria-label','Visual decision');
      for(const [v,t] of [[p.implementation_required?'endorsed':'approved',p.implementation_required?'Accept direction — implement then preview':'Accept exact preview'],['rejected','Decline'],['deferred','Defer'],['changes_requested','Request changes']]){const o=node('option',t);o.value=v;decision.append(o);}
      const reason=node('textarea');reason.required=true;reason.maxLength=1200;reason.setAttribute('aria-label','Reason for visual decision');reason.placeholder='What should be kept, changed, or investigated?';
      const dateLabel=node('label','Reconsider after (for Defer)'),date=node('input');date.type='date';dateLabel.append(date);dateLabel.hidden=true;decision.onchange=()=>{dateLabel.hidden=decision.value!=='deferred';date.required=decision.value==='deferred';};
      const label=node('label');label.className='toggle';const confirm=node('input');confirm.type='checkbox';confirm.required=true;label.append(confirm,node('span','I reviewed this proposal and its evidence. Nothing will be applied or published.'));
      const submit=node('button','Record visual decision'),message=node('p');submit.disabled=!owner;message.setAttribute('role','status');form.append(decision,reason,dateLabel,label,submit,message);card.append(form);
      form.onsubmit=async event=>{event.preventDefault();submit.disabled=true;try{await post('visual-review',{id:p.id,decision:decision.value,rationale:reason.value,confirmed:confirm.checked,proposal_hash:p.proposal_hash,review_hash:p.review_hash,reconsider_after:decision.value==='deferred'?date.value+'T23:59:59Z':null});await load();status.textContent='Decision saved. Nothing applied or published.';}catch(e){message.textContent=e.message;submit.disabled=!owner;}};list.append(card);
    }
    if(selected.length>limit){const more=node('button','Show more recommendations');more.onclick=()=>{limit+=10;draw();};list.append(more);}
  }
  async function load(){status.textContent='Loading private recommendations…';try{const r=await fetch('visuals');if(r.status===404)throw Error('Reopen Research-Control.cmd to load the visual recommendations server.');const data=await r.json();if(!r.ok)throw Error(data.error||'Could not load recommendations');rows=data.proposals;owner=data.reviewer;assess.disabled=!owner;digest.replaceChildren(node('summary','Assessment: KEEP, evidence gaps and unassessed displays'));
    if(data.assessment){const a=data.assessment;digest.append(node('p',`${a.at} · ${a.model_calls} model calls · ${a.unassessed.length} displays unassessed. ${data.invalid_files} unreadable proposal files.`));for(const row of a.rows){const d=node('details');d.append(node('summary',`${row.title} · ${row.status} · ${row.model_status}`),node('p',row.rule),node('pre',JSON.stringify(row,null,2)));digest.append(d);}}
    else digest.append(node('p','No assessment yet. An offline check inventories accepted evidence; session conclusion runs bounded model recommendations.'));
    status.textContent=`${rows.length} retained proposals. Decisions are private.`;draw();
  }catch(e){status.textContent=e.message;}}
  refresh.onclick=load;filter.onchange=()=>{limit=10;draw();};assess.onclick=async()=>{assess.disabled=true;status.textContent='Checking accepted data without inference…';try{await post('visual-assess',{model:false});await load();}catch(e){status.textContent=e.message;}finally{assess.disabled=!owner;}};
  el('review-tab').addEventListener('click',load);
})();
