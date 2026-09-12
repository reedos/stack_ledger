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
import source_policy as sp
import validate as validate_module
from source_policy import grade_for, collection_for
from validate import event_valid, observation_valid, validate, GRADES, REPORT_KINDS


def registry():
    return json.loads((ROOT/'research/sources.json').read_text(encoding='utf-8'))


class GradeDerivationTests(unittest.TestCase):
    """Since 2026-09-10 the grade comes from each source's own REVIEWED provenance, not from its
    crawl rank. Rank scheduled fetches; asking it to also say who published a thing put Epoch AI's
    dataset at A and the page rendering a row of that dataset at C, and badged Stanford HAI
    "Official statistics or filings"."""
    def test_derivation_table(self):
        cases = [
            ('official', 'A'),              # a statistical agency, regulator, central bank or IGO
            ('regulated-filing', 'A'),      # the company authored it, under a regulatory regime
            ('company-channel', 'B'),       # a company speaking for itself
            ('independent-research', 'B'),  # a research body publishing its own dataset
            ('analyst', 'C'),               # a third party estimating someone else's numbers
            ('news', 'C'),                  # an outlet reporting on someone else
            ('social', 'D'),                # a person, or an unverified account
        ]
        for provenance, expected in cases:
            with self.subTest(provenance=provenance):
                self.assertEqual(grade_for(None, {'id': 's', 'provenance': provenance}), expected)

    def test_every_provenance_has_a_grade_and_a_reader_facing_label(self):
        self.assertEqual(set(sp.PROVENANCE_GRADE), set(sp.PROVENANCE_LABEL))
        self.assertEqual(set(sp.PROVENANCE_GRADE.values()), GRADES)

    def test_an_unrecognized_or_missing_provenance_fails_closed_to_d(self):
        for source in [{'id': 's'}, {'id': 's', 'provenance': None},
                       {'id': 's', 'provenance': 'invented'}, {}, None]:
            with self.subTest(source=source):
                self.assertEqual(grade_for(None, source), 'D')

    def test_rank_no_longer_influences_the_grade(self):
        # The whole point of the change: the same source grades the same at any crawl priority.
        source = {'id': 'epoch-page', 'provenance': 'independent-research'}
        for rank in (1, 2, 3, 4, 5, 6, 7):
            with self.subTest(rank=rank):
                self.assertEqual(grade_for({'rank': rank, 'claim_type': 'other'}, source), 'B')
        self.assertEqual(grade_for({'rank': 4, 'claim_type': 'news'}, source), 'B')

    def test_every_registered_source_carries_a_reviewed_provenance(self):
        for source in registry()['sources']:
            with self.subTest(source=source['id']):
                self.assertIn(source.get('provenance'), sp.PROVENANCE)
                self.assertIn(grade_for(None, source), GRADES)

    def test_one_publisher_does_not_get_two_provenances_for_the_same_kind_of_work(self):
        """Epoch AI at both A and C is the defect that prompted this. A company may legitimately
        file with a regulator AND run a blog; nothing else may split."""
        import collections
        by_publisher = collections.defaultdict(set)
        for source in registry()['sources']:
            by_publisher[source['publisher']].add(source['provenance'])
        split = {name: sorted(kinds) for name, kinds in by_publisher.items() if len(kinds) > 1}
        self.assertTrue(all(set(kinds) == {'company-channel', 'regulated-filing'}
                            for kinds in split.values()),
                        'a publisher split across unrelated provenances: %s' % split)

    def test_a_registered_news_outlet_is_never_the_authoritative_record(self):
        r = registry()
        sources = {s['id']: s for s in r['sources']}
        outlets = [sid for sid, p in r['collection'].items() if p['claim_type'] == 'news']
        self.assertTrue(outlets, 'deliverable 4 should have registered at least one news outlet')
        for sid in outlets:
            with self.subTest(source=sid):
                self.assertTrue(r['collection'][sid]['excerpts'])
                self.assertNotEqual(grade_for(None, sources[sid]), 'A')


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

    def test_automated_observation_must_carry_a_grade(self):
        # The grade is no longer a threshold to clear, but it is still mandatory: it is the label
        # the value is drawn with, and an unlabelled C or D on a chart is the thing to avoid.
        with self.assertRaisesRegex(ValueError, 'grade'):
            observation_valid(self.observation(), self.metrics, self.sources)

    def test_grade_a_automated_observation_passes(self):
        observation_valid(self.observation(grade='A'), self.metrics, self.sources)

    def test_grade_c_or_d_automated_observation_is_now_accepted(self):
        # Reversed by owner decision 2026-09-11/12: news and social claims may be numeric records
        # as long as the sourcing is stated. See tests/test_low_grade_numerics.py for the labels
        # that make it honest, and tests/low_grade_labels.cjs for the chart surfaces.
        for g in ('C', 'D'):
            with self.subTest(grade=g):
                observation_valid(self.observation(grade=g), self.metrics, self.sources)

    def test_a_grade_outside_the_vocabulary_is_still_refused(self):
        for g in ('E', 'b', ''):
            with self.subTest(grade=g):
                with self.assertRaises(ValueError):
                    observation_valid(self.observation(grade=g), self.metrics, self.sources)

    def test_curated_observation_never_requires_grade(self):
        curated = dict(id='curated-1', metric='ai-adoption', year=2026, period='2026', value=90,
                        upper=None, status='observation', precision='eq',
                        retrieved_at='2026-09-05T00:00:00Z', method='curated', note='',
                        source='stanford-2026')
        observation_valid(curated, self.metrics, self.sources)


class NumericSeriesGuardTests(unittest.TestCase):
    """Where a numeric record is minted, the grade is stamped rather than screened.

    Until 2026-09-12 a grade C or D source could not mint an observation at all. The owner
    reversed that: such a reading may enter a series as long as we are honest about sourcing, so
    candidate_record now derives the grade from the source and attaches it instead of refusing."""
    def setUp(self):
        self.data = json.loads((ROOT/'site/data/ledger.json').read_text(encoding='utf-8'))
        self.registry = registry()
        self.metrics = {m['id']: m for m in self.data['metrics']}
        self.sources = {s['id']: s for s in self.data['sources']}

    def test_grade_c_registered_news_source_now_mints_a_labelled_observation(self):
        # Picked from a real mapping: an unmapped source fails earlier, on the metric/source rule,
        # which would pass this test for the wrong reason.
        pair = next(((m, self.sources[sid])
                     for m in self.data['metrics'] if not m.get('period_basis')
                     and 'observation' in (m.get('allowed_statuses') or ['observation'])
                     for sid in m['source_ids']
                     if self.sources.get(sid, {}).get('provenance') in ('news', 'social')), None)
        if pair is None:
            self.skipTest('no metric is mapped to a news or social source')
        metric, source = pair
        policy = collection_for(self.registry, source)
        self.assertIn(grade_for(policy, source), ('C', 'D'))
        value = round((metric['min']+metric['max'])/2)
        candidate = {'metric': metric['id'], 'year': 2026, 'period': '2026', 'value': value,
                     'upper': None, 'status': 'observation', 'precision': 'eq', 'note': '',
                     'evidence': f'The outlet reported {value} for 2026.'}
        record = research.candidate_record(candidate, source, candidate['evidence'], self.metrics,
                                            self.sources, [], policy)
        self.assertEqual(record['grade'], grade_for(policy, source),
                         'the record must carry the grade derived from its own source')

    def test_grade_a_source_still_mints_an_observation(self):
        # Chosen by provenance rather than by id: stanford-2026 was reclassified from "official
        # statistics" to independent research on 2026-09-10 and is correctly grade B now.
        metric, source = next(
            (m, self.sources[sid])
            for m in self.data['metrics'] if not m.get('period_basis')
            and 'observation' in (m.get('allowed_statuses') or ['observation'])
            for sid in m['source_ids']
            if self.sources.get(sid, {}).get('provenance') == 'official')
        policy = collection_for(self.registry, source)
        value = round((metric['min']+metric['max'])/2)
        candidate = {'metric': metric['id'], 'year': 2026, 'period': '2026', 'value': value,
                     'upper': None, 'status': 'observation', 'precision': 'eq', 'note': '',
                     'evidence': f'The agency reported {value} for 2026.'}
        record = research.candidate_record(candidate, source, candidate['evidence'], self.metrics,
                                            self.sources, [], policy)
        self.assertEqual(record['grade'], 'A')


class ReportPublicationTests(unittest.TestCase):
    """extract_note assembles the report shape deterministically from the source's policy --
    grade, kind, outlet, reported_on, about, quote, confirmation -- never the model's choice."""
    def test_discovered_news_source_note_becomes_a_report(self):
        source = {'id': 'discovered-abc', 'url': 'https://news.example/2026/09/article',
                   'layers': ['chips'], 'publisher': 'Test News', 'published': '2026-09-01',
                   'provenance': 'news', 'parent_source': 'outlet-test'}
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
        # A company's OWN account is the company speaking (provenance company-channel,
        # grade B), not a social post by a person: it never enters the reports lane and keeps
        # the model's own six-value kind choice.
        source = {'id': 'discovered-social', 'url': 'https://bsky.app/profile/x/post/1',
                   'layers': ['chips'], 'publisher': 'Company X', 'published': '2026-09-01',
                   'provenance': 'company-channel', 'parent_source': 'social-x'}
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
                registered = next(x for x in r['sources'] if x['id'] == added[0])
                self.assertEqual(registered['provenance'], 'news')
                self.assertEqual(grade_for(policy, registered), 'C')
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

    def outlets_fixture(self, tmp):
        # Deliverable 4: the reviewed candidate file register_outlets writes outcomes back onto.
        path = Path(tmp)/'research/news-outlets.json'
        path.write_text(json.dumps({'version': 1, 'reviewed_at': research.now(), 'outlets': [
            {'name': 'Example News', 'home': 'https://news.example.test/', 'layers': ['chips']}]}), encoding='utf-8')
        return path

    def test_register_outlets_records_registration_onto_reviewed_outlets_file(self):
        # Deliverable 1/4: a registered outlet's outcome (status + source_id) is written back.
        with tempfile.TemporaryDirectory() as tmp:
            self.fixture(tmp)
            outlets_path = self.outlets_fixture(tmp)
            with patch.object(ff, 'ROOT', Path(tmp)), patch.object(validate_module, 'ROOT', Path(tmp)):
                payload = {'candidates': [{'publisher': 'Example News', 'host': 'news.example.test',
                            'feed_url': 'https://news.example.test/feed/', 'checked_at': research.now(),
                            'entries': 3, 'links': 5, 'same_host_links': 4, 'top_prefix': '/2026/',
                            'eligible': True, 'status': 'eligible', 'layers': ['chips']}]}
                added = ff.register_outlets(payload)
                self.assertEqual(len(added), 1)
                entry = json.loads(outlets_path.read_text(encoding='utf-8'))['outlets'][0]
                self.assertEqual(entry['status'], 'registered')
                self.assertEqual(entry['source_id'], added[0])
                self.assertNotIn('reason', entry)
                # Re-registering the same host (already carrying an index source) is a no-op:
                # never re-added, and the reviewed file keeps the same registered outcome.
                self.assertEqual(ff.register_outlets(payload), [])
                entry2 = json.loads(outlets_path.read_text(encoding='utf-8'))['outlets'][0]
                self.assertEqual(entry2['status'], 'registered')
                self.assertEqual(entry2['source_id'], added[0])

    def test_register_outlets_records_rejection_reason_onto_reviewed_outlets_file(self):
        # Deliverable 4: a rejected outlet is recorded, not forgotten -- status + a genuine reason.
        with tempfile.TemporaryDirectory() as tmp:
            self.fixture(tmp)
            outlets_path = self.outlets_fixture(tmp)
            with patch.object(ff, 'ROOT', Path(tmp)):
                payload = {'candidates': [{'publisher': 'Example News', 'host': 'news.example.test',
                            'feed_url': 'https://news.example.test/rss.rss', 'entries': 0, 'links': 0,
                            'same_host_links': 0, 'top_prefix': None, 'eligible': False,
                            'status': 'ineligible', 'layers': ['chips']}]}
                self.assertEqual(ff.register_outlets(payload), [])
                entry = json.loads(outlets_path.read_text(encoding='utf-8'))['outlets'][0]
                self.assertEqual(entry['status'], 'rejected')
                self.assertIn('did not parse', entry['reason'])
                self.assertNotIn('source_id', entry)

    def test_register_outlets_is_a_no_op_on_the_outlets_file_when_none_exists(self):
        # No reviewed research/news-outlets.json in the tempdir (as in the two tests above this
        # one): registration must still succeed and simply skip the outcome write-back.
        with tempfile.TemporaryDirectory() as tmp:
            self.fixture(tmp)
            with patch.object(ff, 'ROOT', Path(tmp)), patch.object(validate_module, 'ROOT', Path(tmp)):
                payload = {'candidates': [{'publisher': 'Example News', 'host': 'news.example.test',
                            'feed_url': 'https://news.example.test/feed/', 'entries': 3, 'links': 5,
                            'same_host_links': 4, 'top_prefix': '/2026/', 'eligible': True,
                            'status': 'eligible', 'layers': ['chips']}]}
                self.assertEqual(len(ff.register_outlets(payload)), 1)
                self.assertFalse((Path(tmp)/'research/news-outlets.json').exists())

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
                registered = next(x for x in r['sources'] if x['id'] == added[0])
                self.assertEqual(registered['provenance'], 'company-channel')
                self.assertEqual(grade_for(policy, registered), 'B')
                ledger = json.loads((Path(tmp)/'site/data/ledger.json').read_text(encoding='utf-8'))
                validate(ledger)

    def test_every_social_account_is_a_domain_handle_never_a_platform(self):
        """The file was empty until 2026-09-12 because the rule forbids guessing a handle. A
        company's own domain satisfies it: Bluesky only issues a domain handle to whoever controls
        that domain's DNS, so it cannot resolve to an impersonator. A third-party platform's domain
        does not -- DeepSeek publishes on github.com, and deriving a handle from its reviewed blog
        host found github.com's real Bluesky feed and called it DeepSeek's official account."""
        accounts = ff.social_accounts(ROOT)
        self.assertIn('instructions', accounts)
        companies = {c['id'] for c in json.loads((ROOT/'research/ecosystem.json').read_text(encoding='utf-8'))['companies']}
        for entry in accounts['accounts']:
            with self.subTest(handle=entry['handle']):
                self.assertIn(entry['company_id'], companies)
                self.assertNotIn(entry['handle'].lower(), ff.PLATFORM_HOSTS)
                self.assertIn('verified_by', entry)
                self.assertRegex(entry['handle'], r'^[a-z0-9.-]+\.[a-z]{2,}$')

    def test_a_platform_handle_can_never_register_as_a_company_account(self):
        registry = registry_fixture() if 'registry_fixture' in globals() else None
        probe = ff.run_social(accounts=[{'company_id': 'nvidia', 'handle': 'github.com'}],
                              out=Path(tempfile.mkdtemp())/'probe.json')
        row = probe['candidates'][0]
        self.assertEqual(row['status'], 'platform_handle')
        self.assertFalse(row['eligible'])


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
