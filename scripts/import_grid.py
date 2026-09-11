"""Maintainer tool for the grid-interface load-forecast trackers (deliverable B, 2026-09-10).
No model calls, no numbers hand-entered.

`research/grid-operators.json` is a reviewed configuration of the grid operators this project
tracks -- PJM, ERCOT, MISO, SPP, plus the national EIA figure -- with, per operator, the
reviewed public source for its load forecast and, where one exists, a machine-readable
endpoint. This task's network scope covers only the Federal Register API and the EIA API v2
(`research/api-access.json`), so none of the four RTOs' own hosts were fetched: every one of
their load forecasts is published as a PDF or a stakeholder slide deck, never a CSV or JSON
export this importer could read, and PJM's one machine-readable planning API (Data Miner 2)
needs a separate registered account outside this task's allowed hosts. Per the owner's scope
for this deliverable, a PDF or spreadsheet number is never hand-entered: this script only
registers each operator's reviewed source (a citation, zero observations) and reports which
operators are "needs_reviewed_import" so the owner can decide the next step for each one.

    python scripts/import_grid.py            # report which operators have a real series and which are waiting
    python scripts/import_grid.py --apply    # register the reviewed operator sources (still zero observations)
"""
import argparse
import sys
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
from research import load, now, require
from validate import text, timestamp

ROOT = Path(__file__).resolve().parents[1]
STATUSES = {'needs_reviewed_import', 'imported'}


def policy(root=ROOT):
    p = load(root/'research/grid-operators.json')
    require(set(p) == {'version', 'reviewed_at', 'owner_decision', 'operators'} and p['version'] == 1, 'Unexpected grid-operators shape')
    timestamp(p['reviewed_at']); text(p['owner_decision'], 2000)
    require(isinstance(p['operators'], list) and p['operators'], 'At least one reviewed operator required')
    seen = set()
    for o in p['operators']:
        required = {'id', 'name', 'source_url', 'source_title', 'machine_endpoint', 'format', 'status', 'note'}
        require(set(o) == required, 'Unexpected operator shape')
        require(o['id'] not in seen, 'Duplicate operator id'); seen.add(o['id'])
        text(o['id'], 40); text(o['name'], 120); text(o['source_title'], 250); text(o['format'], 40); text(o['note'], 1500)
        u = urlparse(o['source_url'])
        require(u.scheme == 'https' and u.hostname and not u.username and not u.password, 'Operator source must be public HTTPS')
        if o['machine_endpoint'] is not None:
            text(o['machine_endpoint'], 200)
        require(o['status'] in STATUSES, 'Unknown operator status')
    return p


def operator_source(o):
    """A citation-only source for an operator's reviewed load-forecast report: zero metrics,
    zero observations, registered so it is linkable and reviewable, never a numeric claim."""
    return {'id': f"grid-operator-{o['id']}", 'publisher': o['name'], 'title': o['source_title'], 'url': o['source_url'],
            'published': None, 'layers': ['energy'], 'license': 'Source material retains its original rights; facts paraphrased with attribution.', 'provenance': 'company-channel'}


def collection_entry():
    return {'rank': 1, 'region_book': 'united-states', 'company_id': None, 'claim_type': 'other',
            'cadence': 'manual', 'weekday': 0, 'path_prefixes': [], 'topics': [], 'excerpts': False}


def run(apply=False):
    p = policy(ROOT)
    registry = load(ROOT/'research/sources.json')
    existing_source_ids = {s['id'] for s in registry['sources']}
    waiting = [o for o in p['operators'] if o['status'] == 'needs_reviewed_import']
    imported = [o for o in p['operators'] if o['status'] == 'imported']
    sources = [operator_source(o) for o in p['operators']]
    new_sources = [s for s in sources if s['id'] not in existing_source_ids]
    collection_entries = {s['id']: collection_entry() for s in new_sources}

    print(f"operators {len(p['operators'])} · with a real series {len(imported)} · waiting on a reviewed import {len(waiting)} "
          f"· sources to register {len(new_sources)}", flush=True)
    for o in waiting:
        print(f"  WAITING {o['id']}: {o['format']} only -- {o['note'][:140]}", flush=True)
    result = {'status': 'ok', 'waiting': [o['id'] for o in waiting], 'imported': [o['id'] for o in imported], 'sources': new_sources}
    if not apply:
        return result
    from importer_common import apply_changes
    apply_changes(ROOT, importer_id='grid', new_sources=new_sources, collection_entries=collection_entries,
                  region_book='united-states', snapshot={'retrieved_at': now()})
    print('registry updated (sources only; no metrics or observations); site rebuilt', flush=True)
    return result


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0]); p.add_argument('--apply', action='store_true')
    a = p.parse_args(argv); run(apply=a.apply); return 0


if __name__ == '__main__': sys.exit(main())
