"""Every page type must render at desktop width, not only on a phone.

The desktop site fell back to "Interactive research could not be loaded" on every chart page from
the slot-axis refactor (6103b1aae) until 538c8441b -- chart() read `years.length` after `years`
had been removed, behind a `narrow||` that a phone short-circuits. A day of phone checks passed,
CI validates data rather than executing the page, and the node tests extract expression slices
instead of running it. Nothing exercised the branch the owner does not use.

tests/page_render.cjs loads the page's scripts in the order docs/index.html does, into a stubbed
DOM, and drives the real promise chain against the published datasets at 1280px and 390px.
"""
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which('node'), 'node is not installed')
class PageRenderTests(unittest.TestCase):
    def test_every_page_renders_at_both_widths(self):
        result = subprocess.run(['node', '--test', 'tests/page_render.cjs'], cwd=ROOT,
                                capture_output=True, text=True, encoding='utf-8', errors='replace')
        self.assertEqual(result.returncode, 0, (result.stdout + result.stderr)[-4000:])

    def test_the_harness_covers_the_desktop_branch(self):
        """The whole point: the width a phone never reaches must be in the matrix."""
        source = (ROOT/'tests/page_render.cjs').read_text(encoding='utf-8')
        self.assertIn('1280', source)
        self.assertIn("'desktop'", source)

    def test_the_regression_itself_stays_fixed(self):
        """`years` is not declared in chart(); any read of it is the same crash."""
        app = (ROOT/'site/assets/app.js').read_text(encoding='utf-8')
        start = app.index('function chart(')
        end = app.index('\nfunction ', start+1)
        body = app[start:end]
        self.assertNotRegex(body, r'\byears\.', 'chart() reads a `years` variable it no longer declares')


if __name__ == '__main__':
    unittest.main()
