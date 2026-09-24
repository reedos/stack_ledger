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

    def test_policy_import_author_is_listed_but_its_events_still_need_a_human(self):
        # Grid-interface tracking (2026-09-10): Federal Register grade-A government-action
        # events are additions from an official authority, so 'Policy import (maintainer
        # tool)' joins the reviewed author list -- confirmed here. But a *source* or *note*
        # (event) addition stays off auto_apply.targets on purpose, by the same reviewed rule
        # test_source_or_note_addition_is_never_eligible_regardless_of_author_or_rank checks
        # for every other author: eligible() correctly refuses a Federal Register package
        # shaped exactly like this importer's own additions, regardless of author or rank.
        # scripts/import_policy.py therefore publishes through the non-pushing
        # scripts/importer_common.apply_changes lane instead, never through this one.
        self.assertIn('Policy import (maintainer tool)', self.policy['auto_apply']['authors'])
        source_after = {'id': 'federal-register-2026-18370', 'publisher': 'U.S. Department of Energy',
                         'title': 'Securing the United States Bulk-Power System', 'url': 'https://www.federalregister.gov/documents/2026/09/09/2026-18370/x',
                         'published': '2026-09-09', 'layers': ['energy'], 'license': 'Public domain (U.S. government work)', 'provenance': 'official'}
        note_after = {'id': 'policy-2026-18370', 'layer': 'energy', 'date': '2026-09-09', 'title': 'Securing the United States Bulk-Power System',
                      'summary': 'Notice from U.S. Department of Energy.', 'source': 'federal-register-2026-18370', 'kind': 'Government action', 'grade': 'A'}
        package = {'author': 'Policy import (maintainer tool)',
                   'changes': [{'target': 'source', 'id': source_after['id'], 'before': None, 'after': source_after, 'evidence': ['e1']},
                               {'target': 'note', 'id': note_after['id'], 'before': None, 'after': note_after, 'evidence': ['e1']}],
                   'evidence': [{'id': 'e1', 'url': source_after['url'], 'published_at': '2026-09-09', 'retrieved_at': '2026-09-09T09:00:00Z', 'sha256': 'b'*64, 'summary': 'doc'}]}
        ok, reasons = pp.eligible(package, self.policy, self.registry)
        self.assertFalse(ok)
        self.assertTrue(any('always needs human review' in r for r in reasons), reasons)

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


class ApplyAdmittedTests(unittest.TestCase):
    """One package that fails its preview is left for the owner; the rest still go, until the deadline."""
    def test_a_failed_package_does_not_stop_the_others_and_the_deadline_defers_the_rest(self):
        import publication_policy as pp
        from unittest import mock
        calls=[]
        def fake(root,rid,p):
            calls.append(rid)
            if rid=='catalog-a':raise ValueError('Preview validation failed; left for human review')
            return {'status':'pushed'}
        with mock.patch.object(pp,'admissions',return_value=([],['catalog-a','catalog-b'])),mock.patch.object(pp,'auto_apply',side_effect=fake), \
             mock.patch('research.load',return_value={}):
            result=pp.apply_admitted(ROOT,{'auto_apply':{}})
        self.assertEqual(calls,['catalog-a','catalog-b'])
        self.assertTrue(result['outcomes']['catalog-a'].startswith('failed'));self.assertEqual(result['outcomes']['catalog-b'],'pushed')
        with mock.patch.object(pp,'admissions',return_value=([],['catalog-c'])),mock.patch.object(pp,'auto_apply',side_effect=fake), \
             mock.patch('research.load',return_value={}):
            late=pp.apply_admitted(ROOT,{'auto_apply':{}},deadline=0)
        self.assertTrue(late['outcomes']['catalog-c'].startswith('deferred'))



class OwnerDecisionTests(unittest.TestCase):
    """A person's Defer or Reject is never overridden by the policy (review findings, 09/24/2026)."""
    def test_a_deferred_package_is_not_the_policys_to_publish(self):
        import catalog_review as cr
        from unittest import mock
        rows=[{'id':'catalog-a','status':'pending_review'},{'id':'catalog-b','status':'deferred','last_review':{'reviewer':'owner'}},
              {'id':'catalog-c','status':'approved','last_review':{'reviewer':'publication-policy'}},{'id':'catalog-d','status':'approved','last_review':{'reviewer':'owner'}}]
        with mock.patch.object(cr,'inbox',return_value=rows):
            self.assertEqual([q['id'] for q in pp.pending(ROOT)],['catalog-a','catalog-c'])

    def test_a_decision_recorded_while_the_preview_ran_stands(self):
        import tempfile
        import catalog_review as cr
        from unittest import mock
        package={'id':'catalog-'+'a'*24,'author':'x','changes':[]}
        reviews=iter([None,{'id':package['id'],'status':'rejected','reviewer':'owner'}])
        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch('research.load',return_value={}), mock.patch.object(cr,'package',return_value=package), \
             mock.patch.object(cr,'last_review',side_effect=lambda root,rid:next(reviews)), \
             mock.patch.object(pp,'eligible',return_value=(True,['ok'])), mock.patch.object(cr,'check_base'), mock.patch.object(cr,'check_evidence'), \
             mock.patch.object(cr,'preview_validation',side_effect=ValueError('no saved preview')), \
             mock.patch.object(cr,'preview',return_value={'passed':True,'proposal_hash':cr.digest(package)}), \
             mock.patch.object(cr,'publish_package') as publish:
            with self.assertRaisesRegex(ValueError,'decided while its preview ran'):
                pp.auto_apply(Path(tmp),package['id'],{'auto_apply':{'reviewer_label':'publication-policy'}})
        publish.assert_not_called()

    def test_a_column_slip_is_judged_against_the_same_page_only(self):
        old={'id':'o','metric':'m','source':'page-a','year':2026,'value':100.0,'upper':None}
        new=dict(old,id='n',value=104.0)
        other_page={'id':'x','metric':'m','source':'page-b','year':2026,'value':104.0,'upper':None}
        ledger={'observations':[old,{'id':'o27','metric':'m','source':'page-a','year':2027,'value':150.0,'upper':None}]}
        self.assertIsNone(pp._column_slip(new,old,ledger,[other_page]),'another page\'s reading is not this page\'s neighbouring column')
        self.assertIn('as near',pp._column_slip(new,old,ledger,[dict(other_page,source='page-a',year=2027)]))

    def test_the_same_page_list_is_the_pages_that_update_in_place(self):
        rule=pp.policy(ROOT)['auto_apply']['same_page_revisions']
        registry=json.loads((ROOT/'research/sources.json').read_text(encoding='utf-8'))
        from urllib.parse import urlparse
        urls={s['id']:s['url'] for s in registry['sources']}
        self.assertTrue(set(rule['sources'])<=set(urls),'every listed page is registered')
        self.assertEqual({urlparse(urls[s]).hostname for s in rule['sources']},{'stockanalysis.com','epoch.ai','www.bls.gov'})
        self.assertFalse([s for s in rule['sources'] if urls[s].lower().endswith('.pdf')],'a PDF never revises itself')
        self.assertEqual(rule['max_ratio'],1.1)

if __name__=='__main__':unittest.main()

