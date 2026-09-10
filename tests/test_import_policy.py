import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import import_policy as ip
from validate import event_valid, source_valid

DOE_DOC = {'document_number': '2026-18370', 'title': 'Securing the United States Bulk-Power System',
           'publication_date': '2026-09-09', 'type': 'Notice', 'docket_ids': ['DOE-2026-HQ-2026-1123'],
           'agencies': [{'name': 'Energy Department', 'slug': 'energy-department'}],
           'html_url': 'https://www.federalregister.gov/documents/2026/09/09/2026-18370/securing-the-united-states-bulk-power-system'}

FERC_DOC = {'document_number': '2026-18151', 'title': 'DeepGreen Cook Inlet SPV, LLC; Notice of Preliminary Permit Application',
            'publication_date': '2026-09-04', 'type': 'Notice', 'docket_ids': ['Project No. 15423-000'],
            'agencies': [{'name': 'Energy Department', 'slug': 'energy-department'}, {'name': 'Federal Energy Regulatory Commission', 'slug': 'federal-energy-regulatory-commission'}],
            'html_url': 'https://www.federalregister.gov/documents/2026/09/04/2026-18151/deepgreen-cook-inlet'}

BIS_DOC = {'document_number': '2026-14132', 'title': 'Enhanced Favorable Treatment for the United Arab Emirates Under the Export Administration Regulations',
           'publication_date': '2026-06-01', 'type': 'Rule', 'docket_ids': [],
           'agencies': [{'name': 'Industry and Security Bureau', 'slug': 'industry-and-security-bureau'}],
           'html_url': 'https://www.federalregister.gov/documents/2026/06/01/2026-14132/enhanced-favorable-treatment'}

LONG_TITLE_DOC = {'document_number': '2026-99999', 'title': 'A' + 'very long federal register document title ' * 8,
                   'publication_date': '2026-08-01', 'type': 'Proposed Rule', 'docket_ids': [],
                   'agencies': [{'name': 'Environmental Protection Agency', 'slug': 'environmental-protection-agency'}],
                   'html_url': 'https://www.federalregister.gov/documents/2026/08/01/2026-99999/long-title-document'}


class PolicyTopicsConfigTests(unittest.TestCase):
    def test_reviewed_config_loads_and_validates(self):
        p = ip.policy(ROOT)
        self.assertEqual(p['api_base'], ip.API_BASE)
        self.assertTrue(p['queries'])
        self.assertEqual({q['id'] for q in p['queries']}, {q['id'] for q in p['queries']})   # ids unique (would raise otherwise)
        self.assertTrue(all(q['layer'] in {'energy', 'chips', 'infrastructure', 'models', 'applications'} for q in p['queries']))
        self.assertGreaterEqual(len(p['agencies']), 1)

    def test_since_date_uses_the_reviewed_lookback_window(self):
        self.assertEqual(ip.since_date(120, today=date(2026, 9, 10)), '2026-05-13')


class DocumentsUrlTests(unittest.TestCase):
    def test_url_carries_term_agency_and_date_facets(self):
        url = ip.documents_url('"data center" electricity', ['energy-department', 'industry-and-security-bureau'], '2026-05-13')
        self.assertTrue(url.startswith(ip.API_BASE))
        self.assertIn('conditions[term]=%22data%20center%22%20electricity', url)   # quotes/spaces percent-encoded
        self.assertIn('conditions[agencies][]=energy-department', url)
        self.assertIn('conditions[agencies][]=industry-and-security-bureau', url)
        self.assertIn('conditions[publication_date][gte]=2026-05-13', url)
        self.assertIn('order=newest', url)
        for field in ip.FIELDS:
            self.assertIn(f'fields[]={field}', url)


class ParseTests(unittest.TestCase):
    def test_parse_reads_the_results_list(self):
        body = b'{"count": 1, "results": [{"document_number": "2026-1"}]}'
        self.assertEqual(ip.parse(body), [{'document_number': '2026-1'}])

    def test_parse_rejects_unexpected_shape(self):
        with self.assertRaises(ValueError):
            ip.parse(b'{"results": "not-a-list"}')
        with self.assertRaises(ValueError):
            ip.parse(b'[]')


class SelectDocumentsTests(unittest.TestCase):
    def test_dedup_keeps_the_first_matching_querys_layer(self):
        query_results = [('energy', [DOE_DOC]), ('chips', [DOE_DOC])]   # same document from two queries
        candidates, chosen = ip.select_documents(query_results, 20)
        self.assertEqual(len(candidates), 1)
        doc, layer = candidates['2026-18370']
        self.assertEqual(layer, 'energy')   # first query wins

    def test_sorts_newest_first_and_caps_at_max_documents(self):
        query_results = [('energy', [DOE_DOC, FERC_DOC]), ('chips', [BIS_DOC])]
        candidates, chosen = ip.select_documents(query_results, 2)
        self.assertEqual(len(candidates), 3)
        self.assertEqual(len(chosen), 2)
        self.assertEqual([n for n, _ in chosen], ['2026-18370', '2026-18151'])   # 09-09, 09-04 beat 06-01

    def test_missing_document_number_is_skipped(self):
        candidates, chosen = ip.select_documents([('energy', [{'title': 'no number'}])], 20)
        self.assertEqual(candidates, {})


class SanitizeTests(unittest.TestCase):
    def test_truncates_with_ellipsis_and_strips_markup(self):
        result = ip.sanitize('<b>Title</b>\nwith\tcontrol chars', 12)
        self.assertLessEqual(len(result), 12)
        self.assertNotIn('<', result); self.assertNotIn('>', result)

    def test_short_values_pass_through_collapsed(self):
        self.assertEqual(ip.sanitize('  a   b  ', 20), 'a b')

    def test_empty_falls_back_to_untitled(self):
        self.assertEqual(ip.sanitize(None, 20), 'Untitled')


class DocumentMappingTests(unittest.TestCase):
    def setUp(self):
        self.publisher_by_slug = {a['slug']: a['publisher'] for a in ip.policy(ROOT)['agencies']}

    def test_source_and_event_are_internally_valid_grade_a(self):
        publisher = ip.publisher_for(DOE_DOC, self.publisher_by_slug, 'Federal Register')
        source = ip.document_source(DOE_DOC, 'energy', publisher)
        event = ip.document_event(DOE_DOC, 'energy', publisher, source['id'])
        approved = {source['id']: source}
        source_valid(source, approved)
        event_valid(event, approved)
        self.assertEqual(event['kind'], 'Government action')
        self.assertEqual(event['grade'], 'A')
        self.assertEqual(event['source'], source['id'])
        self.assertEqual(source['url'], DOE_DOC['html_url'])
        self.assertEqual(source['published'], '2026-09-09')
        self.assertEqual(source['license'], 'Public domain (U.S. government work)')
        self.assertEqual(source['layers'], ['energy'])

    def test_publisher_prefers_the_reviewed_agency_over_the_raw_api_name(self):
        publisher = ip.publisher_for(BIS_DOC, self.publisher_by_slug, 'Federal Register')
        self.assertEqual(publisher, 'U.S. Bureau of Industry and Security')

    def test_multi_agency_document_lists_every_agency_in_the_summary(self):
        publisher = ip.publisher_for(FERC_DOC, self.publisher_by_slug, 'Federal Register')
        event = ip.document_event(FERC_DOC, 'energy', publisher, 'federal-register-2026-18151')
        self.assertIn('Energy Department', event['summary'])
        self.assertIn('Federal Energy Regulatory Commission', event['summary'])
        self.assertIn('Project No. 15423-000', event['summary'])
        self.assertIn(FERC_DOC['html_url'], event['summary'])

    def test_long_title_is_truncated_for_the_event_but_more_generous_for_the_source(self):
        publisher = ip.publisher_for(LONG_TITLE_DOC, self.publisher_by_slug, 'Federal Register')
        source = ip.document_source(LONG_TITLE_DOC, 'energy', publisher)
        event = ip.document_event(LONG_TITLE_DOC, 'energy', publisher, source['id'])
        self.assertLessEqual(len(event['title']), 140)
        self.assertLessEqual(len(source['title']), 250)
        source_valid(source, {source['id']: source})
        event_valid(event, {source['id']: source})

    def test_source_id_is_stable_and_lowercase(self):
        source = ip.document_source(DOE_DOC, 'energy', 'U.S. Department of Energy')
        self.assertEqual(source['id'], 'federal-register-2026-18370')


if __name__ == '__main__':
    unittest.main()
