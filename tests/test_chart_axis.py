"""The x-axis gives each reading its own position.

A metric with a sub-annual period_basis holds several readings inside one year. The axis used to be
keyed on the calendar year, so those readings were drawn on top of each other: six monthly readings
of U.S. data-centre construction became overlapping bars with overlapping value labels on a phone,
and each grid-demand series put twelve months into a single slot. 204 metrics were affected.
"""
import collections
import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))

SUB_ANNUAL = {'month', 'quarter', 'snapshot'}


def ledger():
    return json.loads((ROOT/'site/data/ledger.json').read_text(encoding='utf-8'))


class CrowdingTests(unittest.TestCase):
    """The data condition that made the defect visible, so its scale stays in view."""
    def setUp(self):
        d = ledger()
        self.metrics = {m['id']: m for m in d['metrics']}
        self.by_metric = collections.defaultdict(list)
        for o in d['observations']:
            if not o.get('superseded_by'):
                self.by_metric[o['metric']].append(o)

    def test_many_metrics_really_do_hold_several_readings_a_year(self):
        crowded = [mid for mid, rows in self.by_metric.items()
                   if max(collections.Counter(o['year'] for o in rows).values()) > 1]
        self.assertGreater(len(crowded), 100,
                           'if this ever drops, confirm the axis fix is still needed before relaxing it')

    def test_every_crowded_metric_declares_a_sub_annual_basis(self):
        """A metric with several readings a year and no period_basis cannot be given one slot each,
        because its periods are free text. There should be none."""
        offenders = []
        for mid, rows in self.by_metric.items():
            worst = max(collections.Counter(o['year'] for o in rows).values())
            if worst > 1 and self.metrics[mid].get('period_basis') not in SUB_ANNUAL:
                offenders.append('%s (%d in one year, basis %r)' % (mid, worst, self.metrics[mid].get('period_basis')))
        self.assertEqual(offenders, [], 'these would still stack: %s' % offenders[:5])

    def test_a_sub_annual_period_is_unique_within_its_metric(self):
        """One slot per period only works if a period identifies one reading."""
        for mid, rows in self.by_metric.items():
            if self.metrics[mid].get('period_basis') not in SUB_ANNUAL:
                continue
            counts = collections.Counter((o['period'], o['status']) for o in rows)
            repeated = [k for k, n in counts.items() if n > 1]
            self.assertEqual(repeated, [], '%s repeats a period: %s' % (mid, repeated[:3]))


@unittest.skipUnless(shutil.which('node'), 'node is not installed')
class ChartSlotJsTests(unittest.TestCase):
    def test_node_test_passes(self):
        result = subprocess.run(['node', '--test', 'tests/chart_slots.cjs'], cwd=ROOT,
                                 capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_the_published_script_matches_the_source_script(self):
        self.assertEqual((ROOT/'site/assets/app.js').read_text(encoding='utf-8'),
                         (ROOT/'docs/assets/app.js').read_text(encoding='utf-8'),
                         'docs/assets/app.js is what the public site serves')


if __name__ == '__main__':
    unittest.main()
