"""All repository mutations are confined to synthetic, throwaway repositories."""
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import nightly_preflight as preflight
import nightly
import research
import research_loop as loop
import research_notify
import session_receipt


class ReadinessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.git('init', '-q', '-b', 'main')
        self.git('config', 'user.name', 'Synthetic Test')
        self.git('config', 'user.email', 'test@example.invalid')
        self.git('config', 'core.autocrlf', 'false')
        self.write('.gitignore', '.local/\n')
        self.write('.gitattributes', '* text=auto eol=lf\n')
        self.write('notes.txt', 'one\ntwo\n')
        self.write('research/runtime.json', '{}')
        for i in range(129): self.write(f'docs/page-{i}/index.html', 'original\n')
        self.git('add', '.')
        self.git('commit', '-qm', 'baseline')
        self.git('update-ref', 'refs/remotes/origin/main', 'HEAD')

    def git(self, *args):
        return subprocess.check_output(['git', *args], cwd=self.root, stderr=subprocess.PIPE)

    def write(self, name, body):
        path = self.root/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body.encode())

    def test_clean_and_crlf_phantom_are_ready_without_index_mutation(self):
        self.assertEqual(preflight.inspect(self.root)['status'], 'ready')
        self.write('notes.txt', 'one\r\ntwo\r\n')
        before = (self.root/'.git/index').read_bytes()
        self.assertEqual(preflight.inspect(self.root)['status'], 'ready')
        self.assertEqual((self.root/'.git/index').read_bytes(), before)
        self.assertEqual((self.root/'notes.txt').read_bytes(), b'one\r\ntwo\r\n')

    def test_dirty_and_staged_and_untracked_work_block_without_cleanup(self):
        self.write('notes.txt', 'human edit\n')
        self.git('add', 'notes.txt')
        self.write('new file.txt', 'untracked\n')
        before = self.git('diff', '--cached')
        result = preflight.inspect(self.root)
        self.assertEqual(result['status'], 'blocked')
        self.assertEqual(result['dirty_paths'], ['new file.txt', 'notes.txt'])
        self.assertEqual(self.git('diff', '--cached'), before)
        with patch('sys.stdout', new=io.StringIO()):
            self.assertEqual(preflight.main(['--root', str(self.root)]), 1)

    def test_foreign_local_commit_blocks_without_push(self):
        self.git('commit', '--allow-empty', '-qm', 'unrelated operator work')
        result = preflight.inspect(self.root)
        self.assertEqual(result['ahead'], 1)
        self.assertEqual(result['status'], 'blocked')
        # The actual nightly gate must also refuse the unrelated commit.
        self.assertFalse(nightly.push_own_commits(self.root)['pushed'])
        self.assertEqual(self.git('rev-list', '--count', 'origin/main..HEAD').strip(), b'1')

    def test_real_dirty_and_foreign_commit_preflights_exit_three_with_specific_reason(self):
        self.write('research/runtime.json', json.dumps({'branch':'main', 'repository':'example/synthetic'}))
        self.git('add', '.')
        self.git('commit', '-qm', 'synthetic configuration')
        self.git('update-ref', 'refs/remotes/origin/main', 'HEAD')
        original_git = research.git
        def offline_git(*args):
            if args[:2] == ('remote', 'get-url'): return 'https://github.com/example/synthetic'
            if args[0] == 'fetch': return ''
            return original_git(*args)
        for mode, expected in [('dirty', 'unapproved change: notes.txt'), ('commit', 'unrelated local commit')]:
            with self.subTest(mode=mode):
                if mode == 'dirty': self.write('notes.txt', 'operator change\n')
                else:
                    self.git('add', 'notes.txt')
                    self.git('commit', '-qm', 'operator work')
                sid = 'a'*32
                with patch.object(research, 'ROOT', self.root), patch.object(research, 'LOCAL', self.root/'.local'), \
                     patch.object(research, 'git', side_effect=offline_git), patch.object(research.Fetcher, 'fetch') as fetch, \
                     patch.object(sys, 'argv', ['research.py', '--publish', '--session-id', sid]), \
                     patch('sys.stderr', new=io.StringIO()):
                    self.assertEqual(research.main(), 3)
                    fetch.assert_not_called()
                saved = json.loads((self.root/'.local/sessions'/sid/'publication-error.json').read_text())
                self.assertIn(expected, saved['reason'])

    def test_held_lock_fails_nightly_and_session_without_touching_owner_status(self):
        for name in ('research.lock', 'research-session.lock'):
            with self.subTest(lock=name):
                self.write('.local/'+name, json.dumps({'pid': os.getpid()}))
                self.write('.local/session-status.json', '{"state":"researching"}')
                self.assertEqual(preflight.inspect(self.root)['locks_present'], [name])
                with patch.object(loop, 'ROOT', self.root), patch.object(loop, 'overnight_seconds', return_value=60), \
                     patch.object(loop, 'overlap_notice'), patch.object(loop.subprocess, 'Popen') as spawn, \
                     patch('sys.stdout', new=io.StringIO()):
                    self.assertEqual(loop.main(['--start', '--overnight']), 1)
                    spawn.assert_not_called()
                with patch.object(nightly, 'wait_for_window') as wait:
                    self.assertEqual(nightly.stage_research(self.root, 600)['status'], 'failed')
                    wait.assert_not_called()
                self.assertTrue((self.root/'.local'/name).exists())
                self.assertEqual(json.loads((self.root/'.local/session-status.json').read_text())['state'], 'researching')
                (self.root/'.local'/name).unlink()
        statuses = list((self.root/'.local/sessions').glob('*/status.json'))
        self.assertEqual(len(statuses), 2)
        self.assertTrue(all(json.loads(p.read_text())['state']=='blocked' for p in statuses))

    def test_129_generated_leftovers_are_reported_and_preserved(self):
        for i in range(129): self.write(f'docs/page-{i}/index.html', 'updated receipt footer\n')
        before = self.git('diff')
        result = preflight.inspect(self.root)
        self.assertEqual(result['dirty_count'], 129)
        self.assertEqual(result['deferred_output']['candidate_count'], 129)
        self.assertEqual(result['status'], 'blocked')
        self.assertEqual(self.git('diff'), before)

    def test_final_publication_failure_cannot_return_success(self):
        # A real finalize() preflight failure after a successful synthetic batch.
        clock = [0]
        def sleep(seconds): clock[0] += seconds
        def spawn(*args, **kwargs):
            sid = args[0][args[0].index('--session-id')+1]
            self.write(f'.local/sessions/{sid}/batches/batch.json', json.dumps({'monitoring':{}, 'publication':'deferred'}))
            self.write('docs/page-0/index.html', 'deferred output\n')
            child = Mock(returncode=0)
            child.poll.return_value = 0
            return child
        with patch.object(loop, 'ROOT', self.root), patch.object(research, 'ROOT', self.root), \
             patch.object(research, 'LOCAL', self.root/'.local'), \
             patch.object(loop.time, 'monotonic', side_effect=lambda: clock[0]), patch.object(loop.time, 'sleep', side_effect=sleep), \
             patch.object(loop.subprocess, 'Popen', side_effect=spawn), \
             patch.object(research, 'preflight', side_effect=ValueError('unrelated local commit')), \
             patch.object(research, 'publish') as publish, patch('visual_review.finish_session'), \
             patch.dict(os.environ, {'STACK_LEDGER_COMBINED_BRIEF':'1'}), patch('sys.stdout', new=io.StringIO()):
            self.assertEqual(loop.main(['--start', '--publish', '--minutes', '1', '--max-cycles', '1', '--min-minutes', '0', '--ignore-gpu-busy']), 1)
            publish.assert_not_called()
        status = json.loads((self.root/'.local/session-status.json').read_text())
        self.assertEqual(status['state'], 'blocked')
        self.assertIn('unrelated local commit', status['failure_reason'])
        self.assertEqual(status['session_summary_publication'], 'failed')
        self.assertEqual((self.root/'docs/page-0/index.html').read_text(), 'deferred output\n')

    @contextlib.contextmanager
    def _run_one_batch_session(self):
        clock = [0]
        def sleep(seconds): clock[0] += seconds
        def spawn(*args, **kwargs):
            sid = args[0][args[0].index('--session-id')+1]
            self.write(f'.local/sessions/{sid}/batches/batch.json', json.dumps({'monitoring':{}, 'publication':'deferred'}))
            child = Mock(returncode=0)
            child.poll.return_value = 0
            return child
        with patch.object(loop, 'ROOT', self.root), patch.object(research, 'ROOT', self.root),              patch.object(research, 'LOCAL', self.root/'.local'),              patch.object(loop.time, 'monotonic', side_effect=lambda: clock[0]), patch.object(loop.time, 'sleep', side_effect=sleep),              patch.object(loop.subprocess, 'Popen', side_effect=spawn),              patch('visual_review.finish_session'),              patch.dict(os.environ, {'STACK_LEDGER_COMBINED_BRIEF':'1'}), patch('sys.stdout', new=io.StringIO()):
            yield

    def test_raised_finalizer_error_cannot_return_success(self):
        # Reviewer reproduction: finalize() raises (not returns failed) after a good batch.
        error = OSError('synthetic disk full while recording publication receipt')
        with patch('session_receipt.finalize', side_effect=error):
            with self._run_one_batch_session():
                code = loop.main(['--start', '--publish', '--minutes', '1', '--max-cycles', '1', '--min-minutes', '0', '--ignore-gpu-busy'])
        status = json.loads((self.root/'.local/session-status.json').read_text())
        self.assertEqual(code, 1)
        self.assertEqual(status['state'], 'blocked')
        self.assertEqual(status['session_summary_publication'], 'failed')
        self.assertIn('synthetic disk full', status['failure_reason'])

    def test_raised_summary_write_error_cannot_return_success(self):
        error = OSError('synthetic disk full while writing summary')
        with patch.object(research_notify, 'summary', side_effect=error):
            with self._run_one_batch_session():
                code = loop.main(['--start', '--publish', '--minutes', '1', '--max-cycles', '1', '--min-minutes', '0', '--ignore-gpu-busy'])
        status = json.loads((self.root/'.local/session-status.json').read_text())
        self.assertEqual(code, 1)
        self.assertEqual(status['state'], 'blocked')
        self.assertIn('synthetic disk full', status['failure_reason'])

    def test_batch_publication_failure_stops_once_and_retains_concrete_reason(self):
        def spawn(command, **kwargs):
            sid = command[command.index('--session-id')+1]
            self.write(f'.local/sessions/{sid}/publication-error.json', json.dumps({'reason':'Working tree has unapproved change: notes.txt'}))
            child = Mock(returncode=3)
            child.poll.return_value = 3
            return child
        with patch.object(loop, 'ROOT', self.root), patch.object(loop.subprocess, 'Popen', side_effect=spawn) as child, \
             patch.object(research_notify, 'notify_session', return_value={'status':'disabled'}), \
             patch('visual_review.finish_session'), patch('sys.stdout', new=io.StringIO()):
            self.assertEqual(loop.main(['--start', '--publish', '--minutes', '360', '--ignore-gpu-busy']), 1)
            child.assert_called_once()
        status = json.loads((self.root/'.local/session-status.json').read_text())
        self.assertEqual(status['state'], 'blocked')
        self.assertEqual(status['failure_reason'], 'Working tree has unapproved change: notes.txt')

    def test_successful_finalization_preserves_published_elapsed_counter(self):
        clock = [0]
        published = []
        def notify(root, report, folder):
            published.append(report['elapsed_seconds'])
            clock[0] += 40
            report['session_summary_publication'] = 'pushed'
            return {'status':'disabled'}
        child = Mock(returncode=0)
        child.poll.return_value = 0
        with patch.object(loop, 'ROOT', self.root), patch.object(loop.subprocess, 'Popen', return_value=child), \
             patch.object(loop.time, 'monotonic', side_effect=lambda: clock[0]), \
             patch.object(loop.time, 'sleep', side_effect=lambda seconds: clock.__setitem__(0, clock[0]+seconds)), \
             patch.object(research_notify, 'notify_session', side_effect=notify), \
             patch('visual_review.finish_session'), patch('sys.stdout', new=io.StringIO()):
            self.assertEqual(loop.main(['--start', '--publish', '--minutes', '1', '--max-cycles', '1', '--min-minutes', '0', '--ignore-gpu-busy']), 0)
        status = json.loads((self.root/'.local/session-status.json').read_text())
        self.assertEqual(status['elapsed_seconds'], published[0])
        self.assertEqual(status['session_summary_publication'], 'pushed')


if __name__ == '__main__': unittest.main()
