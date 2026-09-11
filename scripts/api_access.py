"""Registered statistical APIs used under their own terms (constitution, owner decision 2026-09-09).

Only hosts and path prefixes listed in research/api-access.json qualify; only reviewed importers
call this module; the model's collection lane never does. Keys live in .local/api-keys.json and
are never written into the repository, a prompt, a receipt or a log line.

fetch() redacts every registered key out of a response body before it returns, and never carries
one across a redirect, so an importer that retains the wire response cannot retain a key with it.
"""
import json
import sys
import time
from pathlib import Path
from urllib.parse import urlparse, urlencode, parse_qsl, urlunparse
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler

sys.path.insert(0,str(Path(__file__).resolve().parent))
from validate import require, text, timestamp

ROOT=Path(__file__).resolve().parents[1]
MAX_BYTES=60_000_000
REDACTED=b'[redacted]'
_last={}


def policy(root=ROOT):
    p=json.loads((root/'research/api-access.json').read_text(encoding='utf-8'))
    require(set(p)=={'version','reviewed_at','owner_decision','hosts','importers_only','never_in_prompts'} and p['version']==1,'Unexpected api-access shape')
    timestamp(p['reviewed_at']);text(p['owner_decision'],1200)
    require(p['importers_only'] is True and p['never_in_prompts'] is True,'API access must stay importer-only and out of prompts')
    for host,h in p['hosts'].items():
        require(isinstance(h.get('paths'),list) and h['paths'] and all(x.startswith('/') and '..' not in x for x in h['paths']),f'{host}: documented API paths required')
        text(h['publisher'],200);text(h['terms'],500);text(h['limits'],300)
        if 'user_agent' in h:text(h['user_agent'],120)   # a publisher that prescribes its own agent format (SEC refuses the project's Bot/1.0 string)
    return p


def allowed(url,p=None):
    """The host and path are listed: the publisher's API terms govern instead of robots.txt."""
    p=p or policy();u=urlparse(url)
    if u.scheme!='https' or u.username or u.password or u.port not in (None,443):return None
    h=p['hosts'].get(u.hostname)
    if not h or not any(u.path.startswith(x) for x in h['paths']):return None
    return h


def vault(root=ROOT):
    f=root/'.local/api-keys.json'
    return json.loads(f.read_text(encoding='utf-8')) if f.exists() else {}


def key(name,root=ROOT):
    if not name:return None
    return vault(root).get(name) or None


def redact(body,root=ROOT):
    """Strip every registered key out of a wire response before any caller can retain it.

    EIA v2 echoes the whole request URL, api_key included, in response.request.params, and the
    EIA importers keep the wire response as their snapshot: 159 retained files under .local/
    (10.7 MB) held the live key on 2026-09-11. Redacting here rather than at each writer means a
    new importer cannot reintroduce it. The 16-char floor keeps a short or placeholder vault
    value from blanking unrelated bytes."""
    for v in vault(root).values():
        if isinstance(v,str) and len(v)>=16:body=body.replace(v.encode('utf-8'),REDACTED)
    return body


class _Redirect(HTTPRedirectHandler):
    """Revalidate the listed host and path on every hop, and drop the key when the host changes.

    urllib follows a Location wherever it points and replays whatever query string it carries, so
    one redirect off api.eia.gov would have handed the owner's key to the redirect target."""
    def __init__(self,p,key_param):self.p=p;self.key_param=key_param

    def redirect_request(self,req,fp,code,msg,headers,newurl):
        u=urlparse(newurl)
        if self.key_param and u.hostname!=urlparse(req.full_url).hostname:
            newurl=urlunparse(u._replace(query=urlencode([(a,b) for a,b in parse_qsl(u.query,keep_blank_values=True) if a!=self.key_param])))
        require(allowed(newurl,self.p) is not None,'API redirect leaves the listed API surface')
        return super().redirect_request(req,fp,code,msg,headers,newurl)


def fetch(url,agent,p=None,root=ROOT,timeout=60):
    """GET a listed API path with the project agent string and the owner's key when the API takes one."""
    p=p or policy(root)
    h=allowed(url,p);require(h is not None,'URL is not a listed statistical API path')
    k=key(h.get('key_name'),root)
    if h.get('key_param') and k:
        u=urlparse(url)
        # parse_qsl keeps repeated names (EIA takes facets[x][]= more than once); dict() dropped all but the last.
        q=[(a,b) for a,b in parse_qsl(u.query,keep_blank_values=True) if a!=h['key_param']]+[(h['key_param'],k)]
        url=urlunparse(u._replace(query=urlencode(q)))
    host=urlparse(url).hostname;wait=1-(time.monotonic()-_last.get(host,0))
    if wait>0:time.sleep(wait)
    _last[host]=time.monotonic()
    opener=build_opener(ProxyHandler({}),_Redirect(p,h.get('key_param')))
    with opener.open(Request(url,headers={'User-Agent':h.get('user_agent') or agent}),timeout=timeout) as response:
        body=response.read(MAX_BYTES+1)
    require(len(body)<=MAX_BYTES,'API response exceeds size cap')
    return redact(body,root)
