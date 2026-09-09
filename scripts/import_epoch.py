"""Maintainer importer for Epoch AI datasets (CC BY 4.0). No model calls.

Epoch publishes machine-readable, vintage-dated estimates with uncertainty. The
collector cannot read ZIP archives by design, so this is a reviewed maintainer tool:

  1. download a dataset, hash it, keep the raw archive privately and a compact
     snapshot under research/epoch/<dataset>.json (one vintage; history is in Git);
  2. reconcile Epoch data-center and GPU-cluster names against the accepted
     projects catalog and write a review report (matches, proposed additions,
     accepted projects without an Epoch row, unresolved) - proposals only;
  3. promote a small reviewed set of Epoch series into ledger metrics as estimates
     on a quarterly period basis (chip components), with the vintage in each note;
  4. export Epoch's own "Selected Sources" URLs as private discovery leads;
  5. cross-check Epoch revenue reports against the ledger's company revenue records.

Estimates are never observations. Every promoted record carries the dataset vintage.

    python scripts/import_epoch.py all                 # download, snapshot, report (private + research/epoch)
    python scripts/import_epoch.py chip-components --apply   # also register the source and promote series
    python scripts/import_epoch.py data-centers --apply      # also register the dataset source
"""
import argparse
import csv
import hashlib
import io
import json
import re
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, build_opener, ProxyHandler

sys.path.insert(0,str(Path(__file__).resolve().parent))
import research
from research import load, save, now, require, digest, UA, allowed_url
from validate import observation_valid, validate

ROOT=Path(__file__).resolve().parents[1]
SNAPSHOTS=ROOT/'research/epoch'
MAX_BYTES=60_000_000
LICENSE='CC BY 4.0'

DATASETS={
    'data-centers':{'url':'https://epoch.ai/data/data_centers/data_centers.zip','page':'https://epoch.ai/data/ai-data-centers','source_id':'epoch-data-centers-dataset','title':'AI Data Centers dataset','layers':['infrastructure']},
    'gpu-clusters':{'url':'https://epoch.ai/data/gpu_clusters.csv','page':'https://epoch.ai/data/gpu-clusters','source_id':'epoch-gpu-clusters-dataset','title':'GPU Clusters dataset','layers':['infrastructure','chips']},
    'chip-components':{'url':'https://epoch.ai/data/ai_chip_components.zip','page':'https://epoch.ai/data/ai-chip-components','source_id':'epoch-chip-components-dataset','title':'AI Chip Components dataset','layers':['chips']},
    'companies':{'url':'https://epoch.ai/data/ai_companies.zip','page':'https://epoch.ai/data/ai-companies','source_id':'epoch-companies-dataset','title':'AI Companies dataset','layers':['models','applications']},
}

# Promoted series: Epoch-computed quarterly medians only; nothing is summed or converted here.
PROMOTED={
    'chip-components':[
        {'metric':'epoch-cowos-supply-quarterly','file':'supply_denominators.csv','column':'CoWoS supply','unit':'wafers / quarter','title':'CoWoS packaging supply (Epoch estimate)','measurement_type':'estimated_cowos_supply_wafers_quarterly','scope':'Epoch AI median estimate of total CoWoS advanced-packaging wafer supply available to AI accelerators per quarter, all designers. 5th to 95th percentile in each note. An estimate of supply, not shipments or installed accelerators.','max':10_000_000},
        {'metric':'epoch-logic-supply-quarterly','file':'supply_denominators.csv','column':'Logic supply','unit':'wafers / quarter','title':'Advanced logic wafer supply for AI accelerators (Epoch estimate)','measurement_type':'estimated_logic_supply_wafers_quarterly','scope':'Epoch AI median estimate of advanced logic wafer supply consumed by AI accelerators per quarter. 5th to 95th percentile in each note. Not total foundry output.','max':100_000_000},
        {'metric':'epoch-hbm-supply-quarterly','file':'supply_denominators.csv','column':'HBM supply (USD)','unit':'USD / quarter','title':'HBM supply value for AI accelerators (Epoch estimate)','measurement_type':'estimated_hbm_supply_usd_quarterly','scope':'Epoch AI median estimate of high-bandwidth-memory supply value consumed by AI accelerators per quarter, in USD. 5th to 95th percentile in each note. Not memory-maker revenue.','max':1_000_000_000_000},
        {'metric':'epoch-nvidia-cowos-wafers-quarterly','file':'quarterly_by_designer.csv','column':'CoWoS wafers','filter':{'Designer':'NVIDIA'},'unit':'wafers / quarter','title':'Nvidia CoWoS wafer consumption (Epoch estimate)','measurement_type':'estimated_cowos_consumption_wafers_quarterly','scope':'Epoch AI median estimate of CoWoS wafers consumed by Nvidia accelerators per quarter. 5th to 95th percentile in each note. Consumption estimate, not TSMC capacity or Nvidia disclosure.','max':10_000_000,'company':'nvidia'},
    ],
}

STOP={'data','center','centre','datacenter','campus','project','phase','the','of','and','ai','facility','site','program','programme','cluster','supercomputer','building','original',
      'north','south','east','west','mega','expansion','first','second','county','city'}


def fetch(url):
    """Robots-checked binary download with the project agent string and a size cap."""
    host=research.Fetcher().check_robots(url)
    allowed_url(url,host)
    with build_opener(ProxyHandler({})).open(Request(url,headers={'User-Agent':UA}),timeout=60) as response:
        body=response.read(MAX_BYTES+1)
    require(len(body)<=MAX_BYTES,'Dataset exceeds size cap')
    return body


def tables(name,blob):
    """filename -> list of row dicts, plus README text when present."""
    out={};readme=''
    if DATASETS[name]['url'].endswith('.csv'):
        out[Path(urlparse(DATASETS[name]['url']).path).name]=list(csv.DictReader(io.StringIO(blob.decode('utf-8',errors='replace'))))
        return out,readme
    z=zipfile.ZipFile(io.BytesIO(blob))
    for info in z.infolist():
        if info.filename.endswith('.csv'):out[info.filename]=list(csv.DictReader(io.TextIOWrapper(z.open(info),encoding='utf-8',errors='replace')))
        elif info.filename.lower().endswith('.md'):readme=z.read(info).decode('utf-8',errors='replace')
    return out,readme


def vintage_of(readme,retrieved_at):
    m=re.search(r'year\s*=\s*\{(\d{4})\}.*?month\s*=\s*\{(\d{1,2})\}',readme,re.S)
    return f'{m[1]}-{int(m[2]):02d}' if m else retrieved_at[:7]


def snapshot(name,blob,tabs,readme):
    sha=hashlib.sha256(blob).hexdigest();retrieved=now()
    private=research.LOCAL/'epoch'/name;private.mkdir(parents=True,exist_ok=True)
    (private/(sha+Path(urlparse(DATASETS[name]['url']).path).suffix)).write_bytes(blob)
    record={'dataset':name,'title':DATASETS[name]['title'],'page':DATASETS[name]['page'],'download':DATASETS[name]['url'],'license':LICENSE,
            'attribution':f'Epoch AI, "{DATASETS[name]["title"].replace(" dataset","")}". Published online at epoch.ai. Retrieved from {DATASETS[name]["page"]}.',
            'retrieved_at':retrieved,'sha256':sha,'vintage':vintage_of(readme,retrieved),'row_counts':{k:len(v) for k,v in tabs.items()},'tables':tabs}
    SNAPSHOTS.mkdir(exist_ok=True)
    save(SNAPSHOTS/f'{name}.json',record)
    return record


def tokens(text):
    words=re.findall(r'[a-z0-9]+',(text or '').lower())
    return {w for w in words if w not in STOP and (len(w)>=4 or w.isdigit())}


def common_tokens(projects,owners=()):
    """Tokens that name owners or programmes rather than places: anything in three or more
    accepted project names, plus every owner token. Epoch's own names are not counted, so a
    place that Epoch lists twice (New Albany, Abilene) stays distinctive."""
    counts={}
    for name in [p['name'] for p in projects]:
        for t in tokens(name):counts[t]=counts.get(t,0)+1
    common={t for t,n in counts.items() if n>=3}
    for owner in list(owners)+[p.get('owner','') for p in projects]:
        common|={t for t in tokens(owner)}
    return common


def owners_conflict(epoch_owner,project_owner):
    a={t.rstrip('#') for t in re.findall(r'[a-z0-9]+',(epoch_owner or '').lower()) if t not in {'confident','likely','speculative'}}
    b=set(re.findall(r'[a-z0-9]+',(project_owner or '').lower()))
    if not a or not b:return False
    return not any(x in y or y in x for x in a for y in b if len(x)>=3 and len(y)>=3)


def match_projects(epoch_name,epoch_owner,projects,aliases,common=None):
    """Reviewed alias first; otherwise a suggestion from a distinctive place token, or a shared
    programme name with agreeing numbers (Colossus 2). Owner names never carry a match on their
    own, and a clear owner conflict vetoes one. Never a silent merge."""
    if epoch_name in aliases:return aliases[epoch_name],'reviewed'
    common=common if common is not None else common_tokens(projects)
    want=tokens(epoch_name);want_digits={t for t in want if t.isdigit()}
    best=None
    for p in projects:
        if owners_conflict(epoch_owner,p.get('owner','')):continue
        have=tokens(p['name'])|tokens(p.get('location',''))
        shared=want&have
        distinctive=[t for t in shared if not t.isdigit() and t not in common]
        programme=[t for t in shared if not t.isdigit() and t in common and t in tokens(p['name'])]
        have_digits={t for t in tokens(p['name']) if t.isdigit()}
        digits_ok=want_digits==have_digits
        if distinctive and digits_ok:score=len(distinctive)*2+len(programme)+1   # a shared programme name breaks ties
        elif programme and want_digits and digits_ok:score=1
        else:continue
        if best is None or score>best[0]:best=(score,p['id'],False)
        elif score==best[0]:best=(best[0],best[1],True)   # a tie is ambiguous, never a match
    if best is None:return None,'none'
    return (None,'ambiguous') if best[2] else (best[1],'suggested')


def markdown_urls(text):
    urls=re.findall(r'\((https?://[^)\s]+)\)',text or '')+re.findall(r'(?<!\()\bhttps?://[^\s)\]]+',text or '')
    return [u for u in dict.fromkeys(urls) if not re.search(r'(^|\.)(x|twitter)\.com|docs\.google\.com',urlparse(u).hostname or '')]


def number(value):
    try:return float(value)
    except (TypeError,ValueError):return None


def reconcile(dc,clusters,delivery,aliases):
    projects=delivery['projects']
    common=common_tokens(projects,[r.get('Owner','') for r in dc['tables'].get('data_centers.csv',[])])
    matched=[];proposed=[];unresolved=[]
    for row in dc['tables'].get('data_centers.csv',[]):
        pid,how=match_projects(row['Name'],row.get('Owner',''),projects,aliases,common)
        item={'epoch_name':row['Name'],'owner':row.get('Owner',''),'users':row.get('Users',''),'country':row.get('Country',''),
              'current_power_mw':number(row.get('Current power (MW)')),'current_h100e':number(row.get('Current H100 equivalents')),
              'capital_cost_2025_usd_bn':number(row.get('Current total capital cost (2025 USD billions)')),'sources':markdown_urls(row.get('Selected Sources','')),'match':pid,'match_basis':how}
        (matched if pid else proposed).append(item)
    matched_ids={m['match'] for m in matched}
    without=[{'id':p['id'],'name':p['name'],'owner':p['owner'],'stage':p['stage']} for p in projects if p['layer']=='infrastructure' and p['id'] not in matched_ids]
    dc_names={t for r in dc['tables'].get('data_centers.csv',[]) for t in tokens(r['Name'])}
    big=[]
    for row in clusters['tables'].get('gpu_clusters.csv',[]):
        mw=number(row.get('Power Capacity (MW)'));h=number(row.get('H100 equivalents'))
        if (mw or 0)<100 and (h or 0)<100_000:continue
        pid,how=match_projects(row['Name'],row.get('Owner',''),projects,aliases,common)
        if pid:continue
        if tokens(row['Name'])&dc_names:continue
        big.append({'epoch_name':row['Name'],'owner':row.get('Owner',''),'country':row.get('Country',''),'status':row.get('Status',''),'certainty':row.get('Certainty',''),'power_mw':mw,'h100e':h,'first_operational':row.get('First Operational Date',''),'possible_duplicate':row.get('Possible Duplicate','')})
    return {'matched':matched,'proposed_additions':proposed,'accepted_without_epoch_row':without,'large_clusters_unmatched':big}


def reconciliation_markdown(result,dc,clusters,ledger):
    obs={o['id']:o for o in ledger['observations']};metrics={m['id']:m for m in ledger['metrics']}
    projects={p['id']:p for p in load(ROOT/'research/delivery.json')['projects']}
    def ledger_mw(pid):
        vals=[]
        for oid in projects.get(pid,{}).get('observations',[]):
            o=obs.get(oid)
            if o and 'MW' in metrics[o['metric']]['unit']:vals.append(f"{o['value']:g} {metrics[o['metric']]['unit']} ({o['period']}, {o['status']})")
        return '; '.join(vals) or 'no MW record'
    L=[f"# Epoch data-center reconciliation · {now()[:10]}",'',f"Epoch AI Data Centers vintage {dc['vintage']} (sha256 {dc['sha256'][:12]}…), GPU Clusters vintage {clusters['vintage']}. {LICENSE}. Epoch figures are estimates from satellite, permit and filing analysis; they are compared here, not adopted. Suggested matches and proposed additions require human review before any catalog change.",'',
       f"Matched {len(result['matched'])} · proposed additions {len(result['proposed_additions'])} · accepted infrastructure projects without an Epoch row {len(result['accepted_without_epoch_row'])} · large unmatched GPU clusters {len(result['large_clusters_unmatched'])}",'',
       '## Matched sites (Epoch estimate vs ledger)','','| Epoch site | Basis | Project | Epoch current MW | Epoch H100e | Epoch capex 2025 USD bn | Ledger MW records |','|---|---|---|---|---|---|---|']
    for m in sorted(result['matched'],key=lambda x:-(x['current_power_mw'] or 0)):
        L.append(f"| {m['epoch_name']} | {m['match_basis']} | {m['match']} | {m['current_power_mw'] or ''} | {round(m['current_h100e']) if m['current_h100e'] else ''} | {round(m['capital_cost_2025_usd_bn'],1) if m['capital_cost_2025_usd_bn'] else ''} | {ledger_mw(m['match'])} |")
    L+=['','## Epoch sites with no accepted project (proposed additions, private review)','','| Epoch site | Owner | Users | Country | Current MW | H100e | Sources |','|---|---|---|---|---|---|---|']
    for p in sorted(result['proposed_additions'],key=lambda x:-(x['current_power_mw'] or 0)):
        L.append(f"| {p['epoch_name']} | {p['owner']} | {p['users'][:40]} | {p['country']} | {p['current_power_mw'] or ''} | {round(p['current_h100e']) if p['current_h100e'] else ''} | {len(p['sources'])} |")
    L+=['','## Accepted infrastructure projects without an Epoch row','']+[f"- {w['id']} · {w['name']} · {w['owner']} · {w['stage']}" for w in result['accepted_without_epoch_row']]
    L+=['','## Large GPU clusters (≥100 MW or ≥100k H100e) matching nothing','','| Cluster | Owner | Country | Status | Certainty | MW | H100e | First operational | Possible duplicate |','|---|---|---|---|---|---|---|---|---|']
    for c in sorted(result['large_clusters_unmatched'],key=lambda x:-(x['power_mw'] or x['h100e'] or 0)):
        L.append(f"| {c['epoch_name']} | {c['owner']} | {c['country']} | {c['status']} | {c['certainty']} | {c['power_mw'] or ''} | {round(c['h100e']) if c['h100e'] else ''} | {c['first_operational']} | {c['possible_duplicate']} |")
    L+=['','Aliases live in research/epoch/aliases.json (Epoch name → project id, or null for a reviewed non-match). Suggested matches are token overlaps, not confirmations.']
    return '\n'.join(L)


def quarter_period(label):
    m=re.fullmatch(r'Q([1-4])\s+(20\d\d)',label.strip())
    require(m is not None,f'Unrecognized quarter label: {label}')
    return f'{m[2]}-Q{m[1]}',int(m[2])


def metric_definition(spec,source_id,vintage):
    return {'id':spec['metric'],'layer':'chips','title':spec['title'],'unit':spec['unit'],'geography':'Global','scope':spec['scope'],'direction':'context','min':0,'max':spec['max'],
            'note':f"Epoch AI estimates, {LICENSE}. Median plotted; 5th to 95th percentile in each record note. Dataset vintage {vintage}; a new vintage replaces the series through reviewed import, never by appending competing values.",
            'source_ids':[source_id],'company':spec.get('company'),'measurement_type':spec['measurement_type'],'project':None,'allowed_statuses':['estimate'],'period_basis':'quarter',
            'series_start_year':2024,'chart_default_start':2024,'chart_default_end':2027,'definition_stable':True,
            'pre_period_note':'Epoch series begins Q1 2024. Earlier quarters are not estimated. Missing quarters are not zero.'}


def promote(name,record,catalog,ledger,registry):
    """Add or refresh promoted metrics and their quarterly estimate records for this vintage."""
    spec_list=PROMOTED.get(name,[]);source_id=DATASETS[name]['source_id']
    added_metrics=[];records=[]
    metrics={m['id']:m for m in catalog['metrics']}
    for spec in spec_list:
        definition=metric_definition(spec,source_id,record['vintage'])
        if spec['metric'] in metrics:
            # Importer-owned definitions are replaced whole; the reviewed spec lives in PROMOTED.
            metrics[spec['metric']].clear();metrics[spec['metric']].update(definition)
        else:
            catalog['metrics'].append(definition);metrics[spec['metric']]=definition;added_metrics.append(spec['metric'])
        rows=record['tables'][spec['file']]
        for row in rows:
            if any(row.get(k)!=v for k,v in spec.get('filter',{}).items()):continue
            period,year=quarter_period(row['Quarter'])
            med=number(row.get(f"{spec['column']} (median)"));lo=number(row.get(f"{spec['column']} (5th percentile)"));hi=number(row.get(f"{spec['column']} (95th percentile)"))
            if med is None:continue
            records.append({'id':f"{spec['metric']}-{period.lower()}",'metric':spec['metric'],'year':year,'period':period,'value':round(med,2),'upper':None,'status':'estimate','source':source_id,'precision':'approx','retrieved_at':record['retrieved_at'],'method':'curated',
                            'note':f"Epoch AI median estimate; 5th to 95th percentile {lo:,.0f} to {hi:,.0f}. Dataset vintage {record['vintage']}, sha256 {record['sha256'][:12]}. {LICENSE}."[:300]})
    # Replace this source's records for promoted metrics wholesale: a new vintage supersedes the whole series.
    keep=[o for o in ledger['observations'] if not (o['source']==source_id and o['metric'] in {s['metric'] for s in spec_list})]
    ledger['observations']=keep+records
    ledger['metrics']=catalog['metrics']
    all_metrics={m['id']:m for m in ledger['metrics']};sources={s['id']:s for s in ledger['sources']}
    for o in records:observation_valid(o,all_metrics,sources)
    return added_metrics,records


def register_source(name,registry,ledger):
    d=DATASETS[name]
    if d['source_id'] in {s['id'] for s in registry['sources']}:return False
    source={'id':d['source_id'],'publisher':'Epoch AI','title':d['title'],'url':d['url'],'published':None,'layers':d['layers'],'license':LICENSE}
    registry['sources'].append(source);ledger['sources'].append(dict(source))
    registry['collection'][d['source_id']]={'rank':1,'region_book':'global','company_id':None,'claim_type':'other','cadence':'manual','weekday':0,'path_prefixes':[],'topics':[],'excerpts':False}
    if d['source_id'] not in registry['region_books']['global']['sources']:registry['region_books']['global']['sources'].append(d['source_id'])
    return True


def export_leads(name,record):
    urls=[]
    for rows in record['tables'].values():
        for row in rows:
            for key,value in row.items():
                if re.search(r'source',key,re.I) and value:urls+=markdown_urls(value)
    urls=list(dict.fromkeys(urls))
    folder=research.LOCAL/'discovery-leads';folder.mkdir(parents=True,exist_ok=True)
    for i in range(0,len(urls),10):
        save(folder/f'epoch-{name}-{record["sha256"][:8]}-{i//10:03d}.json',{'source':DATASETS[name]['source_id'],'retrieved_at':record['retrieved_at'],'urls':urls[i:i+10],'review_required':True,
             'instruction':'Primary-source pointers cited by Epoch AI; untrusted until fetched under the discovery policy. Never a publication permission.'})
    return len(urls)


def revenue_crosscheck(companies_record,ledger,ecosystem):
    names={c['name'].lower():c for c in ecosystem['companies']}
    metrics={m['id']:m for m in ledger['metrics']}
    latest={}
    for o in ledger['observations']:
        m=metrics[o['metric']]
        if m.get('measurement_type') in {'annual_revenue','annualized_run_rate','annual_revenue_forecast'} or m['id'].startswith('revenue-'):
            latest.setdefault(m.get('company'),[]).append(o)
    L=['','## Epoch revenue reports vs ledger company revenue','','| Company | Epoch date | Epoch annualized USD | Type | Confidence | Ledger latest | Epoch source |','|---|---|---|---|---|---|---|']
    for row in sorted(companies_record['tables'].get('ai_companies_revenue_reports.csv',[]),key=lambda r:r.get('Date',''),reverse=True)[:40]:
        company=names.get(row['Company'].lower().split(' (')[0])
        mine=latest.get(company['id'] if company else None,[])
        newest=max(mine,key=lambda o:(o['year'],o['period']),default=None)
        mine_txt=f"{newest['value']:g} {metrics[newest['metric']]['unit']} · {newest['period']} · {newest['status']}" if newest else ('not tracked' if not company else 'no revenue record')
        L.append(f"| {row['Company']} | {row['Date']} | {number(row['Annualized revenue (USD)']) or '':,.0f} | {row['Annualized revenue type']} | {row['Confidence']} | {mine_txt} | {row['Source 1'][:60]} |" if number(row['Annualized revenue (USD)']) else f"| {row['Company']} | {row['Date']} | | {row['Annualized revenue type']} | {row['Confidence']} | {mine_txt} | {row['Source 1'][:60]} |")
    return '\n'.join(L)


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('dataset',choices=[*DATASETS,'all']);p.add_argument('--apply',action='store_true',help='Register dataset sources, promote reviewed series, update catalog/ledger/registry and build')
    p.add_argument('--offline',action='store_true',help='Use the retained snapshot instead of downloading')
    a=p.parse_args(argv)
    names=list(DATASETS) if a.dataset=='all' else [a.dataset]
    records={}
    for name in names:
        if a.offline and (SNAPSHOTS/f'{name}.json').exists():records[name]=load(SNAPSHOTS/f'{name}.json');continue
        blob=fetch(DATASETS[name]['url']);tabs,readme=tables(name,blob)
        records[name]=snapshot(name,blob,tabs,readme)
        print(f"{name}: vintage {records[name]['vintage']} · {records[name]['row_counts']} · leads {export_leads(name,records[name])}",flush=True)
    registry=load(ROOT/'research/sources.json');ledger=load(ROOT/'site/data/ledger.json');catalog=load(ROOT/'research/catalog.json')
    report=[]
    if 'data-centers' in records and 'gpu-clusters' in records:
        aliases=load(SNAPSHOTS/'aliases.json') if (SNAPSHOTS/'aliases.json').exists() else {}
        result=reconcile(records['data-centers'],records['gpu-clusters'],load(ROOT/'research/delivery.json'),aliases)
        report.append(reconciliation_markdown(result,records['data-centers'],records['gpu-clusters'],ledger))
        save(research.LOCAL/'review-candidates'/f"epoch-reconciliation-{now()[:10]}.json",{'kind':'coverage_expansion','source':DATASETS['data-centers']['source_id'],'created_at':now(),'review_required':True,'result':result})
    if 'companies' in records:
        report.append(revenue_crosscheck(records['companies'],ledger,load(ROOT/'research/ecosystem.json')))
    if report:
        path=SNAPSHOTS/f"RECONCILIATION-{now()[:10]}.md";SNAPSHOTS.mkdir(exist_ok=True);path.write_text('\n'.join(report),encoding='utf-8');print(f'report: {path}',flush=True)
    if a.apply:
        for name in names:
            if register_source(name,registry,ledger):print(f"registered source {DATASETS[name]['source_id']}",flush=True)
            if name in PROMOTED:
                added,recs=promote(name,records[name],catalog,ledger,registry)
                print(f'{name}: metrics added {added}; {len(recs)} quarterly estimate records for vintage {records[name]["vintage"]}',flush=True)
        from source_policy import validate_registry
        validate_registry(registry,{c['id'] for c in load(ROOT/'research/ecosystem.json')['companies']})
        ledger['metrics']=catalog['metrics']
        # validate() reads the reviewed catalog and registry from disk, so write them first and
        # restore the originals if the combined result does not validate.
        originals={p:p.read_bytes() for p in [ROOT/'research/catalog.json',ROOT/'research/sources.json',ROOT/'site/data/source-books.json']}
        save(ROOT/'research/catalog.json',catalog);save(ROOT/'research/sources.json',registry)
        save(ROOT/'site/data/source-books.json',{k:registry[k] for k in ['region_books','collection']})  # public mirror of the reviewed registry
        try:validate(ledger)
        except Exception:
            for p,b in originals.items():p.write_bytes(b)
            raise
        save(ROOT/'site/data/ledger.json',ledger)
        from build import build
        build()
        print('catalog, registry and ledger updated; site rebuilt',flush=True)
    return 0


if __name__=='__main__':sys.exit(main())
