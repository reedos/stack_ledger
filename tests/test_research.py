import copy
import json
import sys
import tempfile
import io
import unittest
from datetime import datetime, date, timezone
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
        self.registry=json.loads((ROOT/'research/sources.json').read_text(encoding='utf-8'))
        self.metrics={m['id']:m for m in self.data['metrics']}
        self.sources={s['id']:s for s in self.data['sources']}
        self.candidate={'metric':'ai-adoption','year':2026,'period':'2026','value':90,'upper':None,'status':'observation','precision':'eq','note':'','evidence':'In 2026, 90 percent of surveyed organizations reported AI use.'}
    def record(self,candidate=None,document=None,source_id='stanford-2026'):
        from source_policy import collection_for
        c=candidate or self.candidate
        source=self.sources[source_id]
        return research.candidate_record(c,source,document or c['evidence'],self.metrics,self.sources,policy=collection_for(self.registry,source))
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
            # Pinned sources (feeds now sort first in the default queue -- deliverable 6 --
            # and feed pages never reach note/metric extraction): together these five span
            # every layer, so a clean no-op batch can still reach status 'success'.
            sources=['doe-demand','company-nvidia','msft-wisconsin','stanford-cost','company-microsoft']
            with patch.object(research,'ROOT',path),patch.object(research,'LOCAL',path/'.local'),patch.object(research.Fetcher,'fetch',return_value=document),patch.object(research,'ollama',side_effect=empty_model),patch.object(sys,'argv',['research.py','--sources',*sources]),patch('sys.stdout',new=io.StringIO()):
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
            sources=['doe-demand','company-nvidia','msft-wisconsin','stanford-cost','company-microsoft']
            with patch.object(research,'ROOT',path),patch.object(research,'LOCAL',path/'.local'),patch.object(research.Fetcher,'fetch',return_value=document),patch.object(research,'ollama',side_effect=TimeoutError('fixture timeout')),patch.object(sys,'argv',['research.py','--sources',*sources]),patch('sys.stdout',new=io.StringIO()):
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
            note={'title':'A research development','summary':'The lab reported 42 new facilities in 2026.','layer':'energy','kind':'Research finding','evidence':'In 2026, the lab reported new AI infrastructure progress and 42 new facilities.'}
            def fake_fetch(url):
                # Distinct per-URL text: the review ledger's note identity (deliverable 1) is
                # keyed on document text alone, so three identical documents would only ever
                # reach extract_note once regardless of the per-run cap being tested here.
                d=research.ReadableHTML();d.feed(f'<p>Filler context for {url}. {note["evidence"]}</p>')
                return d
            def fake_model(cfg,system,prompt,schema):
                if schema==research.NOTE_SCHEMA:return {'notes':[note]}
                if schema==research.VERDICT_SCHEMA:return {'verdicts':[{'index':0,'supported':True,'reason':'Direct support'}]}
                return {'observations':[]}
            # All three: no parent_source, excerpts disabled in policy, but each has a linked
            # metric -- the old gate ("publishable or not related") skipped every one of them.
            sources=['doe-demand','company-nvidia','msft-wisconsin']
            with patch.object(research,'ROOT',path),patch.object(research,'LOCAL',path/'.local'),patch.object(research.Fetcher,'fetch',side_effect=fake_fetch), \
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
class ReviewLedgerIdentityTests(unittest.TestCase):
    """Deliverable 1: two independent lane identities, and the ledger built on them."""
    def test_note_rules_bump_never_invalidates_a_metrics_review_and_vice_versa(self):
        note_a=research.note_identity('doc','1');note_b=research.note_identity('doc','2')
        metrics_a=research.metrics_identity('doc',['m1'],'1');metrics_b=research.metrics_identity('doc',['m1'],'2')
        self.assertNotEqual(note_a,note_b)
        self.assertNotEqual(metrics_a,metrics_b)
        # A note-rules bump changes only the note identity; a metrics-rules bump changes
        # only the metrics identity. Neither ever collides with the other lane's key.
        self.assertEqual(research.metrics_identity('doc',['m1'],'1'),metrics_a)
        self.assertEqual(research.note_identity('doc','1'),note_a)
        self.assertNotIn(metrics_a,{note_a,note_b})
    def test_metrics_identity_ignores_metric_order_but_not_membership(self):
        self.assertEqual(research.metrics_identity('doc',['a','b'],'1'),research.metrics_identity('doc',['b','a'],'1'))
        self.assertNotEqual(research.metrics_identity('doc',['a','b'],'1'),research.metrics_identity('doc',['a'],'1'))
    def test_identity_changes_with_document_text(self):
        self.assertNotEqual(research.note_identity('doc-a','1'),research.note_identity('doc-b','1'))
        self.assertNotEqual(research.metrics_identity('doc-a',['m'],'1'),research.metrics_identity('doc-b',['m'],'1'))
    def test_ledger_records_and_reports_outcome(self):
        reviews={}
        key=research.note_identity('doc','1')
        self.assertIsNone(research.already_reviewed(reviews,key))
        entry=research.record_review(reviews,key,'note','test-source','empty',empty_reason='document outside scope')
        self.assertEqual(entry['outcome'],'empty');self.assertEqual(entry['empty_reason'],'document outside scope')
        found=research.already_reviewed(reviews,key)
        self.assertEqual(found['outcome'],'empty');self.assertIn('reviewed_at',found)
    def test_load_reviews_of_a_missing_file_is_empty(self):
        self.assertEqual(research.load_reviews(ROOT/'.local'/'no-such-reviews-file.json'),{})

class NothingNewTests(unittest.TestCase):
    """Deliverable 7: once every due source is already reviewed, the batch is nothing_new."""
    def run_batch(self,path,sources,build_fn):
        document=research.ReadableHTML();document.feed('<p>Public report of 2026 AI infrastructure and progress.</p>')
        with patch.object(research,'ROOT',path),patch.object(research,'LOCAL',path/'.local'),patch.object(research,'build',side_effect=build_fn), \
             patch.object(research.Fetcher,'fetch',return_value=document),patch.object(research,'ollama',side_effect=empty_model), \
             patch.object(sys,'argv',['research.py','--apply','--sources',*sources]),patch('sys.stdout',new=io.StringIO()):
            return research.main()
    def test_second_apply_of_the_same_documents_exits_nothing_new(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp);RunnerTests().fixture(path)
            def fake_build():
                (path/'docs/data').mkdir(parents=True,exist_ok=True);(path/'docs/data/ledger.json').write_bytes((path/'site/data/ledger.json').read_bytes())
            sources=['doe-demand','company-nvidia','stanford-cost']
            self.assertEqual(self.run_batch(path,sources,fake_build),0)
            self.assertEqual(self.run_batch(path,sources,fake_build),2)
            receipts=sorted((path/'.local/runs').glob('*.json'),key=lambda p:p.stat().st_mtime)
            second=research.load(receipts[-1])
            self.assertEqual(second['collection']['already_reviewed'],3)
            self.assertEqual(second['collection']['model_documents'],0)
            self.assertEqual(second['receipt']['source_failures'],[])
    def test_not_attempts_batch_also_reports_nothing_new(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp);RunnerTests().fixture(path);sid='c'*32
            with patch.object(research,'ROOT',path),patch.object(research,'LOCAL',path/'.local'), \
                 patch.object(research.Fetcher,'due',return_value=False), \
                 patch.object(sys,'argv',['research.py','--session-id',sid,'--max-documents','3']),patch('sys.stdout',new=io.StringIO()):
                self.assertEqual(research.main(),2)
            receipts=list((path/'.local/sessions'/sid/'batches').glob('*.json'))
            self.assertEqual(len(receipts),1)
            self.assertEqual(json.loads(receipts[0].read_text(encoding='utf-8'))['status'],'nothing_new')
    def test_an_all_304_batch_is_partial_and_idle_never_failed(self):
        # Regression: zero reviewed documents with zero source_failures (every attempted
        # source came back 304) must never be reported as a genuine model/research failure.
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp);RunnerTests().fixture(path);sid='d'*32
            with patch.object(research,'ROOT',path),patch.object(research,'LOCAL',path/'.local'), \
                 patch.object(research.Fetcher,'fetch',side_effect=research.Unchanged('test')), \
                 patch.object(sys,'argv',['research.py','--session-id',sid,'--sources','doe-demand','company-nvidia']),patch('sys.stdout',new=io.StringIO()):
                self.assertEqual(research.main(),2)
            receipts=list((path/'.local/sessions'/sid/'batches').glob('*.json'))
            receipt=json.loads(receipts[0].read_text(encoding='utf-8'))
            self.assertEqual(receipt['monitoring']['status'],'partial')
            self.assertEqual(receipt['monitoring']['source_failures'],[])
            self.assertEqual(receipt['collection']['unchanged_304'],2)
            self.assertEqual(receipt['status'],'nothing_new')

class IdleTopUpTests(unittest.TestCase):
    """Deliverable 3: before conceding nothing_new, force a feed re-poll and retry
    stale-metric sources past their ordinary cooldown -- both bypassed in the normal pass
    here, so any accepted-into-review-queue document below can only have come from the
    idle top-up, not the ordinary due-list walk."""
    def test_idle_pass_force_repolls_a_feed_the_ordinary_pass_could_not_reach(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp);RunnerTests().fixture(path)
            registry=research.load(path/'research/sources.json')
            feed={'id':'test-feed','publisher':'Test','title':'Test feed','url':'https://feed.example/rss',
                  'published':None,'layers':['energy'],'license':'x','index':True}
            policy={'rank':4,'region_book':'global','company_id':None,'claim_type':'other','cadence':'daily',
                    'weekday':0,'path_prefixes':['/story/'],'topics':['ai'],'excerpts':False}
            registry['sources'].append(feed);registry['collection']['test-feed']=policy
            research.save(path/'research/sources.json',registry)
            def fake_due(url,refresh=False,feed_poll_seconds=None):
                # The ordinary pass never sees feed_poll_seconds==0 (deliverable 3 forces it
                # only in the idle top-up) and never sees the discovered child at all until
                # the feed that names it has been fetched -- so True here can only be reached
                # from the idle top-up's forced re-poll, not the normal due-list walk.
                if feed_poll_seconds==0 and url==feed['url']:return True
                return url=='https://feed.example/story/1-ai'
            def fake_fetch(url):
                d=research.ReadableHTML()
                if url==feed['url']:d.feed('<p>Filler content.</p><a href="https://feed.example/story/1-ai">Story 1</a>')
                else:d.feed('<p>Public report of 2026 AI infrastructure progress at the story link.</p>')
                return d
            with patch.object(research,'ROOT',path),patch.object(research,'LOCAL',path/'.local'), \
                 patch.object(research.Fetcher,'due',side_effect=fake_due), \
                 patch.object(research.Fetcher,'fetch',side_effect=fake_fetch), \
                 patch.object(research,'ollama',side_effect=empty_model), \
                 patch.object(sys,'argv',['research.py','--max-documents','5']),patch('sys.stdout',new=io.StringIO()):
                research.main()
            receipt=research.load(sorted((path/'.local/runs').glob('*.json'))[-1])
            collection=receipt['collection']
            self.assertTrue(collection['idle_pass'])
            self.assertEqual(collection['idle_feeds_polled'],1)
            self.assertEqual(collection['feeds_polled'],1)
            self.assertEqual(collection['feed_entries_new'],1)
            # The forced re-poll found a genuinely new document needing model review, so the
            # batch is no longer nothing_new -- the whole point of looking harder before
            # conceding.
            self.assertGreater(receipt['receipt']['documents_fetched'],0)
            self.assertNotEqual(research.run_summary(receipt)['model_documents'],0)

    def test_idle_pass_retries_a_stale_metrics_source_past_its_ordinary_cooldown(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp);RunnerTests().fixture(path)
            registry=research.load(path/'research/sources.json')
            for source in registry['sources']:source.pop('index',None)  # no feeds: isolate deliverable 3(b)
            research.save(path/'research/sources.json',registry)
            doe_url=next(s for s in registry['sources'] if s['id']=='doe-demand')['url']
            stale=[{'metric':'us-dc-electricity','source_ids':['doe-demand'],'feed_source_ids':[],
                    'latest_period':'2020','latest_value':1,'overdue_days':999,
                    'definition':{'id':'us-dc-electricity','title':'x','unit':'x','scope':'x','geography':'x'}}]
            def fake_due(url,refresh=False,feed_poll_seconds=None):
                # Only the idle top-up's forced retry (refresh=True) may reach this source;
                # the ordinary pass (refresh=args.refresh, false here) never can.
                return bool(refresh) and url==doe_url
            document=research.ReadableHTML();document.feed('<p>Public report of 2026 AI infrastructure progress.</p>')
            with patch.object(research,'ROOT',path),patch.object(research,'LOCAL',path/'.local'), \
                 patch.object(research,'select_stale_tasks',return_value=stale), \
                 patch.object(research.Fetcher,'due',side_effect=fake_due), \
                 patch.object(research.Fetcher,'fetch',return_value=document), \
                 patch.object(research,'ollama',side_effect=empty_model), \
                 patch.object(sys,'argv',['research.py','--max-documents','5']),patch('sys.stdout',new=io.StringIO()):
                research.main()
            receipt=research.load(sorted((path/'.local/runs').glob('*.json'))[-1])
            collection=receipt['collection']
            self.assertTrue(collection['idle_pass'])
            self.assertEqual(collection['idle_stale_tasks_run'],1)
            self.assertEqual(receipt['receipt']['documents_fetched'],1)
            self.assertNotEqual(research.run_summary(receipt)['model_documents'],0)

    def test_a_focused_sources_run_never_gets_the_idle_top_up(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp);RunnerTests().fixture(path)
            with patch.object(research,'ROOT',path),patch.object(research,'LOCAL',path/'.local'), \
                 patch.object(research.Fetcher,'due',return_value=False), \
                 patch.object(sys,'argv',['research.py','--sources','doe-demand']),patch('sys.stdout',new=io.StringIO()):
                self.assertEqual(research.main(),2)
            receipt=research.load(sorted((path/'.local/runs').glob('*.json'))[-1]) if list((path/'.local/runs').glob('*.json')) else None
            # A focused run that finds nothing due exits before any receipt is written at all
            # (the pre-existing not-attempts path); the idle top-up must not have run either.
            self.assertIsNone(receipt)

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
                # Pinned, non-feed sources: feeds sort first in the default queue (deliverable
                # 6) and never reach a model call.
                with patch.object(research,'ROOT',path),patch.object(research,'LOCAL',path/'.local'),patch.object(research.Fetcher,'fetch',return_value=document),patch.object(research,'ollama',side_effect=empty_model) as model,patch.object(sys,'argv',['research.py','--sources','doe-demand','company-nvidia','stanford-cost','--instructions',mode]),patch('sys.stdout',new=io.StringIO()):
                    research.main()
                self.assertTrue(model.call_args_list and all(marker in call.args[1] for call in model.call_args_list))

class ChildCoverageTests(unittest.TestCase):
    def test_discovered_page_inherits_parent_coverage_context(self):
        parent={'id':'claude-current-api-pricing'}
        child={'id':'discovered-0123456789abcdef','parent_source':'claude-current-api-pricing'}
        self.assertEqual(research.coverage_context(ROOT,child),research.coverage_context(ROOT,parent))
        self.assertNotEqual(research.coverage_context(ROOT,child),'{}')

class FeedsFirstOrderingTests(unittest.TestCase):
    """Deliverable 6: feed/index sources win a tie, without starving non-feed breadth."""
    def registry(self):
        sources=[{'id':'daily-a','url':'https://a.example/','layers':['energy']},
                  {'id':'feed-a','url':'https://b.example/feed','layers':['energy'],'index':True},
                  {'id':'daily-b','url':'https://c.example/','layers':['energy']},
                  {'id':'feed-b','url':'https://d.example/feed','layers':['energy'],'index':True}]
        collection={sid:{'cadence':'daily','weekday':0} for sid in ['daily-a','feed-a','daily-b','feed-b']}
        return {'sources':sources,'collection':collection}
    def test_feeds_win_a_tie_at_cold_start(self):
        queue=research.source_queue(self.registry(),date(2026,9,9),attempted={})
        ids=[s['id'] for s in queue]
        self.assertLess(ids.index('feed-a'),ids.index('daily-a'))
        self.assertLess(ids.index('feed-b'),ids.index('daily-b'))
    def test_a_stale_non_feed_source_is_not_starved_forever(self):
        # Once a feed has been attempted more recently than a non-feed, the non-feed's own
        # staleness wins: feed status is a tie-break, not an absolute partition (2026-09-10
        # regression -- an absolute partition let ~29 feeds monopolise every batch forever).
        attempted={'feed-a':'2026-09-09T00:00:00Z','feed-b':'2026-09-09T00:00:00Z'}
        queue=research.source_queue(self.registry(),date(2026,9,9),attempted=attempted)
        ids=[s['id'] for s in queue]
        self.assertLess(ids.index('daily-a'),ids.index('feed-a'))
        self.assertLess(ids.index('daily-b'),ids.index('feed-b'))

class DiscoveryCapTests(unittest.TestCase):
    """Deliverable 6: a feed reads up to max_discovered_per_feed new entries; an ordinary
    page still discovers at most max_discovered_per_source."""
    def run_with_source(self,source,policy,max_discovered_per_feed=3):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp);RunnerTests().fixture(path)
            registry=research.load(path/'research/sources.json')
            registry['sources'].append(source);registry['collection'][source['id']]=policy
            research.save(path/'research/sources.json',registry)
            config=research.load(path/'research/runtime.json')
            config['max_discovered_per_feed']=max_discovered_per_feed
            research.save(path/'research/runtime.json',config)
            links=''.join(f'<a href="https://feed.example/story/{i}-ai">Story {i}</a>' for i in range(10))
            document=research.ReadableHTML();document.feed(f'<p>Filler content.</p>{links}')
            with patch.object(research,'ROOT',path),patch.object(research,'LOCAL',path/'.local'), \
                 patch.object(research.Fetcher,'fetch',return_value=document),patch.object(research,'ollama',side_effect=empty_model), \
                 patch.object(sys,'argv',['research.py','--sources',source['id'],'--max-documents','20']),patch('sys.stdout',new=io.StringIO()):
                research.main()
            receipt=research.load(sorted((path/'.local/runs').glob('*.json'))[0])
            return receipt['collection']['documents']
    def test_feed_source_discovers_up_to_the_per_feed_cap(self):
        source={'id':'test-feed','publisher':'Test','title':'Test feed','url':'https://feed.example/rss','published':None,'layers':['energy'],'license':'x','index':True}
        policy={'rank':4,'region_book':'global','company_id':None,'claim_type':'other','cadence':'daily','weekday':0,'path_prefixes':['/story/'],'topics':['ai'],'excerpts':False}
        documents=self.run_with_source(source,policy,max_discovered_per_feed=3)
        self.assertEqual(len(documents),1+3)  # the feed itself, plus exactly 3 discovered entries
    def test_ordinary_page_still_discovers_only_one(self):
        source={'id':'test-page','publisher':'Test','title':'Test page','url':'https://feed.example/rss','published':None,'layers':['energy'],'license':'x'}
        policy={'rank':4,'region_book':'global','company_id':None,'claim_type':'other','cadence':'daily','weekday':0,'path_prefixes':['/story/'],'topics':['ai'],'excerpts':False}
        documents=self.run_with_source(source,policy)
        self.assertEqual(len(documents),1+1)  # the page itself, plus max_discovered_per_source (1)

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
                           'quarantined_by_reason':{},'private_notes':0,'empty_reasons':{},
                           'unchanged_304':0,'text_unchanged':0,'already_reviewed':0,'model_documents':0,
                           'stale_tasks':0,'stale_tasks_attempted':0,'stale_tasks_met':0,
                           'stale_tasks_skipped_not_refresh_expected':0,'stale_tasks_backed_off':0,
                           'feeds_polled':0,'feed_entries_new':0,'feed_entries_already_reviewed':0,
                           'idle_pass':False,'idle_feeds_polled':0,'idle_stale_tasks_run':0})
    def test_deliverable_8_reports_why_the_model_was_or_was_not_called(self):
        receipt={'receipt':{'documents_fetched':9},'quarantine':[],
                  'collection':{'unchanged_304':2,'text_unchanged':1,'already_reviewed':3,'model_documents':4,
                                'stale_tasks':[{'metric':'m1','overdue_days':5,'outcome':'met'},
                                               {'metric':'m2','overdue_days':2,'outcome':'nothing_newer'}]}}
        summary=research.run_summary(receipt)
        self.assertEqual((summary['unchanged_304'],summary['text_unchanged'],summary['already_reviewed'],summary['model_documents']),(2,1,3,4))
        self.assertEqual((summary['stale_tasks'],summary['stale_tasks_met']),(2,1))
    def test_never_includes_source_text_or_local_paths(self):
        receipt={'receipt':{'documents_fetched':1},'quarantine':[{'source':'a','candidate':{'evidence':'secret excerpt text'},'reason':'other'}],'collection':{}}
        summary=research.run_summary(receipt)
        self.assertNotIn('secret excerpt text',json.dumps(summary))

class NumericTokenSupportTests(unittest.TestCase):
    """candidate_record end to end: suffix-multiplier and unit-scaled table values (deliverable 1)."""
    def setUp(self):
        self.data=json.loads((ROOT/'site/data/ledger.json').read_text(encoding='utf-8'))
        self.registry=json.loads((ROOT/'research/sources.json').read_text(encoding='utf-8'))
        self.metrics={m['id']:m for m in self.data['metrics']}
        self.sources={s['id']:s for s in self.data['sources']}
    def policy(self,source_id):
        from source_policy import collection_for
        return collection_for(self.registry,self.sources[source_id])
    def test_glued_k_suffix_is_accepted_with_a_traceable_note(self):
        c={'metric':'epoch-nvidia-ai-chips-cumulative','year':2024,'period':'2024-Q4','value':110000,'upper':None,'status':'estimate','precision':'eq','note':'','evidence':'B200 Nvidia shipments reached 110k units by year-end 2024.'}
        record=research.candidate_record(c,self.sources['epoch-chip-sales-dataset'],c['evidence'],self.metrics,self.sources,policy=self.policy('epoch-chip-sales-dataset'))
        self.assertEqual(record['value'],110000)
        self.assertIn('110k',record['note'])
    def test_table_value_in_millions_supports_a_usd_billion_metric_value(self):
        c={'metric':'revenue-amphenol','year':2026,'period':'2026','value':23.0947,'upper':None,'status':'observation','precision':'eq','note':'','evidence':'Net sales for the year were 23,094.7 as reported in 2026.'}
        record=research.candidate_record(c,self.sources['company-amphenol'],c['evidence'],self.metrics,self.sources,policy=self.policy('company-amphenol'))
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
        self.registry=json.loads((ROOT/'research/sources.json').read_text(encoding='utf-8'))
        self.metrics={m['id']:m for m in self.data['metrics']}
        self.sources={s['id']:s for s in self.data['sources']}
        self.this_year=datetime.now(timezone.utc).year
    def policy(self,source_id):
        from source_policy import collection_for
        return collection_for(self.registry,self.sources[source_id])
    def test_access_dated_metric_accepts_the_retrieval_year_and_matches_its_own_period_style(self):
        existing=[o for o in self.data['observations'] if o['metric']=='codex-input-price']
        c={'metric':'codex-input-price','year':self.this_year,'period':'','value':1.75,'upper':None,'status':'observation','precision':'eq','note':'','evidence':'Input pricing is listed at $1.75 per million tokens.'}
        record=research.candidate_record(c,self.sources['codex53-pricing'],c['evidence'],self.metrics,self.sources,existing,self.policy('codex53-pricing'))
        self.assertTrue(record['period'].lower().startswith('list pricing accessed'))
        self.assertIn(str(self.this_year),record['period'])
    def test_wrong_year_is_still_rejected_even_when_access_dated(self):
        existing=[o for o in self.data['observations'] if o['metric']=='codex-input-price']
        c={'metric':'codex-input-price','year':self.this_year-1,'period':'','value':1.75,'upper':None,'status':'observation','precision':'eq','note':'','evidence':'Input pricing is listed at $1.75 per million tokens.'}
        with self.assertRaisesRegex(ValueError,'Year not found'):
            research.candidate_record(c,self.sources['codex53-pricing'],c['evidence'],self.metrics,self.sources,existing,self.policy('codex53-pricing'))
    def test_ordinary_metric_with_a_published_source_still_requires_a_year_token(self):
        # revenue-amphenol has no access-style history and its source has a real publication date.
        c={'metric':'revenue-amphenol','year':2024,'period':'2024','value':1,'upper':None,'status':'observation','precision':'eq','note':'','evidence':'Net sales reported at $1 billion for the period.'}
        with self.assertRaisesRegex(ValueError,'Year not found'):
            research.candidate_record(c,self.sources['company-amphenol'],c['evidence'],self.metrics,self.sources,[],self.policy('company-amphenol'))
    def test_snapshot_basis_metric_gets_an_iso_period_not_free_text(self):
        # epoch-chip-sales-dataset has no published date, so this exercises the period_basis
        # branch specifically rather than the "source has no published date" fallback alone.
        metrics=copy.deepcopy(self.metrics);metrics['epoch-nvidia-ai-chips-cumulative']['period_basis']='snapshot'
        c={'metric':'epoch-nvidia-ai-chips-cumulative','year':self.this_year,'period':'','value':500,'upper':None,'status':'estimate','precision':'eq','note':'','evidence':'Cumulative shipments snapshot stood at 500 units.'}
        record=research.candidate_record(c,self.sources['epoch-chip-sales-dataset'],c['evidence'],metrics,self.sources,[],self.policy('epoch-chip-sales-dataset'))
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


class FakeHealth:
    """Enough of collection_health.Health for source_usable_for_stale_task: per-URL records
    with an explicit due() answer, independent of the wall clock."""
    def __init__(self,records=None):self.records=records or {}
    def get(self,kind,target):return self.records.get(target,{})
    def due(self,kind,target):return self.records.get(target,{}).get('_due',True)

class StaleFigureTaskTests(unittest.TestCase):
    """Deliverable 10: overdue-metric tasking, cadence thresholds, prompt target, receipt."""
    def setUp(self):
        self.today=date(2026,9,10)
        def metric(mid,basis,definition_stable=True,company=None,**over):
            m={'id':mid,'title':mid,'unit':'x','scope':'s','geography':'g','source_ids':[f'src-{mid}'],
               'definition_stable':definition_stable}
            if basis is not None:m['period_basis']=basis
            if company:m['company']=company
            m.update(over);return m
        def obs(mid,period,value,year):
            return {'metric':mid,'period':period,'value':value,'year':year}
        self.metrics=[
            metric('m-quarter-stale','quarter'),       # 2025-Q1, 497 days overdue
            metric('m-quarter-fresh','quarter'),        # 2026-Q3, not overdue
            metric('m-month-stale','month'),            # 2026-06, 56 days overdue
            metric('m-snapshot-fresh','snapshot'),       # 2026-08-01, not overdue
            metric('m-yearly-stale',None),               # 2020, 2044 days overdue
            metric('m-unstable-stale','quarter',definition_stable=False),  # would be overdue, but excluded
            metric('m-manual-only','quarter'),           # overdue, but its only source is manual
            metric('m-refused-only','quarter'),          # overdue, but its only source is refused+cooling
        ]
        self.observations=[
            obs('m-quarter-stale','2025-Q1',1,2025),obs('m-quarter-fresh','2026-Q3',1,2026),
            obs('m-month-stale','2026-06',1,2026),obs('m-snapshot-fresh','2026-08-01',1,2026),
            obs('m-yearly-stale','2020',1,2020),obs('m-unstable-stale','2025-Q1',1,2025),
            obs('m-manual-only','2025-Q1',1,2025),obs('m-refused-only','2025-Q1',1,2025),
            # A superseded reading close to today must never mask the real (overdue) latest one.
            {'metric':'m-quarter-stale','period':'2026-Q3','value':9,'year':2026,'superseded_by':'later'},
        ]
        self.data={'metrics':self.metrics,'observations':self.observations}
        self.registry={'sources':[{'id':f'src-{m["id"]}','url':f'https://example.org/{m["id"]}'} for m in self.metrics],
                       'collection':{f'src-{m["id"]}':{'cadence':'daily'} for m in self.metrics}}
        self.registry['collection']['src-m-manual-only']['cadence']='manual'
        self.health=FakeHealth({'https://example.org/m-refused-only':{'status':'unavailable','refused':True,'_due':False}})
        self.ecosystem={'companies':[]}
    def test_thresholds_select_the_right_metrics_and_exclude_fresh_ones(self):
        tasks=research.select_stale_tasks(self.data,self.registry,self.ecosystem,self.health,self.today,20)
        ids=[t['metric'] for t in tasks]
        self.assertIn('m-quarter-stale',ids);self.assertIn('m-month-stale',ids);self.assertIn('m-yearly-stale',ids)
        for excluded in ['m-quarter-fresh','m-snapshot-fresh','m-unstable-stale','m-manual-only','m-refused-only']:
            self.assertNotIn(excluded,ids,excluded)
    def test_ordering_is_most_overdue_first(self):
        tasks=research.select_stale_tasks(self.data,self.registry,self.ecosystem,self.health,self.today,20)
        ids=[t['metric'] for t in tasks]
        self.assertEqual(ids,['m-yearly-stale','m-quarter-stale','m-month-stale'])
        by_id={t['metric']:t for t in tasks}
        self.assertEqual(by_id['m-quarter-stale']['overdue_days'],497)
        self.assertEqual(by_id['m-month-stale']['overdue_days'],56)
    def test_limit_bounds_the_returned_list(self):
        tasks=research.select_stale_tasks(self.data,self.registry,self.ecosystem,self.health,self.today,2)
        self.assertEqual(len(tasks),2)
    def test_a_superseded_reading_never_hides_the_true_latest_observation(self):
        tasks=research.select_stale_tasks(self.data,self.registry,self.ecosystem,self.health,self.today,20)
        task=next(t for t in tasks if t['metric']=='m-quarter-stale')
        self.assertEqual(task['latest_period'],'2025-Q1')
    def test_task_carries_the_metric_definition_and_latest_reading(self):
        task=next(t for t in research.select_stale_tasks(self.data,self.registry,self.ecosystem,self.health,self.today,20) if t['metric']=='m-month-stale')
        self.assertEqual(task['latest_period'],'2026-06');self.assertEqual(task['latest_value'],1)
        self.assertEqual(task['definition']['id'],'m-month-stale')
        self.assertEqual(task['source_ids'],['src-m-month-stale'])

    def test_stale_target_reaches_the_extraction_prompt(self):
        data=json.loads((ROOT/'site/data/ledger.json').read_text(encoding='utf-8'))
        metrics={m['id']:m for m in data['metrics']};sources={s['id']:s for s in data['sources']}
        related=[metrics['ai-adoption']];source=sources['stanford-2026']
        config={'_instructions':'i','_coverage':'c','max_candidates_per_document':8}
        stale_targets=[{'definition':{'id':'ai-adoption'},'latest_period':'2025','latest_value':80}]
        with patch.object(research,'ollama',return_value={'observations':[]}) as model:
            research.extract_observations(config,source,'Filler document text.',related,copy.deepcopy(data),metrics,dict(sources),{'model_calls':0},[],{},stale_targets)
        prompt=json.loads(model.call_args.args[2])
        self.assertEqual(prompt['stale_targets'],stale_targets)
        self.assertIn('period after',prompt['stale_target_instruction'])
        self.assertIn('duplicate',prompt['stale_target_instruction'])
    def test_no_stale_targets_omits_the_field_entirely(self):
        data=json.loads((ROOT/'site/data/ledger.json').read_text(encoding='utf-8'))
        metrics={m['id']:m for m in data['metrics']};sources={s['id']:s for s in data['sources']}
        related=[metrics['ai-adoption']];source=sources['stanford-2026']
        config={'_instructions':'i','_coverage':'c','max_candidates_per_document':8}
        with patch.object(research,'ollama',return_value={'observations':[]}) as model:
            research.extract_observations(config,source,'Filler document text.',related,copy.deepcopy(data),metrics,dict(sources),{'model_calls':0},[],{})
        prompt=json.loads(model.call_args.args[2])
        self.assertNotIn('stale_targets',prompt)

    def test_receipt_accounting_met_quarantined_and_nothing_newer(self):
        tasks=[{'metric':'a','overdue_days':10},{'metric':'b','overdue_days':5},{'metric':'c','overdue_days':1}]
        outcomes={o['metric']:o for o in research.stale_task_outcomes(tasks,met_metrics={'a'},quarantined_metrics={'b'})}
        self.assertEqual(outcomes['a']['outcome'],'met')
        self.assertEqual(outcomes['b']['outcome'],'quarantined')
        self.assertEqual(outcomes['c']['outcome'],'nothing_newer')
        self.assertEqual(outcomes['a']['overdue_days'],10)
    def test_receipt_distinguishes_never_reached_from_genuinely_unmet(self):
        # Deliverable 2 (2026-09-10): an offered task the batch never actually reached (document
        # budget ran out first) must not read the same as one that was tried and taught nothing --
        # only the latter should ever count toward the session back-off rule.
        tasks=[{'metric':'a','overdue_days':10},{'metric':'b','overdue_days':5}]
        outcomes={o['metric']:o for o in research.stale_task_outcomes(tasks,met_metrics=set(),quarantined_metrics=set(),attempted_metrics={'a'})}
        self.assertEqual(outcomes['a']['outcome'],'nothing_newer')
        self.assertEqual(outcomes['b']['outcome'],'not_attempted')


class RefreshExpectedTests(unittest.TestCase):
    """Deliverable 1 (2026-09-10): a reviewed refresh expectation, derived or explicit, so
    select_stale_tasks stops chasing a milestone, plan or fixed study no source will restate."""
    def metric(self,mid='m',**over):
        m={'id':mid,'source_ids':['s']};m.update(over);return m
    def obs(self,mid,status,year=2025):
        return {'metric':mid,'year':year,'period':str(year),'value':1,'status':status}
    def test_explicit_field_always_wins(self):
        self.assertFalse(research.refresh_expected(self.metric(refresh_expected=False,period_basis='quarter'),[]))
        self.assertTrue(research.refresh_expected(self.metric(refresh_expected=True,measurement_type='crash_involvements_per_million_miles'),[]))
    def test_periodic_period_basis_wins_over_an_unset_measurement_type(self):
        for basis in ['month','quarter','snapshot']:
            with self.subTest(basis=basis):
                self.assertTrue(research.refresh_expected(self.metric(period_basis=basis),[]))
    def test_a_quarterly_employment_metric_is_refresh_expected(self):
        m=self.metric('county-employment',measurement_type='county_industry_employment')
        self.assertTrue(research.refresh_expected(m,[self.obs('county-employment','observation')]))
    def test_a_crash_rate_study_is_not_refresh_expected(self):
        m=self.metric('crash-rate',measurement_type='crash_involvements_per_million_miles')
        self.assertFalse(research.refresh_expected(m,[self.obs('crash-rate','estimate')]))
    def test_an_announced_investment_is_not_refresh_expected(self):
        m=self.metric('announced-capital',measurement_type='capex_announced_usd',allowed_statuses=['forecast','company-commitment','government-target'])
        self.assertFalse(research.refresh_expected(m,[self.obs('announced-capital','company-commitment')]))
    def test_capex_guidance_reissued_every_quarter_is_refresh_expected(self):
        # The one FUTURE_ONLY type this catalog uses two ways: allowed_statuses restricted to
        # ['forecast'] alone is a reissued guidance/consensus figure (capital-guidance-aws and
        # friends), not the one-time program pledge the broader status set above represents.
        m=self.metric('capex-guidance',measurement_type='capex_announced_usd',allowed_statuses=['forecast'])
        self.assertTrue(research.refresh_expected(m,[self.obs('capex-guidance','forecast')]))
    def test_a_metric_with_only_commitment_or_target_records_is_not_refresh_expected(self):
        # No measurement_type at all -- crane-restart/eaton-jonesville-investment's own shape --
        # still falls back correctly using the actual recorded history.
        m=self.metric('pledge-only')
        self.assertFalse(research.refresh_expected(m,[self.obs('pledge-only','company-commitment')]))
        m2=self.metric('target-only')
        self.assertFalse(research.refresh_expected(m2,[self.obs('target-only','government-target')]))
    def test_an_untyped_metric_with_an_ordinary_observation_defaults_true(self):
        # Absence of a periodic signal is not by itself evidence of a one-time figure --
        # gemini-solar and inference-cost derive True here and need the reviewed catalog
        # override (deliverable 4) precisely because this default preserves today's behavior
        # for every other untyped legacy metric.
        m=self.metric('untyped-observed')
        self.assertTrue(research.refresh_expected(m,[self.obs('untyped-observed','observation')]))
    def test_a_metric_with_no_recorded_observations_defaults_true(self):
        self.assertTrue(research.refresh_expected(self.metric('no-history'),[]))


class SelectStaleTasksRefreshExpectedAndBackoffTests(unittest.TestCase):
    """select_stale_tasks (deliverable 1/2, 2026-09-10) skips a non-refresh-expected metric
    outright, and withholds one still inside its session back-off window -- both counted into
    the `collection` dict passed in, distinct from the metrics actually offered."""
    def setUp(self):
        self.today=date(2026,9,10)
        self.metrics=[
            {'id':'m-periodic','period_basis':'quarter','source_ids':['src-m-periodic'],'definition_stable':True},
            {'id':'m-one-time','measurement_type':'crash_involvements_per_million_miles','source_ids':['src-m-one-time'],'definition_stable':True},
        ]
        self.observations=[
            {'metric':'m-periodic','period':'2025-Q1','value':1,'year':2025,'status':'observation'},
            {'metric':'m-one-time','period':'2025','value':1,'year':2025,'status':'estimate'},
        ]
        self.data={'metrics':self.metrics,'observations':self.observations}
        self.registry={'sources':[{'id':f'src-{m["id"]}','url':f'https://example.org/{m["id"]}'} for m in self.metrics],
                       'collection':{f'src-{m["id"]}':{'cadence':'daily'} for m in self.metrics}}
        self.ecosystem={'companies':[]}
    def select(self,**kwargs):
        collection={}
        tasks=research.select_stale_tasks(self.data,self.registry,self.ecosystem,None,self.today,20,collection=collection,**kwargs)
        return tasks,collection
    def test_a_one_time_measurement_type_is_skipped_and_counted(self):
        tasks,collection=self.select()
        ids=[t['metric'] for t in tasks]
        self.assertIn('m-periodic',ids);self.assertNotIn('m-one-time',ids)
        self.assertEqual(collection['stale_tasks_skipped_not_refresh_expected'],1)
        self.assertEqual(collection['stale_tasks_backed_off'],0)
    def test_a_metric_inside_its_retry_window_is_withheld(self):
        attempts={'m-periodic':{'unmet_count':1,'last_attempt_batch':5}}
        tasks,collection=self.select(stale_attempts=attempts,current_batch=6,stale_retry_batches=12)
        self.assertEqual([t['metric'] for t in tasks],[])
        self.assertEqual(collection['stale_tasks_backed_off'],1)
    def test_a_metric_past_its_retry_window_is_offered_again(self):
        attempts={'m-periodic':{'unmet_count':1,'last_attempt_batch':1}}
        tasks,collection=self.select(stale_attempts=attempts,current_batch=13,stale_retry_batches=12)
        self.assertEqual([t['metric'] for t in tasks],['m-periodic'])
        self.assertEqual(collection['stale_tasks_backed_off'],0)
    def test_a_dropped_metric_is_withheld_regardless_of_batches_elapsed(self):
        attempts={'m-periodic':{'unmet_count':3,'last_attempt_batch':1,'dropped':True}}
        tasks,_=self.select(stale_attempts=attempts,current_batch=999,stale_retry_batches=12)
        self.assertEqual([t['metric'] for t in tasks],[])
    def test_no_backoff_state_offers_normally(self):
        tasks,collection=self.select(stale_attempts={},current_batch=1)
        self.assertEqual([t['metric'] for t in tasks],['m-periodic'])
        self.assertEqual(collection['stale_tasks_backed_off'],0)


class StaleTaskSessionBackoffStateTests(unittest.TestCase):
    """Deliverable 2 (2026-09-10) end to end through main(): the session's own
    .local/sessions/<id>/stale-attempts.json accumulates unmet attempts, drops a metric after
    three, resets on a met outcome, and is never touched by a focused --sources run."""
    def setUp(self):
        self.stanford_url='https://hai.stanford.edu/ai-index/2026-ai-index-report'
        self.document=research.ReadableHTML();self.document.feed('<p>Public report of 2026 AI infrastructure and progress.</p>')
        self.task={'metric':'ai-adoption','source_ids':['stanford-2026'],'feed_source_ids':[],
            'latest_period':'2025','latest_value':88,'overdue_days':500,
            'definition':{'id':'ai-adoption','title':'AI adoption','unit':'%','scope':'s','geography':'g'}}
    def fake_due(self,url,refresh=False,feed_poll_seconds=None):return url==self.stanford_url
    def run_batch(self,path,sid,select_stale_tasks_mock,model=empty_model,document=None):
        with patch.object(research,'ROOT',path),patch.object(research,'LOCAL',path/'.local'), \
             patch.object(research,'select_stale_tasks',side_effect=select_stale_tasks_mock), \
             patch.object(research.Fetcher,'due',side_effect=self.fake_due), \
             patch.object(research.Fetcher,'fetch',return_value=document or self.document), \
             patch.object(research,'ollama',side_effect=model), \
             patch.object(sys,'argv',['research.py','--session-id',sid,'--refresh']),patch('sys.stdout',new=io.StringIO()):
            return research.main()
    def test_an_unmet_attempt_backs_off_for_the_configured_retry_window(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp);RunnerTests().fixture(path);sid='a'*32
            calls=[]
            def fake_select(*args,**kwargs):
                # main() mutates the same stale_attempts dict object in place later in this
                # same batch (persisting the outcome) -- capture a snapshot, not the reference.
                calls.append((copy.deepcopy(args[6]),args[7]));return [dict(self.task)]
            self.run_batch(path,sid,fake_select)
            state_path=path/'.local/sessions'/sid/'stale-attempts.json'
            self.assertEqual(research.load(state_path),{'ai-adoption':{'unmet_count':1,'last_attempt_batch':1}})
            self.run_batch(path,sid,fake_select)
            # main() must read batch 1's saved state back and advance the batch counter --
            # select_stale_tasks itself already enforces the window (tested directly above).
            self.assertEqual(calls[1],({'ai-adoption':{'unmet_count':1,'last_attempt_batch':1}},2))
            self.assertEqual(research.load(state_path),{'ai-adoption':{'unmet_count':2,'last_attempt_batch':2}})
    def test_three_unmet_attempts_drop_the_metric_for_the_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp);RunnerTests().fixture(path);sid='b'*32
            def fake_select(*args,**kwargs):return [dict(self.task)]
            for _ in range(3):self.run_batch(path,sid,fake_select)
            state=research.load(path/'.local/sessions'/sid/'stale-attempts.json')
            self.assertEqual(state['ai-adoption'],{'unmet_count':3,'last_attempt_batch':3,'dropped':True})
    def test_a_met_outcome_clears_prior_backoff_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp);RunnerTests().fixture(path);sid='c'*32
            session_folder=path/'.local/sessions'/sid
            research.save(session_folder/'stale-attempts.json',{'ai-adoption':{'unmet_count':2,'last_attempt_batch':1}})
            evidence='In 2026, 91 percent of surveyed organizations reported AI use.'
            document=research.ReadableHTML();document.feed(f'<p>{evidence}</p>')
            candidate={'metric':'ai-adoption','year':2026,'period':'2026','value':91,'upper':None,'status':'observation','precision':'eq','note':'','evidence':evidence}
            def fake_model(cfg,system,prompt,schema):
                if schema==research.NOTE_SCHEMA:return {'notes':[]}
                if schema==research.VERDICT_SCHEMA:return {'verdicts':[{'index':0,'supported':True,'reason':'Direct support'}]}
                return {'observations':[candidate]}
            def fake_select(*args,**kwargs):return [dict(self.task)]
            self.run_batch(path,sid,fake_select,model=fake_model,document=document)
            state=research.load(session_folder/'stale-attempts.json')
            self.assertNotIn('ai-adoption',state)
    def test_a_focused_sources_run_never_touches_backoff_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp);RunnerTests().fixture(path);sid='d'*32
            with patch.object(research,'ROOT',path),patch.object(research,'LOCAL',path/'.local'), \
                 patch.object(research,'select_stale_tasks') as mock_select, \
                 patch.object(research.Fetcher,'fetch',return_value=self.document), \
                 patch.object(research,'ollama',side_effect=empty_model), \
                 patch.object(sys,'argv',['research.py','--session-id',sid,'--sources','doe-demand']),patch('sys.stdout',new=io.StringIO()):
                research.main()
            mock_select.assert_not_called()
            self.assertFalse((path/'.local/sessions'/sid/'stale-attempts.json').exists())
            receipts=list((path/'.local/sessions'/sid/'batches').glob('*.json'))
            receipt=research.load(receipts[0])
            self.assertEqual(receipt['collection'].get('stale_tasks_offered',0),0)


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
