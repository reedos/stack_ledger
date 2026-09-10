"""Promote a report into tracked coverage in one tap (report_promotion.py): deterministic
name/location extraction from a report's own headline, owner resolved only from a registered
company_id (never parsed out of prose), a schema-valid status-unverified project draft, the
publication-policy auto-apply refusal, idempotent double promotion, and the refusal paths.
No network; no model.
"""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import catalog_review as c
import report_promotion as rpp
from editorial_review import events
from publication_policy import policy as pub_policy, eligible
from validate_delivery import validate_delivery
from unittest.mock import patch


class SiteTextTests(unittest.TestCase):
    """Deterministic, literal extraction: the last ' in <place>' in the title. No gazetteer,
    no model, no capitalization guesswork beyond requiring the location look place-like."""

    def test_extracts_name_and_location_from_a_real_style_headline(self):
        title = 'S+B Gruppe secures planning permission for 12MW NIMB data center in Bucharest'
        name, location = rpp.site_text(title)
        self.assertEqual(location, 'Bucharest')
        self.assertEqual(name, 'S+B Gruppe secures planning permission for 12MW NIMB data center')

    def test_no_in_clause_refuses(self):
        title = 'Sunrun Voltus residential battery capacity for AI hyperscale data centers'
        self.assertIsNone(rpp.site_text(title))

    def test_lowercase_trailing_phrase_is_not_a_location(self):
        # "in operating costs" is not a place; refuse rather than draft a bogus location.
        title = 'Fixture Co reports a difference in operating costs'
        self.assertIsNone(rpp.site_text(title))

    def test_too_short_remainder_refuses(self):
        self.assertIsNone(rpp.site_text('AI in Ohio'))          # name fragment too short
        self.assertIsNone(rpp.site_text('Fixture Co breaks ground in a'))  # location too short

    def test_multi_word_location_supported(self):
        title = 'Fixture Energy announces a new substation in Lower Saxony'
        name, location = rpp.site_text(title)
        self.assertEqual(location, 'Lower Saxony')
        self.assertEqual(name, 'Fixture Energy announces a new substation')


class PromotionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup); self.root = Path(self.temp.name)
        for file in c.FILES: c.save(self.root/file, c.read(ROOT/file))
        self.git = patch.object(c, 'git', return_value='fixture-head'); self.git.start(); self.addCleanup(self.git.stop)
        ledger = c.read(self.root/'site/data/ledger.json')
        self.source = {'id': 'discovered-fixture-1', 'publisher': 'Fixture Wire',
            'title': 'Discovered public update — Fixture Wire', 'url': 'https://fixturewire.example/2026/09/fixture-site',
            'published': '2026-09-09', 'layers': ['infrastructure'], 'license': 'Original source rights apply',
            'parent_source': 'outlet-fixture-news'}
        ledger['sources'].append(self.source)
        self.report_id = 'note-' + 'a'*20
        self.report = self._report()
        ledger['events'].append(self.report)
        c.save(self.root/'site/data/ledger.json', ledger)

    def _report(self, **overrides):
        report = {'id': self.report_id, 'layer': 'infrastructure', 'date': '2026-09-09',
            'title': 'Fixture Co secures planning permission for a data center in Fixtureville',
            'summary': 'Fixture Co secured planning permission for a data center in Fixtureville, per Fixture Wire.',
            'source': self.source['id'], 'kind': 'News report', 'method': 'automated',
            'retrieved_at': '2026-09-09T12:00:00Z', 'document_sha256': '0'*64, 'evidence_sha256': '0'*64,
            'grade': 'C', 'outlet': 'Fixture Wire', 'reported_on': '2026-09-09', 'about': [],
            'quote': 'Fixture Co said it secured planning permission.', 'confirmation': 'unconfirmed'}
        report.update(overrides)
        return report

    def _set_report(self, **overrides):
        ledger = c.read(self.root/'site/data/ledger.json')
        for i, e in enumerate(ledger['events']):
            if e['id'] == self.report_id:
                ledger['events'][i] = self._report(**overrides)
        c.save(self.root/'site/data/ledger.json', ledger)

    # --- success shape -----------------------------------------------------------------
    def test_builds_a_status_unverified_project_draft(self):
        outcome = rpp.promote(self.root, self.report_id, 'human')
        p = outcome['package']
        self.assertFalse(outcome['already_promoted'])
        self.assertEqual(p['author'], 'Report promotion (owner action)')
        self.assertEqual(len(p['changes']), 1)
        change = p['changes'][0]
        self.assertEqual(change['target'], 'project')
        self.assertIsNone(change['before'])
        after = change['after']
        self.assertEqual(after['stage'], 'status-unverified')
        self.assertEqual(after['location'], 'Fixtureville')
        self.assertEqual(after['owner'], rpp.NOT_NAMED)   # no registered company_id on this source
        self.assertEqual(after['observations'], [])
        self.assertEqual(len(after['milestones']), 1)
        self.assertEqual(after['milestones'][0]['source'], self.source['id'])
        self.assertEqual(after['milestones'][0]['date'], self.report['date'])
        self.assertEqual(after['milestones'][0]['summary'], self.report['summary'])
        self.assertEqual(p['evidence'][0]['id'], self.report_id)
        self.assertNotIn('company_ids', after)

    def test_never_carries_a_numeric_record(self):
        after = rpp.promote(self.root, self.report_id, 'human')['package']['changes'][0]['after']
        self.assertEqual(after['observations'], [])
        for forbidden in ['capacity', 'megawatts', 'value']:
            self.assertNotIn(forbidden, after)

    # --- deliverable test 1: schema validity --------------------------------------------
    def test_package_validates_against_delivery_schema(self):
        p = rpp.promote(self.root, self.report_id, 'human')['package']
        documents = c.base(self.root)
        projected = c.projected(p, documents)
        self.assertTrue(validate_delivery(projected['research/delivery.json'], projected['site/data/ledger.json']))

    # --- deliverable test: never auto-applies -------------------------------------------
    def test_not_eligible_for_auto_apply(self):
        p = rpp.promote(self.root, self.report_id, 'human')['package']
        c.save(self.root/'research/publication-policy.json', c.read(ROOT/'research/publication-policy.json'))
        pol = pub_policy(self.root)
        registry = c.read(self.root/'research/sources.json')
        ok, reasons = eligible(p, pol, registry)
        self.assertFalse(ok)
        self.assertIn('Report promotion (owner action)', reasons[0])

    # --- owner: only from a registered company_id, never parsed from prose --------------
    def test_owner_resolved_from_registered_company_id(self):
        registry = c.read(self.root/'research/sources.json')
        registry['collection']['outlet-fixture-company'] = dict(rank=6, region_book='global', company_id='nextera',
            claim_type='other', cadence='daily', weekday=0, path_prefixes=[], topics=[], excerpts=False)
        c.save(self.root/'research/sources.json', registry)
        ledger = c.read(self.root/'site/data/ledger.json')
        company_source = dict(self.source, id='discovered-fixture-2', parent_source='outlet-fixture-company')
        ledger['sources'].append(company_source)
        report = self._report(id='note-'+'b'*20, source=company_source['id'],
            title='NextEra Energy breaks ground on a new substation in Ohioville')
        ledger['events'].append(report)
        c.save(self.root/'site/data/ledger.json', ledger)
        after = rpp.promote(self.root, report['id'], 'human')['package']['changes'][0]['after']
        self.assertEqual(after['owner'], 'NextEra Energy')
        self.assertEqual(after['company_ids'], ['nextera'])

    def test_owner_never_parsed_from_headline_text(self):
        # The headline names "Fixture Co" as the actor, but its source carries no registered
        # company_id -- the draft must not guess an owner out of the prose.
        after = rpp.promote(self.root, self.report_id, 'human')['package']['changes'][0]['after']
        self.assertNotIn('Fixture Co', after['owner'])
        self.assertEqual(after['owner'], rpp.NOT_NAMED)

    # --- refusals ------------------------------------------------------------------------
    def test_refuses_when_no_site_is_named(self):
        self._set_report(title='Sunrun Voltus residential battery capacity for AI hyperscale data centers')
        with self.assertRaisesRegex(ValueError, 'does not name a site'):
            rpp.promote(self.root, self.report_id, 'human')

    def test_refuses_an_unknown_report(self):
        with self.assertRaisesRegex(ValueError, 'not found'):
            rpp.promote(self.root, 'note-doesnotexist', 'human')

    def test_refuses_a_non_report_event(self):
        ledger = c.read(self.root/'site/data/ledger.json')
        note = {'id': 'note-plain', 'layer': 'infrastructure', 'date': '2026-09-09', 'title': 'A note',
                'summary': 'A plain curated note.', 'source': self.source['id'], 'kind': 'Research finding', 'grade': 'B'}
        ledger['events'].append(note)
        c.save(self.root/'site/data/ledger.json', ledger)
        with self.assertRaisesRegex(ValueError, 'News report or Social post'):
            rpp.promote(self.root, note['id'], 'human')

    def test_refuses_a_retracted_report(self):
        self._set_report(retracted=True, retraction_reason='Misattributed.', retracted_at='2026-09-10T00:00:00Z', retracted_by='human')
        with self.assertRaisesRegex(ValueError, 'Retracted reports cannot be tracked'):
            rpp.promote(self.root, self.report_id, 'human')

    def test_requires_a_reviewer(self):
        with self.assertRaisesRegex(ValueError, 'authorized reviewer'):
            rpp.promote(self.root, self.report_id, '')

    # --- idempotency and audit trail -------------------------------------------------------
    def test_double_promotion_returns_the_existing_package(self):
        first = rpp.promote(self.root, self.report_id, 'human')
        second = rpp.promote(self.root, self.report_id, 'human')
        self.assertFalse(first['already_promoted'])
        self.assertTrue(second['already_promoted'])
        self.assertEqual(first['package']['id'], second['package']['id'])
        promotion_events = [e for e in events(self.root) if e.get('kind') == 'report_promotion' and e.get('report_id') == self.report_id]
        self.assertEqual(len(promotion_events), 1)

    def test_audit_trail_links_report_to_package(self):
        p = rpp.promote(self.root, self.report_id, 'human', identity={'channel': 'loopback', 'login': None})['package']
        event = [e for e in events(self.root) if e.get('kind') == 'report_promotion'][-1]
        self.assertEqual(event['report_id'], self.report_id)
        self.assertEqual(event['package_id'], p['id'])
        self.assertEqual(event['reviewer'], 'human')
        self.assertEqual(event['channel'], 'loopback')
        self.assertNotIn('login', event)

    def test_tailnet_identity_records_login(self):
        rpp.promote(self.root, self.report_id, 'human', identity={'channel': 'tailnet', 'login': 'reedosaki@gmail.com'})
        event = [e for e in events(self.root) if e.get('kind') == 'report_promotion'][-1]
        self.assertEqual(event['channel'], 'tailnet')
        self.assertEqual(event['login'], 'reedosaki@gmail.com')


if __name__ == '__main__':
    unittest.main()
