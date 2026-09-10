import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import import_grid as ig
from validate import source_valid


class GridOperatorsConfigTests(unittest.TestCase):
    def test_reviewed_config_loads_and_validates(self):
        p = ig.policy(ROOT)
        ids = {o['id'] for o in p['operators']}
        self.assertEqual(ids, {'pjm', 'ercot', 'miso', 'spp', 'eia-national'})

    def test_every_operator_is_waiting_on_a_reviewed_import(self):
        # This task's network scope covers only the Federal Register API and EIA API v2; none
        # of the four RTO hosts (or a confirmed EIA peak-load route) were fetched, so nothing
        # here should claim a real series yet.
        p = ig.policy(ROOT)
        self.assertTrue(all(o['status'] == 'needs_reviewed_import' for o in p['operators']))

    def test_every_operator_source_is_a_registerable_public_https_url(self):
        p = ig.policy(ROOT)
        for o in p['operators']:
            source = ig.operator_source(o)
            source_valid(source, {source['id']: source})
            self.assertEqual(source['layers'], ['energy'])
            self.assertTrue(source['url'].startswith('https://'))


class GridImporterRunTests(unittest.TestCase):
    def test_report_mode_lists_every_operator_as_waiting_and_makes_no_change(self):
        result = ig.run(apply=False)
        self.assertEqual(set(result['waiting']), {'pjm', 'ercot', 'miso', 'spp', 'eia-national'})
        self.assertEqual(result['imported'], [])
        self.assertEqual(len(result['sources']), 5)

    def test_operator_source_ids_are_stable_and_namespaced(self):
        p = ig.policy(ROOT)
        ids = {ig.operator_source(o)['id'] for o in p['operators']}
        self.assertEqual(ids, {'grid-operator-pjm', 'grid-operator-ercot', 'grid-operator-miso', 'grid-operator-spp', 'grid-operator-eia-national'})


if __name__ == '__main__':
    unittest.main()
