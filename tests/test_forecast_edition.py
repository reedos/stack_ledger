"""Forecast editions, on fixture data of their own.

These tests never read the live ledger's figures: when the owner approves a real edition, the
preview and the publish gate run this suite against the projected ledger, and a test pinned to
today's MISO or Amazon figures would then fail its own approval (review finding, 09/23/2026).
"""
import copy
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import catalog_review
import forecast_edition as fe
import research
import validate
from publication_policy import eligible, policy as pub_policy

TEMPLATE='miso-coincident-peak-ltlf-gw'  # any energy metric that allows forecasts; only its shape is borrowed


def src(sid,published,url=None):
    return {'id':sid,'publisher':'Fixture Grid Operator','title':'Fixture report '+sid,'url':url or f'https://fixture.example/{sid}.pdf',
            'published':published,'layers':['energy'],'license':'Original source rights apply','provenance':'official'}


SOURCES=[src('fx-2024',"2024-12-01"),src('fx-2026','2026-05-13'),src('fx-mid','2025-06-01'),
         src('fx-feb','2026-02-05'),src('fx-jul','2026-07-30'),src('fx-oct','2026-09-01')]


def metrics_from(live):
    shape=next((m for m in live if m['id']==TEMPLATE),None) or next(m for m in live if m['layer']=='energy' and 'forecast' in (m.get('allowed_statuses') or []))
    base={k:v for k,v in shape.items() if k not in {'edition_mode','chart_companion_metric','chart_overlay_metric'}}
    trajectory=dict(base,id='fx-peak-gw',title='Fixture coincident peak',source_ids=['fx-2024','fx-2026','fx-mid'],edition_mode='trajectory',
                    scope='Fixture rolling forecast.',note='Fixture.')
    by_year=dict(base,id='fx-guidance-gw',title='Fixture guidance',source_ids=['fx-feb','fx-jul','fx-oct'],scope='Fixture guidance by year.',note='Fixture.')
    return [trajectory,by_year]


def curated(oid,metric,year,value,source,status='forecast',upper=None,precision='approx'):
    return {'id':oid,'metric':metric,'year':year,'period':str(year),'value':value,'upper':upper,'status':status,'source':source,
            'precision':precision,'retrieved_at':'2026-09-22T07:00:00Z','method':'curated','note':'Fixture.'}


OBSERVATIONS=[curated('fx-peak-2024','fx-peak-gw',2024,122,'fx-2024',status='observation'),
              curated('fx-peak-2044','fx-peak-gw',2044,152,'fx-2024',upper=186,precision='range'),
              curated('fx-guidance-2026','fx-guidance-gw',2026,220,'fx-jul')]


def rec(metric,year,value,source,upper=None,status='forecast',precision='approx'):
    return {'id':f'auto-{metric}-{year}-{value}','metric':metric,'year':year,'period':str(year),'value':value,'upper':upper,'status':status,
            'source':source,'precision':precision,'retrieved_at':'2026-09-22T09:00:00Z','method':'automated','note':'',
            'document_sha256':'a'*64,'evidence_sha256':'b'*64,'grade':'A'}


class ClassifyTests(unittest.TestCase):
    """The vintage error, every way it arrives."""
    def setUp(self):
        live=json.loads((ROOT/'research/catalog.json').read_text(encoding='utf-8'))['metrics']
        self.metrics={m['id']:m for m in metrics_from(live)};self.sources={s['id']:s for s in SOURCES}

    def classify(self,record,source):
        return fe.classify(record,source,OBSERVATIONS,SOURCES,self.metrics[record['metric']])

    def test_a_newer_edition_of_a_rolling_forecast_is_held_whatever_its_years(self):
        self.assertEqual(self.classify(rec('fx-peak-gw',2046,184,'fx-2026'),self.sources['fx-2026']),'new')

    def test_an_earlier_release_from_the_same_year_is_older_not_new(self):
        # 09/22: February's $200B plan against July's $220B guidance. Both are 2026 documents.
        self.assertEqual(self.classify(rec('fx-guidance-gw',2026,200,'fx-feb'),self.sources['fx-feb']),'older')

    def test_an_older_edition_is_refused_by_the_year_in_its_file_name(self):
        child={'id':'discovered-0123456789abcdef','url':'https://fixture.example/media/2229/2023-itp-report.pdf','published':None}
        self.assertEqual(self.classify(rec('fx-peak-gw',2043,70,child['id']),child),'older')

    def test_documents_that_cannot_be_ordered_are_not_held_as_new(self):
        undated={'id':'discovered-1111111111111111','url':'https://fixture.example/listing','published':None}
        self.assertEqual(self.classify(rec('fx-peak-gw',2046,184,undated['id']),undated),'unordered')
        same_year={'id':'discovered-2222222222222222','url':'https://fixture.example/2026-guidance-deck.pdf','published':None}
        self.assertEqual(self.classify(rec('fx-guidance-gw',2026,230,same_year['id']),same_year),'unordered')

    def test_publisher_paths_give_the_day(self):
        self.assertEqual(fe.edition_date({'url':'https://www.ercot.com/files/docs/2026/12/22/Report.pdf'}),(fe.date(2026,12,22),'day'))
        self.assertEqual(fe.edition_date({'url':'https://www.pjm.com/-/media/las/2026/20260826/20260826-item-03---x.pdf'}),(fe.date(2026,8,26),'day'))
        self.assertEqual(fe.edition_date({'url':'https://www.spp.org/media/2429/2025-itp-report-v10.pdf'}),(2025,'year'))
        self.assertEqual(fe.edition_date({'url':'https://example.org/a','published':'2026-07-30'}),(fe.date(2026,7,30),'day'))

    def test_the_same_document_url_or_day_is_not_a_new_edition(self):
        self.assertIsNone(self.classify(rec('fx-peak-gw',2030,140,'fx-2024'),self.sources['fx-2024']))
        link=dict(self.sources['fx-2024'],id='discovered-3333333333333333')  # a listing's link to the same file
        self.assertIsNone(self.classify(rec('fx-peak-gw',2030,140,link['id']),link))
        same_day=src('fx-jul-deck','2026-07-30')
        self.assertIsNone(self.classify(rec('fx-guidance-gw',2026,221,same_day['id']),same_day))

    def test_by_year_guidance_replaces_only_the_year_it_restates(self):
        self.assertEqual(self.classify(rec('fx-guidance-gw',2026,240,'fx-oct'),self.sources['fx-oct']),'new')
        self.assertIsNone(self.classify(rec('fx-guidance-gw',2027,260,'fx-oct'),self.sources['fx-oct']))

    def test_an_older_document_does_not_start_a_year_beside_a_newer_edition(self):
        # IEA 2025 giving 2035 while the 2026 edition is on the chart: two editions on one line.
        self.assertEqual(self.classify(rec('fx-guidance-gw',2035,300,'fx-feb'),self.sources['fx-feb']),'older')
        self.assertIsNone(self.classify(rec('fx-guidance-gw',2035,300,'fx-oct'),self.sources['fx-oct']))

    def test_a_discovered_file_is_dated_by_its_filing_path_not_its_first_printed_date(self):
        child={'id':'discovered-4444444444444444','parent_source':'fx-index','published':'2025-12-01',
               'url':'https://www.pjm.com/-/media/las/2025/20251027/20251027-item-03---summary.pdf'}
        self.assertEqual(fe.edition_date(child),(fe.date(2025,10,27),'day'))
        registered=dict(child,parent_source=None);registered.pop('parent_source')
        self.assertEqual(fe.edition_date(registered),(fe.date(2025,12,1),'day'),'a reviewed date still wins for a registered source')

    def test_the_same_value_worded_differently_is_a_restatement_not_a_split(self):
        m=self.metrics['fx-peak-gw']
        a=rec('fx-peak-gw',2044,152,'fx-2026',upper=186,precision='range');b=dict(a,status='company-commitment',precision='approx',period='2044 central')
        self.assertTrue(fe.restates(b,OBSERVATIONS,m))
        self.assertEqual(fe.split_slots([a,b],m),set())
        self.assertEqual(fe.split_slots([a,dict(a,value=150)],m),{(2044,)})

    def test_quotes_lose_markup_and_secret_shapes(self):
        cleaned=fe.clean('the cost bearer of upgrades <x>',100)
        self.assertNotIn('<',cleaned);self.assertNotIn('bearer of',cleaned)
        validate.text(cleaned,100)  # passes the reviewed-text rules enqueue applies

    def test_actuals_are_untouched(self):
        self.assertIsNone(self.classify(rec('fx-peak-gw',2025,121,'fx-2026',status='observation'),self.sources['fx-2026']))


class Fixture(unittest.TestCase):
    """A temporary checkout: the real reviewed files plus the fixture metrics, sources and figures."""
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        for folder in ['research','site/data']:
            (self.root/folder).mkdir(parents=True,exist_ok=True)
            for f in (ROOT/folder).glob('*.json'):shutil.copy(f,self.root/folder/f.name)
        read=lambda p:json.loads((self.root/p).read_text(encoding='utf-8'))
        write=lambda p,v:(self.root/p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        catalog=read('research/catalog.json');ledger=read('site/data/ledger.json');registry=read('research/sources.json')
        extra=metrics_from(catalog['metrics'])
        catalog['metrics']+=copy.deepcopy(extra);ledger['metrics']=copy.deepcopy(catalog['metrics'])
        registry['sources']+=copy.deepcopy(SOURCES);ledger['sources']+=copy.deepcopy(SOURCES);ledger['observations']+=copy.deepcopy(OBSERVATIONS)
        write('research/catalog.json',catalog);write('site/data/ledger.json',ledger);write('research/sources.json',registry)
        for target,module in [('git',catalog_review)]:
            p=patch.object(module,target,return_value='0'*40);p.start();self.addCleanup(p.stop)
        p=patch.object(validate,'ROOT',self.root);p.start();self.addCleanup(p.stop)
        self.metrics={m['id']:m for m in ledger['metrics']};self.sources={s['id']:s for s in ledger['sources']}

    def ledger(self):return json.loads((self.root/'site/data/ledger.json').read_text(encoding='utf-8'))

    def hold(self,source_id='fx-2026',rows=None):
        rows=rows or [('Peak load grows from 124 GW in 2026 to 184 GW by 2046 <in the current case>,',rec('fx-peak-gw',2046,184,source_id)),
                      ('The current trajectory reaches 163 GW by 2035 in the central case.',rec('fx-peak-gw',2035,163,source_id))]
        held=[({'evidence':q},r,{'index':i,'supported':True,'defect':None,'reason':'ok'}) for i,(q,r) in enumerate(rows)]
        text='[Page 1]\nPeak load grows from 124 GW in 2026 to 184 GW by 2046, in the current case.\n'*3
        return fe.hold(self.root/'.local',self.sources[source_id],text,held,self.metrics,lambda q:4)

    def apply(self,p):
        """What 'Approve and publish' writes, without git."""
        for rel,value in catalog_review.projected(p,catalog_review.base(self.root)).items():
            (self.root/rel).parent.mkdir(parents=True,exist_ok=True)
            (self.root/rel).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


class EditionPackageTests(Fixture):
    def test_a_held_edition_becomes_one_package_that_retires_the_old_edition(self):
        self.assertEqual(len(self.hold()),1)
        self.assertEqual(self.hold(),[],'the same held edition is never raised twice')
        packaged=fe.materialize(self.root);self.assertEqual(len(packaged),1)
        p=catalog_review.package(self.root,packaged[0])
        self.assertEqual(p['author'],fe.AUTHOR)
        projected=catalog_review.projected(p,catalog_review.base(self.root))['site/data/ledger.json']
        by_id={o['id']:o for o in projected['observations']}
        replacement=by_id[by_id['fx-peak-2044']['superseded_by']]
        self.assertEqual((replacement['year'],replacement['value']),(2046,184))
        self.assertEqual(replacement['edition_supersedes'],['fx-peak-2044'])
        self.assertIn('New edition',replacement['correction_reason'])
        self.assertNotIn('superseded_by',by_id['fx-peak-2024'],'an actual is not part of a forecast edition')
        validate.validate(projected)
        self.assertIn('‹in the current case›',p['evidence'][0]['summary'],'markup in a quote is neutralised, not fatal')
        self.assertIn('p. 4',p['evidence'][0]['summary'])
        pol=copy.deepcopy(pub_policy(ROOT));pol['auto_apply']['enabled']=True;pol['auto_apply']['authors']=[fe.AUTHOR]
        ok,reasons=eligible(p,pol,json.loads((self.root/'research/sources.json').read_text(encoding='utf-8')))
        self.assertFalse(ok);self.assertIn('forecast edition',reasons[0])

    def test_broken_or_self_referencing_edition_links_are_refused(self):
        self.hold();p=catalog_review.package(self.root,fe.materialize(self.root)[0])
        projected=catalog_review.projected(p,catalog_review.base(self.root))['site/data/ledger.json']
        new=next(o for o in projected['observations'] if o['metric']=='fx-peak-gw' and o.get('edition_supersedes'))
        broken=copy.deepcopy(projected);next(o for o in broken['observations'] if o['id']==new['id'])['edition_supersedes']=['fx-guidance-2026']
        with self.assertRaisesRegex(ValueError,'Broken'):validate.validate(broken)
        same=copy.deepcopy(projected)
        for o in same['observations']:
            if o['id']=='fx-peak-2044':o.update(source=new['source'],document_sha256=new['document_sha256'])
        with self.assertRaisesRegex(ValueError,'different document'):validate.validate(same)

    def test_an_edition_overtaken_by_a_newer_one_is_obsolete_not_proposed_backwards(self):
        # Two editions held; the newer is approved first. The older must not then replace it.
        self.hold('fx-2026');p=catalog_review.package(self.root,fe.materialize(self.root)[0])
        self.hold('fx-mid',[('The 2025 edition expects 170 GW by 2045 in the base case today.',rec('fx-peak-gw',2045,170,'fx-mid'))])
        self.apply(p)
        with patch.object(catalog_review,'last_review',return_value={'status':'approved'}):fe.materialize(self.root)
        items={json.loads(f.read_text(encoding='utf-8'))['source']['id']:json.loads(f.read_text(encoding='utf-8'))
               for f in (self.root/'.local/review-candidates').glob('edition-*.json')}
        self.assertEqual(items['fx-mid']['status'],'obsolete')
        self.assertEqual(items['fx-2026']['status'],'applied')

    def events(self):
        path=self.root/'.local/review-candidates/editorial-events.jsonl'
        return [json.loads(l) for l in path.read_text(encoding='utf-8').splitlines()] if path.exists() else []

    def test_a_stale_package_is_withdrawn_and_proposed_again_once(self):
        # Two documents' editions for two metrics share nothing, but the files move under a pending
        # package when anything it touches changes: here the old figure gains a sibling correction.
        self.hold();first=fe.materialize(self.root)[0]
        ledger=self.ledger()
        for o in ledger['observations']:
            if o['id']=='fx-peak-2044':o['note']='Fixture, reworded.'
        (self.root/'site/data/ledger.json').write_text(json.dumps(ledger,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        second=fe.materialize(self.root)
        self.assertEqual(len(second),1);self.assertNotEqual(second[0],first)
        self.assertEqual([(e['id'],e['status']) for e in self.events()],[(first,'withdrawn')])
        self.assertEqual(fe.materialize(self.root),[],'a current package is left for the owner, not proposed again')
        inbox={p['id']:p['status'] for p in catalog_review.inbox(self.root)}
        self.assertEqual((inbox[first],inbox[second[0]]),('withdrawn','pending_review'))

    def test_a_deferred_package_that_goes_stale_is_proposed_again(self):
        self.hold();first=fe.materialize(self.root)[0]
        from editorial_review import append_event
        append_event(self.root,{'id':first,'kind':'catalog_change','status':'deferred','reviewer':'owner','at':'2026-09-22T10:00:00Z'})
        ledger=self.ledger();next(o for o in ledger['observations'] if o['id']=='fx-peak-2044')['note']='Moved.'
        (self.root/'site/data/ledger.json').write_text(json.dumps(ledger,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        self.assertEqual(len(fe.materialize(self.root)),1)

    def test_a_rejected_package_stays_rejected(self):
        self.hold();first=fe.materialize(self.root)[0]
        from editorial_review import append_event
        append_event(self.root,{'id':first,'kind':'catalog_change','status':'rejected','reviewer':'owner','at':'2026-09-22T10:00:00Z'})
        ledger=self.ledger();next(o for o in ledger['observations'] if o['id']=='fx-peak-2044')['note']='Moved.'
        (self.root/'site/data/ledger.json').write_text(json.dumps(ledger,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        self.assertEqual(fe.materialize(self.root),[])

    def test_a_figure_another_file_cites_is_not_retired_without_a_maintainer(self):
        (self.root/'research/fixture-citation.json').write_text('{"baseline": "fx-peak-2044"}\n',encoding='utf-8')
        self.hold();self.assertEqual(fe.materialize(self.root),[])
        item=json.loads(next((self.root/'.local/review-candidates').glob('edition-*.json')).read_text(encoding='utf-8'))
        self.assertEqual(item['status'],'needs_maintainer');self.assertIn('fixture-citation.json',item['reason'])
        self.assertEqual(fe.blocked(self.root),1)

    def test_a_hold_that_only_restates_the_chart_is_obsolete(self):
        self.hold(rows=[('Peak load reaches 152 to 186 GW in 2044 in the range given.',rec('fx-peak-gw',2044,152,'fx-2026',upper=186,precision='range'))])
        self.assertEqual(fe.materialize(self.root),[])
        item=json.loads(next((self.root/'.local/review-candidates').glob('edition-*.json')).read_text(encoding='utf-8'))
        self.assertEqual(item['status'],'obsolete')

    def test_a_failed_hold_is_counted_and_retried_only_when_the_files_change(self):
        self.hold()
        with patch.object(fe,'changes_for',side_effect=ValueError('Object changed since proposal')) as failing:
            fe.materialize(self.root);fe.materialize(self.root)
        self.assertEqual(failing.call_count,1,'unchanged files: no retry')
        self.assertEqual(fe.blocked(self.root),1)
        ledger=self.ledger();ledger['observations'].append(curated('fx-guidance-2027','fx-guidance-gw',2027,250,'fx-oct'))
        (self.root/'site/data/ledger.json').write_text(json.dumps(ledger,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        self.assertEqual(len(fe.materialize(self.root)),1,'retried and packaged once the files changed')
        self.assertEqual(fe.blocked(self.root),0)


class RunnerHoldTests(Fixture):
    """extract_observations holds a newer edition and sets aside everything that is not one."""
    def extract(self,source_id,candidates,document):
        data=self.ledger();metrics={m['id']:m for m in data['metrics']};sources={s['id']:s for s in data['sources']}
        replies=iter([{'observations':candidates},{'verdicts':[{'index':i,'supported':True,'reason':'Direct support.'} for i in range(len(candidates))]}])
        quarantine=[];collection={};before=len(data['observations'])
        with patch.object(research,'LOCAL',self.root/'.local'),patch.object(research,'ollama',side_effect=lambda *a,**k:next(replies)):
            accepted=research.extract_observations({'_instructions':'i','_coverage':'c','max_candidates_per_document':8},sources[source_id],document,
                [metrics[candidates[0]['metric']]],data,metrics,sources,{'model_calls':0},quarantine,collection)
        self.assertEqual(len(data['observations']),before+len(accepted))
        holds=[json.loads(f.read_text(encoding='utf-8')) for f in (self.root/'.local/review-candidates').glob('edition-*.json')] if (self.root/'.local/review-candidates').exists() else []
        return accepted,quarantine,holds

    def cand(self,metric,year,value,quote,upper=None,precision='approx'):
        return {'metric':metric,'year':year,'period':str(year),'value':value,'upper':upper,'status':'forecast','precision':precision,'note':'','evidence':quote}

    DOC='The operator projects coincident peak load to grow from 124 GW in 2026 to 184 GW by 2046, while 2044 reaches 152 to 186 GW in the range.'

    def test_a_newer_edition_is_held_not_published(self):
        accepted,quarantine,holds=self.extract('fx-2026',[self.cand('fx-peak-gw',2046,184,'grow from 124 GW in 2026 to 184 GW by 2046')],self.DOC)
        self.assertEqual(accepted,[]);self.assertEqual(quarantine,[])
        self.assertEqual([[r['record']['value'] for r in h['records']] for h in holds],[[184]])

    def test_a_document_that_only_restates_the_chart_is_a_duplicate(self):
        accepted,quarantine,holds=self.extract('fx-2026',[self.cand('fx-peak-gw',2044,152,'while 2044 reaches 152 to 186 GW in the range',186,'range')],self.DOC)
        self.assertEqual((accepted,quarantine,holds),([],[],[]))

    def test_two_figures_for_one_year_from_one_document_are_not_held(self):
        doc=self.DOC+' A high case puts the 2046 peak at 190 GW instead of the central value.'
        cands=[self.cand('fx-peak-gw',2046,184,'grow from 124 GW in 2026 to 184 GW by 2046'),
               self.cand('fx-peak-gw',2046,190,'A high case puts the 2046 peak at 190 GW instead')]
        accepted,quarantine,holds=self.extract('fx-2026',cands,doc)
        self.assertEqual(holds,[])
        self.assertEqual({q['reason'] for q in quarantine},{fe.REASONS['split']})

    def test_an_earlier_release_from_the_same_year_is_set_aside(self):
        doc='We expect capital spending of about 200 GW-equivalent in 2026 across the company this year.'
        accepted,quarantine,holds=self.extract('fx-feb',[self.cand('fx-guidance-gw',2026,200,'capital spending of about 200 GW-equivalent in 2026')],doc)
        self.assertEqual(holds,[]);self.assertEqual([q['reason'] for q in quarantine],[fe.REASONS['older']])

    def test_an_edition_left_with_only_restatements_after_screening_is_not_held(self):
        # The verifier rejects the one changed figure; the restated one alone must not become a package.
        cands=[self.cand('fx-peak-gw',2046,184,'grow from 124 GW in 2026 to 184 GW by 2046'),
               self.cand('fx-peak-gw',2044,152,'while 2044 reaches 152 to 186 GW in the range',186,'range')]
        data=self.ledger();metrics={m['id']:m for m in data['metrics']};sources={s['id']:s for s in data['sources']}
        replies=iter([{'observations':cands},{'verdicts':[{'index':0,'supported':False,'reason':'The quoted figure is a different scenario.'},
                                                          {'index':1,'supported':True,'reason':'Direct support.'}]}])
        quarantine=[]
        with patch.object(research,'LOCAL',self.root/'.local'),patch.object(research,'ollama',side_effect=lambda *a,**k:next(replies)):
            research.extract_observations({'_instructions':'i','_coverage':'c','max_candidates_per_document':8},sources['fx-2026'],self.DOC,
                [metrics['fx-peak-gw']],data,metrics,sources,{'model_calls':0},quarantine,{})
        self.assertFalse((self.root/'.local/review-candidates').exists() and list((self.root/'.local/review-candidates').glob('edition-*.json')))

    def test_monitoring_cannot_publish_an_edition_link(self):
        head=self.ledger();after=copy.deepcopy(head)
        after['observations'].append(dict(rec('fx-peak-gw',2046,184,'fx-2026'),edition_supersedes=['fx-peak-2044']))
        excerpts=json.loads((self.root/'site/data/excerpts.json').read_text(encoding='utf-8'))
        with self.assertRaisesRegex(ValueError,'Monitoring cannot issue corrections'):
            research.validate_monitoring_delta(head,after,excerpts,excerpts)


if __name__=='__main__':
    unittest.main()
