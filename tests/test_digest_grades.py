"""An unattended night has to say which evidence grades it published.

From 2026-09-12 the model may mint a grade C or D numeric observation, on the condition that the
sourcing is stated. The nightly digest is the only thing the owner reads afterwards, and it
reported commit subjects -- "research: daily ledger" -- with nothing about the grades inside them.

Driven against a throwaway repository. Running the real orchestrator against the live checkout
has twice overwritten a genuine nightly receipt.
"""
import datetime
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import nightly

_NOW = datetime.datetime.now(datetime.timezone.utc).date()
TODAY = _NOW.isoformat()
YESTERDAY = (_NOW - datetime.timedelta(days=1)).isoformat()


def metric(mid='m', title='A measured thing'):
    return {'id': mid, 'title': title, 'layer': 'chips', 'min': 0, 'max': 1000}


def observation(oid, source, grade, value=5, mid='m'):
    return {'id': oid, 'metric': mid, 'year': 2026, 'period': '2026', 'value': value, 'upper': None,
            'status': 'observation', 'source': source, 'precision': 'eq', 'method': 'automated',
            'retrieved_at': '2026-09-12T00:00:00+00:00', 'note': '', 'grade': grade}


SOURCES = [
    {'id': 'agency', 'publisher': 'Bureau of Labor Statistics', 'provenance': 'official'},
    {'id': 'desk', 'publisher': 'SemiAnalysis', 'provenance': 'analyst'},
    {'id': 'wire', 'publisher': 'Associated Press · Kraków', 'provenance': 'news'},
]


class ThrowawayRepo:
    def __init__(self, ledger):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root/'site/data').mkdir(parents=True)
        self.write(ledger)
        self.git('init', '-q')
        self.git('config', 'user.email', 'test@example.com')
        self.git('config', 'user.name', 'Test')
        self.git('add', '-A')
        # Dated before today, so the day under test has a parent commit to diff against -- the
        # real shape of a night. The root-commit case has its own test.
        self.git('commit', '-q', '-m', 'baseline', when=YESTERDAY+' 12:00:00 +0000')

    def git(self, *args, when=None):
        import os
        env = dict(os.environ)
        if when:
            env['GIT_AUTHOR_DATE'] = env['GIT_COMMITTER_DATE'] = when
        subprocess.run(['git', *args], cwd=self.root, capture_output=True, text=True,
                        encoding='utf-8', check=True, env=env)

    def write(self, ledger):
        (self.root/'site/data/ledger.json').write_text(
            json.dumps(ledger, indent=2, ensure_ascii=False), encoding='utf-8')

    def publish(self, ledger, message='research: daily ledger'):
        self.write(ledger)
        self.git('add', '-A')
        self.git('commit', '-q', '--allow-empty', '-m', message)

    def close(self):
        self.tmp.cleanup()


def ledger(observations):
    return {'layers': [], 'metrics': [metric()], 'sources': SOURCES, 'observations': observations,
            'events': []}


class MeasurementTests(unittest.TestCase):
    def report(self, before, after):
        repo = ThrowawayRepo(ledger(before))
        self.addCleanup(repo.close)
        repo.publish(ledger(after))
        return nightly.published_observations(repo.root, TODAY)

    def test_a_night_that_published_nothing_reports_nothing(self):
        r = self.report([], [])
        self.assertEqual(r.get('new_observations'), 0)
        self.assertEqual(r.get('low_grade'), [])

    def test_grades_are_counted(self):
        r = self.report([], [observation('a1', 'agency', 'A'),
                             observation('c1', 'desk', 'C', value=7),
                             observation('d1', 'wire', 'C', value=9)])
        self.assertEqual(r['new_observations'], 3)
        self.assertEqual(r['by_grade'], {'A': 1, 'C': 2})

    def test_every_low_grade_reading_is_named_with_its_source(self):
        r = self.report([observation('a1', 'agency', 'A')],
                        [observation('a1', 'agency', 'A'), observation('c1', 'desk', 'C', value=7)])
        self.assertEqual(r['new_observations'], 1, 'the pre-existing reading is not new')
        self.assertEqual(len(r['low_grade']), 1)
        row = r['low_grade'][0]
        self.assertEqual(row['grade'], 'C')
        self.assertEqual(row['label'], 'Analyst or trade estimate')
        self.assertEqual(row['publisher'], 'SemiAnalysis')
        self.assertEqual(row['title'], 'A measured thing')
        self.assertEqual(row['value'], 7)

    def test_a_high_grade_reading_is_counted_but_not_itemised(self):
        """The itemised list is for readings a reader could not have had before tonight."""
        r = self.report([], [observation('a1', 'agency', 'A')])
        self.assertEqual(r['by_grade'], {'A': 1})
        self.assertEqual(r['low_grade'], [])

    def test_a_non_ascii_ledger_still_measures(self):
        """The regression that made this report an empty night on the day it was written.

        git output was decoded with the platform's ANSI codepage, so a ledger carrying a period
        separator or an accented publisher raised UnicodeDecodeError and the whole report was
        swallowed as {}.
        """
        r = self.report([], [observation('c1', 'wire', 'C', value=3)])
        self.assertEqual(r['new_observations'], 1, 'a non-ASCII publisher must not blank the report')
        self.assertEqual(r['low_grade'][0]['publisher'], 'Associated Press · Kraków')

    def test_a_repository_whose_first_ever_commit_is_today_counts_it_all_as_new(self):
        """There is nothing before the root commit to diff against, and git rejects 'root^'."""
        repo = ThrowawayRepo(ledger([observation('c1', 'desk', 'C')]))
        self.addCleanup(repo.close)
        repo.git('commit', '-q', '--allow-empty', '--amend', '--no-edit')   # re-date it to now
        r = nightly.published_observations(repo.root, TODAY)
        self.assertEqual(r['new_observations'], 1)
        self.assertEqual(r['by_grade'], {'C': 1})

    def test_a_directory_without_git_history_returns_empty_rather_than_raising(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(nightly.published_observations(Path(tmp), TODAY), {})


class RenderingTests(unittest.TestCase):
    def body(self, published):
        return {'date': TODAY, 'applied': [], 'needs_decision': {}, 'site_changes': ['abc123 research'],
                'health': {}, 'stage_receipts': {'research': 'ok'}, 'published_observations': published}

    def test_the_digest_names_each_low_grade_reading(self):
        markdown = nightly.render_digest_markdown(self.body({
            'new_observations': 2, 'by_grade': {'A': 1, 'C': 1},
            'low_grade': [{'observation': 'c1', 'metric': 'm', 'title': 'A measured thing',
                            'period': '2026', 'value': 7, 'grade': 'C',
                            'label': 'Analyst or trade estimate', 'publisher': 'SemiAnalysis'}]}))
        self.assertIn('## Published observations', markdown)
        self.assertIn('2 new: 1 grade A, 1 grade C', markdown)
        self.assertIn('A measured thing 2026 = 7', markdown)
        self.assertIn('Analyst or trade estimate', markdown)
        self.assertIn('SemiAnalysis', markdown)

    def test_a_quiet_night_adds_no_section(self):
        self.assertNotIn('## Published observations',
                         nightly.render_digest_markdown(self.body({'new_observations': 0, 'by_grade': {}, 'low_grade': []})))

    def test_a_digest_from_before_this_change_still_renders(self):
        """Receipts written by an older nightly have no published_observations key at all."""
        body = self.body({}); body.pop('published_observations')
        self.assertIn('## Site changes', nightly.render_digest_markdown(body))

    def test_the_section_sits_above_the_health_dump_that_telegram_truncates(self):
        markdown = nightly.render_digest_markdown(self.body({
            'new_observations': 1, 'by_grade': {'C': 1},
            'low_grade': [{'observation': 'c1', 'metric': 'm', 'title': 'T', 'period': '2026',
                            'value': 1, 'grade': 'C', 'label': 'News report', 'publisher': 'AP'}]}))
        self.assertLess(markdown.index('## Published observations'), markdown.index('## Health'),
                        'the truncated copy must keep what was published')


if __name__ == '__main__':
    unittest.main()
