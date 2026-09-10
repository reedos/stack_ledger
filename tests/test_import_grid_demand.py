import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import import_grid_demand as ig
import validate_expansion as ve
from validate import observation_valid

DAYS = {'2026-01-%02d' % d: 1000.0+d for d in range(1, 32)}          # a complete January
DAYS.update({'2026-02-%02d' % d: 2000.0 for d in range(1, 15)})       # a part February: never recorded


class DailyValueTests(unittest.TestCase):
    def test_unusable_rows_are_skipped_and_never_become_zero(self):
        rows = [{'period': '2026-01-01', 'value': '1500'}, {'period': '2026-01-02', 'value': 'NA'},
                {'period': '2026-01-03', 'value': ''}, {'period': '2026-01-04', 'value': '-5'},
                {'period': '2018-12-31', 'value': '9999'},          # before the reviewed start
                {'period': '2026-01', 'value': '123'}]              # not a day
        self.assertEqual(ig.daily_values(rows), {'2026-01-01': 1500.0})

    def test_a_duplicate_day_keeps_the_first_published_value(self):
        rows = [{'period': '2026-01-01', 'value': '1500'}, {'period': '2026-01-01', 'value': '1600'}]
        self.assertEqual(ig.daily_values(rows), {'2026-01-01': 1500.0})

    def test_one_timezone_facet_per_operator(self):
        url = ig.data_url('PJM', 'Eastern')
        self.assertEqual(url.count('facets[timezone][]='), 1)
        self.assertIn('facets[respondent][]=PJM', url); self.assertIn('facets[type][]=D', url)


class CompleteMonthTests(unittest.TestCase):
    def test_only_a_month_published_in_full_is_recorded(self):
        self.assertEqual(sorted(ig.complete_months(DAYS)), ['2026-01'])

    def test_a_part_month_never_looks_like_a_fall_in_demand(self):
        metrics, observations = ig.records_for('pjm', 'PJM Interconnection', DAYS, '2026-09-10T00:00:00Z', 'a'*64)
        self.assertEqual(sorted({o['period'] for o in observations}), ['2026-01'])


class RecordTests(unittest.TestCase):
    def setUp(self):
        self.metrics, self.observations = ig.records_for('pjm', 'PJM Interconnection', DAYS, '2026-09-10T00:00:00Z', 'b'*64)

    def test_average_and_highest_day_are_derived_from_the_published_days(self):
        by_id = {o['id']: o for o in self.observations}
        january = [v for k, v in DAYS.items() if k.startswith('2026-01')]
        self.assertEqual(by_id['grid-demand-pjm-average-monthly-2026-01']['value'], round(sum(january)/len(january)))
        self.assertEqual(by_id['grid-demand-pjm-peak-monthly-2026-01']['value'], round(max(january)))

    def test_the_note_says_how_many_days_the_point_is_derived_from(self):
        note = next(o['note'] for o in self.observations if o['metric'].endswith('average-monthly'))
        self.assertIn('31 published daily values', note); self.assertIn('sha256', note)

    def test_records_validate_against_their_own_metrics(self):
        sources = {ig.SOURCE_ID: ig.SOURCE}
        for o in self.observations:
            observation_valid(o, self.metrics, sources)

    def test_measurement_types_are_reviewed_public_and_historical_only(self):
        for m in self.metrics.values():
            self.assertIn(m['measurement_type'], ve.TYPES)
            self.assertIn(m['measurement_type'], ve.PUBLIC_TYPES)
            self.assertIn(m['measurement_type'], ve.HISTORICAL_ONLY)
            self.assertEqual(m['allowed_statuses'], ['observation'])   # measured demand, never a forecast

    def test_the_unit_says_a_day_of_energy_not_an_instantaneous_peak(self):
        for m in self.metrics.values():
            self.assertIn('MWh', m['unit'])
            self.assertIn('never an instantaneous peak in megawatts', m['scope'])


class KeyTests(unittest.TestCase):
    def test_the_importer_refuses_without_the_owners_key(self):
        with patch.object(ig.api_access, 'key', return_value=None):
            with self.assertRaises(ValueError):
                ig.run(apply=False)

    def test_the_key_is_never_written_into_the_source_file(self):
        text = (ROOT/'scripts/import_grid_demand.py').read_text(encoding='utf-8')
        self.assertIn("api_access.key('eia')", text)
        self.assertIn("'key': 'owner-registered, not recorded'", text)


class ScheduleTests(unittest.TestCase):
    def test_the_importer_is_scheduled_for_the_nightly_run(self):
        config = json.loads((ROOT/'research/importers.json').read_text(encoding='utf-8'))
        entry = next((i for i in config['importers'] if i['id'] == 'grid-demand'), None)
        self.assertIsNotNone(entry, 'grid-demand must be scheduled in research/importers.json')
        self.assertEqual(entry['command'][0], 'scripts/import_grid_demand.py')


if __name__ == '__main__':
    unittest.main()
