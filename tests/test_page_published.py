"""When a coverage row can say what day its article was published.

412 of 581 rows read "Date not stated" on 2026-09-13. Two causes, both fixed here:

  * The feed was seeded from evidence receipts, which store only url/sha256/text/retrieved_at.
    There was never a publication date in them to seed from.
  * The live parser read only <meta property="article:published_time"|"og:published_time"> and
    then fell back to a printed dateline. Measured over 53 real undated sources that day, that
    pair reached 70%, while schema.org JSON-LD alone carried a date on 74% of the same pages.
    Reading JSON-LD as well takes capture to 89%.

The rule these tests protect: a date is read from what the publisher asserted, or not recorded.
A wrong date is worse than "Date not stated", because a reader sorting by date trusts it.
"""
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import research

TODAY = datetime.now(timezone.utc).date()
TOMORROW = (TODAY + timedelta(days=1)).isoformat()


def parse(html):
    document = research.ReadableHTML()
    document.feed(html)
    return document


class IsoDay(unittest.TestCase):
    def test_accepts_the_three_shapes_publishers_actually_write(self):
        for value in ('2026-09-09', '2026-09-09T14:30:00Z', '2026-09-09T14:30:00+02:00',
                      '  2026-09-09T14:30:00.123456Z'):
            self.assertEqual(research.iso_day(value), '2026-09-09', value)

    def test_refuses_anything_that_is_not_a_machine_readable_day(self):
        for value in ('', None, 'September 9, 2026', '2026', '09/09/2026',
                      'Tue, 09 Sep 2026 14:30:00 GMT', 'draft-2026-09-09'):
            self.assertIsNone(research.iso_day(value), value)

    def test_refuses_an_impossible_day_rather_than_raising(self):
        self.assertIsNone(research.iso_day('2026-02-31'))
        self.assertIsNone(research.iso_day('2026-13-01'))

    def test_refuses_a_future_date(self):
        """A date after today is a template placeholder or an embargo stamp, not a publication."""
        self.assertIsNone(research.iso_day(TOMORROW))
        self.assertIsNone(research.iso_day('2099-01-01'))


class JsonLdCapture(unittest.TestCase):
    def test_reads_datePublished_out_of_a_ld_json_block(self):
        document = parse('<html><head><script type="application/ld+json">'
                         '{"@type":"NewsArticle","datePublished":"2026-08-31T09:00:00Z"}'
                         '</script></head><body><p>Body text.</p></body></html>')
        self.assertEqual(document.published_ldjson, '2026-08-31T09:00:00Z')

    def test_finds_it_inside_a_graph_wrapper(self):
        """Publishers commonly wrap the article in @graph beside Organization/WebSite nodes."""
        document = parse('<html><head><script type="application/ld+json">'
                         '{"@graph":[{"@type":"WebSite","name":"X"},'
                         '{"@type":"Article","datePublished":"2026-07-23"}]}'
                         '</script></head><body><p>Body.</p></body></html>')
        self.assertEqual(research.page_published(document, document.readable()),
                         ('2026-07-23', 'ldjson'))

    def test_a_malformed_block_does_not_break_the_page(self):
        """These blocks are often truncated or contain stray markup; json.loads would throw."""
        document = parse('<html><head><script type="application/ld+json">'
                         '{"@type":"Article","datePublished":"2026-07-23",'
                         '</script></head><body><p>Body.</p></body></html>')
        self.assertEqual(document.published_ldjson, '2026-07-23')

    def test_ld_json_never_leaks_into_readable_text(self):
        """The block is metadata. If it reached readable(), it would be fed to the model as
        document text and could carry instructions."""
        document = parse('<html><head><script type="application/ld+json">'
                         '{"datePublished":"2026-07-23","description":"SECRETMARKER"}'
                         '</script></head><body><p>Real body.</p></body></html>')
        self.assertNotIn('SECRETMARKER', document.readable())
        self.assertNotIn('datePublished', document.readable())

    def test_an_ordinary_script_is_not_read_for_dates(self):
        document = parse('<html><head><script>var datePublished = "2026-07-23";</script>'
                         '</head><body><p>Body.</p></body></html>')
        self.assertIsNone(document.published_ldjson)


class MetaNameCapture(unittest.TestCase):
    def test_reads_the_name_variants_publishers_use(self):
        for name in ('date', 'pubdate', 'parsely-pub-date', 'citation_publication_date'):
            document = parse(f'<html><head><meta name="{name}" content="2026-09-10">'
                             '</head><body><p>Body.</p></body></html>')
            self.assertEqual(research.page_published(document, document.readable()),
                             ('2026-09-10', 'meta-name'), name)

    def test_ignores_an_unrelated_meta_name(self):
        document = parse('<html><head><meta name="og:image:width" content="2026">'
                         '</head><body><p>Body.</p></body></html>')
        self.assertEqual(research.page_published(document, document.readable()), (None, None))


class Precedence(unittest.TestCase):
    ARTICLE_META = '<meta property="article:published_time" content="2026-01-01T00:00:00Z">'
    LDJSON = ('<script type="application/ld+json">{"datePublished":"2026-02-02"}</script>')
    NAME_META = '<meta name="date" content="2026-03-03">'
    DATELINE = '<body><p>Published March 4, 2026</p><p>Body.</p></body>'

    def page(self, *head):
        return '<html><head>' + ''.join(head) + '</head>' + self.DATELINE + '</html>'

    def test_the_article_meta_tag_wins(self):
        document = parse(self.page(self.ARTICLE_META, self.LDJSON, self.NAME_META))
        self.assertEqual(research.page_published(document, document.readable()),
                         ('2026-01-01', 'meta'))

    def test_ld_json_beats_the_name_tag_and_the_dateline(self):
        document = parse(self.page(self.LDJSON, self.NAME_META))
        self.assertEqual(research.page_published(document, document.readable()),
                         ('2026-02-02', 'ldjson'))

    def test_the_name_tag_beats_the_dateline(self):
        document = parse(self.page(self.NAME_META))
        self.assertEqual(research.page_published(document, document.readable()),
                         ('2026-03-03', 'meta-name'))

    def test_the_printed_dateline_is_the_last_resort(self):
        document = parse(self.page())
        self.assertEqual(research.page_published(document, document.readable()),
                         ('2026-03-04', 'dateline'))

    def test_a_page_that_states_no_date_yields_none(self):
        document = parse('<html><head></head><body><p>No date anywhere.</p></body></html>')
        self.assertEqual(research.page_published(document, document.readable()), (None, None))

    def test_an_unusable_high_priority_value_falls_through_rather_than_stopping(self):
        """A publisher that emits an empty or future article:published_time must not shadow a
        good JSON-LD date below it."""
        for bad in ('', TOMORROW):
            document = parse(self.page(f'<meta property="article:published_time" content="{bad}">',
                                       self.LDJSON))
            self.assertEqual(research.page_published(document, document.readable()),
                             ('2026-02-02', 'ldjson'), bad)


class TimeElementIsNotTrusted(unittest.TestCase):
    def test_a_time_element_alone_does_not_produce_a_date(self):
        """<time datetime=...> is used for comment stamps, related-article teasers and
        "last updated" as often as for publication, so it is deliberately not a signal."""
        document = parse('<html><head></head><body><p>Body with no stated date.</p>'
                         '<time datetime="2026-05-05">May 5</time></body></html>')
        self.assertEqual(research.page_published(document, document.readable()), (None, None))


if __name__ == '__main__':
    unittest.main()
