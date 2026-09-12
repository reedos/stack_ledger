"""The publish preflight must not race the test suite it runs.

Measured 2026-09-12: the nightly research session ran 97 batches, fetched 345 documents, accepted
one observation and took in 147 new feed entries -- then published none of it. publish() ran
`unittest discover` with timeout=90 and the suite takes 88 seconds on an idle machine. Under the
load of the live session it crossed 90, raised TimeoutExpired, and research_loop checkpointed
"Publication blocked; saved evidence retained", stopping the session 3.4 hours into its 5-hour
window.

A timeout on the preflight suite is there to catch a hung test, not to fail a suite that grew.
"""
import subprocess
import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import research

# 964 tests on an idle machine, 2026-09-12. Two separate runs: 88.0s and 88.2s.
MEASURED_SUITE_SECONDS = 88


class PreflightBudgetTests(unittest.TestCase):
    def test_the_budget_leaves_real_headroom_over_the_suite_it_runs(self):
        self.assertGreaterEqual(
            research.PREFLIGHT_TEST_TIMEOUT_SECONDS, MEASURED_SUITE_SECONDS*4,
            'the suite takes %ds idle and the preflight runs it under load; a budget of %ds is the '
            'kind of margin that published nothing on 2026-09-12'
            % (MEASURED_SUITE_SECONDS, research.PREFLIGHT_TEST_TIMEOUT_SECONDS))

    def test_publish_uses_the_named_budget_rather_than_a_literal(self):
        """A literal here is how the old 90 survived the suite growing past it unnoticed."""
        source = (ROOT/'scripts/research.py').read_text(encoding='utf-8')
        line = next(l for l in source.splitlines() if "'unittest','discover'" in l and 'subprocess.run' in l)
        self.assertIn('timeout=PREFLIGHT_TEST_TIMEOUT_SECONDS', line, line.strip())

    def test_no_other_preflight_step_carries_a_tighter_budget_than_the_suite(self):
        """git and the suite share the preflight; whichever is tightest decides the night."""
        source = (ROOT/'scripts/research.py').read_text(encoding='utf-8')
        import re
        for timeout in (int(m) for m in re.findall(r'subprocess\.run\([^)]*timeout=(\d+)', source)):
            self.assertGreaterEqual(timeout, MEASURED_SUITE_SECONDS,
                                    'a preflight step budgeted %ds sits inside a publish that '
                                    'needs %ds for the suite alone' % (timeout, MEASURED_SUITE_SECONDS))


if __name__ == '__main__':
    unittest.main()
