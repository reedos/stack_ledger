"""Duration-driven local research sessions. Without --start this only previews."""
import argparse
import contextlib
import ctypes
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from session_options import add_arguments, choice_args, stopped
from atomic_json import save as atomic

ROOT=Path(__file__).resolve().parents[1]


def session_active(elapsed,cycles,minimum,maximum,max_cycles):
    return elapsed<maximum and (not max_cycles or elapsed<minimum or cycles<max_cycles)


def gpu_idle(threshold):
    command=shutil.which('nvidia-smi')
    if not command:raise RuntimeError('Cannot check GPU use: nvidia-smi unavailable')
    result=subprocess.run([command,'--query-gpu=utilization.gpu','--format=csv,noheader,nounits'],capture_output=True,text=True,check=True,timeout=10)
    values=[int(v.strip()) for v in result.stdout.splitlines() if v.strip()]
    return bool(values) and all(0<=v<=threshold for v in values)


def overnight_seconds(at):
    """Return the remaining 2–7 AM Pacific window, including timezone transitions."""
    try:local=at.astimezone(ZoneInfo('America/Los_Angeles'))
    except ZoneInfoNotFoundError:
        if os.name!='nt':raise
        # Windows Python may lack IANA tzdata. Use the OS-maintained Pacific
        # timezone rules rather than a fixed UTC offset or guessed DST dates.
        script="$u=[DateTimeOffset]::Parse($env:STACK_LEDGER_WINDOW_TIME); $z=[TimeZoneInfo]::FindSystemTimeZoneById('Pacific Standard Time'); $l=[TimeZoneInfo]::ConvertTime($u,$z); if($l.Hour -lt 2 -or $l.Hour -ge 7){0}else{ $end=[DateTime]::SpecifyKind($l.Date.AddHours(7),[DateTimeKind]::Unspecified); ([TimeZoneInfo]::ConvertTimeToUtc($end,$z)-$u.UtcDateTime).TotalSeconds }"
        result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',script],
            capture_output=True,text=True,check=True,timeout=15,
            env=dict(os.environ,STACK_LEDGER_WINDOW_TIME=at.isoformat()))
        remaining=float(result.stdout.strip())
        return max(0,remaining)
    if not 2<=local.hour<7:return 0
    end=local.replace(hour=7,minute=0,second=0,microsecond=0)
    return (end.astimezone(timezone.utc)-at.astimezone(timezone.utc)).total_seconds()


@contextlib.contextmanager
def session_lock(root,sid,skip_if_busy=False):
    path=root/'.local/research-session.lock';path.parent.mkdir(exist_ok=True)
    try:fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    except FileExistsError:
        if not skip_if_busy:raise
        overlap_notice(root)
        yield False
        return
    try:
        with os.fdopen(fd,'w') as f:json.dump({'pid':os.getpid(),'session_id':sid},f)
        yield True
    finally:path.unlink(missing_ok=True)


def overlap_notice(root):
    notice={'status':'skipped','at':datetime.now(timezone.utc).isoformat(),
            'reason':'Scheduled research skipped: another research session or batch is active. Its options and duration are unchanged. Next automatic attempt is the next scheduled night.'}
    atomic(root/'.local/schedule-overlap.json',notice)
    print(json.dumps(notice),flush=True)
    from research_notify import deliver
    from research_notify import message
    try:deliver(root,message(notice,{}),root/'.local/notifications'/('overlap-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'.json'))
    except Exception:print('Could not deliver overlap notification; research remains skipped',flush=True)


def batch_command(args,sid,remaining):
    command=[sys.executable,str(ROOT/'scripts/research.py'),'--session-id',sid,
             '--max-documents',str(args.batch_documents),'--max-seconds',str(max(1,min(900,int(remaining)))),*choice_args(args)]
    if args.publish:command.append('--publish')
    return command


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--start',action='store_true')
    p.add_argument('--publish',action='store_true',help='Publish validated monitoring batches; discovery stays private')
    p.add_argument('--minutes',type=int,default=120)
    p.add_argument('--min-minutes',type=int,default=None,help='Legacy optional cycle-cap minimum; defaults to full duration')
    p.add_argument('--max-cycles',type=int,default=0,help='0 means no session batch cap')
    p.add_argument('--batch-documents',type=int,default=8)
    p.add_argument('--idle-percent',type=int,default=10)
    p.add_argument('--ignore-gpu-busy',action='store_true',help='Dedicated research time; do not wait for low GPU utilization')
    p.add_argument('--keep-awake',action='store_true',help='Prevent automatic system sleep during the session on Windows')
    p.add_argument('--overnight',action='store_true',help='Research inside the 2–7 AM Pacific window; finish active work safely at 7 AM')
    add_arguments(p)
    a=p.parse_args(argv)
    if a.min_minutes is None:a.min_minutes=a.minutes
    if not(1<=a.minutes<=1440 and 0<=a.min_minutes<=a.minutes and 0<=a.max_cycles<=10000 and 1<=a.batch_documents<=24 and 0<=a.idle_percent<=20):p.error('Invalid session limits')
    plan=vars(a).copy();plan['budget']='No total document cap. Duration includes waits. Graceful stop finishes the active document and publication.'
    print(json.dumps(plan,indent=2),flush=True)
    if not a.start:return 0
    duration=overnight_seconds(datetime.now(timezone.utc)) if a.overnight else a.minutes*60
    if duration<=0:print('Outside the 2–7 AM Pacific window; no research started',flush=True);return 0
    if a.overnight and (ROOT/'.local/research.lock').exists():
        overlap_notice(ROOT);return 0
    sid=uuid.uuid4().hex
    with session_lock(ROOT,sid,skip_if_busy=a.overnight) as acquired:
        if not acquired:return 0
        folder=ROOT/'.local/sessions'/sid;folder.mkdir(parents=True,exist_ok=True)
        report=dict(session_id=sid,pid=os.getpid(),started_at=datetime.now(timezone.utc).isoformat(),
                    ends_at=(datetime.now(timezone.utc)+timedelta(seconds=duration)).isoformat(),
                    duration_seconds=duration,batches=0,failed_batches=0,consecutive_failures=0,state='starting',options=plan)
        started=time.monotonic();deadline=started+duration
        def checkpoint(state,**fields):
            report.update(state=state,elapsed_seconds=round(time.monotonic()-started),**fields)
            # The per-session record is authoritative; a locked UI mirror cannot kill research.
            atomic(folder/'status.json',report)
            try:atomic(ROOT/'.local/session-status.json',report)
            except OSError:print('Status mirror unavailable; per-session status is current.',flush=True)
        def pause(seconds,state):
            until=min(deadline,time.monotonic()+seconds)
            while time.monotonic()<until and not stopped(ROOT,sid):
                checkpoint(state);print(state,flush=True);time.sleep(min(10,max(0,until-time.monotonic())))
        awake=False
        try:
            if a.keep_awake and os.name=='nt':
                awake=bool(ctypes.windll.kernel32.SetThreadExecutionState(0x80000001))
                if not awake:raise RuntimeError('Windows could not enable keep-awake')
            checkpoint('starting',keep_awake_active=awake)
            cycles=0;idle_samples=0;telemetry_failures=0
            while session_active(time.monotonic()-started,cycles,a.min_minutes*60,duration,a.max_cycles):
                if stopped(ROOT,sid):checkpoint('stopped');return 0
                if (ROOT/'.local/research.lock').exists():pause(30,'waiting for another research batch');continue
                if not a.ignore_gpu_busy:
                    try:
                        idle_samples=idle_samples+1 if gpu_idle(a.idle_percent) else 0
                        telemetry_failures=0
                    except (OSError,ValueError,RuntimeError,subprocess.SubprocessError):
                        idle_samples=0;telemetry_failures+=1
                        if telemetry_failures>=3:
                            checkpoint('blocked',failure_reason='GPU telemetry failed three times; cannot verify the requested idle condition. Check nvidia-smi before restarting.')
                            return 1
                    if idle_samples<3:pause(10,'waiting for idle GPU');continue
                remaining=deadline-time.monotonic()
                if remaining<1:break
                checkpoint('researching',batch_started_at=datetime.now(timezone.utc).isoformat())
                command=batch_command(a,sid,remaining)
                with (folder/'output.log').open('a',encoding='utf-8') as log:
                    child=subprocess.Popen(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,
                        creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),env=dict(os.environ,PYTHONIOENCODING='utf-8',PYTHONUNBUFFERED='1'))
                    while child.poll() is None:
                        if time.monotonic()>=deadline:(folder/'stop').touch()
                        checkpoint('finishing current batch' if stopped(ROOT,sid) else 'researching')
                        print(f'Session {sid}: batch {cycles+1}; {report["elapsed_seconds"]}s elapsed',flush=True)
                        time.sleep(5)
                cycles+=1;idle_samples=0
                report['batches']=cycles
                try:
                    from visual_review import checkpoint as visual_checkpoint
                    visual_checkpoint(ROOT,folder)
                except (OSError,ValueError,KeyError):
                    print('Visual dependency check unavailable; research evidence is retained.',flush=True)
                if child.returncode==2:
                    report['consecutive_failures']=0
                    report['idle_checks']=report.get('idle_checks',0)+1
                    pause(300,'waiting for eligible sources')
                elif child.returncode:
                    report['failed_batches']+=1
                    report['consecutive_failures']+=1
                    checkpoint('batch failed',last_exit_code=child.returncode)
                    if child.returncode==3 or report['consecutive_failures']>=3:
                        reason=('Publication/preflight failed. Saved evidence is retained; inspect the batch log and resolve repository or validation errors before restarting.'
                                if child.returncode==3 else 'Three consecutive batch failures. Inspect the batch log before restarting; retries have stopped.')
                        checkpoint('blocked',failure_reason=reason)
                        print(reason,flush=True)
                        return 1
                    pause(60,'retrying after batch failure')
                else:
                    report['consecutive_failures']=0
                    pause(20,'between batches')
            if report['consecutive_failures']:
                checkpoint('failed',failure_reason='Session ended with unresolved batch failures. Inspect the batch log.')
                return 1
            checkpoint('completed' if time.monotonic()>=deadline else 'cycle limit reached')
            return 0
        except BaseException:
            (folder/'stop').touch()
            try:checkpoint('interrupted')
            except OSError:report['state']='interrupted'
            raise
        finally:
            if awake:ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
            from visual_review import finish_session
            finish_session(ROOT,report,folder)
            from research_notify import notify_session
            notification=notify_session(ROOT,report,folder)
            print('Session notification: '+notification['status'],flush=True)


if __name__=='__main__':sys.exit(main())
