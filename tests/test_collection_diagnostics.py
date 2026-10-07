import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import collection_diagnostics as diagnostics
import nightly


class DiagnosticsTests(unittest.TestCase):
    def test_counts_preserve_failures_without_copying_source_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / 'batches').mkdir()
            batch = {'monitoring': {'source_failures': [
                {'reason': 'HTTP 403'}, {'reason': 'robots blocked'},
                {'reason': 'URL outside approved public host: https://private.example'}]},
                'discovery': {'errors': [{'stage': 'search', 'http_status': 429},
                                        {'stage': 'screen', 'check': 'untrusted text'}]}}
            (folder / 'batches/1.json').write_text(json.dumps(batch), encoding='utf-8')
            result = diagnostics.summarize(folder)
            self.assertEqual(result['source_failures']['total'], 3)
            self.assertEqual(result['discovery_errors']['by_category']['HTTP 429'], 1)
            self.assertNotIn('private.example', json.dumps(result))
            self.assertNotIn('untrusted text', json.dumps(result))
            (folder / 'batches/2.json').write_text('{broken', encoding='utf-8')
            self.assertEqual(diagnostics.summarize(folder)['unreadable_batches'], 1)
            self.assertEqual(diagnostics.summarize(folder)['status'], 'partial')

    def test_missing_session_is_not_a_clean_bill_of_health(self):
        self.assertEqual(diagnostics.for_session(Path('.'), '../other')['status'], 'unavailable')
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(diagnostics.summarize(Path(tmp))['status'], 'partial')

    def health(self, discovery, counts):
        from contextlib import ExitStack
        with ExitStack() as stack:
            for name in ('collection_summary', 'stale_figures', 'disk_usage_top', 'repo_size',
                         'pending_decisions', 'check_storage'):
                stack.enter_context(patch.object(nightly, name, return_value={}))
            stack.enter_context(patch.object(nightly, 'pdf_reader', return_value={'status': 'ok'}))
            stack.enter_context(patch.object(nightly, 'discovery_health', return_value=discovery))
            stack.enter_context(patch.object(nightly, 'load_receipt', return_value={}))
            stack.enter_context(patch.object(diagnostics, 'for_session', return_value=counts))
            return nightly.stage_health(Path('.'), '2026-10-07')['status']

    def test_unavailable_provider_or_collection_gaps_make_health_partial(self):
        clean = {'status': 'ok', 'source_failures': {'total': 0}, 'discovery_errors': {'total': 0}}
        self.assertEqual(self.health({}, clean), 'ok')
        self.assertEqual(self.health({'search_provider': {'status': 'unavailable'}}, clean), 'partial')
        self.assertEqual(self.health({'capacity_reached': True}, clean), 'partial')
        self.assertEqual(self.health({}, {**clean, 'source_failures': {'total': 96}}), 'partial')


if __name__ == '__main__':
    unittest.main()
