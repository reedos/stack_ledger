"""When the model returns nothing, the review record says why -- per source.

Measured 2026-09-12: 1,173 empty model calls, 53% "document outside scope", 33% "duplicate of
existing record". The model stated every one of those reasons, and both extraction lanes wrote
them into a per-run histogram -- but record_review() was never handed the reason, so
.local/reviews.json held 902 empty outcomes with no cause, and no source could be named as the
one wasting calls. A targeting problem you cannot attribute is one you cannot fix.
"""
import sys
import unittest
from unittest import mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import research

SOURCE = {'id': 'src-probe', 'publisher': 'Probe', 'title': 'A probe page', 'url': 'https://example.com/p',
          'layers': ['chips'], 'published': '2026-09-01'}
DOC = ('The company reported that its new fabrication line reached 12,000 wafers per month in July 2026. '
       'It also said the second line remains on schedule.') * 6


def config():
    return {'_instructions': 'inst', '_coverage': 'cov', 'max_candidates_per_document': 3,
            'document_window_chars': 20000}


class NoteLanePassthroughTests(unittest.TestCase):
    def run_note(self, response):
        run = {'model_calls': 0}; quarantine = []; collection = {}
        with mock.patch.object(research, 'ollama', return_value=response):
            note = research.extract_note(config(), SOURCE, DOC, [], run, quarantine, collection, {})
        return note, run, collection

    def test_an_empty_answer_leaves_its_reason_for_the_caller(self):
        note, run, collection = self.run_note({'notes': [], 'empty_reason': 'document outside scope'})
        self.assertIsNone(note)
        self.assertEqual(run['model_calls'], 1)
        self.assertEqual(collection.get('_last_empty_reason'), 'document outside scope')
        self.assertEqual(collection['empty_reasons'], {'document outside scope': 1},
                         'the per-run histogram still counts it')

    def test_an_empty_answer_with_no_reason_leaves_nothing_to_misattribute(self):
        _, _, collection = self.run_note({'notes': []})
        self.assertNotIn('_last_empty_reason', collection)


class MetricsLanePassthroughTests(unittest.TestCase):
    def run_metrics(self, response):
        run = {'model_calls': 0, 'accepted': 0}; quarantine = []; collection = {}
        related = [{'id': 'm', 'title': 'Wafers per month', 'unit': 'wafers', 'min': 0, 'max': 10**6,
                    'layer': 'chips', 'scope': 'one fab'}]
        data = {'observations': [], 'sources': []}
        with mock.patch.object(research, 'ollama', return_value=response):
            accepted = research.extract_observations(config(), SOURCE, DOC, related, data, {'m': related[0]},
                                                     {SOURCE['id']: SOURCE}, run, quarantine, collection, None, {})
        return accepted, run, collection

    def test_an_empty_answer_leaves_its_reason_for_the_caller(self):
        accepted, run, collection = self.run_metrics({'observations': [], 'empty_reason': 'duplicate of existing record'})
        self.assertEqual(accepted, [])
        self.assertEqual(run['model_calls'], 1)
        self.assertEqual(collection.get('_last_empty_reason'), 'duplicate of existing record')
        self.assertEqual(collection['empty_reasons'], {'duplicate of existing record': 1})

    def test_an_empty_answer_with_no_reason_leaves_nothing_to_misattribute(self):
        _, _, collection = self.run_metrics({'observations': []})
        self.assertNotIn('_last_empty_reason', collection)


class CallSiteTests(unittest.TestCase):
    """The stash is only honest if the caller clears it before each call and pops it after."""

    def setUp(self):
        self.lines = (ROOT/'scripts/research.py').read_text(encoding='utf-8').splitlines()

    def preceding_code_line(self, needle):
        i = next(i for i, l in enumerate(self.lines) if needle in l)
        j = i-1
        while not self.lines[j].strip(): j -= 1
        return self.lines[j]

    def test_both_extract_calls_are_preceded_by_a_clear(self):
        for call in ('note=extract_note(', 'accepted_now=extract_observations('):
            with self.subTest(call=call):
                self.assertIn("collection.pop('_last_empty_reason',None)", self.preceding_code_line(call),
                              'a reason from the previous document could be attributed to this one')

    def test_both_review_records_receive_the_reason(self):
        src = '\n'.join(self.lines)
        for lane in ("record_review(reviews,note_key,'note'", "record_review(reviews,metrics_key,'metrics'"):
            with self.subTest(lane=lane):
                line = next(l for l in self.lines if lane in l)
                self.assertIn("empty_reason=collection.pop('_last_empty_reason',None)", line)


class RecordAndAggregateTests(unittest.TestCase):
    def test_record_review_stores_the_reason_when_given(self):
        reviews = {}
        with_reason = research.record_review(reviews, 'k1', 'note', 'src-a', 'empty', empty_reason='document outside scope')
        without = research.record_review(reviews, 'k2', 'note', 'src-a', 'empty')
        self.assertEqual(with_reason['empty_reason'], 'document outside scope')
        self.assertNotIn('empty_reason', without)

    def test_the_most_wasteful_source_comes_first(self):
        reviews = {}
        for i in range(5): research.record_review(reviews, f'a{i}', 'note', 'noisy-outlet', 'empty', empty_reason='document outside scope')
        for i in range(2): research.record_review(reviews, f'b{i}', 'metrics', 'frozen-page', 'empty', empty_reason='duplicate of existing record')
        research.record_review(reviews, 'c0', 'note', 'noisy-outlet', 'empty', empty_reason='no supported number for these metrics')
        research.record_review(reviews, 'd0', 'note', 'fine-source', 'accepted')          # no reason: not counted
        research.record_review(reviews, 'e0', 'note', 'quiet-source', 'empty')            # empty but unexplained: not counted
        by = research.empty_reasons_by_source(reviews)
        self.assertEqual(list(by), ['noisy-outlet', 'frozen-page'])
        self.assertEqual(by['noisy-outlet'], {'document outside scope': 5, 'no supported number for these metrics': 1})
        self.assertEqual(by['frozen-page'], {'duplicate of existing record': 2})

    def test_it_reads_the_shape_reviews_json_actually_has(self):
        """reviews.json is a dict keyed by review identity, and older entries carry no reason."""
        reviews = {'old': {'lane': 'note', 'source': 'legacy', 'outcome': 'empty'},
                   'new': {'lane': 'note', 'source': 'legacy', 'outcome': 'empty', 'empty_reason': 'other'}}
        self.assertEqual(research.empty_reasons_by_source(reviews), {'legacy': {'other': 1}})


if __name__ == '__main__':
    unittest.main()
