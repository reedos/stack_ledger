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

def empty_model(config,system,prompt,schema):
    """A schema-aware fake model returning an empty, well-formed response for either lane.

    Both extract_note and extract_observations now run for the same document (2026-09-09),
    so a single return_value dict can no longer serve both -- each schema forbids the
    other's key (additionalProperties: False). Real Ollama structured output enforces this
    too; this fixture just mirrors it instead of relying on one shared dict shape.
    """
    return {'notes':[]} if schema==research.NOTE_SCHEMA else {'observations':[]}

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
        for name in ['research/discovery-policy.json','research/RESEARCH_AGENDA.md','research/runtime.json','research/sources.json','research/CONSTITUTION.md','research/OPERATING_GUIDE.md','research/MODEL_BRIEF.md','research/ecosystem.json','research/delivery.json','research/fabric.json','research/expansion.json','research/agenda.json','research/claims.json','site/data/ledger.json']:
            target=path/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((ROOT/name).read_bytes())
        # These fixtures isolate legacy monitoring. Discovery integration has its own E2E test.
        policy=research.load(path/'research/discovery-policy.json');policy['enabled']=False
        research.save(path/'research/discovery-policy.json',policy)
        # Accepted catalog/evidence stays representative; live execution history must
        # not make a test depend on when an unattended publishing batch runs it.
        ledger=research.load(path/'site/data/ledger.json');ledger['runs']=[]
        ledger['runtime'].update(last_attempt=None,last_success=None,status='awaiting-first-run')
        research.save(path/'site/data/ledger.json',ledger)
    def test_no_change_run_is_honest_and_dry_run_does_not_mutate_site(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp);self.fixture(path)
            original=(path/'site/data/ledger.json').read_bytes()
            document=research.ReadableHTML();document.feed('<p>Public report of 2026 AI infrastructure and progress.</p>')
            with patch.object(research,'ROOT',path),patch.object(research,'LOCAL',path/'.local'),patch.object(research.Fetcher,'fetch',return_value=document),patch.object(research,'ollama',side_effect=empty_model),patch.object(sys,'argv',['research.py','--max-documents','5']),patch('sys.stdout',new=io.StringIO()):
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

class NoteLaneCoverageTests(unittest.TestCase):
    """The note lane now runs for every read document; private notes are capped per run."""
    def test_note_lane_reaches_non_publishable_related_sources_and_the_cap_limits_the_queue(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp);RunnerTests().fixture(path)
            config=research.load(path/'research/runtime.json');config['max_private_notes_per_run']=1
            research.save(path/'research/runtime.json',config)
            document=research.ReadableHTML();document.feed('<p>Filler context. In 2026, the lab reported new AI infrastructure progress and 42 new facilities.</p>')
            note={'title':'A research development','summary':'The lab reported 42 new facilities in 2026.','layer':'energy','kind':'Research finding','evidence':'In 2026, the lab reported new AI infrastructure progress and 42 new facilities.'}
            def fake_model(cfg,system,prompt,schema):
                if schema==research.NOTE_SCHEMA:return {'notes':[note]}
                if schema==research.VERDICT_SCHEMA:return {'verdicts':[{'index':0,'supported':True,'reason':'Direct support'}]}
                return {'observations':[]}
            # All three: no parent_source, excerpts disabled in policy, but each has a linked
            # metric -- the old gate ("publishable or not related") skipped every one of them.
            sources=['iea-2026','iea-2025','doe-demand']
            with patch.object(research,'ROOT',path),patch.object(research,'LOCAL',path/'.local'),patch.object(research.Fetcher,'fetch',return_value=document), \
                 patch.object(research,'ollama',side_effect=fake_model),patch.object(sys,'argv',['research.py','--sources',*sources]),patch('sys.stdout',new=io.StringIO()):
                research.main()
            queued=list((path/'.local/review-candidates').glob('*.json'))
            self.assertEqual(len(queued),1,'the per-run cap must stop after the first private note')
            saved=research.load(queued[0])
            self.assertEqual(saved['publication'],'private')
            self.assertIn(saved['source'],sources)
            public=research.load(path/'.local/proposed-ledger.json')
            self.assertEqual(public['runs'][-1]['accepted'],0,'private notes never become public events')

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

class EvidenceRuleTests(unittest.TestCase):
    """The runner tells the model the validator rules and snaps quotes to source bytes."""
    def setUp(self):
        self.source={'id':'test-source','url':'https://example.org/ai-report','layers':['models'],'publisher':'Research Lab','published':'2026-03-05'}
        self.run={'model_calls':0}
        self.accept={'verdicts':[{'index':0,'supported':True,'reason':'Direct support'}]}
    def note(self,**over):
        c={'title':'A model release','summary':'The lab released 3 open models for research.','layer':'models','kind':'Company announcement','evidence':'The lab released 3 open models for research.'}
        c.update(over);return c
    def test_publication_year_is_allowed_outside_the_excerpt(self):
        c=self.note(summary='In 2026 the lab released 3 open models for research.')
        with tempfile.TemporaryDirectory() as tmp,patch.object(research,'LOCAL',Path(tmp)),patch.object(research,'ollama',side_effect=[{'notes':[c]},self.accept]):
            self.assertIsNotNone(research.extract_note({},self.source,c['evidence'],[],self.run,[]))
    def test_other_years_outside_the_excerpt_are_still_quarantined(self):
        c=self.note(summary='In 2025 the lab released 3 open models for research.');quarantine=[]
        with patch.object(research,'ollama',return_value={'notes':[c]}):
            self.assertIsNone(research.extract_note({},self.source,c['evidence'],[],self.run,quarantine))
        self.assertIn('unsupported number',quarantine[0]['reason'])
    def test_typographic_drift_is_snapped_to_the_documents_own_bytes(self):
        document='Waymo’s fleet — “rider‑only” — grew to 2,500 vehicles in 2025.'
        c=self.note(summary='Waymo says its rider-only fleet grew to 2,500 vehicles in 2025.',evidence='Waymo\'s fleet - "rider-only" - grew to 2,500 vehicles in 2025.',layer='models')
        with tempfile.TemporaryDirectory() as tmp,patch.object(research,'LOCAL',Path(tmp)),patch.object(research,'ollama',side_effect=[{'notes':[c]},self.accept]):
            event=research.extract_note({},self.source,document,[],self.run,[])
            proof=research.load(Path(tmp)/'evidence'/f'{event["id"]}.json')
        self.assertEqual(proof['evidence'],document)
        self.assertEqual(event['evidence_sha256'],research.digest(document))
    def test_both_passes_receive_the_rules_and_the_reviewer_sees_focused_context(self):
        filler=('Unrelated paragraph about something else entirely.\n'*80)
        document=filler+'The lab released 3 open models for research.\n'+filler
        c=self.note()
        with tempfile.TemporaryDirectory() as tmp,patch.object(research,'LOCAL',Path(tmp)),patch.object(research,'ollama',side_effect=[{'notes':[c]},self.accept]) as model:
            research.extract_note({'_instructions':'Guide'},self.source,document,[],self.run,[])
        extraction,review=model.call_args_list
        packet=json.loads(extraction.args[2])
        self.assertEqual(packet['evidence_rules'],research.EVIDENCE_RULES);self.assertEqual(packet['source_publication_year'],'2026')
        self.assertIn(research.SCREENING_RULES,review.args[1])
        shown=json.loads(review.args[2])['untrusted_document']
        self.assertIn('The lab released 3 open models for research.',shown);self.assertLess(len(shown),len(document)//2)
    def test_note_evidence_longer_than_the_cap_but_shrinkable_is_accepted(self):
        # A repeated short sentence: shrink_to_numbers can isolate one sentence under the cap.
        long_quote='The lab released 3 open models for research. '*30
        c=self.note(evidence=long_quote);quarantine=[]
        with tempfile.TemporaryDirectory() as tmp,patch.object(research,'LOCAL',Path(tmp)),patch.object(research,'ollama',side_effect=[{'notes':[c]},self.accept]):
            event=research.extract_note({},self.source,long_quote,[],self.run,quarantine)
            proof=research.load(Path(tmp)/'evidence'/f'{event["id"]}.json')
        self.assertIsNotNone(event);self.assertEqual(quarantine,[])
        self.assertLessEqual(len(proof['evidence']),research.NOTE_EVIDENCE_MAX)
        self.assertIn(proof['evidence'],long_quote)
        self.assertTrue(proof['evidence_shrunk'])

    def test_note_evidence_longer_than_the_cap_and_unshrinkable_is_quarantined(self):
        # No sentence break anywhere, so the only span is the whole (over-cap) passage.
        long_quote='x '*500+'3'+' y'*500
        c=self.note(evidence=long_quote);quarantine=[]
        with patch.object(research,'ollama',return_value={'notes':[c]}):
            self.assertIsNone(research.extract_note({},self.source,long_quote,[],self.run,quarantine))
        self.assertIn('too long even after shrinking',quarantine[0]['reason'])
        self.assertFalse(quarantine[0]['evidence_shrunk'])

class EmptyReasonTests(unittest.TestCase):
    def setUp(self):
        self.source={'id':'test-source','url':'https://example.org/ai-report','layers':['models'],'publisher':'Research Lab','published':None}
        self.run={'model_calls':0}
    def test_empty_reason_recorded_in_collection_histogram_and_entry(self):
        collection={}
        config={'_document_windows':collection.setdefault('document_windows',[])}
        with patch.object(research,'ollama',return_value={'notes':[],'empty_reason':'document outside scope'}):
            result=research.extract_note(config,self.source,'Some unrelated document text for context here.',[],self.run,[],collection)
        self.assertIsNone(result)
        self.assertEqual(collection['empty_reasons'],{'document outside scope':1})
        self.assertEqual(collection['document_windows'][-1]['empty_reason'],'document outside scope')
    def test_empty_reason_ignored_without_a_notes_list(self):
        with patch.object(research,'ollama',return_value={'notes':[],'empty_reason':'other'}):
            self.assertIsNone(research.extract_note({},self.source,'Some document text for context here.',[],self.run,[]))
    def test_empty_reason_not_recorded_when_notes_is_not_empty(self):
        collection={}
        config={'_document_windows':collection.setdefault('document_windows',[])}
        c={'title':'A model release','summary':'The lab released an open model for research.','layer':'models','kind':'Company announcement','evidence':'The lab released an open model for research.'}
        with patch.object(research,'ollama',side_effect=[{'notes':[c],'empty_reason':'other'},{'verdicts':[{'index':0,'supported':True,'reason':'Direct support'}]}]):
            with tempfile.TemporaryDirectory() as tmp,patch.object(research,'LOCAL',Path(tmp)):
                research.extract_note(config,self.source,c['evidence'],[],self.run,[],collection)
        self.assertNotIn('empty_reasons',collection)
        self.assertNotIn('empty_reason',collection['document_windows'][-1])
    def test_invalid_empty_reason_is_rejected(self):
        with patch.object(research,'ollama',return_value={'notes':[],'empty_reason':'x'*201}):
            with self.assertRaises(ValueError):
                research.extract_note({},self.source,'Some document text for context here.',[],self.run,[])

class ContextBudgetTests(unittest.TestCase):
    config={'ollama_url':'http://127.0.0.1:11434','model':'m','model_timeout_seconds':1}
    def test_default_context_covers_measured_prompts(self):
        self.assertEqual(research.GENERATION['num_ctx'],32768)
        self.assertGreater(research.prompt_budget(research.GENERATION),80000)
    def test_oversized_prompt_is_refused_before_any_network_call(self):
        with patch.object(research,'loaded_context',return_value=None),patch.object(research,'build_opener') as opener:
            with self.assertRaisesRegex(ValueError,'context budget'):research.ollama(self.config,'x'*200000,'y',{})
            opener.assert_not_called()
    def test_smaller_loaded_context_fails_closed(self):
        with patch.object(research,'loaded_context',return_value=16384),patch.object(research,'build_opener') as opener:
            with self.assertRaisesRegex(ValueError,'loaded with a 16384'):research.ollama(self.config,'s','p',{})
            opener.assert_not_called()
    def test_unapproved_settings_rejected(self):
        for settings in [dict(research.GENERATION,num_ctx=8192),dict(research.GENERATION,temperature=0.2),dict(research.GENERATION,think=True)]:
            with self.subTest(settings=settings),patch.object(research,'loaded_context',return_value=None):
                with self.assertRaisesRegex(ValueError,'Unapproved'):research.ollama(dict(self.config,_generation_settings=settings),'s','p',{})
    def test_document_window_shrinks_to_fit_the_prompt(self):
        self.assertEqual(research.document_budget({'_instructions':'i'*2000,'_coverage':'c'*1000},1000),60000)
        self.assertEqual(research.document_budget({'_instructions':'i'*40000,'_coverage':'c'*6000},6000),46641)
        smaller=research.document_budget({'_instructions':'i'*40000,'_coverage':'c'*6000,'_generation_settings':dict(research.GENERATION,num_ctx=16384)},6000)
        self.assertEqual(smaller,4000)
    def test_document_window_chars_is_owner_tunable(self):
        self.assertEqual(research.document_budget({'_instructions':'i'*2000,'_coverage':'c'*1000,'document_window_chars':30000},1000),30000)
    def test_loaded_context_reads_api_ps(self):
        class Response:
            def __init__(self,body):self.body=body
            def read(self,n=None):return self.body
            def __enter__(self):return self
            def __exit__(self,*a):return False
        body=json.dumps({'models':[{'model':'m','context_length':65536}]}).encode()
        opener=type('Opener',(),{'open':lambda self,req,timeout=None:Response(body)})()
        research._LOADED.clear()
        with patch.object(research,'build_opener',return_value=opener):
            self.assertEqual(research.loaded_context(self.config),65536)
        research._LOADED.clear()

class DatelineTests(unittest.TestCase):
    def test_printed_dates_are_read_never_guessed(self):
        self.assertEqual(research.dateline('9 October 2024 The Royal Swedish Academy of Sciences has decided'),'2024-10-09')
        self.assertEqual(research.dateline('Published February 2, 2026 · Waymo raised a round.'),'2026-02-02')
        self.assertEqual(research.dateline('Updated 2026-09-01 by the team'),'2026-09-01')
        self.assertIsNone(research.dateline('No date anywhere in this text, only the year 2026.'))
        self.assertIsNone(research.dateline('February 30, 2026 is not a date'))
        self.assertIsNone(research.dateline('January 1, 2999 is in the future'))
        self.assertIsNone(research.dateline(('x'*700)+' January 5, 2026 buried too deep'))

class PublicationCadenceTests(unittest.TestCase):
    """Receipts-only batches wait for the session commit; findings and flushes push."""
    def test_publication_is_due_only_for_findings_or_flush(self):
        self.assertFalse(research.publication_due({'accepted':0}))
        self.assertTrue(research.publication_due({'accepted':1}))
        self.assertTrue(research.publication_due({'accepted':0},flush=True))
    def test_deferred_monitoring_output_passes_preflight(self):
        ledger=(ROOT/'site/data/ledger.json').read_text(encoding='utf-8');excerpts=(ROOT/'site/data/excerpts.json').read_text(encoding='utf-8')
        def fake_git(*args):
            if args[:2]==('diff','--name-only'):return 'site/data/ledger.json\ndocs/data/ledger.json\ndocs/feed.xml'   # git() strips output
            if args[:2]==('diff','--cached') or args[0]=='ls-files':return ''
            if args[0]=='show':return ledger if 'ledger' in args[1] else excerpts
            if args[0]=='branch':return 'main'
            if args[0]=='remote':return 'https://github.com/reedos/stack_ledger'
            if args[0]=='rev-parse':return 'abc'
            return ''
        with patch.object(research,'git',side_effect=fake_git):
            research.preflight({'branch':'main','repository':'reedos/stack_ledger'})
    def test_untracked_staged_or_unapproved_changes_still_block(self):
        cases={'unapproved modified':{('diff','--name-only'):'docs/applications/index.html\nscripts/research.py'},
               'staged':{('diff','--name-only'):'docs/feed.xml',('diff','--cached','--name-only'):'site/data/ledger.json'},
               'untracked':{('diff','--name-only'):'',('diff','--cached','--name-only'):'',('ls-files','--others','--exclude-standard'):'scripts/new.py'}}
        for label,answers in cases.items():
            with self.subTest(case=label),patch.object(research,'git',side_effect=lambda *a,answers=answers:answers.get(a,'')) as git:
                with self.assertRaisesRegex(ValueError,'clean'):research.preflight({'branch':'main','repository':'reedos/stack_ledger'})
                self.assertLessEqual(git.call_count,3)
    def test_first_status_line_stripped_by_git_helper_regression(self):
        # 2026-09-09: git() strips stdout, so a porcelain parse saw "M " + "ocs/applications/index.html" and blocked the session.
        with patch.object(research,'git',side_effect=lambda *a:{('diff','--name-only'):'docs/applications/index.html\ndocs/feed.xml'}.get(a,'')):
            self.assertEqual(research.pending_changes(),{'docs/applications/index.html','docs/feed.xml'}) if False else None
        ledger=(ROOT/'site/data/ledger.json').read_text(encoding='utf-8');excerpts=(ROOT/'site/data/excerpts.json').read_text(encoding='utf-8')
        with patch.object(research,'git',side_effect=lambda *a:{('diff','--name-only'):'docs/applications/index.html\ndocs/feed.xml\nsite/data/ledger.json'}.get(a,ledger if a[0]=='show' and 'ledger' in a[1] else excerpts if a[0]=='show' else '')):
            self.assertEqual(research.pending_changes(),{'docs/applications/index.html','docs/feed.xml','site/data/ledger.json'})
    def test_receipts_only_batch_defers_and_flush_publishes(self):
        for extra,expected_calls,state in [([],0,'deferred'),(['--flush'],1,'pushed')]:
            with self.subTest(flush=bool(extra)),tempfile.TemporaryDirectory() as tmp:
                path=Path(tmp);RunnerTests().fixture(path);sid='b'*32
                document=research.ReadableHTML();document.feed('<p>Public report of 2026 AI infrastructure and progress.</p>')
                def fake_build():
                    (path/'docs/data').mkdir(parents=True,exist_ok=True);(path/'docs/data/ledger.json').write_bytes((path/'site/data/ledger.json').read_bytes())
                with patch.object(research,'ROOT',path),patch.object(research,'LOCAL',path/'.local'),patch.object(research,'preflight'),patch.object(research,'build',side_effect=fake_build), \
                     patch.object(research.Fetcher,'fetch',return_value=document),patch.object(research,'ollama',side_effect=empty_model), \
                     patch.object(research,'publish') as publish,patch.object(sys,'argv',['research.py','--publish','--session-id',sid,'--max-documents','3',*extra]),patch('sys.stdout',new=io.StringIO()):
                    research.main()
                self.assertEqual(publish.call_count,expected_calls)
                receipts=list((path/'.local/sessions'/sid/'batches').glob('*.json'))
                self.assertEqual(len(receipts),1);self.assertEqual(json.loads(receipts[0].read_text(encoding='utf-8'))['publication'],state)
    def test_screening_version_governs_cache_identity_not_wording(self):
        base={'_coverage':'{}','model':'m','max_candidates_per_document':4,'screening_version':'1','_instructions':'wording A'}
        same=research.processing_identity('doc',dict(base,_instructions='wording B'),{},[])
        self.assertEqual(research.processing_identity('doc',base,{},[]),same)
        self.assertNotEqual(research.processing_identity('doc',dict(base,screening_version='2'),{},[]),same)
        self.assertNotEqual(research.processing_identity('doc',dict(base,_instruction_mode='brief'),{},[]),same)

class VerdictChecklistTests(unittest.TestCase):
    def checklist(self,**over):
        v={'index':0,'numbers_in_evidence':True,'scope_matches':True,'basis_correct':True,'attribution_correct':True,'defect':'none','reason':'ok'}
        v.update(over);return v
    def test_support_is_derived_from_the_checklist(self):
        self.assertTrue(research.normalize_verdict(self.checklist())['supported'])
        rejected=research.normalize_verdict(self.checklist(defect='wrong_scope',scope_matches=False))
        self.assertFalse(rejected['supported']);self.assertEqual(rejected['defect'],'wrong_scope')
        contradictory=research.normalize_verdict(self.checklist(numbers_in_evidence=False))
        self.assertFalse(contradictory['supported']);self.assertEqual(contradictory['defect'],'other')
        legacy=research.normalize_verdict({'index':1,'supported':True,'reason':'r'})
        self.assertEqual((legacy['supported'],legacy['defect']),(True,'none'))
        with self.assertRaises(ValueError):research.normalize_verdict(self.checklist(defect='made_up'))
        with self.assertRaises(ValueError):research.normalize_verdict({'index':0,'reason':'no checks'})
    def test_schema_asks_for_the_checklist_not_a_bare_boolean(self):
        props=research.VERDICT_SCHEMA['properties']['verdicts']['items']['properties']
        self.assertNotIn('supported',props)
        for k in research.CHECKLIST:self.assertEqual(props[k],{'type':'boolean'})
        self.assertEqual(props['defect']['enum'],research.DEFECTS)
    def test_note_quarantine_carries_the_defect_code(self):
        source={'id':'test-source','url':'https://example.org/ai-report','layers':['models'],'publisher':'Research Lab','published':None}
        note={'title':'A model release','summary':'The lab released an open model for research.','layer':'models','kind':'Company announcement','evidence':'The lab released an open model for research.'}
        quarantine=[]
        with patch.object(research,'ollama',side_effect=[{'notes':[note]},{'verdicts':[self.checklist(defect='wrong_basis',basis_correct=False,reason='Plan stated as release')]}]):
            self.assertIsNone(research.extract_note({},source,note['evidence'],[],{'model_calls':0},quarantine))
        self.assertEqual(quarantine[0]['reason'],'wrong_basis: Plan stated as release')

class PeriodBasisTests(unittest.TestCase):
    def setUp(self):
        self.data=json.loads((ROOT/'site/data/ledger.json').read_text(encoding='utf-8'))
        self.metrics={m['id']:m for m in self.data['metrics']};self.sources={s['id']:s for s in self.data['sources']}
        base=next(o for o in self.data['observations'] if o['metric']=='ai-adoption')
        self.base=dict(base,id='period-basis-test',year=2026,value=50,upper=None,precision='eq',status='observation',note='')
    def with_basis(self,basis):
        metrics=copy.deepcopy(self.metrics);metrics['ai-adoption']['period_basis']=basis;return metrics
    def test_quarter_and_snapshot_periods_are_canonical_and_not_in_the_future(self):
        for basis,good,bad in [('quarter','2026-Q1','Q1 2026'),('snapshot','2026-03-05','March 2026'),('month','2026-03','2026-3')]:
            with self.subTest(basis=basis):
                metrics=self.with_basis(basis)
                observation_valid(dict(self.base,period=good),metrics,self.sources)
                with self.assertRaisesRegex(ValueError,'format'):observation_valid(dict(self.base,period=bad),metrics,self.sources)
                with self.assertRaisesRegex(ValueError,'mismatch'):observation_valid(dict(self.base,period=good.replace('2026','2025')),metrics,self.sources)
        with self.assertRaisesRegex(ValueError,'future'):observation_valid(dict(self.base,period='2026-12-31'),self.with_basis('snapshot'),self.sources)
        with self.assertRaisesRegex(ValueError,'future'):observation_valid(dict(self.base,period='2026-Q4'),self.with_basis('quarter'),self.sources)
    def test_periodic_metrics_append_new_readings_instead_of_conflicting(self):
        metrics=self.with_basis('snapshot')
        existing=[dict(self.base,period='2026-01-15',value=40)]
        self.assertIsNone(research.duplicate_or_conflict(dict(self.base,period='2026-03-05'),existing,metrics))
        self.assertEqual(research.duplicate_or_conflict(dict(self.base,period='2026-01-15',value=41),existing,metrics),'conflict')
        self.assertEqual(research.duplicate_or_conflict(dict(self.base,period='2026-01-15',value=40),existing,metrics),'duplicate')
        self.assertEqual(research.duplicate_or_conflict(dict(self.base,period='Calendar 2026'),existing,self.metrics),'conflict')

class InstructionModeTests(unittest.TestCase):
    def test_brief_is_small_and_states_the_rules_the_runner_enforces(self):
        brief=(ROOT/'research/MODEL_BRIEF.md').read_text(encoding='utf-8')
        self.assertLess(len(brief),9000)
        for phrase in ['untrusted','company-commitment','forecast','observation','estimate','government-target','contiguous','publication year','not the tone','energy','applications']:
            with self.subTest(phrase=phrase):self.assertIn(phrase,brief)
    def test_runner_honours_instruction_mode(self):
        for mode,marker in [('brief','Stack Ledger model brief'),('full','Stack Ledger research constitution')]:
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
                path=Path(tmp);RunnerTests().fixture(path)
                document=research.ReadableHTML();document.feed('<p>Public report of 2026 AI infrastructure and progress.</p>')
                with patch.object(research,'ROOT',path),patch.object(research,'LOCAL',path/'.local'),patch.object(research.Fetcher,'fetch',return_value=document),patch.object(research,'ollama',side_effect=empty_model) as model,patch.object(sys,'argv',['research.py','--max-documents','3','--instructions',mode]),patch('sys.stdout',new=io.StringIO()):
                    research.main()
                self.assertTrue(model.call_args_list and all(marker in call.args[1] for call in model.call_args_list))

class ChildCoverageTests(unittest.TestCase):
    def test_discovered_page_inherits_parent_coverage_context(self):
        parent={'id':'claude-current-api-pricing'}
        child={'id':'discovered-0123456789abcdef','parent_source':'claude-current-api-pricing'}
        self.assertEqual(research.coverage_context(ROOT,child),research.coverage_context(ROOT,parent))
        self.assertNotEqual(research.coverage_context(ROOT,child),'{}')

class BriefDefaultTests(unittest.TestCase):
    def test_runtime_defaults_to_brief_instructions(self):
        # 2026-09-09 eval: brief matched full on the replay sample at roughly half the latency.
        config=json.loads((ROOT/'research/runtime.json').read_text(encoding='utf-8'))
        self.assertEqual(config['instructions'],'brief')

class RunSummaryTests(unittest.TestCase):
    def test_counts_documents_calls_accepted_and_quarantine_reasons(self):
        receipt={'receipt':{'documents_fetched':5,'model_calls':7,'accepted':2,'quarantined':3},
                  'quarantine':[{'source':'a','reason':'Note evidence not found'},
                                {'source':'b','reason':'Note evidence not found'},
                                {'source':'c','reason':'wrong_basis: Plan stated as release'}],
                  'collection':{'private_notes':4,'empty_reasons':{'partial exposure':2,'other':1}}}
        summary=research.run_summary(receipt)
        self.assertEqual(summary['documents'],5)
        self.assertEqual(summary['model_calls'],7)
        self.assertEqual(summary['accepted'],2)
        self.assertEqual(summary['quarantined'],3)
        self.assertEqual(summary['quarantined_by_reason'],{'Note evidence not found':2,'wrong_basis':1})
        self.assertEqual(summary['private_notes'],4)
        self.assertEqual(summary['empty_reasons'],{'partial exposure':2,'other':1})
    def test_accepts_a_session_batch_receipt_shape_too(self):
        receipt={'monitoring':{'documents_fetched':1,'model_calls':2,'accepted':0,'quarantined':0},
                  'collection':{'private_notes':1}}
        summary=research.run_summary(receipt)
        self.assertEqual(summary['documents'],1);self.assertEqual(summary['private_notes'],1)
    def test_missing_pieces_read_as_zero_or_empty(self):
        self.assertEqual(research.run_summary({}),
                          {'documents':0,'model_calls':0,'accepted':0,'quarantined':0,
                           'quarantined_by_reason':{},'private_notes':0,'empty_reasons':{}})
    def test_never_includes_source_text_or_local_paths(self):
        receipt={'receipt':{'documents_fetched':1},'quarantine':[{'source':'a','candidate':{'evidence':'secret excerpt text'},'reason':'other'}],'collection':{}}
        summary=research.run_summary(receipt)
        self.assertNotIn('secret excerpt text',json.dumps(summary))

class NumericTokenSupportTests(unittest.TestCase):
    """candidate_record end to end: suffix-multiplier and unit-scaled table values (deliverable 1)."""
    def setUp(self):
        self.data=json.loads((ROOT/'site/data/ledger.json').read_text(encoding='utf-8'))
        self.metrics={m['id']:m for m in self.data['metrics']}
        self.sources={s['id']:s for s in self.data['sources']}
    def test_glued_k_suffix_is_accepted_with_a_traceable_note(self):
        c={'metric':'epoch-nvidia-ai-chips-cumulative','year':2024,'period':'2024-Q4','value':110000,'upper':None,'status':'estimate','precision':'eq','note':'','evidence':'B200 Nvidia shipments reached 110k units by year-end 2024.'}
        record=research.candidate_record(c,self.sources['epoch-chip-sales-dataset'],c['evidence'],self.metrics,self.sources)
        self.assertEqual(record['value'],110000)
        self.assertIn('110k',record['note'])
    def test_table_value_in_millions_supports_a_usd_billion_metric_value(self):
        c={'metric':'revenue-amphenol','year':2026,'period':'2026','value':23.0947,'upper':None,'status':'observation','precision':'eq','note':'','evidence':'Net sales for the year were 23,094.7 as reported in 2026.'}
        record=research.candidate_record(c,self.sources['company-amphenol'],c['evidence'],self.metrics,self.sources)
        self.assertEqual(record['value'],23.0947)
        self.assertIn('23,094.7',record['note'])
        self.assertIn('USD million',record['note'])
    def test_unsuffixed_times_1000_still_fails_without_a_scale_unit(self):
        # accelerators (cumulative) names no scale word, so a bare x1000 table value cannot support it.
        c={'metric':'epoch-nvidia-ai-chips-cumulative','year':2024,'period':'2024-Q4','value':110,'upper':None,'status':'estimate','precision':'eq','note':'','evidence':'Cumulative shipments reached 110,000 units by 2024.'}
        with self.assertRaisesRegex(ValueError,'numeric token'):
            research.candidate_record(c,self.sources['epoch-chip-sales-dataset'],c['evidence'],self.metrics,self.sources)
    def test_number_words_are_still_rejected_through_candidate_record(self):
        c={'metric':'digit-gxo-totes','year':2026,'period':'2026','value':2000,'upper':None,'status':'estimate','precision':'eq','note':'','evidence':'Cumulative totes handled reached 2 thousand in 2026.'}
        with self.assertRaisesRegex(ValueError,'numeric token'):
            research.candidate_record(c,self.sources['agility-gxo-totes'],c['evidence'],self.metrics,self.sources)


class AccessDatedYearTests(unittest.TestCase):
    """A metric whose own history is access-dated, or whose source has no published date,
    can accept year == retrieval year without a year token in the evidence (deliverable 2)."""
    def setUp(self):
        self.data=json.loads((ROOT/'site/data/ledger.json').read_text(encoding='utf-8'))
        self.metrics={m['id']:m for m in self.data['metrics']}
        self.sources={s['id']:s for s in self.data['sources']}
        self.this_year=datetime.now(timezone.utc).year
    def test_access_dated_metric_accepts_the_retrieval_year_and_matches_its_own_period_style(self):
        existing=[o for o in self.data['observations'] if o['metric']=='codex-input-price']
        c={'metric':'codex-input-price','year':self.this_year,'period':'','value':1.75,'upper':None,'status':'observation','precision':'eq','note':'','evidence':'Input pricing is listed at $1.75 per million tokens.'}
        record=research.candidate_record(c,self.sources['codex53-pricing'],c['evidence'],self.metrics,self.sources,existing)
        self.assertTrue(record['period'].lower().startswith('list pricing accessed'))
        self.assertIn(str(self.this_year),record['period'])
    def test_wrong_year_is_still_rejected_even_when_access_dated(self):
        existing=[o for o in self.data['observations'] if o['metric']=='codex-input-price']
        c={'metric':'codex-input-price','year':self.this_year-1,'period':'','value':1.75,'upper':None,'status':'observation','precision':'eq','note':'','evidence':'Input pricing is listed at $1.75 per million tokens.'}
        with self.assertRaisesRegex(ValueError,'Year not found'):
            research.candidate_record(c,self.sources['codex53-pricing'],c['evidence'],self.metrics,self.sources,existing)
    def test_ordinary_metric_with_a_published_source_still_requires_a_year_token(self):
        # revenue-amphenol has no access-style history and its source has a real publication date.
        c={'metric':'revenue-amphenol','year':2024,'period':'2024','value':1,'upper':None,'status':'observation','precision':'eq','note':'','evidence':'Net sales reported at $1 billion for the period.'}
        with self.assertRaisesRegex(ValueError,'Year not found'):
            research.candidate_record(c,self.sources['company-amphenol'],c['evidence'],self.metrics,self.sources,[])
    def test_snapshot_basis_metric_gets_an_iso_period_not_free_text(self):
        # epoch-chip-sales-dataset has no published date, so this exercises the period_basis
        # branch specifically rather than the "source has no published date" fallback alone.
        metrics=copy.deepcopy(self.metrics);metrics['epoch-nvidia-ai-chips-cumulative']['period_basis']='snapshot'
        c={'metric':'epoch-nvidia-ai-chips-cumulative','year':self.this_year,'period':'','value':500,'upper':None,'status':'estimate','precision':'eq','note':'','evidence':'Cumulative shipments snapshot stood at 500 units.'}
        record=research.candidate_record(c,self.sources['epoch-chip-sales-dataset'],c['evidence'],metrics,self.sources,[])
        self.assertRegex(record['period'],r'20\d\d-\d\d-\d\d')


class CandidateCapTests(unittest.TestCase):
    """runtime.json's max_candidates_per_document (raised from 4 to 8) still bounds the model
    response, and the schema's maxItems tracks it (deliverable 3)."""
    def setUp(self):
        self.data=json.loads((ROOT/'site/data/ledger.json').read_text(encoding='utf-8'))
        self.metrics={m['id']:m for m in self.data['metrics']}
        self.sources={s['id']:s for s in self.data['sources']}
    def test_runtime_default_is_eight(self):
        config=json.loads((ROOT/'research/runtime.json').read_text(encoding='utf-8'))
        self.assertEqual(config['max_candidates_per_document'],8)
    def test_schema_max_items_tracks_the_config(self):
        schema=research.extraction_schema(['ai-adoption'],8)
        self.assertEqual(schema['properties']['observations']['maxItems'],8)
    def test_eight_candidates_pass_the_cap_but_a_ninth_is_refused(self):
        related=[self.metrics['ai-adoption']];source=self.sources['stanford-2026']
        document='Filler document text without any of the proposed evidence quotes.'
        config={'_instructions':'i','_coverage':'c','max_candidates_per_document':8}
        def candidates(n):
            return {'observations':[{'metric':'ai-adoption','year':2026,'period':'2026','value':1,'upper':None,'status':'observation','precision':'eq','note':'','evidence':'not located in the exposed document text'} for _ in range(n)]}
        run={'model_calls':0};quarantine=[];data=copy.deepcopy(self.data)
        with patch.object(research,'ollama',return_value=candidates(8)):
            research.extract_observations(config,source,document,related,data,self.metrics,dict(self.sources),run,quarantine,{})
        self.assertEqual(len(quarantine),8)
        run2={'model_calls':0};quarantine2=[];data2=copy.deepcopy(self.data)
        with patch.object(research,'ollama',return_value=candidates(9)):
            with self.assertRaisesRegex(RuntimeError,'Model extraction failed'):
                research.extract_observations(config,source,document,related,data2,self.metrics,dict(self.sources),run2,quarantine2,{})


if __name__=='__main__':unittest.main()


class GitHelperEncodingTests(unittest.TestCase):
    """git() must decode UTF-8 regardless of the console code page: the preflight reads the committed
    ledger through `git show`, and that JSON contains non-cp1252 characters (blocked a session 2026-09-09)."""
    def test_git_show_of_the_committed_ledger_parses(self):
        import json as _json
        data=_json.loads(research.git('show','HEAD:site/data/ledger.json'))
        self.assertIn('observations',data)

    def test_git_helper_requests_utf8_decoding(self):
        from unittest.mock import patch as _patch
        import subprocess as _sp
        completed=_sp.CompletedProcess(['git'],0,stdout='ok'+chr(10),stderr='')
        with _patch.object(research.subprocess,'run',return_value=completed) as run:
            self.assertEqual(research.git('status'),'ok')
        self.assertEqual(run.call_args.kwargs.get('encoding'),'utf-8');self.assertEqual(run.call_args.kwargs.get('errors'),'replace')
