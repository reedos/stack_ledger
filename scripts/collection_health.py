"""Private cross-batch collection cooldowns. Never grants source access."""
import hashlib
import json
import time
from email.utils import parsedate_to_datetime
from urllib.error import HTTPError
from atomic_json import save


def error_details(error):
    cause=error
    while cause.__cause__ is not None:cause=cause.__cause__
    result={'type':type(error).__name__}
    if isinstance(cause,HTTPError):
        result['http_status']=cause.code
        value=cause.headers.get('Retry-After','') if cause.headers else ''
        try:delay=float(value) if value.isdigit() else parsedate_to_datetime(value).timestamp()-time.time()
        except (ValueError,TypeError,OverflowError):delay=0
        if delay>0:result['retry_after_seconds']=delay
        cause.close()
    return result


class CoolingDown(ValueError):
    """A skipped request, not a new source failure."""


class QueryRejected(ValueError):
    """A rejected topic must not take healthy provider access offline."""


class Health:
    def __init__(self,path):
        self.path=path
        self.records=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}

    def key(self,kind,target):return kind+':'+hashlib.sha256(target.encode()).hexdigest()
    def get(self,kind,target):return self.records.get(self.key(kind,target),{})
    def due(self,kind,target):return self.get(kind,target).get('next_attempt',0)<=time.time()
    def put(self,kind,target,value):
        self.records[self.key(kind,target)]=value;save(self.path,self.records)
    def success(self,kind,target,seconds,**fields):
        self.put(kind,target,dict(status='available',failures=0,next_attempt=time.time()+seconds,**fields))
    def failure(self,kind,target,error,minimum=900):
        previous=self.get(kind,target);failures=previous.get('failures',0)+1
        detail=error_details(error)
        # A host that refuses the crawler (401/403/406/451 or a robots block) will not change by the next
        # batch: back off up to three days instead of six hours, so blocked reference pages stop filling
        # every batch's due list (90 such failures in one session on 2026-09-09).
        refused=detail.get('http_status') in (401,403,406,451) or 'robots' in str(error).lower()
        if refused:detail['refused']=True
        ceiling=259200 if refused else 21600
        seconds=max(minimum,min(ceiling,900*2**min(failures-1,8 if refused else 5)),detail.get('retry_after_seconds',0))
        self.put(kind,target,dict(status='unavailable',failures=failures,next_attempt=time.time()+seconds,**detail))
