import copy
import json
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from validate import observation_valid, validate
import research

class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.data=json.loads((ROOT/'site/data/ledger.json').read_text(encoding='utf-8'))
        self.metrics={m['id']:m for m in self.data['metrics']}
        self.sources={s['id']:s for s in self.data['sources']}

    def test_runner_rejects_backfill_before_reviewed_start(self):
        m='us-electrician-employment-oews'
        candidate=dict(metric=m,year=2018,period='May 2018',value=600000,upper=None,status='estimate',precision='eq',note='',evidence='May 2018 employment was 600,000 workers.')
        with self.assertRaisesRegex(ValueError,'backfill requires review'):
            research.candidate_record(candidate,self.sources[self.metrics[m]['source_ids'][0]],candidate['evidence'],self.metrics,self.sources)

    def test_future_append_does_not_require_changing_window(self):
        o=copy.deepcopy(next(o for o in self.data['observations'] if o['metric']=='dc-electricity-iea2025-high-efficiency' and o['status']=='forecast'))
        o.update(year=2040,period='2040')
        observation_valid(o,self.metrics,self.sources)

    def test_daily_ledger_cannot_change_reviewed_history(self):
        self.data['metrics'][0]['series_start_year']=2000
        with self.assertRaisesRegex(ValueError,'Reviewed metrics changed'):validate(self.data)

    def test_context_and_break_are_retained(self):
        for mid in ['us-utility-generation-history','us-electrician-employment-oews','revenue-tsmc']:
            years={o['year'] for o in self.data['observations'] if o['metric']==mid and o['status'] in ['estimate','observation']}
            self.assertIn(2019,years);self.assertGreaterEqual(len(years),5)
        self.assertFalse(self.metrics['us-electrician-employment-oews']['definition_stable'])
        self.assertEqual(self.metrics['us-electrician-employment-oews']['definition_break_year'],2021)
