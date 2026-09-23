"""A new edition of a forecast is a replacement, not a conflict and not an addition.

Grid operators, the IEA and the hyperscalers re-issue their forecasts. Until 09/23/2026 the
monitoring lane compared metric and year only, so a later edition either collided with the
earlier one on a shared year (a 'conflict', quarantined where nobody saw it) or, on the years the
two editions do not share, was published straight into the same chart series: PJM's 2027 report
would have drawn its 2037 and 2047 peaks on one line with the 2026 report's 2036 and 2046. The
same vintage error cost the site Amazon's current guidance on 09/22.

So a forward-looking figure (forecast, company commitment, government target) from a different
document than the one already on the chart is never published by the runner:

- 'older': the document was issued before the edition on the site. Quarantined, including a
  figure for a year the chart does not show yet: an older edition does not start a series beside
  a newer one.
- 'unordered': the two cannot be put in order (an undated document, or two documents from the
  same year with no day to tell them apart). Quarantined; guessing is how February's plan would
  have replaced July's guidance.
- 'new': held with every other figure the same document gives for that metric, and turned into
  one catalog package. The owner sees both editions side by side on the review card; approving
  publishes the new figures and retires the old edition's in one reviewed commit.

An edition is held only if it changes something: a document whose figures all restate the chart
is a duplicate (research.extract_observations checks this before and after screening).

A metric's reviewed `edition_mode` decides what an edition replaces:

- 'trajectory': the new edition replaces the whole old one, whatever years each covers (rolling
  load forecasts, whose horizon moves every year).
- 'by-year' (the default): only the years the new edition restates are replaced, so 2027
  guidance can sit beside 2026 guidance; a year no incumbent covers publishes as before, unless
  the document is older than the edition on the chart.

A page that restates its own figures (a weekly consensus page) is the same source, not a new
edition, and keeps the ordinary duplicate/conflict handling.
"""
import hashlib
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlparse

from atomic_json import save as _save

FORWARD = {'forecast', 'company-commitment', 'government-target'}
MODES = {'trajectory', 'by-year'}
AUTHOR = 'Forecast edition (research runner)'
RUNNER = 'forecast edition runner'
REASONS = {
    'older': 'Older forecast edition than the one on the site',
    'unordered': 'Forecast edition cannot be ordered against the one on the site',
    'split': 'Forecast edition gives two figures for one year',
}
_YEAR = re.compile(r'(?<!\d)(20\d\d)(?!\d)')
_PATH_DAY = re.compile(r'/(20\d\d)/(\d\d)/(\d\d)/')           # ERCOT: /files/docs/2026/12/22/...
_NAME_DAY = re.compile(r'(?<!\d)(20\d\d)(\d\d)(\d\d)(?!\d)')    # PJM: 20260826-item-03...
# validate.text refuses these as possible secrets or local paths; a quote can contain one by accident.
_SECRETISH = re.compile(r'(?i)(gh[pousr]_[A-Za-z0-9]{15,}|sk-[a-z0-9]{20,}|[a-z]:\\users\\|bearer\s+\S+|(api[_-]?key|registrationkey)[\x22\x27\s:=]{1,4}[A-Za-z0-9]{16,}|[?&]key=[A-Za-z0-9]{16,})')


def _now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode('utf-8')).hexdigest()


def clean(value, limit):
    """Reviewed text refuses markup, control characters and anything shaped like a secret; a quote
    from a PDF can carry any of them."""
    value = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', ' ', str(value)).replace('<', '‹').replace('>', '›')
    return _SECRETISH.sub('…', value)[:limit]


def mode(metric):
    return (metric or {}).get('edition_mode', 'by-year')


def _day(y, m, d):
    try:
        return date(int(y), int(m), int(d))
    except ValueError:
        return None


def _path_date(source):
    path = unquote(urlparse((source or {}).get('url', '')).path)
    for pattern in (_PATH_DAY, _NAME_DAY):
        for m in pattern.finditer(path):
            d = _day(*m.groups())
            if d:
                return d, 'day'
    years = [int(y) for y in _YEAR.findall(path.rsplit('/', 1)[-1])]
    return (max(years), 'year') if years else (None, None)


def edition_date(source):
    """(date, 'day') or (year, 'year') for when an edition was issued, else (None, None).

    A registered source's reviewed publication date wins. A discovered child's 'published' is the
    first date printed on its first page, which in a meeting deck is as often a deadline as the
    issue date, so for those the publisher's own filing path wins: ERCOT's /YYYY/MM/DD/, PJM's
    YYYYMMDD- meeting files, then a year in the file name."""
    source = source or {}
    published = None
    if source.get('published'):
        try:
            published = date.fromisoformat(source['published'][:10]), 'day'
        except ValueError:
            pass
    path = _path_date(source)
    if source.get('parent_source'):
        return path if path[0] is not None and path[1] == 'day' else (published or path)
    return published or path


def issued(source):
    """The issue date as reviewed text: '2026-12-22', '2027', or 'undated'."""
    d, kind = edition_date(source)
    return d.isoformat() if kind == 'day' else str(d) if d else 'undated'


def order(new_source, old_sources):
    """'newer', 'older', 'same' or 'unordered' for a document against the editions on the site."""
    new, new_kind = edition_date(new_source)
    olds = [edition_date(s) for s in old_sources]
    if new is None or not olds or any(d is None for d, _ in olds):
        return 'unordered'
    if new_kind == 'day' and all(k == 'day' for _, k in olds):
        newest = max(d for d, _ in olds)
        return 'newer' if new > newest else 'older' if new < newest else 'same'
    year = lambda d: d if isinstance(d, int) else d.year
    newest = max(year(d) for d, _ in olds)
    return 'newer' if year(new) > newest else 'older' if year(new) < newest else 'unordered'


def slot(o, metric):
    """What two figures must share to be the same point: the year, or the period where the metric keys on it
    (the same rule as research.duplicate_or_conflict)."""
    return (o['year'], o['period']) if (metric or {}).get('period_basis') in ('month', 'quarter', 'snapshot') else (o['year'],)


def incumbents(metric_id, observations):
    return [o for o in observations if o['metric'] == metric_id and not o.get('superseded_by') and o['status'] in FORWARD]


_OUTCOME = {'newer': 'new', 'older': 'older', 'unordered': 'unordered', 'same': None}


def classify(record, source, observations, ledger_sources, metric):
    """None (publish or conflict-check as today), 'older', 'unordered' or 'new'."""
    if record['status'] not in FORWARD:
        return None
    current = incumbents(record['metric'], observations)
    if not current:
        return None
    by_id = {s['id']: s for s in ledger_sources}
    src = lambda o: by_id.get(o['source'], {'id': o['source']})
    theirs = [src(o) for o in current]
    if source['id'] in {s['id'] for s in theirs} or source['url'] in {s.get('url') for s in theirs}:
        return None  # the same document restating itself
    if mode(metric) == 'trajectory':
        return _OUTCOME[order(source, theirs)]
    same_slot = [o for o in current if slot(o, metric) == slot(record, metric)]
    if not same_slot:
        # A year nobody has given yet publishes as before, unless an older edition would start a
        # series beside the newer one already on the chart.
        return 'older' if order(source, theirs) == 'older' else None
    return _OUTCOME[order(source, [src(o) for o in same_slot])]


def restates(record, observations, metric):
    """An incumbent figure with the same point and value, whichever document gave it and however it
    was worded (status and precision are the model's reading, not a change on the chart)."""
    key = (slot(record, metric), record['value'], record['upper'])
    return any((slot(o, metric), o['value'], o['upper']) == key for o in incumbents(record['metric'], observations))


def split_slots(records, metric):
    """Points for which one document gives two different values: one chart point cannot hold both."""
    seen, split = {}, set()
    for r in records:
        key, figure = slot(r, metric), (r['value'], r['upper'])
        if key in seen and seen[key] != figure:
            split.add(key)
        seen.setdefault(key, figure)
    return split


def hold(local, source, full_text, held, metrics, page_of=None):
    """Write one review candidate per metric: .local/review-candidates/edition-<24hex>.json.

    `held` is a list of (candidate, record, verdict) with no split points; one record is kept per
    point. A pending or rejected edition is never raised again: the id is a digest of the metric,
    the source and the figures themselves. Returns the ids written.
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
        metric = metrics.get(metric_id)
        rows, seen = [], set()
        for c, r, v in held:
            if r['metric'] == metric_id and slot(r, metric) not in seen:
                seen.add(slot(r, metric))
                rows.append((c, r, v))
        figures = sorted(json.dumps([r['year'], r['period'], r['value'], r['upper'], r['status'], r['precision']], default=str) for _, r, _ in rows)
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
                 'mode': mode(metric), 'source': source, 'document_sha256': sha, 'records': records,
                 'authority': 'Private runner hold. Nothing is published until the owner approves the catalog package.'}
        _save(path, value)
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


def _published_at(source):
    d, kind = edition_date(source)
    return source.get('published') or (d.isoformat() if kind == 'day' else None)


class Obsolete(ValueError):
    """The held edition is no longer the newest, or its figures are already on the site."""


def cited(root, ids):
    """Reviewed files, other than the ledger and the catalog, that name any of these figures."""
    hits = {}
    for path in sorted(Path(root).glob('research/*.json')):
        if path.name in {'catalog.json', 'sources.json'}:
            continue
        try:
            text = path.read_text(encoding='utf-8')
        except OSError:
            continue
        for i in ids:
            if f'"{i}"' in text:
                hits.setdefault(i, []).append(path.name)
    return hits


def changes_for(root, item, ledger, registry_ids):
    """The catalog changes and evidence that publish the held edition and retire the old one."""
    metric = next((m for m in ledger['metrics'] if m['id'] == item['metric']), None)
    if metric is None:
        raise ValueError('Held edition names an unknown metric')
    source = item['source']
    new = [row['record'] for row in item['records']]
    sources = {s['id']: s for s in ledger['sources']}
    current = incumbents(metric['id'], ledger['observations'])
    if any(o['source'] == source['id'] for o in current):
        raise Obsolete('Figures from this document are already on the site for this metric')
    restated = {slot(r, metric) for r in new}
    old = current if mode(metric) == 'trajectory' else [o for o in current if slot(o, metric) in restated]
    if old and order(source, [sources.get(o['source'], {'id': o['source']}) for o in old]) != 'newer':
        # Another edition was approved in the meantime and this one is no longer the newest.
        raise Obsolete('A newer or same-dated edition is already on the site')
    if all(restates(r, ledger['observations'], metric) for r in new):
        # Nothing new to publish; approving could only take the unrestated points off the chart.
        raise Obsolete('The held figures only restate what the site shows')
    citing = cited(root, [o['id'] for o in old])
    if citing:
        first = next(iter(citing))
        raise ValueError(f'{first} is cited by {", ".join(citing[first])}; retiring it needs a maintainer to repoint that reference')
    latest = max(new, key=lambda r: (r['year'], r['upper'] if r['upper'] is not None else r['value']))
    by_slot = {slot(r, metric): r for r in new}
    assigned = {o['id']: by_slot.get(slot(o, metric), latest)['id'] for o in old}
    old_sources = sorted({o['source'] for o in old})
    title = clean(source.get('title') or source['url'], 160)
    olds = '; '.join(f"{clean(sources.get(s, {}).get('title', s), 120)} (published {issued(sources.get(s, {'id': s}))})" for s in old_sources)
    reason = clean(f"New edition: {title} (published {issued(source)}) replaces {olds}.", 500) if old else None

    new_ev = {'id': source['id'], 'url': source['url'], 'published_at': _published_at(source), 'retrieved_at': item['created_at'],
              'sha256': item['document_sha256'],
              'summary': clean('New edition. ' + ' | '.join(f"{_fmt(row['record'])}: \"{clean(row['quote'], 220)}\"" + (f" (p. {row['pdf_page']})" if row.get('pdf_page') else '')
                                                           for row in item['records']), 2000)}
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
            lines.append(f"{_fmt(o)}: " + (f"\"{clean(quote, 220)}\"" if quote else f"quote not retained; note: {clean(o.get('note') or '', 200)}"))
        body = f"Edition on the site now: {s.get('title', sid)} ({s.get('url')}), published {issued(s)}.\n" + '\n'.join(lines)
        url = s.get('url')
        if not (isinstance(url, str) and url.startswith('https://')):
            raise ValueError(f'Old edition source {sid} has no public HTTPS URL for evidence')
        eid = ('old-' + sid)[:140]
        # retrieved_at is the hold's own time, so re-running materialize builds the same package id.
        evidence.append({'id': eid, 'url': url, 'published_at': _published_at(s), 'retrieved_at': item['created_at'],
                         'sha256': _retain(root, body), 'summary': clean('Edition on the site now. ' + ' | '.join(lines), 2000)})
        old_ev[sid] = eid

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
    period = f"{min(r['year'] for r in new)}–{max(r['year'] for r in new)}" if len({r['year'] for r in new}) > 1 else str(new[0]['year'])
    verb = f"replaces {len(old)} figure{'s' if len(old) != 1 else ''} from the earlier edition" if old else 'adds the first figures'
    package_title = clean(f"Forecast edition: {metric.get('title', metric['id'])}, {period}; {verb}", 200)
    return package_title, changes, evidence


def _base_key(docs):
    return _digest({k: _digest(v) for k, v in docs.items()})


def withdraw(root, package_id, reason):
    """Take a runner package off the owner's list once a newer proposal or edition replaces it.
    A bookkeeping event, not a decision: it approves nothing and publishes nothing."""
    from editorial_review import append_event, locked
    with locked(root):
        append_event(root, {'id': package_id, 'kind': 'catalog_change', 'status': 'withdrawn', 'reviewer': RUNNER,
                            'rationale': reason, 'at': _now()})


def materialize(root):
    """Turn holds into catalog packages and keep them current. Enqueue never approves or publishes.

    - ready: packaged against the current reviewed files.
    - packaged: left alone while its package still applies or the owner has rejected it; marked
      applied once its figures are on the site; withdrawn and proposed again when the files moved
      under it (another edition was approved, the owner deferred it) unless a newer edition now
      stands, when it becomes obsolete.
    - needs_maintainer: retried once the reviewed files change.
    """
    from catalog_review import base, check_base, enqueue, package, last_review
    from editorial_review import queue
    results = []
    paths = sorted(queue(root).glob('edition-*.json'))
    if not paths:
        return results
    docs = base(root)
    key = _base_key(docs)
    ledger = docs['site/data/ledger.json']
    on_site = {o['id'] for o in ledger['observations']}
    registry_ids = {s['id'] for s in docs['research/sources.json']['sources']}
    for path in paths:
        try:
            item = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            continue
        if not isinstance(item, dict):
            continue
        status = item.get('status')
        try:
            if status == 'packaged':
                if {r['record']['id'] for r in item['records']} <= on_site:
                    item['status'] = 'applied'
                    _save(path, item)
                    continue
                pid = item['package']
                review = last_review(root, pid)
                if review and review.get('status') in ('rejected', 'withdrawn'):
                    continue
                try:
                    check_base(root, package(root, pid))
                    continue  # still applies: the owner decides
                except (ValueError, KeyError, OSError):
                    withdraw(root, pid, 'The reviewed files changed since this edition was proposed; a current proposal replaces it.')
                    item.setdefault('earlier_packages', []).append(pid)
                    status = 'ready'
            if status == 'needs_maintainer' and item.get('failed_base') != key:
                status = 'ready'
            if status != 'ready':
                continue
            title, changes, evidence = changes_for(root, item, ledger, registry_ids)
            p = enqueue(root, title, changes, evidence, author=AUTHOR)
            item.update(status='packaged', package=p['id'])
            item.pop('reason', None)
            item.pop('failed_base', None)
            results.append(p['id'])
        except FileExistsError:
            continue  # the editorial lock is busy; the next batch retries
        except Obsolete as error:
            item.update(status='obsolete', reason=str(error))
        except (ValueError, KeyError, TypeError) as error:
            item.update(status='needs_maintainer', reason=str(error)[:500], failed_base=key)
        _save(path, item)
    return results


def blocked(root):
    """Holds a maintainer has to look at: they cannot be packaged against the current files."""
    from editorial_review import queue
    count = 0
    for path in queue(root).glob('edition-*.json'):
        try:
            count += json.loads(path.read_text(encoding='utf-8')).get('status') == 'needs_maintainer'
        except (OSError, ValueError, AttributeError):
            count += 1
    return count


if __name__ == '__main__':
    import sys
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root/'scripts'))
    print(json.dumps(materialize(root)))
