"""Loopback-only research control panel. Opening it never starts inference."""
import argparse
import csv
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from session_options import LAYERS, MODES, SOURCE_KINDS

ROOT=Path(__file__).resolve().parents[1]


def gpu_values(output):
    row=next(csv.reader(output.strip().splitlines()))
    if len(row)!=3:raise ValueError('Unexpected GPU telemetry')
    name,usage,temp=(v.strip() for v in row)
    def number(value,maximum):
        if value in ('N/A','[N/A]','[Not Supported]'):return None
        n=int(value)
        if not 0<=n<=maximum:raise ValueError('Invalid GPU reading')
        return n
    return {'name':name,'utilization':number(usage,100),'temperature':number(temp,150)}


class GpuSampler:
    """Read-only, request-driven telemetry; shared across tabs, never starts inference."""
    def __init__(self):
        self.guard=threading.Lock();self.history=deque(maxlen=300)
        self.last_attempt=None;self.latest=None

    def snapshot(self):
        with self.guard:
            if self.last_attempt is None or time.monotonic()-self.last_attempt>=2:
                self.last_attempt=time.monotonic()
                value={'name':None,'utilization':None,'temperature':None}
                state='unavailable'
                try:
                    command=shutil.which('nvidia-smi')
                    if command:
                        result=subprocess.run([command,'--id=0','--query-gpu=name,utilization.gpu,temperature.gpu',
                            '--format=csv,noheader,nounits'],capture_output=True,text=True,check=True,timeout=2,
                            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                        value=gpu_values(result.stdout)
                        state='live' if value['utilization'] is not None and value['temperature'] is not None else 'partial'
                except (OSError,ValueError,StopIteration,subprocess.SubprocessError):pass
                self.latest=dict(value,timestamp_ms=round(time.time()*1000),status=state)
                self.history.append(self.latest)
            return {'latest':self.latest,'samples':list(self.history),'window_seconds':600,'interval_seconds':2,'gpu_index':0}


def command(options):
    expected={'minutes','direction','layers','source_kinds','publish','idle_only','keep_awake'}
    if not isinstance(options,dict) or set(options)!=expected:raise ValueError('Unexpected session options')
    if type(options['minutes']) is not int or not 1<=options['minutes']<=1440:raise ValueError('Choose 1 to 1440 minutes')
    if options['direction'] not in MODES:raise ValueError('Unknown direction')
    for key,choices in [('layers',LAYERS),('source_kinds',SOURCE_KINDS)]:
        v=options[key]
        if not isinstance(v,list) or len(v)>len(choices) or any(not isinstance(x,str) or x not in choices for x in v):raise ValueError('Invalid '+key)
    for key in ['publish','idle_only','keep_awake']:
        if type(options[key]) is not bool:raise ValueError('Invalid '+key)
    argv=[sys.executable,str(ROOT/'scripts/research_loop.py'),'--start','--minutes',str(options['minutes']),
          '--direction',options['direction']]
    for key in ['layers','source_kinds']:
        if options[key]:argv+=['--'+key.replace('_','-'),*options[key]]
    if options['publish']:argv.append('--publish')
    if options['keep_awake']:argv.append('--keep-awake')
    if not options['idle_only']:argv.append('--ignore-gpu-busy')
    return argv


def read(path,default=None):
    try:return json.loads(path.read_text(encoding='utf-8'))
    except (OSError,ValueError):return default


def tail(path,limit=18000):
    try:
        with path.open('rb') as f:
            f.seek(0,2);f.seek(max(0,f.tell()-limit));return f.read().decode('utf-8',errors='replace')
    except OSError:return ''


class Controller:
    def __init__(self,root=ROOT):
        self.root=root;self.child=None;self.guard=threading.Lock()

    def status(self):
        report=read(self.root/'.local/session-status.json',{})
        lock=read(self.root/'.local/research-session.lock',{})
        sid=lock.get('session_id',report.get('session_id',''))
        valid=bool(re.fullmatch('[a-f0-9]{32}',sid))
        if valid:report=read(self.root/'.local/sessions'/sid/'status.json',report)
        active=(self.root/'.local/research-session.lock').exists()
        return dict(session=report,active=active,launching=bool(self.child and self.child.poll() is None),
            log=tail(self.root/'.local/sessions'/sid/'output.log') if valid else '',
            controller_log=tail(self.root/'.local/control-launch.log',3000),
            discovery=read(self.root/'.local/discovery/latest.json',{}),
            notification=read(self.root/'.local/sessions'/sid/'notification.json') if valid else None,
            visual_assessment=read(self.root/'.local/sessions'/sid/'visual-progress.json') if valid else None,
            schedule_notice=read(self.root/'.local/schedule-overlap.json'))

    def start(self,options):
        argv=command(options)
        with self.guard:
            if self.status()['active'] or self.child and self.child.poll() is None:raise ValueError('A session is already active')
            if (self.root/'.local/research.lock').exists():raise ValueError('A research batch is already active')
            if (self.root/'.local/stop-research-loop').exists():raise ValueError('Global stop file is present; inspect it before starting')
            (self.root/'.local').mkdir(exist_ok=True)
            with (self.root/'.local/control-launch.log').open('w',encoding='utf-8') as log:
                self.child=subprocess.Popen(argv,cwd=self.root,stdout=log,stderr=subprocess.STDOUT,
                    creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),env=dict(os.environ,PYTHONIOENCODING='utf-8',PYTHONUNBUFFERED='1'))
        return {'started':True}

    def stop(self):
        with self.guard:
            lock=read(self.root/'.local/research-session.lock',{})
            sid=lock.get('session_id','')
            if not re.fullmatch('[a-f0-9]{32}',sid):raise ValueError('No active session yet; wait for startup')
            folder=self.root/'.local/sessions'/sid
            folder.mkdir(parents=True,exist_ok=True);(folder/'stop').touch()
        return {'stop_requested':True}


def server(root=ROOT):
    token=secrets.token_urlsafe(32);controller=Controller(root);gpu=GpuSampler()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def send(self,code,body,kind='application/json',preview=False):
            raw=body if isinstance(body,bytes) else body.encode('utf-8') if isinstance(body,str) else json.dumps(body).encode('utf-8')
            self.send_response(code);self.send_header('Content-Type',kind+'; charset=utf-8')
            self.send_header('Content-Length',str(len(raw)));self.send_header('Cache-Control','no-store')
            # Site previews may be framed by the panel itself (same origin, same session token) so a
            # reviewer sees the proposed change in place; everything else refuses framing.
            self.send_header('X-Content-Type-Options','nosniff');self.send_header('X-Frame-Options','SAMEORIGIN' if preview else 'DENY')
            self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'"+(" 'unsafe-inline'" if preview else '')+"; frame-ancestors "+("'self'" if preview else "'none'")+"; base-uri 'none'; form-action 'self'")
            self.end_headers();self.wfile.write(raw)
        def valid(self):return self.headers.get('Host')==f'127.0.0.1:{self.server.server_port}' and self.path.startswith('/'+token+'/')
        def do_GET(self):
            if not self.valid():self.send(403,{'error':'Local session URL required'});return
            prefix='/'+token+'/preview/'
            if self.path.startswith(prefix):
                from urllib.parse import unquote,urlsplit
                import mimetypes
                import catalog_review
                parts=unquote(urlsplit(self.path).path[len(prefix):]).split('/',1)
                if not catalog_review.RID.fullmatch(parts[0]):self.send(404,{});return
                folder=(root/'.local/catalog-previews'/parts[0]/'docs').resolve()
                target=(folder/(parts[1] if len(parts)>1 else '')).resolve()
                if target!=folder and folder not in target.parents:self.send(403,{});return
                if target.is_dir():target=target/'index.html'
                if not target.is_file():self.send(404,{});return
                self.send(200,target.read_bytes(),mimetypes.guess_type(str(target))[0] or 'application/octet-stream',preview=True);return
            route=self.path.split('/')[-1]
            if route=='status':self.send(200,controller.status());return
            if route=='gpu':self.send(200,gpu.snapshot());return
            if route=='findings':
                from findings_review import inbox
                try:self.send(200,inbox(root))
                except (OSError,ValueError):self.send(503,{'error':'Review queue is unavailable; try again shortly'})
                return
            assets={'':('index.html','text/html'),'control.js':('control.js','text/javascript'),'control.css':('control.css','text/css'),'reviews.js':('reviews.js','text/javascript')}
            if route=='visuals':
                from visual_review import inbox
                from findings_review import reviewer
                try:self.send(200,dict(inbox(root),reviewer=reviewer(root)))
                except (OSError,ValueError):self.send(503,{'error':'Visual review queue is unavailable'})
                return
            if '/visual-preview/' in self.path:
                from visual_review import load
                import editorial as ed
                try:
                    rid=self.path.split('/')[-1];p,s=load(root,rid)
                    path=root/'.local/editorial'/('visual-'+p['snapshot_hash'])/(rid+'.html')
                    html=path.read_text(encoding='utf-8')
                    if ed.hashed(html)!=p['preview_hash']:raise ValueError('Preview changed')
                    self.send(200,html,'text/html',preview=True)
                except (ValueError,OSError,KeyError):self.send(404,{'error':'Preview unavailable'})
                return
            assets['visuals.js']=('visuals.js','text/javascript')
            if route not in assets:self.send(404,{});return
            name,kind=assets[route];self.send(200,(root/'tools/research-control'/name).read_text(encoding='utf-8'),kind)
        def do_POST(self):
            origin=f'http://127.0.0.1:{self.server.server_port}'
            if not self.valid() or self.headers.get('Origin')!=origin or self.headers.get('X-Session-Key')!=token:
                self.send(403,{'error':'Local control request required'});return
            try:
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=4096 or self.headers.get('Content-Type')!='application/json':raise ValueError('Invalid request')
                value=json.loads(self.rfile.read(size))
                route=self.path.split('/')[-1]
                if route=='start':result=controller.start(value)
                elif route=='stop' and value=={}:result=controller.stop()
                elif route=='review':
                    from findings_review import review
                    result=review(root,value)
                elif route in {'visual-review','visual-assess'}:
                    from findings_review import reviewer
                    import visual_review
                    owner=reviewer(root)
                    if not owner:raise ValueError('This local account cannot review visual recommendations')
                    if route=='visual-review':result=visual_review.review(root,value,owner)
                    else:
                        if value!={'model':False}:raise ValueError('Panel assessment is offline; model evaluation runs at session conclusion')
                        if controller.status()['active'] or (root/'.local/research.lock').exists():raise ValueError('Wait for active research to finish before an on-demand assessment')
                        result=visual_review.assess(root)
                elif route in {'catalog-preview','catalog-review','catalog-publish'}:
                    from findings_review import reviewer
                    import catalog_review
                    owner=reviewer(root)
                    if not owner:raise ValueError('This local account cannot review catalog changes')
                    if route!='catalog-review' and ((root/'.local/research.lock').exists() or (root/'.local/research-session.lock').exists()):
                        raise ValueError('An automatic publication or research batch is running right now; the preview and publish actions will work again when it finishes (usually within a few minutes).')
                    if route=='catalog-preview':
                        if set(value)!={'id'}:raise ValueError('Invalid preview request')
                        result=catalog_review.preview(root,value['id'])
                    elif route=='catalog-review':result=catalog_review.review(root,value,owner)
                    else:
                        if set(value)!={'id','proposal_hash','review_hash','confirmed'}:raise ValueError('Invalid publication request')
                        result=catalog_review.apply_publish(root,value['id'],value['proposal_hash'],value['review_hash'],owner,value['confirmed'])
                else:raise ValueError('Unknown action')
                self.send(200,result)
            except FileExistsError:self.send(409,{'error':'Another review is being saved; reload and try again'})
            except FileNotFoundError:self.send(409,{'error':('A file changed while the preview was being built, usually because a publication or research batch is running; try again in a minute.' if self.path.split('/')[-1].startswith('catalog-') else 'Finding is no longer available; reload the inbox')})
            except (ValueError,TypeError) as e:self.send(400,{'error':str(e)})
            except (OSError,subprocess.SubprocessError):self.send(503,{'error':'Catalog operation failed; saved evidence and publication receipts are retained. Check the local repository and retry.'})
    http=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    return http,f'http://127.0.0.1:{http.server_port}/{token}/'


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--open',action='store_true')
    parser.add_argument('--ephemeral',action='store_true',help='Do not replace the saved panel URL (for isolated UI tests)')
    args=parser.parse_args()
    http,url=server()
    if not args.ephemeral:
        (ROOT/'.local').mkdir(exist_ok=True)
        (ROOT/'.local/research-control-url.txt').write_text(url,encoding='utf-8')
    print('Research control: '+url,flush=True)
    if args.open:webbrowser.open(url)
    try:http.serve_forever()
    except KeyboardInterrupt:pass
    finally:http.server_close()


if __name__=='__main__':main()
