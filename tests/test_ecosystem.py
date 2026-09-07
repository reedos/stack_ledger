import copy
import json
import sys
import unittest
from pathlib import Path
from datetime import date, timedelta

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from validate_ecosystem import validate_ecosystem, validate_files
from research import source_queue

class EcosystemTests(unittest.TestCase):
    def setUp(self):
        self.data=json.loads((ROOT/'site/data/ecosystem.json').read_text(encoding='utf-8'))
        self.ledger=json.loads((ROOT/'site/data/ledger.json').read_text(encoding='utf-8'))

    def test_reviewed_dataset_has_resolvable_evidence(self):
        self.assertTrue(validate_files())

    def test_weekly_rotation_reaches_expanded_registry(self):
        registry=json.loads((ROOT/'research/sources.json').read_text(encoding='utf-8'))
        reached=set()
        for n in range(7):
            queue=source_queue(registry,date(2026,9,7)+timedelta(days=n))
            self.assertEqual(len(queue),len({s['id'] for s in queue}))
            self.assertEqual(queue[0]['id'],'iea-2026')
            reached.update(s['id'] for s in queue[:12])
        self.assertEqual(reached,{s['id'] for s in registry['sources'] if s['layers']})

    def test_missing_revenue_or_source_blocks_publication(self):
        data=copy.deepcopy(self.data);data['companies'][0]['revenue_metric']='invented'
        with self.assertRaisesRegex(ValueError,'Missing revenue'):validate_ecosystem(data,self.ledger)
        data=copy.deepcopy(self.data);data['jobs'][0]['source']='unverified'
        with self.assertRaisesRegex(ValueError,'Unknown jobs'):validate_ecosystem(data,self.ledger)

    def test_forecast_cannot_stand_in_for_reported_revenue(self):
        metric=self.data['companies'][0]['revenue_metric']
        for o in self.ledger['observations']:
            if o['metric']==metric:o['status']='forecast'
        with self.assertRaisesRegex(ValueError,'Missing reported revenue'):validate_ecosystem(self.data,self.ledger)

    def test_signed_employment_change_and_invalid_jobs_count(self):
        self.data['employment']['series'][0]['value']=-100
        self.assertTrue(validate_ecosystem(self.data,self.ledger))
        for value in [True,float('nan'),-100]:
            self.data['jobs'][0]['value']=value
            with self.assertRaisesRegex(ValueError,'Invalid jobs value'):validate_ecosystem(self.data,self.ledger)
