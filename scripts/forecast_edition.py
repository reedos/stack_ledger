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
the same source, not a new edition: when it gives a different figure for a point it already gave,
the change is a 'revision'. A PDF never revises itself: a static document that seems to have
changed was misread, and stays a conflict.

Revisions are settled once a night by settle_revisions, in the nightly policy stage, and none is
carried to another night as an automatic package. Owner decisions, 09/23 and 09/24/2026: a
revision is published unattended only when its page is on the publication policy's same-page
list, the page as last read still carries the reading's quote and no longer shows the old figure,
the reading is from this night, and the policy's same-page rules admit it (value only, within
1.1x, not nearer another year the page gives). Every other revision reaches the owner as a card,
one per page, and a reading the owner rejected is not raised again.
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
REVISION_AUTHOR = 'Same-page revision (research runner)'  # published by settle_revisions, never by apply_admitted
REVIEW_AUTHOR = 'Same-page revision (for review)'  # never admitted by the publication policy: a person decides
SAME_NIGHT_SECONDS = 20*3600  # a reading from an earlier night goes to the owner, never out unattended
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
    """'revision' when this page now gives a different figure for a point it already gave.

    Whether the page still shows the old figure is settle_revisions' question, not this one's: until
    09/24/2026 such a reading was quarantined as a conflict where nobody saw it, so a misread figure
    that had been published could never be put right by the page's next correct reading."""
    if document is None or document.startswith('[Page 1]\n'):
        return None  # a PDF does not update in place: a changed-looking figure there is a misreading
    if any((o['value'], o['upper']) != (record['value'], record['upper']) for o in mine_same_slot):
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
            # An obsolete revision whose page shows its value again is a live reading again, and one
            # that needed a maintainer is tried again when the page is read again.
            if not (change == 'revision' and previous.get('status') in ('obsolete', 'needs_maintainer')):
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
    # One evidence entry per page, metric and replaced figure: two revisions from one page keep their own quotes.
    evid = clean(f"{source['id'][:90]}@{_digest([item['document_sha256'], metric['id']] + [row.get('replaces') for row in item['records']])[:16]}", 140)
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
        # "Only the value changed": the reviewed caveat travels with the figure when it carries no
        # number of its own. A date or figure in it may now be stale, so the runner's reading
        # replaces it and the publication policy sends the change to the owner.
        note = old.get('note', '') if not re.search(r'\d', old.get('note') or '') else r.get('note', '')
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


def withdraw(root, package_id, reason, keep_deferred=False):
    """Take a runner package off the owner's list once it can no longer apply. A bookkeeping event,
    not a decision: it approves nothing and publishes nothing, and it never overrides the owner, whose
    rejection or approval recorded meanwhile is re-read under the same lock the panel writes with.
    keep_deferred leaves a package the owner deferred alone too: materialize takes back a deferred
    edition only because the files moved under it and it can no longer apply."""
    from catalog_review import last_review
    from editorial_review import append_event, locked
    with locked(root):
        review = last_review(root, package_id)
        if review and (review.get('status') in ('rejected', 'withdrawn', 'applied')
                       or (keep_deferred and review.get('status') == 'deferred')
                       or (review.get('status') == 'approved' and review.get('reviewer') != POLICY_REVIEWER)):
            return False  # a person's decision stands; the policy's own approval may be taken back
        append_event(root, {'id': package_id, 'kind': 'catalog_change', 'status': 'withdrawn', 'reviewer': RUNNER,
                            'rationale': reason, 'at': _now()})
    return True


def materialize(root):
    """Turn edition holds into catalog packages and keep them current. Enqueue never approves or
    publishes. Same-page revisions are not touched here: settle_revisions takes them once a night.

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
    for path in paths:
        try:
            item = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            continue
        if not isinstance(item, dict) or item.get('change') == 'revision':
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
                if still_applies:
                    continue  # still applies: the owner decides
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
    return results


def _latest_text(root, url):
    """The page as the runner last read it (fetch state -> saved text), or None."""
    try:
        from collection_health import Health
        sha = Health(Path(root)/'.local/fetch-state.json').get('page', url).get('text_sha256')
        path = Path(root)/'.local/evidence'/f'{sha}.json'
        return json.loads(path.read_text(encoding='utf-8')).get('text') if sha and path.exists() else None
    except Exception:
        return None


_PACKAGE = re.compile(r'catalog-[0-9a-f]{24}')


def _ago(seconds):
    return datetime.fromtimestamp(time.time()-seconds, timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


def _bundle(units, limit=MAX_CHANGES_PER_PACKAGE):
    """Pages' readings in as few packages as the change limit allows. One page's readings and its
    date change always travel together."""
    size = lambda unit: sum(len(x['changes']) for x in unit) + 1  # + the page's date change
    groups, current = [], []
    for unit in units:
        if current and sum(size(u) for u in current) + size(unit) > limit:
            groups.append(current)
            current = []
        current.append(unit)
    if current:
        groups.append(current)
    return groups


def _before(ledger, change):
    return next((o for o in ledger['observations'] if o['id'] == change['id']), None)


def _date_change(registry, source_id, readings):
    """The page's registered date moved to the day it was read, or None when it already says that
    day or later. The site labels a forecast with its source's date, and a revised figure is the
    page as read that day, not the snapshot first registered (review finding, 09/24/2026)."""
    s = next((x for x in registry['sources'] if x['id'] == source_id), None)
    if s is None:
        raise ValueError(f'{source_id} is not a registered source')
    day = max(r['retrieved_at'][:10] for x in readings for r in x['records'])
    if (s.get('published') or '')[:10] >= day:
        return None
    return {'target': 'source', 'id': source_id, 'after': dict(s, published=day),
            'evidence': sorted({x['evidence']['id'] for x in readings})}


def _unconfirmed(ledger, source_id, readings, latest):
    """A forecast from this page that its new date would also vouch for but the page as last read
    does not show, or None."""
    revised = {x['pin'] for x in readings}
    for o in ledger['observations']:
        if o['source'] == source_id and not o.get('superseded_by') and o['status'] in FORWARD and o['id'] not in revised \
                and (not _shows(latest, o['value']) or (o['upper'] is not None and not _shows(latest, o['upper']))):
            return o
    return None


def _for_the_owner(pp, rule, auto, item, row, changes, latest, ledger, registry):
    """Why this reading goes to the owner instead of out unattended, or None."""
    if not auto:
        return 'automatic revisions are off'
    if item['source']['id'] not in rule['sources']:
        return 'the page is not on the same-page list'
    if latest is None:
        return 'no saved text of the page as last read'
    old = _before(ledger, {'id': row['replaces']})
    if _shows(latest, old['value']) or (old['upper'] is not None and _shows(latest, old['upper'])):
        return 'the page as last read still shows the old figure'
    if item.get('created_at', '') < _ago(SAME_NIGHT_SECONDS):
        return 'read on an earlier night'
    ok, reasons = pp.same_page_revision({'changes': [dict(c, before=_before(ledger, c)) for c in changes]}, rule, ledger, registry)
    return None if ok else reasons[0]


def _card_title(readings, registry):
    whys = '; '.join(dict.fromkeys(x['why'] for x in readings))
    if len(readings) == 1:
        return clean(f"Same-page revision to review ({whys}): {readings[0]['lines'][0]}", 200)
    s = next((x for x in registry['sources'] if x['id'] == readings[0]['source']), {})
    return clean(f"{len(readings)} same-page revisions to review from {s.get('title', readings[0]['source'])} ({whys})", 200)


def _committed(root, package_id):
    """The commit that published this package, if HEAD's history has one: a kill between the commit
    and its receipt leaves a live package that looks unpublished."""
    import subprocess
    try:
        r = subprocess.run(['git', 'log', '-1', '--format=%H', '--fixed-strings', f'--grep=catalog: apply {package_id}', 'HEAD'],
                           cwd=root, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    return r.stdout.strip() or None


def settle_revisions(root, auto=False, deadline=None):
    """Settle the night's same-page revisions, once, in the nightly policy stage.

    Every ready reading leaves this call published, on the owner's list, declined (the owner
    rejected the same reading before), obsolete or needing a maintainer; no automatic package
    outlives it. Per site figure only the newest reading counts, and only while the page as last
    read still carries its quote (a page whose text was not saved gives nothing to publish
    unattended). See _for_the_owner for what may go out unattended; the rest reach the owner as one
    card per page, and a card an older reading left for the same figure is withdrawn. A package that
    cannot publish is withdrawn and handed to the owner whole, never split or retried on a later
    night. `deadline` is a time.monotonic() after which nothing new is published. The holds are
    saved whatever happens, so a reading published before a failure is still reported."""
    from catalog_review import base, enqueue
    from editorial_review import events, queue
    from evidence_text import fold
    import publication_policy as pp
    result = {'applied': [], 'cards': [], 'withdrawn': [], 'outcomes': {}}
    reviews = {e['id']: e for e in events(root) if e.get('kind') == 'catalog_change' and 'id' in e}
    packages = {}
    for path in sorted(queue(root).glob('catalog-*.json')):
        if not _PACKAGE.fullmatch(path.stem):
            continue
        try:
            pkg = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            continue
        if isinstance(pkg, dict) and pkg.get('author') in (REVISION_AUTHOR, REVIEW_AUTHOR):
            packages[path.stem] = pkg

    def take_back(pid, reason):
        """withdraw, never over a person's decision (Defer included), and never fatal to the night."""
        try:
            if withdraw(root, pid, reason, keep_deferred=True):
                result['withdrawn'].append(pid)
        except (OSError, ValueError):
            pass  # FileExistsError included: a busy lock leaves the package for the next night

    # A crash can leave an automatic package behind. The policy admits one only within the hour it
    # was built and apply_admitted never runs one, so it could only wait: take it off the list. A
    # committed one is finished by verify_pending_deployments (its receipt is written here if the
    # kill came between the commit and the receipt); a person's decision stands.
    for pid, pkg in packages.items():
        if pkg['author'] != REVISION_AUTHOR or pkg.get('created_at', '') > _ago(3600) \
                or (queue(root)/(pid+'-publication.json')).exists() \
                or (reviews.get(pid) or {}).get('status') in ('withdrawn', 'rejected', 'applied', 'deferred'):
            continue
        commit = _committed(root, pid)
        if commit:
            from catalog_review import digest
            _save(queue(root)/(pid+'-publication.json'), {'commit': commit, 'proposal_hash': digest(pkg), 'status': 'committed', 'at': _now(),
                                                          'recovered_by': 'settle_revisions'})
            continue
        take_back(pid, 'An automatic revision not published the night it was read.')
    # What the owner rejected stays rejected, whichever hold brings the same reading back. Cards
    # still waiting for the owner, by the site figure they would replace.
    declined, waiting_cards = {}, {}
    for pid, pkg in packages.items():
        status = (reviews.get(pid) or {}).get('status')
        for c in pkg.get('changes', []):
            a = c.get('after') or {}
            if c.get('target') != 'observation':
                continue
            if status == 'rejected' and c.get('before') is None and a.get('edition_supersedes'):
                declined[(a.get('source'), a.get('metric'), a.get('year'), a.get('period'), a.get('value'), a.get('upper'))] = pid
            if pkg['author'] == REVIEW_AUTHOR and status in (None, 'pending_review') and c.get('before') is not None:
                waiting_cards.setdefault(c['id'], []).append(pid)
    holds = []
    for path in sorted(queue(root).glob('edition-*.json')):
        try:
            item = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            continue
        if isinstance(item, dict) and item.get('change') == 'revision' and item.get('status') == 'ready':
            holds.append((path, item))
    if not holds:
        return result
    newest, order = {}, (lambda i: (i.get('created_at', ''), i.get('held_ns', 0)))
    for path, item in holds:
        for row in item['records']:
            pin = row.get('replaces')
            if pin and (pin not in newest or order(item) > order(newest[pin][1])):
                newest[pin] = (path, item, row)
    outcome, lines = result['outcomes'], {}
    try:
        _settle(root, auto, deadline, holds, newest, declined, waiting_cards, result, lines, take_back, base, enqueue, fold, pp, queue)
    finally:
        settled_at = _now()
        for path, item in holds:
            states = {}
            for row in item['records']:
                pin = row.get('replaces')
                states[pin] = outcome.get(pin, 'retry: not settled') if newest.get(pin, (None,))[0] == path \
                    else 'obsolete: a newer reading of this figure'
            kinds = {v.split(':', 1)[0] for v in states.values()}
            status = ('ready' if 'retry' in kinds else 'needs_maintainer' if 'needs_maintainer' in kinds
                      else 'settled' if kinds & {'applied', 'publishing', 'card', 'declined'} else 'obsolete')
            item.update(status=status, outcomes=states, lines={pin: lines[pin] for pin in states if pin in lines}, settled_at=settled_at)
            if status == 'needs_maintainer':
                item['reason'] = next(v for v in states.values() if v.startswith('needs_maintainer'))[len('needs_maintainer: '):]
            _save(path, item)
    return result


def _settle(root, auto, deadline, holds, newest, declined, waiting_cards, result, lines, take_back, base, enqueue, fold, pp, queue):
    """settle_revisions' work, apart from the bookkeeping it must do whatever happens here."""
    outcome = result['outcomes']
    p = pp.policy(root)
    rule = p['auto_apply']['same_page_revisions']
    auto = bool(auto and p['auto_apply']['enabled'] and rule['enabled'])
    docs = base(root)
    ledger, registry = docs['site/data/ledger.json'], docs['research/sources.json']
    texts, readings = {}, []
    for pin, (path, item, row) in sorted(newest.items()):
        r = row['record']
        key = (item['source']['id'], r['metric'], r['year'], r['period'], r['value'], r['upper'])
        if key in declined:
            outcome[pin] = f'declined: the owner rejected this reading in {declined[key]}'
            continue
        url = item['source']['url']
        if url not in texts:
            texts[url] = _latest_text(root, url)
        latest = texts[url]
        if latest is not None and fold(row['quote']) not in fold(latest):
            outcome[pin] = 'obsolete: the page as last read no longer carries this reading'
            continue
        try:
            changes, evidence, said = revision_changes(root, dict(item, records=[row]), ledger)
        except Obsolete as error:
            outcome[pin] = f'obsolete: {error}'
            continue
        except (ValueError, KeyError, TypeError) as error:
            outcome[pin] = f'needs_maintainer: {str(error)[:300]}'
            continue
        lines[pin] = said[0]
        readings.append({'pin': pin, 'source': item['source']['id'], 'records': [r], 'changes': changes, 'evidence': evidence, 'lines': said,
                         'latest': latest, 'why': _for_the_owner(pp, rule, auto, item, row, changes, latest, ledger, registry)})
    pages = {}
    for x in readings:
        pages.setdefault(x['source'], []).append(x)
    unattended = []
    for source_id, xs in sorted(pages.items()):
        ready = [x for x in xs if x['why'] is None]
        if not ready:
            continue
        # The page's new date vouches for every forecast it gives: each one it no longer shows sends
        # the page's readings to the owner.
        try:
            dated = _date_change(registry, source_id, ready)
        except ValueError as error:
            for x in ready:
                x['why'] = str(error)[:200]
            continue
        missing = _unconfirmed(ledger, source_id, ready, ready[0]['latest']) if dated else None
        if missing:
            for x in ready:
                x['why'] = f"the page as last read no longer shows its {missing['year']} figure, which its new date would vouch for"
            continue
        unattended.append(ready)

    def package(units, author):
        fresh = base(root)['research/sources.json']  # an earlier package tonight may have moved a page's date
        changes, evidence = [], {}
        for unit in units:
            for x in unit:
                changes += x['changes']
                # A card says why it is one. That also keeps its id apart from an automatic package
                # withdrawn tonight with the same changes, which enqueue would otherwise hand back.
                summary = x['evidence']['summary'] if author == REVISION_AUTHOR else clean(f"For review: {x['why']}. {x['evidence']['summary']}", 2000)
                evidence[x['evidence']['id']] = dict(x['evidence'], summary=summary)
            dated = _date_change(fresh, unit[0]['source'], unit)
            if dated:
                changes.append(dated)
        flat = [x for unit in units for x in unit]
        if author == REVISION_AUTHOR:
            title = clean(f"Same-page revisions: {len(flat)} figures updated by their publishers" if len(flat) > 1
                          else f"Same-page revision: {flat[0]['lines'][0]}", 200)
        else:
            title = _card_title(flat, fresh)
        return enqueue(root, title, changes, list(evidence.values()), author=author)['id']

    def settled(xs, pid, text):
        # A card an older reading left for the same figure can no longer be the right one.
        for x in xs:
            outcome[x['pin']] = text
            for old in waiting_cards.get(x['pin'], []):
                if old != pid:
                    take_back(old, 'A newer reading of the same figure replaces this card.')

    for group in _bundle(unattended):
        flat = [x for unit in group for x in unit]
        if deadline is not None and time.monotonic() > deadline:
            for x in flat:
                x['why'] = 'not enough time left tonight to publish it'
            continue
        try:
            pid = package(group, REVISION_AUTHOR)
        except FileExistsError:
            for x in flat:
                outcome[x['pin']] = 'retry: the editorial lock was busy'
            continue
        except (ValueError, KeyError, TypeError) as error:
            for x in flat:
                x['why'] = f'it could not be packaged ({str(error)[:120]})'
            continue
        try:
            receipt = pp.auto_apply(root, pid, p)
            result['applied'].append(pid)
            settled(flat, pid, f"applied: {pid} ({receipt.get('status')})")
        except Exception as error:
            committed = True  # an unreadable receipt may stand for a live commit: never withdraw that
            try:
                path = queue(root)/(pid+'-publication.json')
                committed = path.exists() and bool(json.loads(path.read_text(encoding='utf-8')).get('commit'))
            except (OSError, ValueError):
                pass
            if committed:
                settled(flat, pid, f'publishing: {pid}')  # verify_pending_deployments finishes it
                continue
            take_back(pid, f'Not published tonight ({type(error).__name__}); handed to the owner.')
            for x in flat:
                x['why'] = f'automatic publication failed ({type(error).__name__}: {str(error)[:120]})'

    def to_owner(xs):
        """One card; False when it could not be packaged (a lone reading then needs a maintainer)."""
        try:
            pid = package([xs], REVIEW_AUTHOR)
        except FileExistsError:
            for x in xs:
                outcome[x['pin']] = 'retry: the editorial lock was busy'
            return True
        except (ValueError, KeyError, TypeError) as error:
            if len(xs) == 1:
                outcome[xs[0]['pin']] = f'needs_maintainer: {str(error)[:300]}'
            return False
        result['cards'].append(pid)
        for x in xs:
            settled([x], pid, f"card: {pid} ({x['why']})")
        return True

    for source_id, xs in sorted(pages.items()):
        waiting = [x for x in xs if x['pin'] not in outcome]
        # One card per page; a reading that cannot be packaged must not hold back the page's others.
        if waiting and not to_owner(waiting) and len(waiting) > 1:
            for x in waiting:
                to_owner([x])


def settled_since(root, since):
    """What settle_revisions did with each reading since `since` (an ISO time), for the night's
    report: read from the holds, so a policy stage that ran out of time still reports it."""
    from editorial_review import queue
    rows = []
    for path in sorted(queue(root).glob('edition-*.json')):
        try:
            item = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            continue
        if not isinstance(item, dict) or item.get('change') != 'revision' or (item.get('settled_at') or '') < since:
            continue
        for pin, text in (item.get('outcomes') or {}).items():
            kind, _, detail = text.partition(': ')
            rows.append({'kind': kind, 'detail': detail, 'replaces': pin, 'source': item['source']['id'],
                         'line': (item.get('lines') or {}).get(pin, '')})
    return rows


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
    # --revisions settles same-page revisions as the nightly policy stage does, but never publishes:
    # every one reaches the owner as a card.
    print(json.dumps(settle_revisions(root) if '--revisions' in sys.argv[1:] else materialize(root)))
