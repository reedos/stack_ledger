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
        self.assertNotIn('company',a['targets']);self.assertNotIn('metric',a['targets']);self.assertNotIn('product',a['targets'])
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

    def test_rank_ceiling_uses_the_best_registered_rank_on_the_host(self):
        ranks=pp.source_ranks(self.registry)
        self.assertEqual(ranks.get('epoch.ai'),1)
        self.assertTrue(all(1<=r<=6 for r in ranks.values()))


if __name__=='__main__':unittest.main()
