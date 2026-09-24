"""Read-only, receipt-backed overnight review and a compact Matrix briefing. No inference."""
import json
import re
from datetime import datetime, timezone
from pathlib import Path

LATEST = 'https://reedos.github.io/stack_ledger/latest/'
STAGES = ('locks', 'importers', 'research', 'policy', 'health', 'prune')
LABELS = {'locks': 'Preparation', 'importers': 'Dataset updates', 'research': 'Research',
          'policy': 'Publication', 'health': 'Checks', 'prune': 'Cleanup'}
IMPORT_NAMES = {'sec':'U.S. company filings (SEC)', 'epoch':'Epoch AI datasets', 'eia':'U.S. energy data', 'bls':'U.S. employment data'}
DECISIONS = {'catalog_packages_pending': 'catalog changes', 'forecast_editions_pending': 'forecast editions', 'forecast_editions_blocked': 'forecast editions that need a maintainer', 'discovery_findings_pending': 'findings',
             'visual_recommendations_pending': 'visual recommendations', 'questions_pending': 'research questions'}

def read(path, default=None):
    try:
        return json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError, ValueError):
        return default

def instant(value):
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(timezone.utc)
    except (ValueError, TypeError, AttributeError):
        return None

def human_date(value):
    d = datetime.strptime(value, '%Y-%m-%d')
    suffix = 'th' if 10 < d.day % 100 < 14 else {1:'st', 2:'nd', 3:'rd'}.get(d.day % 10, 'th')
    return f'{d:%A, %B} {d.day}{suffix}, {d.year}'

def links(root, date):
    """Into Almanac's Research view, which frames the panel at /panel (2026-09-16). The
    standalone Tailscale mount stopped being how Reed reaches it; Almanac is the door, and a
    link that lands there opens the same run or the same decisions with the panel inside."""
    from urllib.parse import quote
    from research_control import tailnet_config
    cfg = tailnet_config(root/'.local/research-control.json')
    almanac = f"https://{cfg['hostname']}:8788/#view=research&rp=" if cfg else None
    return {'review': almanac + quote('#run=' + date, safe='') if almanac else None,
            'decisions': almanac + quote('#decisions', safe='') if almanac else None, 'latest': LATEST}

def sessions_for(root, date, receipt):
    """Bind new receipts by ID; old receipts only by the recorded stage interval."""
    if receipt.get('status') == 'skipped':
        return []
    start, end = instant(receipt.get('started_at')), instant(receipt.get('finished_at'))
    candidates = []
    for path in (root/'.local/sessions').glob('*/status.json'):
        s = read(path, {})
        at = instant(s.get('started_at'))
        if not at or not re.fullmatch('[a-f0-9]{32}', str(s.get('session_id', ''))):
            continue
        if receipt.get('session_id'):
            match = s['session_id'] == receipt['session_id']
        elif start and end:
            match = start <= at <= end and s.get('options', {}).get('overnight') is True
        else:
            match = at.strftime('%Y-%m-%d') == date and s.get('options', {}).get('overnight') is True
        if match:
            candidates.append(s)
    return sorted(candidates, key=lambda s:s['started_at'])

def live_snapshot(root, date='latest'):
    """Overlay current review state without rewriting immutable run receipts."""
    from nightly import pending_decisions
    data = snapshot(root, date)
    counts = pending_decisions(root, strict=True)
    return {**data, 'pending_at_run':data.get('pending', []),
            'pending':[{'kind':k, 'label':DECISIONS[k], 'count':v}
                       for k,v in counts.items() if k!='questions_pending' and v>0],
            'question_backlog':counts.get('questions_pending',0),
            'pending_scope':'current_review_inbox',
            'pending_checked_at':datetime.now(timezone.utc).isoformat()}

def snapshot(root, date='latest', body=None):
    finalizing = body is not None
    dates = sorted({p.name for p in (root/'.local/nightly').glob('*') if re.fullmatch(r'\d{4}-\d{2}-\d{2}', p.name)} |
                   {p.stem for p in (root/'.local/digest').glob('*.json') if re.fullmatch(r'\d{4}-\d{2}-\d{2}', p.stem)})
    if date == 'latest':
        date = dates[-1] if dates else datetime.now(timezone.utc).strftime('%Y-%m-%d')
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', date):
        raise ValueError('Invalid run date')
    label = human_date(date)  # rejects impossible dates too
    saved = read(root/'.local/briefings'/(date+'.json')) if body is None else None
    if isinstance(saved,dict) and saved.get('date') == date:
        return {**saved, 'dates':dates[-60:][::-1], 'links':links(root,date)}
    receipts = {s:read(root/'.local/nightly'/date/(s+'.json'), {}) for s in STAGES}
    body = body if body is not None else read(root/'.local/digest'/(date+'.json'), {})
    sessions = sessions_for(root, date, receipts['research'])
    lock = read(root/'.local/research-session.lock', {})
    from nightly import pid_alive
    active = any(s['session_id'] == lock.get('session_id') for s in sessions) and bool(lock.get('pid')) and pid_alive(lock['pid'])
    stage_status = read(root/'.local/nightly'/date/'live.json', {})
    # A stale live receipt must not disguise a stopped process as active.
    if stage_status.get('pid') and not stage_status.get('finished_at'):
        from nightly import pid_alive
        active = active or pid_alive(stage_status['pid'])
    if finalizing:
        active = False
    documents, totals, hashes = {}, {}, set()
    errors = 0
    for session in sessions:
        folder = root/'.local/sessions'/session['session_id']
        from research_notify import summary
        try:
            counts = summary(folder)
            for key, value in counts.items():
                if isinstance(value, int) and not isinstance(value, bool):
                    totals[key] = totals.get(key, 0) + value
        except (OSError, ValueError, KeyError, TypeError):
            errors += 1
        for path in sorted((folder/'batches').glob('*.json')):
            batch = read(path)
            if not isinstance(batch, dict):
                errors += 1
                continue
            for doc in batch.get('collection', {}).get('documents', []):
                key = (doc.get('url'), doc.get('sha256'))
                if not key[0]:
                    continue
                hashes.add(key[1])
                documents[key] = {k:doc.get(k) for k in ('url', 'title', 'publisher', 'layers', 'published', 'read_at')}
                documents[key]['lane'] = 'Monitoring'
            for attempt in (batch.get('discovery') or {}).get('attempts', []):
                if not attempt.get('document_sha256'):
                    continue
                key = (attempt.get('url'), attempt['document_sha256'])
                hashes.add(key[1])
                documents.setdefault(key, {'url': key[0], 'title': attempt.get('url'), 'layers': [attempt.get('layer')],
                    'lane':'Discovery', 'outcome':attempt.get('outcome'), 'question':attempt.get('question')})
    ledger = read(root/'site/data/ledger.json', {})
    sources = {s['id']:s for s in ledger.get('sources', [])}
    # An event must name a document actually read in this session. Its original date remains visible.
    highlights = []
    for event in ledger.get('events', []):
        at = instant(event.get('retrieved_at'))
        if event.get('document_sha256') not in hashes or not at or at.strftime('%Y-%m-%d') != date:
            continue
        source = sources.get(event.get('source'), {})
        highlights.append({k:event.get(k) for k in ('title','summary','layer','kind','date','grade','confirmation','retracted')})
        highlights[-1]['url'] = source.get('url')
    dashboard = read(root/'.local/nightly'/date/'dashboard.json', {})
    failed = [LABELS[s] for s,r in receipts.items() if r.get('status') in ('failed','timeout')]
    issues = totals.get('source_failures', 0) + totals.get('discovery_errors', 0)
    if active:
        outcome, takeaway = 'running', 'Overnight work is running. Results below update as receipts arrive.'
    elif failed:
        outcome, takeaway = 'needs_attention', 'The night needs attention: ' + ', '.join(failed) + '.'
    elif receipts['research'].get('status') == 'skipped':
        outcome, takeaway = 'skipped', 'Scheduled research did not start. Review the recorded reason before retrying.'
    elif not receipts['research']:
        outcome, takeaway = 'not_recorded', 'No completed research-stage receipt is available for this night.'
    elif issues or any(r.get('status') == 'partial' for r in receipts.values()):
        outcome, takeaway = 'partial', 'The run finished, but some collection or processing work needs attention.'
    else:
        outcome, takeaway = 'completed', 'The overnight workflow finished.'
    if sessions and not active and not highlights and not totals.get('accepted'):
        takeaway += ' No new monitoring findings were accepted.'
    pending = body.get('needs_decision') or receipts['health'].get('pending_decisions') or {}
    return {'date':date, 'date_label':label, 'dates':dates[-60:][::-1], 'outcome':outcome,
        'takeaway':takeaway, 'active':active, 'live_stage':stage_status.get('stage') if active else None,
        'links':links(root,date), 'dashboard':dashboard, 'sessions':[{'id':s['session_id'], 'state':s.get('state'), 'started_at':s.get('started_at'),
            'elapsed_seconds':s.get('elapsed_seconds')} for s in sessions], 'totals':totals,
        'documents':list(documents.values()), 'inventory_errors':errors, 'highlights':highlights,
        'pending':[{'kind':k,'label':DECISIONS.get(k,k.replace('_',' ')), 'count':v} for k,v in pending.items() if isinstance(v,int) and v>0],
        'stages':[{'name':LABELS[s], 'status':r.get('status','not recorded'), 'reason':r.get('reason') or r.get('error'),
                   'elapsed_seconds':r.get('elapsed_seconds')} for s,r in receipts.items()],
        'applied':body.get('applied',[]), 'published_observations':body.get('published_observations',{}),
        'pdf_reader':(receipts['health'].get('pdf_reader') or (body.get('health') or {}).get('pdf_reader') or {}),
        'publication':{'unpushed_commits':body.get('unpushed_commits'), 'final_push':body.get('final_push')},
        'updated_at':datetime.now(timezone.utc).isoformat()}

def compact(text, limit=200):
    value = ' '.join(str(text or '').split())
    # Source-derived prose is data, never Markdown links or instructions in the notification.
    value = re.sub(r'[\[\]<>`*_]', '', value)
    return value if len(value) <= limit else value[:limit-1].rsplit(' ',1)[0]+'…'

def render(data):
    totals = data['totals']
    lines = [f"### Stack Ledger · {data['date_label']}", '', '**'+data['takeaway']+'**', '', '**What came out of it**']
    if data['sessions']:
        lines.append(f"- {len(data['documents'])} document versions listed · {totals.get('accepted',0)} monitoring findings accepted · {totals.get('discovery_proposals',0)} discovery proposals.")
    else:
        lines.append('- Research totals are not recorded for this night.')
    imports = [IMPORT_NAMES.get(x['id'],x['id']) for x in data['applied'] if x.get('kind')=='import']
    if imports:
        lines.append('- Dataset updates: '+', '.join(imports)+'.')
    for h in data['highlights'][:3]:
        qualifier = 'Unconfirmed report' if h.get('grade') in ('C','D') else (h.get('kind') or 'Finding')
        if h.get('retracted'):
            qualifier = 'Retracted report'
        lines.append(f"- {compact(h['title'],100)} — {qualifier}; source dated {human_date(h['date']) if h.get('date') else 'unknown'}. {compact(h.get('summary'),160)}")
    errors = totals.get('source_failures',0) + totals.get('discovery_errors',0)
    watch = []
    if errors:
        watch.append(f'- {errors} collection errors were recorded (may include repeat attempts). The completed run does not mean every source was read.')
    held_back = totals.get('quarantined',0)
    if held_back:
        watch.append(f'- {held_back} figure{"s were" if held_back!=1 else " was"} held back for review rather than published (conflicts with a figure already on the site, older editions, table readings). They are listed with the night\'s receipts.')
    if (data.get('pdf_reader') or {}).get('status') in ('missing','error'):
        watch.append('- Approved PDFs were not read: the nightly Python cannot load pypdf, so grid-operator reports stayed collection gaps. Reinstall pypdf in that environment.')
    if watch:
        lines += ['', '**Watch-outs**'] + watch
    if data.get('dashboard',{}).get('status') == 'unavailable':
        lines.append('- The private dashboard could not be started; Eli should check the viewer service.')
    low = data.get('published_observations') or {}
    if any(low.get('by_grade',{}).get(g,0) for g in ('C','D')):
        lines.append('- Some newly recorded numbers use news/social evidence; review their source grades in the full report.')
    if data['publication'].get('unpushed_commits') and not (data['publication'].get('final_push') or {}).get('pushed'):
        lines.append('- Some changes have not been confirmed pushed to the site.')
    lines += ['', '**Your next step**']
    if data['pending']:
        lines.append('- Review '+', '.join(f"{p['count']} {p['label'][:-1] if p['count']==1 else p['label']}" for p in data['pending'])+'. These are the total waiting inbox, not all new tonight.')
    else:
        lines.append('- No review items were reported in this night’s inbox snapshot.' if data['outcome']!='not_recorded' else '- Check the dashboard for the missing run.')
    if data['links']['review']:
        lines += ['', '[Review this night]('+data['links']['review']+') · [Latest on the site]('+LATEST+')']
    else:
        lines += ['', '[Latest on the site]('+LATEST+') · Private dashboard link is not configured.']
    return '\n'.join(lines)
