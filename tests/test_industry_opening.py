import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from render_industry import industry_opening


class IndustryOpeningTests(unittest.TestCase):
    def setUp(self):
        self.ledger = json.loads((ROOT / 'site/data/ledger.json').read_text(encoding='utf8'))

    def render(self):
        return industry_opening(self.ledger, '../')

    def test_accepted_evidence_and_bounds(self):
        html = self.render()
        self.assertIn('+57%', html)
        self.assertIn('$47.8B', html)
        self.assertIn('$75.2B', html)
        self.assertIn('≈3×', html)
        self.assertIn('≈10,000', html)
        self.assertIn('≈550', html)
        self.assertIn('construction contributors over two years', html)
        self.assertIn('seasonally adjusted annual rate', html)
        self.assertIn('not job counts or hires', html)
        self.assertIn('not added', html)

    def test_no_growth_without_comparable_baseline(self):
        self.ledger['observations'] = [o for o in self.ledger['observations'] if o['id'] != 'census-dc-construction-saar-0']
        self.assertNotIn('+57%', self.render())
        self.assertIn('No year-over-year growth is inferred', self.render())

    def test_different_vintage_not_spliced(self):
        next(o for o in self.ledger['observations'] if o['id'] == 'census-dc-construction-saar-0')['source'] = 'other-vintage'
        self.assertNotIn('+57%', self.render())

    def test_forecast_does_not_replace_estimate(self):
        future = copy.deepcopy(next(o for o in self.ledger['observations'] if o['id'] == 'census-dc-construction-saar-5'))
        future.update(id='future', year=2027, period='2027-07', value=150000, status='forecast')
        self.ledger['observations'].append(future)
        self.assertNotIn('$150.0B', self.render())
        self.assertIn('+57%', self.render())

    def test_superseded_records_not_reused(self):
        next(o for o in self.ledger['observations'] if o['id'] == 'fairwater-onsite-employees-2026')['superseded_by'] = 'reviewed-correction'
        self.assertNotIn('industry-workflow', self.render())

    def test_accepted_revision_recalculates_comparison(self):
        next(o for o in self.ledger['observations'] if o['id'] == 'census-dc-construction-saar-5')['value'] = 47810
        self.assertIn('+0%', self.render())
        self.assertNotIn('+57%', self.render())

    def test_future_workforce_keeps_scope_and_bounds(self):
        html = self.render()
        self.assertIn('&gt;7,500', html)
        self.assertIn('first three fabs only', html)
        self.assertIn('≥3,000', html)
        self.assertIn('Company workforce plan', html)
        self.assertIn('No combined jobs total', html)
        self.assertIn('Relative share of U.S. postings on Indeed · 2023 = 1×', html)
        self.assertNotIn('<b>100</b>', html)

    def test_superseded_commitment_removed_from_plan_cards(self):
        next(o for o in self.ledger['observations'] if o['id'] == 'terafab-permanent-promised-baseline')['superseded_by'] = 'updated-plan'
        self.assertNotIn('≥3,000', self.render())


if __name__ == '__main__':
    unittest.main()
