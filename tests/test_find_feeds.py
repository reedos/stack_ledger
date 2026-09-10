import json
import sys
import unittest
from pathlib import Path
from urllib.error import HTTPError

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import find_feeds as ff
from source_policy import grade_for


class FakeFetcher:
    """A network-free stand-in for research.Fetcher: check_robots always allows, and get()
    pops canned results/exceptions off a queue in call order -- enough to exercise discover()'s
    retry-once-on-4xx path (deliverable 2) without a live host."""
    def __init__(self,gets):
        self.gets=list(gets);self.calls=0
    def check_robots(self,url):
        from urllib.parse import urlparse
        return urlparse(url).hostname
    def get(self,url,host,raw=False,headers=None,capture=None):
        self.calls+=1
        result=self.gets.pop(0)
        if isinstance(result,Exception):raise result
        return result


class FeedDiscoveryTests(unittest.TestCase):
    def test_autodiscovery_reads_alternate_links_and_feed_anchors_only(self):
        p=ff.FeedLinks()
        p.feed('<link rel="alternate" type="application/rss+xml" href="/news/rss.xml"><link rel="stylesheet" href="/a.css">'
               '<a href="/newsroom/feed">RSS</a><a href="/about">About</a><a href="https://twitter.com/x">X</a>')
        self.assertEqual(p.feeds,['/news/rss.xml']);self.assertEqual(p.anchors,['/newsroom/feed'])

    def test_company_hosts_come_from_registry_and_company_records_only(self):
        registry=json.loads((ROOT/'research/sources.json').read_text(encoding='utf-8'))
        ecosystem=json.loads((ROOT/'research/ecosystem.json').read_text(encoding='utf-8'))
        hosts=ff.company_hosts(registry,ecosystem)
        self.assertEqual(set(hosts),{c['id'] for c in ecosystem['companies']})
        every=set().union(*hosts.values())
        self.assertNotIn('github.com',every);self.assertNotIn('huggingface.co',every)
        self.assertTrue(all(h and '/' not in h for h in every))

    def test_registration_shape_matches_reviewed_policy_rules(self):
        # Rank 3 (technical) sources must be weekly; rank 4 newsroom feeds are daily. Topics are the standard set.
        registry=json.loads((ROOT/'research/sources.json').read_text(encoding='utf-8'))
        self.assertEqual(ff.TOPICS,registry['discovery_keywords'])
        for sid,p in registry['collection'].items():
            if p['rank']==3:self.assertIn(p['cadence'],{'weekly','manual'},sid)

    def test_feedlinks_accepts_the_full_reviewed_feed_type_set(self):
        # ENR's own homepage declares its feed as type="application/xml", not the narrower
        # application/rss+xml -- FEED_TYPES (already used for content-type checks elsewhere)
        # is the single reviewed set autodiscovery matches against, so this stays in sync.
        p=ff.FeedLinks()
        p.feed('<link rel="alternate" type="application/xml" title="RSS Feed" href="/rss/articles">')
        self.assertEqual(p.feeds,['/rss/articles'])
        for good_type in ff.FEED_TYPES:
            q=ff.FeedLinks();q.feed(f'<link rel="alternate" type="{good_type}" href="/f">')
            self.assertEqual(q.feeds,['/f'],good_type)
        r=ff.FeedLinks();r.feed('<link rel="alternate" type="text/html" href="/not-a-feed">')
        self.assertEqual(r.feeds,[])

    def test_discover_retries_once_on_a_4xx_then_succeeds(self):
        # Deliverable 2: a single bad response never blackballs an outlet.
        page='<link rel="alternate" type="application/rss+xml" href="/feed">'
        fetcher=FakeFetcher([HTTPError('https://x.example/',403,'Forbidden',{},None),page])
        log=[]
        self.assertEqual(ff.discover(fetcher,'x.example',log),['https://x.example/feed'])
        self.assertEqual(log,[])
        self.assertEqual(fetcher.calls,2)

    def test_discover_gives_up_after_a_second_4xx(self):
        fetcher=FakeFetcher([HTTPError('https://x.example/',403,'Forbidden',{},None),
                              HTTPError('https://x.example/',403,'Forbidden',{},None)])
        log=[]
        self.assertEqual(ff.discover(fetcher,'x.example',log),[])
        self.assertEqual(log,[{'host':'x.example','stage':'root','error':'HTTPError','detail':403}])

    def test_discover_does_not_retry_a_non_4xx_failure(self):
        fetcher=FakeFetcher([TimeoutError('slow host')])
        log=[]
        self.assertEqual(ff.discover(fetcher,'x.example',log),[])
        self.assertEqual(fetcher.calls,1)
        self.assertEqual(log,[{'host':'x.example','stage':'root','error':'TimeoutError','detail':None}])


class OutletCandidateFileTests(unittest.TestCase):
    """Deliverable 1/4: the reviewed research/news-outlets.json candidate file's shape."""
    def test_the_reviewed_file_itself_loads_and_validates(self):
        data=ff.load_outlets()
        self.assertEqual(data['version'],1)
        self.assertTrue(data['outlets'])
        self.assertIn('Data Center Frontier',{o['name'] for o in data['outlets']})

    def base(self,entry):
        return {'version':1,'reviewed_at':'2026-09-10T00:00:00Z','outlets':[entry]}

    def test_outlet_needs_https_home_and_reviewed_layers(self):
        for bad in [
            {'name':'X','home':'http://x.example/','layers':['chips']},      # not https
            {'name':'X','home':'https://x.example/','layers':[]},            # empty layers
            {'name':'X','home':'https://x.example/','layers':['not-a-layer']},
            {'name':'X','home':'https://x.example/'},                        # missing layers
            {'name':'X','home':'https://user:pw@x.example/','layers':['chips']},
        ]:
            with self.assertRaises(ValueError):ff.validate_outlets_file(self.base(bad))

    def test_duplicate_outlet_host_rejected(self):
        data={'version':1,'reviewed_at':'2026-09-10T00:00:00Z','outlets':[
            {'name':'A','home':'https://x.example/','layers':['chips']},
            {'name':'B','home':'https://x.example/other','layers':['chips']}]}
        with self.assertRaises(ValueError):ff.validate_outlets_file(data)

    def test_status_needs_its_matching_field(self):
        with self.assertRaises(ValueError):
            ff.validate_outlets_file(self.base({'name':'A','home':'https://x.example/','layers':['chips'],'status':'registered'}))
        with self.assertRaises(ValueError):
            ff.validate_outlets_file(self.base({'name':'A','home':'https://x.example/','layers':['chips'],'status':'rejected'}))
        self.assertTrue(ff.validate_outlets_file(self.base({'name':'A','home':'https://x.example/','layers':['chips'],'status':'registered','source_id':'outlet-x-1'})))
        self.assertTrue(ff.validate_outlets_file(self.base({'name':'A','home':'https://x.example/','layers':['chips'],'status':'rejected','reason':'no feed'})))

    def test_future_reviewed_at_rejected(self):
        with self.assertRaises(ValueError):
            ff.validate_outlets_file({'version':1,'reviewed_at':'2099-01-01T00:00:00Z','outlets':[]})


class OutletRegistrationShapeTests(unittest.TestCase):
    """Deliverable 1: every outlet-* source registered today matches the reviewed shape."""
    def test_registered_outlets_match_the_reviewed_shape(self):
        registry=json.loads((ROOT/'research/sources.json').read_text(encoding='utf-8'))
        outlet_sources=[s for s in registry['sources'] if s['id'].startswith('outlet-')]
        self.assertGreaterEqual(len(outlet_sources),4)
        for s in outlet_sources:
            p=registry['collection'][s['id']]
            self.assertEqual(p['rank'],4,s['id'])
            self.assertEqual(p['claim_type'],'news',s['id'])
            self.assertTrue(p['excerpts'],s['id'])
            self.assertEqual(p['cadence'],'daily',s['id'])
            self.assertEqual(p['weekday'],0,s['id'])
            self.assertTrue(s['index'],s['id'])
            self.assertEqual(len(p['path_prefixes']),1,s['id'])
            self.assertEqual(p['topics'],ff.TOPICS,s['id'])
            self.assertIsNone(p['company_id'],s['id'])
            self.assertEqual(p['region_book'],'global',s['id'])


class GradeInvariantTests(unittest.TestCase):
    """Deliverable 3: every claim_type: news source grades C and carries excerpts + index."""
    def test_every_news_source_grades_c_with_excerpts_and_index(self):
        registry=json.loads((ROOT/'research/sources.json').read_text(encoding='utf-8'))
        by_id={s['id']:s for s in registry['sources']}
        news=[sid for sid,p in registry['collection'].items() if p['claim_type']=='news']
        self.assertGreaterEqual(len(news),4)
        for sid in news:
            p=registry['collection'][sid]
            self.assertEqual(grade_for(p),'C',sid)
            self.assertTrue(p['excerpts'],sid)
            self.assertTrue(by_id[sid]['index'],sid)


class OutletRejectionReasonTests(unittest.TestCase):
    """Deliverable 1/4: the recorded reason actually explains the probe's own finding."""
    def test_disallowed_robots_takes_priority_over_a_bare_not_found(self):
        rows=[{'feed_url':None,'host':'x.example','status':'no_candidate_feed','robots':'disallowed'}]
        self.assertIn('robots.txt disallows',ff.outlet_rejection_reason(rows))

    def test_unreadable_robots_policy_explains_the_empty_result(self):
        rows=[{'feed_url':None,'host':'x.example','status':'no_candidate_feed','robots':'unavailable'}]
        self.assertIn('robots.txt could not be read',ff.outlet_rejection_reason(rows))

    def test_a_row_that_reached_a_feed_url_outranks_a_bare_not_found_row(self):
        rows=[{'feed_url':None,'host':'x.example','status':'no_candidate_feed','robots':'allowed'},
              {'feed_url':'https://x.example/rss.rss','status':'ineligible','robots':'allowed'}]
        self.assertIn('did not parse',ff.outlet_rejection_reason(rows))

    def test_http_error_without_a_feed_url_names_the_homepage(self):
        rows=[{'feed_url':None,'host':'x.example','status':'http_error','detail':403,'robots':'allowed'}]
        reason=ff.outlet_rejection_reason(rows)
        self.assertIn('403',reason);self.assertIn('twice',reason);self.assertIn('homepage',reason)


if __name__=='__main__':unittest.main()
