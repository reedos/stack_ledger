import copy
import json
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from validate_claims import validate_claims, validate_files
from render_claims import render_claims, water_values


class ClaimsTests(unittest.TestCase):
    def setUp(self):
        self.data=json.loads((ROOT/'research/claims.json').read_text(encoding='utf-8'))
        self.sources=json.loads((ROOT/'site/data/ledger.json').read_text(encoding='utf-8'))['sources']

    def test_reviewed_mirror_and_provenance(self):
        self.assertTrue(validate_files())
        for change in ['unknown-source','duplicate-id','invalid-number','missing-scope']:
            data=copy.deepcopy(self.data)
            if change=='unknown-source':data['claims'][0]['sources']=['invented']
            if change=='duplicate-id':data['claims'][1]['id']=data['claims'][0]['id']
            if change=='invalid-number':data['highlights'][0]['points'][0]['value']=float('nan')
            if change=='missing-scope':del data['claims'][0]['scope']
            with self.subTest(change=change),self.assertRaises(ValueError):
                validate_claims(data,{s['id'] for s in self.sources})

    def test_static_evidence_preserves_forecast_and_unresolved_claims(self):
        html=render_claims(self.data,self.sources)
        self.assertEqual(html.count('class="claim-card"'),len(self.data['claims']))
        self.assertIn('evidence-bar forecast',html)
        self.assertIn('Primary evidence gap',html)
        self.assertIn('What future projects should show',html)
        self.assertIn('<caption>',html)
        self.assertNotIn('localhost',html)

    def test_research_text_cannot_become_markup(self):
        self.data['claims'][0]['claim']='<script>bad()</script>'
        html=render_claims(self.data,self.sources)
        self.assertNotIn('<script>',html)
        self.assertIn('&lt;script&gt;',html)

    def test_almond_calculation_converts_units_without_rounding_inputs(self):
        liters,ml,ratio=water_values(self.data['water_comparison'])
        self.assertAlmostEqual(ml,0.32176000164)
        self.assertAlmostEqual(ratio,610*1.2/453.59237/0.000085)
        self.assertGreater(liters,6.1)
        self.assertLess(liters,6.2)
        self.assertEqual(round(ratio/1000)*1000,19000)
        html=render_claims(self.data,self.sources)
        self.assertIn('not a verified equivalence',html)
        self.assertIn('illustrative assumption',html)
        self.assertIn('blue water only',html)

    def test_zero_query_denominator_rejected(self):
        self.data['water_comparison']['query_gallons']=0
        with self.assertRaises(ValueError):
            validate_claims(self.data,{s['id'] for s in self.sources})
