import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from render import company_snapshot, COMPANY_IDS
from validate_ecosystem import validate_ecosystem
from validate_expansion import validate_files


class CompanyProfiles(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((ROOT / 'site/data/ledger.json').read_text(encoding='utf-8'))
        self.eco = json.loads((ROOT / 'research/ecosystem.json').read_text(encoding='utf-8'))

    def test_all_profiles_are_built_and_have_correct_depth(self):
        for cid in COMPANY_IDS:
            html = (ROOT / f'docs/companies/{cid}/index.html').read_text(encoding='utf-8')
            self.assertIn('data-base="../../"', html)
            self.assertIn(f'data-company="{cid}"', html)
            self.assertIn(f'https://reedos.github.io/stack_ledger/companies/{cid}/', html)

    def test_company_output_metric_renders_as_headline_when_configured(self):
        import copy
        c=copy.deepcopy(next(x for x in self.eco['companies'] if x['id']=='nvidia'));c['output_metric']='epoch-nvidia-ai-chips-cumulative-yearly'
        html=company_snapshot(self.data,c,'../../')
        self.assertIn('company-output',html);self.assertIn('accelerators (cumulative)',html);self.assertIn('Historical estimate',html);self.assertIn('Epoch AI',html)
        plain=company_snapshot(self.data,next(x for x in self.eco['companies'] if x['id']=='nvidia'),'../../');self.assertNotIn('company-output',plain)

    def test_no_script_snapshot_contains_revenue_and_forecast(self):
        c = next(c for c in self.eco['companies'] if c['id'] == 'asml')
        html = company_snapshot(self.data, c, '../../')
        self.assertIn('2030', html)
        self.assertIn('44–60', html)
        # ASML's own 2030 investor-day scenario is company guidance; the nearer-term Stock
        # Analysis/S&P Global consensus years are an independent projection -- both attributed.
        self.assertIn('Company guidance', html)
        self.assertIn('Independent projection', html)
        self.assertIn('EUR billion', html)

    def test_route_traversal_is_rejected(self):
        bad = copy.deepcopy(self.eco)
        bad['companies'][0]['id'] = '../../escape'
        with self.assertRaisesRegex(ValueError, 'Unsafe company route'):
            validate_ecosystem(bad, self.data)

    def test_forecasts_are_separate_from_recognized_revenue(self):
        validate_files()
        metrics = {m['id']: m for m in self.data['metrics']}
        for c in self.eco['companies']:
            m = metrics.get(c.get('revenue_chart_metric') or c['revenue_metric'])
            if not m or not m.get('chart_companion_metric'): continue
            f = metrics[m['chart_companion_metric']]
            self.assertEqual(f['company'], c['id'])
            self.assertEqual(m['unit'], f['unit'])
            self.assertEqual(f['allowed_statuses'], ['forecast'])
            self.assertTrue(all(o['status'] == 'forecast' for o in self.data['observations'] if o['metric'] == f['id']))


if __name__ == '__main__': unittest.main()
