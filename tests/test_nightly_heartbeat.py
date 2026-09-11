"""The nightly job must never go silent, because its supervisor treats silence as death.

The OpenClaw cron entry that runs scripts/nightly.py carries noOutputTimeoutSeconds 420 and
re-arms that timer only on this process's own stdout/stderr; on Windows it then issues
taskkill /PID <pid> /T /F against the whole tree. Every stage captures its children's output, so
the process itself printed nothing outside --dry-run and survived only because the research stage
kept returning in under a second. Once wait_for_window began holding 01:30 to 02:00, and the
research session its own hours, the first genuinely working night would have been killed at
01:37 with no research, no digest and no message.

These tests restate that failure directly: while a stage is running and silent, stdout must still
receive a line, and comfortably inside the supervisor's limit.
"""
import io
import json
import os
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import nightly


class HeartbeatTests(unittest.TestCase):
    def test_a_long_silent_stage_still_produces_output(self):
        stage = {'name': 'research'}
        stop = threading.Event()
        out = io.StringIO()
        with redirect_stdout(out):
            thread = threading.Thread(target=nightly.heartbeat, args=(stage, stop, 0.02), daemon=True)
            thread.start()
            time.sleep(0.25)
            stop.set()
            thread.join(timeout=5)
        lines = [l for l in out.getvalue().splitlines() if l.strip()]
        self.assertGreaterEqual(len(lines), 3, 'a silent stage produced no heartbeat: %r' % lines)
        for line in lines:
            self.assertIn('nightly: research', line)
            self.assertRegex(line, r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}')

    def test_the_heartbeat_names_the_stage_currently_running(self):
        stage = {'name': 'importers'}
        stop = threading.Event()
        out = io.StringIO()
        with redirect_stdout(out):
            thread = threading.Thread(target=nightly.heartbeat, args=(stage, stop, 0.02), daemon=True)
            thread.start()
            time.sleep(0.08)
            stage['name'] = 'research'
            time.sleep(0.12)
            stop.set()
            thread.join(timeout=5)
        text = out.getvalue()
        self.assertIn('nightly: importers', text)
        self.assertIn('nightly: research', text)

    def test_it_stops_when_asked(self):
        stage = {'name': 'digest'}
        stop = threading.Event()
        out = io.StringIO()
        with redirect_stdout(out):
            thread = threading.Thread(target=nightly.heartbeat, args=(stage, stop, 0.02), daemon=True)
            thread.start()
            time.sleep(0.06)
            stop.set()
            thread.join(timeout=5)
            settled = out.getvalue()
            time.sleep(0.1)
        self.assertEqual(out.getvalue(), settled, 'the heartbeat kept printing after it was stopped')


class MarginTests(unittest.TestCase):
    """The interval is only correct relative to what the installed job actually allows."""
    def installed_no_output_timeout(self):
        state = Path(os.path.expanduser('~/.openclaw/state/openclaw.sqlite'))
        if not state.exists():
            return None
        con = sqlite3.connect(state.as_uri()+'?mode=ro', uri=True)
        try:
            rows = con.execute('select payload_message from cron_jobs').fetchall()
        except sqlite3.Error:
            return None
        finally:
            con.close()
        for (payload,) in rows:
            if not payload or 'nightly.py' not in payload:
                continue
            try:
                seconds = json.loads(payload).get('noOutputTimeoutSeconds')
            except ValueError:
                continue
            if isinstance(seconds, (int, float)):
                return float(seconds)
        return None

    def test_the_interval_leaves_real_margin_under_the_installed_limit(self):
        limit = self.installed_no_output_timeout()
        if limit is None:
            self.skipTest('the nightly cron job is not installed on this machine')
        self.assertLess(nightly.HEARTBEAT_SECONDS*3, limit,
                        'HEARTBEAT_SECONDS %s leaves too little margin under the job\'s %s s limit'
                        % (nightly.HEARTBEAT_SECONDS, limit))


class WiringTests(unittest.TestCase):
    """A heartbeat nothing starts is worth nothing, so this drives the real run() instead of
    reading the source: a stage that is busy and silent must still keep stdout alive.

    run() is given a throwaway root, never the repository. Pointed at the real one it performs
    real lock recovery and overwrites .local/nightly/<date>/locks.json -- and the publish preflight
    runs this suite, so on 2026-09-11 the nightly run's own locks receipt was replaced at 07:01 by
    a test, six hours after the stage it was supposed to describe.
    """
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root/'.local').mkdir()

    def slow_locks(self, root):
        time.sleep(0.4)
        return {'status': 'ok', 'locks': [], 'research_blocked': False,
                'editorial_blocked': False, 'stop_research_present': False}

    def test_run_keeps_printing_through_a_silent_stage(self):
        out = io.StringIO()
        with patch.object(nightly, 'HEARTBEAT_SECONDS', 0.05), \
             patch.object(nightly, 'stage_locks', self.slow_locks), redirect_stdout(out):
            nightly.run(self.root, only='locks')
        lines = [l for l in out.getvalue().splitlines() if l.strip()]
        self.assertGreaterEqual(len(lines), 4, 'run() went silent during a busy stage: %r' % lines)
        self.assertTrue(any('nightly: locks' in l for l in lines),
                        'the heartbeat never named the stage that was running: %r' % lines)

    def test_the_run_announces_itself_before_doing_anything(self):
        out = io.StringIO()
        with patch.object(nightly, 'stage_locks', lambda root: {
                'status': 'ok', 'locks': [], 'research_blocked': False,
                'editorial_blocked': False, 'stop_research_present': False}), redirect_stdout(out):
            nightly.run(self.root, only='locks')
        first = out.getvalue().splitlines()[0]
        self.assertIn('nightly: started', first)

    def test_the_heartbeat_is_stopped_when_the_night_ends(self):
        out = io.StringIO()
        with patch.object(nightly, 'HEARTBEAT_SECONDS', 0.05), \
             patch.object(nightly, 'stage_locks', self.slow_locks), redirect_stdout(out):
            nightly.run(self.root, only='locks')
            settled = out.getvalue()
            time.sleep(0.25)
            self.assertEqual(out.getvalue(), settled,
                             'the heartbeat outlived the run and would print into the next job')


if __name__ == '__main__':
    unittest.main()
