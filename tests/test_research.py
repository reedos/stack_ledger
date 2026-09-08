import copy
import json
import sys
import tempfile
import io
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import research
from validate import validate, observation_valid, event_valid

ROOT=Path(__file__).resolve().parents[1]

class IntegrityTests(unittest.TestCase):
    def setUp(self):
        self.data=json.loads((ROOT/'site/data/ledger.json').read_text(encoding='utf-8'))
        self.metrics={m['id']:m for m in self.data['metrics']}
        self.sources={s['id']:s for s in self.data['sources']}
        self.candidate={'metric':'ai-adoption','year':2026,'period':'2026','value':90,'upper':None,'status':'observation','precision':'eq','note':'','evidence':'In 2026, 90 percent of surveyed organizations reported AI use.'}
    def record(self,candidate=None,document=None):
        c=candidate or self.candidate
        return research.candidate_record(c,self.sources['stanford-2026'],document or c['evidence'],self.metrics,self.sources)
    def test_seed_ledger_validates(self):self.assertTrue(validate(self.data))
    def test_invented_evidence_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'Evidence not found'):self.record(document='In 2026, 72 percent of surveyed organizations reported AI use.')
    def test_number_cannot_match_substring(self):
        self.assertFalse(research.numeric_support(50,'150 organizations'))
        self.assertTrue(research.numeric_support(5427,'5,427 data centers'))
        self.assertTrue(research.numeric_support(.07,'cost was $0.07 per million tokens'))
    def test_unsupported_number_rejected(self):
        c=copy.deepcopy(self.candidate);c['value']=91
        with self.assertRaisesRegex(ValueError,'numeric token'):self.record(c)
    def test_source_cannot_supply_unrelated_metric(self):
        c=copy.deepcopy(self.candidate);c['metric']='us-nuclear'
        with self.assertRaisesRegex(ValueError,'mapping'):self.record(c)
    def test_bounds_and_future_observations_rejected(self):
        o=self.record();o['value']=101
        with self.assertRaisesRegex(ValueError,'bounds'):observation_valid(o,self.metrics,self.sources)
        o=self.record();o['year']=2099
        with self.assertRaisesRegex(ValueError,'future'):observation_valid(o,self.metrics,self.sources)
    def test_future_forecast_is_allowed(self):
        o=self.record();o.update(year=2030,period='2030',status='forecast')
        observation_valid(o,self.metrics,self.sources)
    def test_finite_numeric_types_only(self):
        for value in [True,float('nan'),float('inf'),'90']:
            o=self.record();o['value']=value
            with self.assertRaises(ValueError):observation_valid(o,self.metrics,self.sources)
    def test_html_and_local_paths_are_rejected(self):
        for note in ['<script>alert(1)</script>','Read C:\\Users\\reedo\\private.txt']:
            c=copy.deepcopy(self.candidate);c['note']=note
            with self.assertRaises(ValueError):self.record(c)
    def test_inverted_or_unclassified_range_is_rejected(self):
        o=self.record();o.update(upper=80,precision='range')
        with self.assertRaisesRegex(ValueError,'Inverted'):observation_valid(o,self.metrics,self.sources)
        o['upper']=95;o['precision']='eq'
        with self.assertRaisesRegex(ValueError,'Range'):observation_valid(o,self.metrics,self.sources)
    def test_different_period_spelling_cannot_duplicate(self):
        o=copy.deepcopy(self.data['observations'][0]);o['period']='Calendar year 2024'
        self.assertEqual(research.duplicate_or_conflict(o,self.data['observations']),'duplicate')
        o['value']+=1
        self.assertEqual(research.duplicate_or_conflict(o,self.data['observations']),'conflict')
    def test_immutable_catalog_and_unknown_fields_rejected(self):
        self.data['metrics'][0]['unit']='GW'
        with self.assertRaisesRegex(ValueError,'metrics changed'):validate(self.data)
    def test_secret_field_is_not_publishable(self):
        o=self.record();o['api_key']='hidden'
        with self.assertRaisesRegex(ValueError,'fields'):observation_valid(o,self.metrics,self.sources)
    def test_external_discovery_domain_rejected(self):
        src=dict(self.sources['stanford-2026'],id='discovered-test',parent_source='stanford-2026',url='https://attacker.example/report')
        self.data['sources'].append(src)
        with self.assertRaisesRegex(ValueError,'host'):validate(self.data)
    def test_false_runtime_success_rejected(self):
        self.data['runtime']['last_success']='2026-01-01T00:00:00Z'
        with self.assertRaises(ValueError):validate(self.data)
    def test_network_private_addresses_and_foreign_redirect_rejected(self):
        with self.assertRaises(ValueError):research.allowed_url('http://127.0.0.1/','127.0.0.1')
        with self.assertRaises(ValueError):research.allowed_url('https://other.example/','approved.example')
        with patch.object(research.socket,'getaddrinfo',return_value=[(0,0,0,'',('127.0.0.1',443))]):
            with self.assertRaisesRegex(ValueError,'non-public'):research.allowed_url('https://public.example/','public.example')
    def test_readable_html_ignores_scripts_navigation_and_keeps_evidence(self):
        p=research.ReadableHTML();p.feed('<nav>Fake 900</nav><script>steal()</script><main><h1>2026 report</h1><p>AI use reached 90%.</p></main>')
        self.assertNotIn('Fake',p.readable());self.assertNotIn('steal',p.readable());self.assertIn('90%',p.readable())
    def test_clean_tree_required_before_network_or_push(self):
        with patch.object(research,'git',return_value=' M site/assets/app.js') as git:
            with self.assertRaisesRegex(ValueError,'clean'):research.preflight({'branch':'main','repository':'reedos/stack_ledger'})
            self.assertEqual(git.call_count,1)
    def test_publisher_rejects_code_changes(self):
        with patch.object(research,'git',return_value='scripts/research.py') as git:
            with self.assertRaisesRegex(ValueError,'unapproved'):research.publish({'branch':'main'})
            self.assertEqual(git.call_count,1)
    def test_overlapping_run_rejected(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(research,'LOCAL',Path(tmp)):
            with research.lock():
                with self.assertRaises(FileExistsError):
                    with research.lock():pass
            self.assertFalse((Path(tmp)/'research.lock').exists())

class RunnerTests(unittest.TestCase):
    def fixture(self,path):
        for name in ['research/discovery-policy.json','research/RESEARCH_AGENDA.md','research/runtime.json','research/sources.json','research/CONSTITUTION.md','research/OPERATING_GUIDE.md','research/ecosystem.json','research/delivery.json','research/fabric.json','research/expansion.json','research/agenda.json','research/claims.json','site/data/ledger.json']:
            target=path/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((ROOT/name).read_bytes())
        # These fixtures isolate legacy monitoring. Discovery integration has its own E2E test.
        policy=research.load(path/'research/discovery-policy.json');policy['enabled']=False
        research.save(path/'research/discovery-policy.json',policy)
    def test_no_change_run_is_honest_and_dry_run_does_not_mutate_site(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp);self.fixture(path)
            original=(path/'site/data/ledger.json').read_bytes()
            document=research.ReadableHTML();document.feed('<p>Public report of 2026 AI infrastructure and progress.</p>')
            with patch.object(research,'ROOT',path),patch.object(research,'LOCAL',path/'.local'),patch.object(research.Fetcher,'fetch',return_value=document),patch.object(research,'ollama',return_value={'observations':[]}),patch.object(sys,'argv',['research.py','--max-documents','5']),patch('sys.stdout',new=io.StringIO()):
                self.assertEqual(research.main(),0)
            proposal=research.load(path/'.local/proposed-ledger.json')
            self.assertEqual(proposal['runs'][-1]['accepted'],0)
            self.assertEqual(proposal['runs'][-1]['status'],'success')
            self.assertEqual(proposal['runs'][-1]['documents_reviewed'],5)
            self.assertEqual((path/'site/data/ledger.json').read_bytes(),original)
    def test_model_failure_does_not_advance_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp);self.fixture(path)
            before=research.load(path/'site/data/ledger.json')['runtime']['last_success']
            document=research.ReadableHTML();document.feed('<p>Public report of 2026 AI infrastructure and progress.</p>')
            with patch.object(research,'ROOT',path),patch.object(research,'LOCAL',path/'.local'),patch.object(research.Fetcher,'fetch',return_value=document),patch.object(research,'ollama',side_effect=TimeoutError('fixture timeout')),patch.object(sys,'argv',['research.py','--max-documents','5']),patch('sys.stdout',new=io.StringIO()):
                self.assertEqual(research.main(),1)
            proposal=research.load(path/'.local/proposed-ledger.json')
            self.assertEqual(proposal['runtime']['last_success'],before)
            self.assertEqual(proposal['runs'][-1]['status'],'failed')

class NoteTests(unittest.TestCase):
    def setUp(self):
        self.source={'id':'test-source','url':'https://example.org/ai-report','layers':['models'],'publisher':'Research Lab','published':None}
        self.note={'title':'A model release','summary':'The lab released an open model for research.','layer':'models','kind':'Company announcement','evidence':'The lab released an open model for research.'}
        self.run={'model_calls':0}
    def test_unsupported_note_number_is_quarantined(self):
        c=copy.deepcopy(self.note);c['summary']='The model supports 99 languages.'
        quarantine=[]
        with patch.object(research,'ollama',return_value={'notes':[c]}):
            result=research.extract_note({},self.source,c['evidence'],[],self.run,quarantine)
        self.assertIsNone(result);self.assertEqual(len(quarantine),1)
    def test_verifier_rejection_never_publishes_note(self):
        quarantine=[]
        with patch.object(research,'ollama',side_effect=[{'notes':[self.note]},{'verdicts':[{'index':0,'supported':False,'reason':'Insufficient context'}]}]):
            self.assertIsNone(research.extract_note({},self.source,self.note['evidence'],[],self.run,quarantine))
        self.assertEqual(len(quarantine),1)
    def test_supported_note_has_fixed_identity_and_evidence_hash(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(research,'LOCAL',Path(tmp)),patch.object(research,'ollama',side_effect=[{'notes':[self.note]},{'verdicts':[{'index':0,'supported':True,'reason':'Direct support'}]}]):
            event=research.extract_note({},self.source,self.note['evidence'],[],self.run,[])
        self.assertEqual(event['source'],self.source['id']);self.assertEqual(event['method'],'automated');self.assertEqual(len(event['evidence_sha256']),64)
        event_valid(event,{self.source['id']:self.source})

    def test_updated_source_can_add_a_note_and_both_passes_receive_guidance(self):
        previous={'source':self.source['id'],'summary':'Earlier release','document_sha256':'old','id':'old-note'}
        with tempfile.TemporaryDirectory() as tmp,patch.object(research,'LOCAL',Path(tmp)),patch.object(research,'ollama',side_effect=[{'notes':[self.note]},{'verdicts':[{'index':0,'supported':True,'reason':'Direct support'}]}]) as model:
            event=research.extract_note({'_instructions':'Reviewed operating guidance'},self.source,self.note['evidence'],[previous],self.run,[])
            self.assertIsNotNone(event)
            self.assertNotEqual(event['id'],previous['id'])
            self.assertTrue(all('Reviewed operating guidance' in call.args[1] for call in model.call_args_list))

if __name__=='__main__':unittest.main()
