import ast
import copy
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import editorial_fixtures as fx
import editorial as ed
import editorial_review as review
import render_editorial as presentation

ROOT = fx.ROOT


class EvidenceContracts(unittest.TestCase):
    def test_old_report_retrieval_does_not_reset_evidence_age(self):
        s = fx.snapshot()
        clock = s['freshness']['energy']
        self.assertGreater(clock['evidence_age_days'], 200)
        self.assertEqual(clock['retrieved_at'], '2026-09-07T00:00:00Z')
        self.assertIsNone(clock['accepted_at'])
        o=dict(fx.fixture()[0]['observations'][0],period='2023 · June 2025 outlook')
        self.assertEqual(ed.period_bounds(o)[1].isoformat(),'2023-12-31')

    def test_annual_within_publication_window(self):
        self.assertEqual(fx.snapshot()['freshness']['energy']['evidence_state'], 'within_release_window')

    def test_old_event_price_reverified_unchanged(self):
        d, c, p = fx.fixture()
        p['metrics']['models-metric']['cadence'] = 'event'
        s = fx.snapshot(d, c, p, monitoring={'fixture-source': {'checked_at': '2026-09-07T23:00:00Z', 'outcome': 'no_new_evidence'}})
        self.assertEqual(s['freshness']['models']['monitoring_state'], 'fresh')
        self.assertEqual(s['freshness']['models']['observation_period'], '2025')

    def test_access_failure_is_neither_delay_nor_no_change(self):
        s = fx.snapshot(monitoring={'fixture-source': {'checked_at': '2026-09-07T23:00:00Z', 'outcome': 'source_inaccessible'}})
        self.assertEqual(s['freshness']['energy']['monitoring_state'], 'source_inaccessible')
        self.assertEqual(s['features']['energy-metric']['independent_points'], 3)

    def test_automatic_refresh_and_pinned_review(self):
        s = fx.snapshot(displayed={'energy': 'energy-metric-2024'})
        self.assertEqual(s['freshness']['energy']['display_lag'], 'automatic_refresh')
        d, c, p = fx.fixture()
        c['slots']['energy']['pin'] = 'energy-metric-2024'
        s = fx.snapshot(d, c, p)
        self.assertEqual(s['freshness']['energy']['display_lag'], 'pinned_review_required')
        self.assertEqual(presentation.selected(d, c['slots']['energy'], p)['id'], 'energy-metric-2024')

    def test_future_forecast_and_future_misclassified_actual_excluded(self):
        d, c, p = fx.fixture()
        original = d['observations'][0]
        for status in ['forecast', 'observation']:
            d['observations'].append(dict(original, id='future-'+status, year=2030, period='2030', value=9000000, status=status))
        s = fx.snapshot(d, c, p)
        f = s['features']['energy-metric']
        self.assertEqual(f['latest_id'], 'energy-metric-2025')
        self.assertEqual(f['independent_points'], 3)
        self.assertIn('future-forecast', f['forecast_ids'])
        self.assertIn('future-observation', f['rejected'])

    def test_plateau_decline_and_zero_base(self):
        d, c, p = fx.fixture()
        s = fx.snapshot(d, c, p)
        self.assertTrue(s['features']['energy-metric']['chart_ready'])
        self.assertEqual(s['features']['energy-metric']['segments'][0]['change']['percent'], 0)
        d['observations'][0]['value'] = 0
        s = fx.snapshot(d, c, p)
        self.assertIsNone(s['features']['energy-metric']['segments'][0]['change']['cagr'])
        d['observations'][0]['value'] = 200
        s = fx.snapshot(d, c, p)
        self.assertLess(s['features']['energy-metric']['segments'][0]['change']['absolute'], 0)

    def test_sparse_duplicates_and_ranges_cannot_establish_inflection(self):
        d, c, p = fx.fixture()
        d['observations'].append(dict(d['observations'][0], id='duplicate'))
        d['observations'][1].update(upper=130, precision='range')
        s = fx.snapshot(d, c, p)
        f = s['features']['energy-metric']
        self.assertEqual(f['independent_points'], 3)
        self.assertIsNone(f['segments'][0]['change'])
        self.assertEqual(f['segments'][0]['inflection'], 'insufficient_history')

    def test_incompatible_units_entity_scope_period_and_method(self):
        for key, value in [('unit','MW facility'), ('scope','Different campus'), ('company','Other owner'), ('project','Other phase'), ('period_basis','cumulative')]:
            d, c, p = fx.fixture()
            d['observations'][0][key] = value
            self.assertIn(d['observations'][0]['id'], fx.snapshot(d, c, p)['features']['energy-metric']['rejected'])
        d, c, p = fx.fixture()
        d['observations'][0]['methodology'] = 'changed method'
        self.assertEqual(len(fx.snapshot(d, c, p)['features']['energy-metric']['segments']), 2)

    def test_true_elapsed_spacing_and_gap(self):
        d, c, p = fx.fixture()
        d['observations'][0].update(year=2020, period='2020')
        f = fx.snapshot(d, c, p)['features']['energy-metric']
        self.assertFalse(f['chart_ready'])
        self.assertGreater(max(f['segments'][0]['gaps_days']), 1000)

    def test_single_snapshot_delivery_profile_remains_useful(self):
        d, c, p = fx.fixture()
        d['observations'] = [o for o in d['observations'] if o['year'] == 2025]
        p['metrics']['infrastructure-metric'].update(profile='delivery-state', min_points=1, min_span_days=0)
        s = fx.snapshot(d, c, p)
        self.assertTrue(s['features']['infrastructure-metric']['eligible'])
        self.assertFalse(s['features']['energy-metric']['chart_ready'])

    def test_cache_identity_includes_model_policy_schema_prompt_and_config(self):
        base = fx.snapshot()
        for key in ['prompt_version', 'schema_version', 'version', 'implementation_version']:
            d,c,p = fx.fixture()
            if key == 'version':
                p['weights']['significance'] += 1; p['weights']['freshness'] -= 1
            else:
                p[key] = 'changed'
            self.assertNotEqual(fx.snapshot(d,c,p)['snapshot_hash'], base['snapshot_hash'])
        self.assertNotEqual(fx.snapshot(model='different-model')['snapshot_hash'], base['snapshot_hash'])
        d,c,p = fx.fixture(); c['slots']['energy']['visualization'] = 'history'
        self.assertNotEqual(fx.snapshot(d,c,p)['snapshot_hash'], base['snapshot_hash'])
        self.assertEqual(fx.snapshot()['snapshot_hash'], base['snapshot_hash'])

    def test_unicode_snapshot_roundtrip_preserves_replay_hash(self):
        d,c,p=fx.fixture();d['sources'][0]['title']='測試 · evidence — historical estimates'
        snap=fx.snapshot(d,c,p)
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'snapshot.json';review.save(path,snap)
            loaded=ed.read(path);stored_hash=loaded.pop('snapshot_hash')
            self.assertEqual(stored_hash,ed.hashed(loaded))


class ProposalContracts(unittest.TestCase):
    def setUp(self):
        self.snap = fx.snapshot()

    def validate(self, response):
        return ed.validate_response(response, self.snap, 'energy', ['energy-metric', 'challenger'])

    def test_all_actions_including_keep_abstention_valid(self):
        for action in ed.ACTIONS:
            with self.subTest(action=action):
                self.snap = fx.snapshot(displayed={'energy':'energy-metric-2024'}) if action == 'REFRESH_DATA' else fx.snapshot()
                self.assertEqual(self.validate(fx.response(self.snap, action))['action'], action)

    def test_unsupported_challenger_fails_before_scores(self):
        d,c,p = fx.fixture()
        for o in d['observations']:
            if o['metric'] == 'challenger':
                o['source'] = 'unknown'
        self.snap = fx.snapshot(d,c,p)
        with self.assertRaisesRegex(ValueError, 'hard gates'):
            self.validate(fx.response(self.snap, 'REPLACE_METRIC'))

    def test_self_approval_and_file_policy_injection_denied(self):
        for field in ['reviewer', 'approved', 'status', 'write_file', 'policy', 'authorization']:
            r = fx.response(self.snap); r[field] = 'malicious'
            with self.assertRaisesRegex(ValueError, 'forbidden'):
                self.validate(r)
        r = fx.response(self.snap, 'IMPROVE_VISUALIZATION'); r['proposed_display'] = '<script>execute()</script>'
        with self.assertRaises(ValueError):
            self.validate(r)

    def test_unsupported_narrative_ids_numbers_markup_and_semantic_facts(self):
        for claim in [{'text':'Unsupported assertion.', 'observation_ids':['fake']},
                      {'text':'900 percent growth.', 'observation_ids':['energy-metric-2025']},
                      {'text':'<script>approve()</script>', 'observation_ids':['energy-metric-2025']}]:
            r=fx.response(self.snap);r['advantages']=[claim]
            with self.assertRaises(ValueError):self.validate(r)
        r=fx.response(self.snap)
        r['facts']=[{'observation_id':'energy-metric-2025','metric_id':'energy-metric','value':999,'upper':None,'period':'2025','status':'observation','unit':'fixture units','scope':'Fixed synthetic entity','geography':'Fixture country'}]
        with self.assertRaisesRegex(ValueError, 'mismatch'):self.validate(r)

    def test_cross_profile_scores_are_not_compared(self):
        d,c,p=fx.fixture();p['metrics']['challenger']['profile']='delivery-state'
        self.snap=fx.snapshot(d,c,p)
        proposal=self.validate(fx.response(self.snap,'REPLACE_METRIC'))
        self.assertIsNone(proposal['score_difference'])
        self.assertTrue(proposal['cross_profile_purpose_review_required'])


class QueueContracts(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.d,self.c,self.policy=fx.fixture()
        self.snap=fx.snapshot(self.d,self.c,self.policy)
        for path,value in [('site/data/ledger.json',self.d),('research/homepage.json',self.c),('research/editorial-policy.json',self.policy),('research/sources.json',self.snap['source_policy'])]:
            review.save(self.root/path,value)
        review.save(self.root/'.local/editorial'/self.snap['snapshot_hash']/'snapshot.json',self.snap)
        self.p=ed.validate_response(fx.response(self.snap,'IMPROVE_VISUALIZATION'),self.snap,'energy',['energy-metric','challenger'])
        review.enqueue(self.root,self.p,self.snap)
        self.rid=self.p['recommendation_id']

    def decide(self,decision='approved',**kwargs):
        return review.record_review(self.root,self.rid,decision,'reedos','Fixture human decision; test only.',fx.AS_OF,human_confirm=True,**kwargs)

    def test_idempotent_queue_and_rejected_no_spam(self):
        self.assertFalse(review.enqueue(self.root,self.p,self.snap))
        self.decide('rejected')
        self.assertFalse(review.enqueue(self.root,self.p,self.snap))
        self.assertEqual(len(review.events(self.root)),2)

    def test_deferral_honored_until_due(self):
        self.decide('deferred',reconsider_after='2026-10-08T00:00:00Z')
        self.assertFalse(review.enqueue(self.root,self.p,self.snap))
        later=dict(self.snap,as_of='2026-10-09T00:00:00Z')
        self.assertTrue(review.enqueue(self.root,self.p,later))

    def test_no_application_without_human_and_separate_apply(self):
        with self.assertRaisesRegex(ValueError,'human approval'):review.apply(self.root,self.rid)
        with self.assertRaises(ValueError):
            review.record_review(self.root,self.rid,'approved','model','self approval',fx.AS_OF,human_confirm=False)
        self.decide()
        self.assertEqual(ed.read(self.root/'research/homepage.json'),self.c)
        review.apply(self.root,self.rid)
        self.assertEqual(ed.read(self.root/'research/homepage.json')['slots']['energy']['visualization'],'history')
        self.assertEqual(review.status(self.root,self.rid),'applied')

    def test_changed_evidence_config_or_policy_blocks_application(self):
        self.decide()
        for path in ['site/data/ledger.json','research/homepage.json','research/editorial-policy.json']:
            original=ed.read(self.root/path); changed=copy.deepcopy(original)
            if path.endswith('ledger.json'):changed['observations'][0]['value']+=1
            elif path.endswith('homepage.json'):changed['slots']['models']['visualization']='history'
            else:changed['cooldown_days']+=1
            review.save(self.root/path,changed)
            with self.assertRaisesRegex(ValueError,'Stale approval'):review.apply(self.root,self.rid)
            review.save(self.root/path,original)

    def test_same_evidence_on_different_day_has_same_recommendation_id(self):
        later=ed.snapshot(self.d,self.c,self.policy,self.snap['source_policy'],'2026-09-09T00:00:00Z')
        p=ed.validate_response(fx.response(later,'IMPROVE_VISUALIZATION'),later,'energy',['energy-metric','challenger'])
        self.assertEqual(p['recommendation_id'],self.rid)

    def test_model_adapter_bounded_and_no_publication_capability(self):
        runtime=ed.read(ROOT/'research/runtime.json');review.save(self.root/'research/runtime.json',runtime)
        calls=[]
        def adapter(config,system,prompt,schema):
            self.assertEqual(set(config),{'model','ollama_url','model_timeout_seconds','_generation_settings'})
            calls.append(prompt);packet=json.loads(prompt)
            layer=packet['slot']['metric_id'].removesuffix('-metric')
            return fx.response(self.snap,'KEEP',layer)
        result=review.run(self.root,fx.AS_OF,True,adapter=adapter)
        self.assertEqual(result['model_status'],'completed',result['failures'])
        self.assertEqual(len(calls),5)
        self.assertEqual(ed.read(self.root/'research/homepage.json'),self.c)
        self.assertFalse((self.root/'docs').exists())

    def test_material_and_monthly_triggers_debounce_without_inference(self):
        review.save(self.root/'research/runtime.json',ed.read(ROOT/'research/runtime.json'))
        for trigger in ['material','monthly']:
            first=review.run(self.root,fx.AS_OF,trigger=trigger)
            second=review.run(self.root,fx.AS_OF,trigger=trigger)
            self.assertEqual(first['model_status'],'not_requested')
            self.assertEqual(second['model_status'],'debounced')

    def test_review_binds_entire_proposal(self):
        self.decide()
        path=review.queue(self.root)/(self.rid+'.json')
        altered=ed.read(path);altered['response']['advantages'][0]['text']='A different interpretation.'
        review.save(path,altered)
        with self.assertRaisesRegex(ValueError,'changed after human approval'):review.apply(self.root,self.rid)

    def test_research_questions_need_human_approval_and_evidence_to_resolve(self):
        import editorial_questions as q
        ids=q.enqueue_questions(self.root,self.snap)
        self.assertEqual(ids,q.enqueue_questions(self.root,self.snap))
        with self.assertRaisesRegex(ValueError,'human approval'):q.approved_question(self.root,ids[0])
        q.record_question_review(self.root,ids[0],'reedos','Fixture human review.',fx.AS_OF,human_confirm=True)
        question=q.approved_question(self.root,ids[0])
        with self.assertRaises(ValueError):q.validate_result(question,'resolved',[],self.d)
        self.assertFalse(q.validate_result(question,'source_inaccessible',[],self.d))
        self.assertTrue(q.validate_result(question,'resolved',['energy-metric-2025'],self.d))

    def test_replacement_cooldown_and_critical_flaw_exception(self):
        proposal=ed.validate_response(fx.response(self.snap,'REPLACE_METRIC'),self.snap,'energy',['energy-metric','challenger'])
        review.append_event(self.root,{'id':'prior','layer':'energy','status':'applied','at':'2026-09-07T00:00:00Z'})
        self.assertFalse(review.enqueue(self.root,proposal,self.snap))
        proposal['response']['critical_flaw']=True
        self.assertTrue(review.enqueue(self.root,proposal,self.snap))


class HomepageContracts(unittest.TestCase):
    def test_protected_runtime_python_js_footer_and_css_exact(self):
        baseline=ed.read(ROOT/'tests/fixtures/editorial/runtime-contract.json')
        source=(ROOT/'scripts/render.py').read_text(encoding='utf-8')
        node=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name=='runtime')
        self.assertEqual(ast.get_source_segment(source,node),baseline['runtime_python'])
        js=(ROOT/'site/assets/app.js').read_text(encoding='utf-8')
        self.assertEqual(next(l for l in js.splitlines() if l.startswith('function runtime()')),baseline['runtime_js'])
        footer=(ROOT/'site/template.html').read_text(encoding='utf-8').split('<footer')[1].split('</footer>')[0]
        self.assertEqual(footer,baseline['template_footer'])
        for name,value in baseline['runtime_css'].items():
            self.assertEqual(hashlib.sha256((ROOT/'site/assets'/name).read_bytes()).hexdigest(),value)

    def test_runtime_values_and_counters_still_dynamic(self):
        import render
        data=ed.read(ROOT/'site/data/ledger.json');before=render.runtime(data)
        data['runtime'].update(status='failed',display_model='fixture model',last_attempt='2026-09-07T23:00:00Z')
        data['runs'][-1]['accepted']=777
        after=render.runtime(data)
        self.assertNotEqual(before,after);self.assertIn('fixture model',after);self.assertIn('777 accepted records',after)

    def test_preserve_incumbents_and_no_synthetic_history(self):
        d=ed.read(ROOT/'site/data/ledger.json');c=ed.read(ROOT/'research/homepage.json');p=ed.read(ROOT/'research/editorial-policy.json')
        self.assertEqual([s['metric_id'] for s in c['slots'].values()],[l['headline_metric'] for l in d['layers']])
        self.assertNotIn('<svg',presentation.history(d,c['slots']['models'],p,'./'))
        chips=presentation.history(d,c['slots']['chips'],p,'./')
        self.assertIn('<svg',chips);self.assertIn('<table',chips);self.assertIn('Estimate',chips)
        self.assertNotIn('cowos-2026',chips)

    def test_empty_recent_module_and_no_raw_note_promotion(self):
        d,c,p=fx.fixture();d['events']=[{'title':'Unreviewed raw note'}]
        html=presentation.recent_changes(c,d,'./',fx.AS_OF)
        self.assertIn('No developments have been approved',html)
        self.assertNotIn('Unreviewed raw note',html)
        self.assertNotIn('Signals worth following',(ROOT/'site/assets/app.js').read_text(encoding='utf-8'))

    def test_recent_deterministic_escaping_old_event_and_diversity(self):
        d,c,p=fx.fixture()
        for i,layer in enumerate(['energy','energy','chips','models']):
            c['recent_changes'].append({'id':f'change-{i}','event_key':f'event-{i}','layer':layer,'title':'<script>Untrusted</script>',
                'what_changed':'A scoped result was reviewed.','significance':'No causal result inferred.','scope':'Fixture only.',
                'event_date':'2024-01-01','reviewed_at':'2026-09-07T00:00:00Z','reviewer':'reedos','rationale':'Fixture human review.',
                'source_ids':['fixture-source'],'before_id':None,'after_id':None,'priority':0,'pinned':False,'kind':'correction'})
        ed.validate_config(c,d,p)
        html=presentation.recent_changes(c,d,'./',fx.AS_OF)
        self.assertEqual(html.count('<article'),3)
        self.assertIn('chips',html);self.assertIn('models',html);self.assertIn('Historical event, newly reviewed',html)
        self.assertNotIn('<script>',html);self.assertIn('&lt;script&gt;',html)
        self.assertEqual(html,presentation.recent_changes(c,d,'./',fx.AS_OF))
        # A new editorial decision must render even if local research has not run again.
        c['reviewed_at']='2026-09-07T23:00:00Z'
        for item in c['recent_changes']:item['reviewed_at']=c['reviewed_at']
        self.assertIn('<article',presentation.recent_changes(c,d,'./'))

    def test_delivery_parent_phase_overlap_and_unknown(self):
        d,c,p=fx.fixture();m=d['metrics'][0];m.update(project='campus',phase='phase-a');o=d['observations'][2]
        a={'basis':'disjoint-present-state','scope':'Selected synthetic cohort','as_of':'2025-12-31','unit':m['unit'],'exclusions':'Other campuses excluded',
           'phases':[{'id':'phase-a','parent_id':'campus','project_id':'campus','state':'operating','observation_id':o['id'],'scope':m['scope'],'source_ids':['fixture-source']},
                     {'id':'phase-b','parent_id':'campus','project_id':'campus','state':'unknown','observation_id':None,'scope':'Unknown phase scope','source_ids':['fixture-source']}]}
        result=ed.delivery_gate(a,d);self.assertTrue(result['eligible']);self.assertEqual(result['unknown_phases'],1)
        self.assertNotIn('unknown',result['totals'])
        c['delivery_accounting']=a;html=presentation.delivery_context(c,d,'./')
        self.assertIn('100',html);self.assertIn('Unknown; not zero',html);self.assertIn('https://example.org/fixture',html)
        a['phases'].append(dict(a['phases'][0],id='campus',parent_id=None))
        self.assertFalse(ed.delivery_gate(a,d)['eligible'])
        self.assertFalse(ed.delivery_gate(None,d)['eligible'])

    def test_unattended_permissions_unchanged(self):
        import research
        for path in ['research/homepage.json','research/editorial-policy.json','.local/review-candidates/editorial-events.jsonl','docs/assets/home.css']:
            self.assertNotIn(path,research.ALLOWED_CHANGES)

    def test_offline_end_to_end_fixture_review_apply_build(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for folder in ['scripts','research','site']:
                shutil.copytree(ROOT/folder,root/folder,ignore=shutil.ignore_patterns('__pycache__'))
            config=ed.read(root/'research/homepage.json');config['slots']['chips']['visualization']='snapshot'
            review.save(root/'research/homepage.json',config)
            snap=review.assemble(root,fx.AS_OF,'offline-fixture-mock')
            review.save(root/'.local/editorial'/snap['snapshot_hash']/'snapshot.json',snap)
            response=fx.response(snap,'IMPROVE_VISUALIZATION','chips')
            p=ed.validate_response(response,snap,'chips',review.candidates(snap,'chips'))
            review.enqueue(root,p,snap)
            review.record_review(root,p['recommendation_id'],'approved','reedos','Fixture human review of accepted CoWoS ranges.',fx.AS_OF,human_confirm=True)
            review.apply(root,p['recommendation_id'])
            result=subprocess.run([sys.executable,'scripts/build.py'],cwd=root,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            html=(root/'docs/index.html').read_text(encoding='utf-8')
            self.assertIn('headline-history',html);self.assertIn('What changed recently?',html)
            self.assertIn('id="runtime" class="runtime"',html)
            self.assertFalse((root/'docs/editorial').exists())


if __name__=='__main__':unittest.main()
