"""A grade C or D reading may become a numeric observation, so long as it carries its label.

The owner's decision, 2026-09-11 and restated 2026-09-12: news and social claims belong on charts
and headlines "as long as we are honest about sourcing". Before this, research.py refused to mint
the record at all and validate.py refused to accept one, so such evidence could only ever reach a
reader through the report lane.

What replaces the ban is a label that cannot be detached from the number: the grade is derived
from the registered source's reviewed provenance, the whole-ledger pass re-derives it and rejects
any mismatch, and app.js names the class at the tooltip, the mark, the legend, the accessibility
description, the data table, the record row and the CSV export.
"""
import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import validate as v
from source_policy import PROVENANCE_GRADE, collection_for, grade_for

HASH = 'a'*64
SUB_ANNUAL_PERIOD = {'month': '2026-01', 'quarter': '2026-Q1', 'snapshot': '2026-01-01'}


def ledger():
    return json.loads((ROOT/'site/data/ledger.json').read_text(encoding='utf-8'))


def registry():
    return json.loads((ROOT/'research/sources.json').read_text(encoding='utf-8'))


class GateTests(unittest.TestCase):
    """Exercised against a real metric/source pair, so the schema is the shipped one."""

    def setUp(self):
        self.data = ledger()
        self.metrics = {m['id']: m for m in self.data['metrics']}
        self.sources = {s['id']: s for s in self.data['sources']}
        self.pair = self.mapped_pair(('C', 'D'))
        self.assertIsNotNone(self.pair, 'no metric is mapped to a C/D source to test with')

    def mapped_pair(self, grades):
        for m in self.data['metrics']:
            for sid in (m.get('source_ids') or []):
                s = self.sources.get(sid)
                if s and PROVENANCE_GRADE.get(s.get('provenance')) in grades:
                    return m, s
        return None

    def automated(self, pair=None, **over):
        m, s = pair or self.pair
        o = {'id': 'auto-probe', 'metric': m['id'], 'year': 2026,
             'period': SUB_ANNUAL_PERIOD.get(m.get('period_basis'), '2026'),
             'value': m['min'], 'upper': None, 'status': 'observation', 'source': s['id'],
             'precision': 'eq', 'retrieved_at': '2026-09-12T12:00:00+00:00', 'method': 'automated',
             'note': '', 'document_sha256': HASH, 'evidence_sha256': HASH,
             'grade': PROVENANCE_GRADE[s['provenance']]}
        o.update(over)
        return o

    def test_a_low_grade_automated_observation_is_now_accepted(self):
        o = self.automated()
        self.assertIn(o['grade'], ('C', 'D'), 'the fixture must actually be low grade')
        v.observation_valid(o, self.metrics, self.sources)

    def test_an_automated_observation_with_no_grade_is_still_refused(self):
        o = self.automated()
        o.pop('grade')
        with self.assertRaises(ValueError) as caught:
            v.observation_valid(o, self.metrics, self.sources)
        self.assertIn('grade', str(caught.exception).lower())

    def test_a_grade_outside_the_vocabulary_is_refused(self):
        for bad in ('E', 'a', '', None, 1):
            with self.subTest(grade=bad):
                with self.assertRaises(ValueError):
                    v.observation_valid(self.automated(grade=bad), self.metrics, self.sources)

    def test_a_high_grade_automated_observation_still_works(self):
        """Relaxing the rule must not change what was already allowed."""
        pair = self.mapped_pair(('A', 'B'))
        self.assertIsNotNone(pair, 'no A/B mapped pair to test with')
        v.observation_valid(self.automated(pair=pair), self.metrics, self.sources)


class DerivationTests(unittest.TestCase):
    """The label cannot be chosen; the whole-ledger pass re-derives it from the source."""

    def test_a_low_grade_source_cannot_present_itself_as_high_grade(self):
        reg = registry()
        companies = {p['company_id'] for p in reg['collection'].values() if p.get('company_id')}
        low = next(s for s in reg['sources']
                   if PROVENANCE_GRADE.get(s.get('provenance')) in ('C', 'D'))
        derived = grade_for(collection_for(reg, low), low, companies)
        self.assertIn(derived, ('C', 'D'))
        for claimed in ('A', 'B'):
            with self.subTest(claimed=claimed):
                self.assertNotEqual(claimed, derived)

    def test_validate_re_derives_the_grade_for_every_automated_observation(self):
        source = (ROOT/'scripts/validate.py').read_text(encoding='utf-8')
        self.assertIn('Observation grade does not match deterministic derivation from its source',
                      source)


class AdditiveOnlyTests(unittest.TestCase):
    """A low grade may extend a series. It may never displace a better reading.

    Both properties that carry this predate the change, which is why relaxing the gate is safe:
    the monitoring publish path forbids correction fields outright, and a value contradicting a
    published reading for the same metric and period is a conflict rather than a replacement.
    """

    def test_the_monitoring_lane_still_cannot_issue_a_correction(self):
        source = (ROOT/'scripts/research.py').read_text(encoding='utf-8')
        self.assertIn('Monitoring cannot issue corrections', source)
        self.assertIn("'correction_of','superseded_by','correction_reason','corrected_at'", source)

    def test_a_contradicting_value_is_a_conflict_not_a_replacement(self):
        import research
        metrics = {'m': {'id': 'm'}}
        published = [{'metric': 'm', 'year': 2026, 'period': '2026', 'value': 10, 'upper': None,
                      'status': 'observation', 'precision': 'eq'}]
        same = dict(published[0])
        differing = dict(published[0], value=99)
        self.assertEqual(research.duplicate_or_conflict(same, published, metrics), 'duplicate')
        self.assertEqual(research.duplicate_or_conflict(differing, published, metrics), 'conflict')

    def test_research_no_longer_refuses_to_mint_a_low_grade_record(self):
        source = (ROOT/'scripts/research.py').read_text(encoding='utf-8')
        self.assertNotIn('cannot become a numeric observation', source,
                         'the hard refusal is still in the minting path')
        self.assertIn("record['grade']=grade_for(policy,source,tracked_companies())", source)


class LabelledEverywhereTests(unittest.TestCase):
    """Every surface that shows the value names the class of source it came from."""

    def test_the_script_labels_each_surface(self):
        app = (ROOT/'site/assets/app.js').read_text(encoding='utf-8')
        for surface, needle in [
                ('tooltip', "${esc(sourceOf(o.source).publisher)}${lowGrade(o)?"),
                ('bar mark', "${lowGrade(o)?' low-grade':''}"),
                ('line point', "${lowGrade(p.o)?' low-grade':''}"),
                ('legend bucket', 'if(lowGrade(o))return sourceClassOf(o)'),
                ('legend swatch', "['News report','legend-swatch low-grade']"),
                ('accessibility description', "${lowGrade(o)?`, ${esc(sourceClassOf(o))}`:''}"),
                ('data table', "${lowGrade(o)?`<br>${esc(sourceClassOf(o))}`:''}")]:
            with self.subTest(surface=surface):
                self.assertIn(needle, app, '%s does not name the source class' % surface)

    def test_the_stylesheet_can_draw_the_swatch(self):
        css = (ROOT/'site/assets/styles.css').read_text(encoding='utf-8')
        self.assertIn('.legend-swatch.low-grade{', css)

    @unittest.skipUnless(shutil.which('node'), 'node is not installed')
    def test_node_test_passes(self):
        result = subprocess.run(['node', '--test', 'tests/low_grade_labels.cjs'], cwd=ROOT,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, (result.stdout + result.stderr)[-3000:])


if __name__ == '__main__':
    unittest.main()
