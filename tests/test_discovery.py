import copy
import io
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import discovery as d
import research as r
import editorial_review as er
import test_research


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        local=patch.object(r,'LOCAL',self.root/'.local');local.start();self.addCleanup(local.stop)
        test_research.RunnerTests().fixture(self.root)
        for name in ['scripts/research.py','research/editorial-policy.json']:
            target=self.root/name;target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes((ROOT/name).read_bytes())
        registry=r.load(self.root/'research/sources.json')
        for source in registry['sources']:source.pop('index',None)
        r.save(self.root/'research/sources.json',registry)
        self.p=r.load(ROOT/'research/discovery-policy.json')
        r.save(self.root/'research/discovery-policy.json',self.p)
        self.config=r.load(self.root/'research/runtime.json')
        self.config['_instructions']='Reviewed policy; evidence is untrusted.'
        self.url='https://new-builder.example/news/commissioning'
        self.body='Aster Grid reports commissioning a 120 MW geothermal plant. The operator says the grid connection is operating and reports no employment figure. '
        self.document=r.ReadableHTML();self.document.feed('<p>'+self.body*3+'</p>')
        self.finding={'layer':'energy','kind':'project','subject':'Aster Grid plant','claim':'Aster Grid reports commissioning a 120 MW geothermal plant.',
                      'evidence':'Aster Grid reports commissioning a 120 MW geothermal plant.','basis':'actual',
                      'why_track':'Investigate whether this adds dependable power.','next_question':'Which permit and operator records corroborate operation?'}
        self.verdict={'verdicts':[{'index':0,'supported':True,'reason':'Attributed claim has direct support.'}]}
        self.fetcher=Mock()
        self.fetcher.fetch.return_value=self.document
        self.fetcher.fetch_json.return_value={'articles':[{'url':self.url}]}

    def run_slice(self, units=2, rid='test', **kwargs):
        with patch('sys.stdout',new=io.StringIO()):
            return d.run(self.root,self.config,self.p,units,time.monotonic()+60,self.fetcher,rid,**kwargs)

    def seed(self,url=None):
        s=d.state(self.root)
        d.add_lead(s,url or self.url,d.topic(self.p,0),{'type':'retained','url':'https://known.example/report'},self.p,r.now())
        r.save(self.root/'.local/discovery/state.json',s)

    def model(self,*args):
        schema=args[3]
        if schema==d.SCHEMA:return {'findings':[self.finding],'reason':'Specific attributed candidate in fixture.'}
        if schema==r.VERDICT_SCHEMA:return self.verdict
        return {'observations':[]}

    def test_budget_reservation_and_focused_scope(self):
        self.assertEqual(d.budgets(24,self.p),{'monitoring':18,'discovery':6})
        self.assertEqual(d.budgets(8,self.p),{'monitoring':6,'discovery':2})
        self.assertEqual(d.budgets(1,self.p),{'monitoring':1,'discovery':0})
        self.assertEqual(d.budgets(24,self.p,True),{'monitoring':24,'discovery':0})
        for total in range(1,25):
            b=d.budgets(total,self.p)
            self.assertEqual(sum(b.values()),total)
            self.assertGreaterEqual(b['monitoring'],1)

    def test_rotation_covers_every_layer_region_topic_and_constraints(self):
        count=sum(map(len,self.p['layers'].values()))*2*len(self.p['regions'])
        topics=[d.topic(self.p,i) for i in range(count)]
        self.assertEqual({v['layer'] for v in topics[:5]},set(r.LAYERS))
        self.assertEqual({v['question'] for v in topics},{v['question'] for ts in self.p['layers'].values() for v in ts})
        self.assertEqual({v['region'] for v in topics},{v or 'global' for v in self.p['regions']})
        self.assertEqual({v['angle'] for v in topics},{'delivery','constraints'})
        self.assertTrue(any('delay OR shortage OR failure' in v['query'] for v in topics))

    def test_unsafe_urls_and_unsupported_formats_are_ineligible(self):
        for url in ['http://safe.example/a','https://127.0.0.1/a','https://localhost/a',
                    'https://name:secret@safe.example/a','https://safe.example/a?token=secret',
                    'https://safe.example:444/a','https://safe.example/%2e%2e/private',
                    'https://safe.example/login','https://safe.example/report.pdf','https://safe.example/a\\b']:
            with self.subTest(url=url),self.assertRaises(ValueError):d.canonical(url)
        self.assertEqual(d.canonical('https://NEW.example:443/news#part'),'https://new.example/news')
        with patch.object(r.socket,'getaddrinfo',return_value=[(0,0,0,'',('192.168.1.4',443))]):
            with self.assertRaises(ValueError):r.Fetcher().fetch(self.url)

    def test_json_adapter_cannot_be_pointed_to_an_arbitrary_api(self):
        with self.assertRaises(ValueError):r.Fetcher().fetch_json('https://attacker.example/api?key=secret')
        fetch=r.Fetcher()
        with patch.object(fetch,'check_robots',return_value='api.gdeltproject.org') as robots,patch.object(fetch,'get',return_value='{"articles": []}'):
            self.assertEqual(d.search(fetch,d.topic(self.p,0),5),[])
            self.assertIn('maxrecords=5',robots.call_args.args[0])
            self.assertIn('timespan=1month',robots.call_args.args[0])

    def test_offline_plan_and_status_do_not_fetch_or_write(self):
        before=set(self.root.rglob('*'))
        with patch.object(d,'ROOT',self.root),patch.object(r,'ollama') as model,patch.object(r,'Fetcher') as fetch,patch('sys.stdout',new=io.StringIO()):
            d.main([]);d.main(['--status']);d.main(['--documents','8'])
            model.assert_not_called();fetch.assert_not_called()
        self.assertEqual(before,set(self.root.rglob('*')))

    def test_new_host_screened_into_existing_private_queue_never_public(self):
        tracked={p:p.read_bytes() for folder in ['site','research'] for p in (self.root/folder).rglob('*') if p.is_file()}
        with patch.object(r,'ollama',side_effect=self.model):result=self.run_slice()
        self.assertEqual(result['proposals_queued'],1)
        self.assertEqual(result['model_calls'],2)
        self.assertEqual(result['units_used'],2)
        proposals=list(er.queue(self.root).glob('discovery-*.json'))
        self.assertEqual(len(proposals),1)
        proposal=r.load(proposals[0])
        self.assertEqual(proposal['kind'],'coverage_expansion')
        self.assertEqual(proposal['status'],'pending_review')
        self.assertIn('Unknown',proposal['authority'])
        self.assertEqual(er.events(self.root)[-1]['status'],'pending_review')
        self.assertTrue((self.root/'.local/discovery/digest.md').exists())
        for path,original in tracked.items():self.assertEqual(path.read_bytes(),original)
        self.assertNotIn('research/sources.json',r.ALLOWED_CHANGES)
        self.assertNotIn('research/discovery-policy.json',r.ALLOWED_CHANGES)

    def test_existing_backlog_is_consumed_deduplicated_and_follows_one_hop(self):
        src=next(s for s in r.load(self.root/'research/sources.json')['sources'] if s['layers'])
        r.save(self.root/'.local/discovery-leads/old.json',{'source':src['id'],'urls':[self.url,self.url,self.url+'/report.pdf']})
        self.document.links=['https://original.example/research/permit','https://extra.example/report']
        self.fetcher.fetch_json.return_value={'articles':[]}
        with patch.object(r,'ollama',return_value={'findings':[],'reason':'No supported new candidate in fixture.'}):receipt=self.run_slice()
        self.assertEqual(receipt['imported_leads'],1)
        leads=list(d.state(self.root)['leads'].values())
        self.assertEqual(len(leads),3)
        child=next(v for v in leads if v['depth']==1 and 'original.example' in v['url'])
        self.assertEqual(child['url'],'https://original.example/research/permit')
        with patch.object(r,'ollama',return_value={'findings':[],'reason':'No supported new candidate in fixture.'}):receipt=self.run_slice(rid='next')
        self.assertEqual(receipt['imported_leads'],0)
        self.assertEqual(len(d.state(self.root)['leads']),3)

    def test_unknown_backlog_ancestry_is_not_fetched(self):
        r.save(self.root/'.local/discovery-leads/unknown.json',{'source':'invented','urls':[self.url]})
        self.fetcher.fetch_json.return_value={'articles':[]}
        self.assertEqual(self.run_slice()['documents_fetched'],0)
        self.fetcher.fetch.assert_not_called()

    def test_provider_rate_limit_persists_across_topics_while_backlog_continues(self):
        from urllib.error import HTTPError
        from email.message import Message
        import collection_health
        self.seed()
        self.fetcher.fetch_json.side_effect=HTTPError('https://api.gdeltproject.org',429,'limited',Message(),None)
        with patch.object(collection_health.time,'time',return_value=1000),patch.object(r,'ollama',return_value={'findings':[],'reason':'No supported new candidate in fixture.'}):
            first=self.run_slice(rid='rate-limited')
            second=self.run_slice(rid='cooling')
        self.assertEqual(first['search_provider']['http_status'],429)
        self.assertGreaterEqual(first['documents_fetched'],1)
        self.assertEqual(second['search_skipped'],'provider_cooldown')
        self.assertEqual(self.fetcher.fetch_json.call_count,1)
        self.fetcher.fetch_json.side_effect=None
        self.fetcher.fetch_json.return_value={'articles':[]}
        with patch.object(collection_health.time,'time',return_value=20000),patch.object(r,'ollama',return_value={'findings':[],'reason':'No supported new candidate in fixture.'}):
            third=self.run_slice(rid='provider-recovered')
        self.assertEqual(third['search_provider']['status'],'available')
        self.assertEqual(self.fetcher.fetch_json.call_count,2)

    def test_rejected_query_does_not_mark_entire_provider_unavailable(self):
        import collection_health
        self.fetcher.fetch_json.side_effect=collection_health.QueryRejected('Search provider rejected query syntax')
        with patch.object(collection_health.time,'time',return_value=1000),patch.object(r,'ollama',return_value={'findings':[],'reason':'No supported new candidate in fixture.'}):
            first=self.run_slice(rid='bad-query')
        self.assertEqual(first['search_provider']['status'],'available')
        self.assertEqual(first['primary_index_leads'],0)
        with patch.object(collection_health.time,'time',return_value=1061),patch.object(r,'ollama',return_value={'findings':[],'reason':'No supported new candidate in fixture.'}):self.run_slice(rid='different-topic')
        self.assertEqual(self.fetcher.fetch_json.call_count,2)

    def test_source_failure_is_not_no_findings_and_has_backoff(self):
        self.fetcher.fetch.side_effect=OSError('remote secret text')
        result=self.run_slice()
        self.assertEqual(result['status'],'partial')
        self.assertEqual(result['errors'][0]['outcome'],'source_inaccessible')
        self.assertNotIn('remote secret',json.dumps(result))
        lead=next(iter(d.state(self.root)['leads'].values()))
        self.assertGreater(lead['next_attempt'],lead['last_attempt'])
        self.assertNotIn('processing_identity',lead)

    def test_search_failure_still_investigates_backlog(self):
        self.seed()
        self.fetcher.fetch_json.side_effect=OSError('provider unavailable')
        with patch.object(r,'ollama',return_value={'findings':[],'reason':'No supported new candidate in fixture.'}):result=self.run_slice()
        self.assertEqual(result['status'],'partial')
        self.assertEqual(result['documents_screened'],1)
        self.assertEqual(result['proposals_queued'],0)
        self.assertEqual(result['errors'][0]['stage'],'search')

    def test_model_failure_is_not_cached_or_classified_as_access_failure(self):
        with patch.object(r,'ollama',side_effect=TimeoutError):result=self.run_slice()
        self.assertEqual(result['errors'][0]['outcome'],'screen_failed')
        self.assertNotIn('processing_identity',next(iter(d.state(self.root)['leads'].values())))

    def test_unchanged_evidence_skips_model_but_changed_policy_rescreens(self):
        with patch.object(r,'ollama',side_effect=self.model):self.run_slice()
        def make_due():
            s=d.state(self.root)
            for v in s['leads'].values():v['next_attempt']='2000-01-01T00:00:00Z'
            r.save(self.root/'.local/discovery/state.json',s)
        make_due()
        with patch.object(r,'ollama') as model:
            result=self.run_slice(rid='unchanged');model.assert_not_called()
        self.assertEqual(result['attempts'][0]['outcome'],'unchanged')
        make_due();self.p['revisit_days']=8
        with patch.object(r,'ollama',side_effect=self.model) as model:
            result=self.run_slice(rid='policy-change');self.assertEqual(model.call_count,2)
        self.assertEqual(result['proposals_queued'],0)
        self.assertEqual(len(list(er.queue(self.root).glob('discovery-*.json'))),1)

    def test_malicious_or_unsupported_model_fields_never_queue(self):
        for change in [{'url':'https://attacker.example'}, {'claim':'Aster Grid reports 999 new jobs.'},
                       {'evidence':'This quotation does not appear in the actual source document.'}, {'basis':'approved'}]:
            finding=dict(self.finding,**change)
            lead={'context':d.topic(self.p,0)}
            with self.subTest(change=change),patch.object(r,'ollama',return_value={'findings':[finding],'reason':'Specific candidate in fixture.'}),self.assertRaises(ValueError):
                d.screen(self.root,self.config,self.p,lead,self.body,{'model_calls':0},time.monotonic()+10)

    def test_primary_indexes_are_available_when_search_is_healthy(self):
        registry=r.load(self.root/'research/sources.json')
        source=next(v for v in registry['sources'] if 'energy' in v['layers'])
        source['index']=True;r.save(self.root/'research/sources.json',registry)
        self.fetcher.fetch_json.return_value={'articles':[]}
        with patch.object(r,'ollama',return_value={'findings':[],'reason':'No supported new candidate in fixture.'}):result=self.run_slice()
        self.assertEqual(result['primary_index_leads'],1)
        self.fetcher.fetch.assert_called_once_with(source['url'])

    def test_actual_proposal_layer_and_operator_filter(self):
        lead={'url':self.url,'lineage':{},'context':d.topic(self.p,1)}
        self.assertEqual(lead['context']['layer'],'chips')
        with patch.object(r,'ollama',side_effect=self.model):
            result=d.screen(self.root,self.config,self.p,lead,self.body,{'model_calls':0},time.monotonic()+30)
        rid,_=d.enqueue(self.root,lead,result,r.digest(self.body),'fixture',r.now())
        self.assertEqual(r.load(er.queue(self.root)/(rid+'.json'))['layer'],'energy')
        filtered=dict(self.config,_session_layers=['chips'])
        with patch.object(r,'ollama',side_effect=self.model),self.assertRaises(ValueError):
            d.screen(self.root,filtered,self.p,lead,self.body,{'model_calls':0},time.monotonic()+30)

    def test_unsupported_documents_retained_as_gaps_not_fetched(self):
        s=d.state(self.root)
        self.assertFalse(d.add_lead(s,self.url+'/report.pdf',d.topic(self.p,0),{'type':'retained'},self.p,r.now()))
        self.assertEqual(len(s['collection_gaps']),1)
        self.assertEqual(len(s['leads']),0)
        self.assertTrue(d.add_lead(s,self.url+'/feed.xml',d.topic(self.p,0),{'type':'retained'},self.p,r.now()))

    def test_empty_and_rejected_findings_are_legitimate(self):
        with patch.object(r,'ollama',return_value={'findings':[],'reason':'No supported new candidate in fixture.'}):result=self.run_slice()
        self.assertEqual(result['attempts'][0]['outcome'],'no_findings')
        self.assertEqual(result['status'],'completed')
        self.assertEqual(result['proposals_queued'],0)
        self.verdict['verdicts'][0]['supported']=False
        with patch.object(r,'ollama',side_effect=self.model):result=self.run_slice(rid='rejected',refresh=True)
        # Refresh doesn't erase revisit backoff; force a due lead for rejection screening.
        s=d.state(self.root)
        for v in s['leads'].values():v['next_attempt']='2000-01-01T00:00:00Z'
        r.save(self.root/'.local/discovery/state.json',s)
        with patch.object(r,'ollama',side_effect=self.model):result=self.run_slice(rid='rejected-due',refresh=True)
        self.assertEqual(result['attempts'][0]['outcome'],'screen_rejected')
        self.assertEqual(result['proposals_queued'],0)

    def test_human_triage_cannot_approve_publication(self):
        with patch.object(r,'ollama',side_effect=self.model):self.run_slice()
        rid=r.load(next(er.queue(self.root).glob('discovery-*.json')))['id']
        for decision,human in [('approved',True),('investigate',False)]:
            with self.assertRaises(ValueError):d.record_review(self.root,rid,decision,'reedos','Review permit',r.now(),human_confirm=human)
        d.record_review(self.root,rid,'investigate','reedos','Review original permit',r.now(),human_confirm=True)
        self.assertEqual(er.events(self.root)[-1]['status'],'investigate')
        self.assertIn('investigate=1',(self.root/'.local/discovery/digest.md').read_text(encoding='utf-8'))
        with self.assertRaises(ValueError):er.apply(self.root,rid)

    def test_single_unit_batches_alternate_search_and_follow_up(self):
        with patch.object(r,'ollama',return_value={'findings':[],'reason':'No supported new candidate in fixture.'}):
            first=self.run_slice(1,'one');second=self.run_slice(1,'two')
        self.assertEqual((first['search_calls'],first['documents_fetched']),(1,0))
        self.assertEqual((second['search_calls'],second['documents_fetched']),(0,1))

    def test_deadline_and_model_budget_prevent_extra_calls(self):
        with patch.object(r,'ollama') as model,patch('sys.stdout',new=io.StringIO()):
            result=d.run(self.root,self.config,self.p,6,time.monotonic()-1,self.fetcher,'expired')
            model.assert_not_called();self.fetcher.fetch_json.assert_not_called()
        self.assertEqual(result['units_used'],0)
        self.p['max_model_calls']=2
        self.fetcher.fetch_json.return_value={'articles':[{'url':self.url},{'url':self.url+'-other'}]}
        with patch.object(r,'ollama',side_effect=self.model):result=self.run_slice(6,'bounded')
        self.assertEqual(result['model_calls'],2)
        self.assertEqual(result['documents_fetched'],1)

    def test_policy_and_active_agenda_are_validated(self):
        self.assertEqual(d.policy(self.root),self.p)
        self.assertIn('node-level',d.agenda(self.root))
        self.assertNotIn('Published in this expansion',d.agenda(self.root))
        bad=dict(self.p,auto_approve=True)
        r.save(self.root/'research/discovery-policy.json',bad)
        with self.assertRaises(ValueError):d.policy(self.root)

    def test_general_runner_e2e_shares_budget_but_separates_public_receipt(self):
        original=(self.root/'site/data/ledger.json').read_bytes()
        registry=r.load(self.root/'research/sources.json')
        monitor=[next(s for s in registry['sources'] if s['id']==sid) for sid in
                 ['iea-2026','tsmc-2025','msft-wisconsin','stanford-cost','stanford-2026']]
        with patch.object(r,'ROOT',self.root),patch.object(r,'LOCAL',self.root/'.local'),\
             patch.object(r,'Fetcher',return_value=self.fetcher),patch.object(r,'source_queue',return_value=monitor),\
             patch.object(r,'ollama',side_effect=self.model),patch.object(sys,'argv',['research.py','--max-documents','8']),\
             patch('sys.stdout',new=io.StringIO()):
            self.assertEqual(r.main(),0)
        public=r.load(self.root/'.local/proposed-ledger.json')
        private=r.load(self.root/'.local/discovery/latest.json')
        self.assertEqual(public['runs'][-1]['documents_fetched'],5)
        self.assertEqual(public['runs'][-1]['accepted'],0)
        self.assertEqual(private['proposals_queued'],1)
        self.assertLessEqual(public['runs'][-1]['documents_fetched']+private['units_used'],8)
        self.assertNotIn(self.url,{s['url'] for s in public['sources']})
        self.assertEqual((self.root/'site/data/ledger.json').read_bytes(),original)
        self.assertFalse((self.root/'.local/research.lock').exists())


if __name__=='__main__':unittest.main()
