"""A weekly fixed page that never changes is read less often, like a daily one.

Measured 2026-09-12: 325 of 393 fetchable sources were fixed pages, and not one was backed off.
169 were registered weekly and the promotion rule exempted weekly outright; the queue gate in
research.py was written `if cadence == 'daily'`, so even a widened rule would have been a silent
no-op. A weekly page was re-read on its weekday forever, whatever its unchanged streak said.

Indexes are polled on feed_poll_minutes and skip this rule (`not is_feed` at the gate), because
an index's job is discovery and whether its own page text changed is irrelevant to that.
"""
import datetime
import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import source_policy as sp


def weekly(streak, weekday=2):
    return {'cadence': 'weekly', 'weekday': weekday}, {'unchanged_streak': streak}


class RuleTests(unittest.TestCase):
    def test_a_weekly_page_backs_off_after_four_unchanged_weeks(self):
        for streak, expected in [(0, 'weekly'), (1, 'weekly'), (3, 'weekly'), (4, 'monthly'), (12, 'monthly')]:
            with self.subTest(streak=streak):
                policy, state = weekly(streak)
                self.assertEqual(sp.effective_cadence(policy, state), expected)

    def test_daily_semantics_are_unchanged(self):
        for streak, expected in [(0, 'daily'), (6, 'daily'), (7, 'weekly'), (12, 'weekly'), (13, 'monthly')]:
            with self.subTest(streak=streak):
                self.assertEqual(sp.effective_cadence({'cadence': 'daily'}, {'unchanged_streak': streak}), expected)

    def test_no_state_means_the_registered_cadence(self):
        for cadence in ('daily', 'weekly', 'monthly', 'manual'):
            with self.subTest(cadence=cadence):
                self.assertEqual(sp.effective_cadence({'cadence': cadence}, None), cadence)
                self.assertEqual(sp.effective_cadence({'cadence': cadence}, {}), cadence)

    def test_manual_and_monthly_are_never_touched(self):
        for cadence in ('manual', 'monthly'):
            with self.subTest(cadence=cadence):
                self.assertEqual(sp.effective_cadence({'cadence': cadence}, {'unchanged_streak': 99}), cadence)

    def test_a_change_resets_the_next_check_to_weekly(self):
        """The caller stores streak 0 on any change; the rule must follow it back immediately."""
        policy, _ = weekly(0)
        self.assertEqual(sp.effective_cadence(policy, {'unchanged_streak': 0}), 'weekly')


class DueTests(unittest.TestCase):
    """A promoted weekly page is due on its weekday only in the first week of the month."""

    def test_promoted_to_monthly_is_due_once_a_month(self):
        policy, state = weekly(4, weekday=2)   # Wednesday
        year, month = 2026, 10
        days = [datetime.date(year, month, d) for d in range(1, 32)]
        due_days = [d for d in days if sp.due(policy, d, state)]
        self.assertEqual(due_days, [datetime.date(2026, 10, 7)], 'first Wednesday of October only')

    def test_not_yet_promoted_is_still_due_every_week(self):
        policy, state = weekly(3, weekday=2)
        days = [datetime.date(2026, 10, d) for d in range(1, 32)]
        self.assertEqual(len([d for d in days if sp.due(policy, d, state)]), 4, 'every Wednesday')

    def test_a_real_week_still_reaches_every_weekly_source_without_state(self):
        """Queue assembly calls due() with no state; the schedule guarantee there is untouched."""
        registry = json.loads((ROOT/'research/sources.json').read_text(encoding='utf-8'))
        weekly_sources = {sid: p for sid, p in registry['collection'].items() if p['cadence'] == 'weekly'}
        monday = datetime.date(2026, 9, 14)
        seen = {sid for off in range(7) for sid, p in weekly_sources.items()
                if sp.due(p, monday + datetime.timedelta(days=off))}
        self.assertEqual(seen, set(weekly_sources))


class GateTests(unittest.TestCase):
    """The rule only matters if the queue consults it for weekly sources."""

    def setUp(self):
        self.src = (ROOT/'scripts/research.py').read_text(encoding='utf-8')

    def test_the_adaptive_gate_covers_weekly_sources(self):
        gate = next(l for l in self.src.splitlines() if "and not is_feed and source['url'] not in stale_forced_urls" in l)
        self.assertIn("in ('daily','weekly')", gate, 'the gate still says ==daily, so weekly backoff never fires')

    def test_the_gate_only_acts_on_a_promoted_source(self):
        """A weekly source queued off its weekday (never attempted, or overdue -- the attempted
        clause in select_sources) must not be dropped by a second weekday check. Widening the
        gate to weekly without this condition cost one document in three end-to-end tests."""
        self.assertIn("effective_cadence(cadence_policy,page_state)!=cadence_policy.get('cadence')", self.src)

    def test_indexes_are_still_exempt_at_the_gate(self):
        gate = next(l for l in self.src.splitlines() if "in ('daily','weekly')" in l and 'stale_forced_urls' in l)
        self.assertIn('not is_feed', gate)

    def test_the_attempt_log_reports_an_index_at_its_registered_cadence(self):
        """The log recorded the promoted value for indexes and 33 live feeds read as 'monthly'."""
        self.assertIn("None if source.get('index') else fetcher.fetch_state.get('page',source['url'])", self.src)


class RegistryTests(unittest.TestCase):
    """Against the real registry and fetch state: the rule now applies to every weekly page."""

    def test_no_weekly_fixed_page_is_exempt_any_more(self):
        registry = json.loads((ROOT/'research/sources.json').read_text(encoding='utf-8'))
        state_path = ROOT/'.local/fetch-state.json'
        if not state_path.exists():
            self.skipTest('no fetch state on this checkout')
        fetch_state = json.loads(state_path.read_text(encoding='utf-8'))
        col = registry['collection']
        exempt = []; promoted = 0
        for s in registry['sources']:
            p = col.get(s['id']) or {}
            if p.get('cadence') != 'weekly' or s.get('index'): continue
            st = fetch_state.get('page:' + hashlib.sha256(s['url'].encode()).hexdigest()) or {}
            streak = st.get('unchanged_streak', 0) or 0
            eff = sp.effective_cadence(p, st)
            if streak >= sp.PROMOTE_WEEKLY_TO_MONTHLY_STREAK:
                promoted += 1
                if eff != 'monthly': exempt.append(s['id'])
            else:
                self.assertEqual(eff, 'weekly', s['id'])
        self.assertEqual(exempt, [], 'weekly pages past the threshold that the rule still leaves weekly')


if __name__ == '__main__':
    unittest.main()
