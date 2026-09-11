"""Provenance is reviewed per source, and it is what every published number is labelled with.

Until 2026-09-10 the grade was derived from a source's crawl `rank`. Rank schedules fetches; asking
it to also say who published a thing produced labels that were wrong on the live site: Epoch AI
graded A on its dataset and C on the page rendering a row of that same dataset, Stanford HAI badged
"Official statistics or filings", FERC and two Federal Reserve banks badged "Company statement",
grade D unreachable while three social sources read as company statements.

These tests pin the corrections and the invariants that keep them from drifting back.
"""
import collections
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import source_policy as sp
from source_policy import grade_for
from validate import GRADES


def registry():
    return json.loads((ROOT/'research/sources.json').read_text(encoding='utf-8'))


def ledger():
    return json.loads((ROOT/'site/data/ledger.json').read_text(encoding='utf-8'))


class TaxonomyTests(unittest.TestCase):
    def test_the_letter_is_derived_only_from_the_provenance(self):
        for provenance, grade in sp.PROVENANCE_GRADE.items():
            with self.subTest(provenance=provenance):
                self.assertEqual(grade_for(None, {'id': 's', 'provenance': provenance}), grade)
                self.assertIn(grade, GRADES)

    def test_every_category_is_reader_facing(self):
        self.assertEqual(set(sp.PROVENANCE_LABEL), sp.PROVENANCE)
        for label in sp.PROVENANCE_LABEL.values():
            self.assertTrue(label and label[0].isupper(), label)

    def test_a_source_that_cannot_say_who_published_it_fails_closed(self):
        self.assertEqual(grade_for(None, {'id': 's'}), 'D')
        self.assertEqual(grade_for({'rank': 1}, {'id': 's'}), 'D')


class RegistryTests(unittest.TestCase):
    def test_every_registered_source_carries_a_reviewed_provenance(self):
        for source in registry()['sources']:
            with self.subTest(source=source['id']):
                self.assertIn(source.get('provenance'), sp.PROVENANCE)

    def test_every_published_source_carries_one_too(self):
        for source in ledger()['sources']:
            with self.subTest(source=source['id']):
                self.assertIn(source.get('provenance'), sp.PROVENANCE)

    def test_the_ledger_and_the_registry_agree(self):
        approved = {s['id']: s.get('provenance') for s in registry()['sources']}
        for source in ledger()['sources']:
            if source['id'] in approved:
                with self.subTest(source=source['id']):
                    self.assertEqual(source['provenance'], approved[source['id']])

    def test_a_discovered_child_inherits_its_parent(self):
        sources = {s['id']: s for s in ledger()['sources']}
        children = [s for s in sources.values() if s.get('parent_source')]
        self.assertTrue(children, 'the ledger should carry at least one discovered child')
        for child in children:
            parent = sources.get(child['parent_source'])
            if parent:
                with self.subTest(source=child['id']):
                    self.assertEqual(child['provenance'], parent['provenance'],
                                     'a discovered page has the same publisher as its parent')


class CorrectionTests(unittest.TestCase):
    """The specific wrong labels that prompted the change. Named, so a regression says which."""
    def by_publisher(self, needle):
        return [s for s in registry()['sources'] if needle.lower() in (s.get('publisher') or '').lower()]

    def test_one_research_organisation_gets_one_provenance(self):
        epoch = self.by_publisher('Epoch AI')
        self.assertGreaterEqual(len(epoch), 10)
        self.assertEqual({s['provenance'] for s in epoch}, {'independent-research'})

    def test_a_university_institute_is_not_official_statistics(self):
        for source in self.by_publisher('Stanford'):
            with self.subTest(source=source['id']):
                self.assertEqual(source['provenance'], 'independent-research')
                self.assertEqual(grade_for(None, source), 'B')

    def test_regulators_and_statistical_agencies_are_official(self):
        for needle in ['Bureau of Labor Statistics', 'Federal Energy Regulatory',
                       'Reserve Bank', 'Public Utilities Commission', 'Environmental Quality']:
            found = self.by_publisher(needle)
            self.assertTrue(found, 'expected a registered %s source' % needle)
            for source in found:
                with self.subTest(source=source['id']):
                    self.assertEqual(source['provenance'], 'official')
                    self.assertEqual(grade_for(None, source), 'A')

    def test_a_persons_post_is_social_and_a_companys_account_is_not(self):
        sources = {s['id']: s for s in registry()['sources']}
        self.assertEqual(sources['water-altman']['provenance'], 'social')          # a personal blog
        self.assertEqual(sources['waymo-paid-march-2026']['provenance'], 'social')  # a named person's post
        self.assertEqual(sources['waymo-paid-march-post']['provenance'], 'company-channel')

    def test_grade_d_is_reachable_at_all(self):
        """It was advertised in the legend and derived by nothing."""
        live = [s for s in registry()['sources'] if grade_for(None, s) == 'D']
        self.assertTrue(live, 'grade D must describe real sources or not be offered')


class ConsistencyTests(unittest.TestCase):
    def test_a_publisher_splits_only_between_its_filings_and_its_own_channel(self):
        by_publisher = collections.defaultdict(set)
        for source in registry()['sources']:
            by_publisher[source['publisher']].add(source['provenance'])
        split = {name: sorted(k) for name, k in by_publisher.items() if len(k) > 1}
        for name, kinds in split.items():
            with self.subTest(publisher=name):
                self.assertEqual(set(kinds), {'company-channel', 'regulated-filing'})

    def test_every_source_built_in_code_declares_a_provenance(self):
        """An importer that registers a source without one fails validation at apply time, in the
        middle of the night, after it has already written data."""
        pattern = re.compile(r"\{[^{}]*'publisher'\s*:[^{}]*'license'\s*:[^{}]*\}", re.S)
        offenders = []
        for path in sorted((ROOT/'scripts').glob('*.py')):
            body = path.read_text(encoding='utf-8')
            for match in pattern.finditer(body):
                if "'provenance'" not in match.group(0):
                    offenders.append('%s: %s' % (path.name, match.group(0)[:70]))
        self.assertEqual(offenders, [], 'source dicts with no provenance: %s' % offenders)


if __name__ == '__main__':
    unittest.main()
