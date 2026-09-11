"""The published run history is a bounded window.

A session appends one run per batch: the four days to 2026-09-10 published 623 of them into a
ledger every reader downloads, while the site has only ever displayed the most recent 30 and
.local/runs already keeps every receipt. These tests hold the window's three promises -- it is
capped, it never loses the run the runtime's last-success claim names, and retiring a run from it
is not the same thing as rewriting one.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import research
import editorial_review as er
from validate import validate

EXCERPTS = {'version': 1, 'excerpts': []}


def run(n, status='partial', failures=()):
    return {'id': 'run-%04d' % n, 'started_at': '2026-09-10T00:00:00Z',
            'finished_at': '2026-09-10T%02d:00:00Z' % (n % 24), 'status': status,
            'documents_fetched': 0, 'documents_reviewed': 0, 'accepted': 0, 'quarantined': 0,
            'source_failures': [{'source': s, 'reason': 'HTTP 403'} for s in failures],
            'model_calls': 0, 'coverage_layers': []}


def ledger(runs):
    return {'version': 1, 'seed_date': '2026-01-01', 'layers': [], 'metrics': [], 'targets': [],
            'sources': [], 'observations': [], 'events': [], 'runs': list(runs), 'runtime': {}}


def limit():
    return json.loads((ROOT/'research/runtime.json').read_text(encoding='utf-8'))['published_run_limit']


class TrimTests(unittest.TestCase):
    def test_a_history_inside_the_window_is_left_alone(self):
        runs = [run(i) for i in range(10)]
        self.assertEqual(research.trim_published_runs(runs, 250), runs)

    def test_the_newest_runs_are_the_ones_kept(self):
        runs = [run(i) for i in range(400)]
        kept = research.trim_published_runs(runs, 250)
        self.assertEqual(len(kept), 250)
        self.assertEqual(kept, runs[-250:])

    def test_the_last_successful_run_is_pinned_when_it_falls_out_of_the_window(self):
        runs = [run(i) for i in range(400)]
        runs[5]['status'] = 'success'
        kept = research.trim_published_runs(runs, 250)
        # Pinned, still oldest-first, and the window does not grow to make room for it.
        self.assertEqual(len(kept), 250)
        self.assertEqual(kept[0]['id'], 'run-0005')
        self.assertEqual(kept[1:], runs[-249:])

    def test_a_retained_success_is_not_pinned_twice(self):
        runs = [run(i) for i in range(400)]
        runs[399]['status'] = 'success'
        self.assertEqual(research.trim_published_runs(runs, 250), runs[-250:])

    def test_a_window_too_small_to_hold_the_newest_run_is_refused(self):
        # The runtime's last_attempt names the newest run; a limit of 1 plus a pin would drop it.
        runs = [run(i) for i in range(10)]
        for size in (None, 0, 1):
            self.assertEqual(research.trim_published_runs(runs, size), runs)

    def test_the_window_survives_repeated_trimming(self):
        runs = [run(i) for i in range(260)]
        runs[0]['status'] = 'success'
        once = research.trim_published_runs(runs, 250)
        self.assertEqual(research.trim_published_runs(once, 250), once)


class ValidationTests(unittest.TestCase):
    def test_the_published_ledger_is_inside_its_own_limit(self):
        data = json.loads((ROOT/'site/data/ledger.json').read_text(encoding='utf-8'))
        self.assertLessEqual(len(data['runs']), limit())

    def test_an_oversized_history_fails_validation(self):
        data = json.loads((ROOT/'site/data/ledger.json').read_text(encoding='utf-8'))
        last = data['runs'][-1]
        # Same finished_at and status, so only the count is wrong: the runtime still matches.
        while len(data['runs']) <= limit():
            data['runs'].append(dict(last, id=last['id']+'-x%d' % len(data['runs'])))
        with self.assertRaisesRegex(ValueError, 'reviewed window'):
            validate(data)


class MonitoringDeltaTests(unittest.TestCase):
    """A publish that retires the oldest runs is routine; rewriting or reordering one is not."""
    def setUp(self):
        self.limit = limit()
        self.before = ledger(run(i) for i in range(self.limit))

    def published(self, appended=1):
        runs = list(self.before['runs']) + [run(self.limit+i) for i in range(appended)]
        return ledger(research.trim_published_runs(runs, self.limit))

    def test_retiring_the_oldest_runs_to_make_room_is_allowed(self):
        after = self.published()
        self.assertNotIn(self.before['runs'][0]['id'], {r['id'] for r in after['runs']})
        research.validate_monitoring_delta(self.before, after, EXCERPTS, EXCERPTS)

    def test_a_retained_run_may_not_be_rewritten(self):
        after = self.published()
        after['runs'][5] = dict(after['runs'][5], accepted=9)
        with self.assertRaisesRegex(ValueError, 'rewrote existing runs'):
            research.validate_monitoring_delta(self.before, after, EXCERPTS, EXCERPTS)

    def test_the_retained_runs_may_not_be_reordered(self):
        after = self.published()
        after['runs'][0], after['runs'][1] = after['runs'][1], after['runs'][0]
        with self.assertRaisesRegex(ValueError, 'reordered'):
            research.validate_monitoring_delta(self.before, after, EXCERPTS, EXCERPTS)

    def test_runs_may_not_be_dropped_while_the_window_has_room(self):
        after = ledger(self.before['runs'][10:])
        with self.assertRaisesRegex(ValueError, 'without a full window'):
            research.validate_monitoring_delta(self.before, after, EXCERPTS, EXCERPTS)

    def test_a_batch_that_appends_without_retiring_is_still_allowed(self):
        before = ledger(run(i) for i in range(3))
        after = ledger(list(before['runs']) + [run(3)])
        research.validate_monitoring_delta(before, after, EXCERPTS, EXCERPTS)


class MonitoringHistoryTests(unittest.TestCase):
    """The editorial review reads failures from .local/runs, so the window cannot hide a source
    that failed before the oldest published run."""
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root/'site/data').mkdir(parents=True)
        (self.root/'.local/runs').mkdir(parents=True)
        (self.root/'.local/evidence').mkdir(parents=True)

    def write_ledger(self, data):
        (self.root/'site/data/ledger.json').write_text(json.dumps(data), encoding='utf-8')

    def test_a_failure_from_a_retired_run_is_still_reported(self):
        data = ledger([run(900)])
        data['sources'] = [{'id': 'weekly-source', 'url': 'https://example.gov/report'}]
        self.write_ledger(data)
        retired = run(1, failures=['weekly-source'])
        (self.root/'.local/runs/run-0001.json').write_text(
            json.dumps({'receipt': retired, 'quarantine': [], 'collection': {}}), encoding='utf-8')
        result = er.monitoring(self.root)
        self.assertEqual(result['weekly-source']['outcome'], 'source_inaccessible')
        self.assertEqual(result['weekly-source']['checked_at'], retired['finished_at'])

    def test_an_unreadable_receipt_does_not_stop_the_review(self):
        self.write_ledger(ledger([run(900)]))
        (self.root/'.local/runs/broken.json').write_text('{not json', encoding='utf-8')
        self.assertEqual(er.monitoring(self.root), {})


if __name__ == '__main__':
    unittest.main()
