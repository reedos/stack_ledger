import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import chip_capacity as cc
import validate_expansion as ve
from validate import observation_valid


class ChipCapacityUnitTests(unittest.TestCase):
    def test_config_is_reviewed_and_mirrored(self):
        config = json.loads((ROOT / 'research/chip-capacity.json').read_text(encoding='utf-8'))
        mirror = json.loads((ROOT / 'site/data/chip-capacity.json').read_text(encoding='utf-8'))
        self.assertEqual(config, mirror)
        self.assertEqual(config['version'], 1)
        self.assertEqual(set(config['classes']), {'logic-fab', 'packaging', 'hbm-packaging', 'memory-fab'})
        self.assertEqual(len(config['projects']), 23)
        self.assertNotIn('tsmc-arizona-program', config['projects'])
        self.assertNotIn('globalfoundries-singapore-expansion', config['projects'])

    def test_metric_for_matches_the_terafab_announced_capital_shape(self):
        delivery = json.loads((ROOT / 'research/delivery.json').read_text(encoding='utf-8'))
        project = next(p for p in delivery['projects'] if p['id'] == 'terafab')
        entry = {'class': 'logic-fab', 'company': 'spacex', 'scope': 'Test scope.', 'source_ids': ['spacex-terafab-2026'], 'title': 'Test title'}
        cls = {'label': 'Logic fab', 'measurement_type': 'wafer_starts_per_month', 'unit': 'wafer starts / month by node (300 mm equivalent)', 'quantifies': 'x', 'conversion': 'y'}
        m = cc.metric_for('terafab', entry, cls, project)
        self.assertEqual(m['id'], 'terafab-capacity')
        self.assertEqual(m['project'], 'terafab')
        self.assertEqual(m['measurement_type'], 'wafer_starts_per_month')
        self.assertEqual(m['allowed_statuses'], ['observation', 'estimate', 'company-commitment'])
        self.assertEqual((m['series_start_year'], m['chart_default_start'], m['chart_default_end']), (2020, 2024, 2030))
        self.assertTrue(m['definition_stable'])
        self.assertEqual(m['geography'], project['location'])
        self.assertTrue(ve.TYPES.__contains__(m['measurement_type']))

    def test_all_configured_metrics_validate_at_the_observation_level(self):
        """Every generated metric must accept a plausible real observation: bounds, allowed
        statuses and source/metric mapping must be internally consistent (validate.observation_valid)."""
        config = json.loads((ROOT / 'research/chip-capacity.json').read_text(encoding='utf-8'))
        delivery = json.loads((ROOT / 'research/delivery.json').read_text(encoding='utf-8'))
        ecosystem = json.loads((ROOT / 'research/ecosystem.json').read_text(encoding='utf-8'))
        registry = json.loads((ROOT / 'research/sources.json').read_text(encoding='utf-8'))
        registry['sources'].append(dict(cc.WHITEPAPER_SOURCE))
        metrics = cc.build_metrics(config, delivery, ecosystem, registry)
        self.assertEqual(len(metrics), 23)
        sources = {s['id']: s for s in registry['sources']}
        metrics_by_id = {m['id']: m for m in metrics}
        for m in metrics:
            source_id = m['source_ids'][0]
            obs = {'id': f"{m['id']}-fixture", 'metric': m['id'], 'year': 2026, 'period': '2026', 'value': 10,
                   'upper': None, 'status': m['allowed_statuses'][0], 'source': source_id, 'precision': 'eq',
                   'retrieved_at': '2026-09-09T12:00:00Z', 'method': 'curated', 'note': 'Fixture observation for shape validation.'}
            observation_valid(obs, metrics_by_id, sources)

    def test_refuses_unknown_project(self):
        config = {'projects': {'not-a-real-project': {'class': 'logic-fab', 'company': 'tsmc', 'scope': 's', 'source_ids': ['company-tsmc'], 'title': 't'}},
                  'classes': {'logic-fab': {'label': 'Logic fab', 'measurement_type': 'wafer_starts_per_month', 'unit': 'u', 'quantifies': 'q', 'conversion': 'c'}}}
        delivery = json.loads((ROOT / 'research/delivery.json').read_text(encoding='utf-8'))
        ecosystem = json.loads((ROOT / 'research/ecosystem.json').read_text(encoding='utf-8'))
        registry = json.loads((ROOT / 'research/sources.json').read_text(encoding='utf-8'))
        with self.assertRaises(ValueError):
            cc.build_metrics(config, delivery, ecosystem, registry)

    def test_refuses_unregistered_source(self):
        config = {'projects': {'terafab': {'class': 'logic-fab', 'company': 'spacex', 'scope': 's', 'source_ids': ['not-a-registered-source'], 'title': 't'}},
                  'classes': {'logic-fab': {'label': 'Logic fab', 'measurement_type': 'wafer_starts_per_month', 'unit': 'u', 'quantifies': 'q', 'conversion': 'c'}}}
        delivery = json.loads((ROOT / 'research/delivery.json').read_text(encoding='utf-8'))
        ecosystem = json.loads((ROOT / 'research/ecosystem.json').read_text(encoding='utf-8'))
        registry = json.loads((ROOT / 'research/sources.json').read_text(encoding='utf-8'))
        with self.assertRaises(ValueError):
            cc.build_metrics(config, delivery, ecosystem, registry)

    def test_node_conversion_unit_tests(self):
        node = shutil.which('node')
        if not node:
            self.skipTest('node is not installed')
        result = subprocess.run([node, '--test', 'tests/chip_conversions.cjs'], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class ChipCapacityEndToEndTests(unittest.TestCase):
    """Runs the actual maintainer tool on a temp copy of the repo, so nothing here can touch
    the real research/site/docs files."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        for folder in ['scripts', 'research', 'site']:
            shutil.copytree(ROOT / folder, self.root / folder, ignore=shutil.ignore_patterns('__pycache__'))

    def tearDown(self):
        self.temp.cleanup()

    def run_tool(self, *args):
        return subprocess.run([sys.executable, 'scripts/chip_capacity.py', *args], cwd=self.root, capture_output=True, text=True)

    def reset_to_unapplied(self):
        """The worktree this test copies from may already have chip_capacity.py applied
        (it does, once this feature is committed). Strip its effects from the temp copy so
        the test can independently check the create-from-scratch path, not just a no-op."""
        config = json.loads((self.root / 'research/chip-capacity.json').read_text(encoding='utf-8'))
        capacity_ids = {f'{pid}-capacity' for pid in config['projects']}
        catalog = json.loads((self.root / 'research/catalog.json').read_text(encoding='utf-8'))
        catalog['metrics'] = [m for m in catalog['metrics'] if m['id'] not in capacity_ids]
        ledger = json.loads((self.root / 'site/data/ledger.json').read_text(encoding='utf-8'))
        ledger['metrics'] = [m for m in ledger['metrics'] if m['id'] not in capacity_ids]
        ledger['sources'] = [s for s in ledger['sources'] if s['id'] != cc.WHITEPAPER_SOURCE_ID]
        registry = json.loads((self.root / 'research/sources.json').read_text(encoding='utf-8'))
        registry['sources'] = [s for s in registry['sources'] if s['id'] != cc.WHITEPAPER_SOURCE_ID]
        registry['collection'].pop(cc.WHITEPAPER_SOURCE_ID, None)
        registry['region_books']['global']['sources'] = [s for s in registry['region_books']['global']['sources'] if s != cc.WHITEPAPER_SOURCE_ID]
        (self.root / 'research/catalog.json').write_text(json.dumps(catalog), encoding='utf-8')
        (self.root / 'research/sources.json').write_text(json.dumps(registry), encoding='utf-8')
        (self.root / 'site/data/ledger.json').write_text(json.dumps(ledger), encoding='utf-8')
        (self.root / 'site/data/source-books.json').write_text(json.dumps({k: registry[k] for k in ['region_books', 'collection']}), encoding='utf-8')
        (self.root / 'site/data/chip-capacity.json').unlink(missing_ok=True)

    def test_apply_is_idempotent_and_the_ledger_stays_valid(self):
        self.reset_to_unapplied()
        first = self.run_tool('--apply')
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        self.assertIn('23 new', first.stdout)
        mirror = json.loads((self.root / 'site/data/chip-capacity.json').read_text(encoding='utf-8'))
        config = json.loads((self.root / 'research/chip-capacity.json').read_text(encoding='utf-8'))
        self.assertEqual(mirror, config)
        catalog = json.loads((self.root / 'research/catalog.json').read_text(encoding='utf-8'))
        capacity_ids = {f'{pid}-capacity' for pid in config['projects']}
        self.assertTrue(capacity_ids <= {m['id'] for m in catalog['metrics']})
        registry = json.loads((self.root / 'research/sources.json').read_text(encoding='utf-8'))
        self.assertIn('nvidia-hopper-whitepaper', {s['id'] for s in registry['sources']})

        second = self.run_tool('--apply')
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertIn('0 new, 0 changed', second.stdout)
        catalog_after = json.loads((self.root / 'research/catalog.json').read_text(encoding='utf-8'))
        self.assertEqual(catalog, catalog_after)

        build_result = subprocess.run([sys.executable, 'scripts/build.py'], cwd=self.root, capture_output=True, text=True)
        self.assertEqual(build_result.returncode, 0, build_result.stdout + build_result.stderr)

    def test_refuses_unknown_project_end_to_end(self):
        config_path = self.root / 'research/chip-capacity.json'
        config = json.loads(config_path.read_text(encoding='utf-8'))
        config['projects']['not-a-real-project'] = dict(next(iter(config['projects'].values())))
        config_path.write_text(json.dumps(config), encoding='utf-8')
        result = self.run_tool('--apply')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('is not in delivery.json', result.stdout + result.stderr)
        # Nothing on disk should have changed after a refusal.
        catalog = json.loads((self.root / 'research/catalog.json').read_text(encoding='utf-8'))
        self.assertFalse(any(m['id'] == 'not-a-real-project-capacity' for m in catalog['metrics']))

    def test_refuses_unregistered_source_end_to_end(self):
        config_path = self.root / 'research/chip-capacity.json'
        config = json.loads(config_path.read_text(encoding='utf-8'))
        config['projects']['terafab']['source_ids'] = ['definitely-not-a-registered-source']
        config_path.write_text(json.dumps(config), encoding='utf-8')
        result = self.run_tool('--apply')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('unregistered source', result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
