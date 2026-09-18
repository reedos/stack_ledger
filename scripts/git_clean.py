"""Is this working tree really dirty?

`git status` calls a tracked file modified on its size alone, before it compares content. A file
rewritten with Windows line endings and the same content (`* text=auto eol=lf` makes the blob LF,
a text-mode write on Windows makes the file CRLF) therefore reads as ' M' while `git diff` is
empty. On 2026-09-18 that stopped the night at its sync stage: the run before had rewritten
excerpts.json unchanged, nothing staged it, and the night clone looked touched.

dirty_lines() re-stages such paths - the same blob, a fresh stat - and returns what is left.
It never stages a path whose content differs, so it cannot hide or absorb real work.
"""
import subprocess


def _git(root, *args, timeout=60):
    r = subprocess.run(['git', *args], cwd=root, capture_output=True, text=True, encoding='utf-8', timeout=timeout)
    return r.returncode, r.stdout or '', (r.stderr or '').strip()


def _status(root):
    code, out, err = _git(root, 'status', '--porcelain')
    if code != 0:
        raise RuntimeError(f'git status: {err[-300:]}')
    return [line for line in out.splitlines() if line.strip()]


def dirty_lines(root):
    """Porcelain lines for real changes only; size-only phantoms are settled on the way."""
    lines = _status(root)
    unstaged = [line[3:].strip().strip('"') for line in lines if line[:2] == ' M']
    same = [path for path in unstaged if _git(root, 'diff', '--quiet', '--', path)[0] == 0]
    if not same:
        return lines
    _git(root, 'add', '--', *same)
    return _status(root)
