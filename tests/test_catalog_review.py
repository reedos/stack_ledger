import copy
import hashlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import catalog_review as c
import catalog_recommender as recommender
import findings_review
import research
from validate_delivery import validate_delivery

class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        for file in c.FILES:c.save(self.root/file,c.read(ROOT/file))
        c.save(self.root/'research/editorial-policy.json',{'reviewers':['human'],'reviewer_accounts':{'human':['fixture']}})
        self.body=b'Fixture source: next evidence must establish actual delivered output.'
        self.sha=hashlib.sha256(self.body).hexdigest();p=self.root/'.local/catalog-evidence'/(self.sha+'.txt');p.parent.mkdir(parents=True);p.write_bytes(self.body)
        self.evidence=[dict(id='fixture',url='https://example.org/release',published_at='2026-09-08',retrieved_at='2026-09-09T00:00:00Z',sha256=self.sha,summary=self.body.decode())]
        self.project=copy.deepcopy(c.base(self.root)['research/delivery.json']['projects'][0]);self.project['next_evidence']='Verify actual delivered output against the operator disclosure.'
        self.change={'target':'project','id':self.project['id'],'after':self.project,'evidence':['fixture']}
        self.git=patch.object(c,'git',return_value='fixture-head');self.git.start();self.addCleanup(self.git.stop)
    def enqueue(self):return c.enqueue(self.root,'Fixture catalog update',[self.change],self.evidence)
    def payload(self,p):return dict(id=p['id'],decision='approved',rationale='Synthetic human fixture reviewed evidence.',proposal_hash=c.digest(p),review_hash=c.digest(c.last_review(self.root,p['id'])),confirmed=True)
    def test_private_projection_and_mirrors(self):
        before=c.base(self.root);p=self.enqueue();self.assertEqual(c.base(self.root),before)
        projected=c.projected(p,before)
        self.assertEqual(projected['research/delivery.json'],projected['site/data/delivery.json'])
        self.assertEqual(projected['site/data/ledger.json']['runtime'],before['site/data/ledger.json']['runtime'])
        self.assertEqual(projected['site/data/ledger.json']['observations'],before['site/data/ledger.json']['observations'])
        self.assertEqual(self.enqueue()['id'],p['id']);self.assertEqual(c.inbox(self.root)[0]['status'],'pending_review')
    def test_stale_object_but_unrelated_run_allowed(self):
        p=self.enqueue();d=c.read(self.root/'site/data/ledger.json');d['runtime']['last_attempt']='2026-09-09T00:00:00Z';c.save(self.root/'site/data/ledger.json',d);c.check_base(self.root,p)
        d=c.read(self.root/'research/delivery.json');d['projects'][0]['stage']='delayed';c.save(self.root/'research/delivery.json',d)
        with self.assertRaisesRegex(ValueError,'Object changed'):c.check_base(self.root,p)
    def test_evidence_and_target_guards(self):
        for change in [dict(self.change,target='../../secrets'),dict(self.change,evidence=[]),dict(self.change,after=dict(self.project,id='other'))]:
            with self.assertRaises(ValueError):c.enqueue(self.root,'Fixture',[change],self.evidence)
        p=self.enqueue();(self.root/'.local/catalog-evidence'/(self.sha+'.txt')).write_text('changed')
        with self.assertRaises(ValueError):c.check_evidence(self.root,p)
    def test_append_only_corrections(self):
        d=c.base(self.root)
        for target,key in [('note','events'),('observation','observations')]:
            old=d['site/data/ledger.json'][key][0];new=dict(old,note='rewritten')
            with self.assertRaises(ValueError):c.enqueue(self.root,'Fixture',[dict(target=target,id=old['id'],after=new,evidence=['fixture'])],self.evidence)
    def test_human_review_preview_and_stale_hash(self):
        p=self.enqueue()
        with patch.object(findings_review.getpass,'getuser',return_value='outsider'):
            with self.assertRaises(ValueError):c.review(self.root,self.payload(p),'human')
        with patch.object(findings_review.getpass,'getuser',return_value='fixture'):
            with self.assertRaises(ValueError) as caught:c.review(self.root,self.payload(p),'human')
            self.assertIn('Validate the preview first',str(caught.exception))   # a clear 400, not a misleading 409 (seen live 2026-09-09)
            c.save(self.root/'.local/catalog-previews'/p['id']/'validation.json',{'passed':True,'proposal_hash':c.digest(p)})
            payload=self.payload(p);self.assertFalse(c.review(self.root,payload,'human')['published'])
            with self.assertRaises(ValueError):c.review(self.root,payload,'human')
            with self.assertRaises(ValueError):c.review(self.root,dict(self.payload(p),confirmed=False),'human')
    def test_preview_isolated_and_checks_fail_closed(self):
        p=self.enqueue();before=c.base(self.root)
        completed=SimpleNamespace(returncode=0,stdout='fixture pass',stderr='')
        with patch.object(c.subprocess,'run',return_value=completed) as run:
            result=c.preview(self.root,p['id']);self.assertTrue(result['passed']);self.assertEqual(run.call_count,4)
        self.assertEqual(c.base(self.root),before)
        with patch.object(c.subprocess,'run',return_value=SimpleNamespace(returncode=1,stdout='',stderr='invalid')) as run:
            self.assertFalse(c.preview(self.root,p['id'])['passed']);self.assertEqual(run.call_count,1)
    def test_unapproved_publication_blocked(self):
        p=self.enqueue()
        with self.assertRaises(ValueError):c.apply_publish(self.root,p['id'],c.digest(p),c.digest(None),'human',True)
        self.assertEqual(c.base(self.root)['research/delivery.json']['projects'][0]['id'],self.project['id'])
    def test_draft_call_accounting_and_insufficient_evidence(self):
        source=c.base(self.root)['research/sources.json']['sources'][0];note={'id':'fixture-note','title':'Fixture','summary':'An uncertain future plan.'};run={'model_calls':0}
        def model(config,system,prompt,schema):
            self.assertIn('Fixture reviewed operating guidance',system)
            self.assertIn('No approval',system)
            return {'changes':[],'reason':'No defensible catalog change.'}
        recommender.draft(self.root,{'_instructions':'Fixture reviewed operating guidance'},source,self.body.decode(),note,run,model)
        self.assertEqual(run['model_calls'],1);self.assertEqual(recommender.materialize(self.root),[])
        self.assertEqual(len(c.inbox(self.root)),0)
        recommender.draft(self.root,{},source,self.body.decode(),note,run,lambda *args:self.fail('Duplicate inference'))
        self.assertEqual(run['model_calls'],1)
    def test_draft_to_package_without_approval(self):
        source=c.base(self.root)['research/sources.json']['sources'][0];run={'model_calls':0}
        recommender.draft(self.root,{},source,self.body.decode(),{'id':'fixture','title':'Fixture','summary':'Next evidence.'},run,
            lambda *args:{'changes':[{k:v for k,v in self.change.items() if k!='evidence'}],'reason':'Review the changed requirement.'})
        ids=recommender.materialize(self.root);self.assertEqual(len(ids),1)
        self.assertEqual(c.inbox(self.root)[0]['status'],'pending_review');self.assertEqual(recommender.materialize(self.root),[])
    def test_cyclic_phase_accounting_rejected(self):
        d=c.read(ROOT/'research/delivery.json');d['projects'][0]['parent_project']=d['projects'][1]['id'];d['projects'][1]['parent_project']=d['projects'][0]['id']
        with self.assertRaisesRegex(ValueError,'Cyclic'):validate_delivery(d,c.read(ROOT/'site/data/ledger.json'))

    def test_broken_package_does_not_hide_valid_inbox(self):
        p=self.enqueue();(c.queue(self.root)/('catalog-'+'a'*24+'.json')).write_text('{broken')
        errors=[];rows=c.inbox(self.root,errors)
        self.assertEqual([r['id'] for r in rows],[p['id']]);self.assertEqual(len(errors),1)

    def test_non_object_draft_does_not_interrupt_materialization(self):
        c.save(c.queue(self.root)/'draft-invalid.json',[])
        self.assertEqual(recommender.materialize(self.root),[])

    def test_new_project_questions_reach_monitoring_context(self):
        from research import coverage_context
        for name in ['fabric','agenda','claims']:
            c.save(self.root/f'research/{name}.json',c.read(ROOT/f'research/{name}.json'))
        p=self.enqueue();documents=c.projected(p,c.base(self.root))
        c.save(self.root/'research/delivery.json',documents['research/delivery.json'])
        source_id=self.project['milestones'][0]['source']
        context=json.loads(coverage_context(self.root,{'id':source_id}))
        self.assertTrue(any(row.get('next_evidence')==self.project['next_evidence'] for row in context['delivery']))

    def approve(self):
        p=self.enqueue()
        with patch.object(findings_review.getpass,'getuser',return_value='fixture'):
            c.save(self.root/'.local/catalog-previews'/p['id']/'validation.json',{'passed':True,'proposal_hash':c.digest(p)})
            c.review(self.root,self.payload(p),'human')
        c.save(self.root/'research/runtime.json',c.read(ROOT/'research/runtime.json'))
        for name in ['delivery','ecosystem','expansion','source-books']:c.save(self.root/f'site/data/{name}.json',c.read(ROOT/f'site/data/{name}.json'))
        commit='f'*40
        c.save(c.queue(self.root)/(p['id']+'-publication.json'),{'commit':commit,'proposal_hash':c.digest(p),'status':'deployment_pending'})
        return p

    def test_verify_pending_deployments_match_appends_applied_event(self):
        p=self.approve()
        expected={Path(n).name:c.read(self.root/n) for n in ['site/data/ledger.json','site/data/delivery.json','site/data/ecosystem.json','site/data/expansion.json','site/data/source-books.json']}
        def matching(url,timeout=10):return io.BytesIO(json.dumps(expected[url.split('/')[-1].split('?')[0]]).encode())
        with patch.object(research,'ROOT',self.root),patch.object(research,'LOCAL',self.root/'.local'),patch.object(c,'urlopen',side_effect=matching):
            result=c.verify_pending_deployments(self.root)
        self.assertEqual(result,{'checked':[p['id']],'applied':[p['id']],'still_pending':[]})
        self.assertEqual(c.last_review(self.root,p['id'])['status'],'applied')
        self.assertEqual(json.loads((c.queue(self.root)/(p['id']+'-publication.json')).read_text(encoding='utf-8'))['status'],'deployed')
        self.assertTrue((c.queue(self.root)/(p['id']+'-followup.json')).exists())

    def test_verify_pending_deployments_mismatch_leaves_package_untouched(self):
        p=self.approve()
        def mismatching(url,timeout=10):return io.BytesIO(b'{}')
        with patch.object(research,'ROOT',self.root),patch.object(research,'LOCAL',self.root/'.local'),patch.object(c,'urlopen',side_effect=mismatching):
            result=c.verify_pending_deployments(self.root)
        self.assertEqual(result,{'checked':[p['id']],'applied':[],'still_pending':[p['id']]})
        self.assertEqual(c.last_review(self.root,p['id'])['status'],'approved')
        self.assertEqual(json.loads((c.queue(self.root)/(p['id']+'-publication.json')).read_text(encoding='utf-8'))['status'],'deployment_pending')

    def receipt(self,p,**fields):
        path=c.queue(self.root)/(p['id']+'-publication.json');c.save(path,dict(c.read(path),**fields))

    def test_a_failed_push_whose_commit_reached_origin_anyway_is_verified(self):
        # The night's sync pushes its own stranded commits; the receipt still says the push failed.
        p=self.approve();self.receipt(p,status='publication_failed')
        expected={Path(n).name:c.read(self.root/n) for n in ['site/data/ledger.json','site/data/delivery.json','site/data/ecosystem.json','site/data/expansion.json','site/data/source-books.json']}
        def matching(url,timeout=10):return io.BytesIO(json.dumps(expected[url.split('/')[-1].split('?')[0]]).encode())
        with patch.object(research,'ROOT',self.root),patch.object(research,'LOCAL',self.root/'.local'),patch.object(c,'urlopen',side_effect=matching):
            with patch.object(c,'ancestor',return_value=False):
                self.assertEqual(c.verify_pending_deployments(self.root)['checked'],[],'not on origin yet: nothing to verify')
            with patch.object(c,'ancestor',return_value=True):
                self.assertEqual(c.verify_pending_deployments(self.root)['applied'],[p['id']])

    def publish(self,p,git_answers,**patches):
        import contextlib
        answers=dict({'branch':c.read(self.root/'research/runtime.json')['branch'],'remote':'https://github.com/'+c.read(self.root/'research/runtime.json')['repository'],
                      'fetch':'','rev-parse':'h'*40},**git_answers)
        pushed=[]
        def git(root,*args):
            if args[0]=='push':pushed.append(args);return ''
            return answers[args[0]]
        with contextlib.ExitStack() as stack:
            for target,name,value in [(research,'ROOT',self.root),(research,'LOCAL',self.root/'.local'),(research,'lock',lambda:contextlib.nullcontext()),
                                      (c.git_clean,'dirty_lines',lambda root:[]),(c,'git',git)]+[(c,k,v) for k,v in patches.items()]:
                stack.enter_context(patch.object(target,name,value))
            decision=c.last_review(self.root,p['id'])
            return c.publish_package(self.root,p['id'],p,decision,'human'),pushed

    def test_resuming_a_publication_whose_commit_is_on_origin_only_verifies_it(self):
        # Until 09/24/2026 a resume required HEAD to be the publication commit, so a research
        # commit made on top of it left the package failing every night while it was live.
        p=self.approve();self.receipt(p,status='publication_failed')
        receipt,pushed=self.publish(p,{},ancestor=lambda root,commit,ref:True,deployed=lambda root,config,commit:True)
        self.assertEqual((receipt['status'],pushed),('deployed',[]))
        self.assertEqual(c.last_review(self.root,p['id'])['status'],'applied')

    def test_resuming_a_publication_not_yet_on_origin_pushes_only_its_own_commit(self):
        p=self.approve();self.receipt(p,status='publication_failed')
        with self.assertRaisesRegex(ValueError,'Repository changed after publication attempt'):
            self.publish(p,{},ancestor=lambda root,commit,ref:False)
        receipt,pushed=self.publish(p,{'rev-parse':'f'*40},ancestor=lambda root,commit,ref:False,deployed=lambda root,config,commit:True)
        self.assertEqual((receipt['status'],len(pushed)),('deployed',1))

    def test_a_failed_build_puts_the_tree_back(self):
        import subprocess
        p=self.approve();(c.queue(self.root)/(p['id']+'-publication.json')).unlink()
        restored=[]
        with patch.object(c,'check_base'),patch.object(c,'check_evidence'),patch.object(c,'preview',return_value={'passed':True}), \
             patch.object(c.subprocess,'run',side_effect=subprocess.CalledProcessError(1,'validate.py')):
            with self.assertRaises(subprocess.CalledProcessError):
                self.publish(p,{},restore=lambda root:restored.append(root))
        self.assertEqual(restored,[self.root])
        self.assertFalse((c.queue(self.root)/(p['id']+'-publication.json')).exists(),'nothing was committed, so there is nothing to resume')

    def test_a_decision_recorded_while_publishing_stands(self):
        import subprocess
        from editorial_review import append_event
        p=self.approve();(c.queue(self.root)/(p['id']+'-publication.json')).unlink()
        def build(command,**kw):
            # The owner rejects while validate/build run.
            if 'build.py' in command[-1]:append_event(self.root,{'id':p['id'],'kind':'catalog_change','status':'rejected','reviewer':'human','at':c.now()})
            return subprocess.CompletedProcess(command,0)
        restored=[]
        with patch.object(c,'check_base'),patch.object(c,'check_evidence'),patch.object(c,'preview',return_value={'passed':True}), \
             patch.object(c.subprocess,'run',side_effect=build):
            with self.assertRaisesRegex(ValueError,'decision on this package changed'):
                self.publish(p,{'diff':'research/delivery.json','ls-files':''},restore=lambda root:restored.append(root))
        self.assertEqual(restored,[self.root]);self.assertEqual(c.last_review(self.root,p['id'])['status'],'rejected')

    def test_verify_pending_deployments_ignores_packages_without_a_pending_receipt(self):
        with patch.object(research,'ROOT',self.root):
            self.assertEqual(c.verify_pending_deployments(self.root),{'checked':[],'applied':[],'still_pending':[]})

    def test_catalog_search_followups_preserve_broad_rotation_and_layers(self):
        import discovery
        policy=c.read(ROOT/'research/discovery-policy.json')
        # Limit the operator to the reviewed first project's layer.
        layer=self.project['layer'];policy=dict(policy,layers={layer:policy['layers'][layer]})
        documents=c.projected(self.enqueue(),c.base(self.root))
        c.save(self.root/'research/delivery.json',documents['research/delivery.json'])
        followup=discovery.research_topic(self.root,policy,3)
        self.assertEqual(followup['question'],self.project['next_evidence'])
        self.assertEqual(followup['layer'],layer)
        self.assertEqual(followup['angle'],'catalog-follow-up')
        for cursor,broad in [(0,0),(1,1),(2,2),(4,3),(5,4),(6,5),(8,6)]:
            self.assertEqual(discovery.research_topic(self.root,policy,cursor),discovery.topic(policy,broad))

if __name__=='__main__':unittest.main()


class RestoreTests(unittest.TestCase):
    """An uncommitted publication attempt leaves the clone as it found it (review finding, 09/24/2026)."""
    def test_restore_undoes_written_staged_and_built_files_and_nothing_else(self):
        import subprocess
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);run=lambda *a:subprocess.run(['git',*a],cwd=root,check=True,capture_output=True)
            run('init','-q');run('config','user.email','fixture@example.org');run('config','user.name','Fixture')
            (root/'.gitignore').write_text('.local/\n',encoding='utf-8')
            for rel in ['research/a.json','site/data/b.json']:(root/rel).parent.mkdir(parents=True,exist_ok=True);(root/rel).write_text('{}\n',encoding='utf-8')
            run('add','-A');run('commit','-qm','base')
            (root/'research/a.json').write_text('{"changed": true}\n',encoding='utf-8');run('add','research/a.json')
            (root/'site/data/b.json').write_text('{"changed": true}\n',encoding='utf-8')
            (root/'docs').mkdir();(root/'docs/new.html').write_text('x',encoding='utf-8')
            (root/'.local').mkdir();(root/'.local/keep.json').write_text('{}',encoding='utf-8')
            c.restore(root)
            self.assertEqual(subprocess.run(['git','status','--porcelain'],cwd=root,capture_output=True,text=True).stdout,'')
            self.assertTrue((root/'.local/keep.json').exists(),'ignored private files are never touched')


class PreviewCheckRobustnessTests(unittest.TestCase):
    """A child that prints non-UTF-8 bytes must produce a failed/passed check record, never a crash (seen live 2026-09-09)."""
    def test_run_check_survives_non_utf8_output(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        record = c.run_check([sys.executable, '-c', "import sys;sys.stdout.buffer.write(b'x\\xb7y');sys.stderr.buffer.write(b'z\\xb7');sys.exit(1)"], Path(temp.name))
        self.assertFalse(record['passed']); self.assertIn('x', record['output']); self.assertIn('z', record['output'])
        ok = c.run_check([sys.executable, '-c', "print('fine')"], Path(temp.name))
        self.assertTrue(ok['passed']); self.assertIn('fine', ok['output'])

    def test_preview_validation_missing_is_a_clear_value_error(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        with self.assertRaises(ValueError) as caught:
            c.preview_validation(Path(temp.name), 'catalog-' + 'a' * 24)
        self.assertIn('Validate the preview first', str(caught.exception))
        folder = Path(temp.name) / '.local/catalog-previews' / ('catalog-' + 'a' * 24); folder.mkdir(parents=True)
        (folder / 'validation.json').write_text(json.dumps({'passed': True, 'proposal_hash': 'h'}), encoding='utf-8')
        self.assertEqual(c.preview_validation(Path(temp.name), 'catalog-' + 'a' * 24)['proposal_hash'], 'h')
