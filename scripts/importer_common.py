"""Shared apply lane for maintainer importers.

import_qcew.py, import_qwi.py, chip_capacity.py and the tail of import_epoch.py's apply path
all used to duplicate roughly the same block: register a source into the registry, ledger,
collection and region books; add or replace catalog metrics; keep ledger.metrics in sync;
validate new observations and land them; validate the whole ledger with restore-on-failure;
save catalog/registry/source-books; save the ledger; rebuild the site. apply_changes() is
that block, written once.

Idempotent by id: a source already registered, or a metric id not named in
replace_metric_ids, is left untouched rather than duplicated. new_observations upsert by id
(replace an existing record in place, or append a new one), so a later run that lands a
revised Epoch estimate for the same period never produces a duplicate id, and calling
apply_changes twice with identical arguments changes nothing on disk the second time.

Every successful call is also an audit event: a receipt (who ran what, which sources/metrics/
records changed, the snapshot's hashes) is appended to .local/review-candidates/
editorial-events.jsonl as kind 'importer_apply', under the same editorial lock every other
review surface uses, so a direct-lane import is always a recorded, panel-visible action even
though it publishes without a human approving each record (owner decision: credible additions
from named public/CC-BY authorities publish automatically; replacements go through
catalog_review.enqueue for human review).
"""
import getpass
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from research import load, save, now
from validate import validate, observation_valid, event_valid
from source_policy import validate_registry
from editorial_review import append_event, locked

ROOT = Path(__file__).resolve().parents[1]


def _snapshot_sha256s(snapshot):
    """Every string value found under a 'sha256' key anywhere in the snapshot metadata,
    deduped and sorted. Tolerates the different snapshot shapes importers already save
    (a single 'sha256' field, a per-file 'files'/'calls' list, or None)."""
    found = set()
    def walk(value):
        if isinstance(value, dict):
            for k, v in value.items():
                if k == 'sha256' and isinstance(v, str):
                    found.add(v)
                else:
                    walk(v)
        elif isinstance(value, list):
            for item in value:
                walk(item)
    walk(snapshot or {})
    return sorted(found)


def apply_changes(root, *, importer_id, new_sources=(), collection_entries={}, region_book=None,
                   new_metrics=(), replace_metric_ids=(), new_observations=(), new_events=(), snapshot=None):
    """Register sources, add/replace catalog metrics, upsert observations and events, validate
    the whole ledger with restore-on-failure, save, rebuild, and record an 'importer_apply'
    audit event.

    new_sources: source dicts (validate.source_valid shape). Skipped if already registered.
    collection_entries: {source_id: reviewed collection policy dict}, for newly registered sources.
    region_book: the single region book these new sources belong to (all datasets registered by
      one call share a book, matching every importer's current usage).
    new_metrics: metric dicts to add. An id already in the catalog is left untouched unless it
      also appears in replace_metric_ids, in which case it is replaced whole.
    new_observations: observation dicts to land. An id already in the ledger is replaced in
      place (an upsert); a new id is appended. Every one is checked with observation_valid
      against the metrics/sources that result from this same call before it lands.
    new_events: event dicts (validate.event_valid shape) to land the same way -- an id already
      present is replaced in place, a new id is appended, each one checked with event_valid
      against the sources that result from this same call before it lands. Additions only: this
      is for a maintainer importer's own graded events (e.g. an official government publication),
      never a correction of something already published.
    snapshot: the importer's own retained snapshot metadata (whatever shape it already saves),
      used only to fill the receipt's retrieved_at and snapshot_sha256s.

    Returns the receipt dict that was recorded.
    """
    registry = load(root/'research/sources.json')
    ledger = load(root/'site/data/ledger.json')
    catalog = load(root/'research/catalog.json')

    existing_source_ids = {s['id'] for s in registry['sources']}
    sources_touched = []
    for source in new_sources:
        if source['id'] in existing_source_ids:
            continue
        registry['sources'].append(dict(source))
        ledger['sources'].append(dict(source))
        existing_source_ids.add(source['id'])
        sources_touched.append(source['id'])
        entry = collection_entries.get(source['id'])
        if entry is not None:
            registry['collection'][source['id']] = dict(entry)
        if region_book is not None and source['id'] not in registry['region_books'][region_book]['sources']:
            registry['region_books'][region_book]['sources'].append(source['id'])

    catalog_index = {m['id']: i for i, m in enumerate(catalog['metrics'])}
    metrics_added = []
    metrics_replaced = []
    for m in new_metrics:
        if m['id'] in catalog_index:
            if m['id'] in replace_metric_ids:
                catalog['metrics'][catalog_index[m['id']]] = m
                metrics_replaced.append(m['id'])
        else:
            catalog['metrics'].append(m)
            catalog_index[m['id']] = len(catalog['metrics'])-1
            metrics_added.append(m['id'])
    ledger['metrics'] = catalog['metrics']

    metrics_by_id = {m['id']: m for m in ledger['metrics']}
    sources_by_id = {s['id']: s for s in ledger['sources']}
    obs_index = {o['id']: i for i, o in enumerate(ledger['observations'])}
    records_added = []
    for o in new_observations:
        observation_valid(o, metrics_by_id, sources_by_id)
        if o['id'] in obs_index:
            ledger['observations'][obs_index[o['id']]] = o
        else:
            obs_index[o['id']] = len(ledger['observations'])
            ledger['observations'].append(o)
            records_added.append(o['id'])

    event_index = {e['id']: i for i, e in enumerate(ledger['events'])}
    events_added = []
    for e in new_events:
        event_valid(e, sources_by_id)
        if e['id'] in event_index:
            ledger['events'][event_index[e['id']]] = e
        else:
            event_index[e['id']] = len(ledger['events'])
            ledger['events'].append(e)
            events_added.append(e['id'])

    validate_registry(registry, {c['id'] for c in load(root/'research/ecosystem.json')['companies']})

    originals = {p: p.read_bytes() for p in [root/'research/catalog.json', root/'research/sources.json', root/'site/data/source-books.json']}
    save(root/'research/catalog.json', catalog)
    save(root/'research/sources.json', registry)
    save(root/'site/data/source-books.json', {k: registry[k] for k in ['region_books', 'collection']})
    try:
        validate(ledger)
    except Exception:
        for p, b in originals.items():
            p.write_bytes(b)
        raise
    save(root/'site/data/ledger.json', ledger)

    from build import build
    build()

    at = now()
    receipt = {'importer_id': importer_id, 'retrieved_at': (snapshot or {}).get('retrieved_at', at),
               'sources_touched': sources_touched, 'metrics_added': metrics_added, 'metrics_replaced': metrics_replaced,
               'records_added': records_added, 'events_added': events_added, 'snapshot_sha256s': _snapshot_sha256s(snapshot),
               'account': getpass.getuser().lower(), 'channel': 'importer', 'at': at}
    event_id = 'importer-'+hashlib.sha256((importer_id+at).encode('utf-8')).hexdigest()[:24]
    with locked(root):
        append_event(root, dict(receipt, id=event_id, kind='importer_apply'))
    return receipt
