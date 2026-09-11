"""Maintainer importer for Census QWI hires and earnings by county and industry (public domain). No model calls.

The Quarterly Workforce Indicators (LEHD) add what QCEW does not publish: hires in the
quarter and average monthly earnings, by county and 4-digit industry. This importer reads
them through the Census Data API under the owner's registered key (research/api-access.json)
for the same project counties QCEW covers, and records:

  5182  Data processing, hosting and related services  -> hires (HirA), average monthly earnings (EarnS)
  2382  Building equipment contractors (incl. electrical) -> hires, earnings

Employment itself stays with QCEW; QWI's count follows different rules and would read as a
second, slightly different number. Missing or suppressed cells are omitted, never zero.

    python scripts/import_qwi.py            # fetch, snapshot, report what would change
    python scripts/import_qwi.py --apply    # register the source, add metrics and records, rebuild
"""
import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parent))
import research
from importer_common import DEGRADED_EXIT

from research import load, save, now, require, UA
import api_access

ROOT=Path(__file__).resolve().parents[1]
SNAPSHOTS=ROOT/'research/qwi'
SOURCE_ID='census-qwi-api'
SOURCE={'id':SOURCE_ID,'publisher':'U.S. Census Bureau','title':'Quarterly Workforce Indicators (LEHD) · Census Data API','url':'https://www.census.gov/data/developers/data-sets/qwi.html','published':None,'layers':['infrastructure','energy'],'license':'Public domain (U.S. government work)','provenance':'official'}
INDUSTRIES={'5182':('Data processing, hosting and related services','infrastructure'),'2382':('Building equipment contractors (electrical, plumbing, HVAC)','infrastructure')}
SERIES=[('hires','HirA','county_industry_hires','hires in quarter','hires (all workers)',500_000,'Census QWI stable hires (HirA): workers who began a job in the quarter and were employed at the end of it, private ownership, county by 4-digit NAICS. Cells Census suppresses or leaves empty are omitted; omission is not zero.'),
        ('earnings','EarnS','county_industry_avg_monthly_earnings','USD / month (average, stable jobs)','average monthly earnings',100_000,'Census QWI average monthly earnings of stable employees (EarnS), private ownership, county by 4-digit NAICS, nominal dollars. A pay level for the industry in the county, not a project wage.')]
FIRST='2024-Q1'


def latest_quarter(today=None):
    today=today or datetime.now(timezone.utc).date();return f'{today.year}-Q{(today.month-1)//3+1}'


def project_counties(delivery):
    from import_qcew import project_counties as pc
    return pc(delivery)


def query_url(fips,naics,upto):
    return f'https://api.census.gov/data/timeseries/qwi/sa?get=HirA,EarnS,Emp&for=county:{fips[2:]}&in=state:{fips[:2]}&industry={naics}&ownercode=A05&time=from{FIRST}to{upto}'


def parse(body):
    rows=json.loads(body.decode('utf-8'))
    header=rows[0];return [dict(zip(header,r)) for r in rows[1:]]


def metric_definition(key,naics,fips,label):
    industry,layer=INDUSTRIES[naics];_,_,mtype,unit,title,maximum,scope=next(s for s in SERIES if s[0]==key)
    return {'id':f'qwi-{fips}-{naics}-{key}','layer':layer,'title':f'{label} · {title}, {industry.lower()} (NAICS {naics})','unit':unit,'geography':label,'scope':scope,'direction':'context','min':0,'max':maximum,
            'note':'Census Quarterly Workforce Indicators through the Census Data API, public domain. Quarterly series; each import appends newly published quarters and never rewrites earlier ones.',
            'source_ids':[SOURCE_ID],'company':None,'measurement_type':mtype,'project':None,'allowed_statuses':['observation'],'period_basis':'quarter','geography_code':fips,
            'series_start_year':int(FIRST[:4]),'chart_default_start':int(FIRST[:4]),'chart_default_end':int(FIRST[:4])+3,'definition_stable':True,
            'pre_period_note':f'Series begins {FIRST} in this catalog; earlier QWI quarters exist and can be imported on review. Missing quarters are unpublished or suppressed, not zero.'}


def records_for(rows,fips,naics,label,retrieved_at,sha):
    metrics={};observations=[]
    for r in rows:
        period=r.get('time','');year=int(period[:4]) if period[:4].isdigit() else None
        if not year or '-Q' not in period:continue
        for key,column,*_ in SERIES:
            value=r.get(column)
            if value in (None,'','null'):continue
            try:value=int(float(value))
            except ValueError:continue
            if value<0:continue
            m=metric_definition(key,naics,fips,label);metrics[m['id']]=m
            observations.append({'id':f"{m['id']}-{period.lower().replace('-','')}",'metric':m['id'],'year':year,'period':period,'value':value,'upper':None,'status':'observation','source':SOURCE_ID,'precision':'eq','retrieved_at':retrieved_at,'method':'curated',
                                 'note':f"Census QWI {period}, private ownership, NAICS {naics}, county {fips}; employment (Emp) in the same cell {r.get('Emp') or 'n/a'}. Response sha256 {sha[:12]}."[:300]})
    return metrics,observations


def run(apply=False,today=None):
    require(api_access.key('census'),'Census API key missing from .local/api-keys.json')
    delivery=load(ROOT/'research/delivery.json');counties=project_counties(delivery)
    registry=load(ROOT/'research/sources.json');ledger=load(ROOT/'site/data/ledger.json');catalog=load(ROOT/'research/catalog.json')
    retrieved=now();upto=latest_quarter(today);all_metrics={};all_obs=[];calls=[]
    private=research.LOCAL/'qwi';private.mkdir(parents=True,exist_ok=True)
    for fips,label in sorted(counties.items()):
        for naics in INDUSTRIES:
            url=query_url(fips,naics,upto)
            try:body=api_access.fetch(url,UA)
            except Exception as e:
                calls.append({'county':fips,'naics':naics,'status':type(e).__name__});continue
            sha=hashlib.sha256(body).hexdigest();(private/f'{fips}-{naics}-{sha[:12]}.json').write_bytes(body)
            try:rows=parse(body)
            except ValueError:
                calls.append({'county':fips,'naics':naics,'status':'unparseable'});continue
            m,o=records_for(rows,fips,naics,label,retrieved,sha);all_metrics.update(m);all_obs+=o
            calls.append({'county':fips,'naics':naics,'status':'ok','rows':len(rows)})
    SNAPSHOTS.mkdir(exist_ok=True)
    snapshot={'dataset':'Census QWI via Census Data API','source_id':SOURCE_ID,'retrieved_at':retrieved,'industries':INDUSTRIES,'counties':counties,'calls':calls,'metrics':sorted(all_metrics),'records':len(all_obs),'license':'Public domain (U.S. government work)','key':'owner-registered, not recorded'}
    save(SNAPSHOTS/'qwi.json',snapshot)
    from importer_common import check_floors,report_drift, DEGRADED_EXIT
    counts={'calls:ok':sum(1 for c in calls if c['status']=='ok'),'rows':sum(c.get('rows',0) for c in calls),'records':len(all_obs)}
    failures=check_floors(ROOT,'qwi',counts)
    drift=report_drift(ROOT,'qwi',all_obs,ledger['observations'])
    existing={o['id'] for o in ledger['observations']};new_obs=[o for o in all_obs if o['id'] not in existing]
    with_records={o['metric'] for o in all_obs};known={m['id'] for m in catalog['metrics']}
    new_metrics=[m for mid,m in sorted(all_metrics.items()) if mid not in known and mid in with_records]
    ok=sum(1 for c in calls if c['status']=='ok')
    print(f"counties {len(counties)} · api calls ok {ok}/{len(calls)} · metrics {len(all_metrics)} ({len(new_metrics)} new) · records {len(all_obs)} ({len(new_obs)} new) · drift {len(drift)} · latest period {max((o['period'] for o in all_obs),default=None)}",flush=True)
    if not apply:return {'metrics':new_metrics,'records':new_obs,'floor_failures':failures,'drift':drift}
    from importer_common import apply_changes
    collection_entries={SOURCE_ID:{'rank':1,'region_book':'united-states','company_id':None,'claim_type':'labor','cadence':'manual','weekday':0,'path_prefixes':[],'topics':[],'excerpts':False}}
    apply_changes(ROOT,importer_id='qwi',new_sources=[SOURCE] if SOURCE_ID not in {s['id'] for s in registry['sources']} else (),
                  collection_entries=collection_entries,region_book='united-states',
                  new_metrics=new_metrics,new_observations=new_obs,snapshot=snapshot)
    print('catalog, registry and ledger updated; site rebuilt',flush=True)
    return {'metrics':new_metrics,'records':new_obs,'floor_failures':failures,'drift':drift}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__.splitlines()[0]);p.add_argument('--apply',action='store_true')
    a=p.parse_args(argv);return DEGRADED_EXIT if run(apply=a.apply).get('floor_failures') else 0


if __name__=='__main__':sys.exit(main())
