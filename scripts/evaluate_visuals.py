"""Offline visual review evaluation in a disposable copy. No inference or real approvals."""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import editorial as ed
import visual_review as visual
from atomic_json import save

ROOT=Path(__file__).resolve().parents[1]


def fixture(root):
    for name in ['research','site','scripts','tools/research-control']:
        shutil.copytree(ROOT/name,root/name,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    p=visual.policy(root);p['displays']=[d for d in p['displays'] if d['id']=='highlight-chips'];save(root/'research/visual-policy.json',p)
    def adapter(runtime,system,prompt,schema):
        packet=json.loads(prompt);ref=packet['observations'][0]['id']
        response={'action':'REFRAME_PROPOSAL','candidate':None,'visualization':'snapshot','incumbent_scores':None,'candidate_scores':None}
        for field in visual.NARRATIVES:response[field]={'text':'Synthetic evaluation proposal; preserve the sourced checkpoint and review the simpler presentation.', 'refs':[ref]}
        return response
    result=visual.assess(root,True,adapter=adapter)
    if result['failures'] or len(result['proposals'])!=1:raise ValueError('Fixture did not prepare a preview')
    return visual.inbox(root)['proposals'][0]


def evaluate():
    with tempfile.TemporaryDirectory(prefix='stack-ledger-visual-eval-') as folder:
        root=Path(folder);p=fixture(root);before=(root/'research/homepage.json').read_bytes()
        visual.review(root,{'id':p['id'],'decision':'approved','rationale':'Synthetic offline evaluation only.',
            'proposal_hash':p['proposal_hash'],'review_hash':p['review_hash'],'confirmed':True,'reconsider_after':None},'reedos')
        assert (root/'research/homepage.json').read_bytes()==before,'Approval changed configuration'
        # Simulate a separate maintainer applying only the exact approved configuration.
        # Production exposes no visual apply endpoint and no automatic application path.
        save(root/'research/homepage.json',p['config_after'])
        checks=[]
        for command in [[sys.executable,'scripts/validate.py'],[sys.executable,'scripts/build.py']]:
            result=subprocess.run(command,cwd=root,capture_output=True,text=True,timeout=60)
            if result.returncode:raise RuntimeError(result.stdout+result.stderr)
            checks.append(result.stdout.strip())
        before_runtime=ed.read(ROOT/'site/data/ledger.json')['runtime']
        assert ed.read(root/'site/data/ledger.json')['runtime']==before_runtime
        assert len(ed.read(root/'research/homepage.json')['slots'])==5
        output={'mode':'offline mocked fixture; no live model quality claim',
                'approval_did_not_apply':True,'separate_maintainer_simulation':True,
                'runtime_unchanged':True,'checks':checks,'public_changes':False}
    save(ROOT/'.local/editorial-evaluation/visual-results.json',output)
    print(json.dumps(output,indent=2));return output


if __name__=='__main__':evaluate()
