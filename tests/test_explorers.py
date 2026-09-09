import copy
import json
import sys
import unittest
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from validate_explorers import validate_explorers,validate_location
from render_explorers import capital,capabilities,project_map,capital_totals,capital_projections,default_models,map_records,map_symbol

class ExplorerTests(unittest.TestCase):
    def setUp(self):
        read=lambda name:json.loads((ROOT/'site/data'/f'{name}.json').read_text(encoding='utf-8'))
        self.x,self.l,self.e,self.d=[read(name) for name in ['expansion','ledger','ecosystem','delivery']]
    def test_total_requires_complete_cohort_and_keeps_vintages_separate(self):
        series=[({},[{'year':2025,'value':1.1},{'year':2026,'value':5}]),({},[{'year':2025,'value':2.2}])]
        self.assertEqual(capital_totals(series),[(2025,3.3)])
        projected=capital_projections(self.l,self.x['capital'])
        self.assertEqual([y for y,_ in projected],[2026])
        self.assertEqual(len(projected[0][1]),5)
        bad=copy.deepcopy(self.x);bad['capital']['archived_forecast']['companies'].pop()
        with self.assertRaisesRegex(ValueError,'complete cohort'):validate_explorers(bad,self.l,self.e)
    def test_default_model_view_is_only_a_display_filter(self):
        c=self.x['capabilities'];shown=default_models(c)
        from collections import Counter
        counts=Counter(r['organization'] for r in c['rows'])
        self.assertTrue(all(counts[r['organization']]>3 and r['organization']!='Not listed by Epoch' for r in shown))
        self.assertLess(len(shown),len(c['rows']))
        self.assertTrue(all(r['country'] for r in c['rows']))
        html=capabilities(self.l,self.x,'./');self.assertIn('Country of organization',html)
        self.assertNotIn('id="eci-developer"',html)
    def test_real_data_resolves(self):
        self.assertTrue(validate_explorers(self.x,self.l,self.e))
    def test_locality_markers_keep_programs_and_offices_separate(self):
        from validate_delivery import validate_delivery
        from validate_ecosystem import validate_ecosystem
        self.assertTrue(validate_delivery(self.d,self.l));self.assertTrue(validate_ecosystem(self.e,self.l))
        rows=map_records(self.d,self.e)
        waymo=[p for p in rows if p['id']=='waymo-one']
        self.assertEqual(len([p for p in waymo if p['stage']=='operating']),14)
        self.assertEqual(len([p for p in waymo if p['stage']=='announced']),18)
        self.assertEqual(len([p for p in self.d['projects'] if p['id']=='waymo-one']),1)
        self.assertTrue(any(p.get('office_kind') for p in rows))
        bad=copy.deepcopy(self.d);p=next(p for p in bad['projects'] if p.get('map_locations'));p['map_locations'][0]['source']='unknown'
        with self.assertRaisesRegex(ValueError,'locality evidence'):validate_delivery(bad,self.l)
        bad=copy.deepcopy(self.e);c=next(c for c in bad['companies'] if c.get('map_offices'));c['map_offices'][0]['kind']='operating'
        with self.assertRaisesRegex(ValueError,'office kind'):validate_ecosystem(bad,self.l)
    def test_shared_marker_preserves_colors_and_planned_status(self):
        html=map_symbol([{'layer':'energy','stage':'operating'},{'layer':'models','stage':'announced'}],{'energy':'#123456','models':'#abcdef'},2)
        self.assertIn('#123456',html);self.assertIn('#abcdef',html)
        self.assertIn('phase-planned',html);self.assertNotIn('fill="#edf0e4"',html)
    def test_reviewed_operator_directory_is_reconciled_without_duplicate_aliases(self):
        fixture=json.loads((ROOT/'tests/fixtures/hyperscale_coverage_20260909.json').read_text(encoding='utf-8'))
        projects={p['id']:p for p in self.d['projects']}
        self.assertEqual(len(fixture['localities']),33)
        for row in fixture['localities']:
            self.assertIn(row['project'],projects)
            self.assertEqual(projects[row['project']]['layer'],'infrastructure')
        self.assertEqual(len({row['project'] for row in fixture['localities']}),33)
        self.assertIn('Frontier',projects['stargate-shackelford']['name'])
        self.assertFalse(any(p['id']=='vantage-frontier' for p in self.d['projects']))
    def test_planned_gigawatts_and_delivered_it_load_keep_their_basis(self):
        projects={p['id']:p for p in self.d['projects']};obs={o['id']:o for o in self.l['observations']}
        for pid in ['meta-prometheus','meta-lebanon','meta-el-paso']:
            p=projects[pid];self.assertNotEqual(p['stage'],'operating')
            o=obs[p['observations'][0]];self.assertEqual(o['value'],1);self.assertEqual(o['status'],'company-commitment')
        p=projects['galaxy-helios'];o=obs[p['observations'][0]]
        self.assertEqual(p['stage'],'partly-operating');self.assertEqual(o['value'],133);self.assertEqual(o['status'],'observation')
        html=map_symbol([{'layer':'infrastructure','stage':'status-unverified'}],{'infrastructure':'#abcdef'},2)
        self.assertIn('phase-unverified',html);self.assertNotIn('phase-delivery',html);self.assertNotIn('phase-operating',html)
    def test_capital_does_not_accept_forecast_as_actual(self):
        row=self.x['capital']['companies'][0]
        row['history_metric']=row['guidance_metric']
        with self.assertRaisesRegex(ValueError,'basis mismatch'):validate_explorers(self.x,self.l,self.e)
    def test_capital_revisions_require_explicit_supersession(self):
        mid=self.x['capital']['companies'][0]['history_metric']
        o=copy.deepcopy(next(o for o in self.l['observations'] if o['metric']==mid));o['id']='duplicate-capital';self.l['observations'].append(o)
        with self.assertRaisesRegex(ValueError,'Conflicting capital'):validate_explorers(self.x,self.l,self.e)
    def test_capital_source_vintages_and_scopes_are_visible(self):
        html=capital(self.l,self.x,'./')
        self.assertIn('Total · all five',html)
        self.assertIn('September 2025',html)
        self.assertNotIn('capital-archive',html)
        self.assertIn('2021–2026',html)
        self.assertNotIn('September 2025',html.split('<details class="explorer-evidence">')[0])
        self.assertIn('lease reclassification',html)
        self.assertIn('CY2026 guidance',html)
        self.assertIn('FY2026 ended May 31',html)
        self.assertIn('Associated Press',html)
        self.assertIn('bars start at zero',html)
    def test_later_years_extend_capital_history(self):
        row=self.x['capital']['companies'][0];o=copy.deepcopy(next(o for o in self.l['observations'] if o['metric']==row['history_metric']))
        o.update(id='later-capital-fixture',year=2035,period='FY2035',value=200);self.l['observations'].append(o)
        html=capital(self.l,self.x,'./');self.assertIn('2021–2035',html)
        # A missing decade is not joined into a continuous growth trajectory.
        self.assertNotIn('FY2028',html)
    def test_bad_eci_interval_and_mixed_shape_fail(self):
        row=self.x['capabilities']['rows'][0];row['low']=row['score']+1
        with self.assertRaisesRegex(ValueError,'uncertainty interval'):validate_explorers(self.x,self.l,self.e)
    def test_snapshot_without_provenance_fails(self):
        self.x['capabilities']['document_sha256']=''
        with self.assertRaisesRegex(ValueError,'dataset hash'):validate_explorers(self.x,self.l,self.e)
    def test_eci_anchors_and_static_table_remain_accessible(self):
        html=capabilities(self.l,self.x,'./')
        self.assertIn('Anchor; interval not supplied',html)
        self.assertEqual(html.count('<tr data-model='),len(self.x['capabilities']['rows']))
        self.assertIn('90% confidence',html)
        self.assertIn('No future capability is extrapolated',html)
    def test_coordinates_cannot_be_guessed_or_unattributed(self):
        loc=copy.deepcopy(next(p['map_location'] for p in self.d['projects'] if 'map_location' in p))
        sources={s['id']:s for s in self.l['sources']}
        now=datetime.now(timezone.utc)
        for key,value in [('latitude',91),('longitude',float('nan')),('source','missing'),('precision','guessed')]:
            bad={**loc,key:value}
            with self.assertRaises(ValueError):validate_location(bad,sources,'energy',now)
    def test_map_reports_partial_coverage_and_locality_precision(self):
        html=project_map(self.d,self.l,'./')
        self.assertIn(f"of {len(self.d['projects'])} project records",html)
        self.assertIn('not exact facilities',html)
        self.assertIn('GeoNames',html)
        self.assertNotIn('tiles.',html)

if __name__=='__main__':unittest.main()
