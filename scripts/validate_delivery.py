"""Integrity and attribution checks for reviewed delivery snapshots."""
import json
import re
from datetime import datetime,timezone
from pathlib import Path
from validate import require,text,timestamp
ROOT=Path(__file__).resolve().parents[1]
STAGES={'operating','partly-operating','commissioning','construction','permitting',
        'announced','site-selected','equipment-move-in','production-ramp','pilot','delayed'}

def validate_delivery(d,ledger):
    require(set(d)=={'version','reviewed_at','projects','context_metrics','assessment','gaps'},'Unexpected delivery shape')
    require(d['version']==1,'Unsupported delivery version');reviewed=timestamp(d['reviewed_at'])
    sources={s['id']:s for s in ledger['sources']};obs={o['id']:o for o in ledger['observations']};metrics={m['id']:m for m in ledger['metrics']}
    require(set(d['context_metrics'])<=metrics.keys(),'Unknown delivery context metric')
    ids=set()
    parents={p['id']:p.get('parent_project') for p in d['projects']}
    for child in parents:
        seen=set();cursor=child
        while cursor is not None:
            require(cursor not in seen,'Cyclic project phases');seen.add(cursor)
            cursor=parents.get(cursor)
    for p in d['projects']:
        required={'id','name','layer','owner','location','category','stage','ai_relationship','observations','horizon','grid','next_evidence','milestones'}
        require(required<=p.keys() and p.keys()<=required|{'primary_user','measures','company_ids','parent_project'},'Unexpected project fields')
        if 'company_ids' in p:
            require(isinstance(p['company_ids'],list) and len(p['company_ids'])==len(set(p['company_ids'])),'Invalid project company links')
            for cid in p['company_ids']:require(re.fullmatch('[a-z0-9-]+',cid),'Invalid company ID')
        if p.get('parent_project'):require(p['parent_project']!=p['id'] and any(v['id']==p['parent_project'] for v in d['projects']),'Invalid parent project')
        require(re.fullmatch('[a-z0-9-]+',p['id']) and p['id'] not in ids,'Invalid or duplicate project ID');ids.add(p['id'])
        require(p['layer'] in {'energy','chips','infrastructure','models','applications'} and p['stage'] in STAGES,'Invalid delivery stage/layer')
        if 'primary_user' in p:text(p['primary_user'],600)
        for k in ['name','owner','location','category','ai_relationship','horizon','grid','next_evidence']:text(p[k],600)
        require(p['milestones'],'Project needs sourced milestone evidence')
        dates=[]
        for m in p['milestones']:
            require(set(m)=={'date','summary','source'} and m['source'] in sources,'Missing milestone source')
            if m['date'] is not None:
                dt=datetime.strptime(m['date'],'%Y-%m-%d').date();require(dt<=reviewed.date(),'Future milestone evidence')
            require(m['date']==sources[m['source']]['published'],'Milestone must preserve source publication date')
            require(p['layer'] in sources[m['source']]['layers'],'Milestone source layer mismatch');text(m['summary'],600)
            if m['date'] is not None:dates.append(m['date'])
        require(dates==sorted(dates),'Milestones out of order')
        for id in p['observations']:
            require(id in obs and not obs[id].get('superseded_by'),'Missing or superseded project observation')
            require(metrics[obs[id]['metric']]['layer']==p['layer'],'Project capacity layer mismatch')
        if p['stage']=='operating' and p['observations']:
            require(all(obs[id]['status'] in {'observation','estimate'} for id in p['observations']),'Operating capacity cannot be supported by plans alone')
        if 'measures' in p:
            require(isinstance(p['measures'],list),'Project measures must be a list')
            for id in p['measures']:
                require(id in obs and not obs[id].get('superseded_by'),'Missing or superseded project measure')
                metric=metrics[obs[id]['metric']]
                require(metric.get('project')==p['id'],'Project measure belongs to another site')
                require('measurement_type' in metric and 'company' in metric,'Unscoped project measure')
    text(d['assessment'],1000)
    for gap in d['gaps']:text(gap,600)
    return True

def validate_files():
    read=lambda p:json.loads((ROOT/p).read_text(encoding='utf-8'))
    d=read('site/data/delivery.json');require(d==read('research/delivery.json'),'Reviewed delivery metadata changed')
    return validate_delivery(d,read('site/data/ledger.json'))

if __name__=='__main__':
    validate_files();print('Delivery tracker validation passed')
