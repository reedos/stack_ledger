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

    def test_source_or_note_addition_is_never_eligible_regardless_of_author_or_rank(self):
        # Importers produce project/metric/observation changes; source and note stay human-reviewed
        # (research/publication-policy.json auto_apply.targets no longer lists them).
        self.assertNotIn('source',self.policy['auto_apply']['targets']);self.assertNotIn('note',self.policy['auto_apply']['targets'])
        for target in ['source','note']:
            with self.subTest(target=target):
                q=copy.deepcopy(self.package)
                q['changes']=[{'target':target,'id':'x','before':None,'after':{'id':'x'},'evidence':['e1']}]
                ok,reasons=pp.eligible(q,self.policy,self.registry)
                self.assertFalse(ok)
                self.assertTrue(any('always needs human review' in r for r in reasons),reasons)

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

    def observation(self, **over):
        base={'id':'o1','metric':'m1','year':2026,'period':'2026-Q1','value':10,'upper':None,'status':'estimate',
              'source':'s1','precision':'eq','method':'automated','note':'old','retrieved_at':'2026-01-01T00:00:00Z'}
        base.update(over);return base

    def relabel_package(self,changes):
        return {'author':'Epoch import (maintainer tool)','evidence':self.package['evidence'],'changes':changes}

    def test_same_source_relabel_flag_is_reviewed(self):
        self.assertTrue(self.policy['auto_apply']['same_source_relabel'])
        self.assertTrue(any('period, year, note, retrieved_at' in line for line in self.policy['always_human']))

    def test_relabel_admits_period_note_and_retrieved_at_changes(self):
        before=self.observation()
        after=dict(before,period='2026-Q2',note='relabeled',retrieved_at='2026-09-09T00:00:00Z')
        pkg=self.relabel_package([{'target':'observation','id':'o1','before':before,'after':after,'evidence':['e1']}])
        ok,reasons=pp.eligible(pkg,self.policy,self.registry)
        self.assertTrue(ok,reasons)

    def test_relabel_ignores_the_per_package_change_ceiling(self):
        changes=[]
        for i in range(self.policy['auto_apply']['max_changes_per_package']+5):
            before=self.observation(id=f'o{i}')
            after=dict(before,period='2026-Q2',retrieved_at='2026-09-09T00:00:00Z')
            changes.append({'target':'observation','id':f'o{i}','before':before,'after':after,'evidence':['e1']})
        ok,reasons=pp.eligible(self.relabel_package(changes),self.policy,self.registry)
        self.assertTrue(ok,reasons)

    def test_relabel_never_admits_a_changed_value_status_or_source(self):
        before=self.observation()
        for field,new in [('value',11),('status','observation'),('source','s2')]:
            after=dict(before,**{field:new},retrieved_at='2026-09-09T00:00:00Z')
            pkg=self.relabel_package([{'target':'observation','id':'o1','before':before,'after':after,'evidence':['e1']}])
            ok,reasons=pp.eligible(pkg,self.policy,self.registry)
            with self.subTest(field=field):
                self.assertFalse(ok);self.assertTrue(any('already exists' in r for r in reasons),reasons)

    def test_relabel_requires_year_period_consistency(self):
        before=self.observation()
        after=dict(before,period='2026-Q2',year=2027)   # period says 2026, year claims 2027
        pkg=self.relabel_package([{'target':'observation','id':'o1','before':before,'after':after,'evidence':['e1']}])
        self.assertFalse(pp.eligible(pkg,self.policy,self.registry)[0])

    def test_relabel_disabled_by_policy_falls_back_to_human_review(self):
        before=self.observation()
        after=dict(before,note='relabeled',retrieved_at='2026-09-09T00:00:00Z')
        pkg=self.relabel_package([{'target':'observation','id':'o1','before':before,'after':after,'evidence':['e1']}])
        disabled=copy.deepcopy(self.policy);disabled['auto_apply']['same_source_relabel']=False
        ok,reasons=pp.eligible(pkg,disabled,self.registry)
        self.assertFalse(ok);self.assertTrue(any('already exists' in r for r in reasons),reasons)

    def test_admissions_and_apply_admitted_stop_at_first_failure(self):
        from unittest.mock import patch
        with patch.object(pp,'pending',return_value=[dict(self.package,id='catalog-'+'a'*24,title='Fixture',status='pending_review')]):
            rows,admitted=pp.admissions(ROOT,self.policy,self.registry,None)
            self.assertEqual(admitted,['catalog-'+'a'*24]);self.assertTrue(rows[0]['admitted'])
            with patch.object(pp,'auto_apply',side_effect=RuntimeError('boom')):
                result=pp.apply_admitted(ROOT,self.policy)
                self.assertEqual(result['pending'],1);self.assertTrue(result['outcomes']['catalog-'+'a'*24].startswith('failed'))


if __name__=='__main__':unittest.main()
