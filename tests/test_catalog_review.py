import copy
import hashlib
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
            with self.assertRaises(FileNotFoundError):c.review(self.root,self.payload(p),'human')
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
