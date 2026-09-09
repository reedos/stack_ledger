import copy
import json
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import publication_policy as pp


class PublicationPolicyTests(unittest.TestCase):
    def setUp(self):
        self.policy=pp.policy(ROOT)
        self.registry=json.loads((ROOT/'research/sources.json').read_text(encoding='utf-8'))
        self.package={'author':'Epoch import (maintainer tool)','changes':[{'target':'project','id':'x','before':None,'after':{'id':'x','stage':'status-unverified'},'evidence':['e1']}],
                      'evidence':[{'id':'e1','url':'https://epoch.ai/data/ai-data-centers','published_at':None,'retrieved_at':'2026-09-09T09:00:00Z','sha256':'a'*64,'summary':'row'}]}

    def test_policy_file_is_reviewed_and_bounded(self):
        a=self.policy['auto_apply']
        self.assertTrue(a['new_entries_only'] and a['require_passing_preview'])
        self.assertNotIn('company',a['targets']);self.assertNotIn('product',a['targets'])
        self.assertTrue(all(t.startswith('estimated_site_') for t in a['metric_measurement_types']));self.assertEqual(a['project_updates'],'append_observations_only')
        self.assertTrue(any('headline' in line for line in self.policy['always_human']))

    def test_epoch_addition_is_admitted(self):
        ok,reasons=pp.eligible(self.package,self.policy,self.registry)
        self.assertTrue(ok,reasons)

    def test_anything_that_replaces_or_widens_needs_a_human(self):
        cases={'existing object':lambda q:q['changes'][0].__setitem__('before',{'id':'x'}),
               'operating stage':lambda q:q['changes'][0]['after'].__setitem__('stage','operating'),
               'company target':lambda q:q['changes'][0].__setitem__('target','company'),
               'unknown author':lambda q:q.__setitem__('author','GPT Astra'),
               'low-rank evidence host':lambda q:q['evidence'][0].__setitem__('url','https://www.datacenterdynamics.com/x'),
               'unregistered host':lambda q:q['evidence'][0].__setitem__('url','https://example.org/x'),
               'disabled':None}
        for label,mutate in cases.items():
            with self.subTest(case=label):
                q=copy.deepcopy(self.package);p=copy.deepcopy(self.policy)
                if mutate:mutate(q)
                else:p['auto_apply']['enabled']=False
                ok,reasons=pp.eligible(q,p,self.registry)
                self.assertFalse(ok,label);self.assertTrue(reasons)

    def test_site_estimate_metrics_and_append_only_project_updates_are_admitted(self):
        q=copy.deepcopy(self.package)
        before={'id':'x','stage':'status-unverified','observations':['old']}
        q['changes']=[{'target':'metric','id':'epoch-x-it-mw','before':None,'after':{'id':'epoch-x-it-mw','measurement_type':'estimated_site_it_mw','allowed_statuses':['estimate']},'evidence':['e1']},
                      {'target':'observation','id':'epoch-x-it-mw-2026-09-09','before':None,'after':{'status':'estimate'},'evidence':['e1']},
                      {'target':'project','id':'x','before':before,'after':dict(before,observations=['old','epoch-x-it-mw-2026-09-09']),'evidence':['e1']}]
        self.assertTrue(pp.eligible(q,self.policy,self.registry)[0])
        bad=copy.deepcopy(q);bad['changes'][2]['after']['stage']='operating'
        self.assertFalse(pp.eligible(bad,self.policy,self.registry)[0])
        bad=copy.deepcopy(q);bad['changes'][2]['after']['observations']=['epoch-x-it-mw-2026-09-09']   # drops 'old'
        self.assertFalse(pp.eligible(bad,self.policy,self.registry)[0])
        bad=copy.deepcopy(q);bad['changes'][0]['after']['measurement_type']='capex_recognized_usd'
        self.assertFalse(pp.eligible(bad,self.policy,self.registry)[0])
        bad=copy.deepcopy(q);bad['changes'][0]['after']['allowed_statuses']=['observation','estimate']
        self.assertFalse(pp.eligible(bad,self.policy,self.registry)[0])

    def test_rank_ceiling_uses_the_best_registered_rank_on_the_host(self):
        ranks=pp.source_ranks(self.registry)
        self.assertEqual(ranks.get('epoch.ai'),1)
        self.assertTrue(all(1<=r<=6 for r in ranks.values()))

    def test_magnitude_sanity_rule_both_sides(self):
        ledger={'observations':[{'metric':'m1','value':100},{'metric':'m1','value':110},{'metric':'m1','value':90}]}
        def addition(value):
            return {'author':'Epoch import (maintainer tool)','evidence':self.package['evidence'],
                    'changes':[{'target':'observation','id':'o-new','before':None,'after':{'status':'estimate','metric':'m1','value':value},'evidence':['e1']}]}
        ok,reasons=pp.eligible(addition(105),self.policy,self.registry,ledger)   # within [min/10, max*10] = [9, 1100]
        self.assertTrue(ok,reasons)
        ok,reasons=pp.eligible(addition(2000),self.policy,self.registry,ledger)  # above max*10
        self.assertFalse(ok);self.assertIn('magnitude outside trailing range',reasons[0])
        ok,reasons=pp.eligible(addition(1),self.policy,self.registry,ledger)     # below min/10
        self.assertFalse(ok);self.assertIn('magnitude outside trailing range',reasons[0])
        fewer={'observations':ledger['observations'][:2]}                        # under three trailing values: rule does not apply
        self.assertTrue(pp.eligible(addition(999999),self.policy,self.registry,fewer)[0])
        self.assertTrue(pp.eligible(addition(2000),self.policy,self.registry,None)[0])  # no ledger supplied: rule skipped, not enforced

    def test_admissions_and_apply_admitted_stop_at_first_failure(self):
        from unittest.mock import patch
        with patch.object(pp,'pending',return_value=[dict(self.package,id='catalog-'+'a'*24,title='Fixture',status='pending_review')]):
            rows,admitted=pp.admissions(ROOT,self.policy,self.registry,None)
            self.assertEqual(admitted,['catalog-'+'a'*24]);self.assertTrue(rows[0]['admitted'])
            with patch.object(pp,'auto_apply',side_effect=RuntimeError('boom')):
                result=pp.apply_admitted(ROOT,self.policy)
                self.assertEqual(result['pending'],1);self.assertTrue(result['outcomes']['catalog-'+'a'*24].startswith('failed'))


if __name__=='__main__':unittest.main()
