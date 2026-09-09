import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from evidence_text import numeric_tokens, select_windows, context_text, contains_evidence, coverage, fold, locate, locate_in_windows, focus_text
from research import numeric_support
from document_formats import as_html, CollectionGap


class EvidenceTextTests(unittest.TestCase):
    def test_sentence_terminal_number_regression(self):
        self.assertTrue(numeric_support(2025,'Operationally supported since 1 July 2025.'))
        self.assertTrue(numeric_support(1234.5,'Total: 1,234.5.'))
        self.assertTrue(numeric_support(-4.2,'Change: -4.2%.'))
        self.assertEqual(numeric_tokens('The year is 2025.'),['2025'])

    def test_never_accept_partial_numbers_or_scale(self):
        for value,text in [(12,'112'),(12,'12.5'),(2,'1.2.3'),(100,'H100'),(123,'123,45'),(45,'123,45'),(5,'0.5'),(2000,'2 thousand'),(1,'1,234')]:
            with self.subTest(text=text):self.assertFalse(numeric_support(value,text))

    def test_glued_unit_letters_count_as_the_number_without_scaling(self):
        # Last session quarantined "$2B ARR in 2023" against value 2 in a USD billion metric.
        for value,text in [(2,'$2B ARR in 2023'),(20,'$20B+ in 2025'),(500,'a 500MW campus'),(65,'65k wafers'),(1.5,'1.5GW of capacity'),(2048,'2,048 I/O terminals')]:
            with self.subTest(text=text):self.assertTrue(numeric_support(value,text))
        for value,text in [(2000000000,'$2B'),(2000,'2k'),(100,'H100'),(200,'GB200'),(12,'12.5'),(45,'123,45')]:
            with self.subTest(text=text):self.assertFalse(numeric_support(value,text))

    def test_typographic_variants_locate_the_documents_own_text(self):
        doc='Intro.\nWaymo’s fleet — “rider‑only” — grew to 2,500 vehicles.\nTail.'
        quote='Waymo\'s fleet - "rider-only" - grew to 2,500 vehicles.'
        found=locate(doc,quote)
        self.assertEqual(found,'Waymo’s fleet — “rider‑only” — grew to 2,500 vehicles.')
        self.assertIn(found,doc)
        windows=select_windows(doc,'',18000)
        self.assertEqual(locate_in_windows(windows,quote),found)
        self.assertTrue(contains_evidence(windows,quote))
        self.assertEqual(fold('“A” – B…'),'"A" - B...')

    def test_near_match_snaps_to_source_but_stitched_passages_do_not(self):
        para='The company reported 550 employees on site as of June 23, 2026, and said hiring would continue through the year.'
        other='Separately, the operator said 1,200 construction workers were on site at peak in 2025.'
        doc=('Filler sentence about something else here.\n'*40)+para+'\n'+('Other filler text follows in the document.\n'*40)+other
        self.assertEqual(locate(doc,para.replace(' on site','')),para)
        self.assertIsNone(locate(doc,para[:60]+' '+other[-50:]))
        self.assertIsNone(locate(doc,'Completely different text that never appeared in the document at all.'))
        self.assertIsNone(locate(doc,''))

    def test_focus_text_surrounds_the_located_evidence(self):
        doc=('a'*3000)+'\nKey sentence with 42 units.\n'+('b'*3000)
        windows=select_windows(doc,'',18000)
        focused=focus_text(windows,'Key sentence with 42 units.',margin=100)
        self.assertIn('Key sentence with 42 units.',focused)
        self.assertLess(len(focused),400)

    def test_relevant_evidence_after_old_cutoff_is_visible(self):
        text=('General introduction.\n'*1100)+'\nGeothermal commissioning reached 120 MW after grid connection.\n'+('Other material.\n'*1500)
        windows=select_windows(text,'geothermal commissioning grid connection',18000)
        self.assertTrue(contains_evidence(windows,'Geothermal commissioning reached 120 MW after grid connection.'))
        self.assertLessEqual(coverage(text,windows)['exposed_characters'],18000)
        self.assertFalse(coverage(text,windows)['complete'])
        for w in windows:self.assertEqual(text[w['start']:w['end']],w['text'])

    def test_quote_cannot_bridge_omitted_text(self):
        windows=[{'start':0,'end':4,'text':'left'},{'start':20,'end':25,'text':'right'}]
        self.assertFalse(contains_evidence(windows,'left right'))
        self.assertFalse(contains_evidence(windows,context_text(windows)))
        self.assertTrue(coverage('short',select_windows('short','',18000))['complete'])

    def test_csv_and_json_preserve_tokens_without_executing_markup(self):
        value='year,value\n2025,1234.5\n2026,<script>bad</script>'
        self.assertIn('&lt;script&gt;',as_html(value,'text/csv'))
        self.assertIn('1234.5',as_html(value,'text/csv'))
        self.assertIn('2025',as_html('{"year":2025}','application/json'))
        with self.assertRaises(ValueError):as_html('bad','application/json')

    def test_feeds_have_links_and_dates_but_do_not_execute_xml_entities(self):
        rss='<rss><channel><item><title>New report</title><link>https://example.org/report</link><pubDate>2026-09-08</pubDate><description>Planned, not operating.</description></item></channel></rss>'
        self.assertIn('href="https://example.org/report"',as_html(rss,'application/rss+xml'))
        atom='<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Report</title><link href="https://example.org/report"/><updated>2026-09-08</updated></entry></feed>'
        self.assertIn('2026-09-08',as_html(atom,'application/atom+xml'))
        with self.assertRaises(CollectionGap):as_html('<!DOCTYPE rss [<!ENTITY x SYSTEM "file:///secret">]><rss/>','application/xml')
        with self.assertRaises(CollectionGap):as_html('<workbook/>','text/xml')


if __name__=='__main__':unittest.main()
