"""Offline failure/cooldown regression cases; no network or model calls."""
import io
import json
import sys
import tempfile
import unittest
from email.message import Message
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.error import HTTPError

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import research as r
import research_loop as loop
import research_notify as notify
import collection_health as health
import discovery as d
import test_research


class CollectionTests(unittest.TestCase):
    def test_robots_unreachable_is_shared_across_pages_and_batches(self):
        # 5xx and 429 on robots.txt are "unreachable" (RFC 9309): fail closed and cool down.
        with tempfile.TemporaryDirectory() as t,patch.object(r,'LOCAL',Path(t)),patch.object(health.time,'time',return_value=1000):
            with patch.object(r.Fetcher,'get',side_effect=HTTPError('https://example.org/robots.txt',503,'Unavailable',Message(),None)) as get:
                with self.assertRaisesRegex(ValueError,'HTTP 503'):r.Fetcher().fetch('https://example.org/a')
                second=r.Fetcher()
                self.assertFalse(second.due('https://example.org/b'))
                with self.assertRaises(health.CoolingDown):second.fetch('https://example.org/b')
                self.assertEqual(get.call_count,1)
        with tempfile.TemporaryDirectory() as t,patch.object(r,'LOCAL',Path(t)):
            with patch.object(r.Fetcher,'get',side_effect=HTTPError('https://example.org/robots.txt',429,'Too Many',Message(),None)):
                with self.assertRaisesRegex(ValueError,'HTTP 429'):r.Fetcher().check_robots('https://example.org/a')

    def test_robots_4xx_permits_crawling_per_rfc_9309_and_is_recorded(self):
        # 359 of last session's 575 source failures were robots.txt 4xx responses from bot-hostile hosts.
        for code in (401,403,404,410):
            with self.subTest(code=code),tempfile.TemporaryDirectory() as t,patch.object(r,'LOCAL',Path(t)):
                f=r.Fetcher()
                with patch.object(f,'get',side_effect=HTTPError('https://example.org/robots.txt',code,'x',Message(),None)):
                    self.assertEqual(f.check_robots('https://example.org/a'),'example.org')
                record=f.health.get('robots','example.org')
                self.assertEqual(record['status'],'available');self.assertEqual(record['lines'],['User-agent: *','Allow: /'])
                self.assertIn('RFC 9309' if code!=404 else '',record.get('note',''))

    def test_contact_address_in_user_agent(self):
        self.assertIn('reedosaki@gmail.com',r.UA);self.assertIn('github.com/reedos/stack_ledger',r.UA)

    def test_cached_robots_still_enforces_disallow_and_expires(self):
        with tempfile.TemporaryDirectory() as t,patch.object(r,'LOCAL',Path(t)):
            with patch.object(health.time,'time',return_value=1000),patch.object(r.Fetcher,'get',return_value='User-agent: *\nDisallow: /private') as get:
                r.Fetcher().check_robots('https://example.org/public')
                with self.assertRaisesRegex(ValueError,'Blocked'):r.Fetcher().check_robots('https://example.org/private')
                self.assertEqual(get.call_count,1)
            with patch.object(health.time,'time',return_value=30000),patch.object(r.Fetcher,'get',return_value='User-agent: *\nDisallow: /') as get:
                with self.assertRaisesRegex(ValueError,'Blocked'):r.Fetcher().check_robots('https://example.org/public')
                get.assert_called_once()

    def test_html_robots_does_not_silently_allow_crawling(self):
        with tempfile.TemporaryDirectory() as t,patch.object(r,'LOCAL',Path(t)),patch.object(r.Fetcher,'get',return_value='<html>Challenge page</html>'):
            with self.assertRaisesRegex(ValueError,'Robots policy unavailable'):r.Fetcher().check_robots('https://example.org/a')

    def test_retry_after_survives_restart_and_is_not_ignored(self):
        with tempfile.TemporaryDirectory() as t,patch.object(health.time,'time',return_value=1000):
            path=Path(t)/'health.json';headers=Message();headers['Retry-After']='7200'
            error=HTTPError('https://api.gdeltproject.org',429,'limited',headers,None)
            health.Health(path).failure('provider','gdelt',error)
            state=health.Health(path)
            self.assertFalse(state.due('provider','gdelt'))
            self.assertEqual(state.get('provider','gdelt')['http_status'],429)
            self.assertEqual(state.get('provider','gdelt')['next_attempt'],8200)

    def test_recent_success_avoids_refetch_and_refresh_does_not_override_failure(self):
        with tempfile.TemporaryDirectory() as t,patch.object(r,'LOCAL',Path(t)):
            f=r.Fetcher();url='https://example.org/a'
            with patch.object(f,'get',side_effect=['User-agent: *\nAllow: /','<p>'+'Evidence about infrastructure. '*20+'</p>']):f.fetch(url)
            self.assertFalse(r.Fetcher().due(url));self.assertTrue(r.Fetcher().due(url,True))
            f.health.failure('page',url,TimeoutError())
            self.assertFalse(r.Fetcher().due(url,True))

    def test_conditional_headers_are_sent_and_a_304_response_counts_as_unchanged(self):
        # Deliverable 2/9: a fake HTTP response drives the real Fetcher.get/fetch code path
        # (not a mocked .get()), so the outgoing conditional headers are actually checked.
        class FakeResponse:
            def __init__(self,body,headers):self.body=body;self.headers=headers
            def read(self,n=None):return self.body
            def __enter__(self):return self
            def __exit__(self,*a):return False
        class FakeOpener:
            def __init__(self,responses):self.responses=list(responses);self.requests=[]
            def open(self,req,timeout=None):
                self.requests.append(req);result=self.responses.pop(0)
                if isinstance(result,Exception):raise result
                return result
        with tempfile.TemporaryDirectory() as t,patch.object(r,'LOCAL',Path(t)):
            f=r.Fetcher();url='https://example.org/a'
            robots_headers=Message();robots_headers['Content-Type']='text/plain'
            page_headers=Message();page_headers['Content-Type']='text/html; charset=utf-8'
            page_headers['ETag']='"abc123"';page_headers['Last-Modified']='Wed, 09 Sep 2026 00:00:00 GMT'
            page_body=('<p>'+'Evidence about infrastructure. '*20+'</p>').encode()
            first=FakeOpener([FakeResponse(b'User-agent: *\nAllow: /',robots_headers),FakeResponse(page_body,page_headers)])
            with patch.object(r,'build_opener',return_value=first):
                self.assertIsNotNone(f.fetch(url))
            state=f.fetch_state.get('page',url)
            self.assertEqual(state['etag'],'"abc123"');self.assertEqual(state['unchanged_streak'],0)
            # Robots is already cached in memory, so the second fetch is a single request; it
            # must carry the stored validators, and a 304 is unchanged: no hash, no model call
            # is possible from this alone, and the private streak advances.
            second=FakeOpener([HTTPError(url,304,'Not Modified',Message(),None)])
            with patch.object(r,'build_opener',return_value=second):
                with self.assertRaises(r.Unchanged):f.fetch(url)
            sent=second.requests[0]
            self.assertEqual(sent.get_header('If-none-match'),'"abc123"')
            self.assertEqual(sent.get_header('If-modified-since'),'Wed, 09 Sep 2026 00:00:00 GMT')
            self.assertEqual(f.fetch_state.get('page',url)['unchanged_streak'],1)

    def test_text_hash_fallback_when_a_host_ignores_conditional_validators(self):
        # Deliverable 2/3: a host that always answers 200 (no ETag/Last-Modified reused)
        # still gets flagged unchanged once the normalised readable text repeats -- boilerplate
        # (a different footer year) around identical evidence text does not count as a change.
        with tempfile.TemporaryDirectory() as t,patch.object(r,'LOCAL',Path(t)):
            f=r.Fetcher();url='https://example.org/b'
            evidence='<p>'+'Evidence about infrastructure. '*20+'</p>'
            with patch.object(f,'get',side_effect=['User-agent: *\nAllow: /','<footer>2025</footer>'+evidence]):
                f.fetch(url)
            self.assertFalse(f.last_text_unchanged)
            with patch.object(f,'get',side_effect=['<footer>2026 -- updated copyright</footer>'+evidence]):
                f.fetch(url)
            self.assertTrue(f.last_text_unchanged)
            self.assertEqual(f.fetch_state.get('page',url)['unchanged_streak'],1)

    def test_readable_text_hash_ignores_boilerplate_outside_the_document(self):
        a=r.ReadableHTML();a.feed('<nav>Menu 2025</nav><header>Site A</header><p>AI use reached 90 percent in 2026.</p><footer>Copyright A</footer>')
        b=r.ReadableHTML();b.feed('<nav>Different menu</nav><header>Site B</header><p>AI use reached 90 percent in 2026.</p><footer>Copyright B, 2026</footer>')
        self.assertEqual(r.digest(a.readable()),r.digest(b.readable()))

    def test_excess_search_results_are_capped_without_losing_valid_leads(self):
        fetcher=Mock();fetcher.fetch_json.return_value={'articles':[{'url':f'https://example.org/{i}'} for i in range(10)]}
        self.assertEqual(len(d.search(fetcher,{'query':'electricity grid'},5)),5)

    def test_search_plaintext_errors_are_classified_without_echoing_response(self):
        with tempfile.TemporaryDirectory() as t,patch.object(r,'LOCAL',Path(t)):
            f=r.Fetcher()
            with patch.object(f,'check_robots',return_value='api.gdeltproject.org'), \
                 patch.object(f,'get',return_value='One or more keywords were too short: private untrusted text'):
                with self.assertRaises(health.QueryRejected) as error:f.fetch_json('https://api.gdeltproject.org/api/v2/doc/doc?query=AI')
            self.assertNotIn('private untrusted',str(error.exception))

    def test_nothing_due_never_applies_or_publishes(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);test_research.RunnerTests().fixture(root);sid='a'*32
            original=(root/'site/data/ledger.json').read_bytes()
            with patch.object(r,'ROOT',root),patch.object(r,'LOCAL',root/'.local'),patch.object(r,'preflight'), \
                 patch.object(r.Fetcher,'due',return_value=False),patch.object(r.Fetcher,'fetch') as fetch, \
                 patch.object(r,'publish') as publish,patch.object(sys,'argv',['research.py','--publish','--session-id',sid]),patch('sys.stdout',new=io.StringIO()):
                self.assertEqual(r.main(),2);fetch.assert_not_called();publish.assert_not_called()
            self.assertEqual((root/'site/data/ledger.json').read_bytes(),original)

    def test_idle_controller_waits_without_counting_failure(self):
        # 2026-09-10: idle_pause_seconds defaults to 120 (runtime.json), down from the old
        # fixed 300s -- two pauses now span 4 minutes, not 10.
        with tempfile.TemporaryDirectory() as t:
            clock=[0]
            def sleep(seconds):clock[0]+=seconds
            child=Mock(returncode=2);child.poll.return_value=2
            with patch.object(loop,'ROOT',Path(t)),patch.object(loop.time,'monotonic',side_effect=lambda:clock[0]), \
                 patch.object(loop.time,'sleep',side_effect=sleep),patch.object(loop.subprocess,'Popen',return_value=child) as spawn, \
                 patch('research_notify.notify_session',return_value={'status':'disabled'}),patch('builtins.print'):
                self.assertEqual(loop.main(['--start','--minutes','4','--ignore-gpu-busy']),0)
            report=json.loads((Path(t)/'.local/session-status.json').read_text())
            self.assertEqual(report['failed_batches'],0);self.assertEqual(spawn.call_count,2)

    def test_three_consecutive_nothing_new_batches_end_the_session_early_when_opted_in(self):
        # Deliverable 7 (2026-09-09) still exists but is opt-in since deliverable 1
        # (2026-09-10): research.py writes {'status':'nothing_new'} into its batch receipt on
        # exit code 2 when nothing was new; research_loop reads that receipt (not just the
        # exit code, which an "everything unreachable" pause also uses) and, only with
        # end_session_when_idle:true in runtime.json, stops after three in a row -- never
        # counting them as failures.
        with tempfile.TemporaryDirectory() as t:
            (Path(t)/'research').mkdir(parents=True,exist_ok=True)
            (Path(t)/'research/runtime.json').write_text(json.dumps({'end_session_when_idle':True}),encoding='utf-8')
            clock=[0];calls=[0]
            def sleep(seconds):clock[0]+=seconds
            def fake_popen(command,**kwargs):
                calls[0]+=1
                sid=command[command.index('--session-id')+1]
                from research_loop import atomic
                atomic(Path(t)/'.local/sessions'/sid/'batches'/f'{calls[0]}.json',{'status':'nothing_new','monitoring':{},'collection':{}})
                child=Mock(returncode=2);child.poll.return_value=2
                return child
            with patch.object(loop,'ROOT',Path(t)),patch.object(loop.time,'monotonic',side_effect=lambda:clock[0]), \
                 patch.object(loop.time,'sleep',side_effect=sleep),patch.object(loop.subprocess,'Popen',side_effect=fake_popen), \
                 patch('research_notify.notify_session',return_value={'status':'disabled'}),patch('builtins.print'):
                self.assertEqual(loop.main(['--start','--minutes','60','--ignore-gpu-busy']),0)
            report=json.loads((Path(t)/'.local/session-status.json').read_text())
            self.assertEqual(report['state'],'completed (nothing new)')
            self.assertEqual(report['consecutive_nothing_new'],3)
            self.assertEqual(report['idle_passes'],3)
            self.assertEqual(report['failed_batches'],0)
            self.assertEqual(calls[0],3)  # ended after exactly three, not the full duration

    def test_default_settings_keep_exploring_through_repeated_nothing_new_batches(self):
        # Deliverable 1 (2026-09-10): end_session_when_idle defaults false -- a session that
        # has read everything once keeps polling until its own deadline instead of stopping
        # after three consecutive nothing_new batches. idle_passes counts every one of them,
        # never resetting, so the digest can say how much of the session found nothing;
        # consecutive_nothing_new is still tracked but no longer ends the session by itself.
        with tempfile.TemporaryDirectory() as t:
            clock=[0];calls=[0]
            def sleep(seconds):clock[0]+=seconds
            def fake_popen(command,**kwargs):
                calls[0]+=1
                sid=command[command.index('--session-id')+1]
                from research_loop import atomic
                atomic(Path(t)/'.local/sessions'/sid/'batches'/f'{calls[0]}.json',{'status':'nothing_new','monitoring':{},'collection':{}})
                child=Mock(returncode=2);child.poll.return_value=2
                return child
            with patch.object(loop,'ROOT',Path(t)),patch.object(loop.time,'monotonic',side_effect=lambda:clock[0]), \
                 patch.object(loop.time,'sleep',side_effect=sleep),patch.object(loop.subprocess,'Popen',side_effect=fake_popen), \
                 patch('research_notify.notify_session',return_value={'status':'disabled'}),patch('builtins.print'):
                self.assertEqual(loop.main(['--start','--minutes','10','--ignore-gpu-busy']),0)
            report=json.loads((Path(t)/'.local/session-status.json').read_text())
            self.assertEqual(report['state'],'completed')
            self.assertGreater(report['consecutive_nothing_new'],3)  # kept counting past the old cutoff
            self.assertEqual(report['idle_passes'],calls[0])
            self.assertEqual(report['failed_batches'],0)
            self.assertGreater(calls[0],3)  # kept going well past the old three-batch cutoff

    def test_an_unreachable_pause_batch_does_not_count_toward_nothing_new(self):
        # The pre-existing "every due source unreachable" pause also exits 2, but writes no
        # 'status' key at all -- it must not be confused with deliverable 7's nothing_new.
        with tempfile.TemporaryDirectory() as t:
            clock=[0]
            def sleep(seconds):clock[0]+=seconds
            child=Mock(returncode=2);child.poll.return_value=2
            with patch.object(loop,'ROOT',Path(t)),patch.object(loop.time,'monotonic',side_effect=lambda:clock[0]), \
                 patch.object(loop.time,'sleep',side_effect=sleep),patch.object(loop.subprocess,'Popen',return_value=child), \
                 patch('research_notify.notify_session',return_value={'status':'disabled'}),patch('builtins.print'):
                self.assertEqual(loop.main(['--start','--minutes','4','--ignore-gpu-busy']),0)
            report=json.loads((Path(t)/'.local/session-status.json').read_text())
            self.assertNotEqual(report['state'],'completed (nothing new)')
            self.assertEqual(report.get('consecutive_nothing_new',0),0)
            self.assertEqual(report.get('idle_passes',0),0)

    def test_receipt_distinguishes_actual_findings_from_status_pushes(self):
        with tempfile.TemporaryDirectory() as t:
            folder=Path(t)
            for n,accepted in enumerate([1,0]):
                r.save(folder/'batches'/f'{n}.json',{'monitoring':{'documents_fetched':1,'accepted':accepted},'publication':'pushed',
                    'collection':{'documents':[{'sha256':'same'}],'already_reviewed':n,'model_documents':1-n}})
            totals=notify.summary(folder)
            self.assertEqual(totals['finding_pushes'],1);self.assertEqual(totals['monitoring_only_pushes'],1)
            self.assertEqual(totals['unique_document_versions'],1);self.assertEqual(totals['already_reviewed'],1)
            text=notify.message({'state':'completed','options':{'publish':True}},totals)
            self.assertIn('monitoring-only: 1',text)


if __name__=='__main__':unittest.main()


class RefusedHostBackoffTests(unittest.TestCase):
    def test_403_backs_off_for_days_while_transient_errors_keep_the_six_hour_ceiling(self):
        import time as _time
        from urllib.error import HTTPError
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        h = health.Health(Path(temp.name)/'health.json')
        for _ in range(9): h.failure('source', 'https://blocked.example/page', HTTPError('https://blocked.example/page', 403, 'Forbidden', None, None))
        refused = h.get('source', 'https://blocked.example/page')
        self.assertTrue(refused['refused']); self.assertGreater(refused['next_attempt']-_time.time(), 6*3600)
        self.assertLessEqual(refused['next_attempt']-_time.time(), 3*86400+5)
        for _ in range(9): h.failure('source', 'https://flaky.example/page', TimeoutError('timed out'))
        flaky = h.get('source', 'https://flaky.example/page')
        self.assertNotIn('refused', flaky); self.assertLessEqual(flaky['next_attempt']-_time.time(), 6*3600+5)
        h.failure('source', 'https://robots.example/page', ValueError('Blocked by robots policy'))
        self.assertTrue(h.get('source', 'https://robots.example/page')['refused'])
