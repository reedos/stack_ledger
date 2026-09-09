"""Offline catalog approval/application evaluation in a disposable repository.

Only synthetic decisions; git fetch/push and Pages responses are mocked.
No inference, credentials, actual repository writes or external publication.
"""
import io,json,shutil,subprocess,tempfile
from pathlib import Path
from unittest.mock import patch
import catalog_review as c
import findings_review
import research

ROOT=Path(__file__).resolve().parents[1]
def evaluate():
    with tempfile.TemporaryDirectory(prefix='stack-catalog-') as folder:
        root=Path(folder)
        for name in ['scripts','research','site','tests','tools','.github']:
            shutil.copytree(ROOT/name,root/name,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        for name in ['.gitignore','AGENTS.md','README.md']:shutil.copy2(ROOT/name,root/name)
        def command(*args):return subprocess.check_output(list(args),cwd=root,text=True,stderr=subprocess.PIPE).strip()
        command('python','scripts/build.py');command('git','init','-b','main')
        command('git','config','user.name','Offline fixture');command('git','config','user.email','fixture@example.invalid')
        config=c.read(root/'research/runtime.json');command('git','remote','add','origin','https://github.com/'+config['repository'])
        command('git','add','--','scripts','research','site','tests','tools','.github','docs','.gitignore','AGENTS.md','README.md');command('git','commit','-m','fixture baseline')
        baseline=command('git','rev-parse','HEAD')
        before=c.base(root);p=dict(before['research/delivery.json']['projects'][0]);p['next_evidence']='Synthetic offline evaluation: require the next operator disclosure.'
        body=b'Synthetic fixture evidence; not a real-world research finding.'
        import hashlib
        sha=hashlib.sha256(body).hexdigest();proof=root/'.local/catalog-evidence'/(sha+'.txt');proof.parent.mkdir(parents=True);proof.write_bytes(body)
        addition=dict(p,id='offline-fixture-project',name='Synthetic offline project',observations=[])
        proposal=c.enqueue(root,'Synthetic offline catalog test',[{'target':'project','id':row['id'],'after':row,'evidence':['fixture']} for row in [p,addition]],
            [{'id':'fixture','url':'https://example.invalid/fixture','published_at':None,'retrieved_at':c.now(),'sha256':sha,'summary':body.decode()}],author='offline fixture')
        result=c.preview(root,proposal['id']);assert result['passed'],result['checks']
        assert c.base(root)==before
        original_git=c.git;transports=[]
        def fake_git(at,*args):
            if args[0] in {'fetch','push'}:transports.append(args[0]);return ''
            if args==('rev-parse','origin/main'):return baseline
            return original_git(at,*args)
        def live_fixture(url,timeout):
            name=url.split('/data/')[1].split('?')[0]
            return io.BytesIO((root/'site/data'/name).read_bytes())
        with patch.object(findings_review,'reviewer',return_value='fixture-human'),patch.object(research,'ROOT',root),patch.object(research,'LOCAL',root/'.local'),patch.object(c,'git',side_effect=fake_git),patch.object(c,'urlopen',side_effect=live_fixture):
            value={'id':proposal['id'],'decision':'approved','rationale':'Synthetic offline human approval fixture only.',
                'proposal_hash':c.digest(proposal),'review_hash':c.digest(None),'confirmed':True}
            c.review(root,value,'fixture-human');assert command('git','status','--porcelain')==''
            receipt=c.apply_publish(root,proposal['id'],c.digest(proposal),c.digest(c.last_review(root,proposal['id'])),'fixture-human',True)
        assert receipt['status']=='deployed';assert transports==['fetch','push'];assert command('git','status','--porcelain')==''
        assert c.read(root/'site/data/delivery.json')['projects'][0]['next_evidence']==p['next_evidence']
        assert c.read(root/'docs/data/delivery.json')==c.read(root/'research/delivery.json')
        assert len(c.read(root/'docs/data/delivery.json')['projects'])==len(before['research/delivery.json']['projects'])+1
        source_id=p['milestones'][0]['source']
        assert addition['next_evidence'] in research.coverage_context(root,{'id':source_id})
        import discovery
        policy=c.read(root/'research/discovery-policy.json')
        assert discovery.research_topic(root,policy,3)['question']==p['next_evidence']
        assert c.read(root/'site/data/ledger.json')['runtime']==before['site/data/ledger.json']['runtime']
        assert c.last_review(root,proposal['id'])['status']=='applied'
        report={'mode':'offline disposable repository; synthetic human decision and mocked remote transport/Pages',
            'preview_validation':True,'python_tests':True,'editorial_evaluation':True,'canonical_mirrors':True,
            'git_commit':True,'mocked_push_and_live_comparison':True,'followup_recorded':True,'runtime_preserved':True,
            'project_addition_and_followup_context':True,'catalog_discovery_followup':True,'actual_publication':False,'inference':False}
        c.save(ROOT/'.local/catalog-evaluation/results.json',report);print(json.dumps(report,indent=2));return report
if __name__=='__main__':evaluate()
