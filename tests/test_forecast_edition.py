import copy
import io
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


def ledger():return json.loads((ROOT/'site/data/ledger.json').read_text(encoding='utf-8'))


def rec(metric,year,value,source,upper=None,status='forecast'):
    return {'id':f'auto-{metric}-{year}'[:40],'metric':metric,'year':year,'period':str(year),'value':value,'upper':upper,'status':status,
            'source':source,'precision':'approx','retrieved_at':'2026-09-22T09:00:00Z','method':'automated','note':'',
            'document_sha256':'a'*64,'evidence_sha256':'b'*64,'grade':'A'}


class ClassifyTests(unittest.TestCase):
    """The vintage error, three ways: an older edition, a newer one, and a page restating itself."""
    def setUp(self):
        self.data=ledger();self.metrics={m['id']:m for m in self.data['metrics']};self.sources={s['id']:s for s in self.data['sources']}
        reg=json.loads((ROOT/'research/sources.json').read_text(encoding='utf-8'))
        self.registry={s['id']:s for s in reg['sources']}

    def classify(self,record,source):
        return fe.classify(record,source,self.data['observations'],self.data['sources'],self.metrics.get(record['metric']))

    def test_a_newer_edition_of_a_rolling_forecast_is_held_whatever_its_years(self):
        # MISO's 2026 whitepaper forecasts 2046; the site holds the Dec 2024 edition's 2044.
        miso=self.registry['miso-ltlf-whitepaper-2026-05']
        self.assertEqual(self.classify(rec('miso-coincident-peak-ltlf-gw',2046,184,miso['id']),miso),'new')

    def test_an_older_edition_is_refused_by_its_date_or_file_name(self):
        # The SPP listing links the 2024 ITP beside the 2025 one the site already uses.
        child={'id':'discovered-0123456789abcdef','url':'https://www.spp.org/media/2229/2024-itp-assessment-report-v10.pdf','published':None,
               'parent_source':'spp-itp-index'}
        self.assertEqual(self.classify(rec('spp-itp-coincident-peak-gw',2043,70,child['id']),child),'older')

    def test_the_same_document_or_url_is_not_a_new_edition(self):
        same=self.registry['spp-2025-itp-report']
        self.assertIsNone(self.classify(rec('spp-itp-coincident-peak-gw',2030,67,same['id']),same))
        child=dict(same,id='discovered-fedcba9876543210',parent_source='spp-itp-index')  # the listing's link to the same file
        self.assertIsNone(self.classify(rec('spp-itp-coincident-peak-gw',2030,67,child['id']),child))

    def test_by_year_guidance_replaces_only_the_year_it_restates(self):
        # Capex guidance: new CY2026 guidance from another report is held; first CY2027 guidance is not.
        other={'id':'capital-later-report','url':'https://example.org/q3-guidance','published':'2026-10-30'}
        metric=next(m for m in self.data['metrics'] if m['id']=='capital-guidance-aws')
        self.assertNotEqual(metric.get('edition_mode'),'trajectory')
        self.assertEqual(self.classify(rec('capital-guidance-aws',2026,240,other['id']),other),'new')
        self.assertIsNone(self.classify(rec('capital-guidance-aws',2027,260,other['id']),other))

    def test_actuals_and_metrics_with_no_forecast_on_the_site_are_untouched(self):
        miso=self.registry['miso-ltlf-whitepaper-2026-05']
        self.assertIsNone(self.classify(rec('miso-coincident-peak-ltlf-gw',2025,121,miso['id'],status='observation'),miso))


class EditionPackageTests(unittest.TestCase):
    """Hold -> package -> projected ledger: the new edition published, the old one retired, all valid."""
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        for rel in catalog_review.FILES:
            (self.root/rel).parent.mkdir(parents=True,exist_ok=True);shutil.copy(ROOT/rel,self.root/rel)
        patcher=patch.object(catalog_review,'git',return_value='0'*40);patcher.start();self.addCleanup(patcher.stop)
        self.data=ledger();self.metrics={m['id']:m for m in self.data['metrics']}
        reg=json.loads((ROOT/'research/sources.json').read_text(encoding='utf-8'))
        self.source=next(s for s in reg['sources'] if s['id']=='miso-ltlf-whitepaper-2026-05')

    def hold(self):
        held=[({'evidence':'MISO projects coincident peak load to grow from 124 GW in 2026 to 184 GW by 2046,'},
               rec('miso-coincident-peak-ltlf-gw',2046,184,self.source['id']),{'index':0,'supported':True,'defect':None,'reason':'ok'}),
              ({'evidence':'2026 LTLF Current = 163 GW by 2035 in the current trajectory case'},
               rec('miso-coincident-peak-ltlf-gw',2035,163,self.source['id']),{'index':1,'supported':True,'defect':None,'reason':'ok'})]
        text='[Page 1]\nMISO projects coincident peak load to grow from 124 GW in 2026 to 184 GW by 2046, and more.\n'*3
        return fe.hold(self.root/'.local',self.source,text,held,self.metrics,lambda q:4)

    def test_a_held_edition_becomes_one_package_that_retires_the_old_edition(self):
        ids=self.hold()
        self.assertEqual(len(ids),1)
        self.assertEqual(self.hold(),[],'the same held edition is never raised twice')
        packaged=fe.materialize(self.root)
        self.assertEqual(len(packaged),1)
        p=catalog_review.package(self.root,packaged[0])
        self.assertEqual(p['author'],fe.AUTHOR)
        projected=catalog_review.projected(p,catalog_review.base(self.root))['site/data/ledger.json']
        by_id={o['id']:o for o in projected['observations']}
        old=by_id['miso-coincident-peak-2044']
        self.assertTrue(old['superseded_by'].startswith('auto-'))
        replacement=by_id[old['superseded_by']]
        self.assertEqual((replacement['year'],replacement['value']),(2046,184))
        self.assertEqual(replacement['edition_supersedes'],['miso-coincident-peak-2044'])
        self.assertIn('New edition',replacement['correction_reason'])
        self.assertNotIn('superseded_by',by_id['miso-coincident-peak-2024'],'an actual is not part of a forecast edition')
        validate.validate(projected)  # the whole projected ledger passes every rule
        # Never auto-applied, whatever the author list says.
        pol=copy.deepcopy(pub_policy(ROOT));pol['auto_apply']['enabled']=True;pol['auto_apply']['authors']=[fe.AUTHOR]
        ok,reasons=eligible(p,pol,json.loads((ROOT/'research/sources.json').read_text(encoding='utf-8')))
        self.assertFalse(ok);self.assertIn('forecast edition',reasons[0])
        item=json.loads(next((self.root/'.local/review-candidates').glob('edition-*.json')).read_text(encoding='utf-8'))
        self.assertEqual((item['status'],item['package']),('packaged',p['id']))
        self.assertIn('p. 4',p['evidence'][0]['summary'])

    def test_broken_or_self_referencing_edition_links_are_refused(self):
        ids=self.hold();p=catalog_review.package(self.root,fe.materialize(self.root)[0])
        projected=catalog_review.projected(p,catalog_review.base(self.root))['site/data/ledger.json']
        new=next(o for o in projected['observations'] if o.get('edition_supersedes'))
        broken=copy.deepcopy(projected);next(o for o in broken['observations'] if o['id']==new['id'])['edition_supersedes']=['miso-dc-energy-2030']
        with self.assertRaises(ValueError):validate.validate(broken)
        same=copy.deepcopy(projected)
        for o in same['observations']:
            if o['id']=='miso-coincident-peak-2044':o.update(source=new['source'],document_sha256=new['document_sha256'])
        with self.assertRaisesRegex(ValueError,'different document'):validate.validate(same)


class RunnerHoldTests(unittest.TestCase):
    """extract_observations holds a newer edition instead of publishing it or calling it a conflict."""
    def test_a_newer_edition_is_held_not_published(self):
        data=ledger();metrics={m['id']:m for m in data['metrics']};sources={s['id']:s for s in data['sources']}
        reg=json.loads((ROOT/'research/sources.json').read_text(encoding='utf-8'))
        source=next(s for s in reg['sources'] if s['id']=='miso-ltlf-whitepaper-2026-05');sources[source['id']]=source
        document='MISO projects coincident peak load to grow from 124 GW in 2026 to 184 GW by 2046, driven by data centers.'
        candidate={'metric':'miso-coincident-peak-ltlf-gw','year':2046,'period':'2046','value':184,'upper':None,'status':'forecast',
                   'precision':'approx','note':'','evidence':'coincident peak load to grow from 124 GW in 2026 to 184 GW by 2046'}
        replies=iter([{'observations':[candidate]},{'verdicts':[{'index':0,'supported':True,'reason':'Direct support.'}]}])
        before=len(data['observations']);collection={}
        with tempfile.TemporaryDirectory() as tmp,patch.object(research,'LOCAL',Path(tmp)),patch.object(research,'ollama',side_effect=lambda *a,**k:next(replies)):
            accepted=research.extract_observations({'_instructions':'i','_coverage':'c','max_candidates_per_document':8},source,document,
                [metrics['miso-coincident-peak-ltlf-gw']],data,metrics,sources,{'model_calls':0},[],collection)
            holds=list((Path(tmp)/'review-candidates').glob('edition-*.json'))
            self.assertEqual(len(holds),1)
            item=json.loads(holds[0].read_text(encoding='utf-8'))
        self.assertEqual(accepted,[])
        self.assertEqual(len(data['observations']),before,'nothing published by the runner')
        self.assertEqual(collection['editions_held'],1)
        self.assertEqual([r['record']['value'] for r in item['records']],[184])

    def test_monitoring_cannot_publish_an_edition_link(self):
        head=ledger();after=copy.deepcopy(head)
        after['observations'].append(dict(rec('miso-coincident-peak-ltlf-gw',2046,184,'miso-ltlf-whitepaper-2026-05'),edition_supersedes=['miso-coincident-peak-2044']))
        excerpts=json.loads((ROOT/'site/data/excerpts.json').read_text(encoding='utf-8'))
        with self.assertRaisesRegex(ValueError,'Monitoring cannot issue corrections'):
            research.validate_monitoring_delta(head,after,excerpts,excerpts)


if __name__=='__main__':
    unittest.main()
