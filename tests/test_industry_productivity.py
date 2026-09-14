"""Software-industry employment, revenue, and the matched ratio between them.

These exist because of a 3Fourteen Research chart (2026-09) dividing S&P 1500 GICS Application
Software trailing sales by BLS Software Publishers payrolls. Its numerator is unreproducible here:
GICS classification and S&P 1500 membership are licensed, a fixed basket of today's filers carries
survivorship bias, and SEC XBRL frames were measured to yield no complete TTM window at all for
8 of 18 candidate filers because Q4 is never separately reported.

Census QSS replaces it with a matched pair -- QSS revenue and CES employment both measure U.S.
establishments in the same named industry -- and on that data the chart's finding survives and
sharpens (+$3,218/employee/year over 2015-2022, +$105,613 over 2023-2026).

What these tests protect is the arithmetic and the failure behaviour, not the conclusion: a
suppressed quarter must never become a zero, and a ratio must never be published for a quarter
where only one of its two inputs exists.
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import import_ces
import import_qss
import validate_expansion

CATALOG = json.loads((ROOT/'research/catalog.json').read_text(encoding='utf-8'))
LEDGER = json.loads((ROOT/'site/data/ledger.json').read_text(encoding='utf-8'))
METRICS = {m['id']: m for m in CATALOG['metrics']}
BY_METRIC = {}
for _o in LEDGER['observations']:
    BY_METRIC.setdefault(_o['metric'], []).append(_o)

CES_IDS = [m[0] for m in (v for v in import_ces.SERIES.values())]
QSS_REVENUE_IDS = [v[0] for v in import_qss.CATEGORIES.values()]
QSS_RATIO_IDS = [v[3] for v in import_qss.CATEGORIES.values()]


class QuarterPoints(unittest.TestCase):
    def test_only_quarter_end_months_are_kept(self):
        data = [{'year': '2026', 'period': p, 'value': '100.0'}
                for p in ('M01', 'M02', 'M03', 'M04', 'M06', 'M09', 'M12')]
        got = import_ces.quarter_points(data)
        self.assertEqual([(2026, 1), (2026, 2), (2026, 3), (2026, 4)], [(y, q) for y, q, _ in got])

    def test_the_annual_average_row_is_not_a_quarter(self):
        """M13 is CES's annual average. Treating it as a month would invent a 13th period."""
        self.assertEqual([], import_ces.quarter_points([{'year': '2026', 'period': 'M13', 'value': '9'}]))

    def test_thousands_are_converted_to_whole_jobs(self):
        got = import_ces.quarter_points([{'year': '2026', 'period': 'M03', 'value': '658.6'}])
        self.assertEqual([(2026, 1, 658600)], got)

    def test_an_unparseable_value_is_dropped_not_zeroed(self):
        got = import_ces.quarter_points([{'year': '2026', 'period': 'M03', 'value': '-'},
                                         {'year': '2026', 'period': 'M06', 'value': '658.6'}])
        self.assertEqual([(2026, 2, 658600)], got)


class SuppressionIsNeverZero(unittest.TestCase):
    def test_census_suppression_codes_are_recognised(self):
        """Census marks an unpublishable cell with a letter. Recorded as 0 it would read as a
        collapse in revenue."""
        for code in ('S', 'D', 'N', 'X', ''):
            self.assertIn(code, import_qss.SUPPRESSED, code)

    def test_no_recorded_observation_is_zero(self):
        for metric_id in QSS_REVENUE_IDS + CES_IDS + QSS_RATIO_IDS:
            for observation in BY_METRIC.get(metric_id, []):
                self.assertGreater(observation['value'], 0,
                                   f'{observation["id"]} recorded a zero')


class MetricsAreRegistered(unittest.TestCase):
    def test_every_series_reached_the_catalog(self):
        for metric_id in CES_IDS + QSS_REVENUE_IDS + QSS_RATIO_IDS:
            self.assertIn(metric_id, METRICS, metric_id)

    def test_measurement_types_are_reviewed(self):
        for metric_id in CES_IDS + QSS_REVENUE_IDS + QSS_RATIO_IDS:
            self.assertIn(METRICS[metric_id]['measurement_type'], validate_expansion.TYPES)

    def test_industry_wide_metrics_carry_no_company(self):
        """These count a whole industry; attributing them to a company would be a false claim."""
        for metric_id in CES_IDS + QSS_REVENUE_IDS + QSS_RATIO_IDS:
            self.assertIsNone(METRICS[metric_id]['company'], metric_id)
            self.assertIn(METRICS[metric_id]['measurement_type'], validate_expansion.PUBLIC_TYPES)

    def test_they_are_historical_only(self):
        """A payroll count and a revenue survey describe a quarter that has ended; neither can
        legitimately carry a forecast."""
        for metric_id in CES_IDS + QSS_REVENUE_IDS + QSS_RATIO_IDS:
            self.assertIn(METRICS[metric_id]['measurement_type'], validate_expansion.HISTORICAL_ONLY)
            self.assertEqual(['observation'], METRICS[metric_id]['allowed_statuses'], metric_id)


class RatioIsMatched(unittest.TestCase):
    def test_a_ratio_quarter_exists_only_where_both_inputs_do(self):
        for category, (revenue_id, _, employment_id, ratio_id) in import_qss.CATEGORIES.items():
            revenue = {o['period'] for o in BY_METRIC.get(revenue_id, [])}
            employment = {o['period'] for o in BY_METRIC.get(employment_id, [])}
            ratio = {o['period'] for o in BY_METRIC.get(ratio_id, [])}
            self.assertTrue(ratio, category)
            self.assertTrue(ratio <= (revenue & employment),
                            f'{category}: ratio published for a quarter missing an input')

    def test_the_arithmetic_is_revenue_annualised_over_jobs(self):
        for category, (revenue_id, _, employment_id, ratio_id) in import_qss.CATEGORIES.items():
            revenue = {o['period']: o['value'] for o in BY_METRIC.get(revenue_id, [])}
            employment = {o['period']: o['value'] for o in BY_METRIC.get(employment_id, [])}
            for observation in BY_METRIC.get(ratio_id, []):
                period = observation['period']
                expected = revenue[period]*1_000_000*4/employment[period]
                self.assertAlmostEqual(observation['value'], expected, delta=1,
                                       msg=f'{ratio_id} {period}')

    def test_the_ratio_is_marked_approximate(self):
        """It divides a sample survey by a survey on a slightly different NAICS vintage; 'eq'
        would claim a precision neither input supports."""
        for ratio_id in QSS_RATIO_IDS:
            for observation in BY_METRIC.get(ratio_id, []):
                self.assertEqual('approx', observation['precision'], observation['id'])

    def test_the_note_warns_the_level_is_approximate(self):
        """The NAICS 5112-vs-5132 vintage gap makes the level, but not the trend, unreliable.
        A reader sorting on the level must find that stated."""
        for ratio_id in QSS_RATIO_IDS:
            note = METRICS[ratio_id]['note'].lower()
            self.assertIn('trend', note, ratio_id)
            self.assertIn('5112', note, ratio_id)


class SeriesShape(unittest.TestCase):
    def test_each_series_has_no_duplicate_quarters(self):
        for metric_id in CES_IDS + QSS_REVENUE_IDS + QSS_RATIO_IDS:
            periods = [o['period'] for o in BY_METRIC.get(metric_id, [])]
            self.assertEqual(len(periods), len(set(periods)), metric_id)

    def test_employment_and_revenue_cover_the_same_quarters(self):
        """The ratio is only meaningful where the two line up; a silent divergence would shrink
        it without any test failing."""
        for category, (revenue_id, _, employment_id, _r) in import_qss.CATEGORIES.items():
            revenue = {o['period'] for o in BY_METRIC.get(revenue_id, [])}
            employment = {o['period'] for o in BY_METRIC.get(employment_id, [])}
            self.assertGreaterEqual(len(revenue & employment), 40,
                                    f'{category}: only {len(revenue & employment)} shared quarters')


if __name__ == '__main__':
    unittest.main()
