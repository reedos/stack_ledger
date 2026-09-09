import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import render
import research


class StaticPresentationTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((ROOT / 'site/data/ledger.json').read_text(encoding='utf-8'))

    def test_headline_follows_observed_updates_and_corrections_not_forecasts(self):
        layer = self.data['layers'][0]
        old = render.latest_headline(self.data, layer)
        new = dict(old, id='test-new', year=2026, period='2026', value=501)
        forecast = dict(new, id='test-forecast', year=2030, period='2030', status='forecast', value=950)
        self.data['observations'].extend([new, forecast])
        self.assertEqual(render.latest_headline(self.data, layer)['id'], 'test-new')
        new['superseded_by'] = 'test-correction'
        self.assertEqual(render.latest_headline(self.data, layer)['id'], old['id'])

    def test_applications_adoption_cannot_become_productivity_headline(self):
        layer = self.data['layers'][-1]
        self.assertEqual(render.latest_headline(self.data, layer)['metric'], 'waymo-paid-weekly')
        cards = render.layer_cards(self.data, './')
        self.assertIn('paid trips / week', cards)
        self.assertNotIn('88', cards)

    def test_source_and_period_are_escaped_in_static_html(self):
        record = render.latest_headline(self.data, self.data['layers'][0])
        record['period'] = '<script>alert(1)</script>'
        source = next(s for s in self.data['sources'] if s['id'] == record['source'])
        source['publisher'] = '<img onerror="alert(1)">'
        source['url'] = 'javascript:alert(1)'
        cards = render.layer_cards(self.data, './')
        self.assertNotIn('<script>', cards)
        self.assertNotIn('<img onerror', cards)
        self.assertNotIn('javascript:', cards)
        self.assertIn('&lt;script&gt;', cards)

    def test_failed_attempt_keeps_success_distinct_and_updates_build(self):
        before = render.runtime(self.data)
        self.data['runtime'].update(last_attempt='2026-09-07T10:00:00Z', status='failed', last_success=None)
        after = render.runtime(self.data)
        self.assertNotEqual(before, after)
        self.assertIn('<strong>Status:</strong> failed', after)
        self.assertIn('<strong>Last successful research:</strong> Not yet run', after)
        self.assertIn('source failures', after)

    def test_published_schedule_text_hour_matches_the_configured_cron_or_research_window(self):
        # site/data/ledger.json's runtime.schedule is a hand-typed, human-readable string;
        # research/runtime.json's schedule (or a future research_window) is the actual cron.
        # They drifted once (audit: docs-schedule-mismatch); pin the hour so they can't again.
        runtime_config = json.loads((ROOT / 'research/runtime.json').read_text(encoding='utf-8'))
        window = runtime_config.get('research_window')
        start = window.get('start') if isinstance(window, dict) else (window or '')   # dict {start,end} or "HH:MM-HH:MM tz"
        if start and re.match(r'\d{1,2}:\d{2}', start):
            expected_hour = start.split(':')[0].zfill(2)
        else:
            minute, hour = runtime_config['schedule'].split()[:2]
            expected_hour = hour.zfill(2)
        match = re.search(r'(\d{2}):\d{2}', self.data['runtime']['schedule'])
        self.assertIsNotNone(match, self.data['runtime']['schedule'])
        self.assertEqual(match.group(1), expected_hour, self.data['runtime']['schedule'])

    def test_daily_publisher_only_adds_existing_generated_page_paths(self):
        self.assertEqual(len(render.GENERATED_PAGES), 12 + len(render.COMPANY_IDS))
        self.assertTrue(all((ROOT / p).is_file() for p in render.GENERATED_PAGES))
        self.assertEqual(research.ALLOWED_CHANGES - {'site/data/ledger.json', 'docs/data/ledger.json', 'docs/feed.xml', 'site/data/excerpts.json', 'docs/data/excerpts.json'}, render.GENERATED_PAGES)
        for path in ['site/template.html', 'scripts/render.py', 'research/CONSTITUTION.md',
                     'docs/assets/app.js', 'docs/new-page/index.html']:
            self.assertNotIn(path, research.ALLOWED_CHANGES)


if __name__ == '__main__':
    unittest.main()
