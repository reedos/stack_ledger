"""A host that refuses the crawler is not asked again fifteen minutes later.

Measured over the 5-hour session of 2026-09-13: 32 of 692 fetches were repeat 403s against 13
sources that had already refused once inside that same session, because the backoff doubling
started at 900s and a five-hour run gets through 15m/30m/1h/2h before the multi-day ceiling
engages. A 403 or a robots disallow does not change on that timescale.

The trade this encodes: a refusal costs at most one skipped nightly run if it was transient,
against roughly 20 wasted fetches per long session if it was not.
"""
import sys
import tempfile
import time
import unittest
from pathlib import Path
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import collection_health as health

HOUR = 3600
DAY = 86400


def store():
    temp = tempfile.TemporaryDirectory()
    return health.Health(Path(temp.name)/'health.json'), temp


def refuse(store_, url, times=1, code=403):
    for _ in range(times):
        store_.failure('page', url, HTTPError(url, code, 'Forbidden', None, None))
    return store_.get('page', url)


class FirstRefusalWaits(unittest.TestCase):
    def setUp(self):
        self.health, temp = store()
        self.addCleanup(temp.cleanup)

    def test_a_single_403_holds_the_page_for_six_hours(self):
        record = refuse(self.health, 'https://blocked.example/a')
        self.assertGreaterEqual(record['next_attempt']-time.time(), 6*HOUR-5)

    def test_a_five_hour_session_gets_exactly_one_attempt_at_a_refusing_page(self):
        """The regression this file exists for: the whole run must not re-ask."""
        url = 'https://blocked.example/b'
        refuse(self.health, url)
        later = time.time()+5*HOUR
        self.assertGreater(self.health.get('page', url)['next_attempt'], later)

    def test_every_refusing_status_starts_at_six_hours(self):
        for code in (401, 403, 406, 451):
            record = refuse(self.health, 'https://blocked.example/code-%d' % code, code=code)
            self.assertGreaterEqual(record['next_attempt']-time.time(), 6*HOUR-5, code)

    def test_a_robots_disallow_starts_at_six_hours_too(self):
        self.health.failure('page', 'https://robots.example/c', ValueError('Blocked by robots policy'))
        record = self.health.get('page', 'https://robots.example/c')
        self.assertTrue(record['refused'])
        self.assertGreaterEqual(record['next_attempt']-time.time(), 6*HOUR-5)


class TransientErrorsAreUnchanged(unittest.TestCase):
    """A timeout or a 500 may well clear in minutes; only refusals were retimed."""

    def setUp(self):
        self.health, temp = store()
        self.addCleanup(temp.cleanup)

    def test_a_first_timeout_still_waits_only_fifteen_minutes(self):
        self.health.failure('page', 'https://flaky.example/a', TimeoutError('timed out'))
        record = self.health.get('page', 'https://flaky.example/a')
        self.assertNotIn('refused', record)
        self.assertLessEqual(record['next_attempt']-time.time(), 15*60+5)

    def test_a_transient_error_still_tops_out_at_six_hours(self):
        for _ in range(9):
            self.health.failure('page', 'https://flaky.example/b', TimeoutError('timed out'))
        record = self.health.get('page', 'https://flaky.example/b')
        self.assertLessEqual(record['next_attempt']-time.time(), 6*HOUR+5)


class CeilingAndOverrides(unittest.TestCase):
    def setUp(self):
        self.health, temp = store()
        self.addCleanup(temp.cleanup)

    def test_a_persistent_refusal_still_stops_at_three_days(self):
        record = refuse(self.health, 'https://blocked.example/d', times=9)
        self.assertLessEqual(record['next_attempt']-time.time(), 3*DAY+5)
        self.assertGreater(record['next_attempt']-time.time(), 2*DAY)

    def test_it_reaches_the_ceiling_in_four_refusals_not_nine(self):
        record = refuse(self.health, 'https://blocked.example/e', times=4)
        self.assertGreaterEqual(record['next_attempt']-time.time(), 2*DAY-5)

    def test_a_longer_retry_after_still_wins(self):
        """Retry-After is the host telling us when to come back; it outranks our schedule."""
        error = HTTPError('https://blocked.example/f', 429, 'Too Many', {'Retry-After': '604800'}, None)
        self.health.failure('page', 'https://blocked.example/f', error)
        record = self.health.get('page', 'https://blocked.example/f')
        self.assertGreater(record['next_attempt']-time.time(), 6*DAY)


if __name__ == '__main__':
    unittest.main()
