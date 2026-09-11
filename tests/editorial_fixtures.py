"""Synthetic evidence only. Never import these records into the public ledger."""
import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import editorial as ed

AS_OF = '2026-09-08T00:00:00Z'


def fixture():
    layers = ['energy', 'chips', 'infrastructure', 'models', 'applications']
    policy = ed.read(ROOT/'research/editorial-policy.json')
    policy['metrics'] = {}
    policy['candidate_focus'] = {}
    metrics, observations = [], []
    for layer in layers+['energy']:
        mid = layer+'-metric' if layer+'-metric' not in {m['id'] for m in metrics} else 'challenger'
        metrics.append({'id': mid, 'layer': layer, 'title': 'Synthetic fixture '+mid,
                        'unit': 'fixture units', 'scope': 'Fixed synthetic entity', 'geography': 'Fixture country',
                        'source_ids': ['fixture-source'], 'definition_stable': True, 'direction': 'context'})
        policy['metrics'][mid] = {'profile': 'trajectory', 'min_points': 3, 'min_span_days': 700,
                                 'max_gap_days': 400, 'cadence': 'annual', 'expected_days': 365,
                                 'monitor_days': 7, 'grace_days': 120, 'allow_change_statistics': True,
                                 'methodology': 'fixed fixture', 'period_basis': 'annual', 'source_groups': {},
                                 'context': 'Synthetic fixed-scope history.'}
        for y in [2023, 2024, 2025]:
            observations.append({'id': f'{mid}-{y}', 'metric': mid, 'year': y, 'period': str(y),
                                 'value': 100, 'upper': None, 'status': 'observation', 'precision': 'eq',
                                 'source': 'fixture-source', 'retrieved_at': '2026-09-07T00:00:00Z',
                                 'method': 'curated', 'note': ''})
    source = {'id': 'fixture-source', 'publisher': 'Synthetic test publisher', 'title': 'Synthetic test evidence',
              'url': 'https://example.org/fixture', 'published': '2026-01-01', 'layers': layers, 'license': 'Fixture only', 'provenance': 'official'}
    ledger = {'layers': [{'id': l, 'headline_metric': l+'-metric'} for l in layers], 'metrics': metrics,
              'sources': [source], 'observations': observations, 'runs': [], 'events': [], 'seed_date': '2026-09-07'}
    config = {'version': 1, 'reviewed_at': '2026-09-07T00:00:00Z',
              'slots': {l: {'metric_id': l+'-metric', 'profile': 'trajectory', 'visualization': 'snapshot', 'pin': None, 'supporting': []} for l in layers},
              'recent_limit': 3, 'recent_window_days': 45, 'recent_changes': [], 'delivery_accounting': None}
    return ledger, config, policy


def snapshot(ledger=None, config=None, policy=None, **kwargs):
    d, c, p = fixture()
    return ed.snapshot(ledger or d, config or c, policy or p, {'sources': (ledger or d)['sources']}, AS_OF, **kwargs)


def response(snap, action='KEEP', layer='energy'):
    mid = snap['config']['slots'][layer]['metric_id']
    ids = snap['features'][mid]['historical_ids'][-1:]
    claim = {'text': 'The scoped evidence supports continuity; broader outcomes require separate evidence.', 'observation_ids': ids}
    r = {'action': action, 'layer_id': layer, 'challenger_metric_id': None,
         'incumbent_dimension_scores': {k: 60 for k in snap['policy']['weights']},
         'challenger_dimension_scores': None, 'proposed_display': None, 'critical_flaw': False,
         'facts': [], 'research_followups': []}
    for field in ['reader_question', 'advantages', 'tradeoffs', 'case_for_keeping_incumbent', 'incumbent_rechart_option', 'uncertainties', 'contradictions', 'score_basis']:
        r[field] = [copy.deepcopy(claim)]
    if action in {'REPLACE_METRIC', 'ADD_SUPPORTING_CHART'}:
        r.update(challenger_metric_id='challenger', challenger_dimension_scores={k: 85 for k in snap['policy']['weights']}, proposed_display='history')
    if action == 'IMPROVE_VISUALIZATION':
        r['proposed_display'] = 'history'
    if action == 'DEMOTE':
        r['proposed_display'] = 'demoted'
        r['critical_flaw'] = True
    return r
