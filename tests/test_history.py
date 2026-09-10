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
        self.registry=json.loads((ROOT/'research/sources.json').read_text(encoding='utf-8'))
        self.metrics={m['id']:m for m in self.data['metrics']}
        self.sources={s['id']:s for s in self.data['sources']}

    def test_runner_rejects_backfill_before_reviewed_start(self):
        from source_policy import collection_for
        m='us-electrician-employment-oews'
        source=self.sources[self.metrics[m]['source_ids'][0]]
        candidate=dict(metric=m,year=2018,period='May 2018',value=600000,upper=None,status='estimate',precision='eq',note='',evidence='May 2018 employment was 600,000 workers.')
        with self.assertRaisesRegex(ValueError,'backfill requires review'):
            research.candidate_record(candidate,source,candidate['evidence'],self.metrics,self.sources,policy=collection_for(self.registry,source))

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

    def test_broader_aeo_cannot_be_appended_as_utility_scale(self):
        o=copy.deepcopy(next(o for o in self.data['observations'] if o['metric']=='us-total-generation-aeo2026'))
        o['metric']='us-utility-generation-history'
        with self.assertRaisesRegex(ValueError,'mapping not approved'):
            observation_valid(o,self.metrics,self.sources)

    def test_high_growth_overlay_stays_on_its_own_metric(self):
        o=copy.deepcopy(next(o for o in self.data['observations'] if o['metric']=='us-total-generation-aeo2026-high-growth'))
        self.assertGreater(o['value'], next(x['value'] for x in self.data['observations'] if x['metric']=='us-total-generation-aeo2026' and x['year']==o['year']))
        o['metric']='us-utility-generation-history'
        with self.assertRaisesRegex(ValueError,'mapping not approved'):
            observation_valid(o,self.metrics,self.sources)
        self.assertEqual(self.metrics['us-utility-generation-history']['chart_type'],'line')
        self.assertEqual(self.metrics['us-utility-generation-history']['chart_overlay_metric'],'us-total-generation-aeo2026-high-growth')
        self.assertEqual(self.metrics['dc-electricity']['chart_overlay_metric'],'dc-electricity-iea2025-lift-off')
        self.assertNotIn('chart_companion_metric', self.metrics['dc-electricity'])
        self.assertIn(2035,{o['year'] for o in self.data['observations'] if o['metric']=='us-total-generation-aeo2026-high-growth'})

    def test_iihs_crash_rates_are_not_a_tesla_blend(self):
        waymo=next(o for o in self.data['observations'] if o['id']=='waymo-iihs-police-reportable-crash-rate-2021-2024')
        human=next(o for o in self.data['observations'] if o['id']=='human-iihs-matched-crash-rate-2021-2024')
        self.assertEqual(waymo['value'],1.28)
        self.assertEqual(human['value'],4.06)
        self.assertEqual(waymo['source'],'iihs-waymo-crash-2026')
        self.assertEqual(self.metrics['waymo-iihs-police-reportable-crash-rate']['company'],'waymo')
        self.assertIsNone(self.metrics['human-iihs-matched-crash-rate']['company'])
