import json
import sys
import unittest
from datetime import date
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import import_qcew as iq
import validate_expansion as ve
from validate import observation_valid

HEADER='"area_fips","own_code","industry_code","agglvl_code","size_code","year","qtr","disclosure_code","qtrly_estabs","month1_emplvl","month2_emplvl","month3_emplvl","total_qtrly_wages","taxable_qtrly_wages","qtrly_contributions","avg_wkly_wage"'
ROWS=[HEADER,
      '"US000","5","518210","18","0","2026","1","","20000","480000","482000","483969","1","1","1","3200"',
      '"48139","5","518210","78","0","2026","1","","11","170","175","179","1","1","1","2100"',
      '"48139","3","518210","78","0","2026","1","","1","5","5","5","1","1","1","900"',        # local government ownership: ignored
      '"32003","5","518210","78","0","2026","1","N","0","0","0","0","0","0","0","0"',          # suppressed: never a zero
      '"48113","5","518210","78","0","2026","1","","900","12000","12100","12250","1","1","1","2500"',  # county not in the catalog: ignored
      '"48000","5","518210","58","0","2026","1","","3000","90000","90500","91000","1","1","1","2300"']  # state level: ignored


class QcewImportTests(unittest.TestCase):
    def setUp(self):
        self.blob=('\n'.join(ROWS)+'\n').encode('utf-8')
        self.counties={'48139':'Ellis County, TX','32003':'Clark County, NV'}

    def test_quarters_run_from_first_year_to_the_current_quarter(self):
        qs=iq.quarters(date(2026,9,9))
        self.assertEqual(qs[0],(2024,1));self.assertEqual(qs[-1],(2026,3));self.assertEqual(len(qs),11)

    def test_selection_keeps_private_county_rows_and_national_total_only(self):
        rows=iq.select_rows(iq.parse(self.blob),self.counties)
        self.assertEqual(sorted((r['area_fips'],r['own_code']) for r in rows),[('32003','5'),('48139','5'),('US000','5')])

    def test_records_are_valid_quarterly_observations_and_suppression_is_not_zero(self):
        rows=iq.select_rows(iq.parse(self.blob),self.counties)
        metrics,observations,suppressed=iq.records_for(rows,'2026-09-09T12:00:00Z','f'*64,self.counties)
        self.assertEqual(sorted(metrics),['qcew-32003-518210','qcew-48139-518210','qcew-us-518210'])
        self.assertEqual(suppressed,[('qcew-32003-518210','2026','1')])
        self.assertEqual(sorted(o['id'] for o in observations),['qcew-48139-518210-2026q1','qcew-us-518210-2026q1'])
        ellis=next(o for o in observations if o['metric']=='qcew-48139-518210')
        self.assertEqual((ellis['value'],ellis['period'],ellis['status'],ellis['precision']),(179,'2026-Q1','observation','eq'));self.assertIn('11 establishments',ellis['note'])
        self.assertEqual(metrics['qcew-48139-518210']['geography_code'],'48139');self.assertIsNone(metrics['qcew-us-518210']['geography_code'])
        self.assertTrue(all(m['measurement_type'] in ve.TYPES and m['measurement_type'] in ve.PUBLIC_TYPES and m['measurement_type'] in ve.HISTORICAL_ONLY for m in metrics.values()))
        sources={iq.SOURCE_ID:iq.SOURCE}
        for o in observations:observation_valid(o,metrics,sources)

    def test_project_counties_come_from_reviewed_county_locations_only(self):
        delivery=json.loads((ROOT/'research/delivery.json').read_text(encoding='utf-8'))
        counties=iq.project_counties(delivery)
        self.assertTrue(counties);self.assertTrue(all(len(k)==5 and k.isdigit() for k in counties))
        fake={'projects':[{'map_location':{'source':'census-map-places','source_key':'4805000','label':'Austin, TX'}}]}
        self.assertEqual(iq.project_counties(fake),{})


if __name__=='__main__':unittest.main()
