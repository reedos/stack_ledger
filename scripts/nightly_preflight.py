"""Read-only readiness check, suitable for a separate 01:00 Pacific invocation.

Prints JSON and exits 1 for maintenance, 0 for ready. Never fetches, stages,
recovers locks/output, starts inference, publishes, or installs a schedule.
Remote comparisons use the last fetched origin ref, not live remote state.
"""
import argparse
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCKS = ('research.lock', 'research-session.lock', 'review-candidates/editorial.lock')


def git(root, *args):
    return subprocess.check_output(['git', '--no-optional-locks', *args], cwd=root,
                                   stderr=subprocess.PIPE, timeout=60).decode('utf-8')


def inspect(root):
    root = Path(root)
    issues = []
    result = {'status': 'ready', 'issues': issues, 'remote_basis': 'last fetched origin ref; no network check'}
    try:
        # Diff ignores size-only/CRLF phantoms without refreshing or staging the index.
        unstaged = set(filter(None, git(root, 'diff', '--name-only', '-z').split('\0')))
        staged = set(filter(None, git(root, 'diff', '--cached', '--name-only', '-z').split('\0')))
        untracked = set(filter(None, git(root, 'ls-files', '--others', '--exclude-standard', '-z').split('\0')))
        dirty = sorted(unstaged | staged | untracked)
        result['dirty_paths'] = dirty
        result['dirty_count'] = len(dirty)
        if dirty: issues.append('Working tree has real local changes; resolve before the nightly start')
        from deferred_output import DATA_PATHS
        generated = sorted(p for p in unstaged if p in DATA_PATHS or p == 'docs/index.html'
                           or (p.startswith('docs/') and p.endswith('/index.html')))
        result['deferred_output'] = {'candidate_count': len(generated),
            'reason': 'Possible deferred receipts/build output; path shape alone does not prove safe recovery'}
        if generated: issues.append(f'{len(generated)} deferred-output candidate paths remain; inspect final publication receipts')
        config = root/'research/runtime.json'
        branch = json.loads(config.read_text(encoding='utf-8')).get('branch', 'main') if config.exists() else 'main'
        actual = git(root, 'branch', '--show-current').strip()
        if actual != branch: issues.append('Unexpected branch; nightly publication requires '+branch)
        ahead, behind = map(int, git(root, 'rev-list', '--left-right', '--count', 'HEAD...origin/'+branch).split())
        result.update(ahead=ahead, behind=behind)
        if ahead: issues.append(f'{ahead} unpushed local commit(s); review ownership before publication')
        if behind: issues.append(f'{behind} remote commit(s) require synchronization')
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        issues.append('Repository readiness could not be verified: '+type(error).__name__)
    # Presence is conservative: even stale/unreadable locks need the maintained
    # recovery path. A preflight must never unlink them or race the nightly job.
    result['locks_present'] = [name for name in LOCKS if (root/'.local'/name).exists()]
    if result['locks_present']: issues.append('Writer lock(s) present: '+', '.join(result['locks_present']))
    if (root/'.local/stop-research-loop').exists(): issues.append('Research stop flag is present')
    if issues: result['status'] = 'blocked'
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    args = parser.parse_args(argv)
    result = inspect(args.root)
    print(json.dumps(result, indent=2))
    return int(result['status'] != 'ready')


if __name__ == '__main__':
    raise SystemExit(main())
