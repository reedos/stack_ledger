"""Offline contract/quality-fixture evaluation; no claims about live-model accuracy."""
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tests'))
import editorial_fixtures as fixtures
import editorial as ed
from editorial_review import save, proposal_digest


def evaluate():
    cases = ed.read(ROOT/'tests/fixtures/editorial/quality-cases.json')
    rows = []
    for case in cases['cases']:
        ledger, config, policy = fixtures.fixture()
        if case['mutation'] == 'pin':
            config['slots']['energy']['pin'] = 'energy-metric-2024'
        if case['mutation'] == 'sparse':
            ledger['observations'] = [o for o in ledger['observations'] if o['year'] == 2025]
        if case['mutation'] == 'better_scope':
            ledger['metrics'][0]['scope']='Installed nominal capacity, including idle units in a fixed synthetic cohort.'
            ledger['metrics'][-1]['scope']='Usable operating capacity, excluding idle units in the same synthetic cohort.'
        if case['mutation'] == 'method_break':
            ledger['observations'][2]['methodology']='Changed synthetic measurement method'
        if case['mutation'] == 'forecast':
            for o in ledger['observations']:
                if o['metric'] == 'challenger':
                    o.update(status='forecast', source='unapproved-fixture-source', value=10000000)
        snap = fixtures.snapshot(ledger, config, policy, model='offline-mocked-fixture')
        response = fixtures.response(snap, case['action'])
        if case['mutation'] == 'better_scope':
            response['advantages']=[{'text':'The challenger identifies usable operating units rather than nominal installed units.', 'observation_ids':['challenger-2025','energy-metric-2025']}]
            response['tradeoffs']=[{'text':'Nominal installed units remain useful for understanding reserve or idle capacity.', 'observation_ids':['energy-metric-2025']}]
        if case['mutation'] == 'method_break':
            response['contradictions']=[{'text':'The measurement method changed and the latest checkpoint cannot extend the earlier comparable segment.', 'observation_ids':['energy-metric-2024','energy-metric-2025']}]
        if case['mutation'] == 'fabricated':
            response['advantages'][0]['text'] = 'The forecast proves 900 percent realized growth.'
        reason = None
        try:
            proposal = ed.validate_response(response, snap, 'energy', ['energy-metric', 'challenger'])
            accepted = True
            folder = ROOT/'.local/editorial-evaluation'/case['id']
            save(folder/'proposal.json', proposal)
            (folder/'digest.md').write_text(proposal_digest(proposal, snap), encoding='utf-8')
        except ValueError as error:
            accepted, reason = False, str(error)
        rows.append(dict(case, actual_accept=accepted, validation_reason=reason, passed=accepted == case['accept']))
    result = {'mode': 'offline mocked responses against reviewable expectations; live-model quality unmeasured',
              'cases': rows, 'incorrect_acceptance': sum(r['actual_accept'] and not r['accept'] for r in rows),
              'missed_valid_evidence': sum(r['accept'] and not r['actual_accept'] for r in rows),
              'unsupported_replacement': sum(r['action'] == 'REPLACE_METRIC' and r['actual_accept'] and not r['accept'] for r in rows),
              'appropriate_abstention': sum(r['action'] == 'INSUFFICIENT_EVIDENCE' and r['passed'] for r in rows)}
    from editorial_review import enqueue, append_event
    snap=fixtures.snapshot()
    proposal=ed.validate_response(fixtures.response(snap),snap,'energy',['energy-metric','challenger'])
    with tempfile.TemporaryDirectory() as temp:
        root=Path(temp);enqueue(root,proposal,snap)
        repeated=sum(enqueue(root,proposal,snap) for _ in range(3))
        append_event(root,{'id':proposal['recommendation_id'],'status':'rejected','at':snap['as_of'],'rationale':'Synthetic fixture decision'})
        rejected_repeat=enqueue(root,proposal,snap)
        result['recommendation_churn']={'identical_replays':3,'additional_queued':repeated,'requeued_after_rejection':int(rejected_repeat)}
    from editorial_questions import seed_questions, validate_result
    snap=fixtures.snapshot(); q=seed_questions(snap)[0]
    ledger,_,_=fixtures.fixture()
    result['question_cases']=[dict(case, actual_resolution=validate_result(q,case['outcome'],case['evidence_ids'],ledger)) for case in cases['question_cases']]
    result['meaningful_question_resolution']=sum(c['actual_resolution'] for c in result['question_cases'])
    result['false_question_resolution']=sum(c['actual_resolution'] != c['expected_resolution'] for c in result['question_cases'])
    save(ROOT/'.local/editorial-evaluation/results.json', result)
    print(json.dumps(result, indent=2))
    if not all(r['passed'] for r in rows) or result['false_question_resolution'] or repeated or rejected_repeat:
        raise SystemExit(1)
    return result


if __name__ == '__main__':
    evaluate()
