"""News intake must be able to reach the applications layer.

Measured 2026-09-12: every word in the reviewed topic vocabulary described energy, chips or
compute. Topics match whole words of a URL path, so a robotaxi story matched nothing --
/2026/09/zoox-robotaxi-expands-to-atlanta/ and /news/waymo-doubles-weekly-paid-rides/ were both
rejected by topical(), and Waymo is a tracked company with published weekly-ride figures. The
23 registered news outlets could carry the whole layer's coverage and none of it could get in.
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from find_feeds import TOPICS
from source_policy import topical

# Real shapes: an outlet slug, a section path, and a company channel's own post.
APPLICATIONS_PATHS = [
    '/2026/09/zoox-robotaxi-expands-to-atlanta/',
    '/news/waymo-doubles-weekly-paid-rides/',
    '/transportation/zoox-las-vegas-launch/',
    '/2026/08/driverless-service-opens-in-austin/',
    '/news/autonomous-fleet-milestone/',
    '/blog/self-driving-safety-report-2026/',
]


class ApplicationsVocabularyTests(unittest.TestCase):
    def test_a_robotaxi_story_can_match_the_reviewed_vocabulary(self):
        missed = [p for p in APPLICATIONS_PATHS if not topical(p, TOPICS)]
        self.assertEqual(missed, [], 'news intake still cannot reach these: %s' % missed)

    def test_the_registered_outlets_carry_the_widened_vocabulary(self):
        """A policy stores its own snapshot of the list, so widening the constant is not enough."""
        registry = json.loads((ROOT/'research/sources.json').read_text(encoding='utf-8'))
        full = [sid for sid, p in registry['collection'].items() if len(p.get('topics') or []) > 40]
        self.assertGreater(len(full), 20, 'expected the news outlets to carry the full vocabulary')
        for sid in full:
            with self.subTest(source=sid):
                self.assertEqual(registry['collection'][sid]['topics'], list(TOPICS))

    def test_the_published_mirror_matches_the_registry(self):
        registry = json.loads((ROOT/'research/sources.json').read_text(encoding='utf-8'))
        books = json.loads((ROOT/'site/data/source-books.json').read_text(encoding='utf-8'))
        self.assertEqual(books['collection'], registry['collection'])

    def test_the_vocabulary_still_rejects_an_unrelated_story(self):
        """Widening must not turn the filter off; 'ai' matching 'aim' already cost a model call."""
        for path in ['/2026/09/snapchat-adds-a-new-lens/', '/sports/driver-wins-at-monza/',
                     '/recipes/self-rising-flour-substitutes/']:
            with self.subTest(path=path):
                self.assertFalse(topical(path, TOPICS), path)


if __name__ == '__main__':
    unittest.main()
