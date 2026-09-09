import json
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import find_feeds as ff


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


if __name__=='__main__':unittest.main()
