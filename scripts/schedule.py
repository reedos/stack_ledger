"""Install the reviewed OpenClaw command job. No chat delivery is configured."""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
NAME='Stack Ledger · daily research'

def cli():
    command=shutil.which('openclaw.cmd') or shutil.which('openclaw')
    if not command:raise RuntimeError('OpenClaw is not installed')
    if command.endswith('.cmd'):
        entry=Path(command).parent/'node_modules/openclaw/openclaw.mjs'
        if not entry.is_file():raise RuntimeError('Cannot locate the OpenClaw Node entry point')
        return [shutil.which('node') or 'node',str(entry)]
    return [command]

def invoke(args):
    result=subprocess.run(cli()+args,cwd=ROOT,capture_output=True,text=True,encoding='utf-8',check=True,timeout=90)
    # Some OpenClaw versions prefix structured output with a health notice.
    start=result.stdout.find('{')
    if start<0:raise RuntimeError('OpenClaw did not return structured output')
    return json.loads(result.stdout[start:])

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--install',action='store_true',help='Create the daily command job')
    parser.add_argument('--editorial',action='store_true',help='Preview the optional monthly editorial job; installation remains explicit')
    args=parser.parse_args()
    config=json.loads((ROOT/'research/runtime.json').read_text(encoding='utf-8'))
    payload=[sys.executable,str(ROOT/'scripts/research.py'),'--publish']
    name=NAME
    declaration='stack-ledger-daily-v1'
    description='Research the five AI layers, validate evidence, build, commit and push data updates. No chat delivery.'
    if args.editorial:
        policy=json.loads((ROOT/'research/editorial-policy.json').read_text(encoding='utf-8'))
        config=dict(config,schedule=policy['schedule'],timezone=policy['timezone'])
        payload=[sys.executable,str(ROOT/'scripts/editorial_review.py'),'assess','--model','--trigger','monthly']
        name='Stack Ledger · monthly editorial review'
        declaration='stack-ledger-editorial-v1'
        description='Bounded accepted-evidence comparison into the private review queue. No approval, build or publication.'
    command=['cron','add','--name',name,'--description',description,'--cron',config['schedule'],'--tz',config['timezone'],'--exact','--session','isolated','--command-argv',json.dumps(payload),'--command-cwd',str(ROOT),'--timeout-seconds','5400','--no-output-timeout-seconds','420','--no-deliver','--declaration-key',declaration,'--json']
    if not args.install:
        print(json.dumps({'name':name,'schedule':config['schedule'],'timezone':config['timezone'],'argv':payload,'cwd':str(ROOT),'delivery':'none'},indent=2));return
    existing=[j for j in invoke(['cron','list','--json']).get('jobs',[]) if j.get('name')==name]
    if existing:
        job=existing[0]
        if len(existing)!=1 or not job.get('enabled') or job.get('payload',{}).get('argv')!=payload or job.get('schedule',{}).get('expr')!=config['schedule']:
            raise RuntimeError('An existing Stack Ledger job differs from the reviewed configuration; inspect it before changing it')
    else:
        response=invoke(command)
        job=response.get('job',response)
        if not job.get('id'):
            matches=[j for j in invoke(['cron','list','--json']).get('jobs',[]) if j.get('name')==name]
            if len(matches)!=1:raise RuntimeError('Could not verify the installed Stack Ledger job')
            job=matches[0]
    print(json.dumps({k:job.get(k) for k in ['id','name','enabled','schedule']},indent=2,ensure_ascii=False))

if __name__=='__main__':main()
