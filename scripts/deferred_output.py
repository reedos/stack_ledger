"""Recover only hash-verified, receipts-only output left by an interrupted publisher.

Accepted records, source/excerpt changes, staged edits and unknown files always need maintenance.
Snapshots remain private; recovery never approves or publishes data, nor bypasses preflight.
"""
import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from atomic_json import save
from research_safety import check_storage

DATA_PATHS = {'site/data/ledger.json', 'site/data/coverage.json',
              'docs/data/ledger.json', 'docs/data/coverage.json', 'docs/feed.xml'}


def git(root, *args):
    return subprocess.check_output(['git', *args], cwd=root, stderr=subprocess.PIPE, timeout=60)


def sha(body):
    return hashlib.sha256(body).hexdigest()


def journal_path(root):
    # The working and nightly clones share .local on this machine; keep their checkpoints separate.
    identity = sha(str(root.resolve()).casefold().encode('utf-8'))
    return root / '.local/deferred-output' / (identity + '.json')


def paths(root):
    if git(root, 'diff', '--cached', '--name-only').strip():
        raise ValueError('Staged changes require maintenance')
    if git(root, 'ls-files', '--others', '--exclude-standard').strip():
        raise ValueError('Untracked files require maintenance')
    changed = git(root, 'diff', '--name-only', '-z').decode('utf-8').strip('\0').split('\0')
    changed = [p for p in changed if p]
    for p in changed:
        if not (p in DATA_PATHS or (p.startswith('docs/') and p.endswith('/index.html')) or p == 'docs/index.html'):
            raise ValueError('Non-monitoring changes require maintenance')
        target = root / p
        if not target.resolve().is_relative_to(root.resolve()) or target.is_symlink() or not target.is_file():
            raise ValueError('Unexpected deferred output path')
    return changed


def receipts_only(root):
    before = json.loads(git(root, 'show', 'HEAD:site/data/ledger.json'))
    after = json.loads((root / 'site/data/ledger.json').read_text(encoding='utf-8'))
    if set(before) != set(after) or any(before[k] != after[k] for k in before if k not in {'runs', 'runtime'}):
        raise ValueError('Accepted data changed; retain for maintenance')
    runtime_keys = {'last_attempt', 'last_success', 'status'}
    if {k: v for k, v in before['runtime'].items() if k not in runtime_keys} != \
       {k: v for k, v in after['runtime'].items() if k not in runtime_keys}:
        raise ValueError('Runtime configuration or session summary changed')
    old = {r['id']: r for r in before['runs']}
    for run in after['runs']:
        if run['id'] in old:
            if old[run['id']] != run:
                raise ValueError('Existing receipt changed')
        else:
            rid = run['id']
            if Path(rid).name != rid or '/' in rid or '\\' in rid:
                raise ValueError('Invalid receipt identity')
            retained = json.loads((root / '.local/runs' / (rid + '.json')).read_text(encoding='utf-8'))
            if retained.get('receipt') != run or run.get('accepted') != 0:
                raise ValueError('Unverified or accepted research must be reconciled explicitly')


def record(root):
    """Called by the publisher after its own successful deferred build, under research.lock."""
    root = Path(root)
    try:
        changed = paths(root)
        if not changed:
            return False
        receipts_only(root)
        save(journal_path(root), {'head': git(root, 'rev-parse', 'HEAD').decode().strip(),
                             'at': datetime.now(timezone.utc).isoformat(),
                             'files': {p: sha((root / p).read_bytes()) for p in changed}})
        return True
    except (ValueError, OSError, subprocess.SubprocessError):
        # No approval implied by inability to journal. The normal dirty-tree guard still refuses.
        return False


def recover(root):
    """Snapshot then restore only the exact output checkpoint, before normal sync/preflight."""
    root = Path(root)
    journal = journal_path(root)
    if not journal.exists():
        return {'status': 'held', 'reason': 'No verified deferred-output checkpoint'}
    # Never disturb a writer, including a manual session sharing the private directory.
    from nightly import lock_status
    for name in ('research.lock', 'research-session.lock', 'review-candidates/editorial.lock'):
        lock = root / '.local' / name
        if lock_status(lock)['blocking']:
            return {'status': 'held', 'reason': 'A writer lock is active or unresolved'}
    lock = root / '.local/research.lock'
    try: fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError: return {'status': 'held', 'reason': 'Another writer acquired the research lock'}
    try:
        with os.fdopen(fd, 'w') as handle:
            json.dump({'pid': os.getpid(), 'purpose': 'deferred-output recovery'}, handle)
        return _recover_locked(root, journal)
    finally:
        lock.unlink(missing_ok=True)


def _recover_locked(root, journal):
    check_storage(root)
    value = json.loads(journal.read_text(encoding='utf-8'))
    head = git(root, 'rev-parse', 'HEAD').decode().strip()
    changed = paths(root)
    if value.get('head') != head or set(value.get('files', {})) != set(changed):
        return {'status': 'held', 'reason': 'Checkout differs from deferred-output checkpoint'}
    receipts_only(root)
    bodies = {p: (root / p).read_bytes() for p in changed}
    if any(sha(body) != value['files'][p] for p, body in bodies.items()):
        return {'status': 'held', 'reason': 'Output was edited after checkpoint'}
    destination = root / '.local/recovery' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    for p, body in bodies.items():
        target = destination / 'files' / p
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
        if sha(target.read_bytes()) != value['files'][p]:
            raise OSError('Recovery snapshot verification failed')
    save(destination / 'manifest.json', dict(value, reason='Interrupted receipts-only output; no accepted data changed'))
    # Recheck before modifying tracked files. No force-reset, clean, or deletion of unknown work.
    if paths(root) != changed or any(sha((root / p).read_bytes()) != value['files'][p] for p in changed):
        raise ValueError('Checkout changed during recovery; preserved snapshot, restored nothing')
    git(root, 'restore', '--source=' + head, '--worktree', '--', *changed)
    result = {'status': 'recovered', 'files': len(changed), 'snapshot': str(destination.relative_to(root)),
              'reason': 'Receipts and generated output archived; accepted research unchanged'}
    save(destination / 'result.json', result)
    journal.unlink()
    return result
