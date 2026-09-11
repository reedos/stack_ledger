import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT/'tests/_importer_common_runner.py'

FIXTURE_SOURCE = {'id': 'test-importer-common-source', 'publisher': 'Test Publisher', 'title': 'Test dataset',
                  'url': 'https://example.gov/data', 'published': None, 'layers': ['infrastructure'], 'license': 'Public domain (U.S. government work)', 'provenance': 'official'}
FIXTURE_COLLECTION = {'test-importer-common-source': {'rank': 1, 'region_book': 'united-states', 'company_id': None, 'claim_type': 'other', 'cadence': 'manual', 'weekday': 0, 'path_prefixes': [], 'topics': [], 'excerpts': False}}


class ImporterCommonEndToEndTests(unittest.TestCase):
    """Runs apply_changes as a subprocess against a temp copy of the repo, so nothing here
    can touch the real research/site files, and so validate.py's module-level ROOT resolves
    to the temp copy rather than whatever repo happens to already be on this process's path."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        for folder in ['scripts', 'research', 'site']:
            shutil.copytree(ROOT/folder, self.root/folder, ignore=shutil.ignore_patterns('__pycache__'))

    def tearDown(self):
        self.temp.cleanup()

    def read(self, name):
        return json.loads((self.root/name).read_text(encoding='utf-8'))

    def apply(self, **kwargs):
        result = subprocess.run([sys.executable, str(RUNNER), str(self.root)], input=json.dumps(kwargs),
                                 capture_output=True, text=True, encoding='utf-8', timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        payload = json.loads(result.stdout.strip().splitlines()[-1])
        if not payload['ok']:
            raise AssertionError(payload['error'])
        return payload['receipt']

    def apply_expecting_failure(self, **kwargs):
        result = subprocess.run([sys.executable, str(RUNNER), str(self.root)], input=json.dumps(kwargs),
                                 capture_output=True, text=True, encoding='utf-8', timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        payload = json.loads(result.stdout.strip().splitlines()[-1])
        self.assertFalse(payload['ok'], 'Expected apply_changes to raise')
        return payload['error']

    def fixture_metric(self):
        return {'id': 'test-importer-common-metric', 'layer': 'infrastructure', 'title': 'Test metric',
                'unit': 'jobs (third month of quarter)', 'geography': 'United States',
                'scope': 'A metric created only inside a temp copy of the repo for importer_common tests.',
                'direction': 'context', 'min': 0, 'max': 10_000_000, 'note': 'Test fixture; never published.',
                'source_ids': [FIXTURE_SOURCE['id']], 'company': None, 'measurement_type': 'county_industry_employment',
                'project': None, 'allowed_statuses': ['observation'], 'period_basis': 'quarter',
                'geography_code': None, 'series_start_year': 2024, 'chart_default_start': 2024, 'chart_default_end': 2027,
                'definition_stable': True, 'pre_period_note': 'Test fixture series.'}

    def fixture_observation(self, value=100):
        return {'id': 'test-importer-common-metric-2026q1', 'metric': 'test-importer-common-metric', 'year': 2026,
                'period': '2026-Q1', 'value': value, 'upper': None, 'status': 'observation',
                'source': FIXTURE_SOURCE['id'], 'precision': 'eq', 'retrieved_at': '2026-09-09T12:00:00Z',
                'method': 'curated', 'note': 'Test fixture observation.'}

    def fixture_event(self, title='Test fixture event'):
        # FIXTURE_SOURCE is registered at collection rank 1, so grade_for derives grade A.
        return {'id': 'test-importer-common-event', 'layer': 'infrastructure', 'date': '2026-09-09',
                'title': title, 'summary': 'A test fixture event created only inside a temp copy of the repo.',
                'source': FIXTURE_SOURCE['id'], 'kind': 'Government action', 'grade': 'A'}

    def test_apply_registers_adds_and_appends_and_records_an_event(self):
        ledger_before = self.read('site/data/ledger.json')
        self.assertNotIn(FIXTURE_SOURCE['id'], {s['id'] for s in ledger_before['sources']})
        receipt = self.apply(importer_id='test-importer', new_sources=[FIXTURE_SOURCE],
                              collection_entries=FIXTURE_COLLECTION, region_book='united-states',
                              new_metrics=[self.fixture_metric()], new_observations=[self.fixture_observation()],
                              snapshot={'retrieved_at': '2026-09-09T12:00:00Z', 'sha256': 'a'*64})
        self.assertEqual(receipt['importer_id'], 'test-importer')
        self.assertEqual(receipt['sources_touched'], [FIXTURE_SOURCE['id']])
        self.assertEqual(receipt['metrics_added'], ['test-importer-common-metric'])
        self.assertEqual(receipt['records_added'], ['test-importer-common-metric-2026q1'])
        self.assertEqual(receipt['snapshot_sha256s'], ['a'*64])
        self.assertEqual(receipt['channel'], 'importer')

        registry = self.read('research/sources.json')
        self.assertIn(FIXTURE_SOURCE['id'], {s['id'] for s in registry['sources']})
        self.assertIn(FIXTURE_SOURCE['id'], registry['region_books']['united-states']['sources'])
        catalog = self.read('research/catalog.json')
        self.assertIn('test-importer-common-metric', {m['id'] for m in catalog['metrics']})
        ledger = self.read('site/data/ledger.json')
        self.assertEqual(ledger['metrics'], catalog['metrics'])
        self.assertIn('test-importer-common-metric-2026q1', {o['id'] for o in ledger['observations']})
        source_books = self.read('site/data/source-books.json')
        self.assertEqual(source_books, {k: registry[k] for k in ['region_books', 'collection']})

        events_path = self.root/'.local/review-candidates/editorial-events.jsonl'
        events = [json.loads(line) for line in events_path.read_text(encoding='utf-8').splitlines()]
        importer_events = [e for e in events if e.get('kind') == 'importer_apply']
        self.assertEqual(len(importer_events), 1)
        self.assertEqual(importer_events[0]['importer_id'], 'test-importer')
        self.assertEqual(importer_events[0]['records_added'], ['test-importer-common-metric-2026q1'])

    def test_idempotent_second_run_adds_nothing(self):
        args = dict(importer_id='test-importer', new_sources=[FIXTURE_SOURCE], collection_entries=FIXTURE_COLLECTION,
                    region_book='united-states', new_metrics=[self.fixture_metric()],
                    new_observations=[self.fixture_observation()], snapshot={'retrieved_at': '2026-09-09T12:00:00Z'})
        self.apply(**args)
        catalog_after_first = self.read('research/catalog.json')
        ledger_after_first = self.read('site/data/ledger.json')
        registry_after_first = self.read('research/sources.json')

        receipt2 = self.apply(**args)
        self.assertEqual(receipt2['sources_touched'], [])
        self.assertEqual(receipt2['metrics_added'], [])
        self.assertEqual(receipt2['metrics_replaced'], [])
        self.assertEqual(receipt2['records_added'], [])
        self.assertEqual(self.read('research/catalog.json'), catalog_after_first)
        self.assertEqual(self.read('site/data/ledger.json'), ledger_after_first)
        self.assertEqual(self.read('research/sources.json'), registry_after_first)

        events_path = self.root/'.local/review-candidates/editorial-events.jsonl'
        events = [json.loads(line) for line in events_path.read_text(encoding='utf-8').splitlines()]
        self.assertEqual(sum(1 for e in events if e.get('kind') == 'importer_apply'), 2)

    def test_replace_metric_ids_upserts_a_revised_observation(self):
        self.apply(importer_id='test-importer', new_sources=[FIXTURE_SOURCE], collection_entries=FIXTURE_COLLECTION,
                   region_book='united-states', new_metrics=[self.fixture_metric()],
                   new_observations=[self.fixture_observation(100)])
        revised_metric = dict(self.fixture_metric(), note='Test fixture; revised definition.')
        self.apply(importer_id='test-importer', new_metrics=[revised_metric],
                   replace_metric_ids=['test-importer-common-metric'],
                   new_observations=[self.fixture_observation(150)])
        catalog = self.read('research/catalog.json')
        metric = next(m for m in catalog['metrics'] if m['id'] == 'test-importer-common-metric')
        self.assertEqual(metric['note'], 'Test fixture; revised definition.')
        ledger = self.read('site/data/ledger.json')
        obs = next(o for o in ledger['observations'] if o['id'] == 'test-importer-common-metric-2026q1')
        self.assertEqual(obs['value'], 150)
        self.assertEqual(sum(1 for o in ledger['observations'] if o['id'] == 'test-importer-common-metric-2026q1'), 1)

    def test_new_events_upsert_by_id_and_are_recorded_in_the_receipt(self):
        receipt = self.apply(importer_id='test-importer', new_sources=[FIXTURE_SOURCE],
                              collection_entries=FIXTURE_COLLECTION, region_book='united-states',
                              new_events=[self.fixture_event()])
        self.assertEqual(receipt['events_added'], ['test-importer-common-event'])
        ledger = self.read('site/data/ledger.json')
        events = {e['id']: e for e in ledger['events']}
        self.assertEqual(events['test-importer-common-event']['grade'], 'A')
        self.assertEqual(events['test-importer-common-event']['kind'], 'Government action')

        # A second call with a revised title upserts the same id rather than duplicating it.
        receipt2 = self.apply(importer_id='test-importer', new_events=[self.fixture_event('Revised title')])
        self.assertEqual(receipt2['events_added'], [])
        ledger2 = self.read('site/data/ledger.json')
        matching = [e for e in ledger2['events'] if e['id'] == 'test-importer-common-event']
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0]['title'], 'Revised title')

    def test_new_event_with_wrong_grade_for_its_source_rolls_back(self):
        bad_event = dict(self.fixture_event(), grade='C')   # FIXTURE_SOURCE is rank 1: only grade A is valid
        error = self.apply_expecting_failure(importer_id='test-importer', new_sources=[FIXTURE_SOURCE],
                                              collection_entries=FIXTURE_COLLECTION, region_book='united-states',
                                              new_events=[bad_event])
        self.assertIn('Event grade', error)
        ledger = self.read('site/data/ledger.json')
        self.assertNotIn('test-importer-common-event', {e['id'] for e in ledger['events']})

    def test_rollback_on_validation_failure_restores_every_file_byte_for_byte(self):
        catalog_before = (self.root/'research/catalog.json').read_bytes()
        sources_before = (self.root/'research/sources.json').read_bytes()
        source_books_before = (self.root/'site/data/source-books.json').read_bytes()
        ledger_before = (self.root/'site/data/ledger.json').read_bytes()

        bad_metric = dict(self.fixture_metric(), chart_companion_metric='does-not-exist-anywhere')
        self.apply_expecting_failure(importer_id='test-importer', new_sources=[FIXTURE_SOURCE],
                                      collection_entries=FIXTURE_COLLECTION, region_book='united-states',
                                      new_metrics=[bad_metric], new_observations=[self.fixture_observation()])

        self.assertEqual((self.root/'research/catalog.json').read_bytes(), catalog_before)
        self.assertEqual((self.root/'research/sources.json').read_bytes(), sources_before)
        self.assertEqual((self.root/'site/data/source-books.json').read_bytes(), source_books_before)
        self.assertEqual((self.root/'site/data/ledger.json').read_bytes(), ledger_before)
        # No event should be recorded for a call that never completed.
        events_path = self.root/'.local/review-candidates/editorial-events.jsonl'
        events = [json.loads(line) for line in events_path.read_text(encoding='utf-8').splitlines()] if events_path.exists() else []
        self.assertFalse(any(e.get('kind') == 'importer_apply' for e in events))


if __name__ == '__main__':
    unittest.main()
