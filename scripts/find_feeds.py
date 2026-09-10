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

# Deliverable 4: independent news outlets, probed and registered as rank-4 claim_type: news
# sources with excerpts: true (grade C -- see source_policy.grade_for). Layers reflect each
# outlet's actual beat, not a blanket subscription to every topic. host is the outlet's own
# publishing domain; probing decides whether a public feed actually exists there today --
# nothing here is registered until it answers 200 with a valid, same-host feed.
NEWS_OUTLETS={
    'www.datacenterdynamics.com':('Data Center Dynamics',['energy','chips','infrastructure']),
    'www.utilitydive.com':('Utility Dive',['energy']),
    'www.canarymedia.com':('Canary Media',['energy']),
    'semiengineering.com':('Semiconductor Engineering',['chips']),
    'www.eetimes.com':('EE Times',['chips']),
    'www.theregister.com':('The Register',['chips','infrastructure','models','applications']),
    'techcrunch.com':('TechCrunch',['infrastructure','models','applications']),
    'arstechnica.com':('Ars Technica',['chips','infrastructure','models','applications']),
    'www.reuters.com':('Reuters',['energy','chips','infrastructure','models','applications']),
    'apnews.com':('AP News',['chips','infrastructure','models','applications']),
}


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
        registry['region_books'][policy['region_book']]['sources'].append(sid)
        existing.add(r['feed_url']);added.append(sid)
    validate_registry(registry,set(companies))
    from validate import validate
    # validate() reads the reviewed registry from disk: write it (and its public mirror) first,
    # then validate the ledger against it, restoring the originals if anything fails.
    paths=[ROOT/'research/sources.json',ROOT/'site/data/source-books.json']
    originals={p:p.read_bytes() for p in paths}
    save(paths[0],registry);save(paths[1],{k:registry[k] for k in ['region_books','collection']})
    try:validate(ledger)
    except Exception:
        for p,b in originals.items():p.write_bytes(b)
        raise
    save(ROOT/'site/data/ledger.json',ledger)
    return added


def probe_host(fetcher,host,publisher,log,existing_urls):
    """Autodiscover + validate every feed candidate on one host; not tied to a directory company."""
    rows=[]
    for url in discover(fetcher,host,log)[:5]:
        if url in existing_urls:continue
        record={'publisher':publisher,'host':host,'feed_url':url,'checked_at':now()}
        try:
            record.update(validate_feed(fetcher,url))
            feed_host=urlparse(url).hostname
            record['eligible']=bool(record['entries']>=1 and record['same_host_links']>=1 and record['same_host_links']*2>=record['links'] and feed_host==host and record['top_prefix'])
            record['status']='eligible' if record['eligible'] else 'ineligible'
        except CollectionGap as e:record.update(status='unsupported_format',detail=e.kind,eligible=False)
        except HTTPError as e:record.update(status='http_error',detail=e.code,eligible=False)
        except (URLError,TimeoutError) as e:record.update(status='network_error',detail=type(e).__name__,eligible=False)
        except Exception as e:record.update(status='error',detail=type(e).__name__,eligible=False)
        rows.append(record)
        print(f"{record['status']:19s} {publisher[:28]:28s} {url}",flush=True)
    if not rows:
        rows.append({'publisher':publisher,'host':host,'feed_url':None,'status':'no_candidate_feed','eligible':False})
        print(f"{'no_candidate_feed':19s} {publisher[:28]:28s} {host}",flush=True)
    return rows


def run_outlets(outlets=None,out=None):
    """Deliverable 4: probe named independent news-outlet hosts for a public feed. Registration
    is separate (register_outlets) and only ever acts on rows this probe marks eligible."""
    outlets=outlets or NEWS_OUTLETS
    registry=load(ROOT/'research/sources.json')
    fetcher=Fetcher();results=[];log=[]
    existing_urls={s['url'] for s in registry['sources']}
    target=out or research.LOCAL/'feed-candidates-outlets.json'
    def checkpoint():
        save(target,{'generated_at':now(),'complete':False,'errors':log,'candidates':results})
    for host,(publisher,layers) in outlets.items():
        checkpoint()
        for record in probe_host(fetcher,host,publisher,log,existing_urls):
            results.append(dict(record,layers=layers))
    payload={'generated_at':now(),'complete':True,'errors':log,'candidates':results,
             'note':'Eligible means the feed parsed, its entries link to the same host, and a path prefix exists for discovery. Registration is a reviewed change.'}
    save(target,payload)
    return payload


def register_outlets(payload):
    """Add eligible independent-news-outlet feeds as rank-4 claim_type: news, excerpts: true
    sources (deliverable 4) -- grade C, never a company's own channel (source_policy.grade_for).
    """
    registry=load(ROOT/'research/sources.json');ledger=load(ROOT/'site/data/ledger.json')
    existing={s['url'] for s in registry['sources']};added=[]
    hosts_done={urlparse(s['url']).hostname for s in registry['sources'] if s.get('index')}
    for r in payload['candidates']:
        if not r.get('eligible') or r['feed_url'] in existing or r['host'] in hosts_done:continue  # one feed per host
        sid='outlet-'+re.sub(r'[^a-z0-9]+','-',r['host'].lower()).strip('-')+'-'+digest(r['feed_url'])[:6]
        source={'id':sid,'publisher':r['publisher'],'title':f"{r['publisher']} feed · {r['host']}",'url':r['feed_url'],'published':None,'layers':r['layers'],'license':'Original source rights apply','index':True}
        policy={'rank':4,'region_book':'global','company_id':None,'claim_type':'news','cadence':'daily','weekday':0,'path_prefixes':[r['top_prefix']],'topics':TOPICS,'excerpts':True}
        hosts_done.add(r['host'])
        registry['sources'].append(source);registry['collection'][sid]=policy;ledger['sources'].append(dict(source))
        registry['region_books']['global']['sources'].append(sid)
        existing.add(r['feed_url']);added.append(sid)
    validate_registry(registry,{s.get('company_id') for s in registry['collection'].values() if s.get('company_id')})
    from validate import validate
    paths=[ROOT/'research/sources.json',ROOT/'site/data/source-books.json']
    originals={p:p.read_bytes() for p in paths}
    save(paths[0],registry);save(paths[1],{k:registry[k] for k in ['region_books','collection']})
    try:validate(ledger)
    except Exception:
        for p,b in originals.items():p.write_bytes(b)
        raise
    save(ROOT/'site/data/ledger.json',ledger)
    return added


def social_accounts(root=ROOT):
    """research/social-accounts.json: a reviewed, human-verified list of company Bluesky
    handles. Deliverable 4 explicitly forbids guessing handles; an empty accounts list (with
    the file's own instructions) is the honest default until a maintainer verifies one."""
    path=root/'research/social-accounts.json'
    return load(path) if path.exists() else {'version':1,'accounts':[]}


def run_social(accounts=None,out=None):
    """Probe research/social-accounts.json's reviewed handles for a working Bluesky RSS feed."""
    accounts=social_accounts()['accounts'] if accounts is None else accounts
    registry=load(ROOT/'research/sources.json');ecosystem={c['id']:c for c in load(ROOT/'research/ecosystem.json')['companies']}
    fetcher=Fetcher();results=[];log=[]
    existing_urls={s['url'] for s in registry['sources']}
    target=out or research.LOCAL/'feed-candidates-social.json'
    def checkpoint():
        save(target,{'generated_at':now(),'complete':False,'errors':log,'candidates':results})
    for account in accounts:
        company=ecosystem.get(account['company_id'])
        if company is None:
            results.append({'company_id':account['company_id'],'handle':account['handle'],'status':'unknown_company','eligible':False});continue
        checkpoint()
        url=f"https://bsky.app/profile/{account['handle']}/rss"
        record={'company_id':company['id'],'company':company['name'],'layers':company['layers'],'region_book':company.get('region_book','unknown'),'handle':account['handle'],'host':'bsky.app','feed_url':url,'checked_at':now()}
        if url in existing_urls:
            record.update(status='already_registered',eligible=False)
        else:
            try:
                record.update(validate_feed(fetcher,url))
                # A Bluesky RSS bridge's entry links point at bsky.app/profile/<handle>/post/<id>,
                # not the company's own domain -- the same-host check company feeds use does not
                # apply here, only that the feed parsed and actually carries entries.
                record['eligible']=bool(record['entries']>=1)
                record['status']='eligible' if record['eligible'] else 'ineligible'
            except CollectionGap as e:record.update(status='unsupported_format',detail=e.kind,eligible=False)
            except HTTPError as e:record.update(status='http_error',detail=e.code,eligible=False)
            except (URLError,TimeoutError) as e:record.update(status='network_error',detail=type(e).__name__,eligible=False)
            except Exception as e:record.update(status='error',detail=type(e).__name__,eligible=False)
        results.append(record)
        print(f"{record['status']:19s} {company['name'][:28]:28s} {url}",flush=True)
    payload={'generated_at':now(),'complete':True,'errors':log,'candidates':results,
             'note':'Eligible means the Bluesky RSS bridge parsed and carried at least one entry. Registration is a reviewed change.'}
    save(target,payload)
    return payload


def register_social(payload):
    """Add eligible official Bluesky feeds as rank-6 sources (source_policy.grade_for: B, the
    same company-statement grade as any other official channel -- deliverable 1's 'official
    account'). rank 6 is session_options.SOURCE_KINDS' own 'Official social accounts' category.
    """
    registry=load(ROOT/'research/sources.json');ledger=load(ROOT/'site/data/ledger.json')
    ecosystem={c['id']:c for c in load(ROOT/'research/ecosystem.json')['companies']}
    existing={s['url'] for s in registry['sources']};added=[]
    for r in payload['candidates']:
        if not r.get('eligible') or r['feed_url'] in existing:continue
        c=ecosystem[r['company_id']]
        sid='social-'+re.sub(r'[^a-z0-9]+','-',c['id'].lower()).strip('-')+'-'+digest(r['feed_url'])[:6]
        source={'id':sid,'publisher':c['name'],'title':f"{c['name']} official Bluesky · @{r['handle']}",'url':r['feed_url'],'published':None,'layers':c['layers'],'license':'Original source rights apply','index':True}
        policy={'rank':6,'region_book':c.get('region_book','unknown') if c.get('region_book') in registry['region_books'] else 'unknown','company_id':c['id'],'claim_type':'other','cadence':'daily','weekday':0,'path_prefixes':['/profile/'],'topics':TOPICS,'excerpts':False}
        registry['sources'].append(source);registry['collection'][sid]=policy;ledger['sources'].append(dict(source))
        registry['region_books'][policy['region_book']]['sources'].append(sid)
        existing.add(r['feed_url']);added.append(sid)
    validate_registry(registry,set(ecosystem))
    from validate import validate
    paths=[ROOT/'research/sources.json',ROOT/'site/data/source-books.json']
    originals={p:p.read_bytes() for p in paths}
    save(paths[0],registry);save(paths[1],{k:registry[k] for k in ['region_books','collection']})
    try:validate(ledger)
    except Exception:
        for p,b in originals.items():p.write_bytes(b)
        raise
    save(ROOT/'site/data/ledger.json',ledger)
    return added


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('--limit',type=int,default=None);p.add_argument('--register',action='store_true')
    p.add_argument('--from-file',type=Path,default=None,help='Register from an existing candidates file instead of probing')
    p.add_argument('--outlets',action='store_true',help='Deliverable 4: probe the named independent news outlets instead of directory companies')
    p.add_argument('--social',action='store_true',help='Deliverable 4: probe research/social-accounts.json\'s reviewed Bluesky handles instead of directory companies')
    a=p.parse_args(argv)
    research.LOCAL.mkdir(exist_ok=True)
    if a.outlets:
        payload=load(a.from_file) if a.from_file else run_outlets()
        register_fn=register_outlets
    elif a.social:
        payload=load(a.from_file) if a.from_file else run_social()
        register_fn=register_social
    else:
        payload=load(a.from_file) if a.from_file else run(a.limit)
        register_fn=register
    eligible=[r for r in payload['candidates'] if r.get('eligible')]
    print(f"\n{len(payload['candidates'])} candidate feeds; {len(eligible)} eligible; {len(payload.get('errors',[]))} host errors",flush=True)
    if a.register:
        added=register_fn(payload)
        print(f'Registered {len(added)} feeds: '+', '.join(added),flush=True)
        from build import build
        build()
    return 0


if __name__=='__main__':sys.exit(main())
