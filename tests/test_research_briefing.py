import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import research_briefing as brief
import research_notify as notify
import nightly

class BriefingTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.date='2026-09-15';self.sid='a'*32
        self.save('.local/research-control.json',{'tailnet':{'hostname':'reeds-pc.tailf68402.ts.net','mount':'/research','port':47395}})
    def save(self,name,value):
        path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value),encoding='utf-8')
    def session(self):
        self.save('.local/nightly/'+self.date+'/research.json',{'status':'ok','started_at':'2026-09-15T09:00:00Z','finished_at':'2026-09-15T14:00:00Z'})
        self.save('.local/sessions/'+self.sid+'/status.json',{'session_id':self.sid,'started_at':'2026-09-15T09:01:00Z','state':'completed','options':{'overnight':True}})
        batch={'monitoring':{'documents_fetched':1,'accepted':1,'source_failures':[{}]},'collection':{'documents':[{'url':'https://example.org/a','title':'A study','sha256':'abc','published':'2025-01-01'}]}}
        self.save('.local/sessions/'+self.sid+'/batches/1.json',batch)
        self.save('.local/sessions/'+self.sid+'/batches/2.json',batch)
    def test_counts_versions_not_repeated_fetches_and_separates_collection_health(self):
        self.session();data=brief.snapshot(self.root,self.date)
        self.assertEqual(len(data['documents']),1);self.assertEqual(data['totals']['documents'],2)
        self.assertEqual(data['outcome'],'partial');self.assertIn('Tuesday, September 15th, 2026',brief.render(data))
        # Into Almanac's Research view, which frames the panel (2026-09-16); the hash is URL-encoded
        # because it rides inside Almanac's own hash.
        self.assertTrue(data['links']['review'].endswith(':8788/#view=research&rp=%23run%3D2026-09-15'), data['links']['review'])
        self.assertTrue(data['links']['decisions'].endswith(':8788/#view=research&rp=%23decisions'))
    def test_manual_and_other_day_sessions_do_not_bleed_into_night(self):
        self.session()
        self.save('.local/sessions/'+'b'*32+'/status.json',{'session_id':'b'*32,'started_at':'2026-09-15T10:00:00Z','options':{'overnight':False}})
        self.save('.local/sessions/'+'c'*32+'/status.json',{'session_id':'c'*32,'started_at':'2026-09-14T10:00:00Z','options':{'overnight':True}})
        self.assertEqual(len(brief.snapshot(self.root,self.date)['sessions']),1)
    def test_a_missing_pdf_parser_is_a_watch_out_not_a_quiet_night(self):
        # Without pypdf every approved PDF silently returns to being a collection gap.
        self.session()
        self.save('.local/nightly/'+self.date+'/health.json',{'status':'partial','pdf_reader':{'status':'missing','parser':None}})
        data=brief.snapshot(self.root,self.date)
        self.assertEqual(data['outcome'],'partial')
        self.assertIn('Approved PDFs were not read',brief.render(data))
        self.save('.local/nightly/'+self.date+'/health.json',{'status':'ok','pdf_reader':{'status':'ok','parser':'pypdf 6.19.0'}})
        self.assertNotIn('Approved PDFs',brief.render(brief.snapshot(self.root,self.date)))

    def test_pdf_reader_health_reports_the_parser_and_the_approvals(self):
        root=Path(__file__).resolve().parents[1]
        with patch.dict(sys.modules,{'pypdf':None}):
            missing=nightly.pdf_reader(root)
        self.assertEqual(missing['status'],'missing')
        self.assertGreater(missing['approved']['documents'],0)
        try:
            import pypdf  # noqa: F401
        except ImportError:
            return
        self.assertEqual(nightly.pdf_reader(root)['status'],'ok')
        body={'date':self.date,'stage_receipts':{},'applied':[],'needs_decision':{},'site_changes':[],
              'health':{'pdf_reader':{'status':'missing','python':'python.exe'}}}
        self.assertIn('Approved PDFs could not be read',nightly.render_digest_markdown(body))

    def test_figures_held_back_are_a_watch_out(self):
        self.session()
        data=brief.snapshot(self.root,self.date);data['totals']['quarantined']=3
        self.assertIn('3 readings were held back or rejected',brief.render(data))
        self.assertEqual(brief.render(data).count('**Watch-outs**'),1)

    def test_automatic_same_page_revisions_are_named_in_the_briefing(self):
        self.session()
        new=lambda i,old,value:{'id':i,'metric':'revenue-fixture-forecast','period':'FY2027 · analyst consensus','value':value,'edition_supersedes':[old]}
        self.save('.local/review-candidates/catalog-'+'a'*24+'.json',{'author':'Same-page revision (research runner)','changes':[
            {'target':'observation','id':'n1','before':None,'after':new('n1','o1',411.49)},{'target':'observation','id':'o1','before':{'id':'o1','value':411.35},'after':{'id':'o1'}},
            {'target':'observation','id':'n2','before':None,'after':new('n2','o2',682.9)},{'target':'observation','id':'o2','before':{'id':'o2','value':682.87},'after':{'id':'o2'}},
            {'target':'source','id':'s','before':{'id':'s'},'after':{'id':'s'}}]})
        data=brief.snapshot(self.root,self.date,body={'applied':[{'kind':'catalog_change','id':'catalog-'+'a'*24,'outcome':'deployed'}]})
        text=brief.render(data)
        self.assertIn('2 figures on the site updated automatically',text)
        self.assertIn('revenue-fixture-forecast FY2027 · analyst consensus: 411.35 → 411.49',text,'the briefing says what changed, not only how many')

    def test_missing_is_not_zero_or_completed(self):
        data=brief.snapshot(self.root,self.date)
        self.assertEqual(data['outcome'],'not_recorded');self.assertIn('not recorded',brief.render(data))

    def test_live_reviews_override_saved_counts_without_changing_receipt(self):
        saved=brief.snapshot(self.root,self.date)
        saved['pending']=[dict(kind='catalog_packages_pending',label='catalog changes',count=47)]
        self.save('.local/briefings/'+self.date+'.json',saved)
        path=self.root/'.local/briefings'/(self.date+'.json');before=path.read_bytes()
        with patch.object(nightly,'pending_decisions',return_value=dict(catalog_packages_pending=0,questions_pending=5)):
            current=brief.live_snapshot(self.root,self.date)
        self.assertEqual(current['pending'],[])
        self.assertEqual(current['question_backlog'],5)
        self.assertEqual(current['pending_at_run'],saved['pending'])
        self.assertEqual(path.read_bytes(),before)
        with patch.object(nightly,'pending_decisions',return_value=dict(discovery_findings_pending=2,questions_pending=5)):
            self.assertEqual(brief.live_snapshot(self.root,self.date)['pending'][0]['count'],2)

    def test_live_review_failure_is_not_reported_as_caught_up(self):
        with patch.object(nightly,'pending_decisions',side_effect=ValueError('Incomplete records')):
            with self.assertRaises(ValueError):brief.live_snapshot(self.root,self.date)
    def test_skipped_run_does_not_claim_an_earlier_session(self):
        self.session();self.save('.local/nightly/'+self.date+'/research.json',{'status':'skipped','reason':'Another run holds the lock'})
        data=brief.snapshot(self.root,self.date);self.assertFalse(data['sessions']);self.assertEqual(data['outcome'],'skipped')
    def test_only_evidence_from_the_recorded_run_becomes_a_highlight(self):
        self.session();self.save('site/data/ledger.json',{'sources':[], 'events':[
            {'title':'Earlier event date preserved','document_sha256':'abc','retrieved_at':'2026-09-15T10:00:00Z','date':'2025-01-01','grade':'C'},
            {'title':'Unrelated','document_sha256':'other','retrieved_at':'2026-09-15T10:00:00Z'}]})
        data=brief.snapshot(self.root,self.date);self.assertEqual(len(data['highlights']),1)
        text=brief.render(data);self.assertIn('Unconfirmed report',text);self.assertIn('January 1st, 2025',text)
    def test_path_traversal_and_bad_dates_refused(self):
        for date in ('../secrets','2026-02-31','2026-09-15?x=1'):
            with self.assertRaises(ValueError):brief.snapshot(self.root,date)
    def test_digest_snapshot_is_complete_even_while_orchestrator_is_running(self):
        self.session();self.save('.local/nightly/'+self.date+'/live.json',{'pid':os.getpid(),'stage':'digest'})
        self.assertFalse(brief.snapshot(self.root,self.date,{})['active'])
    def test_matrix_sage_route_and_dated_dedup(self):
        self.save('.local/telegram-notifications.json',{'enabled':True,'channel':'matrix','role':'sage','briefing':True})
        path=self.root/'routes.json';path.write_text('{}')
        team=Mock();team.route.return_value={'account':'sage'};team.send.return_value='$sent'
        with patch.dict(os.environ,ARA_NOTIFICATION_ROUTES=str(path)),patch.dict(sys.modules,team_notifications=team):
            self.assertEqual(notify.send_text(self.root,'Brief','nightly-brief-'+self.date)['status'],'sent')
            self.assertEqual(notify.send_text(self.root,'Brief','nightly-brief-'+self.date)['status'],'already_attempted')
        team.send.assert_called_once_with('sage','Brief')
    def test_combined_digest_is_short_and_preserves_full_diagnostics(self):
        self.session();self.save('.local/telegram-notifications.json',{'briefing':True})
        with patch('research_notify.send_text',return_value={'status':'sent'}) as send,patch.object(nightly,'commits_ahead',return_value=0),patch.object(nightly,'site_changes',return_value=[]),patch.object(nightly,'published_observations',return_value={}):
            nightly.stage_digest(self.root,self.date)
        text=send.call_args.args[1]
        self.assertLess(len(text),2200);self.assertNotIn('```json',text);self.assertIn('Review this night',text)
        self.assertTrue((self.root/'.local/digest/2026-09-15.md').exists())

if __name__=='__main__':unittest.main()
