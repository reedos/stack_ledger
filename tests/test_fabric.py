import copy
import json
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from validate_fabric import validate_fabric, validate_files
from validate_ecosystem import validate_ecosystem

class FabricTests(unittest.TestCase):
    def setUp(self):
        read=lambda p:json.loads((ROOT/p).read_text(encoding='utf-8'))
        self.fabric=read('research/fabric.json');self.ledger=read('site/data/ledger.json');self.eco=read('research/ecosystem.json')

    def test_reviewed_references_resolve(self):
        self.assertTrue(validate_files())

    def test_unknown_supplier_blocks_publication(self):
        self.fabric['components'][0]['companies'].append('invented')
        with self.assertRaisesRegex(ValueError,'company references'):
            validate_fabric(self.fabric,self.ledger,self.eco)

    def test_source_date_is_not_retrieval_date(self):
        self.fabric['milestones'][0]['date']='2026-09-07'
        with self.assertRaisesRegex(ValueError,'publication date'):
            validate_fabric(self.fabric,self.ledger,self.eco)

    def test_future_investment_cannot_be_reported_production(self):
        self.fabric['energy_cases'][-1]['stage']='Production reported'
        with self.assertRaisesRegex(ValueError,'cannot be a plan'):
            validate_fabric(self.fabric,self.ledger,self.eco)

    def test_superseded_measure_requires_snapshot_review(self):
        id=self.fabric['workforce_observations'][0]
        next(o for o in self.ledger['observations'] if o['id']==id)['superseded_by']='replacement'
        with self.assertRaisesRegex(ValueError,'Superseded'):
            validate_fabric(self.fabric,self.ledger,self.eco)

    def test_missing_revenue_is_explicit_and_not_numeric(self):
        self.assertTrue(validate_ecosystem(self.eco,self.ledger))
        c=next(c for c in self.eco['companies'] if c['revenue_kind']=='unavailable')
        c['revenue_metric']='revenue-nvidia'
        with self.assertRaisesRegex(ValueError,'no numeric metric'):
            validate_ecosystem(self.eco,self.ledger)

    def test_unknown_product_source_blocks_publication(self):
        self.eco['companies'][0]['role_sources']=['invented']
        with self.assertRaisesRegex(ValueError,'role source'):
            validate_ecosystem(self.eco,self.ledger)
