"""Evidence-linked catalog packages in the existing human review queue.

Research may enqueue and preview. Only explicit local review authorizes application.
No arbitrary paths, code, deletes, source-policy wildcards or model approvals.
"""
import copy
import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen
from editorial_review import queue, events, append_event, locked, save, now
from validate import require, text, timestamp

TARGETS={
 'project':('research/delivery.json','projects'),
 'company':('research/ecosystem.json','companies'),
 'product':('research/expansion.json','products'),
 'source':('research/sources.json','sources'),
 'metric':('research/catalog.json','metrics'),
 'observation':('site/data/ledger.json','observations'),
 'note':('site/data/ledger.json','events'),
}
FILES=tuple(dict.fromkeys(p for p,k in TARGETS.values()))
RID=re.compile(r'catalog-[a-f0-9]{24}')
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True,ensure_ascii=False,allow_nan=False).encode()).hexdigest()
def git(root,*args):return subprocess.check_output(['git',*args],cwd=root,text=True,encoding='utf-8',stderr=subprocess.PIPE).strip()
def last_review(root,rid):return next((e for e in reversed(events(root)) if e.get('kind')=='catalog_change' and e['id']==rid),None)
def package(root,rid):
    require(isinstance(rid,str) and RID.fullmatch(rid),'Invalid catalog package ID')
    p=read(queue(root)/(rid+'.json'))
    require(isinstance(p,dict),'Invalid package object')
    require(p.get('id')==rid and p.get('kind')=='catalog_change','Invalid package identity')
    return p
def base(root):return {p:read(root/p) for p in FILES}
def check_base(root,p):
    # Unrelated run receipts and separately reviewed additions do not invalidate
    # a proposal. Every edited incumbent must still match, then the complete
    # projected catalog must pass fresh cross-file validation before application.
    projected(p,base(root))

def projected(p,documents):
    d=copy.deepcopy(documents)
    for op in p['changes']:
        require(set(op)=={'target','id','before','after','evidence'},'Unexpected catalog operation')
        require(op['target'] in TARGETS and isinstance(op['after'],dict),'Unsupported catalog operation')
        require(op['after'].get('id')==op['id'],'Object ID mismatch')
        path,key=TARGETS[op['target']];rows=d[path][key]
        index=next((i for i,r in enumerate(rows) if r['id']==op['id']),None)
        current=rows[index] if index is not None else None
        require(current==op['before'],'Object changed since proposal')
        if op['target']=='note' and current is not None:
            require(current==op['after'],'Existing notes need appended correction records')
        if op['target']=='observation' and current is not None:
            require({k:v for k,v in current.items() if k!='superseded_by'}=={k:v for k,v in op['after'].items() if k!='superseded_by'},'Numerical revisions need appended correction records')
        if index is None:rows.append(op['after'])
        else:rows[index]=op['after']
    # One canonical edit feeds every existing public snapshot.
    ledger=d['site/data/ledger.json'];ledger['metrics']=copy.deepcopy(d['research/catalog.json']['metrics'])
    registry=d['research/sources.json']
    registered={s['id']:s for s in registry['sources']}
    ledger['sources']=[copy.deepcopy(registered.get(s['id'],s)) for s in ledger['sources']]
    existing={s['id'] for s in ledger['sources']}
    ledger['sources'].extend(copy.deepcopy(s) for s in registry['sources'] if s['id'] not in existing)
    for name in ['delivery','ecosystem','expansion']:
        path=f'research/{name}.json'
        if d[path]!=documents[path]:d[path]['reviewed_at']=p['created_at']
        d[f'site/data/{name}.json']=copy.deepcopy(d[path])
    d['site/data/source-books.json']={k:copy.deepcopy(registry[k]) for k in ['region_books','collection']}
    return d

def enqueue(root,title,changes,evidence,author='GPT Astra'):
    """Maintainer/research entry point. Enqueue never approves or publishes."""
    text(title,200);text(author,100)
    require(isinstance(changes,list) and 0<len(changes)<=100,'Package needs 1–100 object changes')
    require(isinstance(evidence,list) and evidence,'Source evidence required')
    for e in evidence:
        require(set(e)=={'id','url','published_at','retrieved_at','sha256','summary'},'Unexpected evidence fields')
        text(e['id'],140);text(e['summary'],2000);timestamp(e['retrieved_at'])
        if e['published_at'] is not None:
            from datetime import date
            require(date.fromisoformat(e['published_at'])<=timestamp(e['retrieved_at']).date(),'Evidence publication is in the future')
        from urllib.parse import urlparse
        u=urlparse(e['url']);require(u.scheme=='https' and u.hostname and not u.username and not u.password,'Public HTTPS evidence required')
        require(re.fullmatch('[a-f0-9]{64}',e['sha256']),'Evidence hash required')
        retained=root/'.local/catalog-evidence'/(e['sha256']+'.txt')
        require(retained.exists() and hashlib.sha256(retained.read_bytes()).hexdigest()==e['sha256'],'Retained evidence missing or changed')
    ids={e['id'] for e in evidence};require(len(ids)==len(evidence),'Duplicate evidence ID')
    documents=base(root);ops=[];seen=set()
    for c in changes:
        require(set(c)=={'target','id','after','evidence'} and c['target'] in TARGETS,'Invalid proposed object')
        require((c['target'],c['id']) not in seen,'Duplicate object change');seen.add((c['target'],c['id']))
        require(c['evidence'] and set(c['evidence'])<=ids,'Every change needs attached evidence')
        if c['target']=='source':
            require(any(e['url']==c['after'].get('url') and e['id'] in c['evidence'] for e in evidence),'Source URL must match retained evidence')
        path,key=TARGETS[c['target']]
        before=next((r for r in documents[path][key] if r['id']==c['id']),None)
        require(before!=c['after'],'Unchanged object is not a catalog update')
        ops.append(dict(c,before=before))
    p=dict(kind='catalog_change',title=title,author=author,created_at=now(),base_revision=git(root,'rev-parse','HEAD'),base_hashes={k:digest(v) for k,v in documents.items()},changes=ops,evidence=evidence)
    p['id']='catalog-'+digest({k:p[k] for k in ['base_hashes','changes','evidence']})[:24]
    projected(p,documents)
    with locked(root):
        path=queue(root)/(p['id']+'.json')
        if path.exists():return read(path)
        save(path,p)
    return p

def check_evidence(root,p):
    require(isinstance(p['evidence'],list) and p['evidence'],'Evidence required')
    ids={e['id'] for e in p['evidence']}
    require(len(ids)==len(p['evidence']),'Duplicate evidence identity')
    require(p['changes'] and len(p['changes'])<=100,'Invalid operation count')
    require(len({(c['target'],c['id']) for c in p['changes']})==len(p['changes']),'Duplicate operation')
    for op in p['changes']:
        require(op['evidence'] and set(op['evidence'])<=ids,'Missing operation evidence')
        if op['target']=='source':
            require(any(e['url']==op['after'].get('url') and e['id'] in op['evidence'] for e in p['evidence']),'Source URL must match retained evidence')
    for e in p['evidence']:
        require(set(e)=={'id','url','published_at','retrieved_at','sha256','summary'},'Unexpected evidence fields')
        timestamp(e['retrieved_at']);text(e['summary'],2000)
        if e['published_at'] is not None:
            from datetime import date
            require(date.fromisoformat(e['published_at'])<=timestamp(e['retrieved_at']).date(),'Evidence publication is in the future')
        from urllib.parse import urlparse
        u=urlparse(e['url']);require(u.scheme=='https' and u.hostname and not u.username and not u.password,'Public HTTPS evidence required')
        require(re.fullmatch('[a-f0-9]{64}',e['sha256']),'Invalid evidence hash')
        f=root/'.local/catalog-evidence'/(e['sha256']+'.txt')
        require(f.exists() and hashlib.sha256(f.read_bytes()).hexdigest()==e['sha256'],'Retained evidence changed')

def preview(root,rid):
    p=package(root,rid);check_base(root,p);check_evidence(root,p)
    destination=root/'.local/catalog-previews'/rid
    destination.mkdir(parents=True,exist_ok=True)
    # Isolated copy excludes local secrets, repositories, caches and runtime processes.
    for name in ['scripts','research','site','tests','tools','.github']:
        if not (root/name).exists():continue
        shutil.copytree(root/name,destination/name,dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__','*.pyc','*.tmp'))  # *.tmp: atomic saves in flight
    for name in ['AGENTS.md','README.md']:
        if (root/name).exists():shutil.copy2(root/name,destination/name)
    for name,value in projected(p,base(root)).items():save(destination/name,value)
    commands=[[sys.executable,'scripts/validate.py'],[sys.executable,'scripts/build.py'],[sys.executable,'-m','unittest','discover','-s','tests'],[sys.executable,'scripts/evaluate_editorial.py']]
    checks=[]
    for command in commands:
        r=subprocess.run(command,cwd=destination,capture_output=True,text=True,encoding='utf-8',timeout=120)
        checks.append({'command':' '.join(command[1:]),'passed':r.returncode==0,'output':(r.stdout+r.stderr)[-12000:]})
        if r.returncode:break
    result={'proposal_hash':digest(p),'base_hashes':p['base_hashes'],'passed':all(c['passed'] for c in checks) and len(checks)==len(commands),'checks':checks,'at':now()}
    save(destination/'validation.json',result)
    return result

def inbox(root,errors=None):
    rows=[]
    for path in sorted(queue(root).glob('catalog-*.json')):
        if not RID.fullmatch(path.stem):continue
        try:
            p=package(root,path.stem);review=last_review(root,p['id'])
            require(isinstance(p['changes'],list) and isinstance(p['evidence'],list),'Invalid package shape')
            validation=root/'.local/catalog-previews'/p['id']/'validation.json'
            rows.append(dict(p,status=review['status'] if review else 'pending_review',last_review=review,
                             proposal_hash=digest(p),review_hash=digest(review),validation=read(validation) if validation.exists() else None))
        except (OSError,ValueError,KeyError,TypeError):
            if errors is not None:errors.append(path.name)
    return rows

def review(root,value,reviewer):
    require(set(value)=={'id','decision','rationale','proposal_hash','review_hash','confirmed'},'Invalid catalog review fields')
    require(value['decision'] in {'approved','deferred','rejected'},'Invalid catalog decision')
    require(value['confirmed'] is True and reviewer,'Human review confirmation required');text(value['rationale'],1200)
    from findings_review import reviewer as current_reviewer
    require(current_reviewer(root)==reviewer,'Unauthorized local reviewer')
    with locked(root):
        p=package(root,value['id']);prior=last_review(root,p['id'])
        require(digest(p)==value['proposal_hash'] and digest(prior)==value['review_hash'],'Package or review changed; reload')
        if value['decision']=='approved':
            check_base(root,p);check_evidence(root,p)
            validation=read(root/'.local/catalog-previews'/p['id']/'validation.json')
            require(validation['passed'] and validation['proposal_hash']==digest(p),'Passing preview required before approval')
        append_event(root,dict(id=p['id'],kind='catalog_change',status=value['decision'],reviewer=reviewer,rationale=value['rationale'],at=now(),proposal_hash=digest(p)))
    return {'status':value['decision'],'published':False}

def apply_publish(root,rid,proposal_hash,review_hash,reviewer,confirmed=False):
    """Human publication: the reviewer is the local authorized account and confirms explicitly."""
    require(confirmed is True and reviewer,'Explicit human publication action required')
    p=package(root,rid)
    with locked(root):
        decision=last_review(root,rid)
        require(digest(p)==proposal_hash and digest(decision)==review_hash,'Package or review changed; reload')
        require(decision and decision['status']=='approved' and decision['proposal_hash']==digest(p),'Recorded approval required')
        from findings_review import reviewer as current_reviewer
        require(current_reviewer(root)==reviewer,'Unauthorized local reviewer')
        return publish_package(root,rid,p,decision,reviewer)

def publish_package(root,rid,p,decision,reviewer):
    """Shared publication body: preview, project the change, validate, build, commit, push, verify.

    Called after either a human approval (apply_publish) or a recorded policy approval
    (publication_policy.auto_apply). The approval event must already exist and match.
    """
    require(decision and decision['status']=='approved' and decision['proposal_hash']==digest(p),'Recorded approval required')
    if True:
        import research
        require(root.resolve()==research.ROOT.resolve(),'Repository mismatch')
        require(not (root/'.local/research-session.lock').exists(),'Research session active; retry after it finishes')
        with research.lock():
            receipt_path=queue(root)/(rid+'-publication.json')
            receipt=read(receipt_path) if receipt_path.exists() else {}
            config=read(root/'research/runtime.json')
            require(not git(root,'status','--porcelain'),'Working tree must be clean')
            require(git(root,'branch','--show-current')==config['branch'],'Wrong branch')
            require(git(root,'remote','get-url','origin').removesuffix('.git')=='https://github.com/'+config['repository'],'Wrong remote')
            git(root,'fetch','origin',config['branch'])
            head=git(root,'rev-parse','HEAD');remote=git(root,'rev-parse','origin/'+config['branch'])
            if receipt.get('commit'):
                require(head==receipt['commit'],'Repository changed after publication attempt')
            else:
                require(head==remote,'Repository needs synchronization');check_base(root,p);check_evidence(root,p)
                result=preview(root,rid);require(result['passed'],'Preview validation failed')
                changes=projected(p,base(root))
                # Public review freshness comes from the human decision, not
                # from when a researcher first drafted the proposal.
                for name in ['delivery','ecosystem','expansion']:
                    path=f'research/{name}.json'
                    if changes[path]!=read(root/path):
                        changes[path]['reviewed_at']=decision['at']
                        changes[f'site/data/{name}.json']=copy.deepcopy(changes[path])
                for name,v in changes.items():
                    if read(root/name)!=v:save(root/name,v)
                for command in [[sys.executable,'scripts/validate.py'],[sys.executable,'scripts/build.py']]:
                    subprocess.run(command,cwd=root,check=True,capture_output=True,timeout=120)
                changed=git(root,'diff','--name-only').splitlines()+git(root,'ls-files','--others','--exclude-standard').splitlines()
                require(changed and all(x in changes or x.startswith('docs/') for x in changed),'Unexpected catalog build changes')
                git(root,'add','--',*changed);git(root,'commit','-m','catalog: apply '+rid)
                receipt={'commit':git(root,'rev-parse','HEAD'),'proposal_hash':digest(p),'status':'committed','at':now()};save(receipt_path,receipt)
            try:
                git(root,'push','origin','HEAD:'+config['branch'])
                receipt['status']='pushed';save(receipt_path,receipt)
                # Verify the actual data, not merely successful git transport.
                url='https://'+config['repository'].split('/')[0]+'.github.io/'+config['repository'].split('/')[1]+'/data/'
                expected={Path(n).name:read(root/n) for n in ['site/data/ledger.json','site/data/delivery.json','site/data/ecosystem.json','site/data/expansion.json','site/data/source-books.json']}
                for attempt in range(18):
                    try:
                        matches=all(json.load(urlopen(url+name+'?revision='+receipt['commit'],timeout=10))==v for name,v in expected.items())
                        if matches:break
                    except (OSError,ValueError):matches=False
                    time.sleep(5)
                receipt['status']='deployed' if matches else 'deployment_pending';save(receipt_path,receipt)
                if matches:
                    append_event(root,dict(id=rid,kind='catalog_change',status='applied',reviewer=reviewer,at=now(),proposal_hash=digest(p),commit=receipt['commit']))
                    save(queue(root)/(rid+'-followup.json'),{'kind':'catalog_followup','package':rid,'status':'pending_evidence','created_at':now(),'questions':[{'target':c['target'],'id':c['id'],'next_evidence':c['after'].get('next_evidence') or c['after'].get('gap') or 'Check the next dated primary disclosure for changed facts.'} for c in p['changes'] if c['target'] in {'project','company','product'}]})
                return receipt
            except Exception:
                receipt['status']='publication_failed';save(receipt_path,receipt);raise
