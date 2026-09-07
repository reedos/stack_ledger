"""Opt-in GPU downtime batches. Default only prints a plan; never starts research."""
import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def gpu_idle(threshold):
    command=shutil.which('nvidia-smi')
    if not command:raise RuntimeError('Cannot check GPU use: nvidia-smi unavailable')
    result=subprocess.run([command,'--query-gpu=utilization.gpu','--format=csv,noheader,nounits'],capture_output=True,text=True,check=True,timeout=10)
    values=[int(v.strip()) for v in result.stdout.splitlines() if v.strip()]
    return bool(values) and all(0<=v<=threshold for v in values)


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--start',action='store_true')
    p.add_argument('--publish',action='store_true',help='Publish validated batches; otherwise private proposals only')
    p.add_argument('--minutes',type=int,default=120)
    p.add_argument('--max-cycles',type=int,default=6)
    p.add_argument('--batch-documents',type=int,default=8)
    p.add_argument('--idle-percent',type=int,default=10)
    a=p.parse_args(argv)
    if not(1<=a.minutes<=720 and 1<=a.max_cycles<=48 and 1<=a.batch_documents<=24 and 0<=a.idle_percent<=20):p.error('Invalid session limits')
    print(json.dumps(dict(start=a.start,publish=a.publish,minutes=a.minutes,max_cycles=a.max_cycles,batch_documents=a.batch_documents,idle_percent=a.idle_percent,stop_file='.local/stop-research-loop',budget='Stops between documents; active document may finish beyond session deadline'),indent=2),flush=True)
    if not a.start:return 0
    deadline=time.monotonic()+a.minutes*60
    idle_samples=0;cycles=0
    while cycles<a.max_cycles and time.monotonic()<deadline:
        if (ROOT/'.local/stop-research-loop').exists():print('Stop requested',flush=True);break
        if (ROOT/'.local/research.lock').exists():print('Another research run is active; stopping',flush=True);break
        idle_samples=idle_samples+1 if gpu_idle(a.idle_percent) else 0
        if idle_samples<3:
            print('Waiting for three low-utilization GPU samples',flush=True)
            time.sleep(min(10,max(0,deadline-time.monotonic())));continue
        remaining=int(deadline-time.monotonic())
        if remaining<1:break
        command=[sys.executable,str(ROOT/'scripts/research.py'),'--max-documents',str(a.batch_documents),'--max-seconds',str(min(900,remaining))]
        if a.publish:command.append('--publish')
        # The runner owns its lock, evidence validation and publication boundary.
        result=subprocess.run(command,cwd=ROOT)
        cycles+=1;idle_samples=0
        if result.returncode:print('Batch failed; inspect local receipts before resuming',flush=True);return result.returncode
    print(f'Session finished after {cycles} batches',flush=True)
    return 0


if __name__=='__main__':sys.exit(main())
