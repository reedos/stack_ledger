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
    required={'id','publisher','title','url','published','layers','license'}
    require(required <= source.keys() and source.keys() <= required|{'parent_source','index'},'Unknown/missing source fields')
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
    optional={'document_sha256','evidence_sha256','correction_of','superseded_by','correction_reason'}
    require(isinstance(o,dict) and required<=o.keys() and o.keys()<=required|optional,'Unknown/missing observation fields')
    require(re.fullmatch(r'[a-z0-9][a-z0-9-]{0,99}',o['id']) is not None,'Invalid observation ID')
    require(o['metric'] in metrics and o['source'] in sources,'Unknown metric/source')
    m=metrics[o['metric']]
    s=sources[o['source']]
    require(s.get('parent_source',s['id']) in m['source_ids'],'Metric/source mapping not approved')
    require(type(o['year']) is int and 2000<=o['year']<=2150,'Invalid year')
    require(o['status'] in STATUSES and o['precision'] in PRECISIONS,'Invalid classification')
    require(o['method'] in {'curated','automated'},'Invalid research method')
    for k in ['value','upper']:
        if o[k] is None and k=='upper':continue
        require(type(o[k]) in (int,float) and math.isfinite(o[k]),'Invalid numeric value')
        require(m['min']<=o[k]<=m['max'],'Value outside metric bounds')
    require((o['upper'] is not None)==(o['precision']=='range'),'Range bounds/precision mismatch')
    if o['upper'] is not None:require(o['upper']>=o['value'],'Inverted interval')
    dt=timestamp(o['retrieved_at'])
    if o['status'] in {'estimate','observation'}:require(o['year']<=dt.year,'Historical result cannot be in the future')
    text(o['period'],80)
    if o['note']:text(o['note'],300)
    if o['method']=='automated':
        for k in ['document_sha256','evidence_sha256']:require(re.fullmatch(r'[0-9a-f]{64}',o.get(k,'')) is not None,'Missing evidence hash')
    if 'correction_of' in o: text(o.get('correction_reason',''),500)

def event_valid(event,sources):
    required={'id','layer','date','title','summary','source','kind'}
    optional={'method','retrieved_at','document_sha256','evidence_sha256'}
    require(required<=event.keys() and event.keys()<=required|optional,'Unexpected event shape')
    require(event['source'] in sources and event['layer'] in LAYERS,'Invalid event mapping')
    for k in ['id','title','summary','kind']:text(event[k],600 if k=='summary' else 140)
    if event['date']:
        dt=datetime.strptime(event['date'],'%Y-%m-%d')
        require(dt.date()<=datetime.now(timezone.utc).date(),'Future event publication date')
    if event.get('method')=='automated':
        require(event['layer'] in sources[event['source']]['layers'],'Invalid event/source layer')
        require(event['date']==sources[event['source']]['published'],'Event must preserve source publication date')
        require(event['kind'] in {'Reported milestone','Research finding','Company announcement','Forecast update','Government target','Constraint update'},'Invalid note classification')
        require(re.fullmatch(r'note-[0-9a-f]{20}',event['id']) is not None,'Invalid automated note ID')
        for k in ['document_sha256','evidence_sha256']:require(re.fullmatch(r'[0-9a-f]{64}',event.get(k,'')) is not None,'Missing note evidence hash')
        timestamp(event['retrieved_at'])
    else:require(not (optional & event.keys()),'Unexpected curated note metadata')

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
    ids=set(); periods=set()
    for o in data['observations']:
        observation_valid(o,metrics,sources)
        require(o['id'] not in ids,'Duplicate observation ID');ids.add(o['id'])
        key=(o['metric'],o['year'],o['period'],o['status'])
        if not o.get('superseded_by'):
            require(key not in periods,'Duplicate metric period/status');periods.add(key)
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
    require(len({e['id'] for e in data['events']})==len(data['events']),'Duplicate event IDs')
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
    require(set(r)=={'display_model','model','engine','hardware','timezone','schedule','last_attempt','last_success','status'},'Unexpected runtime shape')
    config=json.loads((ROOT/'research/runtime.json').read_text(encoding='utf-8'))
    for k in ['display_model','model','hardware','timezone']:require(r[k]==config[k],'Runtime identity changed')
    if data['runs']:
        last=data['runs'][-1]
        require(r['last_attempt']==last['finished_at'] and r['status']==last['status'],'Runtime does not match latest run')
        successes=[x for x in data['runs'] if x['status']=='success']
        require(r['last_success']==(successes[-1]['finished_at'] if successes else None),'False successful timestamp')
    else:require(r['last_attempt'] is None and r['last_success'] is None and r['status']=='awaiting-first-run','False run attribution')
    return True

if __name__=='__main__':
    validate(json.loads((ROOT/'site/data/ledger.json').read_text(encoding='utf-8')))
    print('Ledger validation passed')
