"""The workforce survey must show the answer the source calls primary.

Until 2026-09-11 the chart titled "How AI-using service firms changed staffing" plotted layoffs,
more hiring and less hiring, and mentioned retraining only in a footnote -- although retraining is
the largest category and the New York Fed's own summary is that "retraining employees in response
to AI remains the primary way firms are adjusting their workforces." A reader saw a chart that
looked like AI mostly means fewer hires, under a headline that says the opposite.

The source states retraining as "just over a third" with no exact percentage, so it publishes as a
floor rather than an invented digit.
"""
import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from render_claims import survey_value


def survey():
    return json.loads((ROOT/'research/claims.json').read_text(encoding='utf-8'))['employment_context']['survey']


class SurveyContentTests(unittest.TestCase):
    def test_retraining_is_on_the_chart(self):
        labels = [p['label'] for p in survey()['points']]
        self.assertTrue(any('etrain' in l for l in labels), 'retraining must be a plotted category: %s' % labels)

    def test_retraining_is_the_largest_category_and_is_shown_first(self):
        points = survey()['points']
        retraining = next(p for p in points if 'etrain' in p['label'])
        self.assertEqual(points[0], retraining, 'the largest answer leads, as the source does')
        self.assertEqual(retraining['value'], max(p['value'] for p in points))

    def test_it_publishes_as_a_floor_because_the_source_gives_no_exact_figure(self):
        retraining = next(p for p in survey()['points'] if 'etrain' in p['label'])
        self.assertEqual(retraining.get('precision'), 'gt')
        self.assertEqual(survey_value(retraining), 'more than 33%')

    def test_the_title_describes_what_the_survey_actually_asked(self):
        title = survey()['title']
        self.assertNotIn('changed staffing', title,
                         'retraining is a workforce adjustment, not a staffing level change')
        self.assertIn('workforce', title.lower())

    def test_the_note_says_why_the_number_is_loose(self):
        self.assertIn('just over a third', survey()['note'])

    def test_the_published_mirror_matches_the_reviewed_file(self):
        self.assertEqual(json.loads((ROOT/'research/claims.json').read_text(encoding='utf-8')),
                         json.loads((ROOT/'site/data/claims.json').read_text(encoding='utf-8')))


class PrecisionRenderingTests(unittest.TestCase):
    def test_each_reviewed_precision_reads_as_itself(self):
        self.assertEqual(survey_value({'label': 'x', 'value': 15}), '15%')
        self.assertEqual(survey_value({'label': 'x', 'value': 15, 'precision': 'eq'}), '15%')
        self.assertEqual(survey_value({'label': 'x', 'value': 33, 'precision': 'gt'}), 'more than 33%')
        self.assertEqual(survey_value({'label': 'x', 'value': 34, 'precision': 'approx'}), 'about 34%')

    def test_an_unreviewed_precision_never_reaches_the_page(self):
        from validate_claims import validate_claims as check
        sources = {s['id'] for s in json.loads((ROOT/'site/data/ledger.json').read_text(encoding='utf-8'))['sources']}
        data = json.loads((ROOT/'research/claims.json').read_text(encoding='utf-8'))
        check(data, sources)                     # the reviewed file passes as it stands
        data['employment_context']['survey']['points'][0]['precision'] = 'invented'
        with self.assertRaisesRegex(ValueError, 'precision'):
            check(data, sources)

    def test_a_point_may_not_carry_an_unknown_field(self):
        from validate_claims import validate_claims as check
        sources = {s['id'] for s in json.loads((ROOT/'site/data/ledger.json').read_text(encoding='utf-8'))['sources']}
        data = json.loads((ROOT/'research/claims.json').read_text(encoding='utf-8'))
        data['employment_context']['survey']['points'][0]['footnote'] = 'smuggled'
        with self.assertRaisesRegex(ValueError, 'survey point'):
            check(data, sources)


@unittest.skipUnless(shutil.which('node'), 'node is not installed')
class DisclosureJsTests(unittest.TestCase):
    """A collapsed section showed its title twice, once as the summary and once inside."""
    def test_node_test_passes(self):
        result = subprocess.run(['node', '--test', 'tests/disclosure.cjs'], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
