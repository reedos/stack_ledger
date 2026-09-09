"""Opt-in offline replay of saved documents through the production extraction and screening. No network, publication or ledger writes."""
import argparse
import copy
import json
import statistics
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from random import Random
from urllib.parse import urlparse

import research
from model_rules import DEFECTS
from source_policy import collection_for

ROOT = Path(__file__).resolve().parents[1]
# Read-only source of saved documents: a sibling checkout of the production repository.
# Never written to. The eval worktree itself starts with no .local/evidence of its own.
PRODUCTION_LOCAL = ROOT.parent / 'stack_ledger' / '.local'


def now_stamp():
    return datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')


def hostname(url):
    return (urlparse(url).hostname or '').lower()


def base_domain(host):
    """A stdlib-only approximation of the registrable domain: the last two labels.

    No public-suffix list is available offline, so this is wrong for domains like
    "co.uk"; it is only used as a last-resort fallback to guess a discovery parent.
    """
    parts = host.split('.')
    return '.'.join(parts[-2:]) if len(parts) >= 2 else host


def saved_documents(local_dir=None):
    """Every saved fetched document under an evidence folder: {'url','retrieved_at','sha256','text'}.

    The same folder also holds accepted-record and note proof files ({'record',...}); those
    are skipped by checking the exact key set. Read-only: this never writes to local_dir.
    """
    folder = (local_dir or PRODUCTION_LOCAL) / 'evidence'
    documents = []
    if not folder.is_dir():
        return documents
    for path in sorted(folder.glob('*.json')):
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if isinstance(data, dict) and set(data) == {'url', 'retrieved_at', 'sha256', 'text'}:
            documents.append(data)
    return documents


def active_lock():
    """The first research.lock/research-session.lock found, in the eval worktree or the
    production checkout the corpus is read from; None if neither is present."""
    for base in (research.LOCAL, PRODUCTION_LOCAL):
        for name in ('research.lock', 'research-session.lock'):
            path = base / name
            if path.exists():
                return path
    return None


def best_by_rank(candidates, registry):
    return min(candidates, key=lambda s: (collection_for(registry, s).get('rank', 5), s['id']))


def match_document(doc, top_sources, registry):
    """Map a saved document to a registered source and a match tier, or (None, None).

    exact: the document's own URL is a registered source's URL; used unchanged.
    host: no exact hit, but the document's host matches a registered source's host; the
      highest-ranked (lowest collection rank) source on that host is used, with its url
      replaced by the document's real url so prompts and the report show real provenance.
    discovered: no host match, but the document's host shares a base domain with a
      registered source's host; treated as a discovered child of the highest-ranked
      source on that base domain, mirroring how main() builds discovered pages during a
      live crawl (approximate: see base_domain).
    """
    host = hostname(doc['url'])
    exact = next((s for s in top_sources if s['url'] == doc['url']), None)
    if exact:
        return exact, 'exact'
    same_host = [s for s in top_sources if hostname(s['url']) == host]
    if same_host:
        matched = best_by_rank(same_host, registry)
        return dict(matched, url=doc['url']), 'host'
    base = base_domain(host) if host else None
    same_base = [s for s in top_sources if base and base_domain(hostname(s['url'])) == base] if base else []
    if same_base:
        parent = best_by_rank(same_base, registry)
        child = dict(parent, id='eval-discovered-' + research.digest(doc['url'])[:16], url=doc['url'],
                     published=None, parent_source=parent['id'],
                     title='Discovered public update \u00b7 ' + parent.get('publisher', ''))
        child.pop('index', None)
        return child, 'discovered'
    return None, None


def expected_observations(observations, source_id, related_ids):
    """Non-superseded observations this exact source contributed to a metric the document could report.

    The holdout leave-one-out set: what removing them and re-running extraction should recall.
    """
    return [o for o in observations if not o.get('superseded_by') and o['source'] == source_id and o['metric'] in related_ids]


def select_documents(documents, registry, metrics_by_id, seed, target, exclude_hosts, only_related, observations=None, holdout=False):
    """Deterministic shuffle-and-filter over the corpus. Returns (selected, stats).

    selected is a list of (document, source, match_type). stats records why documents
    that were considered were not selected, for the report's corpus section. In holdout
    mode the whole eligible corpus is scanned (no early stop) and split into documents
    whose matched source has at least one expected record and those with none; the
    sample is filled from the former first, and leftover latter candidates are counted
    as skipped rather than discarded outright (they still fill remaining slots).
    """
    top_sources = registry['sources']
    exclude = {h.lower() for h in exclude_hosts}
    eligible = sorted((d for d in documents if len(d.get('text', '')) >= 1500), key=lambda d: d['sha256'])
    Random(seed).shuffle(eligible)
    qualifying, other = [], []
    per_host = Counter()
    stats = Counter()
    unmatched_hosts = set()
    for doc in eligible:
        if not holdout and len(qualifying) >= target:
            break
        host = hostname(doc['url'])
        if host in exclude:
            stats['excluded_host'] += 1
            continue
        if per_host[host] >= 3:
            stats['per_host_cap'] += 1
            continue
        source, match = match_document(doc, top_sources, registry)
        if source is None:
            stats['unmatched_host'] += 1
            unmatched_hosts.add(host)
            continue
        related = [m for m in metrics_by_id.values() if source.get('parent_source', source['id']) in m['source_ids']]
        if only_related and not related:
            stats['no_related_metrics'] += 1
            continue
        per_host[host] += 1
        entry = (doc, source, match)
        if holdout and not expected_observations(observations or (), source['id'], {m['id'] for m in related}):
            other.append(entry)
        else:
            qualifying.append(entry)
    if holdout:
        selected = (qualifying + other)[:target]
        stats['holdout_qualifying_available'] = len(qualifying)
        stats['holdout_no_expected_skipped'] = max(0, len(other) - max(0, target - len(qualifying)))
    else:
        selected = qualifying[:target]
    corpus = {'total_saved_documents': len(documents), 'eligible_after_length_filter': len(eligible),
              'unmatched_hosts_skipped': stats['unmatched_host'], 'unmatched_host_names': sorted(unmatched_hosts),
              'excluded_host_skipped': stats['excluded_host'], 'per_host_cap_skipped': stats['per_host_cap'],
              'only_related_skipped': stats['no_related_metrics']}
    if holdout:
        corpus['holdout_qualifying_available'] = stats['holdout_qualifying_available']
        corpus['holdout_no_expected_skipped'] = stats['holdout_no_expected_skipped']
    return selected, corpus


def make_recorder(original, sink):
    """Wrap research.ollama to time each call and record a deep-copied raw response.

    Later mutation of the returned dict by extract_note/extract_observations (they snap
    evidence to the document's own bytes in place) must not change what was recorded here.
    """
    kind_by_key = {'observations': 'metric_extraction', 'notes': 'note_extraction', 'verdicts': 'review'}

    def recorder(config, system, prompt, schema):
        kind = kind_by_key.get(next(iter(schema.get('properties', {})), None), 'unknown')
        entry = {'kind': kind, 'system_chars': len(system), 'prompt_chars': len(prompt)}
        started = time.monotonic()
        try:
            result = original(config, system, prompt, schema)
        except Exception as error:
            entry.update(elapsed_seconds=round(time.monotonic() - started, 3), ok=False,
                         error=f'{type(error).__name__}: {error}')
            sink.append(entry)
            raise
        entry.update(elapsed_seconds=round(time.monotonic() - started, 3), ok=True, response=copy.deepcopy(result))
        sink.append(entry)
        return result
    return recorder


def _forbidden_fetch(*_a, **_k):
    raise AssertionError('Network fetch is not permitted in the evaluation harness; documents come from disk')


def classify_reason(reason):
    """Whether a quarantine reason came from the deterministic validators or the model reviewer."""
    head = reason.split(': ', 1)[0]
    if head in DEFECTS or reason == 'Conflicting proposal':
        return 'reviewer'
    return 'validator'


def read_proof(record_id):
    return json.loads((research.LOCAL / 'evidence' / f'{record_id}.json').read_text(encoding='utf-8'))


def note_row(doc_index, note_result, quarantine, private=False):
    candidate_id = f'd{doc_index}-n0'
    privacy = 'private' if private else 'public'
    if note_result:
        proof = read_proof(note_result['id'])
        return {'id': candidate_id, 'kind': 'note', 'outcome': 'accepted', 'title': note_result['title'],
                'summary': note_result['summary'], 'layer': note_result['layer'], 'note_kind': note_result['kind'],
                'evidence_quote': proof['evidence'][:400], 'validator_result': 'passed', 'validator_reason': None,
                'reviewer_verdict': 'supported', 'reviewer_defect': proof['review']['defect'],
                'reviewer_reason': proof['review']['reason'], 'grade': None, 'privacy': privacy}
    if quarantine:
        q = quarantine[0]
        c = q['candidate'] if isinstance(q['candidate'], dict) else {}
        stage = classify_reason(q['reason'])
        return {'id': candidate_id, 'kind': 'note', 'outcome': 'quarantined', 'title': c.get('title'),
                'summary': c.get('summary'), 'layer': c.get('layer'), 'note_kind': c.get('kind'),
                'evidence_quote': (c.get('evidence') or '')[:400] if isinstance(c.get('evidence'), str) else '',
                'validator_result': 'failed' if stage == 'validator' else 'passed',
                'validator_reason': q['reason'] if stage == 'validator' else None,
                'reviewer_verdict': 'unsupported' if stage == 'reviewer' else None,
                'reviewer_defect': q['reason'].split(': ', 1)[0] if stage == 'reviewer' else None,
                'reviewer_reason': q['reason'] if stage == 'reviewer' else None, 'grade': None, 'privacy': privacy}
    return None


def metric_rows(doc_index, accepted, quarantine):
    rows = []
    n = 0
    for record in accepted:
        proof = read_proof(record['id'])
        rows.append({'id': f'd{doc_index}-m{n}', 'kind': 'observation', 'outcome': 'accepted',
                     'metric': record['metric'], 'value': record['value'], 'period': record['period'],
                     'year': record.get('year'), 'upper': record.get('upper'),
                     'status': record['status'], 'precision': record['precision'], 'note': record.get('note', ''),
                     'evidence_quote': proof['evidence'][:400], 'validator_result': 'passed', 'validator_reason': None,
                     'reviewer_verdict': 'supported', 'reviewer_defect': proof['review']['defect'],
                     'reviewer_reason': proof['review']['reason'], 'grade': None})
        n += 1
    for q in quarantine:
        c = q['candidate'] if isinstance(q['candidate'], dict) else {}
        stage = classify_reason(q['reason'])
        evidence = c.get('evidence')
        rows.append({'id': f'd{doc_index}-m{n}', 'kind': 'observation', 'outcome': 'quarantined',
                     'metric': c.get('metric'), 'value': c.get('value'), 'period': c.get('period'),
                     'year': c.get('year'), 'upper': c.get('upper'),
                     'status': c.get('status'), 'precision': c.get('precision'), 'note': c.get('note', ''),
                     'evidence_quote': evidence[:400] if isinstance(evidence, str) else '',
                     'validator_result': 'failed' if stage == 'validator' else 'passed',
                     'validator_reason': q['reason'] if stage == 'validator' else None,
                     'reviewer_verdict': 'unsupported' if stage == 'reviewer' else None,
                     'reviewer_defect': q['reason'].split(': ', 1)[0] if stage == 'reviewer' else None,
                     'reviewer_reason': q['reason'] if stage == 'reviewer' else None, 'grade': None})
        n += 1
    return rows


def raw_metric_candidates(entry):
    """The model's own metric_extraction response for this document, unmutated (see make_recorder)."""
    for call in entry.get('model_calls', []):
        if call.get('kind') == 'metric_extraction' and call.get('ok') and isinstance(call.get('response'), dict):
            return call['response'].get('observations') or []
    return []


def candidate_fingerprint(c):
    """The same identity extract_observations/candidate_record use, minus evidence (which gets mutated in place)."""
    return tuple(c.get(k) for k in ('metric', 'year', 'period', 'value', 'upper', 'status', 'precision'))


def candidate_dispositions(entry):
    """Where each raw candidate (in model order) stopped, or None if silently dropped as a duplicate.

    entry['metric_candidates'] carries every candidate the harness actually dispositioned
    (accepted or quarantined); a raw candidate missing from it exactly duplicated a still-
    present ledger record and was dropped before validation, per extract_observations.
    """
    pool = list(enumerate(entry.get('metric_candidates') or []))
    used = set()
    dispositions = []
    for c in raw_metric_candidates(entry):
        fp = candidate_fingerprint(c)
        hit = next(((j, r) for j, r in pool if j not in used and candidate_fingerprint(r) == fp), None)
        if hit:
            used.add(hit[0])
            dispositions.append(hit[1])
        else:
            dispositions.append(None)
    return dispositions


def value_close(candidate_value, expected):
    """Within 0.5% of the expected value, or inside its upper bound for a range."""
    try:
        value = float(candidate_value)
    except (TypeError, ValueError):
        return False
    target = expected['value']
    if abs(value - target) <= abs(target) * 0.005:
        return True
    upper = expected.get('upper')
    return upper is not None and target <= value <= upper


def candidate_matches_expected(candidate, expected):
    return (candidate.get('metric') == expected['metric']
            and (candidate.get('year') == expected.get('year') or candidate.get('period') == expected.get('period'))
            and value_close(candidate.get('value'), expected))


def match_to_expected(raw_candidates, expected):
    """Greedy one-to-one match, in candidate order. Returns (matches, missed_ids) where matches
    is a {candidate_index: expected_id} map; each expected record can be claimed once."""
    remaining = list(expected)
    matches = {}
    for i, c in enumerate(raw_candidates):
        hit = next((e for e in remaining if candidate_matches_expected(c, e)), None)
        if hit:
            remaining.remove(hit)
            matches[i] = hit['id']
    return matches, [e['id'] for e in remaining]


def build_holdout_entry(entry, expected):
    expected_view = [{'id': o['id'], 'metric': o['metric'], 'value': o['value'], 'period': o['period']} for o in expected]
    raw = raw_metric_candidates(entry)
    dispositions = candidate_dispositions(entry)
    matches, missed_ids = match_to_expected(raw, expected)
    candidates = []
    for i, c in enumerate(raw):
        row = dispositions[i]
        if row is None:
            stopped, validator_reason, reviewer_defect = 'duplicate_of_existing', None, None
        elif row['outcome'] == 'accepted':
            stopped, validator_reason, reviewer_defect = 'accepted', None, None
        elif row['validator_result'] == 'failed':
            stopped, validator_reason, reviewer_defect = 'quarantined_validator', row['validator_reason'], None
        else:
            stopped, validator_reason, reviewer_defect = 'quarantined_reviewer', None, row['reviewer_defect']
        candidates.append({'candidate_index': i, 'metric': c.get('metric'), 'year': c.get('year'), 'period': c.get('period'),
                            'value': c.get('value'), 'upper': c.get('upper'), 'matched_expected_id': matches.get(i),
                            'stopped': stopped, 'validator_reason': validator_reason, 'reviewer_defect': reviewer_defect})
    false_proposals = [c for c in candidates if c['matched_expected_id'] is None]
    validator_false_rejects = [c for c in candidates if c['matched_expected_id'] and c['stopped'] == 'quarantined_validator']
    reviewer_false_rejects = [c for c in candidates if c['matched_expected_id'] and c['stopped'] == 'quarantined_reviewer']
    missed = [e for e in expected_view if e['id'] in set(missed_ids)]
    return {'expected': expected_view, 'candidates': candidates, 'matched': len(matches), 'missed': missed,
            'false_proposals': false_proposals, 'validator_false_rejects': validator_false_rejects,
            'reviewer_false_rejects': reviewer_false_rejects}


def holdout_summarize(entries):
    holdouts = [e['holdout'] for e in entries if e.get('holdout')]
    expected_total = sum(len(h['expected']) for h in holdouts)
    proposed_total = sum(len(h['candidates']) for h in holdouts)
    matched_total = sum(h['matched'] for h in holdouts)
    validator_fr = [c for h in holdouts for c in h['validator_false_rejects']]
    reviewer_fr = [c for h in holdouts for c in h['reviewer_false_rejects']]
    return {
        'documents_with_expected_records': sum(1 for h in holdouts if h['expected']),
        'documents_with_zero_expected_records': sum(1 for h in holdouts if not h['expected']),
        'expected_total': expected_total,
        'proposed_total': proposed_total,
        'matched_total': matched_total,
        'recall': round(matched_total / expected_total, 4) if expected_total else None,
        'precision': round(matched_total / proposed_total, 4) if proposed_total else None,
        'validator_false_rejects': len(validator_fr),
        'validator_false_reject_reasons': dict(Counter(c['validator_reason'] for c in validator_fr)),
        'reviewer_false_rejects': len(reviewer_fr),
        'reviewer_false_reject_defects': dict(Counter(c['reviewer_defect'] for c in reviewer_fr)),
    }


def process_document(index, doc, source, match_type, ledger_base, registry, base_config, instructions, mode, calls, holdout=False):
    data = copy.deepcopy(ledger_base)
    metrics = {m['id']: m for m in data['metrics']}
    sources = {s['id']: s for s in data['sources']}
    policy = collection_for(registry, source)
    related = [m for m in metrics.values() if source.get('parent_source', source['id']) in m['source_ids']]
    publishable = bool(source.get('parent_source') or policy.get('excerpts'))
    expected = []
    if holdout:
        expected = expected_observations(data['observations'], source['id'], {m['id'] for m in related})
        if expected:
            drop = {o['id'] for o in expected}
            data['observations'] = [o for o in data['observations'] if o['id'] not in drop]
    config = dict(base_config, _instructions=instructions, _instruction_mode=mode,
                  _coverage=research.coverage_context(research.ROOT, source))
    run = {'model_calls': 0, 'accepted': 0}
    collection = {}
    entry = {'index': index, 'document_sha256': doc['sha256'], 'document_url': doc['url'],
             'document_retrieved_at': doc['retrieved_at'], 'text_length': len(doc['text']),
             'matched_source_id': source['id'], 'match_type': match_type,
             'related_metric_ids': [m['id'] for m in related],
             'related_metric_units': {m['id']: m.get('unit') for m in related},
             'publishable': publishable, 'error': None, 'note_candidate': None, 'metric_candidates': []}
    calls.clear()
    try:
        if source.get('parent_source'):
            # The saved document keeps only readable text, not the original HTML meta tags,
            # so only the printed-dateline fallback main() uses is available here.
            inferred = research.dateline(doc['text'])
            source['published'] = inferred
            entry['published_basis'] = 'dateline' if inferred else 'unavailable'
        entry['already_noted_before_call'] = any(
            e['source'] == source['id'] and e.get('document_sha256') == research.digest(doc['text'])
            for e in data['events'])
        # Every selected document runs the note lane now, not just publishable or metric-less ones;
        # a note from a source with no excerpt permission is still measured, just marked private below.
        note_quarantine = []
        config['_document_windows'] = collection.setdefault('document_windows', [])
        note_result = research.extract_note(config, source, doc['text'], data['events'], run, note_quarantine)
        metric_quarantine = []
        accepted_records = []
        if related:
            accepted_records = research.extract_observations(
                config, source, doc['text'], related, data, metrics, sources, run, metric_quarantine, collection)
        entry['note_candidate'] = note_row(index, note_result, note_quarantine, private=not publishable)
        entry['metric_candidates'] = metric_rows(index, accepted_records, metric_quarantine)
    except Exception as error:
        entry['error'] = f'{type(error).__name__}: {error}'
    entry['windows'] = collection.get('document_windows', [])
    entry['model_calls'] = list(calls)
    entry['run'] = dict(run)
    if holdout:
        entry['holdout'] = build_holdout_entry(entry, expected)
    return entry


def summarize(entries):
    calls = [c for e in entries for c in e.get('model_calls', [])]
    durations = [c['elapsed_seconds'] for c in calls]
    metrics_all = [r for e in entries for r in e.get('metric_candidates', [])]
    notes_all = [e['note_candidate'] for e in entries if e.get('note_candidate')]
    proposed_metric = sum(len(c['response'].get('observations', [])) for c in calls
                           if c['kind'] == 'metric_extraction' and c.get('ok') and isinstance(c.get('response'), dict))
    proposed_notes = sum(len(c['response'].get('notes', [])) for c in calls
                          if c['kind'] == 'note_extraction' and c.get('ok') and isinstance(c.get('response'), dict))
    accepted_metric = [r for r in metrics_all if r['outcome'] == 'accepted']
    quarantined_validator = [r for r in metrics_all if r['outcome'] == 'quarantined' and r['validator_result'] == 'failed']
    quarantined_reviewer = [r for r in metrics_all if r['outcome'] == 'quarantined' and r['validator_result'] == 'passed']
    accepted_notes = [r for r in notes_all if r['outcome'] == 'accepted']
    quarantined_notes = [r for r in notes_all if r['outcome'] == 'quarantined']
    duplicate_of_existing = max(0, proposed_metric - (len(accepted_metric) + len(quarantined_validator) + len(quarantined_reviewer)))
    return {
        'documents': len(entries),
        'documents_with_errors': sum(1 for e in entries if e.get('error')),
        'model_calls': len(calls),
        'model_calls_failed': sum(1 for c in calls if not c.get('ok')),
        'mean_seconds_per_call': round(statistics.mean(durations), 2) if durations else None,
        'median_seconds_per_call': round(statistics.median(durations), 2) if durations else None,
        'metric_candidates_proposed': proposed_metric,
        'metric_candidates_passed_validators': len(accepted_metric) + len(quarantined_reviewer),
        'metric_candidates_accepted': len(accepted_metric),
        'metric_candidates_quarantined_by_validators': len(quarantined_validator),
        'metric_quarantine_validator_reasons': dict(Counter(r['validator_reason'] for r in quarantined_validator)),
        'metric_candidates_quarantined_by_reviewer': len(quarantined_reviewer),
        'metric_quarantine_reviewer_defects': dict(Counter(r['reviewer_defect'] for r in quarantined_reviewer)),
        'metric_candidates_duplicate_of_existing': duplicate_of_existing,
        'notes_proposed': proposed_notes,
        'notes_accepted': len(accepted_notes),
        'notes_accepted_private': sum(1 for r in accepted_notes if r.get('privacy') == 'private'),
        'notes_quarantined': len(quarantined_notes),
        'documents_with_zero_candidates': sum(1 for e in entries if not e.get('metric_candidates') and not e.get('note_candidate') and not e.get('error')),
    }


def render_holdout_section(entries, holdout_summary):
    lines = ['## Holdout (leave-one-out recall)', '', '| metric | value |', '|---|---|']
    for key, value in holdout_summary.items():
        lines.append(f'| {key} | {value} |')
    lines += ['', '| doc | source | expected | matched | missed | false proposals |', '|---|---|---|---|---|---|']
    for e in entries:
        h = e.get('holdout')
        if not h:
            continue
        missed = ', '.join(f"{m['metric']}={m['value']}({m['period']})" for m in h['missed']) or '(none)'
        lines.append(f"| d{e['index']} | {e['matched_source_id']} | {len(h['expected'])} | {h['matched']} | {missed} | {len(h['false_proposals'])} |")
    return '\n'.join(lines)


def render_report(meta, entries, summary):
    lines = [f"# Extraction evaluation \u2014 {meta['started_at']}", '',
             f"Model: `{meta['model']}` \u00b7 Instructions: **{meta['instruction_mode']}** \u00b7 "
             f"Screening version: `{meta['screening_version']}` \u00b7 Seed: {meta['seed']} \u00b7 Holdout: {meta.get('holdout', False)}",
             f"Documents requested: {meta['requested_documents']} \u00b7 Documents selected: {len(entries)}",
             f"Corpus: {json.dumps(meta['corpus'])}", '', '## Summary', '', '| metric | value |', '|---|---|']
    for key, value in summary.items():
        lines.append(f'| {key} | {value} |')
    lines += ['', '## Documents', '']
    for e in entries:
        lines.append(f"### d{e['index']} \u2014 {e['matched_source_id']} ({e['match_type']} match)")
        lines.append('')
        lines.append(f"- URL: {e['document_url']}")
        related = ', '.join(f"{mid} ({meta['metric_units'].get(mid) or 'n/a'})" for mid in e['related_metric_ids']) or '(none)'
        lines.append(f"- Related metrics: {related}")
        lines.append(f"- Text length: {e['text_length']} characters")
        for w in e.get('windows', []):
            pct = round(100 * w['exposed_characters'] / w['document_characters'], 1) if w['document_characters'] else 0.0
            lines.append(f"- Windows coverage ({w['purpose']}): {pct}% ({w['exposed_characters']}/{w['document_characters']} chars)")
        if e.get('error'):
            lines.append(f"- ERROR: {e['error']}")
        rows = list(e.get('metric_candidates') or []) + ([e['note_candidate']] if e.get('note_candidate') else [])
        if rows:
            lines += ['', '| id | metric/kind | value | period | status/precision | claim / note text | evidence quote | validator | reviewer | grade |',
                      '|---|---|---|---|---|---|---|---|---|---|']
            for r in rows:
                if r['kind'] == 'note':
                    metric = r.get('note_kind') or ''
                    status = r.get('layer') or ''
                    precision = ''
                    prefix = '[private] ' if r.get('privacy') == 'private' else ''
                    claim = f"{prefix}{r.get('title', '')} \u2014 {r.get('summary', '')}"
                    value = period = ''
                else:
                    metric = r.get('metric') or ''
                    status = r.get('status') or ''
                    precision = r.get('precision') or ''
                    claim = r.get('note') or ''
                    value = r.get('value', '')
                    period = r.get('period', '')
                validator = 'passed' if r['validator_result'] == 'passed' else f"failed: {r['validator_reason']}"
                if r.get('reviewer_verdict') is None:
                    reviewer = '\u2014'
                elif r['reviewer_verdict'] == 'supported':
                    reviewer = f"supported ({r['reviewer_defect']})"
                else:
                    reviewer = f"unsupported ({r['reviewer_defect']}): {r['reviewer_reason']}"
                quote = (r.get('evidence_quote') or '').replace('|', '\\|').replace('\n', ' ')[:400]
                claim = claim.replace('|', '\\|').replace('\n', ' ')
                validator = validator.replace('|', '\\|')
                reviewer = reviewer.replace('|', '\\|')
                lines.append(f"| {r['id']} | {metric} | {value} | {period} | {status}/{precision} | {claim} | {quote} | {validator} | {reviewer} | grade: |")
        else:
            lines.append('')
            lines.append('(no candidates)')
        lines.append('')
    if summary.get('holdout'):
        lines += ['', render_holdout_section(entries, summary['holdout'])]
    return '\n'.join(lines)


def build_grades_template(entries):
    template = {}
    for e in entries:
        for r in e.get('metric_candidates', []):
            template[r['id']] = None
        if e.get('note_candidate'):
            template[e['note_candidate']['id']] = None
    return template


def load_instructions(root, mode):
    if mode == 'brief':
        return (root / 'research/MODEL_BRIEF.md').read_text(encoding='utf-8')
    return (root / 'research/CONSTITUTION.md').read_text(encoding='utf-8') + '\n' + (root / 'research/OPERATING_GUIDE.md').read_text(encoding='utf-8')


def run(args):
    blocking = active_lock()
    if blocking:
        print(f'Refusing to run: {blocking} exists; a research session may be active.', file=sys.stderr)
        return 2
    documents = saved_documents()
    if not documents:
        print(f'No saved documents found under {PRODUCTION_LOCAL / "evidence"}.', file=sys.stderr)
        return 1
    ledger = json.loads((research.ROOT / 'site/data/ledger.json').read_text(encoding='utf-8'))
    registry = json.loads((research.ROOT / 'research/sources.json').read_text(encoding='utf-8'))
    base_config = json.loads((research.ROOT / 'research/runtime.json').read_text(encoding='utf-8'))
    mode = args.instructions or base_config.get('instructions', 'full')
    metrics_by_id = {m['id']: m for m in ledger['metrics']}
    selected, corpus = select_documents(documents, registry, metrics_by_id, args.seed, args.documents,
                                         args.exclude_hosts, args.only_related,
                                         observations=ledger['observations'], holdout=args.holdout)

    out = Path(args.out) if args.out else ROOT / '.local/evaluations' / f'extraction-{now_stamp()}'
    out.mkdir(parents=True, exist_ok=True)

    instructions = load_instructions(research.ROOT, mode)
    started_at = research.now()
    original_ollama = research.ollama
    original_fetch = research.Fetcher.fetch
    original_get = research.Fetcher.get
    original_fetch_json = research.Fetcher.fetch_json
    calls = []
    research.ollama = make_recorder(original_ollama, calls)
    research.Fetcher.fetch = _forbidden_fetch
    research.Fetcher.get = _forbidden_fetch
    research.Fetcher.fetch_json = _forbidden_fetch
    entries = []
    try:
        # Read the saved documents first (done above); only now repoint LOCAL so every
        # proof this run saves lands under --out, never in the production .local/evidence.
        research.LOCAL = out / 'local'
        for index, (doc, source, match_type) in enumerate(selected):
            entries.append(process_document(index, doc, source, match_type, ledger, registry, base_config,
                                             instructions, mode, calls, holdout=args.holdout))
    finally:
        research.ollama = original_ollama
        research.Fetcher.fetch = original_fetch
        research.Fetcher.get = original_get
        research.Fetcher.fetch_json = original_fetch_json

    finished_at = research.now()
    summary = summarize(entries)
    if args.holdout:
        summary['holdout'] = holdout_summarize(entries)
    meta = {'model': base_config['model'], 'screening_version': base_config.get('screening_version'),
            'instruction_mode': mode, 'seed': args.seed, 'requested_documents': args.documents,
            'exclude_hosts': sorted(args.exclude_hosts), 'only_related': args.only_related, 'holdout': args.holdout,
            'started_at': started_at, 'finished_at': finished_at, 'corpus': corpus,
            'metric_units': {m['id']: m.get('unit') for m in ledger['metrics']}}
    results = {'config': {'model': base_config['model'], 'ollama_url': base_config.get('ollama_url'),
                           'screening_version': base_config.get('screening_version'),
                           'model_timeout_seconds': base_config.get('model_timeout_seconds'),
                           'max_candidates_per_document': base_config.get('max_candidates_per_document')},
               'model': base_config['model'], 'screening_version': base_config.get('screening_version'),
               'instruction_mode': mode, 'seed': args.seed, 'requested_documents': args.documents,
               'exclude_hosts': sorted(args.exclude_hosts), 'only_related': args.only_related, 'holdout': args.holdout,
               'started_at': started_at, 'finished_at': finished_at, 'corpus': corpus,
               'documents': entries, 'summary': summary}
    (out / 'results.json').write_text(json.dumps(results, indent=2, ensure_ascii=False, default=str), encoding='utf-8')
    (out / 'report.md').write_text(render_report(meta, entries, summary), encoding='utf-8')
    (out / 'grades.template.json').write_text(json.dumps(build_grades_template(entries), indent=2), encoding='utf-8')
    print(json.dumps({'out': str(out), 'summary': summary}, indent=2))
    return 0


def score(args):
    grades_path = Path(args.grade)
    grades = json.loads(grades_path.read_text(encoding='utf-8'))
    out = Path(args.out) if args.out else grades_path.parent
    results = json.loads((out / 'results.json').read_text(encoding='utf-8'))
    entries = results['documents']
    metrics_all = [r for e in entries for r in e.get('metric_candidates', [])]
    notes_all = [e['note_candidate'] for e in entries if e.get('note_candidate')]

    def graded(rows):
        return [(r, grades.get(r['id'])) for r in rows if grades.get(r['id']) in {'correct', 'incorrect', 'uncertain'}]

    accepted = [r for r in metrics_all if r['outcome'] == 'accepted']
    accepted_graded = graded(accepted)
    correct_accepted = sum(1 for _, g in accepted_graded if g == 'correct')
    incorrect_accepted = [r for r, g in accepted_graded if g == 'incorrect']
    precision = correct_accepted / len(accepted_graded) if accepted_graded else None

    validator_q = [r for r in metrics_all if r['outcome'] == 'quarantined' and r['validator_result'] == 'failed']
    validator_q_graded = graded(validator_q)
    validator_false_reject = (sum(1 for _, g in validator_q_graded if g == 'correct') / len(validator_q_graded)
                               if validator_q_graded else None)

    reviewer_q = [r for r in metrics_all if r['outcome'] == 'quarantined' and r['validator_result'] == 'passed']
    reviewer_q_graded = graded(reviewer_q)
    reviewer_false_reject = (sum(1 for _, g in reviewer_q_graded if g == 'correct') / len(reviewer_q_graded)
                              if reviewer_q_graded else None)
    reviewer_false_accept = (sum(1 for _, g in accepted_graded if g == 'incorrect') / len(accepted_graded)
                              if accepted_graded else None)

    note_accepted = [r for r in notes_all if r['outcome'] == 'accepted']
    note_accepted_graded = graded(note_accepted)
    note_correct = sum(1 for _, g in note_accepted_graded if g == 'correct')
    note_incorrect = [r for r, g in note_accepted_graded if g == 'incorrect']
    note_precision = note_correct / len(note_accepted_graded) if note_accepted_graded else None

    all_ids = {r['id'] for r in metrics_all} | {r['id'] for r in notes_all}
    ungraded = sorted(cid for cid in all_ids if grades.get(cid) not in {'correct', 'incorrect', 'uncertain'})

    def fmt(x):
        return 'n/a (nothing graded)' if x is None else f'{x:.1%}'

    lines = ['# Scored extraction evaluation', '', f'Grades file: `{grades_path}`', f'Results: `{out / "results.json"}`', '',
              '| metric | value |', '|---|---|',
              f'| precision of accepted observations (correct/accepted) | {fmt(precision)} ({correct_accepted}/{len(accepted_graded)}) |',
              f'| validator false-reject rate (quarantined-but-correct / quarantined by validators) | {fmt(validator_false_reject)} ({len(validator_q_graded) and sum(1 for _, g in validator_q_graded if g == "correct")}/{len(validator_q_graded)}) |',
              f'| reviewer false-reject rate (quarantined-but-correct / quarantined by reviewer) | {fmt(reviewer_false_reject)} ({len(reviewer_q_graded) and sum(1 for _, g in reviewer_q_graded if g == "correct")}/{len(reviewer_q_graded)}) |',
              f'| reviewer false-accept rate (accepted-but-incorrect / accepted) | {fmt(reviewer_false_accept)} ({len(incorrect_accepted)}/{len(accepted_graded)}) |',
              f'| note precision (correct/accepted) | {fmt(note_precision)} ({note_correct}/{len(note_accepted_graded)}) |',
              f'| ungraded candidates | {len(ungraded)} |', '']
    incorrect_all = incorrect_accepted + note_incorrect
    lines.append('## Incorrect accepted items')
    lines.append('')
    if not incorrect_all:
        lines.append('(none)')
    else:
        for r in incorrect_all:
            if r['kind'] == 'note':
                lines.append(f"- `{r['id']}`: note \u2014 {r.get('title')}: {r.get('summary')}")
            else:
                lines.append(f"- `{r['id']}`: {r.get('metric')} = {r.get('value')} ({r.get('period')}, {r.get('status')})")
    scored_path = out / 'scored.md'
    scored_path.write_text('\n'.join(lines), encoding='utf-8')
    print('\n'.join(lines))
    return 0


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--documents', type=int, default=24)
    parser.add_argument('--seed', type=int, default=1)
    parser.add_argument('--instructions', choices=['full', 'brief'], default=None)
    parser.add_argument('--exclude-hosts', nargs='*', default=['stockanalysis.com'])
    parser.add_argument('--only-related', action='store_true')
    parser.add_argument('--holdout', action='store_true',
                         help='Leave-one-out recall mode: remove each selected source\'s own related observations before extraction and score recall against them')
    parser.add_argument('--out', type=str, default=None)
    parser.add_argument('--grade', type=str, default=None, help='Score a filled grades JSON against a previous run; writes scored.md alongside it')
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    if args.grade:
        return score(args)
    return run(args)


if __name__ == '__main__':
    sys.exit(main())
