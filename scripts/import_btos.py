"""Maintainer importer for the Census Bureau's Business Trends and Outlook Survey (BTOS)
AI-use supplement (public domain). No model calls.

BTOS asks a rotating biweekly panel of about 1.2 million U.S. businesses whether they used AI
in any business function in the prior two weeks, and Census publishes the current national and
by-sector shares every two weeks. Checked first: the keyed Census API's dataset catalog
(api.census.gov/data.json) does not list a "btos" timeseries/eits entry, and
https://api.census.gov/data/timeseries/eits/btos/variables.json 404s -- BTOS is not served
there today. Its own data page (census.gov/hfp/btos/data) is a JS app with no static download
link in the HTML, but the app itself fetches small public JSON files, found by reading its
bundle:

  https://www.census.gov/hfp/btos/ai_national.json   (national, dated biweekly points)
  https://www.census.gov/hfp/btos/AI_sector.json      (by NAICS sector, same shape)

This importer reads those files directly, robots-checked (www.census.gov allows it), the same
way import_epoch.py reads Epoch's public downloads -- no key, no api_access.py call, since
they are not on the keyed api.census.gov host. Records one national metric plus the two sector
breakdowns the task names (NAICS 51 Information, NAICS 54 Professional/Scientific/Technical),
one snapshot observation per published biweekly reference-period date. A survey estimate,
never an observation: sampling error applies and is not separately disclosed in these files.

    python scripts/import_btos.py            # download, snapshot, report what would change
    python scripts/import_btos.py --apply    # register the source, add metrics and records, rebuild
"""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from urllib.request import Request, build_opener, ProxyHandler

sys.path.insert(0,str(Path(__file__).resolve().parent))
import research
from research import load, save, now, require, UA, allowed_url

ROOT=Path(__file__).resolve().parents[1]
SNAPSHOTS=ROOT/'research/btos'
SOURCE_ID='census-btos-data'
SOURCE={'id':SOURCE_ID,'publisher':'U.S. Census Bureau','title':'Business Trends and Outlook Survey · AI use supplement','url':'https://www.census.gov/hfp/btos/data','published':None,'layers':['applications'],'license':'Public domain (U.S. government work)','provenance':'official'}
NATIONAL_URL='https://www.census.gov/hfp/btos/ai_national.json'
SECTOR_URL='https://www.census.gov/hfp/btos/AI_sector.json'
SERIES_TAG='Current AI Use (Last Two Weeks)'
# (NAICS code, the BTOS file's own sector label, a lowercase title-case label for our metric title/scope)
SECTORS=[('51','Information','Information'),('54','Professional, Scientific, and Technical Services','Professional, scientific and technical services')]
MAX_BYTES=5_000_000


def fetch(url):
    """Robots-checked public JSON download with the project agent string; not the keyed
    Census API (BTOS is not published there -- see module docstring)."""
    host=research.Fetcher().check_robots(url)
    allowed_url(url,host)
    with build_opener(ProxyHandler({})).open(Request(url,headers={'User-Agent':UA}),timeout=60) as response:
        body=response.read(MAX_BYTES+1)
    require(len(body)<=MAX_BYTES,'BTOS file exceeds size cap')
    return body


def parse(body):
    rows=json.loads(body.decode('utf-8'))
    require(isinstance(rows,list),'Unexpected BTOS response shape')
    return rows


def metric_definition(mid,title,geography,naics=None):
    return {'id':mid,'layer':'applications','title':title,'unit':'% of businesses','geography':geography,
            'scope':f"U.S. Census Bureau Business Trends and Outlook Survey: share of businesses reporting AI use in any business function in the prior two weeks, {geography}. A biweekly panel survey estimate, not a census; sampling error applies and is not separately disclosed in the machine-readable file.",
            'direction':'context','min':0,'max':100,
            'note':'Census BTOS AI-use supplement, public domain. Biweekly series; each import appends newly published reference periods and never rewrites earlier ones.',
            'source_ids':[SOURCE_ID],'company':None,'measurement_type':'business_ai_use_share','project':None,'allowed_statuses':['estimate'],'period_basis':'snapshot',
            'geography_code':naics,'series_start_year':2025,'chart_default_start':2025,'chart_default_end':2027,'definition_stable':True,
            'pre_period_note':'BTOS AI-use tracking begins with the survey supplement in this catalog (late 2025). Earlier periods are not estimated. Missing biweekly periods are not zero.'}


def records_for(rows,mid,retrieved_at,sha):
    observations=[]
    for r in rows:
        if r.get('xmltag')!=SERIES_TAG:continue
        d=(r.get('Date') or '').strip()
        if not re.fullmatch(r'20\d\d-\d\d-\d\d',d):continue
        value=r.get('Estimate')
        if not isinstance(value,(int,float)):continue
        observations.append({'id':f'{mid}-{d}','metric':mid,'year':int(d[:4]),'period':d,'value':round(float(value),1),'upper':None,'status':'estimate','source':SOURCE_ID,'precision':'approx','retrieved_at':retrieved_at,'method':'curated',
            'note':f"Census BTOS biweekly panel estimate, reference period ending {d}. Response file sha256 {sha[:12]}."[:300]})
    return observations


def run(apply=False):
    national_body=fetch(NATIONAL_URL);sector_body=fetch(SECTOR_URL)
    national_sha=hashlib.sha256(national_body).hexdigest();sector_sha=hashlib.sha256(sector_body).hexdigest()
    retrieved=now()
    private=research.LOCAL/'btos';private.mkdir(parents=True,exist_ok=True)
    (private/f'national-{national_sha[:12]}.json').write_bytes(national_body)
    (private/f'sector-{sector_sha[:12]}.json').write_bytes(sector_body)
    national_rows=parse(national_body);sector_rows=parse(sector_body)

    metrics={};observations=[];per_metric={}
    metrics['btos-ai-use-share']=metric_definition('btos-ai-use-share','Share of U.S. businesses currently using AI (Census BTOS)','United States')
    national_obs=records_for(national_rows,'btos-ai-use-share',retrieved,national_sha)
    per_metric['btos-ai-use-share']=len(national_obs);observations+=national_obs
    for naics,census_label,title_label in SECTORS:
        mid=f'btos-ai-use-share-naics-{naics}'
        metrics[mid]=metric_definition(mid,f'Share of U.S. businesses currently using AI · {title_label} (NAICS {naics}, Census BTOS)',f'United States, {title_label.lower()} (NAICS {naics})',naics=naics)
        rows=[r for r in sector_rows if r.get('NAICS')==census_label]
        sector_obs=records_for(rows,mid,retrieved,sector_sha)
        per_metric[mid]=len(sector_obs);observations+=sector_obs

    SNAPSHOTS.mkdir(exist_ok=True)
    snapshot={'dataset':'Census BTOS AI-use supplement','source_id':SOURCE_ID,'retrieved_at':retrieved,
              'national_url':NATIONAL_URL,'national_sha256':national_sha,'sector_url':SECTOR_URL,'sector_sha256':sector_sha,
              'sectors':{n:l for n,l,_ in SECTORS},'metrics':sorted(metrics),'records':len(observations),'license':'Public domain (U.S. government work)'}
    save(SNAPSHOTS/'btos.json',snapshot)

    ledger=load(ROOT/'site/data/ledger.json');catalog=load(ROOT/'research/catalog.json');registry=load(ROOT/'research/sources.json')
    existing_obs={o['id'] for o in ledger['observations']};new_obs=[o for o in observations if o['id'] not in existing_obs]
    # A series with no observations gets no metric: Census renaming a sector label leaves the file
    # fetchable and that one series empty, and an empty series reads as zero.
    with_records={o['metric'] for o in observations}
    known_metrics={m['id'] for m in catalog['metrics']};new_metrics=[m for mid,m in sorted(metrics.items()) if mid not in known_metrics and mid in with_records]
    from importer_common import apply_changes,check_floors,report_drift
    counts={'rows:national':len(national_rows),'rows:sector':len(sector_rows),**{f'records:{mid}':n for mid,n in per_metric.items()}}
    failures=check_floors(ROOT,'btos',counts)
    drift=report_drift(ROOT,'btos',observations,ledger['observations'])
    print(f"national periods {len({o['period'] for o in observations if o['metric']=='btos-ai-use-share'})} · metrics {len(metrics)} ({len(new_metrics)} new) · records {len(observations)} ({len(new_obs)} new) · drift {len(drift)} · latest period {max((o['period'] for o in observations),default=None)}",flush=True)
    if not apply:return {'metrics':new_metrics,'records':new_obs,'floor_failures':failures,'drift':drift}
    collection_entries={SOURCE_ID:{'rank':1,'region_book':'united-states','company_id':None,'claim_type':'other','cadence':'manual','weekday':0,'path_prefixes':[],'topics':[],'excerpts':False}}
    apply_changes(ROOT,importer_id='btos',new_sources=[SOURCE] if SOURCE_ID not in {s['id'] for s in registry['sources']} else (),
                  collection_entries=collection_entries,region_book='united-states',
                  new_metrics=new_metrics,new_observations=new_obs,snapshot=snapshot)
    print('catalog, registry and ledger updated; site rebuilt',flush=True)
    return {'metrics':new_metrics,'records':new_obs,'floor_failures':failures,'drift':drift}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__.splitlines()[0]);p.add_argument('--apply',action='store_true')
    a=p.parse_args(argv);return 1 if run(apply=a.apply).get('floor_failures') else 0


if __name__=='__main__':sys.exit(main())
