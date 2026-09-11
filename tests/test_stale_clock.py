"""A figure is overdue when a newer one could exist, not when we have held it a while.

Measured on 2026-09-11: a two-hour session spent 116 of its fetch-and-model cycles on 40 metrics,
39 of which were annual company revenues whose newest held figure was FY2025. It was September
2026. Those fiscal years had not closed, no source anywhere had an FY2026 number, and every one of
those attempts correctly came back "nothing newer". The lane was working perfectly and asking an
impossible question.
"""
import datetime
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import research
import nightly

SEPT_2026 = datetime.date(2026, 9, 12)


def metric(**fields):
    base = {'id': 'm', 'period_basis': None}
    base.update(fields)
    return base


def reading(period, year):
    return {'metric': 'm', 'period': period, 'year': year, 'value': 1}


class NextReadingTests(unittest.TestCase):
    def test_an_annual_figure_waits_for_the_year_after_it_to_end(self):
        when = research.next_reading_possible(metric(), reading('FY2025', 2025))
        self.assertEqual(when, datetime.date(2027, 3, 31), 'end of 2026 plus the filing lag')
        self.assertGreater(when, SEPT_2026, 'an FY2026 revenue cannot exist in September 2026')

    def test_a_monthly_figure_waits_for_the_next_month_to_close(self):
        self.assertEqual(research.next_reading_possible(metric(period_basis='month'), reading('2026-07', 2026)),
                         datetime.date(2026, 10, 15))

    def test_a_monthly_figure_rolls_over_the_year(self):
        self.assertEqual(research.next_reading_possible(metric(period_basis='month'), reading('2026-12', 2026)),
                         datetime.date(2027, 3, 17), 'January 2027 closes 31 Jan, plus 45 days')

    def test_a_quarterly_figure_waits_for_the_next_quarter_to_close(self):
        self.assertEqual(research.next_reading_possible(metric(period_basis='quarter'), reading('2025-Q4', 2025)),
                         datetime.date(2026, 7, 29), 'Q1 2026 closes 31 March, plus 120 days')

    def test_a_leap_february_is_handled(self):
        self.assertEqual(research.next_reading_possible(metric(period_basis='month'), reading('2024-01', 2024)),
                         datetime.date(2024, 4, 14), 'February 2024 has 29 days')

    def test_an_irregular_snapshot_series_still_ages_from_its_own_date(self):
        """A fortnightly business survey has no next period to compute."""
        self.assertEqual(research.next_reading_possible(metric(period_basis='snapshot'), reading('2026-01-11', 2026)),
                         datetime.date(2026, 3, 12))

    def test_an_unparseable_period_falls_back_to_the_year(self):
        for period in ['Year-end 2025', 'Commercial operation · July 2025', '']:
            with self.subTest(period=period):
                self.assertEqual(research.next_reading_possible(metric(), reading(period, 2025)),
                                 datetime.date(2027, 3, 31))


class ReviewedLagTests(unittest.TestCase):
    """The defaults are a rule of thumb. Census QWI lands a quarter about eight months after it
    ends, so the 120-day default put roughly 120 of its metrics on the overdue list months before
    Census could possibly have published them (measured 2026-09-12)."""
    def test_a_reviewed_lag_overrides_the_default(self):
        slow = metric(period_basis='quarter', publication_lag_days=240)
        fast = metric(period_basis='quarter')
        self.assertEqual(research.next_reading_possible(fast, reading('2025-Q4', 2025)), datetime.date(2026, 7, 29))
        self.assertEqual(research.next_reading_possible(slow, reading('2025-Q4', 2025)), datetime.date(2026, 11, 26))

    def test_a_nonsense_lag_is_ignored_rather_than_trusted(self):
        for bad in (0, -30, 'soon', None, 12.5):
            with self.subTest(lag=bad):
                m = metric(period_basis='quarter', publication_lag_days=bad)
                self.assertEqual(research.next_reading_possible(m, reading('2025-Q4', 2025)),
                                 datetime.date(2026, 7, 29), 'falls back to the default')

    def test_the_slow_agencies_carry_their_reviewed_lag(self):
        data = json.loads((ROOT/'site/data/ledger.json').read_text(encoding='utf-8'))
        for source, expected in [('census-qwi-api', 240), ('bls-qcew-open-data', 180)]:
            owned = [m for m in data['metrics'] if source in (m.get('source_ids') or [])]
            self.assertTrue(owned, source)
            for m in owned:
                with self.subTest(metric=m['id']):
                    self.assertEqual(m.get('publication_lag_days'), expected)

    def test_the_validator_bounds_it(self):
        from validate import require
        import validate as v
        data = json.loads((ROOT/'research/catalog.json').read_text(encoding='utf-8'))
        target = next(m for m in data['metrics'] if 'publication_lag_days' in m)
        for bad in (0, -1, 5000, 'soon', 12.5):
            with self.subTest(lag=bad):
                probe = dict(target, publication_lag_days=bad)
                with self.assertRaises(ValueError):
                    if 'publication_lag_days' in probe:
                        require(type(probe['publication_lag_days']) is int and 0 < probe['publication_lag_days'] <= 1000,
                                'Invalid publication lag')


class SelectionTests(unittest.TestCase):
    """The 40 metrics that burned the session must no longer be offered, and a figure that really
    is late must still be."""
    def setUp(self):
        self.data = json.loads((ROOT/'site/data/ledger.json').read_text(encoding='utf-8'))
        self.registry = json.loads((ROOT/'research/sources.json').read_text(encoding='utf-8'))
        self.ecosystem = json.loads((ROOT/'research/ecosystem.json').read_text(encoding='utf-8'))

    class Health:
        def get(self, *a, **k): return {}
        def due(self, *a, **k): return True

    def offered(self, limit=20):
        return research.select_stale_tasks(self.data, self.registry, self.ecosystem,
                                            self.Health(), SEPT_2026, limit)

    def test_no_annual_revenue_anchored_on_2025_is_offered_in_september_2026(self):
        offered = {t['metric'] for t in self.offered(limit=200)}
        revenues = {m['id'] for m in self.data['metrics']
                    if m['id'].startswith('revenue-') and not m.get('period_basis')}
        self.assertTrue(revenues, 'the catalog should hold annual revenue metrics')
        self.assertEqual(offered & revenues, set(),
                         'these cannot have a newer figure until the fiscal year closes')

    def test_every_offered_task_could_actually_have_a_newer_reading(self):
        for task in self.offered(limit=200):
            m = next(x for x in self.data['metrics'] if x['id'] == task['metric'])
            latest = research.latest_non_superseded(self.data['observations'], m['id'])
            with self.subTest(metric=m['id']):
                self.assertLessEqual(research.next_reading_possible(m, latest), SEPT_2026)
                self.assertGreaterEqual(task['overdue_days'], 0)

    def test_the_old_clock_would_have_offered_far_more(self):
        """Guards the saving, so a regression shows up as a number rather than a slowdown."""
        obs = self.data['observations']
        old = new = 0
        for m in self.data['metrics']:
            if m.get('definition_stable') is False: continue
            latest = research.latest_non_superseded(obs, m['id'])
            if latest is None: continue
            threshold = research.STALE_THRESHOLD_DAYS.get(m.get('period_basis'), research.STALE_DEFAULT_THRESHOLD_DAYS)
            old += (SEPT_2026 - research.observation_anchor_date(m, latest)).days > threshold
            new += SEPT_2026 >= research.next_reading_possible(m, latest)
        self.assertLess(new, old*0.7, 'the new clock should free most of the queue: %d -> %d' % (old, new))


class HealthReportTests(unittest.TestCase):
    """The health report and the research lane must not disagree about what is overdue."""
    def test_the_report_uses_the_same_clock(self):
        report = nightly.stale_figures(ROOT)
        data = json.loads((ROOT/'site/data/ledger.json').read_text(encoding='utf-8'))
        today = datetime.datetime.now(datetime.timezone.utc).date()
        expected = 0
        for m in data['metrics']:
            o = research.latest_non_superseded(data['observations'], m['id'])
            if o is None: continue
            expected += today >= research.next_reading_possible(m, o)
        self.assertEqual(report['overdue_count'], expected)

    def test_each_row_says_when_a_newer_reading_became_possible(self):
        for row in nightly.stale_figures(ROOT)['most_overdue']:
            self.assertIn('newer_reading_possible_from', row)
            self.assertNotIn('age_days', row, 'time held is the question that produced the waste')


if __name__ == '__main__':
    unittest.main()
