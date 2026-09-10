import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import nightly
import catalog_review as cr
import publication_policy as pp
from validate import validate_importers


FAKE_IMPORTER = """import sys
from pathlib import Path
mode = sys.argv[1] if len(sys.argv) > 1 else 'ok'
target = Path('research/imported.json')
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text('{"ok": true}', encoding='utf-8')
sys.exit(0 if mode == 'ok' else 1)
"""


def git(root, *args, check=True):
    return subprocess.run(['git', *args], cwd=root, capture_output=True, text=True, check=check, timeout=30)


class LockRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup); self.root = Path(self.temp.name)

    def test_pid_alive_true_for_self_false_for_a_reaped_process(self):
        self.assertTrue(nightly.pid_alive(os.getpid()))
        child = subprocess.Popen([sys.executable, '-c', 'pass'])
        child.wait()  # spawn and reap: this pid is now certainly free
        self.assertFalse(nightly.pid_alive(child.pid))
        self.assertFalse(nightly.pid_alive(-1))
        self.assertFalse(nightly.pid_alive('not-a-pid'))

    def test_lock_with_dead_pid_is_removed_with_a_receipt(self):
        child = subprocess.Popen([sys.executable, '-c', 'pass']); child.wait()
        path = self.root/'research.lock'; path.write_text(json.dumps({'pid': child.pid, 'started_at': 'x'}), encoding='utf-8')
        result = nightly.lock_status(path)
        self.assertEqual(result['action'], 'removed_dead_pid'); self.assertFalse(result['blocking'])
        self.assertFalse(path.exists())

    def test_lock_with_the_current_process_pid_blocks(self):
        path = self.root/'research-session.lock'; path.write_text(json.dumps({'pid': os.getpid(), 'session_id': 'x'}), encoding='utf-8')
        result = nightly.lock_status(path)
        self.assertEqual(result['action'], 'left_alive'); self.assertTrue(result['blocking'])
        self.assertTrue(path.exists())  # a live lock is never removed

    def test_lock_with_no_pid_is_removed_only_once_stale(self):
        path = self.root/'editorial.lock'; path.write_text('', encoding='utf-8')
        fresh = nightly.lock_status(path)
        self.assertEqual(fresh['action'], 'left_no_pid_recent'); self.assertTrue(fresh['blocking']); self.assertTrue(path.exists())
        old_time = time.time() - 13*3600
        os.utime(path, (old_time, old_time))
        stale = nightly.lock_status(path)
        self.assertEqual(stale['action'], 'removed_stale_no_pid'); self.assertFalse(stale['blocking']); self.assertFalse(path.exists())

    def test_absent_lock_is_reported_and_never_blocks(self):
        result = nightly.lock_status(self.root/'missing.lock')
        self.assertFalse(result['present']); self.assertFalse(result['blocking']); self.assertEqual(result['action'], 'absent')

    def test_stage_locks_recovers_all_three_and_reports_stop_flag(self):
        for rel in nightly.LOCKS:
            path = self.root/rel; path.parent.mkdir(parents=True, exist_ok=True); path.write_text('', encoding='utf-8')
            os.utime(path, (time.time()-13*3600,)*2)
        (self.root/'.local').mkdir(exist_ok=True); (self.root/'.local/stop-research-loop').write_text('', encoding='utf-8')
        result = nightly.stage_locks(self.root)
        self.assertEqual(result['status'], 'ok'); self.assertTrue(result['stop_research_present'])
        self.assertTrue(all(l['action'] == 'removed_stale_no_pid' for l in result['locks']))
        self.assertFalse(result['research_blocked']); self.assertFalse(result['editorial_blocked'])


class ImportersDueTests(unittest.TestCase):
    def test_due_by_weekday_and_daily_cadence(self):
        config = {'importers': [
            {'id': 'weekly-mon', 'cadence': 'weekly', 'weekday': 0},
            {'id': 'weekly-wed', 'cadence': 'weekly', 'weekday': 2},
            {'id': 'daily-one', 'cadence': 'daily'},
        ]}
        monday = date(2026, 9, 7); wednesday = date(2026, 9, 9)
        self.assertEqual(monday.weekday(), 0); self.assertEqual(wednesday.weekday(), 2)
        self.assertEqual({i['id'] for i in nightly.due_importers(config, monday)}, {'weekly-mon', 'daily-one'})
        self.assertEqual({i['id'] for i in nightly.due_importers(config, wednesday)}, {'weekly-wed', 'daily-one'})
        thursday = date(2026, 9, 10)
        self.assertEqual({i['id'] for i in nightly.due_importers(config, thursday)}, {'daily-one'})

    def test_real_importers_json_is_reviewed_and_epoch_is_wednesday(self):
        config = validate_importers(ROOT)
        epoch = next(i for i in config['importers'] if i['id'] == 'epoch')
        self.assertEqual(epoch['weekday'], 2)
        self.assertIn(epoch['id'], {i['id'] for i in nightly.due_importers(config, date(2026, 9, 9))})


class ValidateImportersTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup); self.root = Path(self.temp.name)
        (self.root/'scripts').mkdir(parents=True); (self.root/'scripts/import_x.py').write_text('', encoding='utf-8')
        (self.root/'research').mkdir()
        self.base = {'version': 1, 'reviewed_at': '2026-09-09T00:00:00Z',
                     'importers': [{'id': 'x', 'command': ['scripts/import_x.py', '--apply'], 'cadence': 'weekly', 'weekday': 2, 'timeout_seconds': 300}]}

    def write(self, value):
        (self.root/'research/importers.json').write_text(json.dumps(value), encoding='utf-8')

    def test_valid_file_returns_parsed_content(self):
        self.write(self.base)
        self.assertEqual(validate_importers(self.root)['importers'][0]['id'], 'x')

    def test_rejects_bad_cadence(self):
        bad = json.loads(json.dumps(self.base)); bad['importers'][0]['cadence'] = 'monthly'
        self.write(bad)
        with self.assertRaises(ValueError): validate_importers(self.root)

    def test_weekly_requires_weekday_in_range(self):
        bad = json.loads(json.dumps(self.base)); del bad['importers'][0]['weekday']
        self.write(bad)
        with self.assertRaises(ValueError): validate_importers(self.root)
        bad = json.loads(json.dumps(self.base)); bad['importers'][0]['weekday'] = 7
        self.write(bad)
        with self.assertRaises(ValueError): validate_importers(self.root)

    def test_daily_must_not_set_weekday(self):
        bad = json.loads(json.dumps(self.base)); bad['importers'][0]['cadence'] = 'daily'
        self.write(bad)
        with self.assertRaises(ValueError): validate_importers(self.root)

    def test_timeout_bounds(self):
        for bad_timeout in (10, 5000):
            bad = json.loads(json.dumps(self.base)); bad['importers'][0]['timeout_seconds'] = bad_timeout
            self.write(bad)
            with self.assertRaises(ValueError): validate_importers(self.root)

    def test_unknown_script_path_rejected(self):
        bad = json.loads(json.dumps(self.base)); bad['importers'][0]['command'] = ['scripts/does_not_exist.py']
        self.write(bad)
        with self.assertRaises(ValueError): validate_importers(self.root)

    def test_script_outside_scripts_directory_rejected(self):
        (self.root/'evil.py').write_text('', encoding='utf-8')
        bad = json.loads(json.dumps(self.base)); bad['importers'][0]['command'] = ['evil.py']
        self.write(bad)
        with self.assertRaises(ValueError): validate_importers(self.root)

    def test_duplicate_id_rejected(self):
        bad = json.loads(json.dumps(self.base)); bad['importers'].append(dict(bad['importers'][0]))
        self.write(bad)
        with self.assertRaises(ValueError): validate_importers(self.root)

    def test_future_reviewed_at_rejected(self):
        bad = json.loads(json.dumps(self.base)); bad['reviewed_at'] = '2999-01-01T00:00:00Z'
        self.write(bad)
        with self.assertRaises(ValueError): validate_importers(self.root)

    def test_unexpected_top_level_field_rejected(self):
        bad = json.loads(json.dumps(self.base)); bad['extra'] = True
        self.write(bad)
        with self.assertRaises(ValueError): validate_importers(self.root)

    def test_research_ignore_gpu_busy_must_be_bool(self):
        bad = json.loads(json.dumps(self.base)); bad['research_ignore_gpu_busy'] = 'true'
        self.write(bad)
        with self.assertRaises(ValueError): validate_importers(self.root)
        ok = json.loads(json.dumps(self.base)); ok['research_ignore_gpu_busy'] = False
        self.write(ok)
        self.assertFalse(validate_importers(self.root)['research_ignore_gpu_busy'])


class RunStageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup); self.root = Path(self.temp.name)
        self.date = '2026-09-09'

    def read_receipt(self, name):
        return json.loads((self.root/'.local/nightly'/self.date/(name+'.json')).read_text(encoding='utf-8'))

    def test_successful_stage_writes_an_ok_receipt(self):
        receipt = nightly.run_stage(self.root, self.date, 'demo', 5, lambda: {'result': 42})
        self.assertEqual(receipt['status'], 'ok'); self.assertEqual(receipt['result'], 42)
        self.assertEqual(self.read_receipt('demo')['status'], 'ok')

    def test_raising_stage_is_recorded_failed_not_raised(self):
        def boom(): raise RuntimeError('synthetic failure')
        receipt = nightly.run_stage(self.root, self.date, 'demo', 5, boom)
        self.assertEqual(receipt['status'], 'failed'); self.assertIn('synthetic failure', receipt['message'])
        self.assertEqual(self.read_receipt('demo')['status'], 'failed')

    def test_slow_stage_times_out_without_blocking(self):
        started = time.monotonic()
        receipt = nightly.run_stage(self.root, self.date, 'demo', 0.1, lambda: time.sleep(5))
        self.assertLess(time.monotonic()-started, 4)
        self.assertEqual(receipt['status'], 'timeout')

    def test_stage_can_report_its_own_status(self):
        receipt = nightly.run_stage(self.root, self.date, 'demo', 5, lambda: {'status': 'skipped', 'reason': 'not due'})
        self.assertEqual(receipt['status'], 'skipped'); self.assertEqual(receipt['reason'], 'not due')


class RunOrchestrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup); self.root = Path(self.temp.name)
        self.date = datetime.now(timezone.utc).strftime('%Y-%m-%d')

    def test_dry_run_writes_nothing_and_reports_the_plan(self):
        (self.root/'research').mkdir()
        (self.root/'research/importers.json').write_text((ROOT/'research/importers.json').read_text(encoding='utf-8'), encoding='utf-8')
        config = json.loads((ROOT/'research/importers.json').read_text(encoding='utf-8'))
        (self.root/'scripts').mkdir()
        for imp in config['importers']: (self.root/imp['command'][0]).write_text('', encoding='utf-8')
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = nightly.run(self.root, dry_run=True, only=None)
        self.assertEqual(code, 0)
        plan = json.loads(buf.getvalue())
        self.assertEqual(plan['stages'], nightly.STAGES)
        self.assertIn('epoch', plan['importers_due'])
        self.assertTrue(plan['research_ignore_gpu_busy'])
        self.assertFalse((self.root/'.local').exists())

    def test_dry_run_only_narrows_the_reported_stage_list(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            nightly.run(self.root, dry_run=True, only='health')
        self.assertEqual(json.loads(buf.getvalue())['stages'], ['health'])

    def test_main_dry_run_flag_reaches_run(self):
        with patch.object(nightly, 'run', return_value=0) as fake:
            self.assertEqual(nightly.main(['--dry-run']), 0)
        fake.assert_called_once_with(nightly.ROOT, dry_run=True, only=None)

    def test_failed_stage_is_recorded_and_skipped_digest_reports_it_exit_zero(self):
        calls = []
        def fake(name, value):
            def inner(*_a):
                calls.append(name)
                if name == 'health': raise RuntimeError('collection host unreachable')
                return value
            return inner
        with patch.object(nightly, 'stage_locks', fake('locks', {'status': 'ok'})), \
             patch.object(nightly, 'stage_importers', fake('importers', {'status': 'ok', 'due': [], 'results': []})), \
             patch.object(nightly, 'stage_research', fake('research', {'status': 'skipped', 'reason': 'test'})), \
             patch.object(nightly, 'stage_policy', fake('policy', {'status': 'skipped', 'reason': 'test'})), \
             patch.object(nightly, 'stage_health', fake('health', None)), \
             patch.object(nightly, 'stage_prune', fake('prune', {'status': 'ok', 'deleted': [], 'bytes_freed': 0, 'count': 0, 'dry_run': False})):
            code = nightly.run(self.root, dry_run=False, only=None)
        self.assertEqual(code, 0)  # only a failed digest itself would return 1
        self.assertEqual(calls, ['locks', 'importers', 'research', 'policy', 'health', 'prune'])
        health_receipt = json.loads((self.root/'.local/nightly'/self.date/'health.json').read_text(encoding='utf-8'))
        self.assertEqual(health_receipt['status'], 'failed')
        digest = json.loads((self.root/'.local/digest'/(self.date+'.json')).read_text(encoding='utf-8'))
        self.assertEqual(digest['stage_receipts']['health'], 'failed')
        self.assertEqual(digest['stage_receipts']['locks'], 'ok')
        markdown = (self.root/'.local/digest'/(self.date+'.md')).read_text(encoding='utf-8')
        self.assertIn('health: failed', markdown)

    def test_only_runs_a_single_stage(self):
        with patch.object(nightly, 'stage_health', return_value={'status': 'ok', 'marker': True}) as fake_health, \
             patch.object(nightly, 'stage_locks') as fake_locks:
            nightly.run(self.root, dry_run=False, only='health')
        fake_health.assert_called_once()
        fake_locks.assert_not_called()
        self.assertTrue((self.root/'.local/nightly'/self.date/'health.json').exists())
        self.assertFalse((self.root/'.local/nightly'/self.date/'locks.json').exists())


class StageValidatePendingTests(unittest.TestCase):
    """So cards are ready in the morning: the policy stage re-validates every pending package whose
    preview is missing or stale before the digest runs, receipted separately from admission/apply."""
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup); self.root = Path(self.temp.name)

    def test_validates_only_packages_missing_or_stale_validation(self):
        rows = [
            {'id': 'catalog-a', 'status': 'pending_review', 'proposal_hash': 'h1', 'validation': None},
            {'id': 'catalog-b', 'status': 'pending_review', 'proposal_hash': 'h2', 'validation': {'passed': True, 'proposal_hash': 'h2'}},
            {'id': 'catalog-c', 'status': 'pending_review', 'proposal_hash': 'h3', 'validation': {'passed': False, 'proposal_hash': 'h3'}},
            {'id': 'catalog-d', 'status': 'approved', 'proposal_hash': 'h4', 'validation': None},
        ]
        calls = []
        with patch.object(cr, 'inbox', return_value=rows), \
             patch.object(cr, 'preview', side_effect=lambda root, rid: calls.append(rid) or {'passed': True}):
            validated, failed = nightly.stage_validate_pending(self.root)
        self.assertEqual(calls, ['catalog-a', 'catalog-c'])  # missing, and failed-for-this-hash; not the passing one, not the non-pending one
        self.assertEqual(validated, [{'id': 'catalog-a', 'passed': True}, {'id': 'catalog-c', 'passed': True}])
        self.assertEqual(failed, [])

    def test_a_failing_preview_is_reported_not_raised(self):
        rows = [{'id': 'catalog-a', 'status': 'pending_review', 'proposal_hash': 'h1', 'validation': None}]
        with patch.object(cr, 'inbox', return_value=rows), patch.object(cr, 'preview', side_effect=ValueError('boom')):
            validated, failed = nightly.stage_validate_pending(self.root)
        self.assertEqual(validated, [])
        self.assertEqual(len(failed), 1); self.assertIn('boom', failed[0]['error']); self.assertEqual(failed[0]['id'], 'catalog-a')


class StagePolicyValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup); self.root = Path(self.temp.name)

    def test_validation_runs_even_when_auto_apply_is_disabled(self):
        with patch.object(nightly, 'stage_validate_pending', return_value=([{'id': 'catalog-a', 'passed': True}], [])) as fake_validate, \
             patch.object(pp, 'policy', return_value={'auto_apply': {'enabled': False}}):
            result = nightly.stage_policy(self.root)
        fake_validate.assert_called_once_with(self.root)
        self.assertEqual(result['status'], 'skipped')
        self.assertEqual(result['validated'], [{'id': 'catalog-a', 'passed': True}])
        self.assertEqual(result['validation_failures'], [])

    def test_a_validation_failure_alone_still_marks_the_disabled_stage_partial(self):
        with patch.object(nightly, 'stage_validate_pending', return_value=([], [{'id': 'catalog-a', 'error': 'boom'}])), \
             patch.object(pp, 'policy', return_value={'auto_apply': {'enabled': False}}):
            result = nightly.stage_policy(self.root)
        self.assertEqual(result['status'], 'partial')

    def test_a_validation_failure_marks_the_stage_partial_even_when_policy_succeeds(self):
        with patch.object(nightly, 'stage_validate_pending', return_value=([], [{'id': 'catalog-a', 'error': 'boom'}])), \
             patch.object(pp, 'policy', return_value={'auto_apply': {'enabled': True}}), \
             patch.object(nightly, 'lock_status', return_value={'blocking': False}), \
             patch.object(pp, 'apply_admitted', return_value={'pending': 0, 'admitted': [], 'outcomes': {}}), \
             patch.object(cr, 'verify_pending_deployments', return_value={'checked': [], 'applied': [], 'still_pending': []}):
            result = nightly.stage_policy(self.root)
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(result['validation_failures'], [{'id': 'catalog-a', 'error': 'boom'}])

    def test_receipt_stays_ok_when_nothing_failed(self):
        with patch.object(nightly, 'stage_validate_pending', return_value=([{'id': 'catalog-a', 'passed': True}], [])), \
             patch.object(pp, 'policy', return_value={'auto_apply': {'enabled': True}}), \
             patch.object(nightly, 'lock_status', return_value={'blocking': False}), \
             patch.object(pp, 'apply_admitted', return_value={'pending': 1, 'admitted': ['catalog-a'], 'outcomes': {'catalog-a': 'deployed'}}), \
             patch.object(cr, 'verify_pending_deployments', return_value={'checked': [], 'applied': [], 'still_pending': []}):
            result = nightly.stage_policy(self.root)
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(result['validated'], [{'id': 'catalog-a', 'passed': True}])


class PruneTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup); self.root = Path(self.temp.name)
        self.base = self.root/'.local/catalog-previews'

    def make(self, rid, files=('a.json',)):
        folder = self.base/rid; folder.mkdir(parents=True)
        for name in files: (folder/name).write_text('x'*100, encoding='utf-8')
        return folder

    def test_deletes_only_old_decided_packages_and_reports_bytes(self):
        old_applied = 'catalog-' + 'a'*24
        old_rejected = 'catalog-' + 'b'*24
        recent_applied = 'catalog-' + 'c'*24
        undecided = 'catalog-' + 'd'*24
        not_a_package = 'not-a-package-id'
        for rid in (old_applied, old_rejected, recent_applied, undecided, not_a_package):
            self.make(rid)
        old_at = (datetime.now(timezone.utc)-timedelta(days=10)).isoformat().replace('+00:00', 'Z')
        recent_at = (datetime.now(timezone.utc)-timedelta(days=1)).isoformat().replace('+00:00', 'Z')
        reviews = {old_applied: {'status': 'applied', 'at': old_at}, old_rejected: {'status': 'rejected', 'at': old_at},
                   recent_applied: {'status': 'applied', 'at': recent_at}, undecided: {'status': 'pending_review', 'at': recent_at}}
        with patch.object(cr, 'last_review', side_effect=lambda root, rid: reviews.get(rid)):
            result = nightly.stage_prune(self.root)
        deleted_ids = {d['id'] for d in result['deleted']}
        self.assertEqual(deleted_ids, {old_applied, old_rejected})
        self.assertFalse((self.base/old_applied).exists()); self.assertFalse((self.base/old_rejected).exists())
        self.assertTrue((self.base/recent_applied).exists()); self.assertTrue((self.base/undecided).exists())
        self.assertTrue((self.base/not_a_package).exists())  # never matched RID, left alone
        self.assertGreater(result['bytes_freed'], 0)

    def test_dry_run_reports_without_deleting(self):
        rid = 'catalog-' + 'e'*24; self.make(rid)
        old_at = (datetime.now(timezone.utc)-timedelta(days=30)).isoformat().replace('+00:00', 'Z')
        with patch.object(cr, 'last_review', return_value={'status': 'applied', 'at': old_at}):
            result = nightly.stage_prune(self.root, dry_run=True)
        self.assertEqual([d['id'] for d in result['deleted']], [rid])
        self.assertTrue((self.base/rid).exists())  # dry run: nothing actually removed

    def test_no_preview_directory_is_a_clean_no_op(self):
        result = nightly.stage_prune(self.root)
        self.assertEqual(result, {'status': 'ok', 'deleted': [], 'bytes_freed': 0, 'count': 0, 'dry_run': False})


class ImporterGitRollbackTests(unittest.TestCase):
    """The importer stage's own safety net: a failing importer must never leave tracked changes behind."""
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup); self.root = Path(self.temp.name)
        for d in ['research', 'site', 'docs', 'tools']: (self.root/d).mkdir()
        (self.root/'research/.gitkeep').write_text('', encoding='utf-8')
        (self.root/'tools/fake_importer.py').write_text(FAKE_IMPORTER, encoding='utf-8')
        git(self.root, 'init', '-q')
        git(self.root, 'config', 'user.email', 'test@example.com'); git(self.root, 'config', 'user.name', 'Test')
        git(self.root, 'add', '-A'); git(self.root, 'commit', '-q', '-m', 'init')

    def test_success_commits_the_change_with_the_nightly_import_prefix(self):
        outcome = nightly.run_importer(self.root, {'id': 'fake', 'command': ['tools/fake_importer.py', 'ok'], 'timeout_seconds': 30})
        self.assertEqual(outcome['status'], 'ok'); self.assertTrue(outcome['committed'])
        subject = git(self.root, 'log', '-1', '--format=%s').stdout.strip()
        self.assertTrue(subject.startswith('nightly(import:fake):'), subject)
        self.assertTrue((self.root/'research/imported.json').exists())
        self.assertEqual(git(self.root, 'status', '--porcelain').stdout.strip(), '')

    def test_failure_leaves_the_tree_exactly_as_it_was(self):
        outcome = nightly.run_importer(self.root, {'id': 'fake', 'command': ['tools/fake_importer.py', 'fail'], 'timeout_seconds': 30})
        self.assertEqual(outcome['status'], 'failed')
        self.assertEqual(git(self.root, 'status', '--porcelain').stdout.strip(), '')
        self.assertFalse((self.root/'research/imported.json').exists())

    def test_no_changes_is_ok_without_a_commit(self):
        (self.root/'tools/fake_importer.py').write_text('import sys\nsys.exit(0)\n', encoding='utf-8')
        before = git(self.root, 'rev-parse', 'HEAD').stdout.strip()
        outcome = nightly.run_importer(self.root, {'id': 'noop', 'command': ['tools/fake_importer.py'], 'timeout_seconds': 30})
        self.assertEqual(outcome['status'], 'ok'); self.assertFalse(outcome['committed'])
        self.assertEqual(git(self.root, 'rev-parse', 'HEAD').stdout.strip(), before)


if __name__ == '__main__':
    unittest.main()


class PushTests(unittest.TestCase):
    """Importer commits must reach origin before the research preflight compares HEAD with origin."""
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup); base = Path(self.temp.name)
        self.remote = base/'origin.git'; self.root = base/'work'; self.root.mkdir()
        git(base, 'init', '-q', '--bare', str(self.remote))
        git(self.root, 'init', '-q'); git(self.root, 'config', 'user.email', 't@example.com'); git(self.root, 'config', 'user.name', 'T')
        (self.root/'research').mkdir(); (self.root/'research/runtime.json').write_text(json.dumps({'branch': 'main'}), encoding='utf-8')
        git(self.root, 'checkout', '-q', '-b', 'main'); git(self.root, 'add', '-A'); git(self.root, 'commit', '-q', '-m', 'init')
        git(self.root, 'remote', 'add', 'origin', str(self.remote)); git(self.root, 'push', '-q', 'origin', 'main')

    def test_push_origin_pushes_local_commits_and_commits_ahead_tracks_them(self):
        (self.root/'research/new.json').write_text('{}', encoding='utf-8'); git(self.root, 'add', '-A'); git(self.root, 'commit', '-q', '-m', 'nightly(import:x): one')
        self.assertEqual(nightly.commits_ahead(self.root), 1)
        result = nightly.push_origin(self.root)
        self.assertTrue(result['pushed']); self.assertEqual(result['branch'], 'main')
        self.assertEqual(nightly.commits_ahead(self.root), 0)
        self.assertEqual(git(self.root, 'rev-parse', 'origin/main').stdout.strip(), git(self.root, 'rev-parse', 'HEAD').stdout.strip())

    def test_importers_stage_pushes_only_when_something_was_committed(self):
        calls = []
        config = {'importers': [{'id': 'a', 'command': ['scripts/x.py'], 'cadence': 'daily', 'timeout_seconds': 30}]}
        with patch.object(nightly, 'validate_importers', return_value=config), patch.object(nightly, 'push_origin', side_effect=lambda r: calls.append(r) or {'pushed': True, 'attempts': 1, 'branch': 'main'}):
            with patch.object(nightly, 'run_importer', return_value={'id': 'a', 'status': 'ok', 'committed': False}):
                receipt = nightly.stage_importers(self.root, 600)
            self.assertIsNone(receipt['push']); self.assertEqual(calls, [])
            with patch.object(nightly, 'run_importer', return_value={'id': 'a', 'status': 'ok', 'committed': True, 'commit': 'abc'}):
                receipt = nightly.stage_importers(self.root, 600)
            self.assertEqual(len(calls), 1); self.assertTrue(receipt['push']['pushed']); self.assertEqual(receipt['status'], 'ok')
        with patch.object(nightly, 'validate_importers', return_value=config), patch.object(nightly, 'push_origin', return_value={'pushed': False, 'attempts': 2, 'branch': 'main', 'error': 'offline'}):
            with patch.object(nightly, 'run_importer', return_value={'id': 'a', 'status': 'ok', 'committed': True, 'commit': 'abc'}):
                receipt = nightly.stage_importers(self.root, 600)
        self.assertEqual(receipt['status'], 'partial')
