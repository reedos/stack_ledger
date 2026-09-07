"""Validate reviewed component, workforce and clean-energy evidence."""
import json
from pathlib import Path
from validate import require, text, timestamp

ROOT=Path(__file__).resolve().parents[1]

def validate_fabric(f,ledger,eco):
    require(set(f)=={'version','reviewed_at','components','milestones','workforce_metrics','workforce_observations','workforce_notes','energy_cases','gaps'},'Unexpected fabric shape')
    require(f['version']==1,'Unsupported fabric version');timestamp(f['reviewed_at'])
    sources={s['id']:s for s in ledger['sources']};companies={c['id'] for c in eco['companies']}
    metrics={m['id'] for m in ledger['metrics']};observations={o['id']:o for o in ledger['observations']}
    def refs(items,known,label):
        require(isinstance(items,list) and items and len(items)==len(set(items)) and set(items)<=set(known),'Invalid '+label+' references')
    def obs_refs(items):
        refs(items,observations,'observation')
        require(all(not observations[id].get('superseded_by') for id in items),'Superseded fabric observation needs review')
    seen=set()
    for c in f['components']:
        require(set(c)=={'id','title','role','companies','sources','watch'},'Unexpected component shape')
        require(c['id'] not in seen,'Duplicate component ID');seen.add(c['id'])
        for k in ['id','title','role','watch']:text(c[k],700)
        refs(c['companies'],companies,'company');refs(c['sources'],sources,'source')
    for m in f['milestones']:
        require(set(m)=={'title','stage','date','summary','source'},'Unexpected technology milestone')
        require(m['source'] in sources,'Unknown milestone source')
        require(m['date']==sources[m['source']]['published'],'Milestone must preserve source publication date')
        require(m['stage'] in {'Volume production reported','Sampling reported','Acquisition completed','Demonstration announced'},'Unreviewed technology stage')
        for k in ['title','summary']:text(m[k],700)
    refs(f['workforce_metrics'],metrics,'metric');obs_refs(f['workforce_observations'])
    for n in f['workforce_notes']:
        require(set(n)=={'title','summary','source'},'Unexpected workforce note')
        require(n['source'] in sources,'Unknown workforce source')
        text(n['title']);text(n['summary'],700)
    for c in f['energy_cases']:
        require(set(c)=={'name','stage','scope','observations','sources'},'Unexpected energy case')
        for k in ['name','stage','scope']:text(c[k],700)
        require(c['stage'] in {'Production reported','Cell production started; ramp planned','Manufacturing investment plan'},'Unreviewed energy stage')
        refs(c['sources'],sources,'source');obs_refs(c['observations'])
        require(all(observations[id]['source'] in c['sources'] for id in c['observations']),'Energy case source mismatch')
        if c['stage']=='Production reported':
            require(all(observations[id]['status']=='observation' for id in c['observations']),'Production evidence cannot be a plan')
    for gap in f['gaps']:text(gap,700)
    return True

def validate_files():
    read=lambda p:json.loads((ROOT/p).read_text(encoding='utf-8'))
    f=read('research/fabric.json')
    require(f==read('site/data/fabric.json'),'Reviewed fabric changed')
    return validate_fabric(f,read('site/data/ledger.json'),read('research/ecosystem.json'))

if __name__=='__main__':
    validate_files()
    print('Component and workforce validation passed')
