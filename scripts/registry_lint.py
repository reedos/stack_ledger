"""Registry triage report: which sources can publish, which only inform, and which keep failing.

Read-only by default. No network, no model. Registry edits remain reviewed changes.

    python scripts/registry_lint.py                       # print
    python scripts/registry_lint.py --write                # also save .local/evaluations/registry-lint.md
    python scripts/registry_lint.py --retire-dated          # list dated one-off sources (dry run)
    python scripts/registry_lint.py --retire-dated --apply  # set cadence: manual for exactly that list
"""
import argparse
import glob
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0,str(Path(__file__).resolve().parent))
from source_policy import collection_for
from atomic_json import save as atomic_save

ROOT=Path(__file__).resolve().parents[1]
LOCAL=ROOT/'.local'

# Deliverable 5: a dated one-off document -- a report or press release published once and
# never revised in place -- looks like this in its registered id and its URL path. Both
# must match, plus index:false (a feed/index page is never a one-off) and cadence!=manual
# already (nothing to retire twice).
DATED_ID=re.compile(r'-(19|20)\d\d(-|$)|-q[1-4]-|-may-|-\d{8}$')
FIXED_DOCUMENT_PATH=re.compile(r'press-release|news-release|news\.release|/reports?/|\.pdf$|annualreport|/ai-index/|/\d{4}/\d{1,2}/|-\d{2}-\d{2}-\d{4}|\d{8}|/abs/|edgar|/archives/|prospectus|/\d?10-?[kq]/|[^a-z]6-?k[^a-z]',re.IGNORECASE)


def load(path):return json.loads(path.read_text(encoding='utf-8'))


def dated_one_offs(registry):
    """Registered source ids matching every retirement criterion, in registry order.

    Printed for a maintainer to review; --apply is the only thing that ever writes
    cadence: manual, and it changes cadence only -- research/sources.json's other reviewed
    fields (rank, region_book, topics, excerpts, ...) are untouched.
    """
    out=[]
    for s in registry['sources']:
        if s.get('index'):continue
        policy=registry.get('collection',{}).get(s['id'])
        # No registered collection policy at all (an evidence-only citation, never actively
        # fetched) is already outside unattended monitoring; --apply only ever sets an
        # existing policy's cadence, never fabricates one.
        if policy is None or policy.get('cadence')=='manual':continue
        if not DATED_ID.search(s['id']):continue
        if not FIXED_DOCUMENT_PATH.search(urlparse(s['url']).path):continue
        out.append(s['id'])
    return out


def classify(registry,ledger):
    metrics=ledger['metrics'];linked={sid for m in metrics for sid in m['source_ids']}
    rows=[]
    for s in registry['sources']:
        p=collection_for(registry,s)
        rows.append({'id':s['id'],'host':urlparse(s['url']).hostname,'publisher':s['publisher'],'layers':s['layers'],'rank':p.get('rank'),'cadence':p.get('cadence'),
                     'metric_link':s['id'] in linked,'excerpts':bool(p.get('excerpts')),'index':bool(s.get('index')),
                     'route':('metric' if s['id'] in linked else 'public note' if p.get('excerpts') else 'index' if s.get('index') else 'private note only')})
    return rows


def failures():
    """Per-source failure counts from retained run receipts, by sanitized reason."""
    counts=defaultdict(Counter)
    for path in glob.glob(str(LOCAL/'runs'/'*.json')):
        try:d=load(Path(path))
        except (OSError,ValueError):continue
        for f in (d.get('receipt',d)).get('source_failures',[]) or []:
            counts[f.get('source')][(f.get('reason') or '')[:60]]+=1
    return counts


def robots_health():
    path=LOCAL/'collection-health.json'
    if not path.exists():return {}
    return {k:v for k,v in load(path).items() if k.startswith('robots:') and v.get('status')!='available'}


def report(rows,fails,unhealthy):
    routes=Counter(r['route'] for r in rows);manual=[r for r in rows if r['cadence']=='manual']
    lines=['# Registry lint','',f'{len(rows)} registered sources. Routes: '+', '.join(f'{k} {v}' for k,v in routes.most_common())+f'. Manual cadence: {len(manual)}.','',
           'Route meanings: metric = numeric extraction against a catalog metric; public note = excerpt-permitted research notes; index = discovers same-host pages; private note only = read, but any note stays in the private review queue until excerpt permission or a metric mapping is reviewed.','',
           '## Private-note-only sources (candidates for excerpt permission, a metric mapping, or removal)','','| Source | Publisher | Host | Rank | Cadence | Layers |','|---|---|---|---|---|---|']
    lines+=[f"| {r['id']} | {r['publisher']} | {r['host']} | {r['rank']} | {r['cadence']} | {', '.join(r['layers'])} |" for r in rows if r['route']=='private note only']
    hot=sorted(((sid,sum(c.values()),c) for sid,c in fails.items()),key=lambda x:-x[1])[:40]
    lines+=['','## Sources failing most often in retained receipts','','| Source | Failures | Reasons |','|---|---|---|']
    lines+=[f"| {sid} | {n} | {'; '.join(f'{k} ×{v}' for k,v in c.most_common(3))} |" for sid,n,c in hot]
    byhost=Counter()
    ids={r['id']:r['host'] for r in rows}
    for sid,n,_ in hot:byhost[ids.get(sid,'?')]+=n
    lines+=['','## Hosts behind those failures','']+[f'- {h}: {n}' for h,n in byhost.most_common(20)]
    lines+=['','## Robots policies currently unavailable (collection health)','']+([f"- {k.split(':',1)[1][:16]}…: {v.get('http_status') or v.get('type')} (failures {v.get('failures')})" for k,v in unhealthy.items()] or ['- none recorded (health file absent or all available)'])
    return '\n'.join(lines)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--write',action='store_true')
    parser.add_argument('--retire-dated',action='store_true',help='List (or, with --apply, retire) dated one-off document sources')
    parser.add_argument('--apply',action='store_true',help='With --retire-dated: write cadence: manual for exactly the printed list (reviewed, maintainer-run change)')
    args=parser.parse_args(argv)
    if args.retire_dated:
        registry=load(ROOT/'research/sources.json')
        ids=dated_one_offs(registry)
        print(f"{len(ids)} dated one-off source(s) {'retired' if args.apply else 'to retire (dry run; pass --apply to write)'}:")
        for sid in ids:print(f'- {sid}')
        if args.apply:
            for sid in ids:registry['collection'][sid]['cadence']='manual'
            atomic_save(ROOT/'research/sources.json',registry)
            print(f'\nSet cadence: manual for {len(ids)} source(s). Manual sources stay registered as evidence and are never fetched by the runner; no other field changed.')
        return 0
    rows=classify(load(ROOT/'research/sources.json'),load(ROOT/'site/data/ledger.json'))
    md=report(rows,failures(),robots_health());print(md)
    if args.write:
        out=LOCAL/'evaluations';out.mkdir(parents=True,exist_ok=True)
        (out/'registry-lint.md').write_text(md,encoding='utf-8');(out/'registry-lint.json').write_text(json.dumps(rows,indent=1),encoding='utf-8')
    return 0


if __name__=='__main__':sys.exit(main())
