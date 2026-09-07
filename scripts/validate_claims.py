"""Integrity checks for curated claims; unattended researchers cannot edit this snapshot."""
import json
import math
import re
from pathlib import Path
from validate import require, text, timestamp

ROOT = Path(__file__).resolve().parents[1]
TOPICS = {'Water','Power & bills','Clean energy','Jobs & economy','Taxes & communities','AI & work'}


def validate_claims(data, sources):
    require(set(data)=={'version','reviewed_at','reviewer','claims','highlights','article_audit'} and data['version']==1, 'Invalid claims snapshot')
    timestamp(data['reviewed_at']); text(data['reviewer'],200)
    ids=set()
    def identity(value):
        require(isinstance(value,str) and re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*',value) and value not in ids,'Invalid or duplicate claim ID')
        ids.add(value)
    def evidence(values):
        require(isinstance(values,list) and values and len(set(values))==len(values) and set(values)<=sources,'Unknown claims source')
    require(data['claims'] and data['highlights'] and data['article_audit'],'Empty claims review')
    for c in data['claims']:
        require(set(c)=={'id','topic','claim','verdict','scope','evidence','sources','future','gap'},'Invalid claim fields')
        identity(c['id']);require(c['topic'] in TOPICS,'Unknown claim topic');evidence(c['sources'])
        for key in ['claim','verdict','scope','evidence','future','gap']:text(c[key],1500)
    for h in data['highlights']:
        require(set(h)=={'id','title','unit','scope','note','source','points'},'Invalid benefit graphic')
        identity(h['id']);evidence([h['source']])
        for key in ['title','unit','scope','note']:text(h[key],1000)
        require(len(h['points'])>=2,'Graphic needs comparative evidence')
        periods=set()
        for p in h['points']:
            require(set(p)=={'period','value','status'},'Invalid benefit point')
            text(p['period'],100);require(p['period'] not in periods,'Duplicate benefit period');periods.add(p['period'])
            require(type(p['value']) in (int,float) and math.isfinite(p['value']) and p['value']>0,'Invalid benefit value')
            require(p['status'] in {'observation','estimate','forecast'},'Invalid benefit status')
    for a in data['article_audit']:
        require(set(a)=={'claim','status','finding','sources'},'Invalid article check')
        evidence(a['sources'])
        for key in ['claim','status','finding']:text(a[key],1000)
    return True


def validate_files():
    read=lambda p:json.loads((ROOT/p).read_text(encoding='utf-8'))
    data=read('research/claims.json')
    require(data==read('site/data/claims.json'),'Reviewed claims mirror changed')
    return validate_claims(data,{s['id'] for s in read('site/data/ledger.json')['sources']})

if __name__=='__main__':
    validate_files()
    print('Claims validation passed')
