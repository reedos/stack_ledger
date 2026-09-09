"""Find and validate official RSS/Atom feeds for companies already in the directory.

Discovery is search-driven today and the search provider fails most of the time.
A newsroom or investor-relations feed on the company's own host is small, static,
bot-friendly and already parsed by document_formats. This script finds candidate
feeds (autodiscovery on pages the registry already trusts, then a few well-known
paths), validates that each parses with entries linking to the same host, and
writes a review file. --register adds the validated feeds as rank-4 daily index
sources with the standard discovery topics. Registry changes are reviewed changes:
the owner authorized additions on hosts already in the registry or on a directory
company's own domain, nothing else.

    python scripts/find_feeds.py                    # discover + validate, write .local/feed-candidates.json
    python scripts/find_feeds.py --register         # add validated feeds to sources.json and the ledger, then build
    python scripts/find_feeds.py --limit 10         # probe only the first N companies (smoke test)
"""
import argparse
import json
import re
import sys
import time
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse

sys.path.insert(0,str(Path(__file__).resolve().parent))
import research
from research import Fetcher, load, save, now, require, digest
from document_formats import as_html, CollectionGap, SUPPORTED
from source_policy import validate_registry

ROOT=Path(__file__).resolve().parents[1]
FEED_TYPES={'application/rss+xml','application/atom+xml','application/xml','text/xml'}
WELL_KNOWN=['/feed','/rss','/rss.xml','/feed.xml','/atom.xml','/news/rss','/news/rss.xml','/newsroom/rss.xml','/press-releases/rss','/blog/feed','/blog/rss.xml','/rss/news-releases.xml','/rss/pressrelease.aspx','/rss/news-releases']
TOPICS=['ai','artificial-intelligence','data-center','data-centre','nuclear','annual','report','inference','semiconductor','model','chip','compute','power','intelligence']


class FeedLinks(HTMLParser):
    def __init__(self):super().__init__();self.feeds=[];self.anchors=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='link' and (a.get('rel') or '').lower().find('alternate')>=0 and (a.get('type') or '').lower() in {'application/rss+xml','application/atom+xml'} and a.get('href'):self.feeds.append(a['href'])
        if tag=='a' and a.get('href') and re.search(r'(rss|atom|feed)(\.xml)?(/|$|\?)',a['href'].lower()):self.anchors.append(a['href'])


def company_hosts(registry,ecosystem):
    """Hosts the registry already trusts for each company, plus the company's own IR/blog hosts."""
    by_id={s['id']:s for s in registry['sources']}
    out={}
    for c in ecosystem['companies']:
        hosts=set()
        for sid,p in registry['collection'].items():
            if p.get('company_id')==c['id'] and sid in by_id:hosts.add(urlparse(by_id[sid]['url']).hostname)
        for u in [by_id.get(c.get('source'),{}).get('url'),c.get('ir_url'),*c.get('blog_urls',[])]:
            if u:hosts.add(urlparse(u).hostname)
        hosts={h for h in hosts if h and h not in {'github.com','huggingface.co','www.sec.gov','docs.openclaw.ai'}}
        out[c['id']]=sorted(hosts)
    return out


def probe(fetcher,host,url,raw=True):
    hostname=fetcher.check_robots(url)
    return fetcher.get(url,hostname,raw=raw)


def discover(fetcher,host,log):
    """Candidate feed URLs for one host: autodiscovery on the root page, then well-known paths."""
    candidates=[]
    root_url=f'https://{host}/'
    try:
        page=probe(fetcher,host,root_url)
        p=FeedLinks();p.feed(page)
        for href in p.feeds+p.anchors:
            u=urljoin(root_url,href)
            if urlparse(u).scheme=='https':candidates.append(u)
    except Exception as e:
        # An unresponsive or blocking host gets no well-known-path probing: each miss costs a timeout.
        log.append({'host':host,'stage':'root','error':type(e).__name__})
        return []
    if not candidates:
        for path in WELL_KNOWN[:4]:
            u=root_url.rstrip('/')+path
            try:
                body=probe(fetcher,host,u)
                if re.search(r'<(rss|feed)\b',body[:2000],re.I):candidates.append(u)
            except Exception:continue
    return list(dict.fromkeys(candidates))


def validate_feed(fetcher,url):
    """Fetch through the normal collection path and inspect entry links."""
    hostname=fetcher.check_robots(url)
    html=fetcher.get(url,hostname,raw=False)   # raises CollectionGap for unsupported content types
    parser=research.ReadableHTML();parser.feed(html)
    entries=html.count('<section>')
    links=[urljoin(url,l) for l in parser.links if l.startswith('http')]
    same=[l for l in links if urlparse(l).hostname==hostname]
    prefixes=Counter('/'+urlparse(l).path.strip('/').split('/')[0]+'/' for l in same if urlparse(l).path.strip('/'))
    return {'entries':entries,'links':len(links),'same_host_links':len(same),'top_prefix':prefixes.most_common(1)[0][0] if prefixes else None,'sample_links':same[:3]}


def run(limit=None,out=None):
    registry=load(ROOT/'research/sources.json');ecosystem=load(ROOT/'research/ecosystem.json')
    hosts=company_hosts(registry,ecosystem)
    fetcher=Fetcher();results=[];log=[];seen_hosts=set()
    companies=ecosystem['companies'][:limit] if limit else ecosystem['companies']
    existing_urls={s['url'] for s in registry['sources']}
    target=out or research.LOCAL/'feed-candidates.json'
    def checkpoint():
        save(target,{'generated_at':now(),'complete':False,'hosts_probed':len(seen_hosts),'errors':log,'candidates':results})
    for c in companies:
        for host in hosts.get(c['id'],[]):
            if host in seen_hosts:continue
            seen_hosts.add(host);checkpoint()
            for url in discover(fetcher,host,log)[:3]:
                if url in existing_urls:continue
                record={'company_id':c['id'],'company':c['name'],'layers':c['layers'],'region_book':c.get('region_book','unknown'),'host':host,'feed_url':url,'checked_at':now()}
                try:
                    record.update(validate_feed(fetcher,url))
                    feed_host=urlparse(url).hostname
                    record['eligible']=bool(record['entries']>=1 and record['same_host_links']>=1 and record['same_host_links']*2>=record['links'] and feed_host==host and record['top_prefix'])
                    record['status']='eligible' if record['eligible'] else 'ineligible'
                except CollectionGap as e:record.update(status='unsupported_format',detail=e.kind,eligible=False)
                except HTTPError as e:record.update(status='http_error',detail=e.code,eligible=False)
                except Exception as e:record.update(status='error',detail=type(e).__name__,eligible=False)
                results.append(record)
                print(f"{record['status']:19s} {c['name'][:28]:28s} {url}",flush=True)
    payload={'generated_at':now(),'complete':True,'hosts_probed':len(seen_hosts),'errors':log,'candidates':results,
             'note':'Eligible means the feed parsed, its entries link to the same host, and a path prefix exists for discovery. Registration is a reviewed change.'}
    save(target,payload)
    return payload


def register(payload):
    """Add eligible feeds as rank-4 daily index sources; mirror into the ledger; validate."""
    registry=load(ROOT/'research/sources.json');ledger=load(ROOT/'site/data/ledger.json')
    companies={c['id']:c for c in load(ROOT/'research/ecosystem.json')['companies']}
    existing={s['url'] for s in registry['sources']};added=[];hosts_done={urlparse(s['url']).hostname for s in registry['sources'] if s.get('index')}
    for r in payload['candidates']:
        if not r.get('eligible') or r['feed_url'] in existing or r['host'] in hosts_done:continue  # one feed per host
        if re.match(r'^(support|docs|status|help|community)\.',r['host']):continue   # help desks and manuals are not newsrooms
        c=companies[r['company_id']]
        # Engineering, research and product publishing is collected narrowly: rank 3, weekly.
        technical=bool(re.search(r'research|blog|developer|engineering|docs|resources',r['host']+urlparse(r['feed_url']).path+(r.get('top_prefix') or ''),re.I))
        sid='feed-'+re.sub(r'[^a-z0-9]+','-',c['id'].lower()).strip('-')+'-'+digest(r['feed_url'])[:6]
        source={'id':sid,'publisher':c['name'],'title':f"{c['name']} official feed · {r['host']}",'url':r['feed_url'],'published':None,'layers':c['layers'],'license':'Original source rights apply','index':True}
        policy={'rank':3 if technical else 4,'region_book':c.get('region_book','unknown') if c.get('region_book') in registry['region_books'] else 'unknown','company_id':c['id'],'claim_type':'other','cadence':'weekly' if technical else 'daily','weekday':hash(sid)%7 if technical else 0,'path_prefixes':[r['top_prefix']],'topics':TOPICS,'excerpts':False}
        hosts_done.add(r['host'])
        registry['sources'].append(source);registry['collection'][sid]=policy;ledger['sources'].append(dict(source))
        existing.add(r['feed_url']);added.append(sid)
    validate_registry(registry,set(companies))
    from validate import validate
    validate(ledger)
    save(ROOT/'research/sources.json',registry);save(ROOT/'site/data/ledger.json',ledger)
    return added


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('--limit',type=int,default=None);p.add_argument('--register',action='store_true')
    p.add_argument('--from-file',type=Path,default=None,help='Register from an existing candidates file instead of probing')
    a=p.parse_args(argv)
    research.LOCAL.mkdir(exist_ok=True)
    payload=load(a.from_file) if a.from_file else run(a.limit)
    eligible=[r for r in payload['candidates'] if r.get('eligible')]
    print(f"\n{len(payload['candidates'])} candidate feeds; {len(eligible)} eligible; {len(payload.get('errors',[]))} host errors",flush=True)
    if a.register:
        added=register(payload)
        print(f'Registered {len(added)} feeds: '+', '.join(added),flush=True)
        from build import build
        build()
    return 0


if __name__=='__main__':sys.exit(main())
