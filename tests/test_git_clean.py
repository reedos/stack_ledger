"""A file rewritten with CRLF and the same content is not a change; a real edit still is."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import atomic_json
import git_clean


def git(root, *args):
    return subprocess.run(['git', *args], cwd=root, capture_output=True, text=True, check=True).stdout


def repo(folder):
    root = Path(folder)
    git(root, 'init', '-q', '-b', 'main')
    git(root, 'config', 'user.email', 't@example.invalid'); git(root, 'config', 'user.name', 't')
    git(root, 'config', 'core.autocrlf', 'true')
    (root / '.gitattributes').write_bytes(b'* text=auto eol=lf\n')
    (root / 'data.json').write_bytes(b'{\n  "a": 1\n}\n')
    (root / 'notes.txt').write_bytes(b'one\ntwo\n')
    git(root, 'add', '-A'); git(root, 'commit', '-q', '-m', 'first')
    return root


class GitClean(unittest.TestCase):
    def test_crlf_rewrite_with_same_content_is_clean(self):
        with tempfile.TemporaryDirectory() as folder:
            root = repo(folder)
            (root / 'data.json').write_bytes(b'{\r\n  "a": 1\r\n}\r\n')
            # The complaint itself: plain status calls it modified though the diff is empty.
            self.assertIn('data.json', git(root, 'status', '--porcelain'))
            self.assertEqual(git_clean.dirty_lines(root), [])
            self.assertEqual(git(root, 'status', '--porcelain'), '')
            self.assertEqual(git(root, 'diff', '--cached', '--name-only'), '')

    def test_real_edit_is_still_reported_and_left_unstaged(self):
        with tempfile.TemporaryDirectory() as folder:
            root = repo(folder)
            (root / 'data.json').write_bytes(b'{\r\n  "a": 1\r\n}\r\n')
            (root / 'notes.txt').write_bytes(b'one\r\nthree\r\n')
            (root / 'new.txt').write_bytes(b'x\n')
            lines = git_clean.dirty_lines(root)
            self.assertEqual(sorted(line[3:] for line in lines), ['new.txt', 'notes.txt'])
            self.assertEqual(git(root, 'diff', '--cached', '--name-only'), '')

    def test_atomic_json_writes_lf_on_every_platform(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'x.json'
            atomic_json.save(path, {'a': [1, 2]})
            self.assertNotIn(b'\r', path.read_bytes())
            self.assertTrue(path.read_bytes().endswith(b'\n'))


if __name__ == '__main__':
    unittest.main()
