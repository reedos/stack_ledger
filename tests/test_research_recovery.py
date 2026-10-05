import copy
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import deferred_output as recovery
import research_safety as safety
import nightly
import research_loop as loop
import research_control as control
import discovery


class DeferredRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        def git(*args): return recovery.git(self.root, *args)
        self.git = git
        git('init', '-q'); git('config', 'user.name', 'Test'); git('config', 'user.email', 'test@example.invalid')
        self.write('.gitignore', '.local/\n')
        self.before = {'runtime': {'model': 'fixed', 'status': 'success'}, 'runs': [], 'observations': []}
        self.write('site/data/ledger.json', self.before)
        self.write('docs/index.html', 'original')
        git('add', '.'); git('commit', '-qm', 'baseline')
        self.run = {'id': 'run-test', 'accepted': 0}
        after = dict(self.before, runs=[self.run], runtime=dict(self.before['runtime'], last_attempt='now'))
        self.write('site/data/ledger.json', after)
        self.write('docs/index.html', 'generated')
        self.write('.local/runs/run-test.json', {'receipt': self.run})

    def write(self, p, value):
        path = self.root / p; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value) if isinstance(value, dict) else value, encoding='utf-8')

    def test_receipts_only_interruption_is_archived_and_clean_for_sync(self):
        self.assertTrue(recovery.record(self.root))
        result = recovery.recover(self.root)
        self.assertEqual(result['status'], 'recovered')
        self.assertEqual(self.git('status', '--porcelain').strip(), b'')
        archive = self.root / result['snapshot']
        self.assertEqual((archive / 'files/docs/index.html').read_text(), 'generated')
        self.assertEqual(json.loads((archive / 'files/site/data/ledger.json').read_text())['runs'], [self.run])
        self.assertTrue((self.root / '.local/runs/run-test.json').exists())
        self.assertFalse((self.root / '.local/research.lock').exists())

    def test_unknown_edits_and_staged_work_are_never_restored(self):
        self.assertTrue(recovery.record(self.root))
        self.write('docs/index.html', 'human change after build')
        self.assertEqual(recovery.recover(self.root)['status'], 'held')
        self.assertEqual((self.root / 'docs/index.html').read_text(), 'human change after build')
        self.git('add', 'docs/index.html')
        with self.assertRaises(ValueError): recovery.recover(self.root)

    def test_changed_accepted_data_cannot_be_checkpointed(self):
        after = copy.deepcopy(self.before); after['observations'].append({'id': 'new-data'})
        self.write('site/data/ledger.json', after)
        self.assertFalse(recovery.record(self.root))
        self.assertEqual(recovery.recover(self.root)['status'], 'held')

    def test_live_writer_prevents_recovery(self):
        recovery.record(self.root)
        self.write('.local/research-session.lock', {'pid': os.getpid()})
        self.assertEqual(recovery.recover(self.root)['status'], 'held')
        self.assertTrue(self.git('status', '--porcelain').strip())

    def test_disk_full_snapshot_failure_preserves_every_tracked_file(self):
        recovery.record(self.root)
        before = self.git('diff')
        with patch.object(recovery, 'save', side_effect=OSError(28, 'No space left on device')):
            with self.assertRaises(OSError): recovery.recover(self.root)
        self.assertEqual(self.git('diff'), before)
        self.assertFalse((self.root / '.local/research.lock').exists())

    def test_recovery_requires_original_head(self):
        recovery.record(self.root)
        self.git('commit', '--allow-empty', '-qm', 'new baseline')
        self.assertEqual(recovery.recover(self.root)['status'], 'held')

    def test_next_sync_recovers_then_fast_forwards_to_new_remote_code(self):
        with tempfile.TemporaryDirectory() as t:
            remote = Path(t) / 'origin.git'; other = Path(t) / 'other'
            subprocess.run(['git', 'init', '--bare', '-q', str(remote)], check=True)
            self.git('branch', '-M', 'main'); self.git('remote', 'add', 'origin', str(remote))
            self.git('push', '-u', 'origin', 'main')
            subprocess.run(['git', 'clone', '-q', '-b', 'main', str(remote), str(other)], check=True)
            recovery.git(other, 'config', 'user.name', 'Test'); recovery.git(other, 'config', 'user.email', 'test@example.invalid')
            (other / 'new-code.txt').write_text('reviewed code update')
            recovery.git(other, 'add', '.'); recovery.git(other, 'commit', '-qm', 'code update'); recovery.git(other, 'push')
            self.assertTrue(recovery.record(self.root))
            result = nightly.stage_sync(self.root)
            self.assertEqual(result['status'], 'ok')
            self.assertTrue(result['moved'])
            self.assertEqual(result['recovery']['status'], 'recovered')
            self.assertEqual(self.git('status', '--porcelain').strip(), b'')
            self.assertTrue((self.root / 'new-code.txt').exists())


class StorageAndStatusTests(unittest.TestCase):
    def test_storage_checks_the_private_junction_target_too(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t); (root / '.local').mkdir()
            with patch.object(safety.shutil, 'disk_usage', side_effect=[SimpleNamespace(free=3*1024**3), SimpleNamespace(free=100)]):
                with self.assertRaises(safety.LowDiskSpace): safety.check_storage(root)

    def test_low_space_stops_before_any_model_subprocess(self):
        with tempfile.TemporaryDirectory() as t, patch.object(loop, 'ROOT', Path(t)), \
             patch.object(loop, 'check_storage', side_effect=safety.LowDiskSpace('disk reserve exhausted')), \
             patch.object(loop.subprocess, 'Popen') as spawn, \
             patch('research_notify.notify_session', return_value={'status': 'deferred'}), \
             patch('builtins.print'):
            self.assertEqual(loop.main(['--start', '--minutes', '5', '--ignore-gpu-busy']), 1)
            spawn.assert_not_called()
            self.assertEqual(json.loads((Path(t) / '.local/session-status.json').read_text())['state'], 'blocked')

    def test_receipt_write_failure_reaches_supervisor_instead_of_throwing(self):
        with tempfile.TemporaryDirectory() as t, patch.object(nightly, 'save', side_effect=OSError(28, 'disk full')), \
             patch('sys.stdout', new_callable=io.StringIO) as output:
            receipt = nightly.run_stage(Path(t), '2026-10-05', 'research', 1, lambda: {'status': 'ok'})
            self.assertEqual(receipt['status'], 'failed')
            self.assertIn('Receipt could not be saved', output.getvalue())

    def test_full_disk_status_error_does_not_orphan_the_active_batch(self):
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as t:
            root=Path(t); real_atomic=loop.atomic; clock=[0]; writes=[0]
            def write(path, value):
                if path.name=='status.json':
                    writes[0]+=1
                    if writes[0]>=3: raise OSError(28, 'No space left on device')
                return real_atomic(path,value)
            child=Mock(returncode=0); child.poll.side_effect=[None,0]
            # Loop preflight succeeds; storage becomes exhausted only after the child launched.
            with patch.object(loop,'ROOT',root), patch.object(loop,'atomic',side_effect=write), \
                 patch.object(loop,'check_storage',side_effect=[[],safety.LowDiskSpace('disk full'),safety.LowDiskSpace('disk full')]), \
                 patch.object(loop.subprocess,'Popen',return_value=child), \
                 patch.object(loop.time,'sleep',side_effect=lambda s:clock.__setitem__(0,clock[0]+s)), \
                 patch.object(loop.time,'monotonic',side_effect=lambda:clock[0]), \
                 patch('research_notify.notify_session',return_value={'status':'deferred'}), patch('builtins.print'):
                self.assertEqual(loop.main(['--start','--minutes','5','--ignore-gpu-busy']),1)
            self.assertEqual(child.poll.call_count,2)
            self.assertFalse((root/'.local/research-session.lock').exists())

    def test_dead_session_is_reported_interrupted_without_rewriting_history(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t); local = root / '.local'; local.mkdir()
            original = {'session_id': 'a'*32, 'pid': 99999999, 'state': 'waiting for eligible sources'}
            (local / 'session-status.json').write_text(json.dumps(original))
            with patch.object(nightly, 'pid_alive', return_value=False): result = control.Controller(root).status()
            self.assertFalse(result['active'])
            self.assertEqual(result['session']['state'], 'interrupted')
            self.assertEqual(json.loads((local / 'session-status.json').read_text()), original)

    def test_dead_lock_is_not_displayed_as_running_or_bypassed_for_launch(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t); local = root / '.local'; local.mkdir()
            (local / 'research-session.lock').write_text(json.dumps({'pid':99999999, 'session_id':'b'*32}))
            with patch.object(nightly, 'pid_alive', return_value=False):
                self.assertFalse(control.Controller(root).status()['active'])
            self.assertTrue((local / 'research-session.lock').exists())


class DiscoveryCapacityTests(unittest.TestCase):
    def test_full_queue_archives_exhausted_lead_and_remembers_it(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t); policy = {'max_leads': 10}
            state = {'leads': {}, 'archived': {}}
            context = {'layer': 'energy'}
            for i in range(10):
                discovery.add_lead(state, f'https://example.org/news/{i}', context, {'type': 'retained'}, policy, '2026-09-01T00:00:00Z')
            key, lead = next(iter(state['leads'].items()))
            lead.update(status='source_inaccessible', failures=4, attempts=4, last_attempt='2026-09-20T00:00:00Z')
            original = copy.deepcopy(lead)
            self.assertEqual(discovery.archive_exhausted(root, state, policy, '2026-10-05T08:00:00Z'), 1)
            self.assertEqual(len(state['leads']), 9)
            archived = next((root / '.local/discovery/archive' / key).glob('*.json'))
            self.assertEqual(json.loads(archived.read_text())['lead'], original)
            self.assertFalse(discovery.add_lead(state, original['url'], context, {}, policy, '2026-10-06T00:00:00Z'))
            self.assertTrue(discovery.add_lead(state, 'https://example.org/news/new', context, {}, policy, '2026-10-06T00:00:00Z'))

    def test_proposals_indexes_and_partial_screens_remain_protected(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t); policy = {'max_leads': 3}
            lead = {'first_seen': '2026-09-01', 'last_attempt': '2026-09-20', 'attempts': 10,
                    'failures': 10, 'status': 'no_findings', 'screen_coverage': {'complete': True}}
            state = {'leads': {'proposal': dict(lead, proposal_id='pending'),
                               'index': dict(lead, lineage={'type': 'registered_index'}),
                               'partial': dict(lead, screen_coverage={'complete': False})}}
            self.assertEqual(discovery.archive_exhausted(root, state, policy, '2026-10-05T08:00:00Z'), 0)
            self.assertEqual(len(state['leads']), 3)


if __name__ == '__main__': unittest.main()
