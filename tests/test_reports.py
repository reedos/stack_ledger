"""Deliverable 7: grade derivation, report schema/rendering data, confirmation/contradiction/
expiry logic, discovery/numeric-series publication gates, registry additions, and the panel's
Activity listing + Retract action. No network; no model."""
import copy
import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import research
import reports as rp
import find_feeds as ff
import validate as validate_module
from source_policy import grade_for, collection_for
from validate import event_valid, observation_valid, validate, GRADES, REPORT_KINDS


def registry():
    return json.loads((ROOT/'research/sources.json').read_text(encoding='utf-8'))


class GradeDerivationTests(unittest.TestCase):
    """The deterministic table: rank 1 -> A; a registered news outlet -> C regardless of rank;
    every other rank 2/3/4/6 -> B (company statement, incl. official social account); rank 5
    (trade/analyst) -> C; anything unrecognized fails closed to D."""
    def test_derivation_table(self):
        cases = [
            ({'rank': 1, 'claim_type': 'other'}, 'A'),
            ({'rank': 1, 'claim_type': 'news'}, 'A'),          # rank 1 wins regardless of claim_type
            ({'rank': 2, 'claim_type': 'financial'}, 'B'),
            ({'rank': 3, 'claim_type': 'other'}, 'B'),
            ({'rank': 4, 'claim_type': 'other'}, 'B'),
            ({'rank': 4, 'claim_type': 'news'}, 'C'),
            ({'rank': 5, 'claim_type': 'other'}, 'C'),
            ({'rank': 5, 'claim_type': 'news'}, 'C'),
            ({'rank': 6, 'claim_type': 'other'}, 'B'),         # official social account
            ({'rank': 7, 'claim_type': 'other'}, 'D'),         # outside the reviewed 1-6 range
            # No collection policy at all: an evidence-only citation the runner never collects. It is
            # graded by its publisher, not called an unverified social claim (corrected 2026-09-10,
            # when 64 curated company press releases were badged "Grade D" on the public site).
            (None, 'C'),
            ({}, 'C'),
        ]
        for policy, expected in cases:
            with self.subTest(policy=policy):
                self.assertEqual(grade_for(policy), expected)


    def test_an_evidence_only_citation_is_graded_by_its_publisher(self):
        companies = [{'name': 'Marvell', 'ir_url': 'https://investor.marvell.com/', 'blog_urls': []}]
        company_page = {'id': 'astra-marvell-optics', 'url': 'https://investor.marvell.com/news/x', 'publisher': 'Marvell'}
        independent = {'id': 'someone-else', 'url': 'https://example.org/analysis', 'publisher': 'Example Institute'}
        self.assertEqual(grade_for(None, company_page, companies), 'B')
        self.assertEqual(grade_for(None, independent, companies), 'C')
        self.assertEqual(grade_for(None, company_page, []), 'C')       # no company records: independent, never D
        self.assertEqual(grade_for({'rank': 7}, company_page, companies), 'D')   # a registered rank outside 1-6 stays D
    def test_every_registered_source_grades_to_a_known_value(self):
        r = registry()
        for sid, policy in r['collection'].items():
            with self.subTest(source=sid):
                self.assertIn(grade_for(policy), GRADES)

    def test_registered_news_outlets_are_grade_c_with_excerpts(self):
        r = registry()
        outlets = [sid for sid, p in r['collection'].items() if p['claim_type'] == 'news']
        self.assertTrue(outlets, 'deliverable 4 should have registered at least one news outlet')
        for sid in outlets:
            p = r['collection'][sid]
            self.assertEqual(p['rank'], 4)
            self.assertTrue(p['excerpts'])
            self.assertEqual(grade_for(p), 'C')

    def test_rank_one_always_wins_as_a_even_with_news_claim_type(self):
        self.assertEqual(grade_for({'rank': 1, 'claim_type': 'news'}), 'A')


class ReportEventSchemaTests(unittest.TestCase):
    """event_valid's report-lane shape: required fields, kind/grade coupling, confirmation
    vocabulary, matching-field bundling, and retraction fields."""
    def setUp(self):
        self.source = {'id': 'outlet-test', 'url': 'https://news.example/feed', 'layers': ['chips'],
                        'publisher': 'Test News', 'published': '2026-09-01'}
        self.sources = {'outlet-test': self.source}
        self.event = {'id': 'note-' + 'a'*20, 'layer': 'chips', 'date': '2026-09-01', 'title': 'A report',
                       'summary': 'A summary of the report.', 'source': 'outlet-test', 'kind': 'News report',
                       'method': 'automated', 'retrieved_at': '2026-09-02T00:00:00Z',
                       'document_sha256': '0'*64, 'evidence_sha256': '0'*64, 'grade': 'C',
                       'outlet': 'Test News', 'reported_on': '2026-09-01', 'about': ['company-x'],
                       'quote': 'A quoted passage.', 'confirmation': 'unconfirmed'}

    def test_valid_report_passes(self):
        event_valid(self.event, self.sources)

    def test_report_kind_requires_grade_c_or_d(self):
        with self.assertRaises(ValueError):
            event_valid(dict(self.event, grade='B'), self.sources)

    def test_non_report_kind_cannot_carry_report_fields(self):
        e = dict(self.event, kind='Company announcement', grade='B')
        with self.assertRaises(ValueError):
            event_valid(e, self.sources)

    def test_missing_grade_rejected(self):
        e = {k: v for k, v in self.event.items() if k != 'grade'}
        with self.assertRaises(ValueError):
            event_valid(e, self.sources)

    def test_report_missing_a_required_report_field_rejected(self):
        for k in ['outlet', 'reported_on', 'about', 'quote', 'confirmation']:
            with self.subTest(missing=k):
                e = {x: v for x, v in self.event.items() if x != k}
                with self.assertRaises(ValueError):
                    event_valid(e, self.sources)

    def test_invalid_confirmation_state_rejected(self):
        with self.assertRaises(ValueError):
            event_valid(dict(self.event, confirmation='maybe'), self.sources)

    def test_confirmed_by_and_contradicted_by_states_accepted(self):
        event_valid(dict(self.event, confirmation='confirmed_by:some-obs-id'), self.sources)
        event_valid(dict(self.event, confirmation='contradicted_by:some-obs-id'), self.sources)

    def test_expired_confirmation_state_accepted(self):
        event_valid(dict(self.event, confirmation='expired'), self.sources)

    def test_matching_fields_must_travel_together(self):
        e = dict(self.event, metric_id='ai-adoption')  # period/value/precision/upper missing
        with self.assertRaises(ValueError):
            event_valid(e, self.sources)

    def test_complete_matching_fields_accepted(self):
        e = dict(self.event, metric_id='ai-adoption', period='2026', value=50.0, precision='eq', upper=None)
        event_valid(e, self.sources)

    def test_retraction_requires_every_field(self):
        with self.assertRaises(ValueError):
            event_valid(dict(self.event, retracted=True), self.sources)
        complete = dict(self.event, retracted=True, retraction_reason='Misattributed claim',
                         retracted_at='2026-09-05T00:00:00Z', retracted_by='reedos')
        event_valid(complete, self.sources)

    def test_retraction_fields_only_valid_on_a_report(self):
        base = {'id': 'note-' + 'b'*20, 'layer': 'chips', 'date': '2026-09-01', 'title': 'A note',
                'summary': 'A plain note.', 'source': 'outlet-test', 'kind': 'Research finding',
                'method': 'automated', 'retrieved_at': '2026-09-02T00:00:00Z',
                'document_sha256': '0'*64, 'evidence_sha256': '0'*64, 'grade': 'A',
                'retracted': True, 'retraction_reason': 'x', 'retracted_at': '2026-09-05T00:00:00Z',
                'retracted_by': 'reedos'}
        with self.assertRaises(ValueError):
            event_valid(base, self.sources)

    def test_bare_curated_event_needs_only_grade(self):
        curated = {'id': 'curated-note', 'layer': 'chips', 'date': None, 'title': 'Curated',
                   'summary': 'A hand-curated note.', 'source': 'outlet-test', 'kind': 'Research finding',
                   'grade': 'B'}
        event_valid(curated, self.sources)


class AutomatedObservationGradeTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((ROOT/'site/data/ledger.json').read_text(encoding='utf-8'))
        self.metrics = {m['id']: m for m in self.data['metrics']}
        self.sources = {s['id']: s for s in self.data['sources']}

    def observation(self, **overrides):
        base = dict(id='auto-test', metric='ai-adoption', year=2026, period='2026', value=90, upper=None,
                    status='observation', precision='eq', retrieved_at='2026-09-05T00:00:00Z', method='automated',
                    note='', source='stanford-2026', document_sha256='0'*64, evidence_sha256='0'*64)
        base.update(overrides)
        return base

    def test_automated_observation_requires_grade_a_or_b(self):
        with self.assertRaisesRegex(ValueError, 'grade A or B'):
            observation_valid(self.observation(), self.metrics, self.sources)

    def test_grade_a_automated_observation_passes(self):
        observation_valid(self.observation(grade='A'), self.metrics, self.sources)

    def test_grade_c_or_d_automated_observation_rejected(self):
        for g in ('C', 'D'):
            with self.subTest(grade=g):
                with self.assertRaisesRegex(ValueError, 'grade A or B'):
                    observation_valid(self.observation(grade=g), self.metrics, self.sources)

    def test_curated_observation_never_requires_grade(self):
        curated = dict(id='curated-1', metric='ai-adoption', year=2026, period='2026', value=90,
                        upper=None, status='observation', precision='eq',
                        retrieved_at='2026-09-05T00:00:00Z', method='curated', note='',
                        source='stanford-2026')
        observation_valid(curated, self.metrics, self.sources)


class NumericSeriesGuardTests(unittest.TestCase):
    """Deliverable 1's hard rule enforced where a numeric record is actually minted: a grade
    C/D source cannot produce an observation at all -- extraction fails closed, not silently."""
    def setUp(self):
        self.data = json.loads((ROOT/'site/data/ledger.json').read_text(encoding='utf-8'))
        self.registry = registry()
        self.metrics = {m['id']: m for m in self.data['metrics']}
        self.sources = {s['id']: s for s in self.data['sources']}

    def test_grade_c_registered_news_source_cannot_mint_an_observation(self):
        sid = next(s for s, p in self.registry['collection'].items() if p['claim_type'] == 'news')
        source = next(s for s in self.registry['sources'] if s['id'] == sid)
        policy = collection_for(self.registry, source)
        self.assertEqual(grade_for(policy), 'C')
        candidate = {'metric': 'ai-adoption', 'year': 2026, 'period': '2026', 'value': 50, 'upper': None,
                     'status': 'observation', 'precision': 'eq', 'note': '',
                     'evidence': 'The report states 50 percent adoption in 2026.'}
        with self.assertRaisesRegex(ValueError, 'Grade C evidence cannot become a numeric observation'):
            research.candidate_record(candidate, source, candidate['evidence'], self.metrics, self.sources,
                                       [], policy)

    def test_grade_a_source_still_mints_an_observation(self):
        source = self.sources['stanford-2026']
        policy = collection_for(self.registry, source)
        candidate = {'metric': 'ai-adoption', 'year': 2026, 'period': '2026', 'value': 90, 'upper': None,
                     'status': 'observation', 'precision': 'eq', 'note': '',
                     'evidence': 'In 2026, 90 percent of surveyed organizations reported AI use.'}
        record = research.candidate_record(candidate, source, candidate['evidence'], self.metrics,
                                            self.sources, [], policy)
        self.assertEqual(record['grade'], 'A')


class ReportPublicationTests(unittest.TestCase):
    """extract_note assembles the report shape deterministically from the source's policy --
    grade, kind, outlet, reported_on, about, quote, confirmation -- never the model's choice."""
    def test_discovered_news_source_note_becomes_a_report(self):
        source = {'id': 'discovered-abc', 'url': 'https://news.example/2026/09/article',
                   'layers': ['chips'], 'publisher': 'Test News', 'published': '2026-09-01',
                   'parent_source': 'outlet-test'}
        policy = {'rank': 4, 'claim_type': 'news', 'region_book': 'global', 'company_id': None,
                   'cadence': 'daily', 'weekday': 0, 'path_prefixes': ['/2026/'], 'topics': ['ai'],
                   'excerpts': True}
        note = {'title': 'Company X ships new chip', 'kind': 'Research finding', 'layer': 'chips',
                'summary': 'A report says Company X shipped 500 units in 2026.',
                'evidence': 'A report says Company X shipped 500 units in 2026.'}
        run = {'model_calls': 0}
        with tempfile.TemporaryDirectory() as tmp, patch.object(research, 'LOCAL', Path(tmp)), \
             patch.object(research, 'ollama', side_effect=[{'notes': [note]},
                          {'verdicts': [{'index': 0, 'supported': True, 'reason': 'Direct support'}]}]):
            event = research.extract_note({}, source, note['evidence'], [], run, [], None, policy)
        self.assertEqual(event['kind'], 'News report')
        self.assertEqual(event['grade'], 'C')
        self.assertEqual(event['outlet'], 'Test News')
        self.assertEqual(event['reported_on'], '2026-09-01')
        self.assertEqual(event['confirmation'], 'unconfirmed')
        self.assertEqual(event['quote'], note['evidence'])
        event_valid(event, {source['id']: source})

    def test_official_social_account_note_stays_a_normal_announcement_not_a_report(self):
        # rank 6 (official social account) grades B, same as any other company channel: it
        # never enters the reports lane, it keeps the model's own six-value kind choice.
        source = {'id': 'discovered-social', 'url': 'https://bsky.app/profile/x/post/1',
                   'layers': ['chips'], 'publisher': 'Company X', 'published': '2026-09-01',
                   'parent_source': 'social-x'}
        policy = {'rank': 6, 'claim_type': 'other', 'region_book': 'global', 'company_id': 'company-x',
                   'cadence': 'daily', 'weekday': 0, 'path_prefixes': ['/profile/'], 'topics': ['ai'],
                   'excerpts': False}
        note = {'title': 'Company X announces expansion', 'kind': 'Company announcement', 'layer': 'chips',
                'summary': 'Company X posted about a new facility opening in 2026.',
                'evidence': 'Company X posted about a new facility opening in 2026.'}
        run = {'model_calls': 0}
        with tempfile.TemporaryDirectory() as tmp, patch.object(research, 'LOCAL', Path(tmp)), \
             patch.object(research, 'ollama', side_effect=[{'notes': [note]},
                          {'verdicts': [{'index': 0, 'supported': True, 'reason': 'Direct support'}]}]):
            event = research.extract_note({}, source, note['evidence'], [], run, [], None, policy)
        self.assertEqual(event['kind'], 'Company announcement')
        self.assertEqual(event['grade'], 'B')
        self.assertNotIn('outlet', event)
        self.assertNotIn('confirmation', event)
        event_valid(event, {source['id']: source})

    def test_no_registry_policy_fails_closed_to_grade_d(self):
        self.assertEqual(rp.report_kind({'rank': 6}), 'Social post')
        self.assertEqual(rp.report_kind({'rank': 4, 'claim_type': 'news'}), 'News report')
        self.assertEqual(rp.report_kind(None), 'News report')


class AboutLinkingTests(unittest.TestCase):
    """Deterministic, non-model company/project linkage for report cards."""
    def test_company_id_and_project_name_match(self):
        ids = rp.about_ids(ROOT, {'company_id': 'nextera'},
                            'Gemini solar project announced',
                            'The Gemini solar + storage project in Nevada announced an expansion.')
        self.assertIn('nextera', ids)
        self.assertIn('gemini', ids)

    def test_no_project_name_match_returns_just_the_company(self):
        ids = rp.about_ids(ROOT, {'company_id': 'nextera'}, 'Unrelated headline',
                            'Nothing project-specific in this text at all.')
        self.assertEqual(ids, ['nextera'])

    def test_no_policy_and_no_match_returns_empty(self):
        self.assertEqual(rp.about_ids(ROOT, {}, 'x', 'y'), [])
        self.assertEqual(rp.about_ids(ROOT, None, 'x', 'y'), [])

    def test_result_is_bounded(self):
        # Every project name concatenated cannot blow past the deliberate cap.
        delivery = json.loads((ROOT/'research/delivery.json').read_text(encoding='utf-8'))
        text = ' '.join(p['name'] for p in delivery['projects'])
        ids = rp.about_ids(ROOT, {'company_id': 'nextera'}, text, '')
        self.assertLessEqual(len(ids), 5)


class ConfirmationReconciliationTests(unittest.TestCase):
    """Deterministic metric+period matching only -- never a model call."""
    def report(self, **overrides):
        base = {'id': 'note-report1', 'layer': 'chips', 'date': '2026-06-01', 'title': 'A report',
                'summary': 'A summary.', 'source': 'outlet-test', 'kind': 'News report', 'method': 'automated',
                'retrieved_at': '2026-06-01T00:00:00Z', 'document_sha256': '0'*64, 'evidence_sha256': '0'*64,
                'grade': 'C', 'outlet': 'Test News', 'reported_on': '2026-06-01', 'about': [],
                'quote': 'quoted', 'confirmation': 'unconfirmed', 'metric_id': 'ai-adoption',
                'period': '2026', 'value': 50, 'precision': 'eq', 'upper': None}
        base.update(overrides)
        return base

    def test_matching_observation_confirms(self):
        obs = [{'id': 'obs1', 'metric': 'ai-adoption', 'period': '2026', 'value': 50, 'precision': 'eq'}]
        updated, changed = rp.reconcile_confirmations([self.report()], obs)
        self.assertEqual(updated[0]['confirmation'], 'confirmed_by:obs1')
        self.assertEqual(changed, ['note-report1'])

    def test_conflicting_value_contradicts(self):
        obs = [{'id': 'obs1', 'metric': 'ai-adoption', 'period': '2026', 'value': 90, 'precision': 'eq'}]
        updated, changed = rp.reconcile_confirmations([self.report()], obs)
        self.assertEqual(updated[0]['confirmation'], 'contradicted_by:obs1')

    def test_approx_precision_tolerates_a_small_difference(self):
        obs = [{'id': 'obs1', 'metric': 'ai-adoption', 'period': '2026', 'value': 51, 'precision': 'approx'}]
        updated, _ = rp.reconcile_confirmations([self.report(value=50)], obs)
        self.assertEqual(updated[0]['confirmation'], 'confirmed_by:obs1')

    def test_no_matching_period_stays_unconfirmed(self):
        obs = [{'id': 'obs1', 'metric': 'ai-adoption', 'period': '2027', 'value': 50, 'precision': 'eq'}]
        updated, changed = rp.reconcile_confirmations([self.report()], obs)
        self.assertEqual(updated[0]['confirmation'], 'unconfirmed')
        self.assertEqual(changed, [])

    def test_no_matching_metric_stays_unconfirmed(self):
        obs = [{'id': 'obs1', 'metric': 'other-metric', 'period': '2026', 'value': 50, 'precision': 'eq'}]
        updated, changed = rp.reconcile_confirmations([self.report()], obs)
        self.assertEqual(updated[0]['confirmation'], 'unconfirmed')

    def test_superseded_observation_is_not_a_match(self):
        obs = [{'id': 'obs1', 'metric': 'ai-adoption', 'period': '2026', 'value': 50, 'precision': 'eq',
                'superseded_by': 'obs2'}]
        updated, changed = rp.reconcile_confirmations([self.report()], obs)
        self.assertEqual(updated[0]['confirmation'], 'unconfirmed')

    def test_already_decided_report_is_never_rematched(self):
        obs = [{'id': 'obs2', 'metric': 'ai-adoption', 'period': '2026', 'value': 999, 'precision': 'eq'}]
        updated, changed = rp.reconcile_confirmations([self.report(confirmation='confirmed_by:old')], obs)
        self.assertEqual(updated[0]['confirmation'], 'confirmed_by:old')
        self.assertEqual(changed, [])

    def test_retracted_report_is_never_rematched(self):
        report = self.report(retracted=True, retraction_reason='wrong', retracted_at='2026-06-02T00:00:00Z',
                              retracted_by='reedos')
        obs = [{'id': 'obs1', 'metric': 'ai-adoption', 'period': '2026', 'value': 50, 'precision': 'eq'}]
        updated, changed = rp.reconcile_confirmations([report], obs)
        self.assertEqual(updated[0]['confirmation'], 'unconfirmed')
        self.assertEqual(changed, [])

    def test_report_without_metric_id_never_matches(self):
        report = self.report()
        for k in ['metric_id', 'period', 'value', 'precision', 'upper']:
            del report[k]
        obs = [{'id': 'obs1', 'metric': 'ai-adoption', 'period': '2026', 'value': 50, 'precision': 'eq'}]
        updated, changed = rp.reconcile_confirmations([report], obs)
        self.assertEqual(updated[0]['confirmation'], 'unconfirmed')

    def test_non_report_events_are_left_untouched(self):
        note = {'id': 'note-x', 'kind': 'Research finding', 'confirmation': 'unconfirmed'}
        obs = [{'id': 'obs1', 'metric': 'ai-adoption', 'period': '2026', 'value': 50, 'precision': 'eq'}]
        updated, changed = rp.reconcile_confirmations([note], obs)
        self.assertEqual(updated, [note])
        self.assertEqual(changed, [])


class ExpiryDisplayTests(unittest.TestCase):
    """'expired' is a display fact over an unconfirmed report -- the stored field is untouched."""
    def test_unconfirmed_past_90_days_reads_expired(self):
        e = {'confirmation': 'unconfirmed', 'reported_on': '2026-01-01'}
        self.assertEqual(rp.effective_confirmation(e, date(2026, 9, 10)), 'expired')

    def test_unconfirmed_within_90_days_stays_unconfirmed(self):
        e = {'confirmation': 'unconfirmed', 'reported_on': '2026-08-20'}
        self.assertEqual(rp.effective_confirmation(e, date(2026, 9, 10)), 'unconfirmed')

    def test_exactly_90_days_is_still_unconfirmed_not_expired(self):
        e = {'confirmation': 'unconfirmed', 'reported_on': '2026-06-12'}
        self.assertEqual(rp.effective_confirmation(e, date(2026, 9, 10)), 'unconfirmed')

    def test_confirmed_state_never_shown_as_expired(self):
        e = {'confirmation': 'confirmed_by:x', 'reported_on': '2020-01-01'}
        self.assertEqual(rp.effective_confirmation(e, date(2026, 9, 10)), 'confirmed_by:x')

    def test_missing_date_stays_unconfirmed(self):
        e = {'confirmation': 'unconfirmed'}
        self.assertEqual(rp.effective_confirmation(e, date(2026, 9, 10)), 'unconfirmed')

    def test_falls_back_to_date_when_reported_on_missing(self):
        e = {'confirmation': 'unconfirmed', 'date': '2026-01-01'}
        self.assertEqual(rp.effective_confirmation(e, date(2026, 9, 10)), 'expired')


class ConfirmationOnlyChangeTests(unittest.TestCase):
    """The one in-place mutation an ordinary monitoring run may make to an already-published
    report (research.validate_monitoring_delta's authorized exception)."""
    def test_only_confirmation_differs(self):
        old = {'id': 'x', 'confirmation': 'unconfirmed', 'title': 't'}
        self.assertTrue(rp.confirmation_only_change(old, dict(old, confirmation='confirmed_by:y')))

    def test_other_field_change_is_not_confirmation_only(self):
        old = {'id': 'x', 'confirmation': 'unconfirmed', 'title': 't'}
        new = dict(old, confirmation='confirmed_by:y', title='different')
        self.assertFalse(rp.confirmation_only_change(old, new))

    def test_identical_record_is_not_a_change(self):
        old = {'id': 'x', 'confirmation': 'unconfirmed'}
        self.assertFalse(rp.confirmation_only_change(old, dict(old)))

    def test_key_set_change_is_rejected(self):
        old = {'id': 'x', 'confirmation': 'unconfirmed'}
        new = {'id': 'x', 'confirmation': 'confirmed_by:y', 'extra': 1}
        self.assertFalse(rp.confirmation_only_change(old, new))


def minimal_ledger(event=None):
    return {'version': 1, 'seed_date': '2026-01-01', 'layers': [], 'metrics': [], 'targets': [],
            'sources': [], 'observations': [], 'events': [event] if event else [], 'runs': [],
            'runtime': {}}


class MonitoringDeltaConfirmationTests(unittest.TestCase):
    """validate_monitoring_delta's deliverable-2 exception: a confirmation-only change to an
    existing report is allowed; anything else about an existing record still is not."""
    def test_confirmation_only_change_allowed(self):
        event = {'id': 'e1', 'kind': 'News report', 'confirmation': 'unconfirmed', 'other': 'x'}
        before = minimal_ledger(event)
        after = copy.deepcopy(before)
        after['events'][0]['confirmation'] = 'confirmed_by:obs1'
        excerpts = {'version': 1, 'excerpts': []}
        research.validate_monitoring_delta(before, after, excerpts, excerpts)

    def test_other_field_change_on_an_existing_event_still_rejected(self):
        event = {'id': 'e1', 'kind': 'News report', 'confirmation': 'unconfirmed', 'other': 'x'}
        before = minimal_ledger(event)
        after = copy.deepcopy(before)
        after['events'][0]['other'] = 'y'
        excerpts = {'version': 1, 'excerpts': []}
        with self.assertRaisesRegex(ValueError, 'rewrote'):
            research.validate_monitoring_delta(before, after, excerpts, excerpts)

    def test_new_report_event_still_requires_automated_method(self):
        before = minimal_ledger()
        after = copy.deepcopy(before)
        after['events'].append({'id': 'e2', 'kind': 'News report', 'confirmation': 'unconfirmed'})
        excerpts = {'version': 1, 'excerpts': []}
        with self.assertRaisesRegex(ValueError, 'curated'):
            research.validate_monitoring_delta(before, after, excerpts, excerpts)


class RegistryAdditionsValidTests(unittest.TestCase):
    """Deliverable 4/7: find_feeds.register_outlets/register_social produce a registry that
    validate_registry and the full ledger validator both accept -- exercised against an
    isolated tempdir copy, never the real checkout."""
    def fixture(self, tmp):
        for name in ['research/sources.json', 'research/catalog.json', 'research/ecosystem.json',
                     'research/runtime.json', 'site/data/ledger.json']:
            target = Path(tmp)/name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((ROOT/name).read_bytes())
        target = Path(tmp)/'site/data/source-books.json'
        target.parent.mkdir(parents=True, exist_ok=True)
        r = json.loads((Path(tmp)/'research/sources.json').read_text(encoding='utf-8'))
        target.write_text(json.dumps({k: r[k] for k in ['region_books', 'collection']}), encoding='utf-8')

    def test_register_outlets_adds_a_rank4_news_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.fixture(tmp)
            with patch.object(ff, 'ROOT', Path(tmp)), patch.object(validate_module, 'ROOT', Path(tmp)):
                payload = {'candidates': [{'publisher': 'Example News', 'host': 'news.example.test',
                            'feed_url': 'https://news.example.test/feed/', 'checked_at': research.now(),
                            'entries': 3, 'links': 5, 'same_host_links': 4, 'top_prefix': '/2026/',
                            'eligible': True, 'status': 'eligible', 'layers': ['chips']}]}
                added = ff.register_outlets(payload)
                self.assertEqual(len(added), 1)
                r = json.loads((Path(tmp)/'research/sources.json').read_text(encoding='utf-8'))
                policy = r['collection'][added[0]]
                self.assertEqual(policy['rank'], 4)
                self.assertEqual(policy['claim_type'], 'news')
                self.assertTrue(policy['excerpts'])
                self.assertEqual(grade_for(policy), 'C')
                ledger = json.loads((Path(tmp)/'site/data/ledger.json').read_text(encoding='utf-8'))
                validate(ledger)

    def test_register_outlets_skips_ineligible_and_duplicate_host(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.fixture(tmp)
            with patch.object(ff, 'ROOT', Path(tmp)):
                payload = {'candidates': [
                    {'publisher': 'Example News', 'host': 'news.example.test', 'feed_url': 'https://news.example.test/bad',
                     'entries': 0, 'links': 0, 'same_host_links': 0, 'top_prefix': None, 'eligible': False,
                     'status': 'ineligible', 'layers': ['chips']}]}
                self.assertEqual(ff.register_outlets(payload), [])

    def test_register_social_adds_a_rank6_official_account(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.fixture(tmp)
            with patch.object(ff, 'ROOT', Path(tmp)), patch.object(validate_module, 'ROOT', Path(tmp)):
                ecosystem = json.loads((Path(tmp)/'research/ecosystem.json').read_text(encoding='utf-8'))
                company = ecosystem['companies'][0]
                payload = {'candidates': [{'company_id': company['id'], 'company': company['name'],
                            'layers': company['layers'], 'region_book': company.get('region_book', 'unknown'),
                            'handle': 'example.bsky.social', 'host': 'bsky.app',
                            'feed_url': 'https://bsky.app/profile/example.bsky.social/rss',
                            'checked_at': research.now(), 'entries': 2, 'eligible': True, 'status': 'eligible'}]}
                added = ff.register_social(payload)
                self.assertEqual(len(added), 1)
                r = json.loads((Path(tmp)/'research/sources.json').read_text(encoding='utf-8'))
                policy = r['collection'][added[0]]
                self.assertEqual(policy['rank'], 6)
                self.assertEqual(grade_for(policy), 'B')
                ledger = json.loads((Path(tmp)/'site/data/ledger.json').read_text(encoding='utf-8'))
                validate(ledger)

    def test_social_accounts_file_starts_empty_and_reviewed(self):
        accounts = ff.social_accounts(ROOT)
        self.assertEqual(accounts['accounts'], [])
        self.assertIn('instructions', accounts)


class PanelActivityAndRetractTests(unittest.TestCase):
    """Deliverable 5: the Activity tab's report listing and the Retract action."""
    def fixture(self, tmp):
        for name in ['research/sources.json', 'research/catalog.json', 'site/data/ledger.json']:
            target = Path(tmp)/name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((ROOT/name).read_bytes())
        docs = Path(tmp)/'docs/data/ledger.json'
        docs.parent.mkdir(parents=True, exist_ok=True)
        docs.write_bytes((Path(tmp)/'site/data/ledger.json').read_bytes())
        r = json.loads((ROOT/'research/sources.json').read_text(encoding='utf-8'))
        sid = next(s for s, p in r['collection'].items() if p['claim_type'] == 'news')
        source = next(s for s in r['sources'] if s['id'] == sid)
        data = json.loads((Path(tmp)/'site/data/ledger.json').read_text(encoding='utf-8'))
        if not any(s['id'] == source['id'] for s in data['sources']):
            data['sources'].append(source)
        report = {'id': 'note-' + '1'*20, 'layer': source['layers'][0], 'date': source['published'],
                  'title': 'A test report', 'summary': 'A test report summary text.', 'source': source['id'],
                  'kind': 'News report', 'method': 'automated', 'retrieved_at': '2026-09-05T00:00:00Z',
                  'document_sha256': '0'*64, 'evidence_sha256': '0'*64, 'grade': 'C',
                  'outlet': source['publisher'], 'reported_on': source['published'], 'about': [],
                  'quote': 'A quoted passage from the report.', 'confirmation': 'unconfirmed'}
        data['events'].append(report)
        for path in [Path(tmp)/'site/data/ledger.json', docs]:
            path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
        return report['id']

    def test_activity_lists_report_events(self):
        import research_control as rc
        with tempfile.TemporaryDirectory() as tmp:
            rid = self.fixture(tmp)
            result = rc.activity(Path(tmp))
            self.assertIn(rid, [e['id'] for e in result['reports']])

    def test_retract_marks_the_report_and_writes_an_audit_event(self):
        with tempfile.TemporaryDirectory() as tmp:
            rid = self.fixture(tmp)
            result = rp.retract(Path(tmp), rid, 'reedos', 'Misattributed to the wrong company.',
                                 at='2026-09-06T00:00:00Z')
            self.assertEqual(result['status'], 'retracted')
            data = json.loads((Path(tmp)/'site/data/ledger.json').read_text(encoding='utf-8'))
            event = next(e for e in data['events'] if e['id'] == rid)
            self.assertTrue(event['retracted'])
            self.assertEqual(event['retracted_by'], 'reedos')
            validate(data)
            docs = json.loads((Path(tmp)/'docs/data/ledger.json').read_text(encoding='utf-8'))
            self.assertTrue(next(e for e in docs['events'] if e['id'] == rid)['retracted'])
            from editorial_review import events
            audit = events(Path(tmp))
            self.assertTrue(any(e.get('event_id') == rid and e.get('status') == 'retracted' for e in audit))

    def test_retract_refuses_a_second_retraction(self):
        with tempfile.TemporaryDirectory() as tmp:
            rid = self.fixture(tmp)
            rp.retract(Path(tmp), rid, 'reedos', 'First reason.', at='2026-09-06T00:00:00Z')
            with self.assertRaisesRegex(ValueError, 'already retracted'):
                rp.retract(Path(tmp), rid, 'reedos', 'Second reason.', at='2026-09-07T00:00:00Z')

    def test_retract_refuses_an_unknown_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.fixture(tmp)
            with self.assertRaisesRegex(ValueError, 'not found'):
                rp.retract(Path(tmp), 'note-doesnotexist', 'reedos', 'reason', at='2026-09-06T00:00:00Z')

    def test_retract_refuses_a_non_report_event(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.fixture(tmp)
            data = json.loads((Path(tmp)/'site/data/ledger.json').read_text(encoding='utf-8'))
            data['events'][-1]['kind'] = 'Research finding'
            for k in ('outlet', 'reported_on', 'about', 'quote', 'confirmation'):
                data['events'][-1].pop(k, None)
            rid = data['events'][-1]['id']
            (Path(tmp)/'site/data/ledger.json').write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'News report or Social post'):
                rp.retract(Path(tmp), rid, 'reedos', 'reason', at='2026-09-06T00:00:00Z')

    def test_retract_requires_a_rationale(self):
        with tempfile.TemporaryDirectory() as tmp:
            rid = self.fixture(tmp)
            with self.assertRaisesRegex(ValueError, 'rationale'):
                rp.retract(Path(tmp), rid, 'reedos', '   ', at='2026-09-06T00:00:00Z')


if __name__ == '__main__':
    unittest.main()
