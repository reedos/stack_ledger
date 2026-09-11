import json
import re
import sys
import tempfile
import unittest
from unittest.mock import patch
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import import_eia as ie
import importer_common
import api_access
import validate_expansion as ve
from validate import observation_valid

NET_GEN_ROWS = [
    {'period': '2026-01', 'location': 'US', 'fueltypeid': 'ALL', 'sectorid': '99', 'generation': '350000'},
    {'period': '2026-02', 'location': 'US', 'fueltypeid': 'ALL', 'sectorid': '99', 'generation': '340500'},
    {'period': '2026-02', 'location': 'TX', 'fueltypeid': 'ALL', 'sectorid': '99', 'generation': '40000'},   # a state row, not the national total: ignored
    {'period': '2026-02', 'location': 'US', 'fueltypeid': 'SUN', 'sectorid': '99', 'generation': '12000'},   # per-fuel row, not the ALL total: ignored
    {'period': '2026-03', 'location': 'US', 'fueltypeid': 'ALL', 'sectorid': '99', 'generation': 'NA'},       # non-numeric: dropped, never zero
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

RETAIL_PRICE_ROWS = [
    {'period': '2024', 'stateid': 'TX', 'sectorid': 'RES', 'price': '15.32'},
    {'period': '2025', 'stateid': 'TX', 'sectorid': 'RES', 'price': '15.90'},
    {'period': '2025', 'stateid': 'VA', 'sectorid': 'RES', 'price': '14.11'},         # untracked state: ignored
    {'period': '2025', 'stateid': 'TX', 'sectorid': 'IND', 'price': '9.00'},          # untracked sector: ignored
    {'period': '2025', 'stateid': 'US', 'sectorid': 'ALL', 'price': '13.20'},
    {'period': '2018', 'stateid': 'TX', 'sectorid': 'RES', 'price': '11.00'},         # before the reviewed 2019 start: ignored
    {'period': '2026', 'stateid': 'TX', 'sectorid': 'RES', 'price': 'NA'},            # non-numeric: dropped, never zero
]


class EiaNoKeyTests(unittest.TestCase):
    def test_missing_key_prints_registration_and_makes_no_network_call(self):
        # The owner registered a real key on 2026-09-10, so the no-key path is created here rather
        # than assumed; a test must never depend on the machine's private key file.
        def boom(*a, **k): raise AssertionError('import_eia must not call the network without a key')
        with patch.object(ie.api_access, 'key', return_value=None), patch.object(api_access, 'fetch', boom):
            result = ie.run(apply=False)
        self.assertEqual(result['status'], 'no_key')
        self.assertEqual(result['registration_url'], 'https://www.eia.gov/opendata/register.php')
        # The snapshot from a real keyed run may exist; what matters is that the no-key path wrote nothing new.

    def test_main_exits_zero_with_no_key(self):
        # --apply is exercised only in the no-key path: with a real key it would import for real.
        with patch.object(ie.api_access, 'key', return_value=None):
            self.assertEqual(ie.main([]), 0)
            self.assertEqual(ie.main(['--apply']), 0)


class EiaRecordTests(unittest.TestCase):
    def test_net_generation_keeps_only_the_all_fuels_total_and_converts_units(self):
        observations = ie.net_generation_records(NET_GEN_ROWS, '2026-09-09T12:00:00Z')
        self.assertEqual([(o['period'], o['value']) for o in observations], [('2026-01', 350.0), ('2026-02', 340.5)])
        self.assertTrue(all(o['metric'] == 'eia-net-generation-monthly' and o['status'] == 'observation' for o in observations))

    def test_capacity_additions_group_by_source_and_only_count_the_online_month(self):
        metrics, observations = ie.capacity_addition_records(CAPACITY_ROWS, '2026-09-09T12:00:00Z')
        # keyed by metric id, the key run() filters new metrics on; wind excluded (wrong month), coal excluded (untracked)
        self.assertEqual(sorted(metrics), ['eia-operating-capacity-additions-monthly-nuclear', 'eia-operating-capacity-additions-monthly-solar'])
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
        metrics_by_id = {'eia-net-generation-monthly': gen_metric, 'eia-steo-generation-outlook': steo_metric, **cap_metrics}
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


class RetailPriceTests(unittest.TestCase):
    def test_project_states_come_from_reviewed_county_and_place_locations_only(self):
        delivery = json.loads((ROOT/'research/delivery.json').read_text(encoding='utf-8'))
        states = ie.project_states(delivery)
        self.assertTrue(states)
        self.assertTrue(all(len(k) == 2 and k.isalpha() and k == k.upper() for k in states))
        self.assertTrue(all(v == ie.STATE_NAMES[k] for k, v in states.items()))

    def test_project_states_reads_the_state_suffix_off_the_label(self):
        fake = {'projects': [
            {'map_location': {'source': 'census-map-counties', 'source_key': '32003', 'label': 'Clark County, NV'}},
            {'map_locations': [{'location': {'source': 'census-map-places', 'source_key': '5554875', 'label': 'Mount Pleasant village, WI'}}]},
            {'map_location': {'source': 'geonames-map', 'source_key': '2643743', 'label': 'London, GB'}},   # not a U.S. state: ignored
            {'map_location': {'source': 'census-map-places', 'source_key': '1234567', 'label': 'Social Circle, GA — Stanton Springs area'}},
        ]}
        self.assertEqual(ie.project_states(fake), {'NV': 'Nevada', 'WI': 'Wisconsin', 'GA': 'Georgia'})

    def test_project_states_empty_for_no_reviewed_locations(self):
        self.assertEqual(ie.project_states({'projects': []}), {})

    def test_retail_price_records_keep_only_tracked_states_and_sectors(self):
        states = {'TX': 'Texas', 'US': 'United States'}
        metrics, observations = ie.retail_price_records(RETAIL_PRICE_ROWS, '2026-09-10T12:00:00Z', states)
        self.assertEqual(sorted(metrics), ['eia-retail-price-tx-residential', 'eia-retail-price-us-all'])
        by_id = {o['id']: o for o in observations}
        self.assertEqual(by_id['eia-retail-price-tx-residential-2024']['value'], 15.32)
        self.assertEqual(by_id['eia-retail-price-tx-residential-2025']['value'], 15.9)
        self.assertEqual(by_id['eia-retail-price-us-all-2025']['value'], 13.2)
        self.assertNotIn('eia-retail-price-va-residential-2025', by_id)   # untracked state
        self.assertNotIn('eia-retail-price-tx-residential-2018', by_id)  # before the reviewed 2019 start
        self.assertTrue(all(o['status'] == 'observation' and o['source'] == ie.SOURCE_ID for o in observations))

    def test_retail_price_metric_geography_and_code(self):
        state_metric = ie.retail_price_metric('TX', 'Texas', 'residential')
        national_metric = ie.retail_price_metric('US', 'United States', 'all')
        self.assertEqual(state_metric['geography'], 'Texas'); self.assertEqual(state_metric['geography_code'], 'TX')
        self.assertEqual(national_metric['geography'], 'United States'); self.assertEqual(national_metric['geography_code'], 'US')
        self.assertEqual(state_metric['unit'], 'cents/kWh'); self.assertIsNone(state_metric['period_basis'])   # annual averages, one point per year
        self.assertEqual(state_metric['series_start_year'], 2019)

    def test_retail_price_metrics_are_reviewed_public_measurement_type_and_internally_valid(self):
        states = {'TX': 'Texas', 'US': 'United States'}
        metrics, observations = ie.retail_price_records(RETAIL_PRICE_ROWS, '2026-09-10T12:00:00Z', states)
        for m in metrics.values():
            self.assertTrue(m['measurement_type'] in ve.TYPES and m['measurement_type'] in ve.PUBLIC_TYPES and m['measurement_type'] in ve.HISTORICAL_ONLY)
            self.assertIsNone(m['company'])
        sources = {ie.SOURCE_ID: ie.SOURCE}
        for o in observations:
            observation_valid(o, metrics, sources)

    def test_retail_price_url_carries_state_and_sector_facets(self):
        url = ie.retail_price_url(['TX', 'CA', 'US'], 'RES')
        self.assertTrue(url.startswith('https://api.eia.gov/v2/electricity/retail-sales/data/'))
        self.assertIn('facets[stateid][]=TX', url); self.assertIn('facets[stateid][]=CA', url); self.assertIn('facets[stateid][]=US', url)
        self.assertIn('facets[sectorid][]=RES', url); self.assertIn('data[0]=price', url)


if __name__ == '__main__':
    unittest.main()


class LiveShapeRegressionTests(unittest.TestCase):
    """Both routes were mis-queried against the live API on 2026-09-10: generation returned a row per
    state that all collapsed onto the national record id, and a multi-state price request returned
    only one state."""
    def test_generation_asks_for_and_keeps_only_the_national_row(self):
        self.assertIn('facets[location][]=US', ie.net_generation_url())
        rows = [{'period': '2026-01', 'location': 'US', 'fueltypeid': 'ALL', 'generation': '332493.16'},
                {'period': '2026-01', 'location': 'TX', 'fueltypeid': 'ALL', 'generation': '40000.0'},
                {'period': '2026-01', 'location': 'AK', 'fueltypeid': 'ALL', 'generation': '590.145'}]
        obs = ie.net_generation_records(rows, '2026-09-10T00:00:00Z')
        self.assertEqual(len(obs), 1)
        self.assertEqual(len({o['id'] for o in obs}), len(obs))
        self.assertEqual(obs[0]['value'], 332.493)

    def test_retail_price_url_names_exactly_one_state(self):
        url = ie.retail_price_url(['TX'], 'ALL')
        self.assertEqual(url.count('facets[stateid][]='), 1)
        self.assertIn('facets[stateid][]=TX', url)


class CapacityRouteTests(unittest.TestCase):
    """The capacity route advertised five metrics and produced not one record from the day it was
    written, and the weekly run still reported ok. The 2026-09-10 response retained under
    .local/eia/capacity-additions-*.json says why: EIA's operable-generator inventory, 5,000 rows
    of 4,808,947, every one of them 2008-01, and no operating-year-month field because the request
    never asked for that column. Periods here are 2027 onward so nothing collides with a published
    record."""

    def setUp(self):
        self.capacity_healthy = False
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        private = Path(self.temp.name)
        for p in [patch.object(ie, 'SNAPSHOTS', private/'snapshots'), patch.object(ie.research, 'LOCAL', private/'local'),
                   patch.object(ie.api_access, 'key', return_value='test-key'), patch.object(api_access, 'fetch', self.fetch)]:
            p.start(); self.addCleanup(p.stop)

    def body(self, rows, warnings=(), total=None):
        return json.dumps({'warnings': [{'warning': w} for w in warnings],
                            'response': {'total': len(rows) if total is None else total, 'data': rows}}).encode('utf-8')

    def fetch(self, url, agent):
        if 'operating-generator-capacity' in url:
            if self.capacity_healthy:
                return self.body([{'period': '2027-03', 'energy_source_code': 'SUN', 'operating-year-month': '2027-03', 'nameplate-capacity-mw': '120.5'},
                                   {'period': '2027-03', 'energy_source_code': 'NUC', 'operating-year-month': '2026-11', 'nameplate-capacity-mw': '900'}])
            live = {'period': '2008-01', 'stateid': 'AL', 'sector': 'electric-utility', 'energy_source_code': 'NG',
                    'status': 'OP', 'nameplate-capacity-mw': '153.1'}
            return self.body([live]*ie.PAGE_LIMIT, warnings=['incomplete return'], total=4_808_947)
        if 'electric-power-operational-data' in url:
            months = [f'{year}-{month:02d}' for year in range(2027, 2035) for month in range(1, 13)][:90]
            return self.body([{'period': m, 'location': 'US', 'fueltypeid': 'ALL', 'generation': '350000'} for m in months])
        if '/steo/' in url:
            return self.body([{'period': '2027', 'seriesId': ie.STEO_SERIES_ID, 'value': '4600.0'}])
        state = re.search(r'facets\[stateid\]\[\]=(\w+)', url).group(1)
        sector = re.search(r'facets\[sectorid\]\[\]=(\w+)', url).group(1)
        return self.body([{'period': str(year), 'stateid': state, 'sectorid': sector, 'price': '15.0'} for year in range(2027, 2034)])

    def test_capacity_url_requests_the_online_month_column_and_windows_the_series(self):
        url = ie.capacity_url()
        self.assertIn('data[1]=operating-year-month', url)
        self.assertIn(f'start={ie.SERIES_START_YEAR}-01', url)

    def test_a_route_that_returns_rows_and_no_record_fails_instead_of_reporting_ok(self):
        result = ie.run(apply=False)
        self.assertEqual(result['status'], 'failed')
        reasons = ' | '.join(result['floor_failures'])
        self.assertIn('operating-year-month', reasons)
        self.assertIn('truncated page', reasons)
        self.assertIn("'records:capacity-additions' returned 0", reasons)
        # the routes that did answer are not blamed
        self.assertNotIn('net-generation', reasons)
        self.assertNotIn('retail-price', reasons)

    def test_main_exits_non_zero_on_the_dead_route(self):
        # DEGRADED_EXIT, not 1: nightly rolls back research/, site/ and docs/ on any other non-zero
        # exit, discarding the records the routes that did answer produced.
        self.assertEqual(ie.main([]), importer_common.DEGRADED_EXIT)

    def test_a_route_that_answers_properly_reports_ok_and_registers_its_metrics(self):
        self.capacity_healthy = True
        result = ie.run(apply=False)
        self.assertEqual(result['floor_failures'], [])
        self.assertEqual(result['status'], 'ok')
        self.assertIn('eia-operating-capacity-additions-monthly-solar', [m['id'] for m in result['metrics']])
        self.assertEqual(ie.main([]), 0)
