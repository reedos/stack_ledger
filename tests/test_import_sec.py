import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import import_sec as ise
import validate_expansion as ve
from validate import observation_valid

TICKERS_BODY = json.dumps({
    "0": {"cik_str": 1045810, "ticker": "NVDA", "title": "NVIDIA CORP"},
    "1": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
}).encode('utf-8')

# A trimmed companyfacts response for one company (values invented; shape matches SEC's real API).
FIXTURE_FACTS = {
    "cik": 1045810, "entityName": "NVIDIA CORP",
    "facts": {
        "us-gaap": {
            "Revenues": {
                "units": {
                    "USD": [
                        {"end": "2024-01-28", "val": 100000000000, "accn": "0001045810-25-000010", "fy": 2024, "fp": "FY", "form": "10-K", "filed": "2025-02-25", "frame": "CY2024"},
                        {"end": "2025-01-26", "val": 130497000000, "accn": "0001045810-26-000010", "fy": 2025, "fp": "FY", "form": "10-K", "filed": "2026-02-25", "frame": "CY2025"},
                        {"end": "2025-04-27", "val": 25000000000, "accn": "0001045810-25-000030", "fy": 2025, "fp": "Q1", "form": "10-Q", "filed": "2025-05-01", "frame": "CY2025Q1"},
                        {"end": "2025-07-27", "val": 30000000000, "accn": "0001045810-25-000040", "fy": 2025, "fp": "Q2", "form": "10-Q", "filed": "2025-08-01", "frame": "CY2025Q2"},
                        # Restated in a later filing; the later-filed value should win.
                        {"end": "2025-07-27", "val": 34567000000, "accn": "0001045810-25-000041", "fy": 2025, "fp": "Q2", "form": "10-Q", "filed": "2025-08-15", "frame": "CY2025Q2"},
                        # No frame: SEC's non-deduplicated raw tag. Must be ignored.
                        {"end": "2025-06-30", "val": 999, "accn": "0001045810-25-000099", "fy": 2025, "fp": "Q2", "form": "10-Q", "filed": "2025-08-01"},
                        # Wrong form: an amendment, not a 10-K/10-Q. Must be ignored even with a frame.
                        {"end": "2025-10-26", "val": 40000000000, "accn": "0001045810-25-000050", "fy": 2025, "fp": "Q3", "form": "10-K/A", "filed": "2025-11-01", "frame": "CY2025Q3"},
                    ]
                }
            },
            "PaymentsToAcquirePropertyPlantAndEquipment": {
                "units": {
                    "USD": [
                        {"end": "2025-01-26", "val": 5000000000, "accn": "0001045810-26-000010", "fy": 2025, "fp": "FY", "form": "10-K", "filed": "2026-02-25", "frame": "CY2025"},
                        {"end": "2025-04-27", "val": 1200000000, "accn": "0001045810-25-000030", "fy": 2025, "fp": "Q1", "form": "10-Q", "filed": "2025-05-01", "frame": "CY2025Q1"},
                    ]
                }
            },
        }
    },
}


class SecImportTests(unittest.TestCase):
    def test_ciks_for_resolves_reviewed_tickers(self):
        result = ise.ciks_for(TICKERS_BODY, ['NVDA'])
        self.assertEqual(result, {'NVDA': 1045810})

    def test_ciks_for_fails_loudly_on_a_missing_ticker(self):
        with self.assertRaises(ValueError):
            ise.ciks_for(TICKERS_BODY, ['ZZZZ'])

    def test_select_concept_tries_revenue_tags_in_order(self):
        concept, usd = ise.select_concept(FIXTURE_FACTS, ise.REVENUE_CONCEPTS)
        self.assertEqual(concept, 'Revenues')
        self.assertTrue(usd)
        # A filer that skipped 'Revenues' entirely falls through to the next concept in order.
        facts_without_first = {"facts": {"us-gaap": {"RevenueFromContractWithCustomerExcludingAssessedTax": {"units": {"USD": [{"val": 1, "form": "10-K", "filed": "2025-01-01", "frame": "CY2024"}]}}}}}
        concept2, usd2 = ise.select_concept(facts_without_first, ise.REVENUE_CONCEPTS)
        self.assertEqual(concept2, 'RevenueFromContractWithCustomerExcludingAssessedTax')
        self.assertTrue(usd2)
        # No revenue concept present at all.
        concept3, usd3 = ise.select_concept({"facts": {"us-gaap": {}}}, ise.REVENUE_CONCEPTS)
        self.assertIsNone(concept3); self.assertEqual(usd3, [])

    def test_frame_selection_ignores_unframed_and_wrong_form_facts_and_keeps_latest_restatement(self):
        _, usd = ise.select_concept(FIXTURE_FACTS, ise.REVENUE_CONCEPTS)
        frames = ise.frame_facts(usd)
        self.assertEqual(sorted(frames), ['CY2024', 'CY2025', 'CY2025Q1', 'CY2025Q2'])   # CY2025Q3 (10-K/A) excluded
        self.assertEqual(frames['CY2025Q2']['val'], 34567000000)   # later-filed restatement wins, not the first-seen fact
        self.assertEqual(frames['CY2025Q2']['filed'], '2025-08-15')

    def test_unit_conversion_to_usd_billion(self):
        _, usd = ise.select_concept(FIXTURE_FACTS, ise.REVENUE_CONCEPTS)
        frames = ise.frame_facts(usd)
        metrics, observations = ise.records_for('nvidia', 'chips', 'revenue', 'Revenues', frames, '2026-09-09T12:00:00Z', 'NVIDIA', 10_000)
        by_id = {o['id']: o for o in observations}
        self.assertEqual(by_id['sec-revenue-nvidia-annual-cy2025']['value'], 130.497)
        self.assertEqual(by_id['sec-revenue-nvidia-quarterly-cy2025q2']['value'], 34.567)
        self.assertIn('$130,497,000,000 USD', by_id['sec-revenue-nvidia-annual-cy2025']['note'])
        self.assertIn('Form 10-K', by_id['sec-revenue-nvidia-annual-cy2025']['note'])
        self.assertIn('filed 2026-02-25', by_id['sec-revenue-nvidia-annual-cy2025']['note'])
        self.assertIn('0001045810-26-000010', by_id['sec-revenue-nvidia-annual-cy2025']['note'])

    def test_quarterly_period_and_year_and_fiscal_vs_calendar_note(self):
        _, usd = ise.select_concept(FIXTURE_FACTS, ise.REVENUE_CONCEPTS)
        frames = ise.frame_facts(usd)
        metrics, observations = ise.records_for('nvidia', 'chips', 'revenue', 'Revenues', frames, '2026-09-09T12:00:00Z', 'NVIDIA', 10_000)
        q = next(o for o in observations if o['id'] == 'sec-revenue-nvidia-quarterly-cy2025q2')
        self.assertEqual((q['year'], q['period'], q['status']), (2025, '2025-Q2', 'observation'))
        a = next(o for o in observations if o['id'] == 'sec-revenue-nvidia-annual-cy2025')
        self.assertEqual((a['year'], a['period']), (2025, 'CY2025'))
        qm = metrics['sec-revenue-nvidia-quarterly']
        self.assertEqual(qm['period_basis'], 'quarter')
        self.assertIn('calendar-quarter', qm['scope'])
        self.assertIn('fiscal', qm['scope'])
        am = metrics['sec-revenue-nvidia-annual']
        self.assertNotIn('period_basis', am)

    def test_metrics_are_reviewed_measurement_types_and_internally_valid(self):
        _, usd = ise.select_concept(FIXTURE_FACTS, ise.REVENUE_CONCEPTS)
        frames = ise.frame_facts(usd)
        metrics, observations = ise.records_for('nvidia', 'chips', 'revenue', 'Revenues', frames, '2026-09-09T12:00:00Z', 'NVIDIA', 10_000)
        for m in metrics.values():
            self.assertEqual(m['company'], 'nvidia')
            self.assertEqual(m['measurement_type'], 'sec_revenue_usd_bn')
            self.assertIn(m['measurement_type'], ve.TYPES)
            self.assertIn(m['measurement_type'], ve.HISTORICAL_ONLY)
            self.assertNotIn(m['measurement_type'], ve.PUBLIC_TYPES)   # company is always set, never None
            self.assertEqual(m['allowed_statuses'], ['observation'])
        sources = {ise.SOURCE_ID: ise.SOURCE}
        for o in observations:
            observation_valid(o, metrics, sources)

    def test_capex_uses_its_own_measurement_type_and_metric_ids(self):
        _, usd = ise.select_concept(FIXTURE_FACTS, ise.CAPEX_CONCEPTS)
        frames = ise.frame_facts(usd)
        metrics, observations = ise.records_for('nvidia', 'chips', 'capex', 'PaymentsToAcquirePropertyPlantAndEquipment', frames, '2026-09-09T12:00:00Z', 'NVIDIA', 2_000)
        self.assertEqual(sorted(metrics), ['sec-capex-nvidia-annual', 'sec-capex-nvidia-quarterly'])
        self.assertTrue(all(m['measurement_type'] == 'sec_capex_usd_bn' for m in metrics.values()))
        by_id = {o['id']: o for o in observations}
        self.assertEqual(by_id['sec-capex-nvidia-annual-cy2025']['value'], 5.0)
        self.assertEqual(by_id['sec-capex-nvidia-quarterly-cy2025q1']['value'], 1.2)

    def test_repeated_runs_produce_stable_ids_idempotent_apply(self):
        """A second run over the same frames must resolve to the same observation ids, so
        importer_common.apply_changes' upsert-by-id never creates a duplicate record."""
        _, usd = ise.select_concept(FIXTURE_FACTS, ise.REVENUE_CONCEPTS)
        frames = ise.frame_facts(usd)
        _, first = ise.records_for('nvidia', 'chips', 'revenue', 'Revenues', frames, '2026-09-09T12:00:00Z', 'NVIDIA', 10_000)
        _, second = ise.records_for('nvidia', 'chips', 'revenue', 'Revenues', frames, '2026-09-10T12:00:00Z', 'NVIDIA', 10_000)
        self.assertEqual(sorted(o['id'] for o in first), sorted(o['id'] for o in second))
        self.assertEqual([o['value'] for o in first], [o['value'] for o in second])

    def test_foreign_filers_and_aws_are_not_in_the_reviewed_ticker_map_and_are_reported(self):
        reviewed = ise.load_companies()['companies']
        for company_id in list(ise.SKIPPED['foreign_filers']) + ['aws']:
            self.assertNotIn(company_id, reviewed)
        self.assertEqual(set(ise.SKIPPED['foreign_filers']), {'tsmc', 'asml', 'nebius', 'alibaba'})
        self.assertIsInstance(ise.SKIPPED['aws'], str)
        self.assertIn('amazon', ise.SKIPPED['aws'].lower())

    def test_reviewed_companies_are_all_sec_domestic_filers(self):
        ecosystem = json.loads((ROOT/'research/ecosystem.json').read_text(encoding='utf-8'))
        by_id = {c['id']: c for c in ecosystem['companies']}
        reviewed = ise.load_companies()['companies']
        self.assertTrue(reviewed)
        for company_id, entry in reviewed.items():
            self.assertIn(company_id, by_id)
            self.assertEqual(by_id[company_id]['filings_jurisdiction'], 'SEC')
            self.assertTrue(entry['ticker'])

    def test_source_is_public_domain_and_covers_every_reviewed_layer(self):
        self.assertEqual(ise.SOURCE['license'], 'Public domain (U.S. government work)')
        ecosystem = json.loads((ROOT/'research/ecosystem.json').read_text(encoding='utf-8'))
        by_id = {c['id']: c for c in ecosystem['companies']}
        reviewed = ise.load_companies()['companies']
        used_layers = {by_id[cid]['layers'][0] for cid in reviewed}
        self.assertTrue(used_layers <= set(ise.SOURCE['layers']))


if __name__ == '__main__':
    unittest.main()


class SeriesStartTests(unittest.TestCase):
    def test_frames_before_the_reviewed_series_start_are_skipped(self):
        import import_sec as isec
        frames={'CY2015': {'val': 1e9, 'form': '10-K', 'filed': '2016-02-01', 'accn': 'a'}, 'CY2024': {'val': 2e9, 'form': '10-K', 'filed': '2025-02-01', 'accn': 'b'}}
        metrics, obs = isec.records_for('nvidia', 'chips', 'revenue', 'us-gaap:Revenues', frames, '2026-09-09T00:00:00Z', 'NVIDIA', 10000)
        self.assertEqual([o['year'] for o in obs], [2024])
        self.assertEqual(metrics['sec-revenue-nvidia-annual']['series_start_year'], isec.START_YEAR)
