"""Background job queue for catalog validate/publish work.

The owner reviews on a phone: validation and publication used to make them wait (or refuse instantly
when a research batch held the lock). One FIFO worker thread per running panel runs `validate(rid)`
(`catalog_review.preview`) and `publish(rid)` (`catalog_review.apply_publish`, which itself calls
`publish_package`) exactly as the routes always have. Validation runs any time; a publish job instead
polls for `.local/research.lock` / `.local/research-session.lock` to clear (every 10s, up to 20 minutes)
rather than failing the tap. Job state lives in memory and is mirrored to `.local/catalog-jobs.json`
after every change, so a panel restart can still show the last known state -- a job recorded as still
queued/running there could not actually have survived the restart, so it is loaded as failed.
"""
import threading
import time
import uuid
from collections import deque
from datetime import datetime, timedelta, timezone
from pathlib import Path

from atomic_json import save

POLL_SECONDS = 10
MAX_WAIT_SECONDS = 20*60
RETAIN_HOURS = 24
KINDS = ('validate', 'publish')
STATUSES = ('queued', 'running', 'done', 'failed')


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


def _path(root):
    return root/'.local/catalog-jobs.json'


def read_all(root):
    """Pure disk read: every retained job, oldest first. Never raises."""
    import json
    try:
        rows = json.loads(_path(root).read_text(encoding='utf-8'))
        return rows if isinstance(rows, list) else []
    except (OSError, ValueError):
        return []


def read_recent(root, hours=RETAIN_HOURS):
    """All jobs from the last `hours`, plus any still queued/running regardless of age."""
    cutoff = (datetime.now(timezone.utc)-timedelta(hours=hours)).isoformat(timespec='seconds').replace('+00:00', 'Z')
    return [j for j in read_all(root) if j.get('created_at', '') >= cutoff or j.get('status') in ('queued', 'running')]


def read_latest(root, rid):
    """The most recently created job for this package (any kind), or None."""
    candidates = [j for j in read_all(root) if j.get('rid') == rid]
    return max(candidates, key=lambda j: j.get('created_at', '')) if candidates else None


def _locks_present(root):
    return (root/'.local/research.lock').exists() or (root/'.local/research-session.lock').exists()


def _run_publish(root, job, *, update, sleep, clock):
    import catalog_review as cr
    params = job['params']
    deadline = clock()+MAX_WAIT_SECONDS
    while True:
        if _locks_present(root):
            if clock() >= deadline:
                raise TimeoutError('Research or a publication lock did not clear within 20 minutes; try again once it finishes')
            update(step='Waiting for research to finish…')
            sleep(POLL_SECONDS)
            continue
        update(step='Publishing: validating, building, committing and pushing…')
        try:
            return cr.apply_publish(root, job['rid'], params['proposal_hash'], params['review_hash'],
                                     params['reviewer'], True, params.get('identity'))
        except FileExistsError:
            if clock() >= deadline: raise TimeoutError('Research or a publication lock did not clear within 20 minutes; try again once it finishes')
            update(step='Waiting for research to finish…')
            sleep(POLL_SECONDS)
        except ValueError as e:
            if 'Research session active' in str(e) and clock() < deadline:
                update(step='Waiting for research to finish…')
                sleep(POLL_SECONDS)
                continue
            raise


def run_job(root, job, *, update, sleep, clock):
    """The body of one job. Overridable per-Queue (tests inject a fake) for exactly this reason."""
    import catalog_review as cr
    if job['kind'] == 'validate':
        update(step='Building and testing the isolated preview…')
        return cr.preview(root, job['rid'])
    if job['kind'] == 'publish':
        return _run_publish(root, job, update=update, sleep=sleep, clock=clock)
    raise ValueError('Unknown job kind: '+job['kind'])


class Queue:
    """One instance per running panel server; owns the single FIFO worker thread."""
    def __init__(self, root, *, runner=None, sleep=time.sleep, clock=time.monotonic, autostart=True):
        self.root = root
        self.guard = threading.Lock()
        self.wake = threading.Condition(self.guard)
        self.pending = deque()
        self.jobs = {}
        self.sleep = sleep
        self.clock = clock
        self.runner = runner or run_job
        self.stopped = False
        self._recover_from_disk()
        self.worker = None
        if autostart:
            self.worker = threading.Thread(target=self._loop, daemon=True)
            self.worker.start()

    def _recover_from_disk(self):
        for row in read_all(self.root):
            if row.get('status') in ('queued', 'running'):
                row = dict(row, status='failed', step='Failed', error='Panel restarted before this job finished', finished_at=now())
            self.jobs[row['id']] = row
        self._save()

    def _save(self):
        cutoff = (datetime.now(timezone.utc)-timedelta(hours=RETAIN_HOURS)).isoformat(timespec='seconds').replace('+00:00', 'Z')
        kept = [j for j in self.jobs.values() if j.get('created_at', '') >= cutoff or j.get('status') in ('queued', 'running')]
        kept.sort(key=lambda j: j.get('created_at', ''))
        save(_path(self.root), kept)

    def enqueue(self, kind, rid, **params):
        """Return the existing queued/running job for (rid, kind) instead of duplicating it."""
        if kind not in KINDS: raise ValueError('Unknown job kind: '+kind)
        with self.guard:
            existing = next((j for j in self.jobs.values()
                              if j['rid'] == rid and j['kind'] == kind and j['status'] in ('queued', 'running')), None)
            if existing: return dict(existing)
            job = {'id': 'job-'+uuid.uuid4().hex[:24], 'rid': rid, 'kind': kind, 'status': 'queued',
                   'step': 'Waiting in queue…', 'created_at': now(), 'started_at': None, 'finished_at': None,
                   'error': None, 'result': None, 'params': params}
            self.jobs[job['id']] = job
            self.pending.append(job['id'])
            self._save()
            self.wake.notify()
            return dict(job)

    def _update(self, job_id, **fields):
        with self.guard:
            self.jobs[job_id].update(fields)
            self._save()

    def _loop(self):
        while True:
            with self.guard:
                while not self.pending and not self.stopped:
                    self.wake.wait()
                if self.stopped and not self.pending: return
                job_id = self.pending.popleft()
            self._update(job_id, status='running', started_at=now(), step='Starting…')
            job = dict(self.jobs[job_id])
            try:
                result = self.runner(self.root, job, update=lambda **f: self._update(job_id, **f), sleep=self.sleep, clock=self.clock)
                summary = result if isinstance(result, dict) else {'value': result}
                self._update(job_id, status='done', finished_at=now(), step='Done', result=summary)
            except Exception as e:
                self._update(job_id, status='failed', finished_at=now(), step='Failed', error=(str(e) or type(e).__name__)[:600])

    def close(self, timeout=15):
        """Stop the worker and WAIT for it. A caller that tears down the root directory needs the
        writes to have stopped, not merely been asked to: the panel tests delete a temporary tree
        in tearDown, and a worker still saving job state raced them into "Directory not empty" on
        roughly half of CI runs (2026-09-11)."""
        with self.guard:
            self.stopped = True
            self.wake.notify_all()
        worker = self.worker
        if worker and worker is not threading.current_thread():
            worker.join(timeout)


def auto_validate(root, queue, packages):
    """Enqueue validate(rid) once per package hash for a pending_review package whose validation is
    missing or stale. Skipped while a research session is active. The worker is single-threaded, so
    this can never cause more than one validation to run at once regardless of how many are queued."""
    if (root/'.local/research-session.lock').exists(): return []
    enqueued = []
    for p in packages:
        if p.get('status') != 'pending_review': continue
        v = p.get('validation')
        if v and v.get('passed') and v.get('proposal_hash') == p.get('proposal_hash'): continue
        already_tried = any(j['kind'] == 'validate' and j['rid'] == p['id']
                             and j.get('params', {}).get('proposal_hash') == p.get('proposal_hash')
                             for j in queue.jobs.values())
        if already_tried: continue
        enqueued.append(queue.enqueue('validate', p['id'], proposal_hash=p.get('proposal_hash')))
    return enqueued
