"""Freezing a live series is the expensive mistake, so the catalog is held to its own history.

`refresh_expected: false` stops the runner ever chasing a metric again. A wrong one does not
fail, warn or show up on the site -- the figure simply stops being updated, forever. A first pass
on 2026-09-10 wrote the field onto 116 metrics and froze 59 live ones with it, including TSMC
Arizona's fab capacity by phase, every Stargate and Colossus planned end-state, and Waymo's
fleet and weekly paid trips. These tests make that mistake loud instead of silent, by checking
the classification against readings the ledger already holds.
"""
import collections
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import research

PLEDGE = {'company-commitment', 'government-target'}
# Reviewed as finished on 2026-09-10: a completed plant's nameplate capacity at commercial
# operation, and a factory's investment and headcount disclosed once at its inauguration.
REVIEWED_OVERRIDES = {'gemini-solar', 'gemini-storage', 'gemini-storage-energy',
                      'firstsolar-la-investment', 'firstsolar-la-jobs'}


def catalog():
    return json.loads((ROOT/'research/catalog.json').read_text(encoding='utf-8'))


def observations():
    return json.loads((ROOT/'site/data/ledger.json').read_text(encoding='utf-8'))['observations']


def restated():
    """Metric ids the ledger shows being restated: two distinct readings that are not both pledges."""
    live = collections.defaultdict(list)
    for o in observations():
        if not o.get('superseded_by'):
            live[o['metric']].append(o)
    out = {}
    for mid, records in live.items():
        periods = {str(r.get('period') or r.get('year')) for r in records}
        if len(periods) >= 2 and not all(r.get('status') in PLEDGE for r in records):
            out[mid] = sorted(periods)
    return out


class EvidenceTests(unittest.TestCase):
    def test_no_metric_the_ledger_shows_being_restated_is_treated_as_finished(self):
        obs = observations()
        was_restated = restated()
        frozen = [m['id'] for m in catalog()['metrics']
                  if m['id'] in was_restated and research.refresh_expected(m, obs) is False]
        self.assertEqual(frozen, [], 'these metrics have been restated and must stay refresh-expected: %s'
                         % {k: was_restated[k] for k in frozen})

    def test_no_one_time_measurement_type_has_a_restated_metric(self):
        was_restated = restated()
        offenders = {}
        for m in catalog()['metrics']:
            if m.get('measurement_type') in research.ONE_TIME_MEASUREMENT_TYPES and m['id'] in was_restated:
                offenders.setdefault(m['measurement_type'], []).append(m['id'])
        self.assertEqual(offenders, {}, 'a one-time type cannot contain a restated metric: %s' % offenders)


class OverrideTests(unittest.TestCase):
    """The explicit field beats the derivation forever, so it stays rare and named."""
    def test_only_the_reviewed_overrides_carry_the_field(self):
        carried = {m['id'] for m in catalog()['metrics'] if 'refresh_expected' in m}
        self.assertEqual(carried, REVIEWED_OVERRIDES)

    def test_every_override_is_false_and_records_a_closed_figure(self):
        obs = observations()
        for m in catalog()['metrics']:
            if m['id'] not in REVIEWED_OVERRIDES:
                continue
            self.assertIs(m['refresh_expected'], False)
            # It must genuinely need the override: the derivation alone must not already catch it.
            bare = {k: v for k, v in m.items() if k != 'refresh_expected'}
            self.assertTrue(research.refresh_expected(bare, obs),
                            '%s does not need an explicit override; the derivation already freezes it' % m['id'])


class LiveSeriesTests(unittest.TestCase):
    """The specific series the first pass froze. Named so a regression says which one broke."""
    CHASED = ['tsmc-cowos-wpm', 'tsmc-arizona-phase1-capacity', 'abilene-it-endstate',
              'colossus-two-it-endstate', 'waymo-paid-weekly', 'waymo-operating-fleet',
              'tesla-cortex-1-compute', 'inference-cost']

    def test_ongoing_capacity_and_activity_are_still_chased(self):
        obs = observations()
        metrics = {m['id']: m for m in catalog()['metrics']}
        for mid in self.CHASED:
            self.assertIn(mid, metrics)
            self.assertTrue(research.refresh_expected(metrics[mid], obs),
                            '%s is a live figure and must stay refresh-expected' % mid)

    def test_a_finished_figure_is_still_left_alone(self):
        obs = observations()
        metrics = {m['id']: m for m in catalog()['metrics']}
        for mid in ['gemini-solar', 'crane-restart', 'eaton-jonesville-investment']:
            self.assertFalse(research.refresh_expected(metrics[mid], obs),
                             '%s is finished and must not be chased' % mid)


if __name__ == '__main__':
    unittest.main()
