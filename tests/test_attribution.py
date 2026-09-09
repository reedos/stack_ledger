import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import render


class AttributionLabelTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((ROOT / 'site/data/ledger.json').read_text(encoding='utf-8'))
        self.metrics = {m['id']: m for m in self.data['metrics']}
        self.sources = {s['id']: s for s in self.data['sources']}

    def label_for(self, observation_id):
        o = next(o for o in self.data['observations'] if o['id'] == observation_id)
        m = self.metrics[o['metric']]
        return render.attribution_label(o, m, self.sources[o['source']], render.COMPANIES.get(m.get('company')))

    def test_meta_first_party_guidance_is_labeled_company_guidance(self):
        self.assertEqual(self.label_for('capital-guidance-meta-2026-reviewed'), 'Company guidance')

    def test_stock_analysis_consensus_forecast_is_labeled_independent(self):
        self.assertEqual(self.label_for('company-finance-revenue-nvidia-forecast-2027-20260907'), 'Independent projection')

    def test_epoch_end_state_forecast_is_labeled_independent(self):
        self.assertEqual(self.label_for('abilene-it-endstate-baseline'), 'Independent projection')

    def test_observation_status_is_unchanged(self):
        o = next(o for o in self.data['observations'] if o['status'] == 'observation' and not o.get('superseded_by'))
        m = self.metrics[o['metric']]
        self.assertEqual(render.attribution_label(o, m, self.sources[o['source']], render.COMPANIES.get(m.get('company'))), 'Reported observation')

    def test_estimate_company_commitment_and_government_target_keep_their_own_labels(self):
        by_status = {}
        for o in self.data['observations']:
            if o.get('superseded_by') or o['status'] in ('observation', 'forecast'):
                continue
            by_status.setdefault(o['status'], o)
        m = self.metrics[by_status['estimate']['metric']]
        self.assertEqual(render.attribution_label(by_status['estimate'], m, self.sources[by_status['estimate']['source']], render.COMPANIES.get(m.get('company'))), 'Historical estimate')
        m = self.metrics[by_status['company-commitment']['metric']]
        self.assertEqual(render.attribution_label(by_status['company-commitment'], m, self.sources[by_status['company-commitment']['source']], render.COMPANIES.get(m.get('company'))), 'Company commitment')
        m = self.metrics[by_status['government-target']['metric']]
        self.assertEqual(render.attribution_label(by_status['government-target'], m, self.sources[by_status['government-target']['source']], render.COMPANIES.get(m.get('company'))), 'Government target')

    def test_every_forecast_observation_gets_a_definite_attribution(self):
        forecasts = [o for o in self.data['observations'] if o['status'] == 'forecast' and not o.get('superseded_by')]
        self.assertGreater(len(forecasts), 0)
        for o in forecasts:
            m = self.metrics[o['metric']]
            label = render.attribution_label(o, m, self.sources[o['source']], render.COMPANIES.get(m.get('company')))
            self.assertIn(label, ('Company guidance', 'Independent projection'), o['id'])

    def test_name_prefix_matches_full_legal_name_but_not_a_look_alike_publisher(self):
        meta = render.COMPANIES['meta']
        source = {'publisher': 'Meta Platforms, Inc.', 'url': 'https://example.com/press'}
        self.assertTrue(render.is_first_party(source, meta))
        lookalike = {'publisher': 'Metaculus', 'url': 'https://example.com/press'}
        self.assertFalse(render.is_first_party(lookalike, meta))

    def test_host_subdomain_of_ir_url_counts_as_first_party(self):
        meta = render.COMPANIES['meta']
        source = {'publisher': 'Investor Relations', 'url': 'https://www.investor.atmeta.com/some/page'}
        self.assertTrue(render.is_first_party(source, meta))


@unittest.skipUnless(shutil.which('node'), 'node is not installed')
class AttributionLabelJsTests(unittest.TestCase):
    def test_node_test_passes(self):
        result = subprocess.run(['node', '--test', 'tests/attribution.cjs'], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
