import copy
import json
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from validate_delivery import validate_delivery,validate_files

class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.data=json.loads((ROOT/'site/data/delivery.json').read_text(encoding='utf-8'))
        self.ledger=json.loads((ROOT/'site/data/ledger.json').read_text(encoding='utf-8'))
    def test_reviewed_tracker_resolves_sources_and_observations(self):
        self.assertTrue(validate_files())
    def test_plans_cannot_be_labeled_operating_capacity(self):
        p=next(p for p in self.data['projects'] if p['id']=='cape-one');p['stage']='operating'
        with self.assertRaisesRegex(ValueError,'plans alone'):validate_delivery(self.data,self.ledger)
    def test_retrieval_date_cannot_replace_milestone_date(self):
        self.data['projects'][0]['milestones'][0]['date']='2026-09-07'
        with self.assertRaisesRegex(ValueError,'publication date'):validate_delivery(self.data,self.ledger)
    def test_unknown_capacity_is_valid_but_invented_reference_is_not(self):
        p=next(p for p in self.data['projects'] if p['id']=='fairwater-one')
        self.assertEqual(p['observations'],[])
        self.assertTrue(validate_delivery(self.data,self.ledger))
        p['observations']=['invented-capacity']
        with self.assertRaisesRegex(ValueError,'Missing or superseded'):validate_delivery(self.data,self.ledger)
    def test_superseded_capacity_requires_review(self):
        id=self.data['projects'][0]['observations'][0]
        next(o for o in self.ledger['observations'] if o['id']==id)['superseded_by']='new'
        with self.assertRaisesRegex(ValueError,'superseded'):validate_delivery(self.data,self.ledger)
