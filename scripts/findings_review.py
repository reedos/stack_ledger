"""Human-operated local discovery inbox using the existing queue and audit log."""
import getpass
import json
import re
from pathlib import Path
from discovery import record_review, FIELDS, KINDS, BASES
from editorial_review import queue, events, now
from research import load, digest

RID=re.compile(r'discovery-[a-f0-9]{24}')


def reviewer(root,identity=None):
    """identity=None or channel 'loopback' -> today's getpass.getuser()/reviewer_accounts mapping.
    channel 'tailnet' -> the Tailscale login against a new reviewer_logins map. An unmapped login
    resolves to None; callers must refuse the request rather than silently downgrading to read-only."""
    p=load(root/'research/editorial-policy.json')
    if identity is not None and identity.get('channel')=='tailnet':
        login=identity.get('login')
        matches=[r for r in p['reviewers'] if login in p.get('reviewer_logins',{}).get(r,[])]
        return matches[0] if len(matches)==1 else None
    account=getpass.getuser().lower()
    matches=[r for r in p['reviewers'] if account in p.get('reviewer_accounts',{}).get(r,[])]
    return matches[0] if len(matches)==1 else None


def authorized(root,reviewer_id,identity=None):
    """True only if reviewer_id is exactly who the current request resolves to; re-derived, never trusted as-passed."""
    return bool(reviewer_id) and reviewer(root,identity)==reviewer_id


def inbox(root,identity=None):
    report={};history=events(root,report=report);latest={}
    for event in history:
        if event.get('kind')=='coverage_expansion':latest[event['id']]=event
    rows=[];invalid=0
    for path in sorted(queue(root).glob('discovery-*.json')):
        try:
            item=load(path);rid=item['id'];finding=item['finding']
            if not RID.fullmatch(rid) or path.stem!=rid or item['kind']!='coverage_expansion':raise ValueError()
            if set(finding) not in (FIELDS,FIELDS-{'layer'}) or finding['kind'] not in KINDS or finding['basis'] not in BASES:raise ValueError()
            if finding.get('layer',item['layer'])!=item['layer']:raise ValueError()
            if any(not isinstance(v,str) or len(v)>2200 for v in finding.values()):raise ValueError()
            event=latest.get(rid)
            proof=None;sha=item.get('document_sha256','')
            if re.fullmatch('[a-f0-9]{64}',sha):
                evidence=root/'.local/discovery/evidence'/(sha+'.json')
                if evidence.exists():proof=load(evidence)
            rows.append(dict(id=rid,layer=item['layer'],url=item['url'],created_at=item['created_at'],
                finding=finding,screening=item.get('screening'),authority=item.get('authority'),novelty=item.get('novelty'),
                published_at=proof.get('published_at') if proof else None,
                retrieved_at=proof.get('retrieved_at') if proof else None,
                status=event['status'] if event else 'pending_review',last_review=event,
                proposal_hash=digest(json.dumps(item,sort_keys=True)),review_hash=digest(json.dumps(event,sort_keys=True))))
        except (OSError,ValueError,KeyError,TypeError):invalid+=1
    rows.sort(key=lambda row:row['created_at'],reverse=True)
    from catalog_review import inbox as catalog_inbox
    handoffs=[]
    for path in queue(root).glob('note-*.json'):
        try:
            item=load(path)
            if not isinstance(item,dict):raise ValueError('Invalid note handoff')
            if item.get('review_required') and item.get('note'):
                handoffs.append({'id':path.stem,'title':item['note']['title'],'summary':item['note']['summary'],'source':item['source'],'reason':item.get('reason','')})
        except (OSError,ValueError,KeyError,TypeError):invalid+=1
    for path in queue(root).glob('draft-*.json'):
        try:
            item=load(path)
            if not isinstance(item,dict):raise ValueError('Invalid catalog draft')
            if item.get('status') not in {'packaged'}:
                handoffs.append({'id':path.stem,'title':item['note']['title'],'summary':item['note']['summary'],
                    'source':item['source']['id'],'reason':item.get('status','')+': '+item.get('reason','')})
        except (OSError,ValueError,KeyError,TypeError):invalid+=1
    errors=[];packages=catalog_inbox(root,errors);invalid+=len(errors)
    importer_events=list(reversed([e for e in history if e.get('kind')=='importer_apply'][-30:]))
    import catalog_jobs
    return {'findings':rows,'reviewer':reviewer(root,identity),'invalid_files':invalid,
            'unreadable_events':report.get('unreadable_events',0),
            'catalog_packages':packages,'handoffs':handoffs,'importer_events':importer_events,
            'jobs':catalog_jobs.read_recent(root),
            'publication':'Discovery triage and catalog approval are distinct. Preview, approve, then explicitly apply and publish catalog packages.'}


def review(root,value,identity=None):
    fields={'id','decision','rationale','proposal_hash','review_hash','confirmed'}
    if not isinstance(value,dict) or set(value)!=fields:raise ValueError('Invalid review fields')
    if not isinstance(value['id'],str) or not RID.fullmatch(value['id']):raise ValueError('Invalid finding ID')
    if value['decision'] not in ('investigate','deferred','rejected'):raise ValueError('Choose Investigate, Defer or Reject')
    if not isinstance(value['rationale'],str) or not 1<=len(value['rationale'].strip())<=1200:raise ValueError('Give a review reason (up to 1200 characters)')
    if value['confirmed'] is not True:raise ValueError('Confirm that you reviewed this finding')
    if any(not isinstance(value[k],str) or not re.fullmatch('[a-f0-9]{64}',value[k]) for k in ['proposal_hash','review_hash']):raise ValueError('Reload the finding before reviewing')
    owner=reviewer(root,identity)
    if owner is None:raise ValueError('This local account is not an authorized reviewer')
    record_review(root,value['id'],value['decision'],owner,value['rationale'].strip(),now(),human_confirm=True,
                  expected_hash=value['proposal_hash'],expected_review=value['review_hash'],identity=identity)
    return {'saved':True,'reviewer':owner,'status':value['decision'],'published':False}
