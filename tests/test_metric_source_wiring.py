"""What the crawler reads must be able to become a number.

Measured 2026-09-12, in a 15-minute verification session: 50 documents fetched, 33 reviewed, 21
sent to the model, and 0 observation candidates proposed. x.ai was the most-read host in the
session. The cause was not the model and not the A/B evidence gate -- every one of these channels
is `company-channel`, which grades B and passes validate's automated-observation rule. The cause
was that no metric named any of them, so research.py resolved `related` to an empty list and
returned at "if not related" before the metrics lane ran at all.

A discovered child page carries parent_source = the index that found it (research.py:1283), and
`related` is resolved through that parent (research.py:1303). So naming the index in a metric's
source_ids is what lets a newly published company post update that metric.
"""
import json
import sys
import unittest
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from source_policy import PROVENANCE_GRADE

# The company news sections registered 2026-09-11/12, and the host each one indexes.
WIRED_INDEXES = {
    'spacexai-news-index': 'x.ai',
    'openai-news-index': 'openai.com',
    'anthropic-news-index': 'www.anthropic.com',
    'claude-blog-index': 'claude.com',
    'google-blog-index': 'blog.google',
}
# Registered and read, but no metric in the catalog is sourced from these hosts at all. Wiring
# them would mean inventing metrics, which is a reviewed content decision, not a mapping.
KNOWN_UNWIRED = {'ibm-research-blog-index', 'ibm-think-news-index', 'meta-ai-blog-index'}


def ledger():
    return json.loads((ROOT/'site/data/ledger.json').read_text(encoding='utf-8'))


def registry():
    return json.loads((ROOT/'research/sources.json').read_text(encoding='utf-8'))


class MetricReachabilityTests(unittest.TestCase):
    def setUp(self):
        self.data = ledger()
        self.reg = {s['id']: s for s in registry()['sources']}
        self.named = set()
        for m in self.data['metrics']:
            self.named.update(m.get('source_ids') or [])

    def test_every_wired_index_is_named_by_at_least_one_metric(self):
        for sid in WIRED_INDEXES:
            with self.subTest(source=sid):
                self.assertIn(sid, self.named,
                              '%s is read every day and nothing it finds can become a number' % sid)

    def test_a_discovered_child_resolves_to_the_metrics_its_index_serves(self):
        """The exact expression research.py uses to decide whether the metrics lane runs."""
        metrics = {m['id']: m for m in self.data['metrics']}
        for sid in WIRED_INDEXES:
            child = dict(self.reg[sid], id='discovered-probe', parent_source=sid)
            related = [m for m in metrics.values()
                       if child.get('parent_source', child['id']) in (m.get('source_ids') or [])]
            with self.subTest(source=sid):
                self.assertTrue(related, 'a child of %s would still hit "if not related"' % sid)

    def test_these_channels_grade_high_enough_to_become_observations(self):
        """validate.py requires grade A or B for an automated numeric observation."""
        for sid in set(WIRED_INDEXES) | KNOWN_UNWIRED:
            with self.subTest(source=sid):
                self.assertIn(PROVENANCE_GRADE[self.reg[sid]['provenance']], {'A', 'B'})

    def test_each_index_is_only_wired_to_metrics_that_already_cite_its_host(self):
        """The mapping rule, so a later edit cannot quietly attach a channel to anything."""
        for m in self.data['metrics']:
            ids = m.get('source_ids') or []
            for sid in ids:
                if sid not in WIRED_INDEXES: continue
                hosts = {urlparse(self.reg[o]['url']).hostname for o in ids if o in self.reg}
                with self.subTest(metric=m['id'], index=sid):
                    self.assertIn(WIRED_INDEXES[sid], hosts,
                                  '%s cites %s but nothing else from that publisher' % (m['id'], sid))

    def test_the_unwired_channels_are_still_declared_rather_than_forgotten(self):
        for sid in KNOWN_UNWIRED:
            with self.subTest(source=sid):
                self.assertIn(sid, self.reg, 'registered but missing from the registry')

    def test_the_catalog_and_the_ledger_agree(self):
        """validate.py refuses to publish while these differ; the wiring edits both."""
        catalog = json.loads((ROOT/'research/catalog.json').read_text(encoding='utf-8'))
        self.assertEqual(catalog['metrics'], self.data['metrics'])


if __name__ == '__main__':
    unittest.main()
