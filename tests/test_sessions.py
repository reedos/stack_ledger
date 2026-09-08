import copy
import json
import sys
import tempfile
import threading
import io
import unittest
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch, Mock

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import research_loop as loop
import research_control as control
import session_options as options
import research
import discovery
import test_research

DEFAULT={'minutes':360,'direction':'balanced','layers':[],'source_kinds':[],
         'publish':False,'idle_only':False,'keep_awake':True}


class SessionTests(unittest.TestCase):
    def test_missing_gpu_telemetry_does_not_wait_for_six_hours(self):
        with tempfile.TemporaryDirectory() as t:
            clock=[0]
            def sleep(seconds):clock[0]+=seconds
            with patch.object(loop,'ROOT',Path(t)),patch.object(loop.time,'monotonic',side_effect=lambda:clock[0]), \
                 patch.object(loop.time,'sleep',side_effect=sleep),patch.object(loop,'gpu_idle',side_effect=ValueError('bad telemetry')), \
                 patch.object(loop.subprocess,'Popen') as spawn,patch('research_notify.notify_session',return_value={'status':'disabled'}),patch('builtins.print'):
                self.assertEqual(loop.main(['--start','--minutes','360']),1)
                spawn.assert_not_called()
            report=json.loads((Path(t)/'.local/session-status.json').read_text())
            self.assertEqual(report['state'],'blocked');self.assertLessEqual(report['elapsed_seconds'],20)

    def test_same_timestamp_in_separate_private_sessions_never_overwrites_receipts(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);test_research.RunnerTests().fixture(root)
            document=research.ReadableHTML();document.feed('<p>Public evidence about energy infrastructure.</p>')
            at=research.now()
            with patch.object(research,'ROOT',root),patch.object(research,'LOCAL',root/'.local'), \
                 patch.object(research.Fetcher,'fetch',return_value=document),patch.object(research,'ollama',return_value={'observations':[]}), \
                 patch.object(research,'now',return_value=at),patch('sys.stdout',new=io.StringIO()):
                for sid in ['a'*32,'b'*32]:
                    with patch.object(sys,'argv',['research.py','--session-id',sid,'--sources','iea-2026']):
                        self.assertEqual(research.main(),0)
            self.assertEqual(len(list((root/'.local/runs').glob('*.json'))),2)
            self.assertEqual(len(list((root/'.local/proposals').glob('*.json'))),2)

    def test_persistent_failures_stop_promptly_and_notify(self):
        for code,expected in [(1,3),(3,1)]:
            with self.subTest(code=code),tempfile.TemporaryDirectory() as t:
                clock=[0]
                def sleep(seconds):clock[0]+=seconds
                child=Mock(returncode=code);child.poll.return_value=code
                with patch.object(loop,'ROOT',Path(t)),patch.object(loop.time,'monotonic',side_effect=lambda:clock[0]), \
                     patch.object(loop.time,'sleep',side_effect=sleep),patch.object(loop.subprocess,'Popen',return_value=child) as spawn, \
                     patch('research_notify.notify_session',return_value={'status':'sent'}) as notify,patch('builtins.print'):
                    self.assertEqual(loop.main(['--start','--minutes','360','--publish','--ignore-gpu-busy']),1)
                report=json.loads((Path(t)/'.local/session-status.json').read_text())
                self.assertEqual(spawn.call_count,expected)
                self.assertEqual(report['state'],'blocked')
                self.assertLessEqual(report['elapsed_seconds'],120)
                self.assertFalse((Path(t)/'.local/research-session.lock').exists())
                notify.assert_called_once()
                self.assertEqual(notify.call_args.args[1]['state'],'blocked')

    def test_status_replace_retries_windows_sharing_errors(self):
        with tempfile.TemporaryDirectory() as t:
            path=Path(t)/'status.json';path.write_text('{"old":true}')
            replace=loop.os.replace
            calls=[]
            def locked(source,target):
                calls.append(source)
                if len(calls)<3:raise PermissionError('sharing violation')
                replace(source,target)
            with patch.object(loop.os,'replace',side_effect=locked),patch.object(loop.time,'sleep'):
                loop.atomic(path,{'state':'blocked'})
            self.assertEqual(json.loads(path.read_text()),{'state':'blocked'})
            self.assertEqual(len(calls),3)
            with patch.object(loop.os,'replace',side_effect=PermissionError('locked')),patch.object(loop.time,'sleep'):
                with self.assertRaises(PermissionError):loop.atomic(path,{'new':True})
            self.assertEqual(list(Path(t).glob('*.tmp')),[])
            self.assertEqual(json.loads(path.read_text()),{'state':'blocked'})

    def test_locked_status_mirror_does_not_abort_session(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);clock=[0];real_atomic=loop.atomic
            def write(path,value):
                if path.name=='session-status.json':raise PermissionError('locked mirror')
                real_atomic(path,value)
            def sleep(seconds):clock[0]+=seconds
            child=Mock(returncode=0);child.poll.return_value=0
            with patch.object(loop,'ROOT',root),patch.object(loop,'atomic',side_effect=write), \
                 patch.object(loop.time,'monotonic',side_effect=lambda:clock[0]),patch.object(loop.time,'sleep',side_effect=sleep), \
                 patch.object(loop.subprocess,'Popen',return_value=child),patch('research_notify.notify_session',return_value={'status':'disabled'}),patch('builtins.print'):
                self.assertEqual(loop.main(['--start','--minutes','1','--ignore-gpu-busy']),0)
            report=json.loads(next((root/'.local/sessions').glob('*/status.json')).read_text())
            self.assertEqual(report['state'],'completed')

    def test_control_uses_active_session_when_status_mirror_is_stale(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);sid='b'*32;folder=root/'.local/sessions'/sid;folder.mkdir(parents=True)
            loop.atomic(root/'.local/session-status.json',{'session_id':'a'*32,'state':'researching'})
            loop.atomic(root/'.local/research-session.lock',{'session_id':sid})
            loop.atomic(folder/'status.json',{'session_id':sid,'state':'batch failed'})
            self.assertEqual(control.Controller(root).status()['session']['state'],'batch failed')

    def test_preflight_failure_does_not_fetch_or_retry(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);test_research.RunnerTests().fixture(root)
            with patch.object(research,'ROOT',root),patch.object(research,'LOCAL',root/'.local'), \
                 patch.object(research,'preflight',side_effect=ValueError('Working tree must be clean')), \
                 patch.object(research.Fetcher,'fetch') as fetch,patch.object(sys,'argv',['research.py','--publish']),patch('sys.stderr',new=io.StringIO()):
                self.assertEqual(research.main(),3);fetch.assert_not_called()

    def test_build_failure_retains_evidence_and_signals_publication_block(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);test_research.RunnerTests().fixture(root);sid='a'*32
            document=research.ReadableHTML();document.feed('<p>Public evidence about energy infrastructure.</p>')
            with patch.object(research,'ROOT',root),patch.object(research,'LOCAL',root/'.local'), \
                 patch.object(research,'preflight'),patch.object(research.Fetcher,'fetch',return_value=document), \
                 patch.object(research,'ollama',return_value={'observations':[]}), \
                 patch.object(research,'build',side_effect=RuntimeError('build failed')),patch.object(research,'publish') as publish, \
                 patch.object(sys,'argv',['research.py','--publish','--session-id',sid,'--sources','iea-2026']), \
                 patch('sys.stderr',new=io.StringIO()),patch('sys.stdout',new=io.StringIO()):
                self.assertEqual(research.main(),3);publish.assert_not_called()
            self.assertTrue((root/'.local/proposed-ledger.json').exists())
            receipt=json.loads(next((root/'.local/sessions'/sid/'batches').glob('*.json')).read_text())
            self.assertEqual(receipt['publication'],'pending')

    def test_gpu_readings_preserve_missing_values_and_reject_invalid_data(self):
        self.assertEqual(control.gpu_values('RTX 5090, 90, 56')['temperature'],56)
        missing=control.gpu_values('RTX 5090, [N/A], 56')
        self.assertIsNone(missing['utilization']);self.assertEqual(missing['temperature'],56)
        for value in ['GPU, 101, 56','GPU, -1, 56','GPU, 50, NaN','GPU, 50']:
            with self.assertRaises(ValueError):control.gpu_values(value)

    def test_gpu_polling_is_cached_bounded_and_failure_is_not_zero(self):
        sampler=control.GpuSampler()
        with patch.object(control.shutil,'which',return_value='nvidia-smi'), \
             patch.object(control.subprocess,'run',return_value=Mock(stdout='RTX 5090, 90, 56')) as run, \
             patch.object(control.time,'monotonic',return_value=10):
            self.assertEqual(sampler.snapshot()['latest']['utilization'],90)
            sampler.snapshot();run.assert_called_once()
            self.assertIn('--id=0',run.call_args.args[0])
        with patch.object(control.shutil,'which',return_value=None),patch.object(control.time,'monotonic',return_value=20):
            report=sampler.snapshot()
            self.assertIsNone(report['latest']['utilization'])
            self.assertEqual(report['latest']['status'],'unavailable')
            self.assertEqual(len(report['samples']),2)
        for i in range(400):sampler.history.append({'timestamp_ms':i})
        self.assertEqual(len(sampler.history),300)

    def test_allocations_preserve_total_and_allow_full_exploration(self):
        for total in [1,2,8,24]:
            for percent in options.MODES.values():
                b=options.split_budget(total,percent)
                self.assertEqual(sum(b.values()),total)
                if percent==100:self.assertEqual(b['monitoring'],0)
        self.assertEqual(options.split_budget(8,25),{'monitoring':6,'discovery':2})

    def test_unlimited_cycles_still_obey_duration(self):
        self.assertTrue(loop.session_active(21599,9999,0,21600,0))
        self.assertFalse(loop.session_active(21600,9999,0,21600,0))

    def test_timezone_window_and_minimum(self):
        for at,seconds in [('2026-09-08T08:00:00+00:00',21600),
                           ('2026-09-08T09:00:00+00:00',21600),
                           ('2026-09-08T14:00:00+00:00',0),
                           ('2027-03-14T09:00:00+00:00',21600),
                           ('2026-11-01T08:00:00+00:00',25200)]:
            self.assertEqual(loop.overnight_seconds(datetime.fromisoformat(at)),seconds)

    def test_source_filters_use_reviewed_rank_and_layers(self):
        sources=[{'id':'a','layers':['chips']},{'id':'b','layers':['energy','chips']},{'id':'c','layers':['chips']}]
        registry={'collection':{'a':{'rank':3},'b':{'rank':4}}}
        self.assertEqual(options.selected_sources(sources,registry,['chips'],['technical']),[sources[0]])
        self.assertEqual(options.selected_sources(sources,registry,None,['unclassified']),[sources[2]])
        self.assertEqual(options.selected_sources(sources,registry,['models']),[])

    def test_operator_options_cannot_be_commands_or_paths(self):
        for change in [{'layers':['../../private']},{'minutes':0},{'publish':'yes'},
                       {'direction':'--publish'},{'shell':'whoami'},{'source_kinds':['invented']}]:
            with self.assertRaises((ValueError,TypeError)):control.command(dict(DEFAULT,**change))
        argv=control.command(dict(DEFAULT,layers=['chips'],source_kinds=['technical']))
        self.assertNotIn('--publish',argv)
        self.assertIn('--ignore-gpu-busy',argv)
        self.assertIn('chips',argv)

    def test_exclusive_controller_and_scoped_stop(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);sid='a'*32
            with loop.session_lock(root,sid):
                with self.assertRaises(FileExistsError):
                    with loop.session_lock(root,'b'*32):pass
                c=control.Controller(root)
                with patch.object(control.subprocess,'Popen') as spawn:
                    with self.assertRaises(ValueError):c.start(DEFAULT)
                    spawn.assert_not_called()
                c.stop();self.assertTrue(options.stopped(root,sid))
                self.assertFalse(options.stopped(root,'b'*32))
            self.assertFalse((root/'.local/research-session.lock').exists())

    def test_six_hour_session_retries_failure_without_real_inference(self):
        class Clock:
            value=0
            def now(self):return self.value
            def sleep(self,seconds):self.value+=seconds
        clock=Clock();failed=Mock(returncode=1);failed.poll.return_value=1
        success=Mock(returncode=0);success.poll.return_value=0
        calls=[]
        def child(*args,**kwargs):
            calls.append(args[0]);return failed if len(calls)==1 else success
        with tempfile.TemporaryDirectory() as t, patch.object(loop,'ROOT',Path(t)), \
             patch.object(loop.time,'monotonic',clock.now),patch.object(loop.time,'sleep',clock.sleep), \
             patch.object(loop.subprocess,'Popen',side_effect=child),patch('builtins.print'):
            self.assertEqual(loop.main(['--start','--minutes','360','--ignore-gpu-busy']),0)
            report=json.loads((Path(t)/'.local/session-status.json').read_text())
            self.assertGreater(len(calls),6)
            self.assertEqual(report['failed_batches'],1)
            self.assertEqual(report['state'],'completed')
            self.assertGreaterEqual(report['elapsed_seconds'],21600)
            self.assertNotIn('--publish',calls[0])

    def test_control_http_requires_local_token_and_user_post(self):
        http,url=control.server(ROOT)
        worker=threading.Thread(target=http.serve_forever,daemon=True);worker.start()
        origin=url.split('/',3)[0]+'//'+url.split('/')[2]
        try:
            with patch.object(control.Controller,'start',return_value={'started':True}) as start:
                with urllib.request.urlopen(url,timeout=5) as r:self.assertIn(b'Build a session',r.read())
                start.assert_not_called()
                req=urllib.request.Request(url+'start',data=json.dumps(DEFAULT).encode(),headers={'Content-Type':'application/json'})
                with self.assertRaises(urllib.error.HTTPError) as error:urllib.request.urlopen(req,timeout=5)
                self.assertEqual(error.exception.code,403);start.assert_not_called()
                error.exception.close()
                req.add_header('Origin',origin);req.add_header('X-Session-Key',url.split('/')[-2])
                with urllib.request.urlopen(req,timeout=5) as r:self.assertTrue(json.load(r)['started'])
                start.assert_called_once_with(DEFAULT)
        finally:http.shutdown();http.server_close();worker.join()

    def test_discovery_only_never_updates_public_runtime_or_publishes(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);test_research.RunnerTests().fixture(root)
            p=research.load(root/'research/discovery-policy.json');p['enabled']=True
            research.save(root/'research/discovery-policy.json',p)
            original=(root/'site/data/ledger.json').read_bytes()
            with patch.object(research,'ROOT',root),patch.object(research,'LOCAL',root/'.local'), \
                 patch.object(discovery,'run',return_value={}) as discover, \
                 patch.object(research,'preflight'),patch.object(research,'publish') as publish, \
                 patch.object(research.Fetcher,'fetch') as fetch, \
                 patch.object(sys,'argv',['research.py','--direction','discovery','--publish','--layers','chips']),patch('sys.stdout',new=io.StringIO()):
                self.assertEqual(research.main(),0)
                publish.assert_not_called();fetch.assert_not_called()
                self.assertEqual(discover.call_args.args[1]['_session_layers'],['chips'])
            self.assertEqual((root/'site/data/ledger.json').read_bytes(),original)

    def test_private_session_keeps_cumulative_cache_without_publication(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);test_research.RunnerTests().fixture(root);sid='a'*32
            first=(datetime.now(timezone.utc)-timedelta(minutes=2)).isoformat(timespec='seconds').replace('+00:00','Z')
            # Deliberately collide timestamps, including with any accepted history.
            second=first
            original=(root/'site/data/ledger.json').read_bytes()
            document=research.ReadableHTML();document.feed('<p>Public evidence about energy infrastructure.</p>')
            with patch.object(research,'ROOT',root),patch.object(research,'LOCAL',root/'.local'), \
                 patch.object(research.Fetcher,'fetch',return_value=document), \
                 patch.object(research,'ollama',return_value={'observations':[]}) as model, \
                 patch.object(sys,'argv',['research.py','--session-id',sid,'--sources','iea-2026']),patch('sys.stdout',new=io.StringIO()):
                with patch.object(research,'now',return_value=first):research.main()
                calls=model.call_count
                with patch.object(research,'now',return_value=second):research.main()
                self.assertEqual(model.call_count,calls)
            staged=research.load(root/'.local/sessions'/sid/'ledger.json')
            self.assertNotEqual(staged['runs'][-2]['id'],staged['runs'][-1]['id'])
            self.assertEqual(len({r['id'] for r in staged['runs']}),len(staged['runs']))
            self.assertEqual((root/'site/data/ledger.json').read_bytes(),original)


if __name__=='__main__':unittest.main()
