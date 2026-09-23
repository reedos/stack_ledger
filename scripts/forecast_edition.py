"""A new edition of a forecast is a replacement, not a conflict and not an addition.

Grid operators, the IEA and the hyperscalers re-issue their forecasts. Until 09/23/2026 the
monitoring lane compared metric and year only, so a later edition either collided with the
earlier one on a shared year (a 'conflict', quarantined where nobody saw it) or, on the years the
two editions do not share, was published straight into the same chart series: PJM's 2027 report
would have drawn its 2037 and 2047 peaks on one line with the 2026 report's 2036 and 2046. The
same vintage error cost the site Amazon's current guidance on 09/22.

So a forward-looking figure (forecast, company commitment, government target) from a different
document than the one already on the chart is held, never published by the runner:

- 'older': the document is an earlier edition than the one on the site. Quarantined.
- 'new': it is held with every other figure the same document gives for that metric, and turned
  into one catalog package. The owner sees both editions side by side on the review card;
  approving publishes the new figures and retires the old edition's in one reviewed commit.

A metric's reviewed `edition_mode` decides what an edition replaces:

- 'trajectory': the new edition replaces the whole old one, whatever years each covers (rolling
  load forecasts, whose horizon moves every year).
- 'by-year' (the default): only the years the new edition restates are replaced, so 2027
  guidance can sit beside 2026 guidance; a year no incumbent covers publishes as before.

A page that restates its own figures (a weekly consensus page) is the same source, not a new
edition, and keeps the ordinary duplicate/conflict handling.
"""
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlparse

FORWARD = {'forecast', 'company-commitment', 'government-target'}
MODES = {'trajectory', 'by-year'}
AUTHOR = 'Forecast edition (research runner)'
_YEAR = re.compile(r'(?<!\d)(20\d\d)(?!\d)')


def _now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()


def mode(metric):
    return (metric or {}).get('edition_mode', 'by-year')


def edition_year(source):
    """The year an edition was issued: its reviewed publication date, else a year in its file name."""
    if (source or {}).get('published'):
        return int(source['published'][:4])
    name = unquote(urlparse((source or {}).get('url', '')).path).rsplit('/', 1)[-1]
    years = [int(y) for y in _YEAR.findall(name)]
    return max(years) if years else None


def slot(o, metric):
    """What two figures must share to be the same point: the year, or the period where the metric keys on it
    (the same rule as research.duplicate_or_conflict)."""
    return (o['year'], o['period']) if (metric or {}).get('period_basis') in ('month', 'quarter', 'snapshot') else (o['year'],)


def incumbents(metric_id, observations):
    return [o for o in observations if o['metric'] == metric_id and not o.get('superseded_by') and o['status'] in FORWARD]


def classify(record, source, observations, ledger_sources, metric):
    """None (publish or conflict-check as today), 'older' or 'new'."""
    if record['status'] not in FORWARD:
        return None
    current = incumbents(record['metric'], observations)
    if not current:
        return None
    by_id = {s['id']: s for s in ledger_sources}
    theirs = [by_id.get(o['source'], {'id': o['source']}) for o in current]
    if source['id'] in {s['id'] for s in theirs} or source['url'] in {s.get('url') for s in theirs}:
        return None  # the same document restating itself
    new, old = edition_year(source), [y for y in (edition_year(s) for s in theirs) if y]
    if new is not None and old and new < max(old):
        return 'older'
    if mode(metric) == 'trajectory':
        return 'new'
    return 'new' if slot(record, metric) in {slot(o, metric) for o in current} else None


def hold(local, source, full_text, held, metrics, page_of=None):
    """Write one review candidate per metric: .local/review-candidates/edition-<24hex>.json.

    `held` is a list of (candidate, record, verdict). A pending or rejected edition is never
    raised again: the id is a digest of the metric, the source and the figures themselves.
    Returns the ids written.
    """
    folder = Path(local)/'review-candidates'
    folder.mkdir(parents=True, exist_ok=True)
    body = full_text.encode('utf-8')
    sha = hashlib.sha256(body).hexdigest()
    retained = Path(local)/'catalog-evidence'/(sha+'.txt')
    retained.parent.mkdir(parents=True, exist_ok=True)
    if not retained.exists():
        retained.write_bytes(body)
    written = []
    for metric_id in sorted({r['metric'] for _, r, _ in held}):
        rows = [(c, r, v) for c, r, v in held if r['metric'] == metric_id]
        figures = sorted((r['year'], r['period'], r['value'], r['upper'], r['status'], r['precision']) for _, r, _ in rows)
        rid = 'edition-' + _digest([metric_id, source['id'], source['url'], figures])[:24]
        path = folder/(rid+'.json')
        if path.exists():
            continue
        records = []
        for c, r, v in rows:
            # The old edition may hold an identical automated figure under the same id; the
            # source in the identity keeps the two apart.
            identity = json.dumps([r[k] for k in ['metric', 'year', 'period', 'value', 'upper', 'status', 'precision']] + [source['id']], separators=(',', ':'))
            rec = dict(r, id='auto-' + hashlib.sha256(identity.encode('utf-8')).hexdigest()[:20])
            records.append({'record': rec, 'quote': c['evidence'], 'review': v,
                            'pdf_page': page_of(c['evidence']) if page_of else None})
        value = {'id': rid, 'kind': 'forecast_edition', 'status': 'ready', 'created_at': _now(), 'metric': metric_id,
                 'mode': mode(metrics.get(metric_id)), 'source': source, 'document_sha256': sha, 'records': records,
                 'authority': 'Private runner hold. Nothing is published until the owner approves the catalog package.'}
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        written.append(rid)
    return written


def _retain(root, text):
    body = text.encode('utf-8')
    sha = hashlib.sha256(body).hexdigest()
    path = Path(root)/'.local/catalog-evidence'/(sha+'.txt')
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_bytes(body)
    return sha


def _fmt(o):
    value = f"{o['value']}" + (f"–{o['upper']}" if o.get('upper') is not None else '')
    return f"{o['year']} {o['period']}: {value} ({o['status']}, {o['precision']})"


def changes_for(root, item, ledger, registry_ids):
    """The catalog changes and evidence that publish the held edition and retire the old one."""
    metric = next((m for m in ledger['metrics'] if m['id'] == item['metric']), None)
    if metric is None:
        raise ValueError('Held edition names an unknown metric')
    source = item['source']
    new = [row['record'] for row in item['records']]
    old_all = [o for o in incumbents(metric['id'], ledger['observations']) if o['source'] != source['id']]
    restated = {slot(r, metric) for r in new}
    old = old_all if mode(metric) == 'trajectory' else [o for o in old_all if slot(o, metric) in restated]
    latest = max(new, key=lambda r: (r['year'], r['upper'] if r['upper'] is not None else r['value']))
    by_slot = {slot(r, metric): r for r in new}
    assigned = {o['id']: by_slot.get(slot(o, metric), latest)['id'] for o in old}
    sources = {s['id']: s for s in ledger['sources']}
    old_sources = sorted({o['source'] for o in old})
    title = source.get('title') or source['url']
    olds = '; '.join(f"{sources.get(s, {}).get('title', s)} (published {sources.get(s, {}).get('published') or 'undated'})" for s in old_sources)
    reason = f"New edition: {title} (published {source.get('published') or 'undated'}) replaces {olds}."[:500] if old else None

    new_ev = {'id': source['id'], 'url': source['url'], 'published_at': source.get('published'), 'retrieved_at': item['created_at'],
              'sha256': item['document_sha256'],
              'summary': ('New edition. ' + ' | '.join(f"{_fmt(row['record'])}: \"{row['quote'][:220]}\"" + (f" (p. {row['pdf_page']})" if row.get('pdf_page') else '')
                                                    for row in item['records']))[:2000]}
    evidence = [new_ev]
    old_ev = {}
    for sid in old_sources:
        s = sources.get(sid, {'id': sid, 'url': None})
        lines = []
        for o in [o for o in old if o['source'] == sid]:
            proof = Path(root)/'.local/evidence'/(o['id']+'.json')
            try:
                quote = json.loads(proof.read_text(encoding='utf-8')).get('evidence') if proof.exists() else None
            except (OSError, ValueError):
                quote = None
            lines.append(f"{_fmt(o)}: " + (f"\"{quote[:220]}\"" if quote else f"quote not retained; note: {o.get('note', '')[:200]}"))
        body = f"Edition on the site now: {s.get('title', sid)} ({s.get('url')}), published {s.get('published') or 'undated'}.\n" + '\n'.join(lines)
        url = s.get('url')
        if not (isinstance(url, str) and url.startswith('https://')):
            raise ValueError(f'Old edition source {sid} has no public HTTPS URL for evidence')
        eid = 'old-' + sid
        evidence.append({'id': eid[:140], 'url': url, 'published_at': s.get('published'), 'retrieved_at': _now(),
                         'sha256': _retain(root, body), 'summary': ('Edition being replaced. ' + ' | '.join(lines))[:2000]})
        old_ev[sid] = eid[:140]

    changes = []
    if source['id'] not in registry_ids:
        changes.append({'target': 'source', 'id': source['id'], 'after': source, 'evidence': [source['id']]})
    for r in new:
        after = dict(r)
        took = [oid for oid, nid in assigned.items() if nid == r['id']]
        if took:
            after.update(edition_supersedes=sorted(took), correction_reason=reason)
        changes.append({'target': 'observation', 'id': r['id'], 'after': after, 'evidence': [source['id']]})
    for o in old:
        changes.append({'target': 'observation', 'id': o['id'], 'after': dict(o, superseded_by=assigned[o['id']]),
                        'evidence': [old_ev[o['source']], source['id']]})
    period = f"{min(r['year'] for r in new)}–{max(r['year'] for r in new)}" if len(new) > 1 else str(new[0]['year'])
    verb = f"replaces {len(old)} figure{'s' if len(old) != 1 else ''} from the earlier edition" if old else 'adds the first figures'
    package_title = f"Forecast edition: {metric.get('title', metric['id'])}, {period}; {verb}"[:200]
    return package_title, changes, evidence


def materialize(root):
    """Turn ready holds into catalog packages. Enqueue never approves or publishes."""
    from catalog_review import base, enqueue
    from editorial_review import queue
    results = []
    for path in sorted(queue(root).glob('edition-*.json')):
        try:
            item = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            continue
        if not isinstance(item, dict) or item.get('status') != 'ready':
            continue
        try:
            docs = base(root)
            ledger = docs['site/data/ledger.json']
            registry_ids = {s['id'] for s in docs['research/sources.json']['sources']}
            title, changes, evidence = changes_for(root, item, ledger, registry_ids)
            p = enqueue(root, title, changes, evidence, author=AUTHOR)
            item.update(status='packaged', package=p['id'])
            results.append(p['id'])
        except FileExistsError:
            continue  # the editorial lock is busy; the next batch retries
        except (ValueError, KeyError, TypeError) as error:
            item.update(status='needs_maintainer', reason=str(error)[:500])
        path.write_text(json.dumps(item, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    return results


if __name__ == '__main__':
    import sys
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root/'scripts'))
    print(json.dumps(materialize(root)))
