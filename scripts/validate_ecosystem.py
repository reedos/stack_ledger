"""Validate reviewed company mappings and industry evidence before building."""
import json
import math
from pathlib import Path
from validate import require, text, timestamp, LAYERS

ROOT=Path(__file__).resolve().parents[1]

def validate_ecosystem(e,ledger):
    require(set(e)=={'version','reviewed_at','companies','capacity_metrics','supply_chain','projects','jobs','employment','interpretation','gaps'},'Unexpected ecosystem shape')
    require(e['version']==1,'Unsupported ecosystem version');timestamp(e['reviewed_at'])
    sources={s['id'] for s in ledger['sources']};metrics={m['id']:m for m in ledger['metrics']}
    ids=set()
    for c in e['companies']:
        require(set(c)=={'id','name','layers','role','revenue_metric','revenue_kind','source'},'Unexpected company shape')
        require(c['id'] not in ids,'Duplicate company ID');ids.add(c['id'])
        for k in ['id','name','role']:text(c[k])
        require(c['layers'] and set(c['layers'])<=set(LAYERS),'Invalid company layers')
        require(c['source'] in sources,'Unknown company source')
        require(c['revenue_kind'] in {'annual','run-rate'},'Invalid revenue basis')
        require(c['revenue_metric'] in metrics,'Missing revenue metric')
        require(c['source'] in metrics[c['revenue_metric']]['source_ids'],'Company revenue source mismatch')
        require(any(o['metric']==c['revenue_metric'] and o['status']=='observation' and not o.get('superseded_by') for o in ledger['observations']),'Missing reported revenue observation')
    require(set(e['capacity_metrics'])<=metrics.keys(),'Unknown capacity metric')
    for step in e['supply_chain']:
        require(set(step)=={'title','role','companies','note'},'Unexpected supply chain shape')
        require(set(step['companies'])<=ids,'Unknown supply chain company')
        for k in ['title','role','note']:text(step[k])
    for p in e['projects']:
        require(set(p)=={'company','title','stage','period','detail','source'},'Unexpected project shape')
        require(p['company'] in ids and p['source'] in sources,'Unknown project mapping')
        require(p['stage'] in {'Operating','Construction milestone','Groundbreaking announced'},'Unreviewed project stage')
        for k in ['title','stage','period','detail']:text(p[k])
    for j in e['jobs']:
        require(set(j)=={'title','value','precision','status','period','scope','source'},'Unexpected jobs shape')
        require(type(j['value']) in (int,float) and math.isfinite(j['value']) and j['value']>=0,'Invalid jobs value')
        require(j['precision'] in {'eq','gt','approx'},'Invalid jobs precision')
        require(j['source'] in sources,'Unknown jobs source')
        for k in ['title','status','period','scope']:text(j[k])
    employment=e['employment']
    require(set(employment)=={'period','geography','basis','source','series','note'},'Unexpected employment shape')
    require(employment['source'] in sources,'Unknown employment source')
    for s in employment['series']:
        require(set(s)=={'name','value'} and type(s['value']) is int,'Invalid employment series');text(s['name'])
    for k in ['period','geography','basis','note']:text(employment[k])
    text(e['interpretation'],1000)
    for gap in e['gaps']:text(gap)
    return True

def validate_files():
    read=lambda p:json.loads((ROOT/p).read_text(encoding='utf-8'))
    e=read('site/data/ecosystem.json')
    require(e==read('research/ecosystem.json'),'Reviewed ecosystem changed')
    return validate_ecosystem(e,read('site/data/ledger.json'))

if __name__=='__main__':
    validate_files()
    print('Company and industry validation passed')
