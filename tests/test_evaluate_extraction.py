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
    if keys == {'observations'}:
        return {'observations': [{'metric': 'ai-adoption', 'year': 2026, 'period': '2026', 'value': 90,
                                   'upper': None, 'status': 'observation', 'precision': 'eq', 'note': '',
                                   'evidence': 'In 2026, 90 percent of surveyed organizations reported AI use.'}]}
    if keys == {'notes'}:
        return {'notes': [{'title': 'ExampleCorp expands data center capacity',
                            'summary': 'ExampleCorp announced plans to expand its data center footprint with new AI infrastructure investment.',
                            'layer': payload['allowed_layers'][0], 'kind': 'Company announcement',
                            'evidence': 'ExampleCorp announced plans to expand its data center footprint with new AI infrastructure investment.'}]}
    if keys == {'verdicts'}:
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


class ExtractObservationsRefactorTests(unittest.TestCase):
    """extract_observations must behave exactly like the inline block it replaced."""
    def setUp(self):
        self.data = json.loads((ROOT / 'site/data/ledger.json').read_text(encoding='utf-8'))
        self.metrics = {m['id']: m for m in self.data['metrics']}
        self.sources = {s['id']: s for s in self.data['sources']}
        self.source = self.sources['stanford-2026']
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
                                                       self.metrics, self.sources, run, quarantine, collection)
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
                                                       self.metrics, self.sources, run, quarantine, collection)
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
                                               self.metrics, self.sources, run, [], {})


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
