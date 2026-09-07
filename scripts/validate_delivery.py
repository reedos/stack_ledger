"""Integrity and attribution checks for reviewed delivery snapshots."""
import json
import re
from datetime import datetime,timezone
from pathlib import Path
from validate import require,text,timestamp
ROOT=Path(__file__).resolve().parents[1]
STAGES={'operating','partly-operating','commissioning','construction','permitting'}

def validate_delivery(d,ledger):
    require(set(d)=={'version','reviewed_at','projects','context_metrics','assessment','gaps'},'Unexpected delivery shape')
    require(d['version']==1,'Unsupported delivery version');reviewed=timestamp(d['reviewed_at'])
    sources={s['id']:s for s in ledger['sources']};obs={o['id']:o for o in ledger['observations']};metrics={m['id']:m for m in ledger['metrics']}
    require(set(d['context_metrics'])<=metrics.keys(),'Unknown delivery context metric')
    ids=set()
    for p in d['projects']:
        require(set(p)=={'id','name','layer','owner','location','category','stage','ai_relationship','observations','horizon','grid','next_evidence','milestones'},'Unexpected project fields')
        require(re.fullmatch('[a-z0-9-]+',p['id']) and p['id'] not in ids,'Invalid or duplicate project ID');ids.add(p['id'])
        require(p['layer'] in {'energy','infrastructure'} and p['stage'] in STAGES,'Invalid delivery stage/layer')
        for k in ['name','owner','location','category','ai_relationship','horizon','grid','next_evidence']:text(p[k],600)
        require(p['milestones'],'Project needs sourced milestone evidence')
        dates=[]
        for m in p['milestones']:
            require(set(m)=={'date','summary','source'} and m['source'] in sources,'Missing milestone source')
            dt=datetime.strptime(m['date'],'%Y-%m-%d').date();require(dt<=reviewed.date(),'Future milestone evidence')
            require(m['date']==sources[m['source']]['published'],'Milestone must preserve source publication date')
            require(p['layer'] in sources[m['source']]['layers'],'Milestone source layer mismatch');text(m['summary'],600);dates.append(m['date'])
        require(dates==sorted(dates),'Milestones out of order')
        for id in p['observations']:
            require(id in obs and not obs[id].get('superseded_by'),'Missing or superseded project observation')
            require(metrics[obs[id]['metric']]['layer']==p['layer'],'Project capacity layer mismatch')
        if p['stage']=='operating' and p['observations']:
            require(all(obs[id]['status']=='observation' for id in p['observations']),'Operating capacity cannot be supported by plans alone')
    text(d['assessment'],1000)
    for gap in d['gaps']:text(gap,600)
    return True

def validate_files():
    read=lambda p:json.loads((ROOT/p).read_text(encoding='utf-8'))
    d=read('site/data/delivery.json');require(d==read('research/delivery.json'),'Reviewed delivery metadata changed')
    return validate_delivery(d,read('site/data/ledger.json'))

if __name__=='__main__':
    validate_files();print('Delivery tracker validation passed')
