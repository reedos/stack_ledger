"""Contracts for reviewed geographic, capital and capability additions.

These extend existing catalogs; they grant no publication or source permissions.
"""
import math
import re
from datetime import date
from validate import require, text, timestamp

def finite(value):
    return type(value) in (int,float) and math.isfinite(value)

def validate_location(g,sources,layer,reviewed):
    require(set(g)=={'latitude','longitude','precision','label','source','source_key','reviewed_at'},'Unexpected map location fields')
    require(finite(g['latitude']) and -90<=g['latitude']<=90 and finite(g['longitude']) and -180<=g['longitude']<=180,'Invalid geographic coordinate')
    require(g['precision'] in {'place','county','facility'},'Unreviewed location precision')
    require(g['source'] in sources and layer in sources[g['source']]['layers'],'Missing location attribution')
    text(g['label'],200);text(g['source_key'],120)
    require(timestamp(g['reviewed_at'])<=reviewed,'Location review is newer than catalog review')

def validate_explorers(x,ledger,ecosystem):
    sources={s['id']:s for s in ledger['sources']};metrics={m['id']:m for m in ledger['metrics']}
    companies={c['id'] for c in ecosystem['companies']}
    if 'capital' in x:
        c=x['capital'];require({'companies','reviewed_at','scope','gaps'}<=c.keys() and c.keys()<={'companies','reviewed_at','scope','gaps','archived_forecast'},'Unexpected capital configuration')
        timestamp(c['reviewed_at']);text(c['scope'],700)
        require(isinstance(c['companies'],list) and c['companies'],'Empty capital comparison')
        seen=set()
        for row in c['companies']:
            require(set(row)=={'company','name','history_metric','guidance_metric','year_end'},'Unexpected capital series')
            require(row['company'] in companies and row['company'] not in seen,'Unknown or duplicate capital company');seen.add(row['company'])
            text(row['name'],100);require(row['year_end'] in {'December 31','June 30','May 31'},'Unreviewed fiscal year basis')
            for key,kind,status in [('history_metric','capex_recognized_usd','observation'),('guidance_metric','capex_announced_usd','forecast')]:
                if row[key] is None:require(key=='guidance_metric','Missing capital history');continue
                m=metrics.get(row[key],{})
                require(m.get('company')==row['company'] and m.get('measurement_type')==kind and m.get('unit')=='USD billion' and m.get('geography')=='Global','Capital metric basis mismatch')
                require(m.get('allowed_statuses')==[status],'Capital actual/guidance status mismatch')
                records=[o for o in ledger['observations'] if o['metric']==row[key] and not o.get('superseded_by')]
                require(records and all(o['status']==status for o in records),'Missing or mixed capital records')
                require(len(records)==len({o['year'] for o in records}),'Conflicting capital vintages need correction review')
        for gap in c['gaps']:text(gap,600)
        if 'archived_forecast' in c:
            a=c['archived_forecast']
            require(set(a)=={'label','as_of','source','companies'} and a['source'] in sources,'Invalid forecast archive')
            text(a['label'],150);require(re.fullmatch(r'\d{4}-\d{2}',a['as_of']),'Invalid forecast vintage')
            require(len(a['companies'])==len(seen) and {r['company'] for r in a['companies']}==seen,'Forecast archive must cover the complete cohort')
            for row in a['companies']:
                require(set(row)=={'company','metric'},'Invalid forecast member')
                m=metrics.get(row['metric'],{})
                require(m.get('company')==row['company'] and m.get('unit')=='USD billion' and m.get('allowed_statuses')==['forecast'],'Archived forecast basis mismatch')
                os=[o for o in ledger['observations'] if o['metric']==row['metric'] and not o.get('superseded_by')]
                require(os and all(o['source']==a['source'] and o['status']=='forecast' for o in os),'Mixed archived forecast source/status')
                require(len(os)==len({o['year'] for o in os}),'Duplicate archived forecast years')
    if 'capabilities' in x:
        c=x['capabilities']
        require(set(c)=={'source','method_source','retrieved_at','document_sha256','confidence_level','rows'},'Unexpected capabilities snapshot')
        retrieved=timestamp(c['retrieved_at'])
        require(c['source'] in sources and c['method_source'] in sources and all('models' in sources[id]['layers'] for id in (c['source'],c['method_source'])),'Missing capability attribution')
        require(re.fullmatch('[0-9a-f]{64}',c['document_sha256']) and c['confidence_level']==.9,'Missing dataset hash or unsupported confidence level')
        require(isinstance(c['rows'],list) and c['rows'],'Empty capability snapshot')
        ids=set()
        for r in c['rows']:
            require(set(r)=={'id','name','released','organization','country','access','score','low','high'},'Unexpected capability row')
            require(re.fullmatch('eci-[a-f0-9]{16}',r['id']) and r['id'] not in ids,'Duplicate or invalid capability ID');ids.add(r['id'])
            for field in ('name','organization','country'):text(r[field],200)
            require(date.fromisoformat(r['released'])<=retrieved.date(),'Future model release')
            require(r['access'] in {'Open weights','Closed weights','Other'},'Unknown model accessibility')
            require(finite(r['score']),'Invalid ECI score')
            require((r['low'] is None)==(r['high'] is None),'Incomplete ECI uncertainty interval')
            if r['low'] is not None:
                require(finite(r['low']) and finite(r['high']) and r['low']<=r['score']<=r['high'],'Invalid ECI uncertainty interval')
    return True
