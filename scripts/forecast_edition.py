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

A page that updates in place (a weekly consensus page, an Epoch site page, BLS projections) is
the same source, not a new edition. Owner decision, 09/23/2026: when such a page changes a figure
it already gave, the change is a 'revision' and is applied automatically, provided the page no
longer shows the old number (a static document the model merely misread still does, and stays a
conflict for review) and the publication policy's same-page rules admit it. A PDF never
revises itself: a static document that seems to have changed was misread. The night's admissible
revisions travel together (split only by the package size limit), each inadmissible one alone,
all packaged once by the nightly policy stage; a bundle whose preview fails is split so the rest
still go.
"""
import hashlib
import json
import re
import time
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlparse

from atomic_json import save as _save
from evidence_text import numeric_tokens

FORWARD = {'forecast', 'company-commitment', 'government-target'}
MODES = {'trajectory', 'by-year'}
AUTHOR = 'Forecast edition (research runner)'
REVISION_AUTHOR = 'Same-page revision (research runner)'
MAX_CHANGES_PER_PACKAGE = 100  # catalog_review.enqueue's limit; each revised figure is two changes
RUNNER = 'forecast edition runner'
POLICY_REVIEWER = 'publication-policy'  # publication-policy.json auto_apply.reviewer_label
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

    A registered source is dated by its reviewed publication date only; a year in its URL can be
    the year it forecasts. A discovered child's 'published' is the
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
    if source.get('parent_source'):
        path = _path_date(source)
        return path if path[0] is not None and path[1] == 'day' else (published or path)
    return published or (None, None)


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


# A page prints '10.86T' where the ledger stores 10,860 (TWD billion), or '42.68M' for 0.04268 (USD
# billion). A figure counts as still shown under any of these decimal scalings, so a page that did
# not change can never pass for a revision: the check errs toward a conflict for the owner.
# Only thousand-steps: a percent scaling roughly doubled coincidental matches on real pages.
_SCALES = (1, 1e3, 1e-3, 1e6, 1e-6, 1e9, 1e-9, 1e12, 1e-12)
# Every run of digits, including one glued to letters: TSMC prints "USD60 billion", which the
# evidence tokenizer (numeric_tokens) deliberately does not split.
_ANY_NUMBER = re.compile(r'\d[\d,]*(?:\.\d+)?')


def _shows(document, value):
    value = float(value)
    for t in _ANY_NUMBER.findall(document):
        try:
            n = float(t.replace(',', ''))
        except ValueError:
            continue
        if any(abs(n*s - value) <= 1e-9*max(1.0, abs(value)) for s in _SCALES):
            return True
    return False


def revision_target(record, source, observations, ledger_sources, metric):
    """This page's own figure that a revision replaces, or None."""
    by_id = {s['id']: s for s in ledger_sources}
    for o in incumbents(record['metric'], observations):
        s = by_id.get(o['source'], {'id': o['source']})
        if (s['id'] == source['id'] or s.get('url') == source['url']) and slot(o, metric) == slot(record, metric) \
                and (o['value'], o['upper']) != (record['value'], record['upper']):
            return o
    return None


def _revision(record, mine_same_slot, document):
    """'revision' when this page's own figure for the point changed and the page no longer shows it."""
    if document is None or document.startswith('[Page 1]\n'):
        return None  # a PDF does not update in place: a changed-looking figure there is a misreading
    for o in mine_same_slot:
        if (o['value'], o['upper']) != (record['value'], record['upper']) and not _shows(document, o['value']) \
                and (o['upper'] is None or not _shows(document, o['upper'])):
            return 'revision'
    return None


def classify(record, source, observations, ledger_sources, metric, document=None):
    """None (publish or conflict-check as today), 'older', 'unordered', 'new' or 'revision'."""
    if record['status'] not in FORWARD:
        return None
    current = incumbents(record['metric'], observations)
    if not current:
        return None
    by_id = {s['id']: s for s in ledger_sources}
    src = lambda o: by_id.get(o['source'], {'id': o['source']})
    mine = lambda s: s['id'] == source['id'] or s.get('url') == source['url']
    mine_same_slot = [o for o in current if slot(o, metric) == slot(record, metric) and mine(src(o))]
    if mode(metric) == 'trajectory':
        theirs = [src(o) for o in current]
        if any(mine(s) for s in theirs):
            return _revision(record, mine_same_slot, document)  # the same page, restating or revising itself
        return _OUTCOME[order(source, theirs)]
    same_slot = [src(o) for o in current if slot(o, metric) == slot(record, metric)]
    if any(mine(s) for s in same_slot):
        return _revision(record, mine_same_slot, document)
    others = [src(o) for o in current if not mine(src(o))]
    if not same_slot:
        # A year nobody has given yet publishes as before, unless an older edition would start a
        # series beside the newer one already on the chart.
        return 'older' if others and order(source, others) == 'older' else None
    return _OUTCOME[order(source, same_slot)]


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


def hold(local, source, full_text, held, metrics, page_of=None, change='edition', ledger=None):
    """Write one review candidate per metric: .local/review-candidates/edition-<24hex>.json.

    `held` is a list of (candidate, record, verdict) with no split points; one record is kept per
    point. A pending or rejected edition is never raised again: the id is a digest of the metric,
    the source and the figures themselves. A revision is pinned to the exact figure it replaces
    (`ledger` gives the observations and sources): its id and its records' ids include that figure,
    so a page that returns to an earlier value is a new revision, and a revision whose figure has
    since changed can only become obsolete, never be re-based onto the newer one. Returns the ids
    written.
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
        replaces, figures_replaced = {}, {}
        if change == 'revision':
            for _, r, _ in rows:
                target = revision_target(r, source, ledger['observations'], ledger['sources'], metric)
                if target:
                    replaces[slot(r, metric)] = target['id']
                    figures_replaced[slot(r, metric)] = [target['value'], target['upper']]
            rows = [(c, r, v) for c, r, v in rows if slot(r, metric) in replaces]
            if not rows:
                continue
        figures = sorted(json.dumps([r['year'], r['period'], r['value'], r['upper'], r['status'], r['precision'], replaces.get(slot(r, metric))], default=str) for _, r, _ in rows)
        rid = 'edition-' + _digest([metric_id, source['id'], source['url'], figures] + ([change] if change != 'edition' else []))[:24]
        path = folder/(rid+'.json')
        if path.exists():
            try:
                previous = json.loads(path.read_text(encoding='utf-8'))
            except (OSError, ValueError):
                previous = {}
            # An obsolete revision whose page shows its value again is a live reading again.
            if not (change == 'revision' and previous.get('status') == 'obsolete'):
                continue
        records = []
        for c, r, v in rows:
            # The old edition may hold an identical automated figure under the same id; the
            # source in the identity keeps the two apart.
            pinned = replaces.get(slot(r, metric))
            identity = json.dumps([r[k] for k in ['metric', 'year', 'period', 'value', 'upper', 'status', 'precision']] + [source['id']] + ([pinned] if pinned else []), separators=(',', ':'))
            rec = dict(r, id='auto-' + hashlib.sha256(identity.encode('utf-8')).hexdigest()[:20])
            records.append({'record': rec, 'quote': c['evidence'], 'review': v,
                            'pdf_page': page_of(c['evidence']) if page_of else None,
                            **({'replaces': pinned, 'replaces_figure': figures_replaced[slot(r, metric)]} if pinned else {})})
        value = {'id': rid, 'kind': 'forecast_edition', 'change': change, 'status': 'ready', 'created_at': _now(), 'held_ns': time.time_ns(), 'metric': metric_id,
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


def revision_changes(root, item, ledger):
    """Changes and evidence for a same-page revision: each revised figure replaces the page's own
    earlier figure for that point, nothing else."""
    metric = next((m for m in ledger['metrics'] if m['id'] == item['metric']), None)
    if metric is None:
        raise ValueError('Held revision names an unknown metric')
    source = item['source']
    current = {o['id']: o for o in incumbents(metric['id'], ledger['observations'])}
    proposed = item.get('proposed_at') or item['created_at']
    # One evidence entry per page and metric: two revisions from one page keep their own quotes.
    evid = clean(f"{source['id'][:90]}@{_digest([item['document_sha256'], metric['id']])[:16]}", 140)
    changes, lines, old_ids = [], [], []
    for row in item['records']:
        r = row['record']
        old = current.get(row.get('replaces'))
        pinned = row.get('replaces_figure')
        if old is None or (old['value'], old['upper']) == (r['value'], r['upper']) \
                or (pinned is not None and [old['value'], old['upper']] != pinned):
            # The figure this revision was read against has itself changed (a newer revision, an
            # owner's decision): never re-base an older reading onto it.
            raise Obsolete('The figure this revision replaced is no longer the one on the site')
        # "Only the value changed": the reviewed caveat travels with the figure unless it quotes the
        # old number, when the runner's reading replaces it.
        quotes_old = old.get('note') and (_shows(old['note'], old['value']) or (old['upper'] is not None and _shows(old['note'], old['upper'])))
        note = old['note'] if old.get('note') and not quotes_old else r.get('note', '')
        reason = clean(f"Revised by the publisher at the same address: {_fmt(old)} is now {_fmt(r)}.", 500)
        changes.append({'target': 'observation', 'id': r['id'], 'after': dict(r, note=note, edition_supersedes=[old['id']], correction_reason=reason), 'evidence': [evid]})
        changes.append({'target': 'observation', 'id': old['id'], 'after': dict(old, superseded_by=r['id']), 'evidence': [evid]})
        lines.append(f"{_fmt(old)} → {_fmt(r)}: \"{clean(row['quote'], 200)}\"")
        old_ids.append(old['id'])
    if not changes:
        raise Obsolete('Nothing left to revise: the site already shows these figures')
    citing = cited(root, old_ids)
    if citing:
        first = next(iter(citing))
        raise ValueError(f'{first} is cited by {", ".join(citing[first])}; replacing it needs a maintainer to repoint that reference')
    evidence = {'id': evid, 'url': source['url'], 'published_at': source.get('published'), 'retrieved_at': proposed,
                'sha256': item['document_sha256'], 'summary': clean(f"Same page, revised figures. {metric.get('title', metric['id'])}: " + ' | '.join(lines), 2000)}
    return changes, evidence, lines


def changes_for(root, item, ledger, registry_ids):
    """The catalog changes and evidence that publish the held edition and retire the old one."""
    metric = next((m for m in ledger['metrics'] if m['id'] == item['metric']), None)
    if metric is None:
        raise ValueError('Held edition names an unknown metric')
    source = item['source']
    new = [row['record'] for row in item['records']]
    sources = {s['id']: s for s in ledger['sources']}
    current = incumbents(metric['id'], ledger['observations'])
    restated = {slot(r, metric) for r in new}
    if any(o['source'] == source['id'] and slot(o, metric) in restated for o in current):
        raise Obsolete('Figures from this document are already on the site for these points')
    current = [o for o in current if o['source'] != source['id']]
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

    proposed = item.get('proposed_at') or item['created_at']
    new_ev = {'id': source['id'], 'url': source['url'], 'published_at': _published_at(source), 'retrieved_at': proposed,
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
        # retrieved_at is this proposal attempt's time: a retry rebuilds the same package id.
        evidence.append({'id': eid, 'url': url, 'published_at': _published_at(s), 'retrieved_at': proposed,
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
    """Take a runner package off the owner's list once it can no longer apply. A bookkeeping event,
    not a decision: it approves nothing and publishes nothing, and it never overrides the owner, whose
    rejection or approval recorded meanwhile is re-read under the same lock the panel writes with."""
    from catalog_review import last_review
    from editorial_review import append_event, locked
    with locked(root):
        review = last_review(root, package_id)
        if review and (review.get('status') in ('rejected', 'withdrawn', 'applied')
                       or (review.get('status') == 'approved' and review.get('reviewer') != POLICY_REVIEWER)):
            return False  # a person's decision stands; the policy's own approval may be taken back
        append_event(root, {'id': package_id, 'kind': 'catalog_change', 'status': 'withdrawn', 'reviewer': RUNNER,
                            'rationale': reason, 'at': _now()})
    return True


def materialize(root, revisions=False):
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
    stale = 'The reviewed files changed since this edition was proposed.'
    revisions_ready = []
    for path in paths:
        try:
            item = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            continue
        if not isinstance(item, dict):
            continue
        status = item.get('status')
        try:
            if status in ('packaged', 'applied', 'obsolete'):
                pid = item.get('package')
                review = last_review(root, pid) if pid else None
                decided = review.get('status') if review else None
                if {r['record']['id'] for r in item['records']} <= on_site:
                    if status != 'applied':
                        item['status'] = 'applied'
                        _save(path, item)
                    # A sibling hold's package that published these figures leaves this one unable to apply.
                    if pid and decided in (None, 'deferred'):
                        withdraw(root, pid, 'These figures were published by another package.')
                    continue
                if status != 'packaged' or decided == 'rejected':
                    continue
                still_applies = False
                if decided != 'withdrawn':
                    try:
                        check_base(root, package(root, pid))
                        still_applies = True
                    except (ValueError, KeyError, OSError):
                        pass
                # A bundle that failed its preview is split: each revision is proposed alone. Checked
                # whether or not a sibling hold has already withdrawn the bundle this pass.
                failure = revisions and item.get('change') == 'revision' and not item.get('solo') and item.get('bundle', 1) > 1 \
                    and _preview_failed(root, pid)
                if failure and failure not in item.get('failed_checkouts', []):
                    item['failed_checkouts'] = sorted(set(item.get('failed_checkouts', [])) | {failure})
                    _save(path, item)
                bundle_failed = bool(failure) and len(item.get('failed_checkouts', [])) >= 2
                if still_applies and not bundle_failed:
                    continue  # still applies: the owner (or the policy) decides
                if bundle_failed:
                    item['solo'] = True
                # Save the hold as ready before withdrawing, so no interruption can leave it
                # pointing at a withdrawn package; the withdrawal itself is retried below.
                item.setdefault('earlier_packages', []).append(pid)
                item.update(status='ready', proposed_at=None)
                _save(path, item)
                status = 'ready'
            if status == 'needs_maintainer' and item.get('failed_base') != key:
                status = 'ready'
            if status != 'ready':
                continue
            for earlier in item.get('earlier_packages', []):
                last = last_review(root, earlier)
                if not last or last.get('status') not in ('withdrawn', 'rejected', 'applied'):
                    withdraw(root, earlier, stale)
            if not item.get('proposed_at'):
                item['proposed_at'] = _now()
                _save(path, item)
            if item.get('change') == 'revision':
                if revisions:
                    revisions_ready.append((path, item))
                continue
            for attempt in range(5):
                title, changes, evidence = changes_for(root, item, ledger, registry_ids)
                p = enqueue(root, title, changes, evidence, author=AUTHOR)
                if p['id'] not in item.get('earlier_packages', []):
                    break
                # Same files and same second as a withdrawn proposal: step this attempt's time back a
                # second (forward would be a future retrieval time, which validation refuses).
                item['proposed_at'] = (datetime.strptime(item['proposed_at'], '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
                                       .timestamp() - 1)
                item['proposed_at'] = datetime.fromtimestamp(item['proposed_at'], timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')
                _save(path, item)
            else:
                raise ValueError('Could not propose this edition apart from its withdrawn packages')
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
    if revisions:
        results += _package_revisions(root, revisions_ready, ledger, key, enqueue)
    return results


def _preview_failed(root, pid):
    """The checkout this exact package last failed its preview on, or False. The caller splits a
    bundle only after failures on two different checkouts, so one flaky preview is retried whole."""
    try:
        from catalog_review import preview_validation, package, digest
        v = preview_validation(root, pid)
        failed = v.get('passed') is False and v.get('proposal_hash') == digest(package(root, pid))
        return (v.get('checkout') or v.get('at') or 'failed') if failed else False
    except Exception:
        return False


def _latest_text(root, url):
    """The page as the runner last read it (fetch state -> saved text), or None."""
    try:
        from collection_health import Health
        sha = Health(Path(root)/'.local/fetch-state.json').get('page', url).get('text_sha256')
        path = Path(root)/'.local/evidence'/f'{sha}.json'
        return json.loads(path.read_text(encoding='utf-8')).get('text') if sha and path.exists() else None
    except Exception:
        return None


def _current_readings(root, revisions):
    """Keep only readings that are still true, one per site figure.

    A reading survives when the page as last read still shows its value and no longer shows the
    figure it replaces, and when no newer reading of the same figure exists. Checked per figure, so
    a reading that partly overlaps a newer one keeps only what the newer one does not cover. A hold
    left with nothing is obsolete; a proposed package that lost figures is withdrawn and proposed
    again without them. An owner's approval is never withdrawn (see withdraw)."""
    from catalog_review import last_review
    from editorial_review import queue
    ready = {str(p): i for p, i in revisions}
    holds = []
    for path in sorted(queue(root).glob('edition-*.json')):
        if str(path) in ready:
            holds.append((path, ready[str(path)]))
            continue
        try:
            item = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            continue
        # A ready hold materialize did not pass in is waiting on something (a busy lock while its
        # earlier package was withdrawn): it waits for the next pass. A package a person rejected or
        # approved is theirs: never trimmed, re-proposed or withdrawn by the runner.
        if not isinstance(item, dict) or item.get('change') != 'revision' or item.get('status') != 'packaged':
            continue
        review = last_review(root, item.get('package'))
        if review and (review.get('status') in ('rejected', 'withdrawn', 'applied')
                       or (review.get('status') == 'approved' and review.get('reviewer') != POLICY_REVIEWER)):
            continue
        holds.append((path, item))
    texts, fresh = {}, {}
    for path, item in holds:
        url = item['source']['url']
        if url not in texts:
            texts[url] = _latest_text(root, url)
        latest = texts[url]
        keep = []
        for row in item['records']:
            r, was = row['record'], row.get('replaces_figure') or [None, None]
            if latest is not None and (not _shows(latest, r['value']) or (r['upper'] is not None and not _shows(latest, r['upper']))
                                       or (was[0] is not None and _shows(latest, was[0]))):
                continue  # the page has moved on (or back) since this reading
            keep.append(row)
        fresh[str(path)] = keep
    order = lambda i: (i['created_at'], i.get('held_ns', 0))
    newest = {}
    for path, item in holds:
        for row in fresh[str(path)]:
            pin = row.get('replaces')
            if pin and (pin not in newest or order(item) > order(newest[pin][1])):
                newest[pin] = (path, item)
    out, withdrawn = [], set()
    kept = {}
    for path, item in holds:
        kept[str(path)] = [row for row in fresh[str(path)] if not row.get('replaces') or newest[row['replaces']][0] == path]
        if len(kept[str(path)]) != len(item['records']) and item['status'] == 'packaged' and item.get('package'):
            withdraw(root, item['package'], 'A newer reading of the same figure, or the page as last read, replaces part of this revision.')
            withdrawn.add(item['package'])
    for path, item in holds:
        keep = kept[str(path)]
        moved = item['status'] == 'packaged' and item.get('package') in withdrawn
        if len(keep) == len(item['records']) and not moved:
            if item['status'] == 'ready':
                out.append((path, item))
            continue
        if moved:
            item.setdefault('earlier_packages', []).append(item['package'])
        if not keep:
            item.update(status='obsolete', reason='A newer reading of the same figure, or the page as last read, replaces this revision')
            _save(path, item)
            continue
        # Trimmed, or a sibling in a bundle that had to be withdrawn: proposed again tonight.
        item.update(records=keep, status='ready', proposed_at=_now())
        _save(path, item)
        out.append((path, item))
    return out


def _bundle(admitted, limit=MAX_CHANGES_PER_PACKAGE):
    """Admissible revisions in as few packages as the change limit allows."""
    groups, current = [], []
    for b in admitted:
        if current and sum(len(x[2]) for x in current) + len(b[2]) > limit:
            groups.append(current)
            current = []
        current.append(b)
    if current:
        groups.append(current)
    return groups


def _before(ledger, change):
    return next((o for o in ledger['observations'] if o['id'] == change['id']), None)


def _package_revisions(root, revisions, ledger, key, enqueue):
    """The night's same-page revisions: admissible ones together, each inadmissible one alone."""
    revisions = _current_readings(root, revisions)
    built = []
    for path, item in revisions:
        try:
            changes, evidence, lines = revision_changes(root, item, ledger)
            built.append((path, item, changes, evidence, lines))
        except Obsolete as error:
            item.update(status='obsolete', reason=str(error))
            _save(path, item)
        except (ValueError, KeyError, TypeError) as error:
            item.update(status='needs_maintainer', reason=str(error)[:500], failed_base=key)
            _save(path, item)
    results = []
    # Screen each revision against the publication policy first: those it would admit travel in one
    # package, and each one it would not gets a package of its own for the owner, so one scale slip
    # cannot send the whole night's revisions to review or take them down with a rejection.
    try:
        import publication_policy
        rule = publication_policy.policy(root)['auto_apply']['same_page_revisions']
        fits = lambda b: publication_policy.same_page_revision({'changes': [dict(c, before=_before(ledger, c)) for c in b[2]]}, rule)[0]
    except Exception:
        fits = lambda b: False

    def attempt(group):
        changes = [c for _, _, cs, _, _ in group for c in cs]
        evidence = list({e['id']: e for _, _, _, e, _ in group}.values())
        count = sum(len(ls) for _, _, _, _, ls in group)
        title = clean(f"Same-page revisions: {count} figure{'s' if count != 1 else ''} updated by their publishers"
                      if len(group) > 1 else f"Same-page revision: {group[0][4][0]}", 200)
        p = enqueue(root, title, changes, evidence, author=REVISION_AUTHOR)
        for path, item, _, _, _ in group:
            item.update(status='packaged', package=p['id'], bundle=len(group))
            item.pop('reason', None)
            item.pop('failed_base', None)
            _save(path, item)
        results.append(p['id'])

    # Readings the same-page rule would admit travel together; each one it would not (a scale slip,
    # a status change) gets a card of its own, whether or not auto-apply is on.
    admitted = [b for b in built if fits(b) and not b[1].get('solo')]
    groups = _bundle(admitted) + [[b] for b in built if b not in admitted]
    for group in groups:
        try:
            attempt(group)
        except FileExistsError:
            return results  # the editorial lock is busy; the next batch retries
        except (ValueError, KeyError, TypeError):
            for one in group:
                try:
                    attempt([one])
                except FileExistsError:
                    return results
                except (ValueError, KeyError, TypeError) as error:
                    one[1].update(status='needs_maintainer', reason=str(error)[:500], failed_base=key)
                    _save(one[0], one[1])
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
    # --revisions packages same-page revisions too, as the nightly policy stage does.
    print(json.dumps(materialize(root, revisions='--revisions' in sys.argv[1:])))
