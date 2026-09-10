"""Promote a grade C/D report into a private, evidence-linked catalog draft.

A report is deliberately not a project -- it can never create a catalog object on its own.
This module builds one catalog_change package from a single report event so a human reviewer
can decide, in the existing Decisions queue, whether the coverage is worth tracking. It never
writes research/delivery.json directly: catalog_review.enqueue() is the only write, exactly as
every other private draft (catalog_recommender.py) already goes through it.

Deterministic, bounded extraction only -- no model call, no gazetteer, no fuzzy matching:
  - name/location come only from the report's own headline, split on its last literal ' in '
    (see site_text). A headline that never says "in <somewhere>", or whose surviving name or
    location fragment is implausibly short or lower-cased, names no specific site and is
    refused rather than guessed at.
  - owner comes only from the report's own source's *registered* company_id -- the same
    structured link reports.about_ids already uses -- never parsed out of prose. Absent that,
    the draft says plainly that no owner was named.
  - Every field the schema requires but a single report cannot possibly supply (category,
    horizon, grid interconnection, and any numeric observation) is left as an explicit, honest
    placeholder for a later, better-evidenced update -- never invented. No megawatts, owner or
    stage is ever inferred from prose.

The package's author is 'Report promotion (owner action)', which is not on
publication-policy.json's auto_apply allowlist, so it always waits for the owner's approval in
the Decisions feed like any other catalog change.
"""
import hashlib
import json

from catalog_review import enqueue, base, package as load_package
from editorial_review import events, append_event, locked, channel_fields, now
from source_policy import collection_for
from validate import require, REPORT_KINDS

NOT_NAMED = 'Not named in this report.'
NOT_ESTABLISHED = {
    'category': 'Category not established by this single report; confirm before publishing.',
    'horizon': 'Timeline not established by this single report; confirm before publishing.',
    'grid': 'Grid interconnection not established by this single report; confirm before publishing.',
}


def site_text(title):
    """(name, location) parsed from a report's own headline, or None when it names no
    specific site. The last literal ' in <place>' in the title is the location; everything
    before it is the name. No model, no gazetteer, no fuzzy matching: a headline that never
    says where, or whose surviving fragments are implausibly short or not place-like, is
    refused rather than guessed at."""
    idx = title.rfind(' in ')
    if idx == -1:
        return None
    name = title[:idx].strip(' .,;:-"\'')
    location = title[idx+4:].strip(' .,;:-"\'')
    if len(name) < 6 or len(location) < 2 or not location[0].isupper():
        return None
    return name, location


def _owner(root, ledger, registry, report):
    """The report's own source's registered company_id, resolved to that company's reviewed
    name -- (name, company_id), or (None, None) when the source names no company. Never a
    guess parsed out of the headline or summary."""
    sources = {s['id']: s for s in ledger['sources']}
    source = sources.get(report['source'])
    if source is None:
        return None, None
    company_id = collection_for(registry, source).get('company_id')
    if not company_id:
        return None, None
    try:
        ecosystem = json.loads((root/'research/ecosystem.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None, None
    company = next((c for c in ecosystem.get('companies', []) if c['id'] == company_id), None)
    return (company['name'], company_id) if company else (None, None)


def _unique_id(existing, candidate):
    if candidate not in existing:
        return candidate
    n = 2
    while f'{candidate}-{n}' in existing:
        n += 1
    return f'{candidate}-{n}'


def _retain_evidence(root, report):
    """Retains the report's own text (never a new network fetch) under the same
    content-addressed evidence store catalog_review.enqueue checks against."""
    body = json.dumps({'report_id': report['id'], 'title': report['title'], 'summary': report['summary'],
                        'quote': report.get('quote', '')}, ensure_ascii=False, sort_keys=True).encode('utf-8')
    sha = hashlib.sha256(body).hexdigest()
    path = root/'.local/catalog-evidence'/(sha+'.txt')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    return sha


def already_promoted(root, report_id):
    """The existing package id from this report's own promotion audit event, or None."""
    for e in reversed(events(root)):
        if e.get('kind') == 'report_promotion' and e.get('report_id') == report_id:
            return e.get('package_id')
    return None


def promote(root, report_id, reviewer, identity=None):
    """Build (or, idempotently, return) the catalog_change package that tracks this report as
    a status-unverified project draft. {'package': the package dict, 'already_promoted': bool}.

    Never writes the catalog: only catalog_review.enqueue() (the existing private review-queue
    write) and the editorial audit log are touched, exactly like every other private draft.
    """
    require(bool(reviewer and reviewer.strip()), 'Promotion needs an authorized reviewer')
    ledger = json.loads((root/'site/data/ledger.json').read_text(encoding='utf-8'))
    report = next((e for e in ledger['events'] if e.get('id') == report_id), None)
    require(report is not None, 'Report not found')
    require(report.get('kind') in REPORT_KINDS, 'Only a News report or Social post event can be tracked')
    require(not report.get('retracted'), 'Retracted reports cannot be tracked')

    existing = already_promoted(root, report_id)
    if existing:
        return {'package': load_package(root, existing), 'already_promoted': True}

    site = site_text(report['title'])
    require(site is not None, 'this report does not name a site; nothing to track')
    name, location = site

    registry = json.loads((root/'research/sources.json').read_text(encoding='utf-8'))
    owner, company_id = _owner(root, ledger, registry, report)

    delivery = base(root)['research/delivery.json']
    project_id = _unique_id({p['id'] for p in delivery['projects']},
                             'report-'+hashlib.sha256(report_id.encode('utf-8')).hexdigest()[:12])

    outlet, layer = report['outlet'], report['layer']
    after = {
        'id': project_id, 'name': name, 'layer': layer, 'owner': owner or NOT_NAMED, 'location': location,
        'category': NOT_ESTABLISHED['category'], 'stage': 'status-unverified',
        'ai_relationship': (f'Reported by {outlet} as {layer}-layer AI buildout coverage; independent '
                             'confirmation of the AI relationship is not yet available.'),
        'observations': [], 'horizon': NOT_ESTABLISHED['horizon'], 'grid': NOT_ESTABLISHED['grid'],
        'next_evidence': (f'Independent confirmation of "{name}" beyond {outlet}: an official statement, '
                           'filing or additional independent report naming site, capacity and owner.'),
        'milestones': [{'date': report['date'], 'summary': report['summary'], 'source': report['source']}],
    }
    if company_id:
        after['company_ids'] = [company_id]

    sources_by_id = {s['id']: s for s in ledger['sources']}
    source = sources_by_id[report['source']]
    sha = _retain_evidence(root, report)
    evidence = [{'id': report['id'], 'url': source['url'], 'published_at': report['date'],
                 'retrieved_at': report['retrieved_at'], 'sha256': sha, 'summary': report['summary']}]

    p = enqueue(root, (f'Track report as project: {name}')[:200],
                [{'target': 'project', 'id': project_id, 'after': after, 'evidence': [report['id']]}],
                evidence, author='Report promotion (owner action)')

    with locked(root):
        append_event(root, dict({'id': 'promote-'+report_id, 'kind': 'report_promotion', 'report_id': report_id,
                                  'package_id': p['id'], 'reviewer': reviewer, 'at': now()}, **channel_fields(identity)))
    return {'package': p, 'already_promoted': False}
