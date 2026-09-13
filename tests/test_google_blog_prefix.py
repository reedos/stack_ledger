"""A company channel must not spend model calls on its own consumer marketing.

google-blog-index was registered on 2026-09-12 with a /products-and-platforms/ prefix. In the
5-hour run of 2026-09-13 it became the second-largest source of wasted model calls: of the 12
blog.google paths fetched, every off-thesis one came from that prefix -- football features,
password managers, running-race tips, a short film, Google One plan updates -- and every
on-thesis one came from /innovation-and-ai/ (Finland clean energy, the Google AI commitment).

Sixteen of nineteen wasted calls on this channel came from a prefix I chose. The paths below are
the ones the run actually fetched, not invented examples.

Not changed, and recorded here because it was tried: MODEL_BRIEF.md was edited in the same
sitting to admit launches explicitly, on the theory that its "Exclude ... promotional claims"
line was overriding the task prompt. Measured against the real x.ai/news/grok-4-6 document over
three trials each, the original brief accepted the note 2 times in 3 and both edited variants
accepted it 0 times in 6. The edit was reverted. The brief already admits launches -- the same
run produced three Company announcements -- so the premise was wrong.
"""
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))

BRIEF = (ROOT/'research/MODEL_BRIEF.md').read_text(encoding='utf-8')


def task_prompt():
    src = (ROOT/'scripts/research.py').read_text(encoding='utf-8')
    m = re.search(r"'task':f'Produce at most one concise research note(.*?)','evidence_rules'", src, re.S)
    assert m, 'the note task prompt has moved'
    return m.group(1)


class GoogleBlogPrefixTests(unittest.TestCase):
    """Measured against what the run actually fetched, not against intuition."""

    NOISE = ['/products-and-platforms/products/search/football-features-google-search/',
             '/products-and-platforms/platforms/android/switch-password-managers/',
             '/products-and-platforms/products/google-one/fall-2026-ai-plan-updates/',
             '/products-and-platforms/products/search/running-race-training-tips/',
             '/products-and-platforms/products/gemini/ai-navigate-bureaucracy/']
    KEEP = ['/innovation-and-ai/infrastructure-and-cloud/global-network/clean-energy-finland/',
            '/innovation-and-ai/infrastructure-and-cloud/global-network/google-ai-commitment-to-finland/',
            '/innovation-and-ai/models-and-research/google-research/mapping-global-methane-emissions/']

    def setUp(self):
        self.registry = json.loads((ROOT/'research/sources.json').read_text(encoding='utf-8'))
        self.policy = self.registry['collection']['google-blog-index']
        self.source = next(s for s in self.registry['sources'] if s['id'] == 'google-blog-index')

    def test_the_marketing_prefix_is_gone(self):
        self.assertNotIn('/products-and-platforms/', self.policy['path_prefixes'])

    def test_the_on_thesis_prefix_remains(self):
        self.assertEqual(self.policy['path_prefixes'], ['/innovation-and-ai/'])

    def test_every_page_the_run_wasted_a_call_on_is_now_refused(self):
        from source_policy import discoverable
        for path in self.NOISE:
            with self.subTest(path=path):
                self.assertFalse(discoverable(self.source, 'https://blog.google'+path, self.policy))

    def test_every_on_thesis_page_is_still_reachable(self):
        from source_policy import discoverable
        for path in self.KEEP:
            with self.subTest(path=path):
                self.assertTrue(discoverable(self.source, 'https://blog.google'+path, self.policy))

    def test_the_published_mirror_matches_the_registry(self):
        books = json.loads((ROOT/'site/data/source-books.json').read_text(encoding='utf-8'))
        self.assertEqual(books['collection'], self.registry['collection'])


if __name__ == '__main__':
    unittest.main()
