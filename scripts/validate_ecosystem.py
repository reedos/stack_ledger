"""Validate reviewed company mappings and industry evidence before building."""
import json
import math
import re
from pathlib import Path
from validate import require, text, timestamp, LAYERS

ROOT=Path(__file__).resolve().parents[1]

def validate_ecosystem(e,ledger):
    require(set(e)=={'version','reviewed_at','companies','capacity_metrics','supply_chain','projects','jobs','employment','interpretation','gaps'},'Unexpected ecosystem shape')
    require(e['version']==1,'Unsupported ecosystem version');timestamp(e['reviewed_at'])
    sources={s['id'] for s in ledger['sources']};metrics={m['id']:m for m in ledger['metrics']}
    ids=set()
    for c in e['companies']:
        required={'id','name','layers','role','revenue_metric','revenue_kind','source'}
        require(required<=c.keys() and c.keys()<=required|{'role_sources','ir_url','filings_jurisdiction','blog_urls','official_lang','region_book','revenue_chart_metric','map_offices','output_metric'},'Unexpected company shape')
        if 'map_offices' in c:
            from validate_explorers import validate_location
            require('models' in c['layers'] and isinstance(c['map_offices'],list) and c['map_offices'],'Invalid model developer offices')
            office_ids=set();source_rows={s['id']:s for s in ledger['sources']}
            for office in c['map_offices']:
                require(set(office)=={'id','kind','name','source','note','location'},'Unexpected office fields')
                require(re.fullmatch('[a-z0-9-]+',office['id']) and office['id'] not in office_ids,'Duplicate office ID');office_ids.add(office['id'])
                require(office['kind'] in {'headquarters','co-headquarters','office','registered-office'},'Invalid office kind')
                require(office['source'] in source_rows and 'models' in source_rows[office['source']]['layers'],'Missing office evidence')
                text(office['name'],200);text(office['note'],600)
                validate_location(office['location'],source_rows,'models',timestamp(e['reviewed_at']))
        require(re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', c['id']) is not None, 'Unsafe company route')
        if c.get('output_metric'):
            # A company's headline output (accelerators shipped, wafers, HBM) must be a metric attributed to that company.
            require(c['output_metric'] in metrics and metrics[c['output_metric']].get('company') == c['id'], 'Company output metric ownership mismatch')
        if c.get('revenue_chart_metric'):
            require(c['revenue_chart_metric'] in metrics and metrics[c['revenue_chart_metric']].get('company') == c['id'], 'Company chart ownership mismatch')
        require(c['id'] not in ids,'Duplicate company ID');ids.add(c['id'])
        for k in ['id','name','role']:text(c[k])
        require(c['layers'] and set(c['layers'])<=set(LAYERS),'Invalid company layers')
        require(c['source'] in sources,'Unknown company source')
        if 'role_sources' in c:
            require(isinstance(c['role_sources'],list) and c['role_sources'] and set(c['role_sources'])<=sources,'Unknown company role source')
        from source_policy import REGIONS
        from urllib.parse import urlparse
        require(c['region_book'] in REGIONS, 'Invalid company region')
        for key in ['filings_jurisdiction','official_lang']: text(c[key])
        require(isinstance(c['blog_urls'],list) and len(c['blog_urls'])<=5, 'Too many blog URLs')
        for url in ([c['ir_url']] if c['ir_url'] else [])+c['blog_urls']:
            u=urlparse(url); require(u.scheme=='https' and u.hostname and '*' not in url and not u.username and not u.password, 'Invalid company source URL')
        require(c['revenue_kind'] in {'annual','run-rate','unavailable'},'Invalid revenue basis')
        if c['revenue_kind']=='unavailable':
            require(c['revenue_metric'] is None,'Unverified revenue must have no numeric metric')
            continue
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
