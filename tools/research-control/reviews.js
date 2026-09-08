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
      draw();if(data.invalid_files)el('review-message').textContent+=` ${data.invalid_files} unreadable records need maintenance.`;
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
  el('refresh-findings').onclick=refresh;
  for(const id of ['review-layer','review-status'])el(id).onchange=()=>{limit=10;draw();};
  el('more-findings').onclick=()=>{limit+=10;draw();};
})();
