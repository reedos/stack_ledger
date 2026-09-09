import contextlib
import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import schedule


class ScheduleTests(unittest.TestCase):
    """schedule.py never calls the real OpenClaw binary here; invoke() is always mocked."""

    def test_preview_schedules_nightly_from_the_reviewed_config(self):
        buf = io.StringIO()
        with patch.object(sys, 'argv', ['schedule.py']), contextlib.redirect_stdout(buf):
            schedule.main()
        payload = json.loads(buf.getvalue())
        config = json.loads((ROOT/'research/runtime.json').read_text(encoding='utf-8'))
        self.assertEqual(payload['argv'], [sys.executable, str(ROOT/'scripts/nightly.py')])
        self.assertEqual(payload['schedule'], config['schedule']); self.assertEqual(payload['schedule'], '30 1 * * *')
        self.assertEqual(payload['timezone'], 'America/Los_Angeles'); self.assertEqual(payload['delivery'], 'none')

    def test_install_uses_the_reviewed_declaration_cron_and_timeout(self):
        calls = []
        def fake_invoke(args):
            calls.append(args)
            if args[:2] == ['cron', 'list']: return {'jobs': []}
            return {'job': {'id': 'job-1', 'name': schedule.NAME, 'enabled': True, 'schedule': {'expr': '30 1 * * *'}}}
        with patch.object(sys, 'argv', ['schedule.py', '--install']), patch.object(schedule, 'invoke', side_effect=fake_invoke), contextlib.redirect_stdout(io.StringIO()):
            schedule.main()
        add_call = next(c for c in calls if c[:2] == ['cron', 'add'])
        self.assertIn('stack-ledger-daily-v2', add_call)
        self.assertIn('--declaration-key', add_call)
        self.assertEqual(add_call[add_call.index('--timeout-seconds')+1], '21600')
        self.assertEqual(add_call[add_call.index('--cron')+1], '30 1 * * *')
        argv = json.loads(add_call[add_call.index('--command-argv')+1])
        self.assertEqual(argv, [sys.executable, str(ROOT/'scripts/nightly.py')])

    def test_editorial_job_is_unchanged_by_the_nightly_switch(self):
        buf = io.StringIO()
        with patch.object(sys, 'argv', ['schedule.py', '--editorial']), contextlib.redirect_stdout(buf):
            schedule.main()
        payload = json.loads(buf.getvalue())
        self.assertIn('editorial_review.py', payload['argv'][1])


if __name__ == '__main__':
    unittest.main()
