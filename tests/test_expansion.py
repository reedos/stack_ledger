import json
import sys
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from validate_expansion import validate_expansion, validate_files
from validate import observation_valid
from validate_delivery import validate_delivery


class ExpansionTests(unittest.TestCase):
    def setUp(self):
        read = lambda name: json.loads((ROOT / 'site/data' / (name + '.json')).read_text(encoding='utf-8'))
        self.x, self.l, self.e, self.d = [read(n) for n in ['expansion', 'ledger', 'ecosystem', 'delivery']]

    def test_reviewed_files_resolve(self):
        self.assertTrue(validate_files())

    def test_announced_capex_cannot_be_reclassified_as_spent(self):
        o = next(o for o in self.l['observations'] if o['metric'] == 'terafab-announced-capital')
        o['status'] = 'observation'
        with self.assertRaisesRegex(ValueError, 'measurement basis'):
            observation_valid(o, {m['id']: m for m in self.l['metrics']}, {s['id']: s for s in self.l['sources']})

    def test_product_cannot_inherit_another_companys_usage(self):
        self.x['products'][0]['observations'] = self.x['products'][1]['observations']
        with self.assertRaisesRegex(ValueError, 'another company'):
            validate_expansion(self.x, self.l, self.e, self.d)

    def test_project_cannot_inherit_another_sites_jobs(self):
        p = next(p for p in self.d['projects'] if p['id'] == 'terafab')
        p['measures'].append('hyperion-permanent-jobs-baseline')
        with self.assertRaisesRegex(ValueError, 'another site'):
            validate_delivery(self.d, self.l)

    def test_unknown_hires_are_not_seeded_as_zero(self):
        # A missing value is allowed even after other projects acquire reported
        # jobs. Do not freeze the entire catalog into having no actuals forever.
        template=next(m for m in self.l['metrics'] if m.get('measurement_type')=='permanent_jobs_reported')
        missing=dict(template,id='fixture-undisclosed-operating-jobs')
        self.l['metrics'].append(missing)
        before=json.dumps(self.l['observations'],sort_keys=True)
        validate_expansion(self.x,self.l,self.e,self.d)
        self.assertEqual(json.dumps(self.l['observations'],sort_keys=True),before)
        self.assertFalse(any(o['metric']==missing['id'] for o in self.l['observations']))

    def test_supervised_driving_stays_in_separate_metric_and_project(self):
        supervised = next(m for m in self.l['metrics'] if m['id'] == 'tesla-supervised-europe-miles')
        rider_only = next(m for m in self.l['metrics'] if m['id'] == 'waymo-rider-only-miles')
        self.assertNotEqual(supervised['measurement_type'], rider_only['measurement_type'])
        self.assertNotEqual(supervised['project'], rider_only['project'])

    def test_status_policy_cannot_turn_promised_jobs_into_hires(self):
        m = next(m for m in self.l['metrics'] if m['id'] == 'terafab-permanent-promised')
        m['allowed_statuses'].append('observation')
        with self.assertRaisesRegex(ValueError, 'Promised measurement'):
            validate_expansion(self.x, self.l, self.e, self.d)

    def test_waymo_target_does_not_replace_observed_paid_service(self):
        from render import latest_headline
        layer = next(l for l in self.l['layers'] if l['id'] == 'applications')
        latest = latest_headline(self.l, layer)
        self.assertEqual((latest['year'], latest['value'], latest['status']), (2026, 500000, 'observation'))
        self.assertTrue(any(o['metric'] == 'waymo-paid-weekly' and o['year'] == 2025 for o in self.l['observations']))
        target = next(o for o in self.l['observations'] if o['metric'] == 'waymo-weekly-rides-target')
        self.assertEqual(target['status'], 'company-commitment')
        self.assertNotEqual(latest['metric'], target['metric'])

    def test_colossus_locations_and_unknown_productive_robots_stay_separate(self):
        projects = {p['id']: p for p in self.d['projects']}
        self.assertNotIn('Southaven', projects['colossus-one']['location'])
        self.assertNotEqual(projects['colossus-two']['location'], projects['southaven-permanent-power']['location'])
        self.assertEqual(projects['tesla-optimus']['stage'], 'pilot')
        self.assertEqual(projects['tesla-optimus']['observations'], [])


if __name__ == '__main__': unittest.main()
