"""Opt-in bounded local-model replay of saved evidence; never enqueues/publishes."""
import argparse
import json
import time
import uuid
from pathlib import Path

import discovery
from research import load, save, digest, now, lock
from research_loop import session_lock

ROOT=Path(__file__).resolve().parents[1]
CASES=('jupiter-power-design','economist-biography')


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',action='store_true',help='Explicitly call local Ollama on two cached cases')
    args=parser.parse_args(argv)
    if not args.run:
        print(json.dumps({'mode':'offline_plan','cases':CASES,'max_model_calls':4,'max_seconds':240,'publication':'none'}));return
    with session_lock(ROOT,uuid.uuid4().hex):
        with lock():replay()


def replay():
    config=load(ROOT/'research/runtime.json')
    config['_instructions']=(ROOT/'research/CONSTITUTION.md').read_text(encoding='utf-8')+'\n'+(ROOT/'research/OPERATING_GUIDE.md').read_text(encoding='utf-8')
    config['model_timeout_seconds']=min(config['model_timeout_seconds'],120)
    p=discovery.policy(ROOT);p['max_model_calls']=4
    receipt={'model_calls':0};deadline=time.monotonic()+240;rows=[]
    labels=load(ROOT/'research/collection-audit-cases.json')['cases']
    for case_id in CASES:
        label=next(c for c in labels if c['id']==case_id)
        saved=load(ROOT/'.local/discovery/evidence'/(label['sha256']+'.json'))
        if digest(saved['text'])!=label['sha256']:raise ValueError('Evidence hash mismatch')
        context={'layer':label['layer'],'question':p['layers'][label['layer']][0]['question'],
                 'query':'saved evidence evaluation','region':'global','angle':'delivery'}
        lead={'context':context}
        try:
            result=discovery.screen(ROOT,config,p,lead,saved['text'],receipt,deadline)
            outcome='empty' if result is None else 'rejected' if result.get('rejected') else 'screened_candidate'
            rows.append({'case':case_id,'outcome':outcome,'result':result,'coverage':lead.get('screen_coverage'),'reason':lead.get('screen_reason')})
        except Exception as error:
            rows.append({'case':case_id,'outcome':'screen_failed','error_type':type(error).__name__})
    report={'at':now(),'model':config['model'],'model_calls':receipt['model_calls'],'cases':rows,
            'limits':'Two purposive cases are not a recall estimate. Model screening is not independent verification or approval. No queue, ledger or publisher was invoked.'}
    save(ROOT/'.local/evaluations/discovery-model-replays'/(now().replace(':','')+'-'+uuid.uuid4().hex[:8]+'.json'),report)
    save(ROOT/'.local/evaluations/discovery-model-replay.json',report)
    print(json.dumps({'model_calls':receipt['model_calls'],'cases':[{'case':r['case'],'outcome':r['outcome']} for r in rows]},indent=2))


if __name__=='__main__':main()
