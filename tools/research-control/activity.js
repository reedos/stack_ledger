'use strict';
(()=>{
  const el=id=>document.getElementById(id);
  function node(tag,text,className){const n=document.createElement(tag);if(text!==undefined&&text!==null)n.textContent=text;if(className)n.className=className;return n;}
  async function load(){
    el('activity-message').textContent='Loading automated activity…';
    try{
      const r=await fetch('activity');
      if(r.status===404)throw new Error('Reopen Research-Control.cmd to load the activity log on the newly started server.');
      const data=await r.json();if(!r.ok)throw new Error(data.error||'Could not load activity');
      const box=el('activity-log');box.replaceChildren();
      if(data.unreadable_events)box.append(node('p',`${data.unreadable_events} unreadable audit-log line(s) skipped.`,'banner-warning'));
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
      el('activity-message').textContent=`${data.policy_events.length} automated event(s)${data.digests.length?`, ${data.digests.length} digest file(s)`:''}.`;
    }catch(e){el('activity-message').textContent=e.message;}
  }
  el('refresh-activity').onclick=load;
  el('activity-tab').onclick=()=>{showPanel('activity-panel');load();};
})();
