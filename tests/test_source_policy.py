import copy
import json
import sys
import unittest
from datetime import date
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from source_policy import discoverable, due, append_excerpt, validate_excerpts, validate_registry
from research import duplicate_or_conflict, source_queue
from validate_agenda import validate_files

class SourcePolicyTests(unittest.TestCase):
    def setUp(self):
        read=lambda p:json.loads((ROOT/p).read_text(encoding='utf-8'))
        self.registry=read('research/sources.json');self.ledger=read('site/data/ledger.json')
        self.companies={c['id'] for c in read('research/ecosystem.json')['companies']}
        self.source=next(s for s in self.ledger['sources'] if s['id']=='marvell-cpo-architecture')
        self.policy=self.registry['collection'][self.source['id']]
    def test_reviewed_artifacts(self):self.assertTrue(validate_files())
    def test_discovery_needs_path_and_topic(self):
        p=dict(self.policy,path_prefixes=['/blogs/'],topics=['co-packaged-optics'])
        self.assertTrue(discoverable(self.source,self.source['url'],p))
        for url in ['https://evil.example/blogs/co-packaged-optics','https://www.marvell.com/jobs/co-packaged-optics','https://www.marvell.com/blogs/culture','https://www.marvell.com/blogs/%2e%2e/co-packaged-optics','https://www.marvell.com/blogs/co-packaged-optics?next=other']:
            self.assertFalse(discoverable(self.source,url,p))
        self.assertFalse(discoverable(self.source,self.source['url'],{}))
    def test_wildcards_and_daily_technical_pass_rejected(self):
        for change in [{'path_prefixes':['/*']},{'cadence':'daily'}]:
            r=copy.deepcopy(self.registry);r['collection'][self.source['id']].update(change)
            with self.assertRaises(ValueError):validate_registry(r,self.companies)
    def test_weekly_technical_queue(self):
        monday=date(2026,9,7);tuesday=date(2026,9,8)
        self.assertTrue(due(self.policy,monday));self.assertFalse(due(self.policy,tuesday))
        self.assertNotIn(self.source['id'],[s['id'] for s in source_queue(self.registry,tuesday)])
    def test_manual_archives_never_enter_monitoring(self):
        manual={sid for sid,p in self.registry['collection'].items() if p['cadence']=='manual'}
        self.assertIn('epoch-eci-dataset',manual)
        for weekday in range(7):
            day=date(2026,9,7+weekday)
            for attempted in [None,{},dict.fromkeys(manual,'2020-01-01T00:00:00Z')]:
                self.assertFalse(manual & {s['id'] for s in source_queue(self.registry,day,attempted=attempted)})
            for sid in manual:self.assertFalse(due(self.registry['collection'][sid],day))
        with self.assertRaisesRegex(ValueError,'maintainer import'):
            source_queue(self.registry,date(2026,9,8),['epoch-eci-dataset'])
        # Featured priority cannot override a manual restriction either.
        self.registry['collection']['iea-2026']['cadence']='manual'
        self.assertNotIn('iea-2026',{s['id'] for s in source_queue(self.registry,date(2026,9,8),attempted={})})
    def test_manual_sources_cannot_enable_extraction(self):
        self.registry['collection']['epoch-eci-dataset']['excerpts']=True
        with self.assertRaisesRegex(ValueError,'Manual sources'):validate_registry(self.registry,self.companies)
    def test_excerpt_identity_and_quote_budget(self):
        d={'version':1,'excerpts':[]}
        append_excerpt(d,self.source,self.policy,'Optical connections connect the reference design.','Architecture description, not installed capacity.','2026-09-07T00:00:00Z','observation')
        validate_excerpts(d,self.ledger,self.registry)
        self.assertFalse(append_excerpt(d,self.source,self.policy,'Another quote','Another note','2026-09-07T00:00:00Z'))
        for key,value in [('company_id','nvidia'),('url','https://evil.example/'),('metric_ids',['invented']),('quote','word '*26)]:
            bad=copy.deepcopy(d);bad['excerpts'][0][key]=value
            with self.assertRaises(ValueError):validate_excerpts(bad,self.ledger,self.registry)
    def test_monthly_observations_and_revisions(self):
        metrics={m['id']:m for m in self.ledger['metrics']}
        old=next(o for o in self.ledger['observations'] if o['metric']=='census-dc-construction-saar' and o['period']=='2026-07')
        new=dict(old,period='2026-08',value=76000)
        self.assertIsNone(duplicate_or_conflict(new,[old],metrics))
        self.assertEqual(duplicate_or_conflict(dict(old,value=76000),[old],metrics),'conflict')
        with self.assertRaises(ValueError):duplicate_or_conflict(dict(new,period='August'),[old],metrics)
