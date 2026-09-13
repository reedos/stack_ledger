"""Coverage: every article the crawler read, labelled by who published it.

Measured over the 5-hour session of 2026-09-13: 294 model calls, 219 documents rejected as
"document outside scope", 4 accepted. The note lane's bar is right for a record of verified
figures and wrong as the only route onto the site. This is a second lane with a smaller promise --
a row says a page exists and names its publisher, nothing more -- so the owner gets the latest of
everything in one place with lower-grade material included and labelled rather than discarded.

Relevance comes from the registry: we only ever fetch from reviewed sources, so anything we read
is on-thesis by construction. The filter here is SHAPE, not subject. Filtering by topic words was
measured on the same session and cost the two layers the owner most wanted fleshed out: 10% of
models and applications documents passed, against 17-29% for energy, chips and infrastructure,
because the topic vocabulary describes physical plant and those layers are software.
"""
import json
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import coverage_feed as cf
from source_policy import PROVENANCE_GRADE, PROVENANCE_LABEL

NOW = datetime(2026, 9, 13, 12, 0, tzinfo=timezone.utc)

SOURCES = {
    'outlet': {'id': 'outlet', 'publisher': 'Data Center Dynamics', 'provenance': 'news',
               'layers': ['infrastructure'], 'url': 'https://www.datacenterdynamics.com/en/rss/', 'index': True},
    'lab': {'id': 'lab', 'publisher': 'Anthropic', 'provenance': 'company-channel',
            'layers': ['models'], 'url': 'https://www.anthropic.com/news', 'index': True},
    'agency': {'id': 'agency', 'publisher': 'EIA', 'provenance': 'official',
               'layers': ['energy'], 'url': 'https://www.eia.gov/todayinenergy/', 'index': True},
}


def doc(url, source='outlet', title='A headline of a reasonable length', read_at=None, published=None):
    return {'url': url, 'source': source, 'title': title,
            'read_at': (read_at or NOW.isoformat()), 'published': published}


class ShapeFilterTests(unittest.TestCase):
    """What counts as an article. The registry already decided what counts as on-thesis."""

    INDEXES = {s['url'].rstrip('/') for s in SOURCES.values()}

    def keep(self, url):
        return cf.article(url, self.INDEXES)[0]

    def test_a_real_article_passes(self):
        for url in ['https://www.datacenterdynamics.com/en/news/meta-breaks-ground-in-kuna-idaho/',
                    'https://www.anthropic.com/news/claude-opus-5',
                    'https://x.ai/news/grok-4-6-amazon-bedrock']:
            with self.subTest(url=url):
                self.assertTrue(self.keep(url))

    def test_the_index_page_itself_is_not_an_article(self):
        for s in SOURCES.values():
            with self.subTest(url=s['url']):
                self.assertFalse(self.keep(s['url']))
                self.assertFalse(self.keep(s['url'].rstrip('/')))

    def test_section_and_nav_pages_are_refused(self):
        for url in ['https://www.anthropic.com/news', 'https://epoch.ai/blog',
                    'https://blog.google/', 'https://x.ai/news']:
            with self.subTest(url=url):
                self.assertFalse(self.keep(url))

    def test_feeds_and_non_html_are_refused(self):
        for url in ['https://example.com/news/feed', 'https://example.com/news/index.xml',
                    'https://investors.example.com/reports/2025-annual-report.pdf',
                    'https://example.com/data/series-download.csv']:
            with self.subTest(url=url):
                self.assertFalse(self.keep(url))

    def test_an_insecure_url_never_enters_the_feed(self):
        self.assertFalse(self.keep('http://example.com/news/some-long-article-slug/'))

    def test_each_refusal_states_a_reason(self):
        """A silent filter is how a coverage feed quietly stops covering something."""
        for url in ['https://www.anthropic.com/news', 'https://example.com/a/b.pdf']:
            with self.subTest(url=url):
                keep, why = cf.article(url, self.INDEXES)
                self.assertFalse(keep)
                self.assertTrue(why)

    def test_the_models_and_applications_slugs_the_topic_filter_rejected_now_pass(self):
        """The measured failure: software-layer slugs carry no energy or chip vocabulary."""
        for url in ['https://openai.com/index/a-business-that-scales-with-the-value-of-intelligence/',
                    'https://claude.com/blog/claude-in-chrome-generally-available',
                    'https://ai.meta.com/blog/introducing-muse-spark-meta-model-api/']:
            with self.subTest(url=url):
                self.assertTrue(self.keep(url))


class TitleTests(unittest.TestCase):
    def test_a_publisher_suffix_is_dropped(self):
        self.assertEqual(cf.clean_title('Introducing Grok 4.6 | SpaceXAI', 'https://x.ai/news/grok-4-6'),
                         'Introducing Grok 4.6')
        self.assertEqual(cf.clean_title('Introducing Claude Opus 5 \\ Anthropic', 'https://www.anthropic.com/news/x'),
                         'Introducing Claude Opus 5')

    def test_a_short_title_is_never_truncated_to_nothing(self):
        """Dropping a suffix must not leave a stub; "AI | Google" keeps its whole text."""
        self.assertEqual(cf.clean_title('AI | Google', 'https://blog.google/news/a-long-slug-here'), 'AI | Google')

    def test_a_missing_title_falls_back_to_a_readable_slug(self):
        self.assertEqual(cf.clean_title('', 'https://example.com/news/meta-breaks-ground-in-kuna/'),
                         'meta breaks ground in kuna')

    def test_a_slug_that_is_only_a_filename_yields_no_title(self):
        """Seeding from receipts produced 69 rows titled "default.aspx" and "empsit 09042026.htm".
        A row whose headline is a server filename is noise; the feed exists to be scanned."""
        for url in ['https://example.com/x/default.aspx', 'https://example.com/news/index.htm',
                    'https://example.com/news/2026/', 'https://example.com/a/view']:
            with self.subTest(url=url):
                self.assertIsNone(cf.clean_title('', url))

    def test_a_file_extension_is_never_part_of_a_headline(self):
        self.assertEqual(cf.clean_title('', 'https://www.bls.gov/news.release/empsit_09042026.htm'),
                         'empsit 09042026')

    def test_a_title_is_bounded(self):
        self.assertLessEqual(len(cf.clean_title('x'*5000, 'https://example.com/news/slug-here')), cf.MAX_TITLE)


class MergeTests(unittest.TestCase):
    def merge(self, existing, documents, now=NOW):
        return cf.merge(existing, documents, SOURCES, now=now)

    def test_a_row_carries_its_source_identity_and_nothing_it_invented(self):
        rows, _ = self.merge([], [doc('https://www.anthropic.com/news/claude-opus-5', 'lab')])
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['publisher'], 'Anthropic')
        self.assertEqual(row['provenance'], 'company-channel')
        self.assertEqual(row['layers'], ['models'])
        self.assertEqual(set(row), cf.ROW_FIELDS)

    def test_the_same_page_read_twice_occupies_one_row(self):
        url = 'https://www.datacenterdynamics.com/en/news/a-long-enough-article-slug/'
        rows, counts = self.merge([], [doc(url, read_at='2026-09-12T00:00:00+00:00'),
                                       doc(url, read_at='2026-09-13T00:00:00+00:00')])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['read_at'], '2026-09-13T00:00:00+00:00', 'the newer read wins')
        self.assertEqual(counts['added'], 1)

    def test_a_re_read_keeps_the_publication_date_first_seen(self):
        """A page re-read nightly must not drift to the top of the feed for ever."""
        url = 'https://www.datacenterdynamics.com/en/news/a-long-enough-article-slug/'
        first, _ = self.merge([], [doc(url, published='2026-09-01')])
        again, _ = self.merge(first, [doc(url, published=None, read_at='2026-09-13T06:00:00+00:00')])
        self.assertEqual(again[0]['published'], '2026-09-01')

    def test_newest_first_by_publication_then_by_read(self):
        rows, _ = self.merge([], [
            doc('https://a.example.com/news/older-article-slug/', published='2026-09-01'),
            doc('https://b.example.com/news/newer-article-slug/', published='2026-09-10'),
            doc('https://c.example.com/news/undated-article-slug/', read_at='2026-09-13T11:00:00+00:00')])
        self.assertEqual([r['url'].split('//')[1][0] for r in rows], ['c', 'b', 'a'],
                         'an undated page read today outranks a page published last week')

    def test_a_document_from_an_unregistered_source_is_refused(self):
        rows, counts = self.merge([], [doc('https://evil.example.com/news/a-long-slug-here/', 'nope')])
        self.assertEqual(rows, [])
        self.assertIn('source not registered', counts['dropped'])

    def test_rows_older_than_the_window_expire(self):
        old = (NOW - timedelta(days=cf.RETENTION_DAYS + 1)).isoformat()
        keep = (NOW - timedelta(days=cf.RETENTION_DAYS - 1)).isoformat()
        rows, counts = self.merge([], [doc('https://a.example.com/news/old-article-slug/', read_at=old),
                                       doc('https://b.example.com/news/new-article-slug/', read_at=keep)])
        self.assertEqual([r['url'].split('//')[1][0] for r in rows], ['b'])
        self.assertEqual(counts['expired'], 1)

    def test_the_row_cap_binds_and_is_reported(self):
        many = [doc('https://a.example.com/news/article-slug-%05d/' % i) for i in range(cf.MAX_ROWS + 25)]
        rows, counts = self.merge([], many)
        self.assertEqual(len(rows), cf.MAX_ROWS)
        self.assertEqual(counts['over_cap'], 25, 'a silent truncation reads as full coverage')


class ValidationTests(unittest.TestCase):
    def rows(self, **over):
        row = {'url': 'https://www.anthropic.com/news/claude-opus-5', 'title': 'Introducing Claude Opus 5',
               'source': 'lab', 'publisher': 'Anthropic', 'provenance': 'company-channel',
               'layers': ['models'], 'published': '2026-09-01', 'read_at': NOW.isoformat()}
        row.update(over)
        return [row]

    def test_a_well_formed_feed_passes(self):
        self.assertEqual(cf.validate_rows(self.rows(), list(SOURCES.values())), 1)

    def test_a_forged_provenance_is_refused(self):
        """The one way a row could overstate itself: the grade a reader sees derives from this."""
        with self.assertRaises(ValueError):
            cf.validate_rows(self.rows(provenance='official'), list(SOURCES.values()))

    def test_a_forged_publisher_or_layer_is_refused(self):
        for over in ({'publisher': 'Reuters'}, {'layers': ['energy']}):
            with self.subTest(over=over):
                with self.assertRaises(ValueError):
                    cf.validate_rows(self.rows(**over), list(SOURCES.values()))

    def test_an_unregistered_source_is_refused(self):
        with self.assertRaises(ValueError):
            cf.validate_rows(self.rows(source='ghost'), list(SOURCES.values()))

    def test_a_duplicate_url_is_refused(self):
        with self.assertRaises(ValueError):
            cf.validate_rows(self.rows()*2, list(SOURCES.values()))

    def test_an_insecure_url_is_refused(self):
        with self.assertRaises(ValueError):
            cf.validate_rows(self.rows(url='http://www.anthropic.com/news/x'), list(SOURCES.values()))

    def test_unexpected_fields_are_refused(self):
        row = self.rows()[0]; row['summary'] = 'a claim about what the page says'
        with self.assertRaises(ValueError):
            cf.validate_rows([row], list(SOURCES.values()))


class PublishedFeedTests(unittest.TestCase):
    """The feed as shipped."""

    def setUp(self):
        path = ROOT/'site/data/coverage.json'
        if not path.exists():
            self.skipTest('no coverage feed published yet')
        self.data = json.loads(path.read_text(encoding='utf-8'))
        self.rows = self.data['rows']

    def test_it_validates_against_the_registry(self):
        import validate
        self.assertEqual(validate.validate_coverage(), len(self.rows))

    def test_every_grade_including_the_low_ones_is_represented(self):
        """The point of the lane: C and D material included and labelled, not discarded."""
        grades = {PROVENANCE_GRADE[r['provenance']] for r in self.rows}
        self.assertTrue({'C'} & grades, 'no lower-grade coverage reached the feed')

    def test_the_software_layers_are_actually_covered(self):
        """models and applications are the layers this lane exists to reach."""
        for layer in ('models', 'applications'):
            with self.subTest(layer=layer):
                self.assertGreater(len([r for r in self.rows if layer in r['layers']]), 20)

    def test_every_row_can_be_labelled(self):
        for row in self.rows:
            with self.subTest(url=row['url']):
                self.assertIn(row['provenance'], PROVENANCE_LABEL)

    def test_the_published_mirror_carries_the_same_rows(self):
        """generated_at differs by design -- build stamps its own -- so compare the rows."""
        docs = ROOT/'docs/data/coverage.json'
        if docs.exists():
            self.assertEqual(json.loads(docs.read_text(encoding='utf-8'))['rows'], self.data['rows'])

    def test_no_row_is_titled_with_a_server_filename(self):
        import re
        bad = [r['title'] for r in self.rows if re.search(r'\.(htm|html|aspx|php|jsp)$', r['title'])]
        self.assertEqual(bad, [], 'these read as noise in a scannable feed: %s' % bad[:5])

    def test_every_title_is_long_enough_to_mean_something(self):
        short = [r['title'] for r in self.rows if len(r['title']) < 12]
        self.assertEqual(short, [], short[:5])


if __name__ == '__main__':
    unittest.main()
