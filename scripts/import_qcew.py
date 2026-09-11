"""Maintainer importer for BLS QCEW county employment (public domain). No model calls.

The Quarterly Census of Employment and Wages counts jobs from unemployment-insurance
records, so it is a near-census rather than a survey. This importer reads the open-data
industry files for two industries that track the buildout on the ground, keeps a
vintage-stamped snapshot, and records quarterly private employment for every county
where the catalog places a project, plus the national total:

  518210  Data processing, hosting and related services   (the data centers themselves)
  23821   Electrical contractors and other wiring installation contractors (who wires them)

Suppressed quarters (disclosure code N) are omitted, never recorded as zero. Employment
is the third-month level of the quarter, the series BLS publishes as the quarterly figure.
County coverage follows the projects' reviewed map counties; places without a county
FIPS wait for a place-to-county crosswalk.

    python scripts/import_qcew.py            # download, snapshot, report what would change
    python scripts/import_qcew.py --apply    # register the source, add metrics and records, rebuild
"""
import argparse
import csv
import hashlib
import io
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, build_opener, ProxyHandler

sys.path.insert(0,str(Path(__file__).resolve().parent))
import research
from research import load, save, now, require, UA, allowed_url

ROOT=Path(__file__).resolve().parents[1]
SNAPSHOTS=ROOT/'research/qcew'
SOURCE_ID='bls-qcew-open-data'
SOURCE={'id':SOURCE_ID,'publisher':'U.S. Bureau of Labor Statistics','title':'Quarterly Census of Employment and Wages · open data files','url':'https://www.bls.gov/cew/additional-resources/open-data/','published':None,'layers':['infrastructure','energy'],'license':'Public domain (U.S. government work)','provenance':'official'}
INDUSTRIES={'518210':('Data processing, hosting and related services','infrastructure'),'23821':('Electrical contractors and other wiring installation contractors','infrastructure')}
# QCEW aggregation levels by NAICS depth: (county, national). 6-digit files carry 78/18, 5-digit files 77/17.
AGGLVL={6:('78','18'),5:('77','17'),4:('76','16')}
FIRST_YEAR=2024
MAX_BYTES=20_000_000


def fetch(url):
    """data.bls.gov open-data paths are a listed statistical API (research/api-access.json); everything else goes through robots."""
    import api_access
    if api_access.allowed(url):return api_access.fetch(url,UA)
    host=research.Fetcher().check_robots(url);allowed_url(url,host)
    with build_opener(ProxyHandler({})).open(Request(url,headers={'User-Agent':UA}),timeout=60) as response:
        body=response.read(MAX_BYTES+1)
    require(len(body)<=MAX_BYTES,'QCEW file exceeds size cap')
    return body


def quarters(today=None):
    """(year, quarter) from FIRST_YEAR Q1 through the most recent quarter that could be published."""
    today=today or datetime.now(timezone.utc).date()
    out=[];y,q=FIRST_YEAR,1
    while (y,q)<=(today.year,(today.month-1)//3+1):
        out.append((y,q));q+=1
        if q==5:y,q=y+1,1
    return out


def parse(blob):
    return list(csv.DictReader(io.StringIO(blob.decode('utf-8-sig',errors='replace'))))


def project_counties(delivery):
    """county FIPS -> label, from reviewed map counties on accepted projects."""
    counties={}
    for p in delivery['projects']:
        locs=[p['map_location']] if p.get('map_location') else [e.get('location',e) for e in p.get('map_locations',[])]
        for l in locs:
            if l.get('source')=='census-map-counties' and l.get('source_key'):counties[str(l['source_key']).zfill(5)]=l.get('label') or l['source_key']
    return counties


def select_rows(rows,counties):
    """Private county rows for target counties plus the national private total; suppressed rows kept for the report, not recorded."""
    out=[]
    for r in rows:
        if r['own_code']!='5':continue
        county,national=AGGLVL.get(len(r['industry_code']),('78','18'))
        if r['area_fips']=='US000' and r['agglvl_code']==national:out.append(r)
        elif r['agglvl_code']==county and r['area_fips'] in counties:out.append(r)
    return out


def metric_definition(naics,fips,label):
    industry,layer=INDUSTRIES[naics]
    national=fips=='US000'
    return {'id':f"qcew-{'us' if national else fips}-{naics}",'layer':layer,'title':f"{'United States' if national else label} · private employment, {industry.lower()} (NAICS {naics})",
            'unit':'jobs (third month of quarter)','geography':'United States' if national else label,
            'scope':f"BLS QCEW private-ownership employment in NAICS {naics}, {'national total' if national else 'county'} level, third-month employment level of each quarter, from unemployment-insurance records. A near-census, not a survey. Quarters BLS suppresses for confidentiality are omitted; omission is not zero. Establishments in the note.",
            'direction':'context','min':0,'max':10_000_000 if national else 500_000,
            'note':'BLS Quarterly Census of Employment and Wages open data, public domain. Quarterly series; each import appends newly published quarters and never rewrites earlier ones.',
            'source_ids':[SOURCE_ID],'company':None,'measurement_type':'county_industry_employment','project':None,'allowed_statuses':['observation'],'period_basis':'quarter',
            'geography_code':None if national else fips,'series_start_year':FIRST_YEAR,'chart_default_start':FIRST_YEAR,'chart_default_end':FIRST_YEAR+3,'definition_stable':True,
            'pre_period_note':f'Series begins {FIRST_YEAR} Q1 in this catalog; earlier QCEW quarters exist and can be imported on review. Missing quarters are suppressed or unpublished, not zero.'}


def records_for(rows,retrieved_at,sha,counties):
    """Metrics and observations for selected rows of one quarter file."""
    metrics={};observations=[];suppressed=[]
    for r in rows:
        naics=r['industry_code'];fips=r['area_fips'];label=counties.get(fips,'United States')
        m=metric_definition(naics,fips,label);metrics[m['id']]=m
        if r['disclosure_code'].strip()=='N':suppressed.append((m['id'],r['year'],r['qtr']));continue
        year,q=int(r['year']),int(r['qtr'])
        observations.append({'id':f"{m['id']}-{year}q{q}",'metric':m['id'],'year':year,'period':f'{year}-Q{q}','value':int(r['month3_emplvl']),'upper':None,'status':'observation','source':SOURCE_ID,'precision':'eq','retrieved_at':retrieved_at,'method':'curated',
                             'note':f"BLS QCEW {year} Q{q}, private ownership, NAICS {naics}; {int(r['qtrly_estabs']):,} establishments; average weekly wage ${int(r['avg_wkly_wage']):,}. File sha256 {sha[:12]}."[:300]})
    return metrics,observations,suppressed


def run(apply=False,today=None):
    delivery=load(ROOT/'research/delivery.json');counties=project_counties(delivery)
    registry=load(ROOT/'research/sources.json');ledger=load(ROOT/'site/data/ledger.json');catalog=load(ROOT/'research/catalog.json')
    retrieved=now();all_metrics={};all_obs=[];all_supp=[];files=[];available=[]
    for naics in INDUSTRIES:
        for year,q in quarters(today):
            url=f'https://data.bls.gov/cew/data/api/{year}/{q}/industry/{naics}.csv'
            try:blob=fetch(url)
            except Exception as e:
                files.append({'url':url,'status':type(e).__name__});continue
            sha=hashlib.sha256(blob).hexdigest();private=research.LOCAL/'qcew';private.mkdir(parents=True,exist_ok=True);(private/f'{naics}-{year}q{q}-{sha[:12]}.csv').write_bytes(blob)
            rows=select_rows(parse(blob),counties);m,o,s=records_for(rows,retrieved,sha,counties)
            all_metrics.update(m);all_obs+=o;all_supp+=s;available.append((naics,year,q));files.append({'url':url,'status':'ok','sha256':sha,'rows_kept':len(rows)})
    SNAPSHOTS.mkdir(exist_ok=True)
    snapshot={'dataset':'BLS QCEW open data','source_id':SOURCE_ID,'retrieved_at':retrieved,'industries':INDUSTRIES,'counties':counties,'files':files,'quarters_available':available,'suppressed':all_supp,
              'metrics':sorted(all_metrics),'records':len(all_obs),'license':'Public domain (U.S. government work)'}
    save(SNAPSHOTS/'qcew.json',snapshot)
    from importer_common import check_floors,report_drift
    counts={'files:ok':sum(1 for f in files if f['status']=='ok'),'rows:kept':sum(f.get('rows_kept',0) for f in files),'records':len(all_obs)}
    failures=check_floors(ROOT,'qcew',counts)
    drift=report_drift(ROOT,'qcew',all_obs,ledger['observations'])
    existing_ids={o['id'] for o in ledger['observations']}
    new_obs=[o for o in all_obs if o['id'] not in existing_ids]
    # A county whose every quarter is suppressed gets no metric: an empty series would read as zero.
    with_records={o['metric'] for o in all_obs}
    known={m['id'] for m in catalog['metrics']};new_metrics=[m for mid,m in sorted(all_metrics.items()) if mid not in known and mid in with_records]
    print(f"counties {len(counties)} · quarters available {sorted(set((y,q) for _,y,q in available))[-1] if available else None} · metrics {len(all_metrics)} ({len(new_metrics)} new) · records {len(all_obs)} ({len(new_obs)} new) · drift {len(drift)} · suppressed county-quarters {len(all_supp)}",flush=True)
    if not apply:return {'metrics':new_metrics,'records':new_obs,'suppressed':all_supp,'floor_failures':failures,'drift':drift}
    from importer_common import apply_changes
    collection_entries={SOURCE_ID:{'rank':1,'region_book':'united-states','company_id':None,'claim_type':'labor','cadence':'manual','weekday':0,'path_prefixes':[],'topics':[],'excerpts':False}}
    apply_changes(ROOT,importer_id='qcew',new_sources=[SOURCE] if SOURCE_ID not in {s['id'] for s in registry['sources']} else (),
                  collection_entries=collection_entries,region_book='united-states',
                  new_metrics=new_metrics,new_observations=new_obs,snapshot=snapshot)
    print('catalog, registry and ledger updated; site rebuilt',flush=True)
    return {'metrics':new_metrics,'records':new_obs,'suppressed':all_supp,'floor_failures':failures,'drift':drift}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__.splitlines()[0]);p.add_argument('--apply',action='store_true')
    a=p.parse_args(argv);return 1 if run(apply=a.apply).get('floor_failures') else 0


if __name__=='__main__':sys.exit(main())
