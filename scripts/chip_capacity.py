"""Maintainer tool for chip-project capacity quantification. No model calls.

Chips-layer project cards show "Not quantified" for every fab, packaging site and HBM
plant. This tool turns research/chip-capacity.json (a reviewed configuration: measurement
classes, a reference die and one entry per configured project) into one capacity metric
per configured project, id "{project}-capacity", so the site can show what would quantify
each project's output and which registered sources are being watched for a disclosure.
It never invents a figure: metrics are created with zero observations; the daily research
runner attaches observations independently once a disclosure is found.

    python scripts/chip_capacity.py            # report what would change
    python scripts/chip_capacity.py --apply    # register source, create/update metrics, rebuild
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parent))
import research
from research import load, save, require
from validate import validate

ROOT=Path(__file__).resolve().parents[1]
CONFIG_PATH=ROOT/'research/chip-capacity.json'
MIRROR_PATH=ROOT/'site/data/chip-capacity.json'

WHITEPAPER_SOURCE_ID='nvidia-hopper-whitepaper'
WHITEPAPER_SOURCE={'id':WHITEPAPER_SOURCE_ID,'publisher':'NVIDIA','title':'NVIDIA H100 Tensor Core GPU Architecture whitepaper','url':'https://resources.nvidia.com/en-us-tensor-core/gtc22-whitepaper-hopper','published':'2022-03-22','layers':['chips'],'license':'NVIDIA publication; cited for the GH100 die area'}

ALLOWED_STATUSES=['observation','estimate','company-commitment']
PRE_PERIOD_NOTE='Starts at the earliest reviewed disclosure or measurement period. No pre-project history is inferred; commitments are not operating capacity.'


def metric_for(project_id,entry,cls,project):
    """One catalog metric for a configured project. Follows the terafab-announced-capital shape."""
    return {'id':f'{project_id}-capacity','layer':'chips','title':entry['title'],'unit':cls['unit'],'geography':project['location'],
            'scope':entry['scope'],'direction':'context','min':0,'max':1_000_000,'note':entry['scope'],'source_ids':entry['source_ids'],
            'company':entry['company'],'measurement_type':cls['measurement_type'],'project':project_id,'allowed_statuses':list(ALLOWED_STATUSES),
            'series_start_year':2020,'chart_default_start':2024,'chart_default_end':2030,'definition_stable':True,'pre_period_note':PRE_PERIOD_NOTE}


def build_metrics(config,delivery,ecosystem,registry):
    """Every configured project's metric, or a clear error naming what is not reviewed."""
    projects={p['id']:p for p in delivery['projects']}
    companies={c['id'] for c in ecosystem['companies']}
    source_ids={s['id'] for s in registry['sources']}|{WHITEPAPER_SOURCE_ID}
    metrics=[]
    for project_id,entry in config['projects'].items():
        require(project_id in projects,f'Configured project {project_id} is not in delivery.json')
        require(projects[project_id]['layer']=='chips',f'Configured project {project_id} is not a chips project')
        require(entry['class'] in config['classes'],f'Configured project {project_id} has an unreviewed class')
        require(entry['source_ids'] and set(entry['source_ids'])<=source_ids,f'Configured project {project_id} cites an unregistered source')
        require(entry['company'] is None or entry['company'] in companies,f'Configured project {project_id} has an unreviewed company')
        cls=config['classes'][entry['class']]
        metrics.append(metric_for(project_id,entry,cls,projects[project_id]))
    return metrics


def run(apply=False):
    config=load(CONFIG_PATH)
    delivery=load(ROOT/'research/delivery.json')
    ecosystem=load(ROOT/'research/ecosystem.json')
    registry=load(ROOT/'research/sources.json')
    metrics=build_metrics(config,delivery,ecosystem,registry)
    catalog=load(ROOT/'research/catalog.json')
    index={m['id']:i for i,m in enumerate(catalog['metrics'])}
    new_metrics=[m for m in metrics if m['id'] not in index]
    changed_metrics=[m for m in metrics if m['id'] in index and catalog['metrics'][index[m['id']]]!=m]
    mirror_current=MIRROR_PATH.exists() and load(MIRROR_PATH)==config
    source_missing=WHITEPAPER_SOURCE_ID not in {s['id'] for s in registry['sources']}
    print(f"configured projects {len(config['projects'])} · metrics {len(metrics)} ({len(new_metrics)} new, {len(changed_metrics)} changed) · whitepaper source {'missing' if source_missing else 'registered'} · mirror {'stale' if not mirror_current else 'current'}",flush=True)
    if not apply:return {'metrics':new_metrics,'changed':changed_metrics}
    ledger=load(ROOT/'site/data/ledger.json')
    if source_missing:
        registry['sources'].append(dict(WHITEPAPER_SOURCE));ledger['sources'].append(dict(WHITEPAPER_SOURCE))
        registry['collection'][WHITEPAPER_SOURCE_ID]={'rank':2,'region_book':'global','company_id':'nvidia','claim_type':'other','cadence':'manual','weekday':0,'path_prefixes':[],'topics':[],'excerpts':False}
        registry['region_books']['global']['sources'].append(WHITEPAPER_SOURCE_ID)
    for m in changed_metrics:catalog['metrics'][index[m['id']]]=m
    catalog['metrics']+=new_metrics
    ledger['metrics']=catalog['metrics']
    from source_policy import validate_registry
    validate_registry(registry,{c['id'] for c in ecosystem['companies']})
    originals={p:p.read_bytes() for p in [ROOT/'research/catalog.json',ROOT/'research/sources.json',ROOT/'site/data/source-books.json'] if p.exists()}
    mirror_existed=MIRROR_PATH.exists();mirror_original=MIRROR_PATH.read_bytes() if mirror_existed else None
    save(ROOT/'research/catalog.json',catalog);save(ROOT/'research/sources.json',registry)
    save(ROOT/'site/data/source-books.json',{k:registry[k] for k in ['region_books','collection']})
    save(MIRROR_PATH,config)
    try:validate(ledger)
    except Exception:
        for p,b in originals.items():p.write_bytes(b)
        if mirror_existed:MIRROR_PATH.write_bytes(mirror_original)
        else:MIRROR_PATH.unlink(missing_ok=True)
        raise
    save(ROOT/'site/data/ledger.json',ledger)
    from build import build
    build();print('chip capacity metrics registered; site rebuilt',flush=True)
    return {'metrics':new_metrics,'changed':changed_metrics}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__.splitlines()[0]);p.add_argument('--apply',action='store_true')
    a=p.parse_args(argv);run(apply=a.apply);return 0


if __name__=='__main__':sys.exit(main())
