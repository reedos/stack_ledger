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
        with tempfile.TemporaryDirectory() as t:
            clock=[0]
            def sleep(seconds):clock[0]+=seconds
            child=Mock(returncode=2);child.poll.return_value=2
            with patch.object(loop,'ROOT',Path(t)),patch.object(loop.time,'monotonic',side_effect=lambda:clock[0]), \
                 patch.object(loop.time,'sleep',side_effect=sleep),patch.object(loop.subprocess,'Popen',return_value=child) as spawn, \
                 patch('research_notify.notify_session',return_value={'status':'disabled'}),patch('builtins.print'):
                self.assertEqual(loop.main(['--start','--minutes','10','--ignore-gpu-busy']),0)
            report=json.loads((Path(t)/'.local/session-status.json').read_text())
            self.assertEqual(report['failed_batches'],0);self.assertEqual(spawn.call_count,2)

    def test_receipt_distinguishes_actual_findings_from_status_pushes(self):
        with tempfile.TemporaryDirectory() as t:
            folder=Path(t)
            for n,accepted in enumerate([1,0]):
                r.save(folder/'batches'/f'{n}.json',{'monitoring':{'documents_fetched':1,'accepted':accepted},'publication':'pushed',
                    'collection':{'documents':[{'sha256':'same'}],'cache_hits':n,'model_documents':1-n}})
            totals=notify.summary(folder)
            self.assertEqual(totals['finding_pushes'],1);self.assertEqual(totals['monitoring_only_pushes'],1)
            self.assertEqual(totals['unique_document_versions'],1);self.assertEqual(totals['cache_hits'],1)
            text=notify.message({'state':'completed','options':{'publish':True}},totals)
            self.assertIn('monitoring-only: 1',text)


if __name__=='__main__':unittest.main()
