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
import copy
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
    'chip-sales':{'url':'https://epoch.ai/data/ai_chip_sales.zip','page':'https://epoch.ai/data/ai-chip-sales','source_id':'epoch-chip-sales-dataset','title':'AI Chip Sales dataset','layers':['chips']},
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
    'chip-sales':[
        {'metric':'epoch-nvidia-ai-chips-cumulative','file':'cumulative_timelines_by_designer.csv','column':'Number of units','end_date':'End date','filter':{'Chip manufacturer':'Nvidia'},'unit':'accelerators (cumulative)','title':'Nvidia AI accelerators shipped, cumulative (Epoch estimate)','measurement_type':'estimated_cumulative_ai_chips','scope':'Epoch AI median estimate of cumulative Nvidia data-center AI accelerators shipped since Q1 2022, all chip types. 5th to 95th percentile in each note. An estimate built from disclosed revenue and supply chains, not a shipment count disclosed by Nvidia.','max':1_000_000_000,'company':'nvidia'},
        {'metric':'epoch-amd-ai-chips-cumulative','file':'cumulative_timelines_by_designer.csv','column':'Number of units','end_date':'End date','filter':{'Chip manufacturer':'AMD'},'unit':'accelerators (cumulative)','title':'AMD AI accelerators shipped, cumulative (Epoch estimate)','measurement_type':'estimated_cumulative_ai_chips','scope':'Epoch AI median estimate of cumulative AMD data-center AI accelerators shipped since Q1 2024. 5th to 95th percentile in each note. An estimate, not an AMD disclosure.','max':1_000_000_000,'company':'amd'},
        {'metric':'epoch-nvidia-ai-compute-cumulative','file':'cumulative_timelines_by_designer.csv','column':'Compute estimate in H100e','end_date':'End date','filter':{'Chip manufacturer':'Nvidia'},'unit':'H100 equivalents (cumulative)','title':'Nvidia AI compute shipped, cumulative (Epoch estimate)','measurement_type':'estimated_cumulative_ai_compute_h100e','scope':'Epoch AI median estimate of cumulative Nvidia AI accelerator compute shipped, in H100 equivalents using the Epoch conversion. 5th to 95th percentile in each note.','max':1_000_000_000,'company':'nvidia'},
        {'metric':'epoch-nvidia-ai-chips-cumulative-yearly','file':'cumulative_timelines_by_designer.csv','column':'Number of units','end_date':'End date','yearly_latest':True,'filter':{'Chip manufacturer':'Nvidia'},'unit':'accelerators (cumulative)','title':'Nvidia AI accelerators shipped, cumulative (Epoch estimate, year-end or latest quarter)','measurement_type':'estimated_cumulative_ai_chips','scope':'Epoch AI median estimate of cumulative Nvidia data-center AI accelerators shipped since Q1 2022, one point per year: the latest complete quarter of that year. The current year is cumulative through its latest complete quarter. 5th to 95th percentile in each note. Estimate, not an Nvidia disclosure.','max':1_000_000_000,'company':'nvidia'},
        {'metric':'epoch-amd-ai-chips-cumulative-yearly','file':'cumulative_timelines_by_designer.csv','column':'Number of units','end_date':'End date','yearly_latest':True,'filter':{'Chip manufacturer':'AMD'},'unit':'accelerators (cumulative)','title':'AMD AI accelerators shipped, cumulative (Epoch estimate, year-end or latest quarter)','measurement_type':'estimated_cumulative_ai_chips','scope':'Epoch AI median estimate of cumulative AMD data-center AI accelerators shipped since Q1 2024, one point per year: the latest complete quarter of that year. 5th to 95th percentile in each note. Estimate, not an AMD disclosure.','max':1_000_000_000,'company':'amd'},
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


def metric_definition(spec,source_id,vintage,start_year=2024):
    return {'id':spec['metric'],'layer':'chips','title':spec['title'],'unit':spec['unit'],'geography':'Global','scope':spec['scope'],'direction':'context','min':0,'max':spec['max'],
            'note':f"Epoch AI estimates, {LICENSE}. Median plotted; 5th to 95th percentile in each record note. Dataset vintage {vintage}; a new vintage replaces the series through reviewed import, never by appending competing values.",
            'source_ids':[source_id],'company':spec.get('company'),'measurement_type':spec['measurement_type'],'project':None,'allowed_statuses':['estimate'],**({} if spec.get('yearly_latest') else {'period_basis':'quarter'}),
            'series_start_year':start_year,'chart_default_start':start_year,'chart_default_end':2027,'definition_stable':True,
            'pre_period_note':f'Epoch series begins Q1 {start_year}. Earlier quarters are not estimated. Missing quarters are not zero.'}


def promote(name,record,catalog,ledger,registry):
    """Add or refresh promoted metrics and their quarterly estimate records for this vintage."""
    spec_list=PROMOTED.get(name,[]);source_id=DATASETS[name]['source_id']
    added_metrics=[];records=[]
    metrics={m['id']:m for m in catalog['metrics']}
    for spec in spec_list:
        rows=record['tables'][spec['file']]
        years=[int(r[spec['end_date']][:4]) if spec.get('end_date') else quarter_period(r['Quarter'])[1] for r in rows if all(r.get(k)==v for k,v in spec.get('filter',{}).items()) and (r.get('Incomplete') or '').strip().lower()!='true']
        definition=metric_definition(spec,source_id,record['vintage'],min(years) if years else 2024)
        if spec['metric'] in metrics:
            # Importer-owned definitions are replaced whole; the reviewed spec lives in PROMOTED.
            metrics[spec['metric']].clear();metrics[spec['metric']].update(definition)
        else:
            catalog['metrics'].append(definition);metrics[spec['metric']]=definition;added_metrics.append(spec['metric'])
        for row in rows:
            if any(row.get(k)!=v for k,v in spec.get('filter',{}).items()):continue
            if spec.get('end_date'):
                if (row.get('Incomplete') or '').strip().lower()=='true':continue   # partial quarter: wait for the complete estimate
                end=row[spec['end_date']];period,year=f"{end[:4]}-Q{(int(end[5:7])-1)//3+1}",int(end[:4])
            else:period,year=quarter_period(row['Quarter'])
            med=number(row.get(f"{spec['column']} (median)"));lo=number(row.get(f"{spec['column']} (5th percentile)"));hi=number(row.get(f"{spec['column']} (95th percentile)"))
            if med is None:continue
            record_id=f"{spec['metric']}-{year}" if spec.get('yearly_latest') else f"{spec['metric']}-{period.lower()}"
            if spec.get('yearly_latest'):
                # Periods the editorial parser understands: a complete year as "Year-end YYYY", a partial year by its quarter-end date.
                end=row[spec['end_date']];period=f'Year-end {year}' if period.endswith('Q4') else f"{datetime(int(end[:4]),int(end[5:7]),int(end[8:10])).strftime('%B')} {int(end[8:10])}, {year}"
            records.append({'_end':row.get(spec.get('end_date',''),period) if spec.get('end_date') else period,'id':record_id,'metric':spec['metric'],'year':year,'period':period,'value':round(med,2),'upper':None,'status':'estimate','source':source_id,'precision':'approx','retrieved_at':record['retrieved_at'],'method':'curated',
                            'note':f"Epoch AI median estimate; 5th to 95th percentile {lo:,.0f} to {hi:,.0f}. Dataset vintage {record['vintage']}, sha256 {record['sha256'][:12]}. {LICENSE}."[:300]})
    # Yearly variants keep one record per metric and year: the latest complete quarter.
    latest={}
    for r in records:
        spec=next(x for x in spec_list if x['metric']==r['metric'])
        if spec.get('yearly_latest'):
            k=(r['metric'],r['year'])
            if k not in latest or r['_end']>latest[k]['_end']:latest[k]=r   # latest complete quarter by end date, not by label
    records=[r for r in records if not next(x for x in spec_list if x['metric']==r['metric']).get('yearly_latest')]+list(latest.values())
    for r in records:r.pop('_end',None)
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


def owner_label(raw):
    """'Microsoft #confident, OpenAI #likely' -> 'Microsoft, OpenAI'; blank -> 'Undisclosed'."""
    parts=[re.sub(r'\s*#\w+','',x).strip() for x in (raw or '').split(',')]
    return ', '.join(p for p in parts if p) or 'Undisclosed'


def company_links(*labels,companies):
    """Directory company ids whose name shares a distinctive token with the Epoch owner or user labels."""
    want=set()
    for label in labels:want|=tokens(owner_label(label))
    ids=[]
    for c in companies:
        if tokens(c['name'])&want:ids.append(c['id'])
    return sorted(set(ids))


def slug(text):return re.sub(r'-+','-',re.sub(r'[^a-z0-9]+','-',text.lower())).strip('-')[:80]


def draft_project(row,record,companies):
    """A status-unverified project drafted from one Epoch data-center row. Estimates stay in prose."""
    source_id=DATASETS['data-centers']['source_id'];vintage=record['vintage']
    mw=number(row.get('Current power (MW)'));h=number(row.get('Current H100 equivalents'));capex=number(row.get('Current total capital cost (2025 USD billions)'))
    owner=owner_label(row.get('Owner'));users=owner_label(row.get('Users')) if row.get('Users') else None
    location=', '.join(x for x in [row.get('Address','').strip(),row.get('Country','').strip()] if x) or row.get('Country','') or 'Location not stated'
    facts=' · '.join(x for x in [f'current power about {mw:g} MW' if mw else None,f'about {h:,.0f} H100 equivalents' if h else None,f'capital cost about {capex:.1f} billion 2025 USD' if capex else None] if x)
    return {'id':slug(row['Name']),'name':row['Name'],'layer':'infrastructure','owner':owner[:600],'location':location[:600],'category':'AI data center','stage':'status-unverified',
            'ai_relationship':(f"Epoch AI identifies this site as an AI data center from satellite, permit and filing analysis (dataset vintage {vintage}). "+(f"Users named by Epoch: {users}. " if users else '')+"AI-only allocation and the delivery stage are not established by this record.")[:600],
            'observations':[],
            'horizon':f'Epoch estimate as of dataset vintage {vintage}; no completion date is inferred. Seek a dated operator or permitting update.',
            'grid':(f'Epoch estimates {facts}. These are estimates with stated uncertainty, not energized-capacity or grid-connection records.' if facts else 'Power and grid connection are not quantified in this record.')[:600],
            'next_evidence':'Confirm site identity against Epoch\'s cited sources, then verify delivery stage, energized IT load, campus boundaries and local jobs from dated operator, utility or permitting evidence before any stage other than status-unverified.',
            'milestones':[{'date':None,'summary':(f"Epoch AI Data Centers dataset (vintage {vintage}) lists this site: owner {owner}"+(f", users {users}" if users else '')+f", {row.get('Country','')}"+(f"; {facts}" if facts else '')+". Directory presence is not proof of operation.")[:600],'source':source_id}],
            'company_ids':company_links(row.get('Owner'),row.get('Users'),companies=companies)}


def enqueue_additions(root,result,record,min_mw=100,per_package=6):
    """Draft proposed additions as catalog_change packages for the Research Control review panel.

    One package per owner group. Nothing is applied here: the panel's Validate preview, Approve
    and Apply steps remain the only path into the catalog.
    """
    from catalog_review import enqueue
    companies=load(root/'research/ecosystem.json')['companies']
    existing={p['id'] for p in load(root/'research/delivery.json')['projects']}
    rows={r['Name']:r for r in record['tables']['data_centers.csv']}
    chosen=[a for a in result['proposed_additions'] if (a['current_power_mw'] or 0)>=min_mw and slug(a['epoch_name']) not in existing]
    groups={}
    for a in chosen:groups.setdefault(owner_label(a['owner']).split(',')[0],[]).append(a)
    evidence_dir=root/'.local/catalog-evidence';evidence_dir.mkdir(parents=True,exist_ok=True)
    packages=[]
    for owner,items in sorted(groups.items()):
        for i in range(0,len(items),per_package):
            batch=items[i:i+per_package];changes=[];evidence=[]
            for a in batch:
                row=rows[a['epoch_name']];draft=draft_project(row,record,companies)
                body=json.dumps({'dataset':record['title'],'vintage':record['vintage'],'dataset_sha256':record['sha256'],'row':row},ensure_ascii=False,indent=1)
                sha=hashlib.sha256(body.encode('utf-8')).hexdigest();(evidence_dir/(sha+'.txt')).write_bytes(body.encode('utf-8'))
                eid='epoch-dc-'+draft['id']
                evidence.append({'id':eid,'url':record['page'],'published_at':None,'retrieved_at':record['retrieved_at'],'sha256':sha,
                                 'summary':(f"Epoch AI Data Centers row for {a['epoch_name']} (vintage {record['vintage']}, dataset sha256 {record['sha256'][:12]}). Epoch cites: "+'; '.join(a['sources'][:6]))[:2000]})
                changes.append({'target':'project','id':draft['id'],'after':draft,'evidence':[eid]})
            title=f"Epoch data centers: add {len(batch)} {owner} site{'s' if len(batch)>1 else ''} as status-unverified"[:200]
            packages.append(enqueue(root,title,changes,evidence,author='Epoch import (maintainer tool)'))
    return packages


SITE_SERIES=[
    ('it-mw','Current power (MW)','estimated_site_it_mw','MW IT','current IT power (Epoch estimate)',10000,1,'Epoch AI site estimate of current IT power from satellite, permit and filing evidence; not metered consumption. Campus boundary may exceed an individual building.'),
    ('h100e','Current H100 equivalents','estimated_site_h100_equivalents','H100 equivalents','installed compute (Epoch estimate)',100_000_000,0,"Epoch AI estimate of installed accelerator compute expressed in H100 equivalents using Epoch's published conversion; not a chip count disclosed by the operator."),
    ('capex','Current total capital cost (2025 USD billions)','estimated_site_capital_cost_usd_bn','USD billion (2025)','cumulative capital cost (Epoch estimate)',1000,2,'Epoch AI estimate of cumulative capital cost to date in 2025 dollars, compute and construction combined; not recognized capex from a filing.'),
]


def site_records(row,project,record,companies):
    """Per-site estimate metrics and snapshot records for one Epoch row, attached to a project.

    Returns (metrics, observations, updated_project). IT power and compute join the project's
    headline records; capital cost reaches the card's money section through the metric's
    project link. Nothing already attached to the project is touched.
    """
    source_id=DATASETS['data-centers']['source_id'];vintage=record['vintage'];day=record['retrieved_at'][:10];year=int(day[:4])
    owner=owner_label(row.get('Owner'));links=company_links(row.get('Owner'),companies=companies)
    geography=', '.join(x for x in [row.get('Address','').strip(),row.get('Country','').strip()] if x) or row.get('Country','') or 'Location not stated'
    metrics=[];observations=[]
    for key,column,mtype,unit,label,maximum,digits,scope in SITE_SERIES:
        value=number(row.get(column))
        if value is None or value<=0:continue
        mid=f"epoch-{project['id']}-{key}"
        metrics.append({'id':mid,'layer':'infrastructure','title':f"{project['name']} · {label}",'unit':unit,'geography':geography[:700],'scope':scope,'direction':'context','min':0,'max':maximum,
            'note':f"Epoch AI Data Centers dataset, {LICENSE}. Snapshot series: each import records the current estimate on its retrieval date; a new vintage adds a dated point and never rewrites earlier ones.",
            'source_ids':[source_id],'company':links[0] if links else None,'measurement_type':mtype,'project':project['id'],'allowed_statuses':['estimate'],'period_basis':'snapshot',
            'series_start_year':2024,'chart_default_start':2024,'chart_default_end':2027,'definition_stable':True,'pre_period_note':'Epoch site estimates begin with the first imported vintage. Earlier values are not estimated. Missing dates are not zero.'})
        observations.append({'id':f"{mid}-{day}",'metric':mid,'year':year,'period':day,'value':round(value,digits) if digits else round(value),'upper':None,'status':'estimate','source':source_id,'precision':'approx','retrieved_at':record['retrieved_at'],'method':'curated',
            'note':f"Epoch AI estimate for {row['Name']} (owner {owner}), dataset vintage {vintage}, sha256 {record['sha256'][:12]}. {LICENSE}."[:300]})
    updated=copy.deepcopy(project)
    headline=[o['id'] for o in observations if not o['metric'].endswith('-capex')]
    updated['observations']=list(project.get('observations',[]))+[i for i in headline if i not in project.get('observations',[])]
    return metrics,observations,updated


def has_epoch_capacity(project,ledger,catalog):
    metrics={m['id']:m for m in catalog['metrics']}
    if any(m['id'].startswith(f"epoch-{project['id']}-") for m in catalog['metrics']):return True
    obs={o['id']:o for o in ledger['observations']}
    return any(oid in obs and obs[oid]['metric'] in metrics and any(sid.startswith('epoch-') for sid in metrics[obs[oid]['metric']]['source_ids']) for oid in project.get('observations',[]))


def enqueue_capacity(root,result,record,per_package=2):
    """Attach Epoch power, compute and capital-cost estimates to every project that lacks them, as catalog packages."""
    from catalog_review import enqueue
    companies=load(root/'research/ecosystem.json')['companies'];delivery=load(root/'research/delivery.json');ledger=load(root/'site/data/ledger.json');catalog=load(root/'research/catalog.json')
    projects={p['id']:p for p in delivery['projects']};rows={r['Name']:r for r in record['tables']['data_centers.csv']}
    pairs=[]
    for m in result['matched']:
        if m['match'] in projects:pairs.append((m['epoch_name'],projects[m['match']]))
    for a in result['proposed_additions']:
        if slug(a['epoch_name']) in projects:pairs.append((a['epoch_name'],projects[slug(a['epoch_name'])]))
    pairs=[(n,p) for n,p in pairs if not has_epoch_capacity(p,ledger,catalog)]
    groups={}
    for n,p in pairs:groups.setdefault(owner_label(rows[n].get('Owner')).split(',')[0],[]).append((n,p))
    evidence_dir=root/'.local/catalog-evidence';evidence_dir.mkdir(parents=True,exist_ok=True)
    packages=[]
    for owner,items in sorted(groups.items()):
        for i in range(0,len(items),per_package):
            batch=items[i:i+per_package];changes=[];evidence=[]
            for name,project in batch:
                row=rows[name];metrics,observations,updated=site_records(row,project,record,companies)
                if not metrics:continue
                body=json.dumps({'dataset':record['title'],'vintage':record['vintage'],'dataset_sha256':record['sha256'],'row':row},ensure_ascii=False,indent=1)
                sha=hashlib.sha256(body.encode('utf-8')).hexdigest();(evidence_dir/(sha+'.txt')).write_bytes(body.encode('utf-8'))
                eid='epoch-dc-'+slug(name)
                evidence.append({'id':eid,'url':record['page'],'published_at':None,'retrieved_at':record['retrieved_at'],'sha256':sha,'summary':(f"Epoch AI Data Centers row for {name} (vintage {record['vintage']}, dataset sha256 {record['sha256'][:12]}): current power, H100 equivalents and capital cost estimates. Epoch cites: "+'; '.join(markdown_urls(row.get('Selected Sources',''))[:6]))[:2000]})
                for m in metrics:changes.append({'target':'metric','id':m['id'],'after':m,'evidence':[eid]})
                for o in observations:changes.append({'target':'observation','id':o['id'],'after':o,'evidence':[eid]})
                changes.append({'target':'project','id':project['id'],'after':updated,'evidence':[eid]})
            if not changes:continue
            title=f"Epoch estimates: attach power, compute and capital cost to {len(batch)} {owner} site{'s' if len(batch)>1 else ''}"[:200]
            packages.append(enqueue(root,title,changes,evidence,author='Epoch import (maintainer tool)'))
    return packages


def confirm_matches(result,accept_suggested=False,rejects=(),path=None):
    """Record reviewed aliases: Epoch name -> project id, or null for a reviewed non-match."""
    path=path or SNAPSHOTS/'aliases.json'
    aliases=load(path) if path.exists() else {}
    if accept_suggested:
        for m in result['matched']:
            if m['match_basis']=='suggested':aliases[m['epoch_name']]=m['match']
    for name in rejects:aliases[name]=None
    save(path,dict(sorted(aliases.items())))
    return aliases


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('dataset',choices=[*DATASETS,'all']);p.add_argument('--apply',action='store_true',help='Register dataset sources, promote reviewed series, update catalog/ledger/registry and build')
    p.add_argument('--offline',action='store_true',help='Use the retained snapshot instead of downloading')
    p.add_argument('--enqueue-additions',action='store_true',help='Draft proposed data-center additions as catalog packages for the review panel')
    p.add_argument('--enqueue-capacity',action='store_true',help='Attach Epoch power, compute and capital-cost estimate records to matched and imported projects as catalog packages')
    p.add_argument('--min-mw',type=float,default=100,help='Only enqueue Epoch sites at or above this estimated current power')
    p.add_argument('--confirm-suggested-matches',action='store_true',help='Record every suggested site match as a reviewed alias')
    p.add_argument('--reject',action='append',default=[],metavar='EPOCH_NAME',help='Record an Epoch site name as a reviewed non-match')
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
        if a.confirm_suggested_matches or a.reject:
            aliases=confirm_matches(result,a.confirm_suggested_matches,a.reject)
            print(f"aliases recorded: {sum(1 for v in aliases.values() if v)} matches, {sum(1 for v in aliases.values() if v is None)} non-matches -> {SNAPSHOTS/'aliases.json'}",flush=True)
        if a.enqueue_capacity:
            packages=enqueue_capacity(ROOT,result,records['data-centers'])
            print(f"{len(packages)} capacity packages queued: "+'; '.join(f"{q['id']} ({len(q['changes'])})" for q in packages),flush=True)
        if a.enqueue_additions:
            packages=enqueue_additions(ROOT,result,records['data-centers'],a.min_mw)
            print(f"{len(packages)} catalog packages queued for the review panel: "+'; '.join(f"{q['id']} ({len(q['changes'])})" for q in packages),flush=True)
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
