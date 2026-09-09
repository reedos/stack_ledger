"""Registered statistical APIs used under their own terms (constitution, owner decision 2026-09-09).

Only hosts and path prefixes listed in research/api-access.json qualify; only reviewed importers
call this module; the model's collection lane never does. Keys live in .local/api-keys.json and
are never written into the repository, a prompt, a receipt or a log line.
"""
import json
import sys
import time
from pathlib import Path
from urllib.parse import urlparse, urlencode, parse_qsl, urlunparse
from urllib.request import Request, build_opener, ProxyHandler

sys.path.insert(0,str(Path(__file__).resolve().parent))
from validate import require, text, timestamp

ROOT=Path(__file__).resolve().parents[1]
MAX_BYTES=60_000_000
_last={}


def policy(root=ROOT):
    p=json.loads((root/'research/api-access.json').read_text(encoding='utf-8'))
    require(set(p)=={'version','reviewed_at','owner_decision','hosts','importers_only','never_in_prompts'} and p['version']==1,'Unexpected api-access shape')
    timestamp(p['reviewed_at']);text(p['owner_decision'],1200)
    require(p['importers_only'] is True and p['never_in_prompts'] is True,'API access must stay importer-only and out of prompts')
    for host,h in p['hosts'].items():
        require(isinstance(h.get('paths'),list) and h['paths'] and all(x.startswith('/') and '..' not in x for x in h['paths']),f'{host}: documented API paths required')
        text(h['publisher'],200);text(h['terms'],500);text(h['limits'],300)
    return p


def allowed(url,p=None):
    """The host and path are listed: the publisher's API terms govern instead of robots.txt."""
    p=p or policy();u=urlparse(url)
    if u.scheme!='https' or u.username or u.password or u.port not in (None,443):return None
    h=p['hosts'].get(u.hostname)
    if not h or not any(u.path.startswith(x) for x in h['paths']):return None
    return h


def key(name,root=ROOT):
    if not name:return None
    f=root/'.local/api-keys.json'
    if not f.exists():return None
    return json.loads(f.read_text(encoding='utf-8')).get(name) or None


def fetch(url,agent,p=None,root=ROOT,timeout=60):
    """GET a listed API path with the project agent string and the owner's key when the API takes one."""
    h=allowed(url,p);require(h is not None,'URL is not a listed statistical API path')
    k=key(h.get('key_name'),root)
    if h.get('key_param') and k:
        u=urlparse(url);q=dict(parse_qsl(u.query));q[h['key_param']]=k;url=urlunparse(u._replace(query=urlencode(q)))
    host=urlparse(url).hostname;wait=1-(time.monotonic()-_last.get(host,0))
    if wait>0:time.sleep(wait)
    _last[host]=time.monotonic()
    with build_opener(ProxyHandler({})).open(Request(url,headers={'User-Agent':agent}),timeout=timeout) as response:
        body=response.read(MAX_BYTES+1)
    require(len(body)<=MAX_BYTES,'API response exceeds size cap')
    return body
