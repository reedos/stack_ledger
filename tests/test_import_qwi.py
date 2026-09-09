import json
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import import_qwi as iw
import validate_expansion as ve
from validate import observation_valid

BODY=json.dumps([["HirA","EarnS","Emp","industry","ownercode","time","state","county"],
                 ["188","18834","2034","5182","A05","2024-Q1","32","003"],
                 ["201",None,"2100","5182","A05","2024-Q2","32","003"],      # suppressed earnings: omitted, never zero
                 ["-1","19000","2120","5182","A05","2024-Q3","32","003"],    # negative sentinel: omitted
                 ["150","19500","2148","5182","A05","2025-Q4","32","003"]]).encode('utf-8')


class QwiImportTests(unittest.TestCase):
    def test_query_targets_county_industry_private_ownership_and_the_period_range(self):
        url=iw.query_url('32003','5182','2026-Q3')
        self.assertIn('for=county:003&in=state:32',url);self.assertIn('industry=5182',url);self.assertIn('ownercode=A05',url);self.assertIn('time=from2024-Q1to2026-Q3',url)
        self.assertTrue(url.startswith('https://api.census.gov/data/timeseries/qwi/sa?'))

    def test_records_are_valid_and_gaps_are_not_zero(self):
        rows=iw.parse(BODY)
        metrics,observations=iw.records_for(rows,'32003','5182','Clark County, NV','2026-09-09T12:00:00Z','a'*64)
        self.assertEqual(sorted(metrics),['qwi-32003-5182-earnings','qwi-32003-5182-hires'])
        hires=[o for o in observations if o['metric'].endswith('-hires')];earn=[o for o in observations if o['metric'].endswith('-earnings')]
        self.assertEqual([(o['period'],o['value']) for o in hires],[('2024-Q1',188),('2024-Q2',201),('2025-Q4',150)])   # -1 dropped
        self.assertEqual([(o['period'],o['value']) for o in earn],[('2024-Q1',18834),('2024-Q3',19000),('2025-Q4',19500)])  # None dropped
        self.assertTrue(all(m['measurement_type'] in ve.TYPES and m['measurement_type'] in ve.PUBLIC_TYPES and m['measurement_type'] in ve.HISTORICAL_ONLY for m in metrics.values()))
        self.assertEqual(metrics['qwi-32003-5182-hires']['geography_code'],'32003')
        for o in observations:observation_valid(o,metrics,{iw.SOURCE_ID:iw.SOURCE})

    def test_key_is_required_and_never_recorded(self):
        src=(ROOT/'scripts/import_qwi.py').read_text(encoding='utf-8')
        self.assertIn("api_access.key('census')",src);self.assertNotIn('591971',src)
        self.assertIn("'key':'owner-registered, not recorded'",src)


if __name__=='__main__':unittest.main()
