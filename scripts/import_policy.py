"""Maintainer importer for U.S. government policy action on the grid interface, via the
Federal Register API (public domain, keyless). No model calls.

Deliverable C of the grid-interface tracking work (owner-approved 2026-09-10): PJM telling
data centres to bring power or face cuts, DOE's Eddystone retention and transmission-corridor
retreat, a federal board halting a Nevada project, BIS export controls on advanced computing --
these are official government actions the site tracked almost none of. This importer searches
`research/policy-topics.json`'s reviewed query set against the Federal Register API's keyless
`documents.json` route, filtered to the last `lookback_days` (120) and to the reviewed agency
list (DOE, FERC, BIS, EPA), and turns each matching document into a **grade A event** (an
official government publication) of kind `Government action` -- never a numeric record: a
quantity named inside a rule is a research question for the model, not an import.

Each document gets its own registered source (own URL, title, publication date, agency
publisher) at collection rank 1, so `source_policy.grade_for` derives grade A deterministically
and the site's "read source" link goes to the actual document, not a generic search page.
Candidates are deduplicated on `document_number` (a document matching more than one reviewed
query keeps the first query's layer), sorted newest-first, and capped at
`max_documents_per_run` (20) per run. A vintage snapshot lands under `research/policy/`.

This is additions only, applied through the same shared `importer_common.apply_changes()` lane
every other maintainer importer uses (never `catalog_review`/`publication_policy`, which commits
and pushes -- out of scope for this importer). See `research/publication-policy.json` and
`tests/test_publication_policy.py` for the separate, tested confirmation that a package shaped
like this importer's own additions would also be admitted under that policy's `eligible()` rule,
for a future maintainer tool that chooses that lane instead.

www.federalregister.gov/robots.txt allows `/api/`; checked 2026-09-10 (`Disallow: /documents/
search` etc. name only the HTML site, not the API host's JSON routes).

    python scripts/import_policy.py            # fetch, snapshot, report what would change
    python scripts/import_policy.py --apply    # register sources, add events, rebuild
"""
import argparse
import hashlib
import json
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, build_opener, ProxyHandler

sys.path.insert(0, str(Path(__file__).resolve().parent))
import research
from research import load, save, now, require, UA, allowed_url
from validate import text, timestamp, LAYERS

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOTS = ROOT/'research/policy'
API_BASE = 'https://www.federalregister.gov/api/v1/documents.json'
FIELDS = ['document_number', 'title', 'publication_date', 'agencies', 'html_url', 'docket_ids', 'type', 'abstract']
MAX_BYTES = 5_000_000
CONTROL_OR_MARKUP_RE = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f<>]')


def policy(root=ROOT):
    p = json.loads((root/'research/policy-topics.json').read_text(encoding='utf-8'))
    required = {'version', 'reviewed_at', 'owner_decision', 'api_base', 'lookback_days', 'max_documents_per_run', 'agencies', 'queries', 'anchors'}
    require(set(p) == required and p['version'] == 1, 'Unexpected policy-topics shape')
    timestamp(p['reviewed_at']); text(p['owner_decision'], 1200)
    require(p['api_base'] == API_BASE, 'Reviewed Federal Register API base changed')
    require(isinstance(p['lookback_days'], int) and 1 <= p['lookback_days'] <= 365, 'Invalid lookback window')
    require(isinstance(p['max_documents_per_run'], int) and 1 <= p['max_documents_per_run'] <= 100, 'Invalid document cap')
    require(isinstance(p['agencies'], list) and p['agencies'], 'At least one reviewed agency required')
    for a in p['agencies']:
        require(set(a) == {'slug', 'publisher'}, 'Unexpected agency shape')
        text(a['slug'], 100); text(a['publisher'], 200)
    require(isinstance(p['queries'], list) and p['queries'], 'At least one reviewed query required')
    seen_ids = set()
    for q in p['queries']:
        require(set(q) == {'id', 'term', 'layer', 'note'}, 'Unexpected query shape')
        require(q['id'] not in seen_ids, 'Duplicate query id'); seen_ids.add(q['id'])
        text(q['id'], 80); text(q['term'], 200); text(q['note'], 500)
        require(q['layer'] in LAYERS, 'Invalid query layer')
    return p


def since_date(lookback_days, today=None):
    today = today or datetime.now(timezone.utc).date()
    return (today - timedelta(days=lookback_days)).isoformat()



# The abstract is the document's own summary and rarely exceeds a few thousand characters; the
# UAE export rule names 'advanced computing items' only in its last sentence, so read all of it.
ANCHOR_LIMIT = 4000


def mentions(text_value, anchors):
    """An anchor phrase appears as whole words in the document's own words."""
    words = ' '.join(re.split(r'[^a-z0-9]+', (text_value or '').lower())).strip()
    for anchor in anchors or []:
        parts = [w for w in re.split(r'[^a-z0-9]+', str(anchor).lower()) if w]
        if not parts:
            continue
        # A trailing plural is the same phrase: "data centers" matches the anchor "data center".
        pattern = r'(?:^| )'+re.escape(' '.join(parts[:-1])+' ' if parts[:-1] else '')+re.escape(parts[-1])+r's?(?: |$)'
        if re.search(pattern, words):
            return True
    return False


def on_topic(doc, anchors):
    """Publish only a document whose own title or abstract is about the buildout.

    The Federal Register's `conditions[term]` searches full text, so a query for "data center"
    electricity also returned a Wyoming regional-haze plan, an Alaska hydro preliminary permit and
    three "Combined Notice of Filings" digests (checked 2026-09-10). Those are real matches deep in a
    document and useless to a reader as an event, so they stay private leads instead.
    """
    if not anchors:
        return True   # no reviewed anchors configured: nothing to filter on
    return mentions(doc.get('title'), anchors) or mentions((doc.get('abstract') or '')[:ANCHOR_LIMIT], anchors)

def documents_url(term, agency_slugs, since, per_page=20):
    parts = [f'conditions[term]={quote(term, safe="")}']
    for slug in agency_slugs:
        parts.append(f'conditions[agencies][]={slug}')
    parts += [f'conditions[publication_date][gte]={since}', f'per_page={per_page}', 'order=newest']
    parts += [f'fields[]={field}' for field in FIELDS]
    return API_BASE + '?' + '&'.join(parts)


def fetch(fetcher, url):
    """Robots-checked public JSON download with the project agent string; not a listed
    api-access.json host (the Federal Register API is keyless and robots-permitting, the same
    lane import_btos.py uses for Census's public JSON files)."""
    host = fetcher.check_robots(url)
    allowed_url(url, host)
    with build_opener(ProxyHandler({})).open(Request(url, headers={'User-Agent': UA}), timeout=60) as response:
        body = response.read(MAX_BYTES + 1)
    require(len(body) <= MAX_BYTES, 'Federal Register response exceeds size cap')
    return body


def parse(body):
    payload = json.loads(body.decode('utf-8'))
    require(isinstance(payload, dict) and isinstance(payload.get('results'), list), 'Unexpected Federal Register API response shape')
    return payload['results']


def sanitize(value, max_len):
    """Plain, single-line text safe for validate.text(): no control/markup characters, collapsed
    whitespace, truncated to at most max_len with a trailing ellipsis when cut."""
    cleaned = re.sub(r'\s+', ' ', CONTROL_OR_MARKUP_RE.sub('', str(value or ''))).strip()
    if len(cleaned) <= max_len:
        return cleaned or 'Untitled'
    return cleaned[:max_len - 1].rstrip() + '…'


def publisher_for(doc, publisher_by_slug, fallback):
    for a in doc.get('agencies') or []:
        p = publisher_by_slug.get(a.get('slug'))
        if p:
            return p
    agencies = doc.get('agencies') or []
    return (agencies[0].get('name') if agencies else None) or fallback


def document_source(doc, layer, publisher):
    return {'id': f"federal-register-{doc['document_number'].lower()}", 'publisher': sanitize(publisher, 250),
            'title': sanitize(doc.get('title'), 250), 'url': doc['html_url'], 'published': doc['publication_date'],
            'layers': [layer], 'license': 'Public domain (U.S. government work)'}


def document_event(doc, layer, publisher, source_id):
    agencies = ', '.join(sanitize(a.get('name') or a.get('raw_name'), 80) for a in (doc.get('agencies') or [])[:4]) or publisher
    dockets = '; '.join(sanitize(d, 60) for d in (doc.get('docket_ids') or [])[:4]) or 'none listed'
    doc_type = sanitize(doc.get('type'), 40)
    summary = sanitize(f"{doc_type} from {agencies}. Docket {dockets}. Published in the Federal Register {doc['publication_date']}. {doc['html_url']}", 600)
    return {'id': f"policy-{doc['document_number'].lower()}", 'layer': layer, 'date': doc['publication_date'],
            'title': sanitize(doc.get('title'), 140), 'summary': summary, 'source': source_id,
            'kind': 'Government action', 'grade': 'A'}


def select_documents(query_results, max_documents, anchors=()):
    """({document_number: (doc, layer)}, published, leads). A document matching more than one
    reviewed query keeps the FIRST query's layer. Only a document whose own title or abstract is
    about the buildout is published; the rest are returned as private leads."""
    candidates = {}
    for layer, results in query_results:
        for doc in results:
            number = doc.get('document_number')
            if not number or number in candidates:
                continue
            candidates[number] = (doc, layer)
    ordered = sorted(candidates.items(), key=lambda kv: (kv[1][0].get('publication_date') or '', kv[0]), reverse=True)
    published = [(n, v) for n, v in ordered if on_topic(v[0], anchors)]
    leads = [{'document_number': n, 'title': v[0].get('title'), 'url': v[0].get('html_url'),
              'publication_date': v[0].get('publication_date'), 'layer': v[1],
              'reason': 'full-text match only: no reviewed anchor phrase in the title or abstract'}
             for n, v in ordered if not on_topic(v[0], anchors)]
    return candidates, published[:max_documents], leads


def run(apply=False, today=None):
    p = policy(ROOT)
    since = since_date(p['lookback_days'], today)
    agency_slugs = [a['slug'] for a in p['agencies']]
    publisher_by_slug = {a['slug']: a['publisher'] for a in p['agencies']}
    retrieved = now()
    private = research.LOCAL/'policy'; private.mkdir(parents=True, exist_ok=True)
    fetcher = research.Fetcher()
    calls = []
    query_results = []
    for i, q in enumerate(p['queries']):
        url = documents_url(q['term'], agency_slugs, since)
        try:
            body = fetch(fetcher, url)
        except Exception as e:
            calls.append({'query': q['id'], 'status': type(e).__name__}); continue
        sha = hashlib.sha256(body).hexdigest()
        (private/f"{q['id']}-{sha[:12]}.json").write_bytes(body)
        try:
            results = parse(body)
        except ValueError:
            calls.append({'query': q['id'], 'status': 'unparseable'}); continue
        calls.append({'query': q['id'], 'status': 'ok', 'sha256': sha, 'results': len(results)})
        query_results.append((q['layer'], results))
        if i < len(p['queries']) - 1:
            time.sleep(1)   # one request per second per host

    candidates, chosen, leads = select_documents(query_results, p['max_documents_per_run'], p['anchors'])
    # A full-text-only match is retained privately: real, but not something a reader would
    # recognise as an event about the buildout.
    save(research.LOCAL/'policy-leads'/f'leads-{retrieved[:10]}.json', {'retrieved_at': retrieved, 'leads': leads})

    registry = load(ROOT/'research/sources.json')
    existing_source_ids = {s['id'] for s in registry['sources']}
    new_sources = []
    new_events = []
    collection_entries = {}
    report_rows = []
    for number, (doc, layer) in chosen:
        publisher = publisher_for(doc, publisher_by_slug, 'Federal Register')
        source = document_source(doc, layer, publisher)
        new_sources.append(source)
        new_events.append(document_event(doc, layer, publisher, source['id']))
        collection_entries[source['id']] = {'rank': 1, 'region_book': 'united-states', 'company_id': None,
                                             'claim_type': 'other', 'cadence': 'manual', 'weekday': 0,
                                             'path_prefixes': [], 'topics': [], 'excerpts': False}
        report_rows.append({'document_number': number, 'title': doc.get('title'), 'layer': layer,
                             'publication_date': doc.get('publication_date'), 'agency': publisher, 'url': doc.get('html_url')})
    new_count = sum(1 for s in new_sources if s['id'] not in existing_source_ids)

    SNAPSHOTS.mkdir(exist_ok=True)
    snapshot = {'dataset': 'Federal Register API documents', 'source': 'federal-register-api', 'retrieved_at': retrieved,
                'since': since, 'calls': calls, 'candidates_matched': len(candidates), 'documents_selected': len(chosen),
                'document_numbers': [n for n, _ in chosen], 'license': 'Public domain (U.S. government work)'}
    save(SNAPSHOTS/'policy.json', snapshot)

    ok = sum(1 for c in calls if c['status'] == 'ok')
    print(f"api calls ok {ok}/{len(calls)} · candidates matched {len(candidates)} · documents selected {len(chosen)} "
          f"({new_count} new sources) · lookback since {since}", flush=True)
    result = {'status': 'ok', 'sources': new_sources, 'events': new_events, 'calls': calls,
              'candidates_matched': len(candidates), 'rows': report_rows}
    if not apply:
        return result
    from importer_common import apply_changes
    apply_changes(ROOT, importer_id='policy', new_sources=new_sources, collection_entries=collection_entries,
                  region_book='united-states', new_events=new_events, snapshot=snapshot)
    print('catalog, registry and ledger updated; site rebuilt', flush=True)
    return result


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0]); p.add_argument('--apply', action='store_true')
    a = p.parse_args(argv); run(apply=a.apply); return 0


if __name__ == '__main__': sys.exit(main())
