import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT/'tests/_importer_common_runner.py'
sys.path.insert(0, str(ROOT/'scripts'))
import importer_common as ic
from validate import importer_expect, validate_importers

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


class FloorTests(unittest.TestCase):
    """Until 2026-09-11 no importer asserted a minimum expected result, so a dead route and a quiet
    week were the same run: EIA's capacity route returned 5,000 rows, produced zero records, and
    reported ok every week."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); (self.root/'research').mkdir()
        self.write_config({'rows:one': 10, 'records:one': 1})

    def write_config(self, minimums):
        (self.root/'research/importers.json').write_text(json.dumps(
            {'version': 1, 'reviewed_at': '2026-09-11T00:00:00Z',
             'importers': [{'id': 'x', 'command': ['scripts/import_x.py'], 'cadence': 'weekly', 'weekday': 2,
                            'timeout_seconds': 300, 'expect': {'minimums': minimums, 'note': 'Test fixture floor.'}}]}), encoding='utf-8')

    def test_a_route_that_returns_rows_and_no_record_fails(self):
        failures = ic.floor_failures(self.root, 'x', {'rows:one': 5000, 'records:one': 0})
        self.assertEqual(len(failures), 1)
        self.assertIn("'records:one' returned 0", failures[0])
        self.assertIn('not a quiet week', failures[0])

    def test_a_healthy_run_that_adds_no_new_record_still_passes(self):
        # Re-importing unchanged data legitimately adds nothing; the floor is what came back.
        self.assertEqual(ic.floor_failures(self.root, 'x', {'rows:one': 12, 'records:one': 40}), [])

    def test_a_renamed_route_fails_rather_than_going_unchecked(self):
        failures = ic.floor_failures(self.root, 'x', {'rows:one': 12})
        self.assertEqual(len(failures), 1)
        self.assertIn('records:one', failures[0])

    def test_keys_limits_the_check_to_the_part_of_the_run_that_happened(self):
        self.assertEqual(ic.floor_failures(self.root, 'x', {'rows:one': 12}, keys={'rows:one'}), [])

    def test_an_importer_with_no_reviewed_floor_is_an_error(self):
        value = json.loads((self.root/'research/importers.json').read_text(encoding='utf-8'))
        del value['importers'][0]['expect']
        (self.root/'research/importers.json').write_text(json.dumps(value), encoding='utf-8')
        with self.assertRaises(ValueError):
            ic.floor_failures(self.root, 'x', {'rows:one': 12, 'records:one': 4})

    def test_every_scheduled_importer_has_a_reviewed_floor(self):
        for imp in validate_importers(ROOT)['importers']:
            self.assertTrue(ic.reviewed_expectations(ROOT, imp['id'])['minimums'], imp['id'])


class DriftTests(unittest.TestCase):
    """Six of seven importers skip an id the ledger already holds, so a figure restated by the
    agency stayed frozen at whatever the first import saw, with nothing reported."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def held(self):
        return [{'id': 'm-2025', 'metric': 'm', 'period': '2025', 'value': 10.0, 'upper': None, 'status': 'observation'}]

    def test_a_restated_figure_is_reported_and_queued_without_rewriting_the_ledger(self):
        held = self.held()
        fresh = [{'id': 'm-2025', 'metric': 'm', 'period': '2025', 'value': 11.5, 'upper': None, 'status': 'observation'},
                 {'id': 'm-2026', 'metric': 'm', 'period': '2026', 'value': 12.0, 'upper': None, 'status': 'observation'}]
        rows = ic.report_drift(self.root, 'qcew', fresh, held)
        self.assertEqual([r['id'] for r in rows], ['m-2025'])
        self.assertEqual(rows[0]['changed']['value'], {'ledger': 10.0, 'source': 11.5})
        self.assertEqual(held[0]['value'], 10.0)   # reported, never rewritten by an import
        queued = sorted((self.root/'.local/review-candidates').glob('importer-drift-qcew-*.json'))
        self.assertEqual(len(queued), 1)
        payload = json.loads(queued[0].read_text(encoding='utf-8'))
        self.assertEqual(payload['kind'], 'importer_drift')
        self.assertTrue(payload['review_required'])
        self.assertEqual([r['id'] for r in payload['records']], ['m-2025'])

    def test_an_unchanged_reimport_reports_nothing(self):
        held = self.held()
        self.assertEqual(ic.report_drift(self.root, 'qcew', [dict(held[0])], held), [])
        self.assertFalse((self.root/'.local/review-candidates').exists())

    def test_a_status_restatement_is_drift_too(self):
        held = self.held()
        fresh = [dict(held[0], status='estimate')]
        rows = ic.report_drift(self.root, 'qcew', fresh, held)
        self.assertEqual(rows[0]['changed']['status'], {'ledger': 'observation', 'source': 'estimate'})


class SnapshotRedactionTests(unittest.TestCase):
    """EIA echoes the request back with api_key in it, so every response retained under .local/eia
    and .local/grid held the owner's key in plaintext (checked 2026-09-11)."""

    def test_the_key_is_stripped_before_a_response_is_retained(self):
        body = json.dumps({'request': {'command': '/v2/x', 'params': {'frequency': 'monthly', 'api_key': 'SECRETKEY123'}},
                            'response': {'total': 1, 'data': [{'period': '2026-01'}]}}).encode('utf-8')
        out = ic.redacted_body(body)
        self.assertNotIn(b'SECRETKEY123', out)
        self.assertEqual(json.loads(out)['response'], json.loads(body)['response'])
        self.assertEqual(json.loads(out)['request']['params']['api_key'], 'redacted')

    def test_a_response_with_no_echoed_key_is_left_alone(self):
        body = b'[{"period": "2026-01"}]'
        self.assertIs(ic.redacted_body(body), body)

    def test_both_eia_importers_redact_before_retaining(self):
        for name in ('import_eia', 'import_grid_demand'):
            source = (ROOT/'scripts'/f'{name}.py').read_text(encoding='utf-8')
            self.assertIn('redacted_body(', source, f"{name} writes the owner's API key into .local/")


class ImporterWiringTests(unittest.TestCase):
    LANDS_OBSERVATIONS = ('import_eia', 'import_btos', 'import_qcew', 'import_qwi', 'import_sec', 'import_grid_demand')

    def test_every_scheduled_importer_checks_its_floor_and_can_exit_non_zero(self):
        for imp in validate_importers(ROOT)['importers']:
            source = (ROOT/imp['command'][0]).read_text(encoding='utf-8')
            self.assertIn('check_floors(', source, f"{imp['id']} reports ok whatever its routes return")
            self.assertIn('return 1 if', source, f"{imp['id']} exits 0 even when a reviewed floor is breached")

    def test_every_importer_that_lands_observations_reports_drift(self):
        for name in self.LANDS_OBSERVATIONS:
            source = (ROOT/'scripts'/f'{name}.py').read_text(encoding='utf-8')
            self.assertIn('report_drift(', source, f'{name} never compares what the source says now with what the ledger holds')


class ImporterExpectValidationTests(unittest.TestCase):
    def test_reviewed_floor_shape_is_checked(self):
        importer_expect({'minimums': {'rows:one': 10}, 'note': 'Grounded in the retained snapshot.'})
        for bad in ({'minimums': {}, 'note': 'why'},
                     {'minimums': {'rows:one': -1}, 'note': 'why'},
                     {'minimums': {'rows:one': 1.5}, 'note': 'why'},
                     {'minimums': {'rows:one': 1}},
                     {'minimums': {'rows:one': 1}, 'note': 'why', 'extra': True}):
            with self.assertRaises(ValueError):
                importer_expect(bad)

    def test_validate_importers_rejects_a_scheduled_importer_whose_floor_is_malformed(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        (root/'scripts').mkdir(); (root/'scripts/import_x.py').write_text('', encoding='utf-8'); (root/'research').mkdir()
        config = {'version': 1, 'reviewed_at': '2026-09-11T00:00:00Z',
                  'importers': [{'id': 'x', 'command': ['scripts/import_x.py'], 'cadence': 'weekly', 'weekday': 2,
                                 'timeout_seconds': 300, 'expect': {'minimums': {'rows:one': 10}, 'note': 'Reviewed floor.'}}]}
        (root/'research/importers.json').write_text(json.dumps(config), encoding='utf-8')
        self.assertEqual(validate_importers(root)['importers'][0]['expect']['minimums'], {'rows:one': 10})
        config['importers'][0]['expect'] = {'minimums': {'rows:one': 'lots'}, 'note': 'Reviewed floor.'}
        (root/'research/importers.json').write_text(json.dumps(config), encoding='utf-8')
        with self.assertRaises(ValueError):
            validate_importers(root)

    def test_the_real_file_carries_a_reviewed_floor_and_a_note_for_every_importer(self):
        for imp in validate_importers(ROOT)['importers']:
            self.assertTrue(imp['expect']['minimums'] and imp['expect']['note'], imp['id'])


if __name__ == '__main__':
    unittest.main()
