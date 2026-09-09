"""Offline fixtures: no live inference, approval, publication or public data changes."""
import copy
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import visual_review as v
import editorial as ed
from atomic_json import save

AT='2026-09-10T00:00:00Z'


def answer(payload, action='REFRAME_PROPOSAL'):
    refs=[o['id'] for o in payload['observations']][:1] or [o['id'] for o in payload['catalog_sample']][:1]
    r={'action':action,'candidate':None,'visualization':'snapshot' if payload['display']['selector']=='slot' and action=='REFRAME_PROPOSAL' else None,
       'incumbent_scores':None,'candidate_scores':None}
    for key in v.NARRATIVES:r[key]={'text':'Preserve the scope and source attribution; review the clearer presentation.', 'refs':refs}
    return r


class VisualTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        clock=patch.object(v.er,'now',return_value=AT);clock.start();self.addCleanup(clock.stop)
        for name in v.FILES+['research/runtime.json']:
            path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,path)
        p=v.policy(self.root);p['displays']=[d for d in p['displays'] if d['id']=='highlight-chips'];save(self.root/'research/visual-policy.json',p)

    def assess(self,action='REFRAME_PROPOSAL',**kwargs):
        return v.assess(self.root,True,adapter=lambda runtime,system,prompt,schema:answer(json.loads(prompt),action),at=AT,**kwargs)

    def proposal(self):
        result=self.assess();self.assertEqual(result['failures'],[])
        return v.inbox(self.root)['proposals'][0]

    def decision(self,p,status='approved'):
        return {'id':p['id'],'decision':status,'rationale':'Synthetic human fixture review, not live authorization.',
                'proposal_hash':p['proposal_hash'],'review_hash':p['review_hash'],'confirmed':True,'reconsider_after':None}

    def test_offline_no_inference_or_mutation(self):
        before=v.material(self.root)
        with patch('research.ollama',side_effect=AssertionError('No inference')):
            r=v.assess(self.root,at=AT)
        self.assertEqual(r['model_calls'],0);self.assertEqual(len(r['unassessed']),1)
        self.assertEqual(v.material(self.root),before)

    def test_exact_preview_approval_never_applies(self):
        before=(self.root/'research/homepage.json').read_bytes();p=self.proposal()
        html=self.root/'.local/editorial'/('visual-'+p['snapshot_hash'])/(p['id']+'.html')
        self.assertIn('Current',html.read_text(encoding='utf-8'));self.assertNotIn('<script',html.read_text(encoding='utf-8'))
        result=v.review(self.root,self.decision(p),'reedos')
        self.assertFalse(result['applied']);self.assertFalse(result['published'])
        self.assertEqual((self.root/'research/homepage.json').read_bytes(),before)
        self.assertNotEqual(p['config_after'],ed.read(self.root/'research/homepage.json'))

    def test_stale_evidence_blocks_acceptance(self):
        p=self.proposal();ledger=ed.read(self.root/'site/data/ledger.json');ledger['observations'][0]['note']+=' fixture revision';save(self.root/'site/data/ledger.json',ledger)
        with self.assertRaisesRegex(ValueError,'changed'):v.review(self.root,self.decision(p),'reedos')

    def test_runtime_receipts_do_not_invalidate_approval(self):
        p=self.proposal();l=ed.read(self.root/'site/data/ledger.json');l['runtime']['status']='fixture';l['runs']=[];save(self.root/'site/data/ledger.json',l)
        self.assertTrue(v.review(self.root,self.decision(p),'reedos')['saved'])

    def test_tampered_preview_blocks_acceptance(self):
        p=self.proposal();html=self.root/'.local/editorial'/('visual-'+p['snapshot_hash'])/(p['id']+'.html');html.write_text('tamper',encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'Preview'):v.review(self.root,self.decision(p),'reedos')

    def test_review_requires_identity_confirmation_and_current_decision(self):
        p=self.proposal();value=self.decision(p)
        with self.assertRaises(ValueError):v.review(self.root,value,'model')
        value['confirmed']=False
        with self.assertRaises(ValueError):v.review(self.root,value,'reedos')
        value['confirmed']=True;v.review(self.root,value,'reedos')
        with self.assertRaisesRegex(ValueError,'Stale'):v.review(self.root,value,'reedos')

    def test_decline_suppresses_reworded_identical_suggestion(self):
        p=self.proposal();v.review(self.root,self.decision(p,'rejected'),'reedos')
        def adapter(runtime,system,prompt,schema):
            r=answer(json.loads(prompt));r['why']['text']='Different wording for the same suggested chart.';return r
        result=v.assess(self.root,True,adapter=adapter,at=AT)
        self.assertEqual(result['proposals'],[]);self.assertEqual(len(v.inbox(self.root)['proposals']),1)

    def test_keep_is_not_a_pending_card_and_cache_skips_calls(self):
        r=self.assess('KEEP');self.assertEqual(r['rows'][0]['status'],'KEEP');self.assertEqual(r['proposals'],[])
        with patch('research.ollama',side_effect=AssertionError('Cached')):
            cached=v.assess(self.root,True,at=AT)
        self.assertEqual(cached['model_calls'],0);self.assertEqual(cached['rows'][0]['model_status'],'cached')

    def test_bad_model_answers_are_failures_not_keep(self):
        for change in ['digit','unknown','reference','score']:
            def adapter(runtime,system,prompt,schema):
                r=answer(json.loads(prompt))
                if change=='digit':r['why']['text']='Claims 900 million jobs.'
                if change=='unknown':r['approve']=True
                if change=='reference':r['why']['refs']=['invented']
                if change=='score':r['incumbent_scores']={'made_up':100}
                return r
            r=v.assess(self.root,True,adapter=adapter,at=AT)
            self.assertEqual(r['rows'][0]['status'],'EVALUATION_FAILED');self.assertEqual(len(r['failures']),1)

    def test_timeout_does_not_touch_evidence(self):
        before=v.material(self.root)
        def adapter(*args):raise TimeoutError('fixture timeout')
        r=v.assess(self.root,True,adapter=adapter,at=AT)
        self.assertEqual(len(r['failures']),1);self.assertEqual(before,v.material(self.root))

    def test_specification_requires_endorsement_not_final_approval(self):
        p=v.policy(self.root);p['displays']=[d for d in v.policy(ROOT)['displays'] if d['id']=='construction'];save(self.root/'research/visual-policy.json',p)
        item=self.proposal();self.assertTrue(item['implementation_required'])
        with self.assertRaises(ValueError):v.review(self.root,self.decision(item),'reedos')
        self.assertTrue(v.review(self.root,self.decision(item,'endorsed'),'reedos')['saved'])

    def test_model_budget_and_fair_rotation_include_unassessed(self):
        p=v.policy(self.root);p['displays']=[d for d in v.policy(ROOT)['displays'] if d['id'] in {'construction','fairwater','hiring-demand'}];p['model_calls']=1;save(self.root/'research/visual-policy.json',p)
        a=self.assess('KEEP');b=self.assess('KEEP')
        self.assertEqual(a['model_calls'],1);self.assertEqual(b['model_calls'],1)
        self.assertEqual(len(a['unassessed']),2);self.assertEqual(len(b['unassessed']),1)

    def test_failed_display_cannot_starve_other_displays(self):
        p=v.policy(self.root);p['displays']=[d for d in v.policy(ROOT)['displays'] if d['id'] in {'construction','fairwater'}];p['model_calls']=1;save(self.root/'research/visual-policy.json',p)
        def adapter(*args):raise RuntimeError('fixture')
        a=v.assess(self.root,True,adapter=adapter,at=AT);b=v.assess(self.root,True,adapter=adapter,at=AT)
        self.assertNotEqual(a['failures'][0]['display'],b['failures'][0]['display'])

    def test_oversize_packet_not_silently_truncated(self):
        ep=ed.read(self.root/'research/editorial-policy.json');ep['budgets']['input_characters']=100;save(self.root/'research/editorial-policy.json',ep)
        with patch('research.ollama',side_effect=AssertionError('No packet')):
            r=v.assess(self.root,True,at=AT)
        self.assertEqual(r['model_calls'],0);self.assertIn('budget',r['failures'][0]['reason'])

    def test_decline_can_be_saved_after_evidence_changes(self):
        p=self.proposal();l=ed.read(self.root/'site/data/ledger.json');l['observations'][0]['note']='fixture';save(self.root/'site/data/ledger.json',l)
        self.assertTrue(v.review(self.root,self.decision(p,'rejected'),'reedos')['saved'])

    def test_defer_needs_future_date(self):
        p=self.proposal();value=self.decision(p,'deferred')
        with self.assertRaises(ValueError):v.review(self.root,value,'reedos')
        value['reconsider_after']='2099-01-01T00:00:00Z';v.review(self.root,value,'reedos')
        self.assertEqual(self.assess()['proposals'],[])

    def test_stop_and_failure_never_trigger_model(self):
        for state in ['stopped','blocked','failed','interrupted']:
            with patch.object(v,'assess',return_value={}) as assess:
                v.finish_session(self.root,{'state':state},self.root/'.local/session-fixture')
                self.assertFalse(assess.call_args.kwargs['use_model'])
        with patch.object(v,'assess',return_value={}) as assess:
            v.finish_session(self.root,{'state':'completed'},self.root/'.local/session-fixture')
            self.assertTrue(assess.call_args.kwargs['use_model'])

    def test_session_assessment_failure_is_private(self):
        folder=self.root/'.local/session-fixture'
        with patch.object(v,'assess',side_effect=RuntimeError('fixture')):v.finish_session(self.root,{'state':'completed'},folder)
        self.assertEqual(ed.read(folder/'visual-recommendations.json')['status'],'failed')

    def test_checkpoint_detects_change_without_queue(self):
        folder=self.root/'.local/session-fixture';self.assertEqual(v.checkpoint(self.root,folder),[])
        l=ed.read(self.root/'site/data/ledger.json');next(o for o in l['observations'] if o['metric']=='tsmc-cowos-wpm')['note']+=' fixture';save(self.root/'site/data/ledger.json',l)
        self.assertEqual(v.checkpoint(self.root,folder),['highlight-chips'])
        self.assertFalse(v.er.queue(self.root).exists())

    def test_path_traversal_and_unknown_contract_rejected(self):
        with self.assertRaises(ValueError):v.load(self.root,'../../research/homepage')
        p=v.policy(self.root);p['displays'][0]['renderer']='execute-model-code';save(self.root/'research/visual-policy.json',p)
        with self.assertRaises(ValueError):v.policy(self.root)

    def test_on_demand_model_does_not_overlap_research(self):
        lock=self.root/'.local/research-session.lock';lock.parent.mkdir();lock.touch()
        with self.assertRaisesRegex(ValueError,'active research'):self.assess()

    def test_changed_proposed_config_cannot_reuse_old_preview(self):
        p=self.proposal();raw=ed.read(v.er.queue(self.root)/(p['id']+'.json'))
        raw['config_after']['slots']['models']['visualization']='demoted';save(v.er.queue(self.root)/(p['id']+'.json'),raw)
        revised=v.inbox(self.root)['proposals'][0]
        with self.assertRaisesRegex(ValueError,'Preview|validated response'):v.review(self.root,self.decision(revised),'reedos')

    def test_request_changes_allows_new_revision_for_review(self):
        p=self.proposal();v.review(self.root,self.decision(p,'changes_requested'),'reedos')
        result=self.assess();self.assertEqual(len(result['proposals']),1);self.assertNotEqual(result['proposals'][0],p['id'])


class RealDataContracts(unittest.TestCase):
    def test_inventory_coverage_and_calculations(self):
        s=v.frozen(ROOT);rows,f=v.contracts_assessment(s,AT)
        self.assertEqual(len(rows),19);self.assertFalse(any(r['missing_metrics'] for r in rows))
        by={r['id']:r for r in rows}
        self.assertEqual(by['hiring-demand']['calculation']['approximate_multiple'],3)
        self.assertIn('forbidden',by['fairwater']['calculation']['aggregation'])
        self.assertIsNone(by['capital']['calculation']['growth'])
        self.assertGreater(by['construction']['calculation']['percent'],50)
        for d in s['research/visual-policy.json']['displays']:v.packet(s,d,f,[],0)

    def test_missing_capex_member_prevents_total(self):
        s=v.frozen(ROOT);d=next(d for d in s['research/visual-policy.json']['displays'] if d['id']=='capital')
        s['site/data/ledger.json']['observations']=[o for o in s['site/data/ledger.json']['observations'] if o['metric']!='capital-cash-aws']
        self.assertEqual(v.calculation(s,d)['totals'],[])

    def test_posting_volume_cannot_substitute_for_share(self):
        s=v.frozen(ROOT);d=next(d for d in s['research/visual-policy.json']['displays'] if d['id']=='hiring-demand')
        s['site/data/ledger.json']['observations']=[o for o in s['site/data/ledger.json']['observations'] if o['metric']!='indeed-dc-postings-share']
        self.assertIn('blocked',v.calculation(s,d))

    def test_changed_construction_vintage_prevents_growth(self):
        s=v.frozen(ROOT);d=next(d for d in s['research/visual-policy.json']['displays'] if d['id']=='construction')
        o=max((o for o in s['site/data/ledger.json']['observations'] if o['metric']=='census-dc-construction-saar'),key=lambda o:o['period']);o['source']='different-vintage'
        self.assertIn('blocked',v.calculation(s,d))


if __name__=='__main__':unittest.main()
