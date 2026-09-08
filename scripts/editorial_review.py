"""Bounded editorial CLI; default is offline assessment. All operational output is private.

Human review requires an interactive local terminal. No CLI flag can auto-approve.
Application edits only research/homepage.json; it never builds, commits or pushes.
"""
import argparse
import contextlib
import difflib
import getpass
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import editorial as ed
from validate import require

ROOT = ed.ROOT


def save(path, value):
    # Same atomic JSON convention as the research runner; no model-selected paths.
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False)+'\n', encoding='utf-8')
    os.replace(tmp, path)


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


def queue(root):
    return root/'.local/review-candidates'


@contextlib.contextmanager
def locked(root):
    folder = queue(root)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder/'editorial.lock'
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    try:
        os.close(fd)
        yield
    finally:
        path.unlink()


def events(root):
    path = queue(root)/'editorial-events.jsonl'
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()] if path.exists() else []


def append_event(root, event):
    with (queue(root)/'editorial-events.jsonl').open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(event, sort_keys=True, ensure_ascii=False)+'\n')
        stream.flush()
        os.fsync(stream.fileno())


def status(root, rid):
    return next((e['status'] for e in reversed(events(root)) if e['id'] == rid), None)


def monitoring(root):
    # Attempts are not successful checks. Retained source bodies prove retrieval;
    # run failures take precedence when later than a successful retrieval.
    result = {}
    ledger = ed.read(root/'site/data/ledger.json')
    by_url = {s['url']: s['id'] for s in ledger['sources']}
    def record(sid, checked_at, outcome):
        if sid not in result or checked_at > result[sid]['checked_at']:
            result[sid] = {'checked_at': checked_at, 'outcome': outcome}
    for path in (root/'.local/evidence').glob('*.json'):
        body = ed.read(path)
        if body.get('url') in by_url and body.get('retrieved_at'):
            # Retrieval alone is not an assertion that content is unchanged.
            record(by_url[body['url']], body['retrieved_at'], 'retrieved_change_unknown')
    for run in ledger['runs']:
        for failure in run['source_failures']:
            record(failure['source'], run['finished_at'], 'source_inaccessible')
    return result


def displayed(root):
    import re
    path = root/'docs/index.html'
    if not path.exists():
        return {}
    return dict(re.findall(r'data-layer="([a-z-]+)" data-observation="([a-z0-9-]+)"', path.read_text(encoding='utf-8')))


def assemble(root, as_of, model='not-requested'):
    return ed.snapshot(ed.read(root/'site/data/ledger.json'), ed.read(root/'research/homepage.json'),
                       ed.read(root/'research/editorial-policy.json'), ed.read(root/'research/sources.json'),
                       as_of, monitoring(root), events(root), model, displayed(root))


def candidates(snap, layer):
    incumbent = snap['config']['slots'][layer]['metric_id']
    metrics = [m for m in snap['metrics'] if m['layer'] == layer and snap['features'][m['id']]['eligible']]
    focus = snap['policy'].get('candidate_focus',{}).get(layer,[])
    # This deterministic shortlist orders review work, not editorial merit. No growth sort.
    metrics.sort(key=lambda m: (m['id'] != incumbent, focus.index(m['id']) if m['id'] in focus else len(focus), m['id'] not in snap['policy']['metrics'], m['id']))
    return [m['id'] for m in metrics[:snap['policy']['budgets']['candidates_per_layer']]]


def input_packet(snap, layer):
    ids = candidates(snap, layer)
    incumbent = snap['config']['slots'][layer]['metric_id']
    if incumbent not in ids:
        ids = [incumbent]+ids[:snap['policy']['budgets']['candidates_per_layer']-1]
    observations = [o for o in snap['observations'] if o['metric'] in ids]
    used = {o['source'] for o in observations}
    packet = {'as_of': snap['as_of'], 'timezone': snap['timezone'], 'slot': snap['config']['slots'][layer],
              'metrics': [m for m in snap['metrics'] if m['id'] in ids],
              'observations': observations, 'sources': [s for s in snap['sources'] if s['id'] in used],
              'features': {mid: snap['features'][mid] for mid in ids}, 'freshness': snap['freshness'][layer],
              'prior_decisions': [e for e in snap['prior_decisions'] if e.get('layer') == layer][-10:],
              'rubric': snap['policy']['weights'], 'schema': ed.model_schema(snap, layer, ids)}
    encoded = json.dumps(packet, ensure_ascii=False)
    require(len(encoded) <= snap['policy']['budgets']['input_characters'], 'Evidence packet exceeds budget; do not silently truncate')
    return ids, encoded


def enqueue(root, proposal, snap):
    rid = proposal['recommendation_id']
    with locked(root):
        # Material revisions may reconsider rejected work; routine replacements still
        # respect a layer cooldown after an application. A flagged flaw is always surfaced.
        if proposal['action'] == 'REPLACE_METRIC' and not proposal['response']['critical_flaw']:
            applied = [e for e in events(root) if e.get('layer') == proposal['layer_id'] and e['status'] == 'applied']
            if applied and (ed.instant(snap['as_of'])-ed.instant(applied[-1]['at'])).days < snap['policy']['cooldown_days']:
                return False
        previous = [e for e in events(root) if e['id'] == rid]
        if previous:
            last = previous[-1]
            if last['status'] != 'deferred' or ed.instant(snap['as_of']) < ed.instant(last['reconsider_after']):
                return False
        path = queue(root)/(rid+'.json')
        if not path.exists():
            save(path, proposal)
        elif ed.read(path) != proposal:
            # Same material decision retains its original model output/snapshot.
            proposal = ed.read(path)
        append_event(root, {'id': rid, 'layer': proposal['layer_id'], 'status': 'pending_review', 'at': snap['as_of'], 'material_hash': proposal['material_hash']})
        for q in proposal['response']['research_followups']:
            qid = 'question-'+ed.hashed(q)[:24]
            if not (queue(root)/(qid+'.json')).exists():
                save(queue(root)/(qid+'.json'), {'kind': 'research_question', 'id': qid, 'question': q,
                     'review_required': True, 'parent_recommendation': rid, 'status': 'pending_review'})
    return True


def proposed_config(proposal, snap, reviewed_at):
    updated = json.loads(json.dumps(snap['config']))
    action = proposal['action']
    slot = updated['slots'][proposal['layer_id']]
    r = proposal['response']
    if action in {'KEEP', 'INSUFFICIENT_EVIDENCE'}:
        return updated
    if action == 'REPLACE_METRIC':
        slot.update(metric_id=proposal['challenger_metric_id'], pin=None,
                    profile=snap['features'][proposal['challenger_metric_id']]['profile'],
                    visualization=r['proposed_display'] or 'snapshot')
    elif action == 'ADD_SUPPORTING_CHART':
        slot['supporting'] = [proposal['challenger_metric_id']]
    elif action == 'REFRESH_DATA':
        if slot['pin'] is not None:
            slot['pin'] = snap['features'][slot['metric_id']]['latest_id']
        else:
            return updated  # Approved automatic refresh already belongs to the renderer.
    else:
        slot['visualization'] = r['proposed_display']
    updated['reviewed_at'] = reviewed_at
    return updated


def config_diff(before, after):
    lines = lambda v: (json.dumps(v, indent=2, ensure_ascii=False)+'\n').splitlines(keepends=True)
    return ''.join(difflib.unified_diff(lines(before), lines(after), fromfile='research/homepage.json (current)', tofile='research/homepage.json (proposed)')) or 'No configuration change.\n'


def proposal_digest(p, snap):
    f = snap['freshness'][p['layer_id']]
    out = [f"# {p['recommendation_id']} — {p['action']}",
           f"{p['incumbent_metric_id']} → {p['challenger_metric_id'] or p['incumbent_metric_id']}",
           f"Evaluation: {snap['as_of']} ({snap['timezone']}). Model: {snap['model']}.",
           f"Displayed: {f['displayed_observation_id']}; candidate: {snap['features'][p['challenger_metric_id'] or p['incumbent_metric_id']]['latest_id']}.",
           f"Computed weighted scores (editorial judgments): {p['computed_scores']}; difference: {p['score_difference']}.",
           f"Cross-profile purpose review: {p['cross_profile_purpose_review_required']}.",
           f"Validation limits: {p['validation_limits']}"]
    for key in ['reader_question', 'advantages', 'tradeoffs', 'case_for_keeping_incumbent', 'incumbent_rechart_option', 'uncertainties', 'contradictions', 'score_basis']:
        out.extend(['', key.replace('_', ' ').capitalize()+':'])
        out.extend('- '+c['text']+' ['+', '.join(c['observation_ids'])+']' for c in p['response'][key])
    out.extend(['', 'Evidence preview (accepted ledger values, no interpolation):',
                '| Observation | Period | Value / upper | Status | Source |', '|---|---|---|---|---|'])
    obs = {o['id']: o for o in snap['observations']}
    sources = {s['id']: s for s in snap['sources']}
    for oid in p['supporting_observation_ids']:
        o = obs[oid]
        out.append(f"| {oid} | {o['period']} | {o['value']} / {o['upper']} | {o['status']} | [{o['source']}]({sources[o['source']]['url']}) |")
    out.extend(['', 'Proposed configuration (review timestamp shown at evaluation time):', '```diff',
                config_diff(snap['config'], proposed_config(p, snap, snap['as_of'])), '```', '',
                'Feature and dimension breakdown:', '```json', json.dumps({'features': p['feature_values'],
                'incumbent_scores': p['response']['incumbent_dimension_scores'],
                'challenger_scores': p['response']['challenger_dimension_scores'], 'freshness': f}, indent=2), '```'])
    return '\n'.join(out)+'\n'


def assessment(snap):
    rows = []
    for layer, slot in snap['config']['slots'].items():
        f = snap['features'][slot['metric_id']]
        clock = snap['freshness'][layer]
        action = ('INSUFFICIENT_EVIDENCE' if not f['eligible'] else 'REFRESH_DATA' if clock['display_lag'] in {'automatic_refresh','pinned_review_required'}
                  else 'IMPROVE_VISUALIZATION' if f['chart_ready'] and f['profile'] == 'trajectory' and slot['visualization'] != 'history' else 'KEEP')
        rows.append({'layer': layer, 'incumbent': slot['metric_id'], 'deterministic_triage': action,
                     'model_review': 'not_run', 'best_challenger': None,
                     'challenger_note': 'No qualitative review performed; shortlist is not a ranking.',
                     'shortlist': candidates(snap, layer), 'historical_points': f['independent_points'],
                     'segments': f['segments'], 'forecast_ids': f['forecast_ids'], 'freshness': clock,
                     'gap': f['contract']['context'] if not f['chart_ready'] else 'No inflection claim. Preserve scope, bounds and source attribution.'})
    return rows


def run(root, as_of, use_model=False, trigger='on-demand', adapter=None, critique=False):
    runtime = ed.read(root/'research/runtime.json')
    snap = assemble(root, as_of, runtime['model'] if use_model else 'not-requested')
    trigger_path = root/'.local/editorial/triggers.json'
    previous = ed.read(trigger_path) if trigger_path.exists() else {}
    trigger_key = f'{trigger}:{use_model}:{critique}'
    material = ed.hashed({k: snap[k] for k in ['config', 'policy', 'metrics', 'observations', 'source_policy']})
    if trigger != 'on-demand' and trigger_key in previous:
        last = previous[trigger_key]
        elapsed = (ed.instant(as_of)-ed.instant(last['at'])).total_seconds()/3600
        same_month = as_of[:7] == last['at'][:7]
        if elapsed < snap['policy']['debounce_hours'] or trigger == 'material' and last['material'] == material or trigger == 'monthly' and same_month:
            return {'snapshot_hash': snap['snapshot_hash'], 'model_status': 'debounced', 'proposals': [], 'failures': []}
    folder = root/'.local/editorial'/snap['snapshot_hash']
    save(folder/'snapshot.json', snap)
    result = {'as_of': as_of, 'snapshot_hash': snap['snapshot_hash'], 'trigger': trigger,
              'model_status': 'not_requested', 'assessment': assessment(snap), 'proposals': [], 'failures': [], 'reviewed_layers': []}
    if use_model:
        # Reuse only the existing local JSON adapter, passing no repository credentials.
        if adapter is None:
            from research import ollama
            adapter = ollama
        permitted = {k: runtime[k] for k in ['model', 'ollama_url', 'model_timeout_seconds']}
        permitted['_generation_settings'] = dict(ed.SETTINGS, num_predict=snap['policy']['budgets']['output_tokens'])
        budget = snap['policy']['budgets']['model_calls']
        calls = 0
        result['model_status'] = 'completed'
        for layer in snap['config']['slots']:
            if calls >= budget:
                break
            try:
                ids, packet = input_packet(snap, layer)
                key = ed.hashed({'snapshot': snap['snapshot_hash'], 'packet': packet, 'schema': ed.model_schema(snap, layer, ids)})
                path = folder/(layer+'-model.json')
                # Frozen response cache and replay never claim deterministic inference.
                if path.exists() and ed.read(path)['cache_key'] == key:
                    response = ed.read(path)['response']
                else:
                    calls += 1
                    response = adapter(permitted, ed.SYSTEM, packet, ed.model_schema(snap, layer, ids))
                    save(path, {'cache_key': key, 'response': response})
                p = ed.validate_response(response, snap, layer, ids)
                if critique and calls < budget:
                    critique_schema = {'type':'object','properties':{'stance':{'enum':['supports','objects','insufficient_evidence']},
                        'limitations':{'type':'string'},'observation_ids':{'type':'array','items':{'type':'string'}}},
                        'required':['stance','limitations','observation_ids'],'additionalProperties':False}
                    critique_prompt = json.dumps({'frozen_packet':json.loads(packet),'proposal':response,'task':'Critique the proposal, strongest KEEP case and scope losses. No authority or new research. Qualitative text only.'},ensure_ascii=False)
                    require(len(critique_prompt) <= snap['policy']['budgets']['input_characters'], 'Critique packet exceeds budget')
                    calls += 1
                    criticism = adapter(permitted, ed.SYSTEM, critique_prompt, critique_schema)
                    require(set(criticism)==set(critique_schema['properties']) and criticism['stance'] in {'supports','objects','insufficient_evidence'},'Invalid critique schema')
                    require(isinstance(criticism['limitations'],str) and 0<len(criticism['limitations'])<=1200, 'Invalid critique text')
                    require(set(criticism['observation_ids']) <= set(p['supporting_observation_ids']), 'Unsupported critique references')
                    save(folder/(layer+'-critique.json'),dict(criticism,authority='Fallible model assistance; not independent corroboration or human approval.'))
                queued = enqueue(root, p, snap)
                (folder/(layer+'-digest.md')).write_text(proposal_digest(p, snap), encoding='utf-8')
                if queued:
                    result['proposals'].append(p['recommendation_id'])
                result['reviewed_layers'].append(layer)
            except (ValueError, OSError, RuntimeError, KeyError, TypeError) as error:
                result['failures'].append({'layer': layer, 'reason': str(error)[:300]})
        if result['failures']:
            result['model_status'] = 'failed_or_partial'
        elif len(result['reviewed_layers']) < len(snap['config']['slots']):
            result['model_status'] = 'budget_limited'
        result['model_calls'] = calls
    save(folder/'assessment.json', result)
    lines = ['# Accepted-data editorial assessment', '', f"As of {as_of}. Model: {result['model_status']}.",
             'Deterministic triage is not a completed editorial review. No configuration was changed.', '',
             '| Layer | Incumbent | Historical points | Triage |', '|---|---|---:|---|']
    for row in result['assessment']:
        lines.append(f"| {row['layer']} | {row['incumbent']} | {row['historical_points']} | {row['deterministic_triage']} |")
    for row in result['assessment']:
        lines.extend(['', f"{row['layer']}: {row['gap']}", ''])
    lines.extend(['', 'Delivery graphic: '+ed.delivery_gate(snap['config']['delivery_accounting'], ed.read(root/'site/data/ledger.json'))['reason'] if snap['config']['delivery_accounting'] is None else '',
                  'Best challenger: not adjudicated. See assessment.json for bounded candidate IDs, rejected evidence, segments and freshness clocks.'])
    (folder/'digest.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    save(root/'.local/editorial/latest.json', {'snapshot_hash': snap['snapshot_hash'], 'as_of': as_of, 'trigger': trigger})
    if result['model_status'] != 'failed_or_partial':
        previous[trigger_key] = {'at': as_of, 'material': material}
        save(trigger_path, previous)
    return result


def load_proposal(root, rid):
    import re
    require(re.fullmatch('editorial-[0-9a-f]{24}', rid), 'Invalid recommendation ID')
    p = ed.read(queue(root)/(rid+'.json'))
    snap = ed.read(root/'.local/editorial'/p['evidence_snapshot_hash']/'snapshot.json')
    body = {k: v for k, v in snap.items() if k != 'snapshot_hash'}
    require(ed.hashed(body) == snap['snapshot_hash'], 'Snapshot changed')
    return p, snap


def state_guard(root, snap, approved_after=None):
    # Material source/config/metric/evidence changes invalidate approval. Runtime receipts do not.
    current = ed.read(root/'site/data/ledger.json')
    for key in ['metrics', 'sources', 'observations']:
        require(current[key] == snap[key], 'Stale approval: accepted '+key+' changed')
    require(ed.read(root/'research/homepage.json') in [snap['config'], approved_after], 'Stale approval: homepage changed')
    require(ed.read(root/'research/editorial-policy.json') == snap['policy'], 'Stale approval: policy changed')
    require(ed.read(root/'research/sources.json') == snap['source_policy'], 'Stale approval: source policy changed')
    require(ed.implementation_identity() == snap['implementation_hash'], 'Stale approval: implementation changed')
    for layer, slot in snap['config']['slots'].items():
        mid = slot['metric_id']
        metric = next(m for m in current['metrics'] if m['id'] == mid)
        require(ed.series_features(metric, current['observations'], {s['id']: s for s in current['sources']}, snap['policy'], snap['as_of']) == snap['features'][mid], 'Stale eligibility')


def record_review(root, rid, decision, reviewer, rationale, reviewed_at, *, human_confirm, reconsider_after=None):
    """Trusted operator seam. Only interactive CLI calls it operationally; model adapter never can."""
    require(human_confirm is True, 'Explicit human terminal confirmation required')
    require(decision in {'approved', 'rejected', 'deferred', 'superseded'}, 'Invalid review decision')
    p, snap = load_proposal(root, rid)
    require(reviewer in snap['policy']['reviewers'] and rationale.strip(), 'Authorized human and rationale required')
    require(ed.instant(reviewed_at) >= ed.instant(snap['as_of']), 'Review predates evidence snapshot')
    with locked(root):
        require(status(root, rid) in {'pending_review', 'deferred'}, 'Proposal is not pending')
        if decision == 'approved':
            state_guard(root, snap)
        if decision == 'deferred':
            require(reconsider_after and ed.instant(reconsider_after) > ed.instant(reviewed_at), 'Deferral needs future reconsideration date')
        before = snap['config']
        after = proposed_config(p, snap, reviewed_at)
        event = {'id': rid, 'layer': p['layer_id'], 'status': decision, 'reviewer': reviewer,
                 'rationale': rationale, 'at': reviewed_at, 'reconsider_after': reconsider_after,
                 'before': before, 'after': after, 'diff': config_diff(before, after), 'proposal_hash': ed.hashed(p)}
        append_event(root, event)
    return event


def apply(root, rid):
    p, snap = load_proposal(root, rid)
    with locked(root):
        review = next((e for e in reversed(events(root)) if e['id'] == rid), None)
        require(review and review['status'] == 'approved' and review['reviewer'] in snap['policy']['reviewers'], 'Recorded human approval required')
        require(review.get('proposal_hash') == ed.hashed(p), 'Proposal changed after human approval')
        current = ed.read(root/'research/homepage.json')
        state_guard(root, snap, review['after'])
        checked = ed.validate_response(p['response'], snap, p['layer_id'], candidates(snap, p['layer_id']))
        require(checked == p, 'Proposal changed after validation')
        if current != review['after'] or review['before'] == review['after']:
            ed.validate_config(review['after'], ed.read(root/'site/data/ledger.json'), snap['policy'])
            save(root/'research/homepage.json', review['after'])
        # Recovery after interrupted atomic save is safe only for the exact approved result.
        append_event(root, {'id': rid, 'layer': p['layer_id'], 'status': 'applied', 'at': now(),
                            'before_hash': ed.hashed(review['before']), 'after_hash': ed.hashed(review['after'])})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command')
    assess = sub.add_parser('assess')
    assess.add_argument('--as-of', default=None)
    assess.add_argument('--model', action='store_true', help='Opt in to bounded local inference; never approves')
    assess.add_argument('--critique', action='store_true', help='Optional second-pass critique within the same model-call budget')
    assess.add_argument('--trigger', choices=['on-demand', 'monthly', 'material'], default='on-demand')
    review = sub.add_parser('review')
    review.add_argument('id')
    review.add_argument('--decision', choices=['approved', 'rejected', 'deferred', 'superseded'], required=True)
    review.add_argument('--reviewer', required=True)
    review.add_argument('--rationale', required=True)
    review.add_argument('--reconsider-after')
    application = sub.add_parser('apply')
    application.add_argument('id')
    sub.add_parser('questions', help='Seed bounded follow-ups into the existing private queue; no research starts')
    discovery_review = sub.add_parser('review-discovery', help='Human coverage triage; never registers or publishes a source')
    discovery_review.add_argument('id')
    discovery_review.add_argument('--decision', choices=['investigate','deferred','rejected'], required=True)
    discovery_review.add_argument('--reviewer', required=True)
    discovery_review.add_argument('--rationale', required=True)
    for command in ['review-question', 'resolve-question']:
        qparser = sub.add_parser(command)
        qparser.add_argument('id')
        qparser.add_argument('--reviewer', required=True)
        qparser.add_argument('--rationale', required=True)
        if command == 'resolve-question':
            qparser.add_argument('--outcome', choices=sorted(ed.OUTCOMES), required=True)
            qparser.add_argument('--observations', nargs='*', default=[])
    args = parser.parse_args()
    if args.command in {None, 'assess'}:
        result = run(ROOT, getattr(args, 'as_of', None) or now(), getattr(args, 'model', False), getattr(args, 'trigger', 'on-demand'), critique=getattr(args,'critique',False))
        print(json.dumps({'snapshot_hash': result['snapshot_hash'], 'model_status': result['model_status'], 'proposals': result['proposals'], 'failures': result['failures']}, indent=2))
    elif args.command == 'apply':
        apply(ROOT, args.id)
        print('Applied approved local configuration. No build, commit, push or deployment performed.')
    elif args.command == 'questions':
        from editorial_questions import enqueue_questions
        print(json.dumps(enqueue_questions(ROOT, assemble(ROOT, now())), indent=2))
    elif args.command == 'review-discovery':
        import re
        from discovery import record_review as review_discovery
        require(sys.stdin.isatty() and sys.stdout.isatty(), 'Human review requires an interactive local terminal')
        policy = ed.read(ROOT/'research/editorial-policy.json')
        require(getpass.getuser().lower() in policy.get('reviewer_accounts', {}).get(args.reviewer, []), 'Unauthorized local reviewer account')
        require(re.fullmatch(r'discovery-[0-9a-f]{24}', args.id), 'Invalid discovery ID')
        print(json.dumps(ed.read(queue(ROOT)/(args.id+'.json')), indent=2))
        print(json.dumps({'decision':args.decision,'rationale':args.rationale}))
        require(input('Type the complete discovery ID to confirm human triage: ').strip() == args.id, 'Discovery decision not confirmed')
        review_discovery(ROOT,args.id,args.decision,args.reviewer,args.rationale,now(),human_confirm=True)
        print('Private coverage triage recorded. Source registration, catalog changes and publication still require reviewed implementation.')
    elif args.command in {'review-question', 'resolve-question'}:
        from editorial_questions import load_question, record_question_review, record_result
        require(sys.stdin.isatty() and sys.stdout.isatty(), 'Human review requires an interactive local terminal')
        policy = ed.read(ROOT/'research/editorial-policy.json')
        require(getpass.getuser().lower() in policy.get('reviewer_accounts', {}).get(args.reviewer, []), 'Unauthorized local reviewer account')
        print(json.dumps(load_question(ROOT, args.id), indent=2))
        if args.command == 'resolve-question':
            print(json.dumps({'outcome':args.outcome, 'evidence':args.observations, 'rationale':args.rationale}, indent=2))
        require(input('Type the complete question ID to confirm this human decision: ').strip() == args.id, 'Question decision not confirmed')
        if args.command == 'review-question':
            record_question_review(ROOT,args.id,args.reviewer,args.rationale,now(),human_confirm=True)
        else:
            record_result(ROOT,args.id,args.outcome,args.observations,args.reviewer,args.rationale,now(),human_confirm=True)
        print('Question review recorded. No research or publication started.')
    else:
        require(sys.stdin.isatty() and sys.stdout.isatty(), 'Human review requires an interactive local terminal')
        p, snap = load_proposal(ROOT, args.id)
        require(getpass.getuser().lower() in snap['policy'].get('reviewer_accounts', {}).get(args.reviewer, []), 'Local account is not an authorized human reviewer')
        print(proposal_digest(p, snap))
        criticism=ROOT/'.local/editorial'/snap['snapshot_hash']/(p['layer_id']+'-critique.json')
        if criticism.exists():
            print(json.dumps(ed.read(criticism),indent=2))
        at = now()
        print(config_diff(snap['config'], proposed_config(p, snap, at)))
        require(input('Type the complete recommendation ID to record this human decision: ').strip() == args.id, 'Review not confirmed')
        record_review(ROOT, args.id, args.decision, args.reviewer, args.rationale, at,
                      human_confirm=True, reconsider_after=args.reconsider_after)
        print('Human decision recorded. Nothing applied or published.')


if __name__ == '__main__':
    main()
