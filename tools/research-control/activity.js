'use strict';
(()=>{
  const el=id=>document.getElementById(id);
  function node(tag,text,className){const n=document.createElement(tag);if(text!==undefined&&text!==null)n.textContent=text;if(className)n.className=className;return n;}
  const GRADE_LABEL={A:'Official statistics or filings',B:'Company statement',C:'News report',D:'Unverified secondary or social claim'};
  const PROMOTION_LABEL={pending_review:'Needs review',deferred:'Deferred',approved:'Approved, not yet applied',
    deployment_pending:'Pushed · awaiting deployment check',rejected:'Rejected',applied:'Applied'};
  function confirmationText(e){
    if(e.retracted)return `Retracted ${e.retracted_at} by ${e.retracted_by}: ${e.retraction_reason}`;
    const c=e.confirmation;
    if(!c||c==='unconfirmed'){
      const reported=e.reported_on||e.date;
      const days=reported?(Date.now()-new Date(reported+'T00:00:00Z').getTime())/86400000:null;
      return days!==null&&days>90?'Reported, not yet confirmed · unconfirmed after 90 days':'Reported, not yet confirmed';
    }
    const [state,oid]=c.split(':');
    return (state==='confirmed_by'?'Confirmed by ':'Contradicted by ')+oid;
  }
  // Deliverable 5: grade C/D reports publish automatically and never reach Decisions -- this
  // is the only reviewer-facing list of them. Retract is a single-step action (like
  // review-discovery), not a catalog package: there is no field to preview, only a flag to
  // flip and an audit entry to write.
  function retractForm(e,owner){
    const form=node('form',null,'finding-review');
    const reasonLabel=node('label','Reason for retraction'),reason=node('textarea');reason.required=true;reason.maxLength=500;reason.rows=2;reasonLabel.append(reason);
    const confirmLabel=node('label',null,'toggle'),confirm=node('input');confirm.type='checkbox';confirm.required=true;confirmLabel.append(confirm,node('span','I reviewed this report and its evidence. Retracting replaces it; it stays in the record.'));
    const save=node('button','Retract report');save.type='submit';save.disabled=!owner;
    const message=node('p',null,'hint');message.setAttribute('role','status');
    form.append(reasonLabel,confirmLabel,save,message);
    form.onsubmit=async event=>{
      event.preventDefault();save.disabled=true;
      try{
        const r=await fetch('retract',{method:'POST',headers:{'Content-Type':'application/json','X-Session-Key':sessionKey()},body:JSON.stringify({id:e.id,rationale:reason.value,confirmed:confirm.checked})});
        const data=await r.json();if(!r.ok)throw new Error(data.error||'Retraction could not be recorded');
        await load();
      }catch(err){message.textContent=err.message;save.disabled=!owner;}
    };
    return form;
  }
  // Deliverable: turning a recognized report into tracked coverage is one tap ("Track this"),
  // next to Retract. It never edits the catalog itself -- it drafts a private catalog_change
  // package (report_promotion.promote) that waits in Decisions like any other. A report already
  // promoted shows that queued/decided state instead of the control; a retracted report shows
  // neither (see the !e.retracted guard below, shared with Retract).
  function trackAction(e,owner){
    const wrap=node('div');
    const button=node('button','Track this');button.type='button';button.disabled=!owner;
    const message=node('p',null,'hint');message.setAttribute('role','status');
    button.onclick=async()=>{
      button.disabled=true;message.textContent='';
      try{
        const r=await fetch('report-promote',{method:'POST',headers:{'Content-Type':'application/json','X-Session-Key':sessionKey()},body:JSON.stringify({id:e.id})});
        const data=await r.json();if(!r.ok)throw new Error(data.error||'This report could not be queued for review');
        notify(`Queued "${e.title}" for review in Decisions.`,'ok');
        await load();
      }catch(err){message.textContent=err.message;button.disabled=!owner;}
    };
    wrap.append(button,message);
    return wrap;
  }
  function promotionStatus(promo){
    const label=PROMOTION_LABEL[promo.status]||promo.status.replaceAll('_',' ');
    const p=node('p',`Queued for review: ${label}.`,'eyebrow');
    const link=node('a','Open in Decisions →');link.href='#';
    link.onclick=event=>{event.preventDefault();el('decisions-tab').click();};
    const wrap=node('div');wrap.append(p,link);
    return wrap;
  }
  function reportCard(e,owner,promotions){
    const card=node('article',null,'finding-card');
    card.append(node('p',`${e.grade?`Grade ${e.grade} (${GRADE_LABEL[e.grade]||''}) · `:''}${e.kind} · ${e.layer}`,'eyebrow'),node('h3',e.title));
    card.append(node('p',e.summary,'finding-claim'));
    card.append(node('p',`${e.outlet||'Outlet unlisted'} · ${e.reported_on||'date unlisted'} · about: ${(e.about||[]).join(', ')||'none linked'}`,'hint'));
    card.append(node('p',confirmationText(e),e.retracted?'hint':'eyebrow'));
    if(e.quote)card.append(node('p','“'+e.quote+'”','hint'));
    if(!e.retracted){
      const promo=promotions[e.id];
      card.append(promo?promotionStatus(promo):trackAction(e,owner));
      card.append(retractForm(e,owner));
    }
    return card;
  }
  async function load(){
    el('activity-message').textContent='Loading automated activity…';
    try{
      const r=await fetch('activity');
      if(r.status===404)throw new Error('Reopen Research-Control.cmd to load the activity log on the newly started server.');
      const data=await r.json();if(!r.ok)throw new Error(data.error||'Could not load activity');
      const box=el('activity-log');box.replaceChildren();
      if(data.unreadable_events)box.append(node('p',`${data.unreadable_events} unreadable audit-log line(s) skipped.`,'banner-warning'));
      const promotions=data.promotions||{};
      const reports=node('section');reports.append(node('h3','News reports & social posts (grade C/D)'));
      reports.append(node('p',data.reviewer?`Reviewing as ${data.reviewer}. Additions publish automatically; Track this drafts a catalog package, Retract is the one human action.`:'Read-only: this account is not an authorized reviewer.','hint'));
      if(!data.reports.length)reports.append(node('p','No grade C/D reports published yet.','empty-inbox'));
      for(const e of data.reports)reports.append(reportCard(e,data.reviewer,promotions));
      box.append(reports);
      const events=node('section');events.append(node('h3','Publication-policy events'));
      if(!data.policy_events.length)events.append(node('p','No automatic approvals or applications recorded yet.','empty-inbox'));
      for(const e of [...data.policy_events].reverse()){
        const row=node('article',null,'finding-card');
        row.append(node('p',`${e.at} · ${e.kind} · ${e.status}`,'eyebrow'),node('p',e.id));
        if(e.rationale)row.append(node('p',e.rationale,'hint'));
        if(e.commit)row.append(node('p','Commit '+e.commit.slice(0,10),'hint'));
        events.append(row);
      }
      box.append(events);
      if(data.digests.length){
        const section=node('section');section.append(node('h3','Importer digests'));
        for(const d of data.digests){const detail=node('details');detail.append(node('summary',d.file),node('pre',JSON.stringify(d.value,null,2)));section.append(detail);}
        box.append(section);
      }
      el('activity-message').textContent=`${data.reports.length} report(s), ${data.policy_events.length} automated event(s)${data.digests.length?`, ${data.digests.length} digest file(s)`:''}.`;
    }catch(e){el('activity-message').textContent=e.message;}
  }
  el('refresh-activity').onclick=load;
  el('activity-tab').onclick=()=>{showPanel('activity-panel');load();};
})();
