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
from render_claims import survey_value, survey_value_html


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


class BarFigureLayoutTests(unittest.TestCase):
    """At the bar's 24px type, "more than 33%" wrapped and made that row twice the height of its
    neighbours. The number stays the large element; the qualifier rides in front of it, small."""
    def test_the_qualifier_is_a_separate_small_element(self):
        html = survey_value_html({'label': 'x', 'value': 33, 'precision': 'gt'})
        self.assertEqual(html, '<span class="qualifier">more than</span>33%')

    def test_a_plain_figure_carries_no_extra_markup(self):
        self.assertEqual(survey_value_html({'label': 'x', 'value': 15}), '15%')
        self.assertEqual(survey_value_html({'label': 'x', 'value': 15, 'precision': 'eq'}), '15%')

    def test_the_figure_is_still_read_as_one_phrase(self):
        import re
        html = survey_value_html({'label': 'x', 'value': 33, 'precision': 'gt'})
        self.assertEqual(re.sub(r'<[^>]+>', ' ', html).split(), ['more', 'than', '33%'])

    def test_the_stylesheet_keeps_the_figure_on_one_line_and_the_qualifier_small(self):
        css = (ROOT/'site/assets/claims.css').read_text(encoding='utf-8')
        self.assertIn('.evidence-bar-row strong{', css)
        rule = css.split('.evidence-bar-row strong{', 1)[1].split('}', 1)[0]
        self.assertIn('white-space:nowrap', rule, 'the figure must never wrap')
        self.assertIn('.evidence-bar-row strong .qualifier{', css)
        qualifier = css.split('.evidence-bar-row strong .qualifier{', 1)[1].split('}', 1)[0]
        self.assertIn('font-size:11px', qualifier)

    def test_the_published_stylesheet_matches_the_source(self):
        self.assertEqual((ROOT/'site/assets/claims.css').read_text(encoding='utf-8'),
                         (ROOT/'docs/assets/claims.css').read_text(encoding='utf-8'))

    def test_the_table_cell_stays_plain_text(self):
        html = (ROOT/'docs/claims/index.html').read_text(encoding='utf-8')
        self.assertIn('<td>more than 33%</td>', html, 'the accessible table needs no markup')


@unittest.skipUnless(shutil.which('node'), 'node is not installed')
class DisclosureJsTests(unittest.TestCase):
    """A collapsed section showed its title twice, once as the summary and once inside."""
    def test_node_test_passes(self):
        result = subprocess.run(['node', '--test', 'tests/disclosure.cjs'], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
