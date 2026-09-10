import json
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import catalog_jobs as cj


def wait_for(predicate, timeout=5):
    deadline = time.monotonic()+timeout
    while time.monotonic() < deadline:
        if predicate(): return True
        time.sleep(0.01)
    return predicate()


class FakeClock:
    """Deterministic time for the lock-wait loop: sleep() advances the shared counter instantly."""
    def __init__(self, start=0):
        self.now = start
        self.calls = []

    def clock(self):
        return self.now

    def sleep(self, seconds):
        self.calls.append(seconds)
        self.now += seconds


class QueueTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup); self.root = Path(self.temp.name)

    def test_jobs_run_in_fifo_order(self):
        order = []
        def runner(root, job, **kw):
            order.append(job['rid']); time.sleep(0.02); return {'ok': True}
        q = cj.Queue(self.root, runner=runner)
        self.addCleanup(q.close)
        jobs = [q.enqueue('validate', rid) for rid in ['a', 'b', 'c']]
        self.assertTrue(wait_for(lambda: all(q.jobs[j['id']]['status'] == 'done' for j in jobs)))
        self.assertEqual(order, ['a', 'b', 'c'])

    def test_idempotent_enqueue_returns_existing_queued_or_running_job(self):
        started = []
        def runner(root, job, **kw):
            started.append(job['id']); time.sleep(0.05); return {}
        q = cj.Queue(self.root, runner=runner)
        self.addCleanup(q.close)
        first = q.enqueue('validate', 'catalog-x')
        second = q.enqueue('validate', 'catalog-x')  # still queued/running: same job, not a duplicate
        self.assertEqual(first['id'], second['id'])
        self.assertEqual(len([j for j in q.jobs.values() if j['rid'] == 'catalog-x']), 1)
        self.assertTrue(wait_for(lambda: q.jobs[first['id']]['status'] == 'done'))
        third = q.enqueue('validate', 'catalog-x')  # a fresh, separate job once the first has finished
        self.assertNotEqual(third['id'], first['id'])
        self.assertTrue(wait_for(lambda: q.jobs[third['id']]['status'] == 'done'))

    def test_unknown_kind_rejected(self):
        q = cj.Queue(self.root, runner=lambda *a, **k: None)
        self.addCleanup(q.close)
        with self.assertRaises(ValueError): q.enqueue('bogus', 'catalog-x')

    def test_failure_is_captured_not_raised(self):
        def runner(root, job, **kw):
            raise RuntimeError('synthetic failure')
        q = cj.Queue(self.root, runner=runner)
        self.addCleanup(q.close)
        job = q.enqueue('validate', 'catalog-x')
        self.assertTrue(wait_for(lambda: q.jobs[job['id']]['status'] == 'failed'))
        stored = q.jobs[job['id']]
        self.assertIn('synthetic failure', stored['error'])
        self.assertIsNotNone(stored['finished_at'])

    def test_state_is_mirrored_to_disk_and_recovered_on_restart(self):
        def runner(root, job, **kw): return {'passed': True}
        q = cj.Queue(self.root, runner=runner)
        job = q.enqueue('validate', 'catalog-x')
        self.assertTrue(wait_for(lambda: q.jobs[job['id']]['status'] == 'done'))
        q.close()
        path = self.root/'.local/catalog-jobs.json'
        self.assertTrue(path.exists())
        on_disk = json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(on_disk[0]['id'], job['id']); self.assertEqual(on_disk[0]['status'], 'done')
        self.assertEqual(cj.read_latest(self.root, 'catalog-x')['id'], job['id'])

    def test_a_restart_marks_a_stuck_running_job_failed(self):
        # A job left 'queued'/'running' on disk could not really have survived a process restart.
        cj_path = self.root/'.local/catalog-jobs.json'
        cj_path.parent.mkdir(parents=True)
        cj_path.write_text(json.dumps([{'id': 'job-stale', 'rid': 'catalog-x', 'kind': 'publish', 'status': 'running',
            'step': 'Publishing…', 'created_at': cj.now(), 'started_at': cj.now(), 'finished_at': None,
            'error': None, 'result': None, 'params': {}}]), encoding='utf-8')
        q = cj.Queue(self.root, runner=lambda *a, **k: None, autostart=False)
        self.assertEqual(q.jobs['job-stale']['status'], 'failed')
        self.assertIn('restarted', q.jobs['job-stale']['error'])

    def test_recent_includes_queued_and_running_regardless_of_age_and_excludes_old_terminal(self):
        old = cj.now()
        q = cj.Queue(self.root, runner=lambda *a, **k: {}, autostart=False)
        q.jobs['job-old'] = {'id': 'job-old', 'rid': 'catalog-old', 'kind': 'validate', 'status': 'done',
            'step': 'Done', 'created_at': '2020-01-01T00:00:00Z', 'started_at': old, 'finished_at': old, 'error': None, 'result': {}, 'params': {}}
        q._save()
        recent = cj.read_recent(self.root, hours=24)
        self.assertNotIn('job-old', [j['id'] for j in recent])


class PublishLockWaitTests(unittest.TestCase):
    """The publish job polls (every 10s, up to 20 minutes) for research/session locks instead of failing
    the tap; validation never waits on them at all. A fake clock proves this without real sleeping."""
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup); self.root = Path(self.temp.name)
        (self.root/'.local').mkdir(parents=True)

    def test_publish_waits_for_a_lock_to_clear_then_runs(self):
        lock = self.root/'.local/research.lock'; lock.write_text('{}', encoding='utf-8')
        clock = FakeClock()
        calls = []
        def fake_apply_publish(root, rid, proposal_hash, review_hash, reviewer, confirmed, identity):
            calls.append(1); return {'status': 'deployed', 'commit': 'abc123'}
        import catalog_review
        orig = catalog_review.apply_publish
        catalog_review.apply_publish = fake_apply_publish
        self.addCleanup(setattr, catalog_review, 'apply_publish', orig)

        def remove_lock_after_two_polls():
            if len(clock.calls) >= 2 and lock.exists(): lock.unlink()

        job = {'rid': 'catalog-x', 'params': {'proposal_hash': 'p', 'review_hash': 'r', 'reviewer': 'human', 'identity': None}}
        steps = []
        def update(**fields):
            steps.append(fields)
            remove_lock_after_two_polls()
        result = cj._run_publish(self.root, job, update=update, sleep=clock.sleep, clock=clock.clock)
        self.assertEqual(result['status'], 'deployed')
        self.assertEqual(calls, [1])
        self.assertGreaterEqual(len(clock.calls), 2)
        self.assertTrue(any('Waiting for research' in (s.get('step') or '') for s in steps))

    def test_publish_times_out_after_20_minutes_of_a_held_lock(self):
        (self.root/'.local/research-session.lock').write_text('{}', encoding='utf-8')
        clock = FakeClock()
        job = {'rid': 'catalog-x', 'params': {'proposal_hash': 'p', 'review_hash': 'r', 'reviewer': 'human', 'identity': None}}
        with self.assertRaises(TimeoutError):
            cj._run_publish(self.root, job, update=lambda **f: None, sleep=clock.sleep, clock=clock.clock)
        self.assertGreaterEqual(clock.now, cj.MAX_WAIT_SECONDS)

    def test_validate_never_waits_on_a_lock(self):
        (self.root/'.local/research.lock').write_text('{}', encoding='utf-8')
        import catalog_review
        orig = catalog_review.preview
        catalog_review.preview = lambda root, rid: {'passed': True, 'proposal_hash': 'p'}
        self.addCleanup(setattr, catalog_review, 'preview', orig)
        result = cj.run_job(self.root, {'kind': 'validate', 'rid': 'catalog-x', 'params': {}}, update=lambda **f: None, sleep=lambda s: (_ for _ in ()).throw(AssertionError('validate must not sleep')), clock=time.monotonic)
        self.assertTrue(result['passed'])


class AutoValidateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup); self.root = Path(self.temp.name)

    def package(self, **over):
        base = {'id': 'catalog-' + 'a'*24, 'status': 'pending_review', 'proposal_hash': 'h1', 'validation': None}
        base.update(over); return base

    def test_enqueues_once_for_a_pending_package_missing_validation(self):
        q = cj.Queue(self.root, runner=lambda *a, **k: {}, autostart=False)
        enqueued = cj.auto_validate(self.root, q, [self.package()])
        self.assertEqual(len(enqueued), 1)
        self.assertEqual(enqueued[0]['kind'], 'validate')

    def test_skips_a_package_with_a_passing_validation_for_the_current_hash(self):
        q = cj.Queue(self.root, runner=lambda *a, **k: {}, autostart=False)
        pkg = self.package(validation={'passed': True, 'proposal_hash': 'h1'})
        self.assertEqual(cj.auto_validate(self.root, q, [pkg]), [])

    def test_revalidates_when_the_hash_moves_on_even_with_a_stale_passing_validation(self):
        q = cj.Queue(self.root, runner=lambda *a, **k: {}, autostart=False)
        pkg = self.package(proposal_hash='h2', validation={'passed': True, 'proposal_hash': 'h1'})
        self.assertEqual(len(cj.auto_validate(self.root, q, [pkg])), 1)

    def test_never_enqueues_twice_for_the_same_hash_even_after_a_failed_attempt(self):
        q = cj.Queue(self.root, runner=lambda *a, **k: {}, autostart=False)
        pkg = self.package()
        first = cj.auto_validate(self.root, q, [pkg])
        self.assertEqual(len(first), 1)
        q.jobs[first[0]['id']]['status'] = 'failed'  # finished, unsuccessfully -- still "already tried"
        self.assertEqual(cj.auto_validate(self.root, q, [pkg]), [])

    def test_skips_only_pending_review_packages(self):
        q = cj.Queue(self.root, runner=lambda *a, **k: {}, autostart=False)
        pkg = self.package(status='deferred')
        self.assertEqual(cj.auto_validate(self.root, q, [pkg]), [])

    def test_skips_everything_while_a_research_session_is_active(self):
        (self.root/'.local').mkdir(parents=True)
        (self.root/'.local/research-session.lock').write_text('{}', encoding='utf-8')
        q = cj.Queue(self.root, runner=lambda *a, **k: {}, autostart=False)
        self.assertEqual(cj.auto_validate(self.root, q, [self.package()]), [])


if __name__ == '__main__':
    unittest.main()
