import copy
import json
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import import_epoch as ie
from validate import observation_valid


class EpochImportTests(unittest.TestCase):
    def test_quarter_labels_become_canonical_periods(self):
        self.assertEqual(ie.quarter_period('Q1 2024'),('2024-Q1',2024))
        self.assertEqual(ie.quarter_period('Q4 2025'),('2025-Q4',2025))
        with self.assertRaises(ValueError):ie.quarter_period('2025 Q4')

    def test_matching_needs_distinctive_tokens_and_agreeing_numbers(self):
        projects=[{'id':'colossus-1','name':'Colossus 1','owner':'xAI','location':'Memphis, Tennessee'},{'id':'colossus-2','name':'Colossus 2','owner':'xAI','location':'Memphis, Tennessee'},
                  {'id':'colossus-grid','name':'Colossus grid · Memphis service studies','owner':'MLGW','location':'Memphis, Tennessee'},
                  {'id':'abilene','name':'Stargate · Abilene original campus','owner':'OpenAI / Oracle / Crusoe','location':'Abilene, Texas'},{'id':'temple','name':'Meta Temple data center','owner':'Meta','location':'Temple, Texas'},
                  {'id':'new-carlisle','name':'Anthropic + Amazon New Carlisle','owner':'Amazon','location':'New Carlisle, Indiana'},{'id':'meta-kansas-city','name':'Meta Kansas City','owner':'Meta','location':'Kansas City, Missouri'},
                  {'id':'google-a','name':'Google Alpha','owner':'Google','location':'A'},{'id':'google-b','name':'Google Beta','owner':'Google','location':'B'}]
        self.assertEqual(ie.match_projects('Colossus 2','SpaceXAI #confident',projects,{}),('colossus-2','suggested'))
        self.assertEqual(ie.match_projects('Colossus 1','SpaceXAI',projects,{}),('colossus-1','suggested'))
        self.assertEqual(ie.match_projects('OpenAI Stargate Abilene','OpenAI #confident',projects,{}),('abilene','suggested'))
        self.assertEqual(ie.match_projects('Meta Temple','Meta',projects,{}),('temple','suggested'))
        self.assertEqual(ie.match_projects('Meta Prometheus','Meta',projects,{}),(None,'none'))
        # Owner names alone never match, and an owner conflict vetoes a shared place name.
        self.assertEqual(ie.match_projects('Amazon Madison Mega Site','Amazon #confident',projects,{}),(None,'none'))
        self.assertEqual(ie.match_projects('Google Kansas City East','Google #confident',projects,{}),(None,'none'))
        self.assertEqual(ie.match_projects('Google Gamma','Google',projects,{}),(None,'none'))
        # A shared programme name breaks the tie between two sites in the same place; a true tie is ambiguous.
        abilene=projects+[{'id':'crusoe-abilene','name':'Crusoe / Microsoft · Abilene expansion','owner':'Crusoe / Microsoft','location':'Abilene, TX'}]
        self.assertEqual(ie.match_projects('OpenAI Stargate Abilene','Oracle #confident',abilene,{}),('abilene','suggested'))
        self.assertEqual(ie.match_projects('Crusoe Abilene Expansion','Crusoe #confident',abilene,{}),('crusoe-abilene','suggested'))
        twins=[{'id':'t1','name':'Fairwater · first facility','owner':'Microsoft','location':'Mount Pleasant, Wisconsin'},{'id':'t2','name':'Fairwater · second facility','owner':'Microsoft','location':'Mount Pleasant, Wisconsin'},{'id':'t3','name':'Fairwater · Atlanta region','owner':'Microsoft','location':'Atlanta, GA'}]
        self.assertEqual(ie.match_projects('Microsoft Fairwater Wisconsin','Microsoft #confident',twins,{}),(None,'ambiguous'))
        self.assertEqual(ie.match_projects('Microsoft Fairwater Atlanta','Microsoft #confident',twins,{}),('t3','suggested'))
        self.assertEqual(ie.match_projects('Meta Prometheus','Meta',projects,{'Meta Prometheus':'prometheus'}),('prometheus','reviewed'))
        self.assertEqual(ie.match_projects('Meta Prometheus','Meta',projects,{'Meta Prometheus':None}),(None,'reviewed'))

    def test_source_urls_are_extracted_and_social_links_dropped(self):
        text='- [WSJ](https://www.wsj.com/tech/a)\n- [Musk](https://x.com/elonmusk/status/1)\n- [Sheet](https://docs.google.com/spreadsheets/d/x)\nhttps://www.sec.gov/Archives/edgar/x.htm'
        self.assertEqual(ie.markdown_urls(text),['https://www.wsj.com/tech/a','https://www.sec.gov/Archives/edgar/x.htm'])

    def test_promoted_records_are_valid_quarterly_estimates_with_vintage(self):
        record={'vintage':'2026-07','sha256':'a'*64,'retrieved_at':'2026-09-08T10:00:00Z','tables':{
            'supply_denominators.csv':[{'Quarter':'Q1 2024','CoWoS supply (5th percentile)':'51000','CoWoS supply (median)':'58500.0','CoWoS supply (95th percentile)':'66000','Logic supply (5th percentile)':'1','Logic supply (median)':'2','Logic supply (95th percentile)':'3','HBM supply (USD) (5th percentile)':'1','HBM supply (USD) (median)':'2','HBM supply (USD) (95th percentile)':'3'}],
            'quarterly_by_designer.csv':[{'Quarter':'Q1 2024','Designer':'NVIDIA','CoWoS wafers (5th percentile)':'40000','CoWoS wafers (median)':'45000','CoWoS wafers (95th percentile)':'50000'},{'Quarter':'Q1 2024','Designer':'AMD','CoWoS wafers (5th percentile)':'1','CoWoS wafers (median)':'2','CoWoS wafers (95th percentile)':'3'}]}}
        catalog={'metrics':[]};source={'id':ie.DATASETS['chip-components']['source_id'],'publisher':'Epoch AI','title':'t','url':ie.DATASETS['chip-components']['url'],'published':None,'layers':['chips'],'license':'CC BY 4.0'}
        ledger={'observations':[{'id':'stale','metric':'epoch-cowos-supply-quarterly','source':source['id'],'year':2023,'period':'2023-Q4','value':1}],'metrics':[],'sources':[source]}
        added,records=ie.promote('chip-components',record,catalog,ledger,{})
        self.assertEqual(len(added),4);self.assertEqual(len(records),4)
        self.assertNotIn('stale',{o['id'] for o in ledger['observations']})  # a new vintage replaces the series
        cowos=next(r for r in records if r['metric']=='epoch-cowos-supply-quarterly')
        self.assertEqual((cowos['period'],cowos['year'],cowos['value'],cowos['status'],cowos['precision']),('2024-Q1',2024,58500.0,'estimate','approx'))
        self.assertIn('2026-07',cowos['note']);self.assertIn('51,000 to 66,000',cowos['note'])
        nvidia=next(r for r in records if r['metric']=='epoch-nvidia-cowos-wafers-quarterly');self.assertEqual(nvidia['value'],45000.0)
        metrics={m['id']:m for m in catalog['metrics']}
        for r in records:observation_valid(r,metrics,{source['id']:source})

    def test_drafted_project_validates_inside_the_delivery_catalog(self):
        import validate_delivery as vd
        delivery=json.loads((ROOT/'research/delivery.json').read_text(encoding='utf-8'));ledger=json.loads((ROOT/'site/data/ledger.json').read_text(encoding='utf-8'))
        companies=json.loads((ROOT/'research/ecosystem.json').read_text(encoding='utf-8'))['companies']
        record={'title':'AI Data Centers dataset','vintage':'2026-09','sha256':'b'*64,'retrieved_at':'2026-09-09T09:00:00Z','page':'https://epoch.ai/data/ai-data-centers'}
        row={'Name':'Microsoft Fairwater Atlanta','Owner':'Microsoft #confident','Users':'OpenAI #likely, Microsoft #likely','Country':'United States','Address':'Atlanta, GA','Current power (MW)':'636','Current H100 equivalents':'768769.2','Current total capital cost (2025 USD billions)':'24.1'}
        draft=ie.draft_project(row,record,companies)
        self.assertEqual((draft['id'],draft['stage'],draft['owner']),('microsoft-fairwater-atlanta','status-unverified','Microsoft'))
        self.assertEqual(draft['company_ids'],['microsoft','openai']);self.assertIn('636 MW',draft['grid']);self.assertIsNone(draft['milestones'][0]['date'])
        self.assertTrue(any(s['id']==draft['milestones'][0]['source'] for s in ledger['sources']),'Epoch dataset source must be registered')
        delivery['projects'].append(draft)
        self.assertTrue(vd.validate_delivery(delivery,ledger))
        self.assertEqual(ie.owner_label(''),'Undisclosed');self.assertEqual(ie.owner_label('Google'),'Google')

    def test_confirm_matches_records_aliases_without_touching_the_catalog(self):
        import tempfile
        result={'matched':[{'epoch_name':'Colossus 2','match':'colossus-two','match_basis':'suggested'},{'epoch_name':'Already','match':'x','match_basis':'reviewed'}]}
        with tempfile.TemporaryDirectory() as t:
            path=Path(t)/'aliases.json'
            aliases=ie.confirm_matches(result,accept_suggested=True,rejects=['Meta Kansas City'],path=path)
            self.assertEqual(aliases,{'Colossus 2':'colossus-two','Meta Kansas City':None})
            self.assertEqual(json.loads(path.read_text(encoding='utf-8')),aliases)
            self.assertEqual(ie.match_projects('Meta Kansas City','Meta',[],aliases),(None,'reviewed'))

    def test_site_records_attach_valid_estimates_to_a_project(self):
        import validate_delivery as vd, validate_expansion as ve
        delivery=json.loads((ROOT/'research/delivery.json').read_text(encoding='utf-8'));ledger=json.loads((ROOT/'site/data/ledger.json').read_text(encoding='utf-8'))
        companies=json.loads((ROOT/'research/ecosystem.json').read_text(encoding='utf-8'))['companies']
        record={'title':'AI Data Centers dataset','vintage':'2026-09','sha256':'c'*64,'retrieved_at':'2026-09-09T09:00:00Z','page':'https://epoch.ai/data/ai-data-centers'}
        row={'Name':'Amazon Testville Site','Owner':'Amazon #confident','Users':'Anthropic #speculative','Country':'United States','Address':'1 Test Road, Testville, Mississippi','Current power (MW)':'228','Current H100 equivalents':'171299.4','Current total capital cost (2025 USD billions)':'8.6'}
        project=ie.draft_project(row,record,companies)
        metrics,observations,updated=ie.site_records(row,project,record,companies)
        self.assertEqual([m['measurement_type'] for m in metrics],['estimated_site_it_mw','estimated_site_h100_equivalents','estimated_site_capital_cost_usd_bn'])
        self.assertTrue(all(t in ve.TYPES and t in ve.PUBLIC_TYPES for t in [m['measurement_type'] for m in metrics]))
        mw=next(o for o in observations if o['metric'].endswith('-it-mw'));self.assertEqual((mw['value'],mw['period'],mw['status'],mw['year']),(228,'2026-09-09','estimate',2026))
        self.assertEqual(updated['observations'],[o['id'] for o in observations if not o['metric'].endswith('-capex')])   # capital cost reaches the money section via metric.project
        self.assertEqual(metrics[0]['project'],project['id']);self.assertEqual(metrics[0]['company'],'aws')
        sources={s['id']:s for s in ledger['sources']};allm={m['id']:m for m in ledger['metrics']};allm.update({m['id']:m for m in metrics})
        for o in observations:observation_valid(o,allm,sources)
        ledger2=dict(ledger,metrics=list(allm.values()),observations=ledger['observations']+observations)
        delivery['projects'].append(updated)
        self.assertTrue(vd.validate_delivery(delivery,ledger2))
        self.assertTrue(ie.has_epoch_capacity(updated,ledger2,{'metrics':list(allm.values())}))
        self.assertFalse(ie.has_epoch_capacity(project,ledger,{'metrics':ledger['metrics']}))

    def test_vintage_read_from_readme_citation(self):
        self.assertEqual(ie.vintage_of('@misc{x,\n  year = {2026},\n  month = {07},\n}','2026-09-09T00:00:00Z'),'2026-07')
        self.assertEqual(ie.vintage_of('no citation','2026-09-09T00:00:00Z'),'2026-09')


if __name__=='__main__':unittest.main()
