"""Deliverable 2/5: grade C/D reports (News report / Social post events), automatic
confirmation/contradiction against later official observations, and human-only retraction.

Grade itself is derived by source_policy.grade_for -- a report is simply what a note event
becomes when its source's deterministic grade is C or D (see validate.event_valid). This
module never publishes anything: reconcile_confirmations is a pure function research.py's
publisher calls on its own in-memory ledger before writing it, and retract() is the one
panel-triggered write, gated on an already-authorized reviewer string supplied by the caller.
"""
import json
from datetime import date, datetime, timezone

from validate import require, text, REPORT_KINDS

EXPIRY_DAYS = 90


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


def about_ids(root, policy, title, summary):
    """Deterministic project/company linkage -- never the model's choice.

    A source's own reviewed company_id is the primary link; a delivery.json project whose
    name appears in the note's own text adds a bounded, exact-substring match. No fuzzy
    matching, no scoring: this is presentation linkage, not a catalog change.
    """
    ids = []
    company = (policy or {}).get('company_id')
    if company:
        ids.append(company)
    haystack = ((title or '') + ' ' + (summary or '')).lower()
    try:
        delivery = json.loads((root/'research/delivery.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        delivery = {}
    for p in delivery.get('projects', []):
        name = (p.get('name') or '').strip()
        if len(name) >= 4 and name.lower() in haystack and p.get('id') and p['id'] not in ids:
            ids.append(p['id'])
    return ids[:5]


def report_kind(policy):
    """News report unless the source is registered under the official-social-accounts rank."""
    return 'Social post' if (policy or {}).get('rank') == 6 else 'News report'


def within_precision(claimed, observation):
    """Whether a claimed value is close enough to an official record to count as confirming it.

    The official record's own precision sets the tolerance: eq/approx allow a small reading
    difference (rounding, unit-of-account noise), gt/lt check the stated inequality, range
    checks the disclosed interval. Never a fuzzy percentage on top of an already-loose bound.
    """
    v = observation['value']
    if observation['precision'] == 'eq':
        return abs(claimed-v) <= max(abs(v)*0.01, 1e-9)
    if observation['precision'] == 'approx':
        return abs(claimed-v) <= max(abs(v)*0.1, 1e-9)
    if observation['precision'] == 'gt':
        return claimed > v
    if observation['precision'] == 'lt':
        return claimed < v
    if observation['precision'] == 'range':
        upper = observation.get('upper')
        return v <= claimed <= (upper if upper is not None else v)
    return False


def confirmation_match(report, observations):
    """(confirmed_by|contradicted_by, observation_id) for the first same metric+period official
    record, or None when nothing yet covers that metric and period. A report with no metric_id
    (the common case today: no approved metric maps to a news/social source) never matches."""
    metric_id = report.get('metric_id')
    if not metric_id:
        return None
    candidates = [o for o in observations if o['metric'] == metric_id and o['period'] == report.get('period') and not o.get('superseded_by')]
    if not candidates:
        return None
    for o in candidates:
        if within_precision(report['value'], o):
            return ('confirmed_by', o['id'])
    return ('contradicted_by', candidates[0]['id'])


def confirmation_only_change(old, new):
    """True when `new` differs from `old` in exactly its confirmation field -- the one
    in-place mutation deliverable 2 authorizes an ordinary monitoring run to make to an
    already-published report event."""
    if not isinstance(old, dict) or not isinstance(new, dict) or set(old) != set(new):
        return False
    changed = [k for k in old if old[k] != new[k]]
    return changed == ['confirmation']


def reconcile_confirmations(events, observations):
    """Deterministic, metric+period matching only -- never a model call. Returns
    (updated_events, changed_ids); a report is only ever touched while its confirmation is
    still 'unconfirmed', carries matching fields, and has not been retracted, so a human
    retraction or an earlier confirmation is never silently overwritten."""
    changed = []
    updated = []
    for e in events:
        if e.get('kind') in REPORT_KINDS and e.get('confirmation') == 'unconfirmed' and e.get('metric_id') and not e.get('retracted'):
            match = confirmation_match(e, observations)
            if match:
                kind, oid = match
                e = dict(e, confirmation=f'{kind}:{oid}')
                changed.append(e['id'])
        updated.append(e)
    return updated, changed


def effective_confirmation(event, as_of=None):
    """Display state: an 'unconfirmed' report older than EXPIRY_DAYS reads as expired. The
    stored field itself stays 'unconfirmed' -- expiry is a display fact, not a rewrite; the
    data keeps the honest history of what was and was not independently confirmed."""
    confirmation = event.get('confirmation', 'unconfirmed')
    if confirmation != 'unconfirmed':
        return confirmation
    reported = event.get('reported_on') or event.get('date')
    if not reported:
        return confirmation
    today = as_of or datetime.now(timezone.utc).date()
    age = (today - date.fromisoformat(reported)).days
    return 'expired' if age > EXPIRY_DAYS else confirmation


def retract(root, event_id, reviewer, rationale, at=None, identity=None):
    """The one write in this module: a human marks an already-published report retracted.

    Mirrors find_feeds.register()'s atomic write-validate-rollback shape and
    editorial_review.append_event's audit-log pattern. `reviewer` must already be an
    authorized reviewer string -- this function does not itself check identity, matching how
    research_control.py resolves `findings_review.reviewer(root, ident)` before calling any
    other review/catalog action.
    """
    from atomic_json import save
    from editorial_review import locked, append_event, channel_fields
    from validate import validate as validate_ledger
    require(bool(reviewer and reviewer.strip()), 'Retraction needs an authorized reviewer')
    require(bool(rationale and rationale.strip()), 'Retraction needs a rationale')
    text(rationale, 500)
    at = at or now()
    path = root/'site/data/ledger.json'
    docs_path = root/'docs/data/ledger.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    events = {e['id']: e for e in data['events']}
    event = events.get(event_id)
    require(event is not None, 'Report not found')
    require(event['kind'] in REPORT_KINDS, 'Only a News report or Social post event can be retracted')
    require(not event.get('retracted'), 'Report already retracted')
    updated = dict(event, retracted=True, retraction_reason=rationale, retracted_at=at, retracted_by=reviewer)
    data['events'] = [updated if e['id'] == event_id else e for e in data['events']]
    validate_ledger(data)
    originals = {p: p.read_bytes() for p in (path, docs_path) if p.exists()}
    try:
        save(path, data)
        # Mirrors site/data/ledger.json -> docs/data/ledger.json exactly (a raw byte copy,
        # the same way build.py's shutil.copytree(site/data, docs/data) does it), the same
        # pairing every other public data change keeps in sync (ALLOWED_CHANGES in
        # research.py); a full `build()` is a separate, maintainer-run step (it targets the
        # live checkout by its own fixed ROOT, not this function's root, so it is never
        # called from here).
        if docs_path.exists():
            docs_path.write_bytes(path.read_bytes())
        with locked(root):
            append_event(root, dict({'id': 'retract-'+event_id, 'kind': 'report_retraction',
                'event_id': event_id, 'status': 'retracted', 'reviewer': reviewer,
                'rationale': rationale, 'at': at}, **channel_fields(identity)))
    except Exception:
        for p, b in originals.items():
            p.write_bytes(b)
        raise
    return {'id': event_id, 'status': 'retracted', 'at': at}
