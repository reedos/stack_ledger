import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import import_eia as ie
import api_access
import validate_expansion as ve
from validate import observation_valid

NET_GEN_ROWS = [
    {'period': '2026-01', 'fueltypeid': 'ALL', 'sectorid': '99', 'generation': '350000'},
    {'period': '2026-02', 'fueltypeid': 'ALL', 'sectorid': '99', 'generation': '340500'},
    {'period': '2026-02', 'fueltypeid': 'SUN', 'sectorid': '99', 'generation': '12000'},   # per-fuel row, not the ALL total: ignored
    {'period': '2026-03', 'fueltypeid': 'ALL', 'sectorid': '99', 'generation': 'NA'},       # non-numeric: dropped, never zero
]

CAPACITY_ROWS = [
    {'period': '2026-06', 'energy_source_code': 'SUN', 'operating-year-month': '2026-06', 'nameplate-capacity-mw': '150.0'},
    {'period': '2026-06', 'energy_source_code': 'SUN', 'operating-year-month': '2026-06', 'nameplate-capacity-mw': '50.5'},
    {'period': '2026-06', 'energy_source_code': 'WND', 'operating-year-month': '2026-05', 'nameplate-capacity-mw': '80.0'},  # came online an earlier month: not an addition this period
    {'period': '2026-06', 'energy_source_code': 'COL', 'operating-year-month': '2026-06', 'nameplate-capacity-mw': '999'},   # untracked source: ignored
    {'period': '2026-07', 'energy_source_code': 'NUC', 'operating-year-month': '2026-07', 'nameplate-capacity-mw': '1100'},
]

STEO_ROWS = [
    {'period': '2025', 'seriesId': 'ELGEN', 'value': '4430.0'},
    {'period': '2026', 'seriesId': 'ELGEN', 'value': '4508.0'},
    {'period': '2027', 'seriesId': 'ELGEN', 'value': '4632.0'},
]


class EiaNoKeyTests(unittest.TestCase):
    def test_missing_key_prints_registration_and_makes_no_network_call(self):
        self.assertIsNone(api_access.key('eia', root=ROOT))   # confirms the environment has no key, as expected
        def boom(*a, **k): raise AssertionError('import_eia must not call the network without a key')
        real_fetch = api_access.fetch
        api_access.fetch = boom
        try:
            result = ie.run(apply=False)
        finally:
            api_access.fetch = real_fetch
        self.assertEqual(result['status'], 'no_key')
        self.assertEqual(result['registration_url'], 'https://www.eia.gov/opendata/register.php')
        self.assertFalse((ROOT/'research/eia/eia.json').exists())

    def test_main_exits_zero_with_no_key(self):
        self.assertEqual(ie.main([]), 0)
        self.assertEqual(ie.main(['--apply']), 0)


class EiaRecordTests(unittest.TestCase):
    def test_net_generation_keeps_only_the_all_fuels_total_and_converts_units(self):
        observations = ie.net_generation_records(NET_GEN_ROWS, '2026-09-09T12:00:00Z')
        self.assertEqual([(o['period'], o['value']) for o in observations], [('2026-01', 350.0), ('2026-02', 340.5)])
        self.assertTrue(all(o['metric'] == 'eia-net-generation-monthly' and o['status'] == 'observation' for o in observations))

    def test_capacity_additions_group_by_source_and_only_count_the_online_month(self):
        metrics, observations = ie.capacity_addition_records(CAPACITY_ROWS, '2026-09-09T12:00:00Z')
        self.assertEqual(sorted(metrics), ['nuclear', 'solar'])   # wind excluded (wrong month), coal excluded (untracked)
        by_id = {o['id']: o for o in observations}
        self.assertEqual(by_id['eia-operating-capacity-additions-monthly-solar-2026-06']['value'], 200.5)
        self.assertEqual(by_id['eia-operating-capacity-additions-monthly-nuclear-2026-07']['value'], 1100.0)
        self.assertNotIn('eia-operating-capacity-additions-monthly-wind-2026-06', by_id)

    def test_steo_status_splits_on_the_elapsed_year_boundary(self):
        observations = ie.steo_records(STEO_ROWS, '2026-09-09T12:00:00Z', today=date(2026, 9, 9))
        by_year = {o['year']: o for o in observations}
        self.assertEqual(by_year[2025]['status'], 'observation')
        self.assertEqual(by_year[2026]['status'], 'forecast')
        self.assertEqual(by_year[2027]['status'], 'forecast')
        self.assertEqual(by_year[2025]['period'], '2025')

    def test_metrics_are_reviewed_measurement_types_and_internally_valid(self):
        gen_metric = ie.net_generation_metric()
        cap_metrics, cap_obs = ie.capacity_addition_records(CAPACITY_ROWS, '2026-09-09T12:00:00Z')
        steo_metric = ie.steo_metric()
        self.assertTrue(gen_metric['measurement_type'] in ve.TYPES and gen_metric['measurement_type'] in ve.PUBLIC_TYPES and gen_metric['measurement_type'] in ve.HISTORICAL_ONLY)
        self.assertIsNone(gen_metric['company'])
        for m in cap_metrics.values():
            self.assertTrue(m['measurement_type'] in ve.TYPES and m['measurement_type'] in ve.PUBLIC_TYPES and m['measurement_type'] in ve.HISTORICAL_ONLY)
        self.assertTrue(steo_metric['measurement_type'] in ve.TYPES and steo_metric['measurement_type'] in ve.PUBLIC_TYPES)
        self.assertNotIn(steo_metric['measurement_type'], ve.HISTORICAL_ONLY)   # mixes observation and forecast
        self.assertEqual(steo_metric['allowed_statuses'], ['observation', 'forecast'])
        metrics = {'eia-net-generation-monthly': gen_metric, **cap_metrics, 'eia-steo-generation-outlook': steo_metric}
        # capacity_addition_records keys metrics by slug; re-key by metric id for observation_valid.
        metrics_by_id = {'eia-net-generation-monthly': gen_metric, 'eia-steo-generation-outlook': steo_metric}
        metrics_by_id.update({f'eia-operating-capacity-additions-monthly-{slug}': m for slug, m in cap_metrics.items()})
        sources = {ie.SOURCE_ID: ie.SOURCE}
        for o in ie.net_generation_records(NET_GEN_ROWS, '2026-09-09T12:00:00Z'):
            observation_valid(o, metrics_by_id, sources)
        for o in cap_obs:
            observation_valid(o, metrics_by_id, sources)
        for o in ie.steo_records(STEO_ROWS, '2026-09-09T12:00:00Z', today=date(2026, 9, 9)):
            observation_valid(o, metrics_by_id, sources)

    def test_urls_carry_the_documented_facets(self):
        self.assertIn('facets[sectorid][]=99', ie.net_generation_url())
        self.assertIn('facets[fueltypeid][]=ALL', ie.net_generation_url())
        self.assertTrue(ie.net_generation_url().startswith('https://api.eia.gov/v2/electricity/electric-power-operational-data/data/'))
        self.assertTrue(ie.capacity_url().startswith('https://api.eia.gov/v2/electricity/operating-generator-capacity/data/'))
        self.assertIn(f'facets[seriesId][]={ie.STEO_SERIES_ID}', ie.steo_url())
        self.assertTrue(ie.steo_url().startswith('https://api.eia.gov/v2/steo/data/'))

    def test_source_is_public_domain_energy_layer(self):
        self.assertEqual(ie.SOURCE['license'], 'Public domain (U.S. government work)')
        self.assertEqual(ie.SOURCE['layers'], ['energy'])


if __name__ == '__main__':
    unittest.main()
