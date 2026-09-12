import copy
import json
import sys
import unittest
from datetime import date, timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from source_policy import discoverable, due, effective_cadence, append_excerpt, validate_excerpts, validate_registry
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
        # The night is the source's own reviewed weekday, not Monday: weekly sources are spread
        # across the week so that no night carries the whole corpus and none carries nothing.
        monday=date(2026,9,7)
        its_night=monday+timedelta(days=self.policy['weekday'])
        other_night=monday+timedelta(days=(self.policy['weekday']+1)%7)
        self.assertTrue(due(self.policy,its_night));self.assertFalse(due(self.policy,other_night))
        self.assertNotIn(self.source['id'],[s['id'] for s in source_queue(self.registry,other_night)])
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
    def test_rank_five_aggregator_cannot_be_an_index_source(self):
        # Deliverable 3: rank-5 trade/analyst aggregators remain private leads, never a walked
        # feed whose discovered children auto-publish.
        rank5=next(sid for sid,p in self.registry['collection'].items() if p['rank']==5)
        r=copy.deepcopy(self.registry)
        next(s for s in r['sources'] if s['id']==rank5)['index']=True
        with self.assertRaisesRegex(ValueError,'rank-5 aggregator'):validate_registry(r,self.companies)
    def test_real_registry_currently_passes_validate_registry(self):
        validate_registry(self.registry,self.companies)  # no rank-5 index source registered today
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

class AdaptiveCadenceTests(unittest.TestCase):
    """Deliverable 4: a daily source unchanged for long enough is checked less often."""
    def setUp(self):
        self.daily={'cadence':'daily','weekday':0}
        self.weekly={'cadence':'weekly','weekday':2}  # Wednesday
        self.wednesday=date(2026,9,9);self.thursday=date(2026,9,10)
    def test_two_arg_calls_are_unaffected(self):
        # Existing call sites (no state argument) must see exactly today's behavior.
        self.assertTrue(due(self.daily,self.thursday))
        self.assertTrue(due(self.weekly,self.wednesday));self.assertFalse(due(self.weekly,self.thursday))
        self.assertEqual(effective_cadence(self.daily),'daily')
    def test_seven_unchanged_checks_promote_daily_to_weekly(self):
        for streak in range(6):
            self.assertEqual(effective_cadence(self.daily,{'unchanged_streak':streak}),'daily')
        self.assertEqual(effective_cadence(self.daily,{'unchanged_streak':7}),'weekly')
        # Promoted to weekly: due only on the registered weekday, same as a registered-weekly source.
        promoted=dict(self.daily,weekday=2)
        self.assertTrue(due(promoted,self.wednesday,{'unchanged_streak':7}))
        self.assertFalse(due(promoted,self.thursday,{'unchanged_streak':7}))
    def test_six_more_unchanged_weekly_checks_promote_to_monthly(self):
        self.assertEqual(effective_cadence(self.daily,{'unchanged_streak':12}),'weekly')
        self.assertEqual(effective_cadence(self.daily,{'unchanged_streak':13}),'monthly')
        promoted=dict(self.daily,weekday=2)
        self.assertTrue(due(promoted,date(2026,9,2),{'unchanged_streak':13}))  # first Wednesday of September
        self.assertFalse(due(promoted,date(2026,9,9),{'unchanged_streak':13}))  # a later Wednesday, same month
    def test_any_change_resets_to_the_registered_cadence(self):
        # The caller resets unchanged_streak to zero on a real change (research.py's Fetcher);
        # effective_cadence reads that state fresh every time, with no memory of its own.
        self.assertEqual(effective_cadence(self.daily,{'unchanged_streak':0}),'daily')
        self.assertTrue(due(self.daily,self.thursday,{'unchanged_streak':0}))
    def test_weekly_promotes_to_monthly_and_manual_never_promotes(self):
        # Reversed 2026-09-12: weekly was exempt outright, so 169 fixed pages could never back
        # off. Four unchanged weekly checks now promote to monthly; manual is still untouched.
        self.assertEqual(effective_cadence(self.weekly,{'unchanged_streak':3}),'weekly')
        self.assertEqual(effective_cadence(self.weekly,{'unchanged_streak':4}),'monthly')
        self.assertEqual(effective_cadence(self.weekly,{'unchanged_streak':99}),'monthly')
        self.assertEqual(effective_cadence({'cadence':'manual'},{'unchanged_streak':99}),'manual')
    def test_state_missing_or_not_a_mapping_reads_as_unpromoted(self):
        # A Mock (or any non-dict) fetch-state stand-in must never crash cadence math.
        self.assertEqual(effective_cadence(self.daily,None),'daily')
        self.assertEqual(effective_cadence(self.daily,object()),'daily')
        self.assertEqual(effective_cadence(self.daily,{}),'daily')
