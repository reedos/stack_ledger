import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import research
import evaluate_extraction as ee
from evidence_text import numeric_tokens
from source_policy import collection_for

ROOT = Path(__file__).resolve().parents[1]

FIXTURE_FILES = ['research/discovery-policy.json', 'research/RESEARCH_AGENDA.md', 'research/runtime.json',
                  'research/sources.json', 'research/CONSTITUTION.md', 'research/OPERATING_GUIDE.md',
                  'research/MODEL_BRIEF.md', 'research/ecosystem.json', 'research/delivery.json',
                  'research/fabric.json', 'research/expansion.json', 'research/agenda.json',
                  'research/claims.json', 'site/data/ledger.json']


def copy_fixture_root(path):
    """A working copy of the real, reviewed prompts/policy/ledger, isolated in a temp dir.

    Mirrors tests/test_research.py's RunnerTests.fixture(): real files, not hand-written
    stand-ins, so validation stays authentic.
    """
    for name in FIXTURE_FILES:
        target = path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / name).read_bytes())


def write_document(folder, url, text):
    folder.mkdir(parents=True, exist_ok=True)
    sha = research.digest(text)
    (folder / f'{sha}.json').write_text(
        json.dumps({'url': url, 'retrieved_at': research.now(), 'sha256': sha, 'text': text}), encoding='utf-8')


def canned_ollama(config, system, prompt, schema):
    """A fake model driven purely by schema shape, so it works regardless of call order."""
    keys = set(schema.get('properties', {}))
    payload = json.loads(prompt)
    if 'observations' in keys:
        return {'observations': [{'metric': 'ai-adoption', 'year': 2026, 'period': '2026', 'value': 90,
                                   'upper': None, 'status': 'observation', 'precision': 'eq', 'note': '',
                                   'evidence': 'In 2026, 90 percent of surveyed organizations reported AI use.'}]}
    if 'notes' in keys:
        return {'notes': [{'title': 'ExampleCorp expands data center capacity',
                            'summary': 'ExampleCorp announced plans to expand its data center footprint with new AI infrastructure investment.',
                            'layer': payload['allowed_layers'][0], 'kind': 'Company announcement',
                            'evidence': 'ExampleCorp announced plans to expand its data center footprint with new AI infrastructure investment.'}]}
    if 'verdicts' in keys:
        return {'verdicts': [{'index': c['index'], 'numbers_in_evidence': True, 'scope_matches': True,
                               'basis_correct': True, 'attribution_correct': True, 'defect': 'none',
                               'reason': 'Directly supported'} for c in payload['candidates']]}
    raise AssertionError(f'unexpected schema keys {keys}')


class ClassifyReasonTests(unittest.TestCase):
    def test_validator_vs_reviewer_stage(self):
        self.assertEqual(ee.classify_reason('Invalid evidence length'), 'validator')
        self.assertEqual(ee.classify_reason('wrong_number: value differs from evidence'), 'reviewer')
        self.assertEqual(ee.classify_reason('Conflicting proposal'), 'reviewer')


class MatchingTests(unittest.TestCase):
    def registry(self):
        return {'sources': [
            {'id': 'top-a', 'url': 'https://example.com/a', 'layers': ['energy'], 'publisher': 'Example'},
            {'id': 'top-b', 'url': 'https://sub.example.com/b', 'layers': ['chips'], 'publisher': 'Example'},
            {'id': 'other', 'url': 'https://another.test/x', 'layers': ['models'], 'publisher': 'Another'},
        ], 'collection': {'top-a': {'rank': 2}, 'top-b': {'rank': 1}, 'other': {'rank': 3}}}

    def test_exact_url_match(self):
        registry = self.registry()
        doc = {'url': 'https://example.com/a', 'sha256': 'x', 'text': 't' * 2000, 'retrieved_at': 'now'}
        source, match = ee.match_document(doc, registry['sources'], registry)
        self.assertEqual(match, 'exact')
        self.assertEqual(source['id'], 'top-a')
        self.assertEqual(source['url'], 'https://example.com/a')

    def test_host_match_picks_best_rank_and_keeps_real_url(self):
        registry = self.registry()
        registry['sources'].append({'id': 'top-c', 'url': 'https://example.com/c', 'layers': ['energy'], 'publisher': 'Example'})
        registry['collection']['top-c'] = {'rank': 5}
        doc = {'url': 'https://example.com/different-page', 'sha256': 'x', 'text': 't' * 2000, 'retrieved_at': 'now'}
        source, match = ee.match_document(doc, registry['sources'], registry)
        self.assertEqual(match, 'host')
        self.assertEqual(source['id'], 'top-a')  # rank 2 beats top-c's rank 5 on the same exact host
        self.assertEqual(source['url'], doc['url'])  # real fetched url shown, not the registered one
        self.assertNotIn('parent_source', source)

    def test_discovered_match_falls_back_to_base_domain(self):
        registry = self.registry()
        doc = {'url': 'https://blog.example.com/post', 'sha256': 'x', 'text': 't' * 2000, 'retrieved_at': 'now'}
        source, match = ee.match_document(doc, registry['sources'], registry)
        self.assertEqual(match, 'discovered')
        same_base = [s for s in registry['sources'] if ee.base_domain(ee.hostname(s['url'])) == 'example.com']
        expected_parent = ee.best_by_rank(same_base, registry)
        self.assertEqual(source['parent_source'], expected_parent['id'])
        self.assertEqual(source['url'], doc['url'])
        self.assertTrue(source['id'].startswith('eval-discovered-'))
        self.assertIsNone(source['published'])

    def test_unmatched_host_returns_none(self):
        registry = self.registry()
        doc = {'url': 'https://totally-unregistered.test/page', 'sha256': 'x', 'text': 't' * 2000, 'retrieved_at': 'now'}
        source, match = ee.match_document(doc, registry['sources'], registry)
        self.assertIsNone(source)
        self.assertIsNone(match)


class SelectDocumentsTests(unittest.TestCase):
    def test_short_documents_are_excluded(self):
        registry = {'sources': [{'id': 's0', 'url': 'https://a.example/a', 'layers': ['energy'], 'publisher': 'x'}], 'collection': {}}
        documents = [{'url': 'https://a.example/a', 'sha256': 'h1', 'text': 'short', 'retrieved_at': 'now'}]
        selected, stats = ee.select_documents(documents, registry, {}, seed=1, target=10, exclude_hosts=[], only_related=False)
        self.assertEqual(selected, [])
        self.assertEqual(stats['eligible_after_length_filter'], 0)

    def test_selection_is_deterministic_for_a_seed_and_seed_changes_order(self):
        registry = {'sources': [{'id': f's{i}', 'url': f'https://host{i}.example/a', 'layers': ['energy'], 'publisher': 'x'} for i in range(10)], 'collection': {}}
        documents = [{'url': f'https://host{i}.example/a', 'sha256': f'h{i}', 'text': 't' * 2000, 'retrieved_at': 'now'} for i in range(10)]
        a, _ = ee.select_documents(documents, registry, {}, seed=42, target=5, exclude_hosts=[], only_related=False)
        b, _ = ee.select_documents(documents, registry, {}, seed=42, target=5, exclude_hosts=[], only_related=False)
        self.assertEqual([d['sha256'] for d, _, _ in a], [d['sha256'] for d, _, _ in b])
        c, _ = ee.select_documents(documents, registry, {}, seed=7, target=5, exclude_hosts=[], only_related=False)
        self.assertNotEqual([d['sha256'] for d, _, _ in a], [d['sha256'] for d, _, _ in c])

    def test_per_host_cap_limits_to_three(self):
        registry = {'sources': [{'id': 's0', 'url': 'https://host.example/a', 'layers': ['energy'], 'publisher': 'x'}], 'collection': {'s0': {'rank': 1}}}
        documents = [{'url': f'https://host.example/page{i}', 'sha256': f'h{i}', 'text': 't' * 2000, 'retrieved_at': 'now'} for i in range(6)]
        selected, stats = ee.select_documents(documents, registry, {}, seed=1, target=10, exclude_hosts=[], only_related=False)
        self.assertEqual(len(selected), 3)
        self.assertEqual(stats['per_host_cap_skipped'], 3)

    def test_exclude_hosts_skips_matching_documents(self):
        registry = {'sources': [{'id': 's0', 'url': 'https://excluded.example/a', 'layers': ['energy'], 'publisher': 'x'},
                                 {'id': 's1', 'url': 'https://kept.example/a', 'layers': ['energy'], 'publisher': 'x'}], 'collection': {}}
        documents = [{'url': 'https://excluded.example/a', 'sha256': 'h1', 'text': 't' * 2000, 'retrieved_at': 'now'},
                     {'url': 'https://kept.example/a', 'sha256': 'h2', 'text': 't' * 2000, 'retrieved_at': 'now'}]
        selected, stats = ee.select_documents(documents, registry, {}, seed=1, target=10, exclude_hosts=['excluded.example'], only_related=False)
        self.assertEqual([d['sha256'] for d, _, _ in selected], ['h2'])
        self.assertEqual(stats['excluded_host_skipped'], 1)

    def test_only_related_skips_documents_with_no_metric_mapping(self):
        registry = {'sources': [{'id': 's0', 'url': 'https://a.example/a', 'layers': ['energy'], 'publisher': 'x'},
                                 {'id': 's1', 'url': 'https://b.example/a', 'layers': ['energy'], 'publisher': 'x'}], 'collection': {}}
        metrics_by_id = {'m1': {'id': 'm1', 'source_ids': ['s1']}}
        documents = [{'url': 'https://a.example/a', 'sha256': 'h1', 'text': 't' * 2000, 'retrieved_at': 'now'},
                     {'url': 'https://b.example/a', 'sha256': 'h2', 'text': 't' * 2000, 'retrieved_at': 'now'}]
        selected, stats = ee.select_documents(documents, registry, metrics_by_id, seed=1, target=10, exclude_hosts=[], only_related=True)
        self.assertEqual([d['sha256'] for d, _, _ in selected], ['h2'])
        self.assertEqual(stats['only_related_skipped'], 1)

    def test_holdout_prefers_documents_whose_source_has_an_expected_record(self):
        # s0 and s2 both map to metric m1, but only s0 has a surviving observation from itself;
        # s2's only m1 observation is superseded, so it counts the same as having none.
        registry = {'sources': [{'id': f's{i}', 'url': f'https://host{i}.example/a', 'layers': ['energy'], 'publisher': 'x'} for i in range(4)],
                    'collection': {}}
        metrics_by_id = {'m1': {'id': 'm1', 'source_ids': ['s0', 's2']}}
        documents = [{'url': f'https://host{i}.example/a', 'sha256': f'h{i}', 'text': 't' * 2000, 'retrieved_at': 'now'} for i in range(4)]
        observations = [{'id': 'o1', 'source': 's0', 'metric': 'm1', 'year': 2025, 'period': '2025', 'value': 1, 'upper': None},
                         {'id': 'o2', 'source': 's2', 'metric': 'm1', 'year': 2024, 'period': '2024', 'value': 2, 'upper': None,
                          'superseded_by': 'o3'}]
        selected, stats = ee.select_documents(documents, registry, metrics_by_id, seed=1, target=1, exclude_hosts=[],
                                               only_related=False, observations=observations, holdout=True)
        self.assertEqual([s['id'] for _, s, _ in selected], ['s0'])
        self.assertEqual(stats['holdout_qualifying_available'], 1)
        self.assertEqual(stats['holdout_no_expected_skipped'], 3)  # s1, s2, s3 all considered and left out

        # A larger target pulls s0 first, then fills the rest (2 of 3) from the no-expected-record pool.
        selected, stats = ee.select_documents(documents, registry, metrics_by_id, seed=1, target=3, exclude_hosts=[],
                                               only_related=False, observations=observations, holdout=True)
        self.assertEqual(len(selected), 3)
        self.assertEqual(selected[0][1]['id'], 's0')
        self.assertEqual(stats['holdout_no_expected_skipped'], 1)  # 1 of the 3 no-expected candidates wasn't needed


class HoldoutMatchingTests(unittest.TestCase):
    def expected(self, **over):
        base = {'id': 'e1', 'metric': 'ai-adoption', 'year': 2025, 'period': '2025', 'value': 88, 'upper': None}
        base.update(over)
        return base

    def test_value_within_half_percent_matches(self):
        e = self.expected()
        self.assertTrue(ee.value_close(88, e))
        self.assertTrue(ee.value_close(88.43, e))    # +0.49%, inside tolerance
        self.assertFalse(ee.value_close(88.45, e))   # +0.51%, outside tolerance

    def test_value_inside_expected_upper_bound_matches_as_a_range(self):
        e = self.expected(value=80, upper=100)
        self.assertTrue(ee.value_close(95, e))    # inside [80, 100], far outside 0.5% of 80
        self.assertFalse(ee.value_close(105, e))  # above the upper bound

    def test_year_or_period_match_either_is_sufficient(self):
        e = self.expected()
        self.assertTrue(ee.candidate_matches_expected({'metric': 'ai-adoption', 'year': 2025, 'period': 'FY2025', 'value': 88}, e))
        self.assertTrue(ee.candidate_matches_expected({'metric': 'ai-adoption', 'year': 1999, 'period': '2025', 'value': 88}, e))
        self.assertFalse(ee.candidate_matches_expected({'metric': 'ai-adoption', 'year': 1999, 'period': 'FY2025', 'value': 88}, e))

    def test_metric_mismatch_never_matches(self):
        e = self.expected()
        self.assertFalse(ee.candidate_matches_expected({'metric': 'other-metric', 'year': 2025, 'period': '2025', 'value': 88}, e))

    def test_match_to_expected_is_one_to_one_and_reports_false_proposals(self):
        expected = [self.expected(id='e1'), self.expected(id='e2', year=2026, period='2026')]
        candidates = [
            {'metric': 'ai-adoption', 'year': 2025, 'period': '2025', 'value': 88},  # matches e1
            {'metric': 'ai-adoption', 'year': 2025, 'period': '2025', 'value': 88},  # e1 already claimed: false proposal
            {'metric': 'ai-adoption', 'year': 2030, 'period': '2030', 'value': 50},  # matches nothing: false proposal
        ]
        matches, missed = ee.match_to_expected(candidates, expected)
        self.assertEqual(matches, {0: 'e1'})
        self.assertEqual(missed, ['e2'])


class ExtractObservationsRefactorTests(unittest.TestCase):
    """extract_observations must behave exactly like the inline block it replaced."""
    def setUp(self):
        self.data = json.loads((ROOT / 'site/data/ledger.json').read_text(encoding='utf-8'))
        self.metrics = {m['id']: m for m in self.data['metrics']}
        self.sources = {s['id']: s for s in self.data['sources']}
        self.source = self.sources['stanford-2026']
        registry = json.loads((ROOT / 'research/sources.json').read_text(encoding='utf-8'))
        self.policy = collection_for(registry, self.source)
        self.related = [self.metrics['ai-adoption']]
        self.document = 'In 2026, 90 percent of surveyed organizations reported AI use.'
        self.candidate = {'metric': 'ai-adoption', 'year': 2026, 'period': '2026', 'value': 90, 'upper': None,
                           'status': 'observation', 'precision': 'eq', 'note': '', 'evidence': self.document}
        self.config = {'_instructions': 'Guide', '_coverage': '{}', 'max_candidates_per_document': 4}

    def test_accepted_candidate_counts_two_model_calls_and_saves_proof(self):
        run = {'model_calls': 0, 'accepted': 0}
        quarantine = []
        collection = {}
        data = copy.deepcopy(self.data)
        verdict = {'index': 0, 'numbers_in_evidence': True, 'scope_matches': True, 'basis_correct': True,
                   'attribution_correct': True, 'defect': 'none', 'reason': 'Directly supported'}
        with tempfile.TemporaryDirectory() as tmp, patch.object(research, 'LOCAL', Path(tmp)), \
             patch.object(research, 'ollama', side_effect=[{'observations': [self.candidate]}, {'verdicts': [verdict]}]):
            accepted = research.extract_observations(self.config, self.source, self.document, self.related, data,
                                                       self.metrics, self.sources, run, quarantine, collection, policy=self.policy)
            proof = json.loads((Path(tmp) / 'evidence' / f'{accepted[0]["id"]}.json').read_text(encoding='utf-8'))
        self.assertEqual(len(accepted), 1)
        self.assertEqual(accepted[0]['metric'], 'ai-adoption')
        self.assertEqual(run['model_calls'], 2)
        self.assertEqual(run['accepted'], 1)
        self.assertEqual(quarantine, [])
        self.assertEqual(len(data['observations']), len(self.data['observations']) + 1)
        self.assertIn(self.source, data['sources'])
        self.assertEqual(proof['record']['metric'], 'ai-adoption')
        self.assertEqual(proof['review']['supported'], True)
        self.assertIn('document_windows', collection)

    def test_candidate_failing_validators_counts_one_model_call(self):
        run = {'model_calls': 0, 'accepted': 0}
        quarantine = []
        collection = {}
        data = copy.deepcopy(self.data)
        bad = dict(self.candidate, value=91)  # not present as a numeric token in the evidence
        with patch.object(research, 'ollama', return_value={'observations': [bad]}):
            accepted = research.extract_observations(self.config, self.source, self.document, self.related, data,
                                                       self.metrics, self.sources, run, quarantine, collection, policy=self.policy)
        self.assertEqual(accepted, [])
        self.assertEqual(run['model_calls'], 1)
        self.assertEqual(len(quarantine), 1)
        self.assertEqual(data['observations'], self.data['observations'])

    def test_model_failure_propagates_as_runtime_error(self):
        run = {'model_calls': 0, 'accepted': 0}
        data = copy.deepcopy(self.data)
        with patch.object(research, 'ollama', side_effect=TimeoutError('fixture timeout')):
            with self.assertRaisesRegex(RuntimeError, 'Model extraction failed'):
                research.extract_observations(self.config, self.source, self.document, self.related, data,
                                               self.metrics, self.sources, run, [], {}, policy=self.policy)

    def test_empty_reason_recorded_in_collection_histogram_and_entry(self):
        run = {'model_calls': 0, 'accepted': 0}
        data = copy.deepcopy(self.data)
        collection = {}
        with patch.object(research, 'ollama', return_value={'observations': [], 'empty_reason': 'no supported number for these metrics'}):
            accepted = research.extract_observations(self.config, self.source, self.document, self.related, data,
                                                       self.metrics, self.sources, run, [], collection, policy=self.policy)
        self.assertEqual(accepted, [])
        self.assertEqual(collection['empty_reasons'], {'no supported number for these metrics': 1})
        self.assertEqual(collection['document_windows'][-1]['empty_reason'], 'no supported number for these metrics')

    def test_invalid_empty_reason_is_rejected(self):
        run = {'model_calls': 0, 'accepted': 0}
        data = copy.deepcopy(self.data)
        with patch.object(research, 'ollama', return_value={'observations': [], 'empty_reason': 'x' * 201}):
            with self.assertRaisesRegex(RuntimeError, 'Model extraction failed'):
                research.extract_observations(self.config, self.source, self.document, self.related, data,
                                               self.metrics, self.sources, run, [], {}, policy=self.policy)

    def test_evidence_over_cap_but_shrinkable_is_accepted_and_marked(self):
        run = {'model_calls': 0, 'accepted': 0}
        quarantine = []
        data = copy.deepcopy(self.data)
        long_doc = 'In 2026, 90 percent of surveyed organizations reported AI use. ' * 40
        candidate = dict(self.candidate, evidence=long_doc)
        verdict = {'index': 0, 'numbers_in_evidence': True, 'scope_matches': True, 'basis_correct': True,
                   'attribution_correct': True, 'defect': 'none', 'reason': 'Directly supported'}
        with tempfile.TemporaryDirectory() as tmp, patch.object(research, 'LOCAL', Path(tmp)), \
             patch.object(research, 'ollama', side_effect=[{'observations': [candidate]}, {'verdicts': [verdict]}]):
            accepted = research.extract_observations(self.config, self.source, long_doc, self.related, data,
                                                       self.metrics, self.sources, run, quarantine, {}, policy=self.policy)
            proof = json.loads((Path(tmp) / 'evidence' / f'{accepted[0]["id"]}.json').read_text(encoding='utf-8'))
        self.assertEqual(len(accepted), 1)
        self.assertEqual(quarantine, [])
        self.assertLessEqual(len(proof['evidence']), research.METRIC_EVIDENCE_MAX)
        self.assertIn(proof['evidence'], long_doc)
        self.assertTrue(proof['evidence_shrunk'])
        self.assertIn('90', numeric_tokens(proof['evidence']))

    def test_evidence_over_cap_and_unshrinkable_is_quarantined(self):
        run = {'model_calls': 0, 'accepted': 0}
        quarantine = []
        data = copy.deepcopy(self.data)
        long_doc = 'x ' * 900 + '90' + ' y' * 900  # no sentence breaks anywhere: unshrinkable
        candidate = dict(self.candidate, evidence=long_doc)
        with patch.object(research, 'ollama', return_value={'observations': [candidate]}):
            accepted = research.extract_observations(self.config, self.source, long_doc, self.related, data,
                                                       self.metrics, self.sources, run, quarantine, {}, policy=self.policy)
        self.assertEqual(accepted, [])
        self.assertEqual(len(quarantine), 1)
        self.assertIn('too long even after shrinking', quarantine[0]['reason'])
        self.assertFalse(quarantine[0]['evidence_shrunk'])


class HarnessRunTests(unittest.TestCase):
    def setUp(self):
        self._fixture_dir = tempfile.TemporaryDirectory()
        self._corpus_dir = tempfile.TemporaryDirectory()
        self._out_dir = tempfile.TemporaryDirectory()
        self.path = Path(self._fixture_dir.name)
        copy_fixture_root(self.path)
        registry = json.loads((self.path / 'research/sources.json').read_text(encoding='utf-8'))
        ledger = json.loads((self.path / 'site/data/ledger.json').read_text(encoding='utf-8'))
        ledger['runs'] = []
        ledger['runtime'].update(last_attempt=None, last_success=None, status='awaiting-first-run')
        (self.path / 'site/data/ledger.json').write_text(json.dumps(ledger), encoding='utf-8')
        metric_source_ids = {sid for m in ledger['metrics'] for sid in m['source_ids']}
        self.related_source = next(s for s in registry['sources'] if s['id'] == 'stanford-2026')
        self.unrelated_source = next(s for s in registry['sources']
                                      if s['id'] not in metric_source_ids and not s.get('parent_source') and s['layers'])
        self.corpus = Path(self._corpus_dir.name)
        doc1 = 'Filler context sentence. ' * 120 + 'In 2026, 90 percent of surveyed organizations reported AI use.'
        doc2 = 'Filler context sentence. ' * 120 + 'ExampleCorp announced plans to expand its data center footprint with new AI infrastructure investment.'
        write_document(self.corpus / 'evidence', self.related_source['url'], doc1)
        write_document(self.corpus / 'evidence', self.unrelated_source['url'], doc2)
        self.out = Path(self._out_dir.name) / 'run1'

    def tearDown(self):
        self._fixture_dir.cleanup()
        self._corpus_dir.cleanup()
        self._out_dir.cleanup()

    def test_run_writes_only_under_out_and_produces_reports(self):
        before = {p: p.read_bytes() for p in self.corpus.rglob('*') if p.is_file()}
        args = ee.parse_args(['--documents', '2', '--seed', '1', '--out', str(self.out), '--exclude-hosts'])
        with patch.object(research, 'ROOT', self.path), patch.object(research, 'LOCAL', self.path / '.local'), \
             patch.object(ee, 'PRODUCTION_LOCAL', self.corpus), patch.object(research, 'ollama', side_effect=canned_ollama):
            code = ee.run(args)
        self.assertEqual(code, 0)
        self.assertFalse((self.path / '.local').exists(), 'nothing should be written under the fixture ROOT')
        after = {p: p.read_bytes() for p in self.corpus.rglob('*') if p.is_file()}
        self.assertEqual(before, after, 'the read-only corpus must be untouched')

        results = json.loads((self.out / 'results.json').read_text(encoding='utf-8'))
        self.assertEqual(len(results['documents']), 2)
        self.assertTrue((self.out / 'local' / 'evidence').is_dir())

        by_source = {e['matched_source_id']: e for e in results['documents']}
        metric_entry = by_source['stanford-2026']
        self.assertEqual(metric_entry['match_type'], 'exact')
        self.assertEqual(len(metric_entry['metric_candidates']), 1)
        self.assertEqual(metric_entry['metric_candidates'][0]['outcome'], 'accepted')
        # The note lane now runs for every document (mirrors main()), including
        # stanford-2026, which has a related metric but no excerpt permission -- its note
        # would stay private even if accepted. canned_ollama's evidence text is written for
        # doc2 (the unrelated source), so on doc1 it correctly fails to locate; that still
        # proves the note lane ran (a model call happened) where the old gate skipped it.
        self.assertFalse(metric_entry['publishable'])
        self.assertIsNotNone(metric_entry['note_candidate'])
        self.assertEqual(metric_entry['note_candidate']['outcome'], 'quarantined')
        self.assertEqual(metric_entry['note_candidate']['validator_reason'], 'Note evidence not found')
        note_entry = by_source[self.unrelated_source['id']]
        self.assertIsNotNone(note_entry['note_candidate'])
        self.assertEqual(note_entry['note_candidate']['outcome'], 'accepted')

        report = (self.out / 'report.md').read_text(encoding='utf-8')
        self.assertIn('## Summary', report)
        self.assertIn('## Documents', report)
        self.assertIn(metric_entry['metric_candidates'][0]['id'], report)
        self.assertIn(note_entry['note_candidate']['id'], report)

        grades = json.loads((self.out / 'grades.template.json').read_text(encoding='utf-8'))
        expected_ids = {r['id'] for e in results['documents'] for r in e['metric_candidates']}
        expected_ids |= {e['note_candidate']['id'] for e in results['documents'] if e.get('note_candidate')}
        self.assertEqual(set(grades), expected_ids)
        self.assertTrue(expected_ids)
        self.assertTrue(all(v is None for v in grades.values()))

        summary = results['summary']
        self.assertEqual(summary['documents'], 2)
        self.assertEqual(summary['metric_candidates_accepted'], 1)
        self.assertEqual(summary['notes_accepted'], 1)
        self.assertEqual(summary['notes_quarantined'], 1)
        self.assertEqual(summary['documents_with_zero_candidates'], 0)

    def test_fetch_is_forbidden_during_the_run_and_restored_after(self):
        original_fetch = research.Fetcher.fetch
        args = ee.parse_args(['--documents', '2', '--seed', '1', '--out', str(self.out), '--exclude-hosts'])
        seen = {}

        def spying_ollama(config, system, prompt, schema):
            seen['fetch_during_run'] = research.Fetcher.fetch
            return canned_ollama(config, system, prompt, schema)
        with patch.object(research, 'ROOT', self.path), patch.object(research, 'LOCAL', self.path / '.local'), \
             patch.object(ee, 'PRODUCTION_LOCAL', self.corpus), patch.object(research, 'ollama', side_effect=spying_ollama):
            ee.run(args)
        self.assertIs(seen.get('fetch_during_run'), ee._forbidden_fetch)
        self.assertIs(research.Fetcher.fetch, original_fetch)
        with self.assertRaises(AssertionError):
            ee._forbidden_fetch()


class HoldoutRunTests(unittest.TestCase):
    """End-to-end --holdout run against real fixture prompts/policy/ledger, with a fake research.ollama."""
    def setUp(self):
        self._fixture_dir = tempfile.TemporaryDirectory()
        self._corpus_dir = tempfile.TemporaryDirectory()
        self._out_dir = tempfile.TemporaryDirectory()
        self.path = Path(self._fixture_dir.name)
        copy_fixture_root(self.path)
        registry = json.loads((self.path / 'research/sources.json').read_text(encoding='utf-8'))
        ledger = json.loads((self.path / 'site/data/ledger.json').read_text(encoding='utf-8'))
        ledger['runs'] = []
        ledger['runtime'].update(last_attempt=None, last_success=None, status='awaiting-first-run')
        (self.path / 'site/data/ledger.json').write_text(json.dumps(ledger), encoding='utf-8')
        # stanford-2026 curates two non-superseded observations of its own: infra-2026
        # (us-data-centers) and apps-2025 (ai-adoption, value 88). Holdout removes both;
        # the fake model re-proposes apps-2025 (with evidence engineered to fail a
        # validator, so it is a genuine validator false-reject) plus one new, unrelated
        # ai-adoption fact that cannot match either removed record.
        self.related_source = next(s for s in registry['sources'] if s['id'] == 'stanford-2026')
        self.corpus = Path(self._corpus_dir.name)
        # No literal "2025" anywhere in the document: candidate_record's year check can only be
        # satisfied by a source-publication-year fallback (stanford-2026 has none), so this
        # candidate is a genuine validator false-reject rather than a validator-correct rejection.
        self.matched_evidence = ('A recent multi-year survey found that eighty-eight, or 88, '
                                  'percent of surveyed organizations reported AI use.')
        self.new_evidence = ('Looking further ahead, the survey projects that 95 percent of '
                              'organizations will report AI use by 2027.')
        doc = 'Filler context sentence. ' * 120 + self.matched_evidence + ' ' + self.new_evidence
        write_document(self.corpus / 'evidence', self.related_source['url'], doc)
        self.out = Path(self._out_dir.name) / 'run1'
        self.ledger_before = (self.path / 'site/data/ledger.json').read_bytes()

    def tearDown(self):
        self._fixture_dir.cleanup()
        self._corpus_dir.cleanup()
        self._out_dir.cleanup()

    def fake_ollama(self, config, system, prompt, schema):
        keys = set(schema.get('properties', {}))
        if 'observations' in keys:
            return {'observations': [
                {'metric': 'ai-adoption', 'year': 2025, 'period': '2025', 'value': 88, 'upper': None,
                 'status': 'observation', 'precision': 'eq', 'note': '', 'evidence': self.matched_evidence},
                {'metric': 'ai-adoption', 'year': 2027, 'period': '2027', 'value': 95, 'upper': None,
                 'status': 'observation', 'precision': 'eq', 'note': '', 'evidence': self.new_evidence},
            ]}
        return canned_ollama(config, system, prompt, schema)

    def test_holdout_removes_expected_records_and_scores_recall(self):
        args = ee.parse_args(['--holdout', '--documents', '1', '--seed', '1', '--out', str(self.out), '--exclude-hosts'])
        with patch.object(research, 'ROOT', self.path), patch.object(research, 'LOCAL', self.path / '.local'), \
             patch.object(ee, 'PRODUCTION_LOCAL', self.corpus), patch.object(research, 'ollama', side_effect=self.fake_ollama):
            code = ee.run(args)
        self.assertEqual(code, 0)
        # The worktree's own site/data/ledger.json (what research.ROOT points at) must never be written.
        self.assertEqual((self.path / 'site/data/ledger.json').read_bytes(), self.ledger_before,
                          'the production ledger file must never be modified by a holdout run')

        results = json.loads((self.out / 'results.json').read_text(encoding='utf-8'))
        self.assertTrue(results['holdout'])
        self.assertEqual(len(results['documents']), 1)
        holdout = results['documents'][0]['holdout']

        # Two of stanford-2026's own non-superseded observations are removed: us-data-centers
        # (infra-2026) and ai-adoption (apps-2025). Only apps-2025 gets re-proposed.
        self.assertEqual(holdout['expected'], [{'id': 'infra-2026', 'metric': 'us-data-centers', 'value': 5427, 'period': '2026 report'},
                                                {'id': 'apps-2025', 'metric': 'ai-adoption', 'value': 88, 'period': '2025'}])
        self.assertEqual(holdout['matched'], 1)
        self.assertEqual(holdout['missed'], [{'id': 'infra-2026', 'metric': 'us-data-centers', 'value': 5427, 'period': '2026 report'}])
        self.assertEqual(len(holdout['false_proposals']), 1)
        self.assertEqual(holdout['false_proposals'][0]['year'], 2027)
        self.assertEqual(len(holdout['validator_false_rejects']), 1)
        self.assertEqual(holdout['validator_false_rejects'][0]['year'], 2025)
        self.assertEqual(holdout['validator_false_rejects'][0]['validator_reason'], 'Year not found in source')
        self.assertEqual(holdout['reviewer_false_rejects'], [])

        summary = results['summary']['holdout']
        self.assertEqual(summary['expected_total'], 2)
        self.assertEqual(summary['proposed_total'], 2)
        self.assertEqual(summary['matched_total'], 1)
        self.assertEqual(summary['recall'], 0.5)
        self.assertEqual(summary['precision'], 0.5)
        self.assertEqual(summary['validator_false_rejects'], 1)
        self.assertEqual(summary['reviewer_false_rejects'], 0)

        report = (self.out / 'report.md').read_text(encoding='utf-8')
        self.assertIn('## Holdout (leave-one-out recall)', report)
        self.assertIn('| d0 | stanford-2026 | 2 | 1 |', report)

    def test_non_holdout_run_has_no_holdout_section(self):
        args = ee.parse_args(['--documents', '1', '--seed', '1', '--out', str(self.out), '--exclude-hosts'])
        with patch.object(research, 'ROOT', self.path), patch.object(research, 'LOCAL', self.path / '.local'), \
             patch.object(ee, 'PRODUCTION_LOCAL', self.corpus), patch.object(research, 'ollama', side_effect=self.fake_ollama):
            code = ee.run(args)
        self.assertEqual(code, 0)
        results = json.loads((self.out / 'results.json').read_text(encoding='utf-8'))
        self.assertFalse(results['holdout'])
        self.assertNotIn('holdout', results['documents'][0])
        self.assertNotIn('holdout', results['summary'])
        report = (self.out / 'report.md').read_text(encoding='utf-8')
        self.assertNotIn('## Holdout', report)


class LockRefusalTests(unittest.TestCase):
    def test_refuses_when_a_lock_file_is_present(self):
        with tempfile.TemporaryDirectory() as local_tmp, tempfile.TemporaryDirectory() as corpus_tmp, \
             tempfile.TemporaryDirectory() as out_tmp:
            local = Path(local_tmp)
            local.mkdir(exist_ok=True)
            (local / 'research.lock').write_text('{}', encoding='utf-8')
            out = Path(out_tmp) / 'run'
            with patch.object(research, 'LOCAL', local), patch.object(ee, 'PRODUCTION_LOCAL', Path(corpus_tmp)):
                code = ee.run(ee.parse_args(['--out', str(out)]))
            self.assertEqual(code, 2)
            self.assertFalse(out.exists())


class ScoringTests(unittest.TestCase):
    def test_scoring_math(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            results = {'documents': [{
                'index': 0,
                'metric_candidates': [
                    {'id': 'd0-m0', 'kind': 'observation', 'outcome': 'accepted', 'metric': 'a', 'value': 1, 'period': '2026', 'status': 'observation'},
                    {'id': 'd0-m1', 'kind': 'observation', 'outcome': 'accepted', 'metric': 'a', 'value': 2, 'period': '2026', 'status': 'observation'},
                    {'id': 'd0-m2', 'kind': 'observation', 'outcome': 'quarantined', 'validator_result': 'failed', 'metric': 'a', 'value': 3, 'period': '2026', 'status': 'observation'},
                    {'id': 'd0-m3', 'kind': 'observation', 'outcome': 'quarantined', 'validator_result': 'passed', 'metric': 'a', 'value': 4, 'period': '2026', 'status': 'observation'},
                ],
                'note_candidate': {'id': 'd0-n0', 'kind': 'note', 'outcome': 'accepted', 'title': 'T', 'summary': 'S'},
            }]}
            (out / 'results.json').write_text(json.dumps(results), encoding='utf-8')
            grades = {'d0-m0': 'correct', 'd0-m1': 'incorrect', 'd0-m2': 'correct', 'd0-m3': 'incorrect', 'd0-n0': 'correct'}
            (out / 'grades.json').write_text(json.dumps(grades), encoding='utf-8')
            code = ee.score(ee.parse_args(['--grade', str(out / 'grades.json')]))
            self.assertEqual(code, 0)
            scored = (out / 'scored.md').read_text(encoding='utf-8')
        self.assertIn('50.0% (1/2)', scored)      # precision of accepted observations
        self.assertIn('100.0% (1/1)', scored)     # validator false-reject rate and note precision both hit 100%
        self.assertIn('0.0% (0/1)', scored)       # reviewer false-reject rate
        self.assertIn('d0-m1', scored)            # listed as an incorrect accepted item
        self.assertNotIn('d0-n0: note', scored)    # the note was graded correct, so it is not listed


if __name__ == '__main__':
    unittest.main()
