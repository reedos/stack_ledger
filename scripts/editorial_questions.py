"""Typed bounded research questions in the existing private review-candidate queue."""
import re

import editorial as ed
from validate import require


QUESTIONS = {
    'energy': ('Find comparable historical data-center demand estimates within a consistent methodology.',
               'Earlier historical consumption with scope and publication vintage.',
               'Forecasts counted as actuals; all-data-center demand relabeled AI-only; synthetic backfills.'),
    'chips': ('Extend the reviewed packaging capacity history and verify estimate revisions.',
              'Dated year-end throughput ranges with a consistent packaging definition and source lineage.',
              'Wafer fabrication, accelerator shipments and packaging throughput treated as interchangeable.'),
    'infrastructure': ('Establish operating capacity for individual Abilene phases and their campus relationship.',
                       'Dated disjoint phase identifiers, IT versus facility power, commissioning and actual workload evidence.',
                       'Parent plus phase totals; silence interpreted as delay; unknown capacity treated as zero.'),
    'models': ('Find a fixed-capability or cost-of-useful-work successor to a named input-token price.',
               'Repeated standardized tasks with benchmark version, quality, latency, output/reasoning tokens, tools, retries and total cost.',
               'Different model input prices treated as equal capability; code volume or list prices treated as useful work.'),
    'applications': ('Extend paid-trip history and identify separately measured digital, physical or scientific outcomes.',
                     'Dated paid-trip disclosures with service footprint; independently supported outcomes with comparison, quality and oversight.',
                     'Trips equated with economic benefit; adoption equated with productivity; unrelated outcomes blended into an index.')}


def seed_questions(snap):
    result = []
    for layer, (question, target, excluded) in QUESTIONS.items():
        slot = snap['config']['slots'][layer]
        metric = next(m for m in snap['metrics'] if m['id'] == slot['metric_id'])
        source_ids = list(metric['source_ids'])
        if layer == 'models' and any(s['id'] == 'stanford-cost' for s in snap['sources']):
            source_ids.append('stanford-cost')
        q = {'question': question, 'layer': layer, 'entity_phase': metric.get('project') or metric.get('company') or metric['scope'],
             'current_interpretation': metric['scope'], 'target_evidence': target, 'excluded_evidence': excluded,
             'eligible_sources': sorted(set(source_ids)),
             'contradiction_search': 'Look for corrections, reversals, scope changes, negative findings and explicit contrary evidence on the approved sources.',
             'cadence': 'monthly', 'budget': 4,
             'stop_conditions': 'Stop at the document/time budget or a documented answer. Record inaccessible, conflicting or insufficient evidence; do not widen source policy.'}
        ed.validate_question(q, snap)
        result.append(q)
    return result


def enqueue_questions(root, snap):
    from editorial_review import queue, locked, save
    ids = []
    with locked(root):
        for q in seed_questions(snap):
            qid = 'question-'+ed.hashed(q)[:24]
            path = queue(root)/(qid+'.json')
            if not path.exists():
                save(path, {'kind':'research_question', 'id':qid, 'question':q,
                            'review_required':True, 'status':'pending_review', 'evidence_snapshot_hash':snap['snapshot_hash']})
            ids.append(qid)
    return ids


def load_question(root, qid):
    from editorial_review import queue
    require(re.fullmatch('question-[0-9a-f]{24}', qid), 'Invalid question ID')
    item = ed.read(queue(root)/(qid+'.json'))
    require(item['kind'] == 'research_question' and item['id'] == qid, 'Not a research question')
    require(qid == 'question-'+ed.hashed(item['question'])[:24], 'Question changed')
    return item


def record_question_review(root, qid, reviewer, rationale, at, *, human_confirm):
    from editorial_review import append_event, locked
    item = load_question(root, qid)
    policy = ed.read(root/'research/editorial-policy.json')
    require(human_confirm is True and reviewer in policy['reviewers'] and rationale.strip(), 'Human question approval required')
    with locked(root):
        append_event(root, {'id':qid, 'kind':'research_question', 'status':'approved', 'reviewer':reviewer,
                            'at':at, 'rationale':rationale, 'question_hash':ed.hashed(item['question']),
                            'source_policy_hash':ed.hashed(ed.read(root/'research/sources.json'))})


def approved_question(root, qid):
    from editorial_review import events
    q = load_question(root, qid)['question']
    approval = next((e for e in reversed(events(root)) if e['id'] == qid and e['status'] in {'approved','rejected','superseded'}), None)
    policy = ed.read(root/'research/editorial-policy.json')
    require(approval and approval['status'] == 'approved' and approval['reviewer'] in policy['reviewers'], 'Question needs human approval')
    require(approval['question_hash'] == ed.hashed(q) and approval['source_policy_hash'] == ed.hashed(ed.read(root/'research/sources.json')), 'Question/source policy approval is stale')
    require(set(q['eligible_sources']) <= {s['id'] for s in ed.read(root/'research/sources.json')['sources']}, 'Question cannot widen sources')
    return q


def validate_result(q, outcome, observation_ids, ledger):
    require(outcome in ed.OUTCOMES, 'Invalid research outcome')
    obs = {o['id']: o for o in ledger['observations']}
    metrics = {m['id']: m for m in ledger['metrics']}
    require(set(observation_ids) <= set(obs), 'Unknown result evidence')
    for oid in observation_ids:
        o = obs[oid]
        require(metrics[o['metric']]['layer'] == q['layer'] and o['source'] in q['eligible_sources'] and not o.get('superseded_by'), 'Result evidence outside question scope')
    require(outcome != 'resolved' or observation_ids, 'Resolution requires accepted evidence and human semantic review')
    require(outcome != 'conflicting_evidence' or len(set(observation_ids)) >= 2, 'A conflict needs both evidence references')
    return outcome == 'resolved'


def record_result(root, qid, outcome, observation_ids, reviewer, rationale, at, *, human_confirm):
    from editorial_review import append_event, locked
    q = approved_question(root, qid)
    require(human_confirm is True and reviewer in ed.read(root/'research/editorial-policy.json')['reviewers'] and rationale.strip(), 'Human resolution review required')
    resolved = validate_result(q, outcome, observation_ids, ed.read(root/'site/data/ledger.json'))
    with locked(root):
        append_event(root, {'id':qid, 'kind':'research_question', 'status':'resolved' if resolved else 'unresolved',
                            'outcome':outcome, 'observation_ids':observation_ids, 'reviewer':reviewer,
                            'rationale':rationale, 'at':at})

