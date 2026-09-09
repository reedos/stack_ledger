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

    def test_promote_notable_models_yearly_counts_and_extremes(self):
        rows=[
            {'Model':'Old Model','Organization':'Acme','Publication date':'2023-05-01','Training compute (FLOP)':'2.0e24'},
            {'Model':'Frontier A','Organization':'Acme','Publication date':'2026-01-15','Training compute (FLOP)':'3.0e25'},
            {'Model':'Frontier B','Organization':'Beta Labs','Publication date':'2026-04-02','Training compute (FLOP)':'5.0e25'},
            {'Model':'No Compute Disclosed','Organization':'Beta Labs','Publication date':'2026-06-20','Training compute (FLOP)':''},
        ]
        record={'vintage':'2026-09','sha256':'d'*64,'retrieved_at':'2026-09-09T09:00:00Z','tables':{'notable_ai_models.csv':rows}}
        metrics,records=ie.promote_notable_models(record)
        self.assertEqual({m['id'] for m in metrics},{'epoch-notable-models-released-yearly','epoch-notable-models-max-compute-yearly','epoch-notable-models-over-1e25-yearly'})
        self.assertTrue(all(m['company'] is None and m['measurement_type'] in {'notable_models_released','max_training_compute_flop','models_over_1e25_flop'} for m in metrics))
        released_2023=next(r for r in records if r['id']=='epoch-notable-models-released-yearly-2023')
        self.assertEqual((released_2023['value'],released_2023['period'],released_2023['status']),(1,'Year-end 2023','estimate'))
        released_2026=next(r for r in records if r['id']=='epoch-notable-models-released-yearly-2026')
        self.assertEqual((released_2026['value'],released_2026['period']),(3,'June 20, 2026'))   # partial year: latest model's own date
        over_2026=next(r for r in records if r['id']=='epoch-notable-models-over-1e25-yearly-2026')
        self.assertEqual(over_2026['value'],2)   # Frontier A and B, not the undisclosed-compute model
        over_2023=next(r for r in records if r['id']=='epoch-notable-models-over-1e25-yearly-2023')
        self.assertEqual(over_2023['value'],0)   # a real, counted zero -- not a missing/suppressed record
        maxflop_2026=next(r for r in records if r['id']=='epoch-notable-models-max-compute-yearly-2026')
        self.assertEqual(maxflop_2026['value'],5e25)
        sources={ie.DATASETS['notable-models']['source_id']:{'id':ie.DATASETS['notable-models']['source_id']}}
        allm={m['id']:m for m in metrics}
        for r in records:observation_valid(r,allm,sources)

    def test_site_records_uses_the_status_table_reading_date_when_available(self):
        import validate_delivery as vd
        delivery=json.loads((ROOT/'research/delivery.json').read_text(encoding='utf-8'));ledger=json.loads((ROOT/'site/data/ledger.json').read_text(encoding='utf-8'))
        companies=json.loads((ROOT/'research/ecosystem.json').read_text(encoding='utf-8'))['companies']
        record={'title':'AI Data Centers dataset','vintage':'2026-09','sha256':'e'*64,'retrieved_at':'2026-09-09T09:00:00Z','page':'https://epoch.ai/data/ai-data-centers',
                'tables':{'data_center_timelines.csv':[
                    {'Data center':'Amazon Reading-Date Site','Date':'2026-07-28','IT power (MW)':'228'},
                    {'Data center':'Amazon Reading-Date Site','Date':'2026-11-01','IT power (MW)':'900'},   # future/projected: excluded
                ]}}
        row={'Name':'Amazon Reading-Date Site','Owner':'Amazon #confident','Users':'','Country':'United States','Address':'1 Test Road, Testville, Mississippi','Current power (MW)':'228','Current H100 equivalents':'171299.4','Current total capital cost (2025 USD billions)':'8.6'}
        project=ie.draft_project(row,record,companies)
        metrics,observations,updated=ie.site_records(row,project,record,companies)
        mw=next(o for o in observations if o['metric'].endswith('-it-mw'))
        self.assertEqual((mw['value'],mw['period'],mw['year']),(228,'2026-07-28',2026))
        self.assertIn(f"{mw['metric']}-2026-07-28",{o['id'] for o in observations})
        self.assertNotIn('reading date not stated',mw['note'])
        sources={s['id']:s for s in ledger['sources']};allm={m['id']:m for m in ledger['metrics']};allm.update({m['id']:m for m in metrics})
        for o in observations:observation_valid(o,allm,sources)
        ledger2=dict(ledger,metrics=list(allm.values()),observations=ledger['observations']+observations)
        delivery['projects'].append(updated)
        self.assertTrue(vd.validate_delivery(delivery,ledger2))

    def test_site_records_falls_back_to_pull_date_without_a_reading_date(self):
        record={'title':'AI Data Centers dataset','vintage':'2026-09','sha256':'f'*64,'retrieved_at':'2026-09-09T09:00:00Z','page':'https://epoch.ai/data/ai-data-centers'}
        row={'Name':'Amazon No-Timeline Site','Owner':'Amazon #confident','Country':'United States','Current power (MW)':'50'}
        companies=json.loads((ROOT/'research/ecosystem.json').read_text(encoding='utf-8'))['companies']
        project=ie.draft_project(row,record,companies)
        metrics,observations,updated=ie.site_records(row,project,record,companies)
        mw=next(o for o in observations if o['metric'].endswith('-it-mw'))
        self.assertEqual((mw['value'],mw['period']),(50,'2026-09-09'))
        self.assertIn('reading date not stated',mw['note'])

    def test_capabilities_rows_reshape_the_eci_scores_table(self):
        rows=[{'Model':'GPT-Test','Organization':'OpenAI','date':'2026-08-01','eci':'150.25','eci_ci_low':'145.1','eci_ci_high':'155.4','Accessibility group':'Closed weights','Country (of organization)':'United States of America'},
              {'Model':'Open-Test','Organization':'Meta','date':'2026-08-05','eci':'120','eci_ci_low':'','eci_ci_high':'','Accessibility group':'Open weights','Country (of organization)':'United States of America'}]
        record={'vintage':'2026-09','sha256':'a1'*32,'retrieved_at':'2026-09-09T09:00:00Z','tables':{'epoch_capabilities_index/eci_scores.csv':rows}}
        out=ie.capabilities_rows(record)
        self.assertEqual(len(out),2)
        self.assertTrue(all(__import__('re').fullmatch('eci-[a-f0-9]{16}',r['id']) for r in out))
        closed=next(r for r in out if r['name']=='GPT-Test')
        self.assertEqual((closed['access'],closed['score'],closed['low'],closed['high']),('Closed weights',150.25,145.1,155.4))
        opened=next(r for r in out if r['name']=='Open-Test')
        self.assertEqual((opened['access'],opened['low'],opened['high']),('Open weights',None,None))


if __name__=='__main__':unittest.main()
