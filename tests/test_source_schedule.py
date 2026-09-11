"""Weekly sources are spread across the week rather than piled onto one night.

`due()` treats a weekly source as due only on its registered `weekday`, which defaults to 0. On
2026-09-11, 155 of 176 weekly sources sat at that default, so 88% of the weekly corpus came due on
Monday and Friday, Saturday and Sunday nights had none at all. Every one of the 198 daily sources
sat there too, so the moment adaptive promotion demoted them to weekly they would have landed on
Monday as well.

A session that has nothing new to read is the "pipeline is healthy, output is empty" complaint.
"""
import collections
import datetime
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from source_policy import due

WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']


def collection():
    return json.loads((ROOT/'research/sources.json').read_text(encoding='utf-8'))['collection']


def weekly():
    return {sid: p for sid, p in collection().items() if p['cadence'] == 'weekly'}


class SpreadTests(unittest.TestCase):
    def test_no_single_night_carries_most_of_the_weekly_corpus(self):
        counts = collections.Counter(p['weekday'] for p in weekly().values())
        total = sum(counts.values())
        busiest = max(counts.values())
        self.assertLess(busiest/total, 0.40,
                        'one night holds %d of %d weekly sources: %s'
                        % (busiest, total, {WEEKDAYS[k]: counts.get(k, 0) for k in range(7)}))

    def test_every_night_of_the_week_has_weekly_sources_to_read(self):
        counts = collections.Counter(p['weekday'] for p in weekly().values())
        empty = [WEEKDAYS[d] for d in range(7) if not counts.get(d)]
        self.assertEqual(empty, [], 'these nights would see no weekly source at all: %s' % empty)

    def test_daily_sources_are_spread_too_because_promotion_inherits_the_weekday(self):
        """A daily source unchanged for a week is checked weekly, on this same field."""
        daily = [p for p in collection().values() if p['cadence'] == 'daily']
        counts = collections.Counter(p['weekday'] for p in daily)
        self.assertLess(max(counts.values())/len(daily), 0.40,
                        'promotion would pile these onto one night: %s'
                        % {WEEKDAYS[k]: counts.get(k, 0) for k in range(7)})

    def test_a_real_week_reaches_every_weekly_source_exactly_once(self):
        """Spreading must not drop or double-check anything: still one visit a week each."""
        seen = collections.Counter()
        monday = datetime.date(2026, 9, 14)
        for offset in range(7):
            day = monday + datetime.timedelta(days=offset)
            for sid, policy in weekly().items():
                if due(policy, day):
                    seen[sid] += 1
        self.assertEqual(set(seen), set(weekly()), 'every weekly source is reached in a week')
        self.assertEqual(set(seen.values()), {1}, 'and exactly once')

    def test_manual_sources_were_left_alone(self):
        """Their weekday is meaningless because they are never fetched; moving them is noise."""
        manual = [p for p in collection().values() if p['cadence'] == 'manual']
        self.assertTrue(manual)
        for policy in manual:
            self.assertFalse(due(policy, datetime.date(2026, 9, 14)))

    def test_the_published_mirror_matches_the_registry(self):
        books = json.loads((ROOT/'site/data/source-books.json').read_text(encoding='utf-8'))
        self.assertEqual(books['collection'], collection())


if __name__ == '__main__':
    unittest.main()
