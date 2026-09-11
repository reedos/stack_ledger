import json
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import import_btos as ib
import validate_expansion as ve
from validate import observation_valid

NATIONAL_FIXTURE = json.dumps([
    {'xmltag': 'Current AI Use (Last Two Weeks)', 'Estimate': 17.3, 'Date': '2025-11-30'},
    {'xmltag': 'Current AI Use (Last Two Weeks)', 'Estimate': 22.4, 'Date': '2026-08-23'},
    {'xmltag': 'Expected AI Use (Next Six Months)', 'Estimate': 25.9, 'Date': '2026-08-23'},   # a different series: not the AI-use-share metric
    {'xmltag': 'Current AI Use (Last Two Weeks)', 'Estimate': None, 'Date': '2026-09-06'},     # non-numeric estimate: dropped, never zero
]).encode('utf-8')

SECTOR_FIXTURE = json.dumps([
    {'xmltag': 'Current AI Use (Last Two Weeks)', 'NAICS': 'Information', 'Estimate': 46.0, 'Date': '2026-08-23'},
    {'xmltag': 'Current AI Use (Last Two Weeks)', 'NAICS': 'Professional, Scientific, and Technical Services', 'Estimate': 41.9, 'Date': '2026-08-23'},
    {'xmltag': 'Current AI Use (Last Two Weeks)', 'NAICS': 'Manufacturing', 'Estimate': 16.1, 'Date': '2026-08-23'},   # not one of the two sectors we track
]).encode('utf-8')


class BtosImportTests(unittest.TestCase):
    def test_records_for_keeps_only_the_current_use_series_and_drops_non_numeric(self):
        rows = ib.parse(NATIONAL_FIXTURE)
        observations = ib.records_for(rows, 'btos-ai-use-share', '2026-09-09T12:00:00Z', 'a'*64)
        self.assertEqual([(o['period'], o['value']) for o in observations], [('2025-11-30', 17.3), ('2026-08-23', 22.4)])
        self.assertTrue(all(o['id'] == f"btos-ai-use-share-{o['period']}" for o in observations))
        self.assertTrue(all(o['status'] == 'estimate' and o['metric'] == 'btos-ai-use-share' for o in observations))

    def test_sector_rows_filter_to_the_named_naics_sector(self):
        rows = ib.parse(SECTOR_FIXTURE)
        info_rows = [r for r in rows if r.get('NAICS') == 'Information']
        observations = ib.records_for(info_rows, 'btos-ai-use-share-naics-51', '2026-09-09T12:00:00Z', 'b'*64)
        self.assertEqual([(o['period'], o['value']) for o in observations], [('2026-08-23', 46.0)])

    def test_metric_definition_and_observations_are_internally_valid(self):
        national = ib.metric_definition('btos-ai-use-share', 'Share of U.S. businesses currently using AI (Census BTOS)', 'United States')
        sector = ib.metric_definition('btos-ai-use-share-naics-51', 'title', 'United States, information (NAICS 51)', naics='51')
        for m in (national, sector):
            self.assertEqual(m['layer'], 'applications')
            self.assertIsNone(m['company'])
            self.assertEqual(m['unit'], '% of businesses')
            self.assertEqual(m['allowed_statuses'], ['estimate'])
            self.assertTrue(m['measurement_type'] in ve.TYPES and m['measurement_type'] in ve.PUBLIC_TYPES)
        sources = {ib.SOURCE_ID: ib.SOURCE}
        metrics = {national['id']: national, sector['id']: sector}
        for o in ib.records_for(ib.parse(NATIONAL_FIXTURE), national['id'], '2026-09-09T12:00:00Z', 'c'*64):
            observation_valid(o, metrics, sources)
        for o in ib.records_for([r for r in ib.parse(SECTOR_FIXTURE) if r.get('NAICS') == 'Information'], sector['id'], '2026-09-09T12:00:00Z', 'd'*64):
            observation_valid(o, metrics, sources)

    def test_source_is_public_domain_and_not_the_keyed_census_api(self):
        self.assertEqual(ib.SOURCE['license'], 'Public domain (U.S. government work)')
        self.assertEqual(ib.SOURCE['layers'], ['applications'])
        self.assertTrue(ib.NATIONAL_URL.startswith('https://www.census.gov/'))
        self.assertTrue(ib.SECTOR_URL.startswith('https://www.census.gov/'))


class BtosEmptySeriesTests(unittest.TestCase):
    """Every other importer filters new metrics to the ones that actually got a record; this one
    registered the metric whatever came back, so a sector label renamed upstream would have
    published an empty series, and an empty series reads as zero."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        private = Path(self.temp.name)
        # A third sector whose label Census does not publish: its series comes back empty.
        sectors = list(ib.SECTORS)+[('52', 'Finance and Insurance (renamed upstream)', 'Finance and insurance')]
        for p in [patch.object(ib, 'SNAPSHOTS', private/'snapshots'), patch.object(ib.research, 'LOCAL', private/'local'),
                   patch.object(ib, 'SECTORS', sectors), patch.object(ib, 'fetch', self.fetch)]:
            p.start(); self.addCleanup(p.stop)

    def dates(self):
        # days 01 and 15: BTOS reference periods never end on either, so nothing here collides
        # with a published record and the run reports no drift.
        return [f'2026-{month:02d}-01' for month in range(1, 13)]+[f'2025-{month:02d}-15' for month in range(1, 13)]

    def fetch(self, url):
        if url == ib.NATIONAL_URL:
            return json.dumps([{'xmltag': ib.SERIES_TAG, 'Estimate': 20.0, 'Date': d} for d in self.dates()]).encode('utf-8')
        rows = []
        for label in ('Information', 'Professional, Scientific, and Technical Services'):
            rows += [{'xmltag': ib.SERIES_TAG, 'NAICS': label, 'Estimate': 40.0, 'Date': d} for d in self.dates()]
        return json.dumps(rows).encode('utf-8')

    def test_a_series_with_no_observations_is_not_registered_as_a_metric(self):
        result = ib.run(apply=False)
        ids = [m['id'] for m in result['metrics']]
        self.assertNotIn('btos-ai-use-share-naics-52', ids)
        self.assertEqual(result['floor_failures'], [])
        self.assertEqual(result['drift'], [])


if __name__ == '__main__':
    unittest.main()
