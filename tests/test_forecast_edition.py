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
         src('fx-feb','2026-02-05'),src('fx-jul','2026-07-30'),src('fx-oct','2026-09-01'),
         src('fx-page','2026-09-07',url='https://fixture.example/consensus/revenue')]


def metrics_from(live):
    shape=next((m for m in live if m['id']==TEMPLATE),None) or next(m for m in live if m['layer']=='energy' and 'forecast' in (m.get('allowed_statuses') or []))
    base={k:v for k,v in shape.items() if k not in {'edition_mode','chart_companion_metric','chart_overlay_metric'}}
    trajectory=dict(base,id='fx-peak-gw',title='Fixture coincident peak',source_ids=['fx-2024','fx-2026','fx-mid'],edition_mode='trajectory',
                    scope='Fixture rolling forecast.',note='Fixture.')
    by_year=dict(base,id='fx-guidance-gw',title='Fixture guidance',source_ids=['fx-feb','fx-jul','fx-oct'],scope='Fixture guidance by year.',note='Fixture.')
    consensus=dict(base,id='fx-consensus',title='Fixture consensus revenue',source_ids=['fx-page'],scope='Fixture consensus page.',note='Fixture.')
    return [trajectory,by_year,consensus]


def curated(oid,metric,year,value,source,status='forecast',upper=None,precision='approx'):
    return {'id':oid,'metric':metric,'year':year,'period':str(year),'value':value,'upper':upper,'status':status,'source':source,
            'precision':precision,'retrieved_at':'2026-09-22T07:00:00Z','method':'curated','note':'Fixture.'}


OBSERVATIONS=[curated('fx-peak-2024','fx-peak-gw',2024,122,'fx-2024',status='observation'),
              curated('fx-peak-2044','fx-peak-gw',2044,152,'fx-2024',upper=186,precision='range'),
              curated('fx-guidance-2026','fx-guidance-gw',2026,220,'fx-jul'),
              curated('fx-consensus-2026','fx-consensus',2026,67.14,'fx-page')]


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
        child={'id':'discovered-0123456789abcdef','url':'https://fixture.example/media/2229/2023-itp-report.pdf','published':None,'parent_source':'fx-index'}
        self.assertEqual(self.classify(rec('fx-peak-gw',2043,70,child['id']),child),'older')

    def test_documents_that_cannot_be_ordered_are_not_held_as_new(self):
        undated={'id':'discovered-1111111111111111','url':'https://fixture.example/listing','published':None}
        self.assertEqual(self.classify(rec('fx-peak-gw',2046,184,undated['id']),undated),'unordered')
        same_year={'id':'discovered-2222222222222222','url':'https://fixture.example/2026-guidance-deck.pdf','published':None,'parent_source':'fx-index'}
        self.assertEqual(self.classify(rec('fx-guidance-gw',2026,230,same_year['id']),same_year),'unordered')

    def test_publisher_paths_give_the_day(self):
        child=lambda url:{'url':url,'published':None,'parent_source':'fx-index'}
        self.assertEqual(fe.edition_date(child('https://www.ercot.com/files/docs/2026/12/22/Report.pdf')),(fe.date(2026,12,22),'day'))
        self.assertEqual(fe.edition_date(child('https://www.pjm.com/-/media/las/2026/20260826/20260826-item-03---x.pdf')),(fe.date(2026,8,26),'day'))
        self.assertEqual(fe.edition_date(child('https://www.spp.org/media/2429/2025-itp-report-v10.pdf')),(2025,'year'))
        # A registered source is dated by its reviewed date only: this file name names the year it forecasts.
        self.assertEqual(fe.edition_date({'url':'https://www.apollo.com/apollo-global-2026-credit-outlook.pdf','published':None}),(None,None))
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

    def test_a_page_that_changed_its_own_figure_is_a_revision(self):
        page=self.sources['fx-page'];r=rec('fx-consensus',2026,67.15,'fx-page')
        self.assertEqual(fe.classify(r,page,OBSERVATIONS,SOURCES,self.metrics['fx-consensus'],'Revenue estimate FY2026: 67.15'),'revision')
        # The page still shows the old number: still a revision, which settle_revisions hands to the
        # owner instead of quarantining it where a misread figure on the site could never be put right.
        self.assertEqual(fe.classify(r,page,OBSERVATIONS,SOURCES,self.metrics['fx-consensus'],'Estimate 67.15, previously 67.14'),'revision')
        self.assertIsNone(fe.classify(rec('fx-consensus',2026,67.14,'fx-page'),page,OBSERVATIONS,SOURCES,self.metrics['fx-consensus'],'Estimate 67.14'))
        self.assertIsNone(fe.classify(r,page,OBSERVATIONS,SOURCES,self.metrics['fx-consensus']),'no document, no revision')

    def test_a_pdf_never_revises_itself(self):
        # TSMC prints "USD60 billion": a misread of the same transcript must stay a conflict.
        page=self.sources['fx-page'];r=rec('fx-consensus',2026,70,'fx-page')
        self.assertIsNone(fe.classify(r,page,OBSERVATIONS,SOURCES,self.metrics['fx-consensus'],'[Page 1]\nAbout 70% to 80% of the budget'))
        self.assertTrue(fe._shows('between USD60 billion and USD64 billion',60))
        self.assertFalse(fe._shows('grew 180.0% this year',1.8),'no percent scaling')

    def test_a_page_printing_another_scale_still_shows_its_old_figure(self):
        # The ledger stores 10,860 (TWD billion); the page prints 10.86T. The page still shows the old
        # figure, so settle_revisions sends a reading of 10,900 to the owner, never out unattended.
        doc='Revenue This Year 10.86T; Avg 10.9T, High 11.3T'
        self.assertTrue(fe._shows(doc,10860.0))
        self.assertTrue(fe._shows('Revenue 42.68M this year',0.04268))

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
        # The mechanism under test runs with the same-page switch on; the shipped policy may have it off.
        policy=read('research/publication-policy.json');policy['auto_apply']['same_page_revisions']['enabled']=True
        write('research/publication-policy.json',policy)
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

    def move(self):
        ledger=self.ledger();next(o for o in ledger['observations'] if o['id']=='fx-peak-2044')['note']='Moved again.'
        (self.root/'site/data/ledger.json').write_text(json.dumps(ledger,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

    def item(self):
        return json.loads(next((self.root/'.local/review-candidates').glob('edition-*.json')).read_text(encoding='utf-8'))

    def test_an_interrupted_reproposal_is_never_stranded_on_a_withdrawn_package(self):
        # The editorial lock is busy exactly when the replacement is enqueued.
        self.hold();first=fe.materialize(self.root)[0];self.move()
        with patch.object(catalog_review,'enqueue',side_effect=FileExistsError('editorial.lock')):
            self.assertEqual(fe.materialize(self.root),[])
        self.assertEqual((self.item()['status'],self.item()['earlier_packages']),('ready',[first]))
        second=fe.materialize(self.root)
        self.assertEqual(len(second),1);self.assertNotEqual(second[0],first,'a re-proposal never reuses the withdrawn id')
        statuses={p['id']:p['status'] for p in catalog_review.inbox(self.root)}
        self.assertEqual((statuses[first],statuses[second[0]]),('withdrawn','pending_review'))

    def test_a_transient_read_error_does_not_strand_the_hold(self):
        self.hold();first=fe.materialize(self.root)[0]
        with patch.object(catalog_review,'check_base',side_effect=PermissionError('sharing violation')):
            again=fe.materialize(self.root)
        self.assertEqual(len(again),1);self.assertNotEqual(again[0],first)
        self.assertEqual(self.item()['package'],again[0])
        self.assertEqual(fe.materialize(self.root),[],'the current package is left for the owner')

    def test_the_runner_never_withdraws_over_the_owner(self):
        self.hold();first=fe.materialize(self.root)[0]
        from editorial_review import append_event
        append_event(self.root,{'id':first,'kind':'catalog_change','status':'rejected','reviewer':'owner','at':'2026-09-22T10:00:00Z'})
        self.assertFalse(fe.withdraw(self.root,first,'stale'))
        self.assertEqual(catalog_review.last_review(self.root,first)['status'],'rejected')

    def test_a_sibling_package_is_withdrawn_once_its_figures_are_published(self):
        # Two holds from one document, one a subset of the other; the owner publishes the larger one.
        self.hold();big=fe.materialize(self.root)[0]
        self.hold(rows=[('Peak load grows from 124 GW in 2026 to 184 GW by 2046 <in the current case>,',rec('fx-peak-gw',2046,184,'fx-2026'))])
        small=[p for p in fe.materialize(self.root)];self.assertEqual(len(small),1)
        self.apply(catalog_review.package(self.root,big))
        fe.materialize(self.root)
        statuses={p['id']:p['status'] for p in catalog_review.inbox(self.root)}
        self.assertEqual(statuses[small[0]],'withdrawn')

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


class RevisionTests(Fixture):
    """Same-page revisions, settled once a night (forecast_edition.settle_revisions).

    Each failure the 09/24/2026 review demonstrated on the old design has a test here, on fixture
    figures: the fiscal-year slip, the stale reading whose number shows elsewhere, the apply step that
    did not depend on the freshness check, the overridden Defer and rejection, the snapshot date."""
    # The page gives two years, as the consensus pages do: a column slip needs a neighbour to be caught.
    PAGE='Consensus revenue estimate for FY2026 now stands at {v} billion; FY2027 at 70.0 billion.'

    def setUp(self):
        super().setUp()
        pol=json.loads((self.root/'research/publication-policy.json').read_text(encoding='utf-8'))
        pol['auto_apply']['same_page_revisions']['sources'].append('fx-page')
        (self.root/'research/publication-policy.json').write_text(json.dumps(pol,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        self.url=self.sources['fx-page']['url']
        self.add_2027(70.0)

    def write_ledger(self,ledger):
        (self.root/'site/data/ledger.json').write_text(json.dumps(ledger,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

    def add_2027(self,value=70.0):
        ledger=self.ledger();ledger['observations']=[o for o in ledger['observations'] if o['id']!='fx-consensus-2027']
        ledger['observations'].append(curated('fx-consensus-2027','fx-consensus',2027,value,'fx-page'));self.write_ledger(ledger)

    def revision_hold(self,value,text=PAGE,year=2026,page=True):
        """The runner's hold for one revised figure, and (page=True) the page text it saved."""
        import hashlib
        doc=text.format(v=value)
        r=dict(rec('fx-consensus',year,value,'fx-page'),document_sha256=hashlib.sha256((doc*3).encode()).hexdigest())
        held=fe.hold(self.root/'.local',self.sources['fx-page'],doc*3,[({'evidence':doc},r,{'index':0,'supported':True,'reason':'ok'})],self.metrics,None,'revision',self.ledger())
        if page:self.save_page(doc*3)
        return held

    def save_page(self,text):
        # What the runner leaves behind after reading a page: the fetch state names its latest text.
        import hashlib
        from collection_health import Health
        sha=hashlib.sha256(text.encode('utf-8')).hexdigest()
        (self.root/'.local/evidence').mkdir(parents=True,exist_ok=True)
        (self.root/'.local/evidence'/f'{sha}.json').write_text(json.dumps({'url':self.url,'text':text}),encoding='utf-8')
        Health(self.root/'.local/fetch-state.json').put('page',self.url,{'text_sha256':sha})

    def holds(self):
        return [json.loads(f.read_text(encoding='utf-8')) for f in sorted((self.root/'.local/review-candidates').glob('edition-*.json'))]

    def item(self):
        (only,)=self.holds();return only

    def admitted(self,pid):
        pol=pub_policy(self.root);registry=json.loads((self.root/'research/sources.json').read_text(encoding='utf-8'))
        return eligible(catalog_review.package(self.root,pid),pol,registry,self.ledger())

    def settle(self,auto=True,fail=None,**kw):
        """settle_revisions with publication stubbed: the policy's own eligibility decides, and an
        admitted package is written the way 'Approve and publish' writes it."""
        import publication_policy
        from editorial_review import append_event
        def publish(root,pid,p=None):
            ok,reasons=self.admitted(pid)
            if not ok:raise ValueError('Not admitted by publication policy: '+reasons[0])
            if fail:return fail(root,pid)
            self.apply(catalog_review.package(root,pid))
            append_event(root,{'id':pid,'kind':'catalog_change','status':'applied','reviewer':'publication-policy','at':fe._now()})
            return {'status':'deployed'}
        with patch.object(publication_policy,'auto_apply',side_effect=publish) as applying:
            result=fe.settle_revisions(self.root,auto=auto,**kw)
        self.applying=applying
        return result

    def value_on_site(self,year=2026):
        return next(o['value'] for o in self.ledger()['observations'] if o['metric']=='fx-consensus' and o['year']==year and not o.get('superseded_by'))

    def card(self,result):
        (pid,)=result['cards'];p=catalog_review.package(self.root,pid)
        self.assertEqual(p['author'],fe.REVIEW_AUTHOR)
        self.assertFalse(self.admitted(pid)[0],'a card is never admitted by the policy')
        return p

    def test_a_research_batch_leaves_revisions_for_the_policy_stage(self):
        self.revision_hold(67.15)
        self.assertEqual(fe.materialize(self.root),[])
        self.assertEqual(self.item()['status'],'ready')

    def test_an_admissible_revision_is_published_the_night_it_is_read(self):
        self.revision_hold(67.15)
        result=self.settle()
        self.assertEqual(len(result['applied']),1);self.assertEqual(result['cards'],[])
        self.assertEqual(self.value_on_site(),67.15)
        ledger=self.ledger();by_id={o['id']:o for o in ledger['observations']}
        new=by_id[by_id['fx-consensus-2026']['superseded_by']]
        self.assertEqual((new['edition_supersedes'],new['note']),(['fx-consensus-2026'],'Fixture.'),'the reviewed caveat travels')
        self.assertIn('same address',new['correction_reason'])
        page=next(s for s in ledger['sources'] if s['id']=='fx-page')
        self.assertEqual(page['published'],'2026-09-22','the page is dated the day it was read, not the snapshot first registered')
        validate.validate(ledger)
        self.assertEqual((self.item()['status'],list(self.item()['outcomes'].values())[0].split(':')[0]),('settled','applied'))
        self.assertEqual(fe.settle_revisions(self.root,auto=True)['applied'],[],'settled once')

    def test_with_automatic_revisions_off_every_revision_is_a_card(self):
        self.revision_hold(67.15)
        p=self.card(self.settle(auto=False))
        self.assertIn('automatic revisions are off',p['title'])
        self.assertEqual(self.applying.call_count,0)
        self.assertEqual(self.value_on_site(),67.14)
        pol=json.loads((self.root/'research/publication-policy.json').read_text(encoding='utf-8'))
        pol['auto_apply']['same_page_revisions']['enabled']=False
        (self.root/'research/publication-policy.json').write_text(json.dumps(pol,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        self.revision_hold(67.16)
        self.assertEqual(len(self.settle(auto=True)['cards']),1,'the policy switch off: a card even when the stage asks for auto')

    def test_a_page_off_the_same_page_list_goes_to_the_owner(self):
        pol=json.loads((self.root/'research/publication-policy.json').read_text(encoding='utf-8'))
        pol['auto_apply']['same_page_revisions']['sources']=[s for s in pol['auto_apply']['same_page_revisions']['sources'] if s!='fx-page']
        (self.root/'research/publication-policy.json').write_text(json.dumps(pol,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        self.revision_hold(67.15)
        self.assertIn('not on the same-page list',self.card(self.settle())['title'])

    def test_the_neighbouring_years_figure_is_never_published_as_this_years(self):
        # s1: the page's Next Year figure read as This Year. Within 1.1x, but it is next year's number.
        self.add_2027(70.0)
        self.revision_hold(70.0,text='Revenue This Year 67.3B. Revenue Next Year {v}B.')
        self.assertIn('as near this page',self.item_outcome_after_settle())
        self.assertEqual(self.value_on_site(),67.14)

    def test_a_reading_the_page_has_moved_on_from_is_dropped_even_if_its_number_shows_elsewhere(self):
        # s4: read 67.15 one night; the page now says 67.20, and 67.15 appears in its history table.
        self.revision_hold(67.15)
        self.save_page('Consensus revenue estimate for FY2026 is 67.20 billion. FY2022 actual: 67.15 billion.')
        result=self.settle()
        self.assertEqual((result['applied'],result['cards']),([],[]))
        self.assertEqual(self.item()['status'],'obsolete')

    def test_a_page_whose_text_was_not_saved_goes_to_the_owner(self):
        self.revision_hold(67.15,page=False)
        self.assertIn('no saved text',self.card(self.settle())['title'])

    def test_a_page_still_showing_the_old_figure_goes_to_the_owner(self):
        self.revision_hold(67.15,text='Consensus revenue estimate for FY2026 is {v} billion, up from 67.14 billion.')
        self.assertIn('still shows the old figure',self.card(self.settle())['title'])

    def test_a_reading_from_an_earlier_night_goes_to_the_owner(self):
        self.revision_hold(67.15)
        path=next((self.root/'.local/review-candidates').glob('edition-*.json'));item=json.loads(path.read_text(encoding='utf-8'))
        item['created_at']='2026-09-20T09:00:00Z';path.write_text(json.dumps(item),encoding='utf-8')
        self.assertIn('earlier night',self.card(self.settle())['title'])

    def test_a_move_beyond_the_ratio_goes_to_the_owner(self):
        self.revision_hold(74.0)  # 1.102x
        self.assertIn('beyond 1.1x',self.card(self.settle())['title'])

    def test_a_note_with_a_date_or_figure_goes_to_the_owner(self):
        ledger=self.ledger();next(o for o in ledger['observations'] if o['id']=='fx-consensus-2026')['note']='Snapshot of September 4, 2026.'
        self.write_ledger(ledger)
        self.revision_hold(67.15)
        p=self.card(self.settle())
        new=next(c['after'] for c in p['changes'] if c['target']=='observation' and c['before'] is None)
        self.assertEqual(new['note'],'','the dated caveat is not carried onto a figure it no longer describes')

    def test_a_dated_title_goes_to_the_owner(self):
        registry=json.loads((self.root/'research/sources.json').read_text(encoding='utf-8'))
        next(s for s in registry['sources'] if s['id']=='fx-page')['title']='Fixture consensus · September 3 dataset'
        (self.root/'research/sources.json').write_text(json.dumps(registry,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        self.revision_hold(67.15)
        self.assertIn('date in its title',self.item_outcome_after_settle())

    def item_outcome_after_settle(self):
        self.card(self.settle());return self.item()['outcomes']['fx-consensus-2026']

    def test_a_bare_year_in_the_title_goes_to_the_owner(self):
        registry=json.loads((self.root/'research/sources.json').read_text(encoding='utf-8'))
        next(s for s in registry['sources'] if s['id']=='fx-page')['title']='Fixture consensus revenue outlook 2026'
        (self.root/'research/sources.json').write_text(json.dumps(registry,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        self.revision_hold(67.15)
        self.assertIn('date in its title',self.item_outcome_after_settle())

    def test_a_slipped_upper_bound_goes_to_the_owner(self):
        # A range figure: the low end moved a little, the high end was read from the next row.
        ledger=self.ledger();o=next(o for o in ledger['observations'] if o['id']=='fx-consensus-2026')
        o.update(value=90000,upper=110000,precision='range')
        ledger['observations']=[x for x in ledger['observations'] if x['id']!='fx-consensus-2027']
        ledger['observations'].append(dict(curated('fx-consensus-2027','fx-consensus',2027,105000,'fx-page',upper=118000,precision='range')))
        self.write_ledger(ledger)
        import hashlib
        doc='Year-end 2026: 91000 to 118000 wafers per month. Year-end 2027: 105000 to 125000.'
        r=dict(rec('fx-consensus',2026,91000,'fx-page',upper=118000,precision='range'),document_sha256=hashlib.sha256(doc.encode()).hexdigest())
        fe.hold(self.root/'.local',self.sources['fx-page'],doc,[({'evidence':doc},r,{'index':0,'supported':True,'reason':'ok'})],self.metrics,None,'revision',self.ledger())
        self.save_page(doc)
        self.assertIn('its upper 118000 is as near',self.item_outcome_after_settle())

    def test_a_forecast_the_page_no_longer_shows_keeps_its_date_off_the_page(self):
        # The new date would vouch for 2027 too, which the page as last read does not show.
        self.revision_hold(67.15,text='Consensus revenue estimate for FY2026 now stands at {v} billion.')
        self.assertIn('2027 figure',self.item_outcome_after_settle())

    def test_one_page_travels_whole_with_its_date(self):
        self.add_2027(70.0)
        import hashlib
        doc='FY2026 consensus 67.15 billion; FY2027 consensus 70.5 billion.'
        rows=[({'evidence':doc},dict(rec('fx-consensus',y,v,'fx-page'),document_sha256=hashlib.sha256(doc.encode()).hexdigest()),{'index':i,'supported':True,'reason':'ok'})
              for i,(y,v) in enumerate([(2026,67.15),(2027,70.5)])]
        fe.hold(self.root/'.local',self.sources['fx-page'],doc,rows,self.metrics,None,'revision',self.ledger());self.save_page(doc)
        result=self.settle()
        (pid,)=result['applied'];p=catalog_review.package(self.root,pid)
        self.assertEqual(sorted(c['target'] for c in p['changes']),['observation']*4+['source'])
        self.assertEqual(len({e['id'] for e in p['evidence']}),2,'each revised figure keeps its own quote')
        self.assertEqual((self.value_on_site(2026),self.value_on_site(2027)),(67.15,70.5))

    def test_the_owners_rejection_sticks_when_a_sibling_figure_changes(self):
        self.add_2027(70.0)
        self.revision_hold(67.15,text='FY2026 consensus {v} billion; FY2027 consensus 70.0 billion.')
        (card,)=self.settle(auto=False)['cards']
        from editorial_review import append_event
        append_event(self.root,{'id':card,'kind':'catalog_change','status':'rejected','reviewer':'owner','at':fe._now()})
        # The page moves 2027; the runner reads both figures again, 2026 still at the rejected 67.15.
        import hashlib
        doc='FY2026 consensus 67.15 billion; FY2027 consensus 70.5 billion.'
        rows=[({'evidence':doc},dict(rec('fx-consensus',y,v,'fx-page'),document_sha256=hashlib.sha256(doc.encode()).hexdigest()),{'index':i,'supported':True,'reason':'ok'})
              for i,(y,v) in enumerate([(2026,67.15),(2027,70.5)])]
        self.assertEqual(len(fe.hold(self.root/'.local',self.sources['fx-page'],doc,rows,self.metrics,None,'revision',self.ledger())),1)
        self.save_page(doc)
        result=self.settle()
        self.assertEqual(self.value_on_site(2026),67.14,'the rejected reading is not published')
        self.assertTrue(result['outcomes']['fx-consensus-2026'].startswith('declined'))
        self.assertTrue(result['outcomes']['fx-consensus-2027'].startswith(('applied','card')))

    def test_a_failed_publication_is_withdrawn_and_handed_to_the_owner(self):
        self.revision_hold(67.15)
        def broken(root,pid):raise ValueError('Preview validation failed; left for human review')
        result=self.settle(fail=broken)
        self.assertEqual(result['applied'],[]);self.assertEqual(len(result['withdrawn']),1)
        self.assertIn('automatic publication failed',self.card(result)['title'])
        self.assertEqual(catalog_review.last_review(self.root,result['withdrawn'][0])['status'],'withdrawn')

    def test_a_publication_that_committed_is_left_to_finish(self):
        self.revision_hold(67.15)
        def pushed_later(root,pid):
            (root/'.local/review-candidates'/(pid+'-publication.json')).write_text(json.dumps({'commit':'c'*40,'status':'publication_failed'}),encoding='utf-8')
            raise RuntimeError('push failed')
        result=self.settle(fail=pushed_later)
        self.assertEqual((result['cards'],result['withdrawn']),([],[]))
        self.assertTrue(list(result['outcomes'].values())[0].startswith('publishing'))
        self.assertEqual(self.item()['status'],'settled')

    def test_past_the_deadline_revisions_go_to_the_owner(self):
        import time
        self.revision_hold(67.15)
        self.assertIn('not enough time',self.card(self.settle(deadline=time.monotonic()-1))['title'])

    def test_a_leftover_automatic_package_is_withdrawn_and_never_applied_by_the_policy(self):
        self.revision_hold(67.15)
        changes,evidence,_=fe.revision_changes(self.root,self.item(),self.ledger())
        pid=catalog_review.enqueue(self.root,'Leftover',changes,[evidence],author=fe.REVISION_AUTHOR)['id']
        import publication_policy
        pol=pub_policy(self.root);registry=json.loads((self.root/'research/sources.json').read_text(encoding='utf-8'))
        rows,admitted=publication_policy.admissions(self.root,pol,registry,self.ledger())
        self.assertNotIn(pid,admitted,'apply_admitted and the CLI never publish a same-page revision')
        path=self.root/'.local/review-candidates'/(pid+'.json');p=json.loads(path.read_text(encoding='utf-8'))
        p['created_at']='2026-09-20T09:00:00Z';path.write_text(json.dumps(p),encoding='utf-8')
        self.assertFalse(self.admitted(pid)[0],'published within the hour it is built or not at all')
        result=self.settle()
        self.assertEqual(result['withdrawn'],[pid])

    def test_of_two_readings_of_one_figure_the_newer_wins(self):
        self.revision_hold(67.15,page=False)
        self.revision_hold(67.2,text='Consensus revenue estimate for FY2026 now reads {v} billion instead; FY2027 at 70.0 billion.')
        result=self.settle()
        self.assertEqual(len(result['applied']),1);self.assertEqual(self.value_on_site(),67.2)
        self.assertEqual(sorted(h['status'] for h in self.holds()),['obsolete','settled'])

    def test_a_stale_revision_is_never_rebased_onto_a_newer_figure(self):
        # Read against 67.14; 67.20 was published meanwhile. The reading must not roll it back.
        self.revision_hold(67.15)
        ledger=self.ledger();o=next(o for o in ledger['observations'] if o['id']=='fx-consensus-2026')
        newer=dict(o,id='fx-consensus-2026b',value=67.2);o['superseded_by']=newer['id'];newer['correction_of']=o['id'];newer['correction_reason']='Fixture.'
        ledger['observations'].append(newer);self.write_ledger(ledger)
        self.assertEqual(self.settle()['applied'],[])
        self.assertEqual(self.item()['status'],'obsolete')

    def test_a_page_returning_to_an_earlier_value_is_a_new_revision_with_new_ids(self):
        first=self.revision_hold(67.15);self.settle()
        second=self.revision_hold(67.14,text='Consensus revenue estimate for FY2026 is back at {v} billion today; FY2027 at 70.0 billion.')
        self.assertEqual(len(second),1);self.assertNotEqual(first,second)
        self.assertEqual(len(self.settle()['applied']),1)
        self.assertEqual(self.value_on_site(),67.14)
        validate.validate(self.ledger())  # no duplicate ids: each revision is pinned to what it replaced

    def test_a_misread_figure_on_the_site_is_put_to_the_owner_by_the_next_correct_reading(self):
        # The site holds a misread 70.0 for 2026 that the page also shows (as 2027). Until 09/24 the
        # page's correct 67.15 was quarantined as a conflict for ever; now it reaches the owner.
        ledger=self.ledger();next(o for o in ledger['observations'] if o['id']=='fx-consensus-2026')['value']=70.0;self.write_ledger(ledger)
        page=self.sources['fx-page']
        doc='Revenue This Year 67.15B. Revenue Next Year 70.0B.'
        self.assertEqual(fe.classify(rec('fx-consensus',2026,67.15,'fx-page'),page,self.ledger()['observations'],self.ledger()['sources'],self.metrics['fx-consensus'],doc),'revision')
        self.revision_hold(67.15,text='Revenue This Year {v}B. Revenue Next Year 70.0B.')
        self.assertIn('still shows the old figure',self.card(self.settle())['title'])

    def test_a_figure_another_file_cites_needs_a_maintainer(self):
        (self.root/'research/fixture-citation.json').write_text('{"measure": "fx-consensus-2026"}\n',encoding='utf-8')
        self.revision_hold(67.15)
        self.assertEqual(self.settle()['applied'],[])
        self.assertEqual(self.item()['status'],'needs_maintainer');self.assertIn('fixture-citation.json',self.item()['reason'])
        self.assertEqual(fe.blocked(self.root),1)
        (self.root/'research/fixture-citation.json').unlink()
        self.assertEqual(len(self.revision_hold(67.15)),1,'the next reading of the page raises it again')
        self.assertEqual(len(self.settle()['applied']),1)

    def test_a_revision_the_page_bounced_away_from_returns_when_the_page_does(self):
        self.revision_hold(67.15)
        self.save_page('Consensus revenue estimate for FY2026 is 67.14 billion again.')
        self.settle();self.assertEqual(self.item()['status'],'obsolete')
        self.assertEqual(len(self.revision_hold(67.15)),1,'the same reading is raised again')
        self.assertEqual(len(self.settle()['applied']),1)

    def test_a_figure_with_no_neighbour_on_the_page_goes_to_the_owner(self):
        # The FY slip with nothing on file to catch it: the page's first reading of a second year.
        ledger=self.ledger();ledger['observations']=[o for o in ledger['observations'] if o['id']!='fx-consensus-2027'];self.write_ledger(ledger)
        self.revision_hold(70.0,text='Revenue This Year 67.3B. Revenue Next Year {v}B.')
        self.assertIn('column slip cannot be ruled out',self.item_outcome_after_settle())
        self.assertEqual(self.value_on_site(),67.14)

    def pending_cards(self):
        return [p for p in catalog_review.inbox(self.root) if p['author']==fe.REVIEW_AUTHOR and p['status']=='pending_review']

    def added(self,p):
        return sorted(c['after']['value'] for c in p['changes'] if c['target']=='observation' and c['before'] is None)

    def test_a_card_an_older_reading_left_is_replaced_by_the_newer_readings_card(self):
        self.revision_hold(67.15)
        (old_card,)=self.settle(auto=False)['cards']
        self.revision_hold(67.2,text='Consensus revenue estimate for FY2026 now reads {v} billion; FY2027 at 70.0 billion.')
        result=self.settle()
        self.assertEqual(result['applied'],[],'the page has a card open: it waits for the owner')
        self.assertEqual(self.value_on_site(),67.14)
        self.assertEqual(catalog_review.last_review(self.root,old_card)['status'],'withdrawn','approving the stale card could only roll the figure back')
        self.assertEqual([self.added(p) for p in self.pending_cards()],[[67.2]])

    def test_a_newer_reading_of_one_year_keeps_the_other_years_card_alive(self):
        # One card per page: 2026 and 2027 both went to the owner. Only 2026 is read again.
        import hashlib
        doc='FY2026 consensus 67.15 billion; FY2027 consensus 80.0 billion.'
        rows=[({'evidence':doc},dict(rec('fx-consensus',y,v,'fx-page'),document_sha256=hashlib.sha256(doc.encode()).hexdigest()),{'index':i,'supported':True,'reason':'ok'})
              for i,(y,v) in enumerate([(2026,67.15),(2027,80.0)])]
        fe.hold(self.root/'.local',self.sources['fx-page'],doc,rows,self.metrics,None,'revision',self.ledger());self.save_page(doc)
        (old_card,)=self.settle(auto=False)['cards']
        self.revision_hold(67.2,text='FY2026 consensus {v} billion; FY2027 consensus 80.0 billion.')
        self.settle(auto=False)
        self.assertEqual(catalog_review.last_review(self.root,old_card)['status'],'withdrawn')
        cards=[p for p in catalog_review.inbox(self.root) if p['author']==fe.REVIEW_AUTHOR and p['status']=='pending_review']
        self.assertEqual(len(cards),1,'one card per page, so two cards never race to move the page date')
        values=sorted(c['after']['value'] for c in cards[0]['changes'] if c['target']=='observation' and c['before'] is None)
        self.assertEqual(values,[67.2,80.0],"the untouched 2027 reading is carried into the page's new card")
        self.apply(cards[0]);validate.validate(self.ledger())

    def test_an_open_card_keeps_its_page_from_publishing_another_year_unattended(self):
        # Review finding, 09/24/2026: publishing 2027 moved the page's date under the open 2026 card,
        # which could then never be approved.
        self.revision_hold(67.15)
        (old_card,)=self.settle(auto=False)['cards']
        self.revision_hold(70.5,year=2027,text='FY2026 consensus 67.15 billion; FY2027 consensus {v} billion.')
        result=self.settle()
        self.assertEqual(result['applied'],[])
        self.assertEqual((self.value_on_site(2026),self.value_on_site(2027)),(67.14,70.0))
        (card,)=self.pending_cards()
        self.assertEqual(self.added(card),[67.15,70.5],'the open 2026 figure is carried into the page\'s one card')
        self.assertEqual(catalog_review.last_review(self.root,old_card)['status'],'withdrawn')
        self.apply(card);validate.validate(self.ledger())

    def test_a_carried_figure_whose_site_figure_moved_is_dropped_not_stuck(self):
        import hashlib
        doc='FY2026 consensus 67.15 billion; FY2027 consensus 80.0 billion.'
        rows=[({'evidence':doc},dict(rec('fx-consensus',y,v,'fx-page'),document_sha256=hashlib.sha256(doc.encode()).hexdigest()),{'index':i,'supported':True,'reason':'ok'})
              for i,(y,v) in enumerate([(2026,67.15),(2027,80.0)])]
        fe.hold(self.root/'.local',self.sources['fx-page'],doc,rows,self.metrics,None,'revision',self.ledger());self.save_page(doc)
        (old_card,)=self.settle(auto=False)['cards']
        ledger=self.ledger();next(o for o in ledger['observations'] if o['id']=='fx-consensus-2027')['note']='Reworded by a person.';self.write_ledger(ledger)
        self.revision_hold(67.2,text='FY2026 consensus {v} billion; FY2027 consensus 80.0 billion.')
        result=self.settle(auto=False)
        self.assertNotIn('stuck',result)
        self.assertEqual([self.added(p) for p in self.pending_cards()],[[67.2]],'one card for the page; the 2027 figure moved under the old card')
        self.assertEqual(catalog_review.last_review(self.root,old_card)['status'],'withdrawn')

    def test_a_deferred_card_is_left_to_the_owner_even_when_a_newer_reading_arrives(self):
        self.revision_hold(67.15)
        (old_card,)=self.settle(auto=False)['cards']
        from editorial_review import append_event
        append_event(self.root,{'id':old_card,'kind':'catalog_change','status':'deferred','reviewer':'owner','at':fe._now()})
        self.revision_hold(67.2,text='Consensus revenue estimate for FY2026 now reads {v} billion; FY2027 at 70.0 billion.')
        result=self.settle()
        self.assertEqual(catalog_review.last_review(self.root,old_card)['status'],'deferred')
        self.assertEqual(result['applied'],[],'the owner deferred this page: nothing answers for them')
        self.assertEqual(self.value_on_site(),67.14)
        (card,)=result['cards']
        self.assertFalse([c for c in catalog_review.package(self.root,card)['changes'] if c['target']=='source'],
                         'the new card leaves the page date to the deferred card')
        catalog_review.check_base(self.root,catalog_review.package(self.root,old_card))  # still approvable

    def leftover(self,**review):
        self.revision_hold(67.15)
        changes,evidence,_=fe.revision_changes(self.root,self.item(),self.ledger())
        pid=catalog_review.enqueue(self.root,'Leftover',changes,[evidence],author=fe.REVISION_AUTHOR)['id']
        path=self.root/'.local/review-candidates'/(pid+'.json');p=json.loads(path.read_text(encoding='utf-8'))
        p['created_at']='2026-09-20T09:00:00Z';path.write_text(json.dumps(p),encoding='utf-8')
        if review:
            from editorial_review import append_event
            append_event(self.root,dict({'id':pid,'kind':'catalog_change','at':fe._now()},**review))
        return pid

    def test_a_leftover_the_owner_deferred_is_not_withdrawn(self):
        pid=self.leftover(status='deferred',reviewer='owner')
        self.assertNotIn(pid,self.settle()['withdrawn'])
        self.assertEqual(catalog_review.last_review(self.root,pid)['status'],'deferred')

    def test_a_leftover_that_was_committed_before_its_receipt_is_finished_not_withdrawn(self):
        pid=self.leftover(status='approved',reviewer='publication-policy')
        with patch.object(fe,'_committed',return_value='c'*40):
            result=self.settle()
        self.assertNotIn(pid,result['withdrawn'])
        receipt=json.loads((self.root/'.local/review-candidates'/(pid+'-publication.json')).read_text(encoding='utf-8'))
        self.assertEqual((receipt['commit'],receipt['status']),('c'*40,'committed'),'verify_pending_deployments finishes it')

    def test_a_failure_after_publishing_still_records_what_was_published(self):
        self.revision_hold(67.2)
        with patch.object(fe,'_retire_cards',side_effect=RuntimeError('disk full')):
            with self.assertRaises(RuntimeError):self.settle()
        self.assertEqual(self.value_on_site(),67.2)
        newest=max(self.holds(),key=lambda h:h['created_at']+str(h['held_ns']))
        self.assertTrue(newest['outcomes']['fx-consensus-2026'].startswith('applied'),'the published reading is still on the night\'s report')

    def test_the_nights_report_reads_what_was_settled_from_the_holds(self):
        self.revision_hold(67.15);self.settle()
        (row,)=fe.settled_since(self.root,'2000-01-01T00:00:00Z')
        self.assertEqual((row['kind'],row['source']),('applied','fx-page'))
        self.assertIn('67.14',row['line']);self.assertIn('67.15',row['line'])
        self.assertEqual(fe.settled_since(self.root,'2999-01-01T00:00:00Z'),[])

    def test_bundles_respect_the_package_size_limit(self):
        units=[[{'changes':[{}]*8}] for _ in range(30)]  # 30 pages, each 4 figures and a date change
        groups=fe._bundle(units)
        self.assertTrue(all(sum(len(x['changes'])+1 for unit in g for x in unit)<=100 for g in groups));self.assertEqual(len(groups),3)
        self.assertEqual(sum(len(g) for g in groups),30)

    def test_the_policy_refuses_what_a_revision_package_must_not_carry(self):
        self.revision_hold(74.0)
        p=catalog_review.package(self.root,self.settle(auto=False)['cards'][0])
        pol=pub_policy(self.root);registry=json.loads((self.root/'research/sources.json').read_text(encoding='utf-8'))
        import publication_policy
        rule=pol['auto_apply']['same_page_revisions']
        as_auto=dict(copy.deepcopy(p),author=fe.REVISION_AUTHOR)
        ok,reasons=eligible(as_auto,pol,registry,self.ledger());self.assertFalse(ok);self.assertIn('beyond',reasons[0])
        small=copy.deepcopy(as_auto)
        for c in small['changes']:
            if c['target']=='observation' and c['before'] is None:c['after']['value']=67.2
        self.assertTrue(eligible(small,pol,registry,self.ledger())[0],'the same package within 1.1x is admitted')
        tampered=copy.deepcopy(small);next(c for c in tampered['changes'] if c['target']=='observation' and c['before'] is None)['after']['status']='company-commitment'
        self.assertFalse(eligible(tampered,pol,registry,self.ledger())[0])
        extra=copy.deepcopy(small);extra['changes'].append({'target':'observation','id':'fx-peak-2044','before':OBSERVATIONS[1],'after':dict(OBSERVATIONS[1],value=1),'evidence':['x']})
        self.assertFalse(eligible(extra,pol,registry,self.ledger())[0])
        renamed=copy.deepcopy(small);next(c for c in renamed['changes'] if c['target']=='source')['after']['title']='Renamed'
        self.assertFalse(eligible(renamed,pol,registry,self.ledger())[0],'only the date of the page may change')
        backwards=copy.deepcopy(small);next(c for c in backwards['changes'] if c['target']=='source')['after']['published']='2026-09-01'
        self.assertFalse(eligible(backwards,pol,registry,self.ledger())[0])
        corrected=copy.deepcopy(small);retired=next(c for c in corrected['changes'] if c['target']=='observation' and c['before'] is not None)
        retired['before']['correction_of']='x';retired['after']['correction_of']='x'
        ok,reasons=publication_policy.same_page_revision(corrected,rule,self.ledger(),registry)
        self.assertFalse(ok);self.assertIn('correction a person made',reasons[0])
        forged=copy.deepcopy(small);forged['author']=fe.AUTHOR
        self.assertFalse(eligible(forged,dict(pol,auto_apply=dict(pol['auto_apply'],authors=[fe.AUTHOR])),registry,self.ledger())[0],
                         'an edition package is never auto-applied, even under a listed author')
        stale=copy.deepcopy(small);stale['created_at']='2026-09-20T09:00:00Z'
        self.assertFalse(eligible(stale,pol,registry,self.ledger())[0])


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

    def test_a_by_year_edition_travels_whole_restated_year_and_new_year_together(self):
        # Later guidance changes 2026 and adds 2027: publishing 2027 alone would strand the 2026 revision.
        doc='Guidance: we now expect 240 GW-equivalent in 2026 and 260 GW-equivalent in 2027 across the company.'
        cands=[self.cand('fx-guidance-gw',2026,240,'we now expect 240 GW-equivalent in 2026'),
               self.cand('fx-guidance-gw',2027,260,'and 260 GW-equivalent in 2027 across')]
        accepted,quarantine,holds=self.extract('fx-oct',cands,doc)
        self.assertEqual((accepted,quarantine),([],[]))
        self.assertEqual(sorted(r['record']['year'] for h in holds for r in h['records']),[2026,2027])

    def test_the_runner_holds_a_same_page_revision(self):
        doc='Consensus revenue estimate for FY2026 now stands at 67.15 billion dollars across analysts.'
        accepted,quarantine,holds=self.extract('fx-page',[self.cand('fx-consensus',2026,67.15,'estimate for FY2026 now stands at 67.15 billion')],doc)
        self.assertEqual((accepted,quarantine),([],[]))
        self.assertEqual([(h['change'],h['records'][0]['record']['value']) for h in holds],[('revision',67.15)])

    def test_a_page_still_showing_the_old_figure_is_held_for_the_owner_not_quarantined(self):
        doc='Consensus revenue estimate for FY2026 is 67.15 billion, up from 67.14 billion last week.'
        accepted,quarantine,holds=self.extract('fx-page',[self.cand('fx-consensus',2026,67.15,'estimate for FY2026 is 67.15 billion')],doc)
        self.assertEqual((accepted,quarantine),([],[]))
        self.assertEqual([(h['change'],h['records'][0]['record']['value']) for h in holds],[('revision',67.15)])

    def test_a_pdf_that_seems_to_revise_itself_stays_a_conflict(self):
        page=dict(self.sources['fx-page'],url='https://fixture.example/consensus/revenue.pdf')
        doc='[Page 1]\nConsensus revenue estimate for FY2026 is 67.15 billion across analysts.'
        r=rec('fx-consensus',2026,67.15,'fx-page')
        self.assertIsNone(fe.classify(r,page,self.ledger()['observations'],self.ledger()['sources'],self.metrics['fx-consensus'],doc))

    def test_monitoring_cannot_publish_an_edition_link(self):
        head=self.ledger();after=copy.deepcopy(head)
        after['observations'].append(dict(rec('fx-peak-gw',2046,184,'fx-2026'),edition_supersedes=['fx-peak-2044']))
        excerpts=json.loads((self.root/'site/data/excerpts.json').read_text(encoding='utf-8'))
        with self.assertRaisesRegex(ValueError,'Monitoring cannot issue corrections'):
            research.validate_monitoring_delta(head,after,excerpts,excerpts)


if __name__=='__main__':
    unittest.main()
