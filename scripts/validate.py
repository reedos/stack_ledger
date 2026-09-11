"""Fail-closed public ledger validation, using only the Python standard library."""
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
STATUSES = {'observation','estimate','forecast','government-target','company-commitment'}
PRECISIONS = {'eq','approx','gt','lt','range'}
LAYERS = ['energy','chips','infrastructure','models','applications']
# Owner decision, September 10, 2026: the grade is a coarse solidity scale derived from each
# source's own REVIEWED provenance (source_policy.PROVENANCE_GRADE), not from its crawl rank.
# A the authoritative record (official statistics, a regulator, or a company's regulated filing);
# B a primary publisher speaking about its own work (a company's own channel, or a research body's
# own dataset); C a third party characterising someone else's numbers (analyst, trade or news);
# D unverified or social. The site displays the provenance itself, not the bare letter.
GRADES = {'A','B','C','D'}
REPORT_KINDS = {'News report','Social post'}
# Reviewed per-metric period bases. Without one, a metric holds one value per year and a second
# value for the same year is a conflict. With one, readings are keyed on the canonical period.
PERIOD_FORMATS = {'month': r'20[0-9]{2}-(0[1-9]|1[0-2])', 'quarter': r'20[0-9]{2}-Q[1-4]', 'snapshot': r'20[0-9]{2}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])'}

def require(condition, message):
    if not condition: raise ValueError(message)

def text(value, maximum=500):
    require(isinstance(value,str) and 0<len(value)<=maximum,'Invalid text length/type')
    require(not re.search(r'[<>\x00-\x08\x0b\x0c\x0e-\x1f]',value),'Markup/control characters are not allowed')
    require(not re.search(r'(?i)(gh[pousr]_[A-Za-z0-9]{15,}|sk-[a-z0-9]{20,}|[a-z]:\\users\\|bearer\s+\S+)',value),'Potential secret or local path')

def timestamp(value):
    require(isinstance(value,str),'Timestamp must be a string')
    dt=datetime.fromisoformat(value.replace('Z','+00:00'))
    require(dt.tzinfo is not None,'Timestamp must include timezone')
    require(dt<=datetime.now(timezone.utc),'Future retrieval/run timestamp')
    return dt

def source_valid(source, approved):
    required={'id','publisher','title','url','published','layers','license','provenance'}
    require(required <= source.keys() and source.keys() <= required|{'parent_source','index'},'Unknown/missing source fields')
    # Reviewed per source since 2026-09-10, never inferred: it is what every published number is
    # labelled with, so a source that cannot say who published it cannot be published from.
    from source_policy import PROVENANCE
    require(source['provenance'] in PROVENANCE,'Unknown source provenance')
    for k in ['id','publisher','title','url','license']:text(source[k],2000 if k=='url' else 250)
    u=urlparse(source['url'])
    require(u.scheme=='https' and u.hostname and not u.username and not u.password and u.port in (None,443),'Source must be public HTTPS')
    require(set(source['layers']) <= set(LAYERS),'Invalid source layers')
    if source['published'] is not None:
        require(re.fullmatch(r'\d{4}-\d{2}-\d{2}',source['published']),'Invalid publication date')
        require(datetime.fromisoformat(source['published']).date()<=datetime.now(timezone.utc).date(),'Future publication date')
    if source['id'] in approved:
        require(source==approved[source['id']],'Reviewed source changed')
    else:
        parent=approved.get(source.get('parent_source'))
        require(parent is not None,'Unapproved source ancestry')
        require(u.hostname==urlparse(parent['url']).hostname,'Discovered source host not approved')
        require(source['layers']==parent['layers'] and source['publisher']==parent['publisher'],'Source attribution changed')

def observation_valid(o,metrics,sources):
    required={'id','metric','year','period','value','upper','status','source','precision','retrieved_at','method','note'}
    optional={'document_sha256','evidence_sha256','correction_of','superseded_by','correction_reason','grade'}
    require(isinstance(o,dict) and required<=o.keys() and o.keys()<=required|optional,'Unknown/missing observation fields')
    require(re.fullmatch(r'[a-z0-9][a-z0-9-]{0,99}',o['id']) is not None,'Invalid observation ID')
    require(o['metric'] in metrics and o['source'] in sources,'Unknown metric/source')
    m=metrics[o['metric']]
    s=sources[o['source']]
    require(s.get('parent_source',s['id']) in m['source_ids'],'Metric/source mapping not approved')
    require(type(o['year']) is int and 2000<=o['year']<=2150,'Invalid year')
    require(o['year']>=m.get('series_start_year',2000),'Year precedes reviewed series start; backfill requires review')
    require(o['status'] in STATUSES and o['precision'] in PRECISIONS,'Invalid classification')
    if 'allowed_statuses' in m:
        require(o['status'] in m['allowed_statuses'],'Status contradicts reviewed measurement basis')
    require(o['method'] in {'curated','automated'},'Invalid research method')
    for k in ['value','upper']:
        if o[k] is None and k=='upper':continue
        require(type(o[k]) in (int,float) and math.isfinite(o[k]),'Invalid numeric value')
        require(m['min']<=o[k]<=m['max'],'Value outside metric bounds')
    require((o['upper'] is not None)==(o['precision']=='range'),'Range bounds/precision mismatch')
    if o['upper'] is not None:require(o['upper']>=o['value'],'Inverted interval')
    dt=timestamp(o['retrieved_at'])
    basis=m.get('period_basis')
    if basis is not None:
        require(basis in PERIOD_FORMATS,'Unknown period basis')
        require(re.fullmatch(PERIOD_FORMATS[basis],o['period']) is not None,f'{basis.title()} period format required')
        require(int(o['period'][:4])==o['year'],f'{basis.title()} period/year mismatch')
        if o['status'] in {'estimate','observation'}:
            if basis=='month':require(o['period']<=dt.strftime('%Y-%m'),'Historical month is in the future')
            if basis=='snapshot':require(o['period']<=dt.strftime('%Y-%m-%d'),'Historical snapshot date is in the future')
            if basis=='quarter':require(o['period']<=f'{dt.year}-Q{(dt.month-1)//3+1}','Historical quarter is in the future')
    if o['status'] in {'estimate','observation'}:require(o['year']<=dt.year,'Historical result cannot be in the future')
    text(o['period'],80)
    if o['note']:text(o['note'],300)
    if o['method']=='automated':
        for k in ['document_sha256','evidence_sha256']:require(re.fullmatch(r'[0-9a-f]{64}',o.get(k,'')) is not None,'Missing evidence hash')
        # Deliverable 1: a grade C or D item never enters a numeric series -- an automated
        # numeric observation must already be official-statistics or company-statement grade.
        require(o.get('grade') in {'A','B'},'Automated observation needs grade A or B; C/D evidence stays a report, never a numeric record')
    elif 'grade' in o:
        require(o['grade'] in GRADES,'Invalid evidence grade')
    if 'correction_of' in o: text(o.get('correction_reason',''),500)

REPORT_FIELDS = {'outlet','reported_on','about','quote','confirmation'}
MATCHING_FIELDS = {'metric_id','period','value','precision','upper'}
RETRACTION_FIELDS = {'retracted','retraction_reason','retracted_at','retracted_by'}

def event_valid(event,sources):
    required={'id','layer','date','title','summary','source','kind','grade'}
    optional={'method','retrieved_at','document_sha256','evidence_sha256'}|REPORT_FIELDS|MATCHING_FIELDS|RETRACTION_FIELDS
    correction={'correction_of','correction_reason','corrected_at'}
    require(required<=event.keys() and event.keys()<=required|optional|correction,'Unexpected event shape')
    require(event['grade'] in GRADES,'Invalid evidence grade')
    require(event['source'] in sources and event['layer'] in LAYERS,'Invalid event mapping')
    for k in ['id','title','summary','kind']:text(event[k],600 if k=='summary' else 140)
    if event['date']:
        dt=datetime.strptime(event['date'],'%Y-%m-%d')
        require(dt.date()<=datetime.now(timezone.utc).date(),'Future event publication date')
    if event.get('method')=='automated':
        require(not correction & event.keys(),'Automated notes cannot issue corrections')
        require(event['layer'] in sources[event['source']]['layers'],'Invalid event/source layer')
        require(event['date']==sources[event['source']]['published'],'Event must preserve source publication date')
        require(event['kind'] in {'Reported milestone','Research finding','Company announcement','Forecast update','Government target','Constraint update'}|REPORT_KINDS,'Invalid note classification')
        require(re.fullmatch(r'note-[0-9a-f]{20}',event['id']) is not None,'Invalid automated note ID')
        for k in ['document_sha256','evidence_sha256']:require(re.fullmatch(r'[0-9a-f]{64}',event.get(k,'')) is not None,'Missing note evidence hash')
        timestamp(event['retrieved_at'])
    elif correction & event.keys():
        require(correction<=event.keys() and event.get('method')=='curated','Incomplete curated correction')
        text(event['correction_of'],140);text(event['correction_reason'],500)
        require(timestamp(event['corrected_at'])>=timestamp(event['retrieved_at']),'Correction precedes collection')
        for k in ['document_sha256','evidence_sha256']:
            require(re.fullmatch(r'[0-9a-f]{64}',event.get(k,'')) is not None,'Missing correction evidence hash')
        require(event['date']==sources[event['source']]['published'],'Correction must preserve source publication date')
    else:require(not (optional & event.keys()),'Unexpected curated note metadata')
    # Deliverable 2: grade C/D evidence from a registered news feed or official social account
    # publishes as a report -- never blended into a metric/note event's normal shape, never
    # rendered as a numeric series or homepage headline. Deliverable 5: a report can carry a
    # human-only retraction; nothing else may.
    if event['kind'] in REPORT_KINDS:
        require(event['grade'] in {'C','D'},'A report event needs grade C or D')
        require(REPORT_FIELDS<=event.keys(),'Report event missing outlet/reported_on/about/quote/confirmation')
        text(event['outlet'],250)
        if event['reported_on'] is not None:
            require(re.fullmatch(r'\d{4}-\d{2}-\d{2}',event['reported_on']) is not None,'Invalid reported_on date')
        require(isinstance(event['about'],list) and len(event['about'])<=10 and all(isinstance(x,str) and 0<len(x)<=140 for x in event['about']),'Invalid about list')
        text(event['quote'],1600)
        require(event['confirmation'] in {'unconfirmed','expired'} or re.fullmatch(r'(confirmed_by|contradicted_by):[a-z0-9-]{1,100}',event['confirmation']) is not None,'Invalid confirmation state')
        present=MATCHING_FIELDS & event.keys()
        if present:
            require(present==MATCHING_FIELDS,'Incomplete confirmation-matching fields')
            require(isinstance(event['metric_id'],str) and event['metric_id'],'Invalid matching metric_id')
            text(event['period'],80)
            require(type(event['value']) in (int,float) and math.isfinite(event['value']),'Invalid matching value')
            require(event['precision'] in PRECISIONS,'Invalid matching precision')
            require((event['upper'] is not None)==(event['precision']=='range'),'Range bounds/precision mismatch')
            if event['upper'] is not None:require(event['upper']>=event['value'],'Inverted matching interval')
        if 'retracted' in event:
            require(event['retracted'] is True and RETRACTION_FIELDS<=event.keys(),'Invalid retraction flag')
            text(event['retraction_reason'],500);timestamp(event['retracted_at']);text(event['retracted_by'],120)
        else:
            require(not (RETRACTION_FIELDS-{'retracted'}) & event.keys(),'Retraction metadata without retracted flag')
    else:
        require(not (REPORT_FIELDS|MATCHING_FIELDS|RETRACTION_FIELDS) & event.keys(),'Only a report event carries reports-lane or retraction fields')

def current_events(events):
    """Original records remain in the ledger; ordinary views use replacements."""
    replaced={e['correction_of'] for e in events if 'correction_of' in e}
    return [e for e in events if e['id'] not in replaced]

def validate_event_corrections(events):
    by_id={e['id']:e for e in events};replaced=set()
    for event in events:
        if 'correction_of' not in event:continue
        old=by_id.get(event['correction_of'])
        require(old is not None and old['id']!=event['id'],'Missing/self correction ancestor')
        require(old['id'] not in replaced,'Conflicting note replacements');replaced.add(old['id'])
        require(all(event[k]==old[k] for k in ['source','layer','date']),'Correction changes source, layer or publication date')
        if old.get('corrected_at'):
            require(timestamp(event['corrected_at'])>=timestamp(old['corrected_at']),'Correction chronology reversed')
        seen={event['id']};ancestor=old
        while ancestor:
            require(ancestor['id'] not in seen,'Cyclic note correction');seen.add(ancestor['id'])
            ancestor=by_id.get(ancestor.get('correction_of'))

def validate_importers(root=ROOT):
    p = json.loads((root/'research/importers.json').read_text(encoding='utf-8'))
    required = {'version', 'reviewed_at', 'importers'}
    require(required <= set(p) <= required | {'research_ignore_gpu_busy'} and p['version'] == 1, 'Unexpected importers shape')
    timestamp(p['reviewed_at'])
    if 'research_ignore_gpu_busy' in p: require(type(p['research_ignore_gpu_busy']) is bool, 'Invalid research_ignore_gpu_busy flag')
    require(isinstance(p['importers'], list) and p['importers'], 'No importers configured')
    ids = set()
    for imp in p['importers']:
        fields = {'id', 'command', 'cadence', 'timeout_seconds'}
        require(fields <= set(imp) <= fields | {'weekday'}, 'Unexpected importer fields')
        text(imp['id'], 60)
        require(imp['id'] not in ids, 'Duplicate importer id'); ids.add(imp['id'])
        require(isinstance(imp['command'], list) and imp['command'] and all(isinstance(x, str) and x for x in imp['command']), 'Invalid importer command')
        script = (root/imp['command'][0]).resolve()
        require(script.is_file() and script.suffix == '.py' and script.parent == (root/'scripts').resolve(), 'Importer command must start with a known scripts/ path')
        require(imp['cadence'] in {'daily', 'weekly'}, 'Invalid importer cadence')
        if imp['cadence'] == 'weekly': require(type(imp.get('weekday')) is int and 0 <= imp['weekday'] <= 6, 'Weekly importer needs weekday 0-6')
        else: require('weekday' not in imp, 'Daily importer must not set weekday')
        require(type(imp['timeout_seconds']) is int and 30 <= imp['timeout_seconds'] <= 3600, 'Importer timeout out of bounds')
    return p


def validate(data):
    require(set(data)=={'version','seed_date','layers','metrics','sources','observations','events','targets','runs','runtime'},'Unexpected ledger shape')
    require(data['version']==1,'Unsupported ledger version')
    catalog=json.loads((ROOT/'research/catalog.json').read_text(encoding='utf-8'))
    registry=json.loads((ROOT/'research/sources.json').read_text(encoding='utf-8'))
    require([l['id'] for l in data['layers']]==LAYERS,'Layer order changed')
    for key in ['layers','metrics','targets']: require(data[key]==catalog[key],f'Reviewed {key} changed')
    approved={s['id']:s for s in registry['sources']}
    sources={s['id']:s for s in data['sources']}
    require(len(sources)==len(data['sources']),'Duplicate source IDs')
    require(set(approved)<=set(sources),'Reviewed source removed')
    for s in data['sources']:source_valid(s,approved)
    metrics={m['id']:m for m in data['metrics']}
    require(len(metrics)==len(data['metrics']),'Duplicate metric IDs')
    for m in metrics.values():
        if 'chart_companion_metric' in m:
            companion=metrics.get(m['chart_companion_metric'])
            require(companion is not None and companion['id']!=m['id'],'Invalid chart companion')
            require(all(companion[k]==m[k] for k in ['unit','geography','layer']),'Chart companion units/geography/layer differ')
            if companion.get('measurement_type') == 'annual_revenue_forecast':
                require(companion.get('company') is not None, 'Revenue outlook needs company attribution')
                for label in ['chart_comparison_label', 'chart_comparison_legend']: text(m.get(label), 180)
            text(m.get('chart_comparison_title'),250)
            text(m.get('chart_comparison_note'),1000)
        if 'chart_overlay_metric' in m:
            overlay=metrics.get(m['chart_overlay_metric'])
            require(overlay is not None and overlay['id'] not in {m['id'], m.get('chart_companion_metric')},'Invalid chart overlay')
            require(all(overlay[k]==m[k] for k in ['unit','geography','layer']),'Chart overlay units/geography/layer differ')
            text(m.get('chart_overlay_legend'),180)
            if 'chart_companion_metric' not in m:
                text(m.get('chart_comparison_note'),1000)
                text(m.get('chart_comparison_title'),250)
        if m.get('chart_type') is not None:
            require(m['chart_type'] in {'bar','line'},'Invalid chart type')
        for field in ['series_start_year','chart_default_start','chart_default_end']:
            require(type(m.get(field)) is int and 2000<=m[field]<=2150,'Invalid chart history metadata')
        require(m['series_start_year']<=m['chart_default_start']<=m['chart_default_end'],'Inverted chart window')
        require(type(m.get('definition_stable')) is bool,'Missing definition stability')
        text(m.get('pre_period_note'),1000)
        if not m['definition_stable']:
            require(type(m.get('definition_break_year')) is int and m['series_start_year']<=m['definition_break_year']<=m['chart_default_end'],'Missing methodology break marker')
        # Deliverable 1 (2026-09-10): a reviewed override of research.refresh_expected()'s
        # derivation -- optional, so most metrics say nothing and let the derivation decide;
        # present, it must be an explicit bool, never a truthy/falsy stand-in.
        if 'refresh_expected' in m:
            require(type(m['refresh_expected']) is bool,'Invalid refresh_expected flag')
    ids=set(); periods=set()
    from source_policy import collection_for, grade_for
    # Company records let an evidence-only citation be graded by its publisher rather than by a
    # collection rank it does not have; a missing ecosystem file simply grades those independent.
    try:companies=json.loads((ROOT/'research/ecosystem.json').read_text(encoding='utf-8'))['companies']
    except (OSError,ValueError,KeyError):companies=[]
    for o in data['observations']:
        observation_valid(o,metrics,sources)
        require(o['id'] not in ids,'Duplicate observation ID');ids.add(o['id'])
        key=(o['metric'],o['year'],o['period'],o['status'])
        if not o.get('superseded_by'):
            require(key not in periods,'Duplicate metric period/status');periods.add(key)
        if o.get('method')=='automated':
            require(o['grade']==grade_for(collection_for(registry,sources[o['source']]),sources[o['source']],companies),'Observation grade does not match deterministic derivation from its source')
    by_id={o['id']:o for o in data['observations']}
    for o in data['observations']:
        if 'superseded_by' in o:
            replacement=by_id.get(o['superseded_by'])
            require(replacement is not None and replacement.get('correction_of')==o['id'],'Broken correction link')
        if 'correction_of' in o:
            old=by_id.get(o['correction_of'])
            require(old is not None and old.get('superseded_by')==o['id'],'Broken correction ancestry')
    for event in data['events']:
        event_valid(event,sources)
        require(event['grade']==grade_for(collection_for(registry,sources[event['source']]),sources[event['source']],companies),'Event grade does not match deterministic derivation from its source')
    require(len({e['id'] for e in data['events']})==len(data['events']),'Duplicate event IDs')
    validate_event_corrections(data['events'])
    run_ids=set()
    for run in data['runs']:
        require(set(run)=={'id','started_at','finished_at','status','documents_fetched','documents_reviewed','accepted','quarantined','source_failures','model_calls','coverage_layers'},'Unexpected run shape')
        require(run['id'] not in run_ids,'Duplicate run ID');run_ids.add(run['id'])
        require(timestamp(run['started_at'])<=timestamp(run['finished_at']),'Invalid run duration')
        require(run['status'] in {'success','partial','failed'},'Invalid run status')
        for k in ['documents_fetched','documents_reviewed','accepted','quarantined','model_calls']:require(type(run[k]) is int and run[k]>=0,'Invalid run count')
        require(run['documents_reviewed']<=run['documents_fetched'],'Reviewed more than fetched')
        require(set(run['coverage_layers'])<=set(LAYERS),'Invalid run coverage')
        if run['status']=='success':require(run['documents_reviewed']>0 and not run['source_failures'] and set(run['coverage_layers'])==set(LAYERS),'Incomplete run cannot be successful')
        for f in run['source_failures']:
            require(set(f)=={'source','reason'},'Unexpected failure shape');text(f['source'],200);text(f['reason'],200)
    r=data['runtime']
    required_runtime={'display_model','model','engine','hardware','timezone','schedule','last_attempt','last_success','status'}
    require(required_runtime<=r.keys() and r.keys()<=required_runtime|{'latest_session'},'Unexpected runtime shape')
    if 'latest_session' in r:
        from session_receipt import validate_receipt
        validate_receipt(r['latest_session'])
    config=json.loads((ROOT/'research/runtime.json').read_text(encoding='utf-8'))
    for k in ['display_model','model','hardware','timezone']:require(r[k]==config[k],'Runtime identity changed')
    # One run per batch: the four days to 2026-09-10 published 623. Only this window is
    # downloaded by every reader; research.trim_published_runs keeps it inside the limit and
    # .local/runs keeps every receipt.
    limit=config.get('published_run_limit')
    if limit is not None:require(len(data['runs'])<=limit,'Published run history exceeds the reviewed window')
    if data['runs']:
        last=data['runs'][-1]
        require(r['last_attempt']==last['finished_at'] and r['status']==last['status'],'Runtime does not match latest run')
        successes=[x for x in data['runs'] if x['status']=='success']
        require(r['last_success']==(successes[-1]['finished_at'] if successes else None),'False successful timestamp')
    else:require(r['last_attempt'] is None and r['last_success'] is None and r['status']=='awaiting-first-run','False run attribution')
    return True

if __name__=='__main__':
    from discovery import policy as discovery_policy, agenda as discovery_agenda
    discovery_policy(ROOT)
    discovery_agenda(ROOT)
    data=json.loads((ROOT/'site/data/ledger.json').read_text(encoding='utf-8'))
    validate(data)
    validate_importers(ROOT)
    from editorial import read, validate_config
    validate_config(read(ROOT/'research/homepage.json'),data,read(ROOT/'research/editorial-policy.json'))
    from visual_review import policy as visual_policy
    visual_policy(ROOT)
    print('Ledger validation passed')
