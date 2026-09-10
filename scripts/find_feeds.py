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
from validate import timestamp, text, LAYERS

ROOT=Path(__file__).resolve().parents[1]
FEED_TYPES={'application/rss+xml','application/atom+xml','application/xml','text/xml'}
WELL_KNOWN=['/feed','/rss','/rss.xml','/feed.xml','/atom.xml','/news/rss','/news/rss.xml','/newsroom/rss.xml','/press-releases/rss','/blog/feed','/blog/rss.xml','/rss/news-releases.xml','/rss/pressrelease.aspx','/rss/news-releases']
# Reviewed on-thesis words for a news outlet's article slugs. Matched whole-word by
# source_policy.topical, so 'ai' no longer matches 'aim' or 'chain' (measured 2026-09-10:
# a Snapchat feature story passed the old substring filter and cost a model call).
TOPICS=["ai", "artificial-intelligence", "data-center", "data-centre", "datacenter", "datacentre", "semiconductor", "semiconductors", "chip", "chips", "wafer", "fab", "foundry", "gpu", "gpus", "accelerator", "accelerators", "hbm", "packaging", "nuclear", "grid", "power", "energy", "electricity", "utility", "utilities", "interconnection", "transmission", "substation", "turbine", "solar", "geothermal", "battery", "storage", "cooling", "megawatt", "megawatts", "gigawatt", "capacity", "compute", "inference", "training", "model", "models", "cluster", "supercomputer", "fusion", "ppa", "capex", "hyperscaler", "hyperscale"]

# Deliverable 4 (owner decision, September 10, 2026): independent news outlets, probed and
# registered as rank-4 claim_type: news sources with excerpts: true (grade C -- see
# source_policy.grade_for). The candidate list itself is a reviewed file, never a hard-coded
# table -- see load_outlets below. Nothing is registered until a candidate's own feed URL
# answers with a genuine, parseable, same-host feed and robots allows it.
OUTLET_ENTRY_REQUIRED={'name','home','layers'}
OUTLET_ENTRY_OPTIONAL=OUTLET_ENTRY_REQUIRED|{'status','reason','source_id','checked_at'}


def validate_outlets_file(data):
    """Shape of the reviewed research/news-outlets.json candidate file (deliverable 1/4): a
    human-reviewed list of outlet name/home/layers, each optionally carrying back a prior
    probe's outcome (status/reason/source_id/checked_at) so a later run can see what already
    answered. No feed URL lives here -- only the probe's own eligibility check ever proposes
    one, in research/sources.json, never this file."""
    require(isinstance(data,dict) and set(data)>={'version','reviewed_at','outlets'} and set(data)<={'version','reviewed_at','outlets','instructions'} and data['version']==1,'Invalid outlet candidate file')
    timestamp(data['reviewed_at'])
    seen=set()
    for o in data['outlets']:
        require(isinstance(o,dict) and OUTLET_ENTRY_REQUIRED<=o.keys()<=OUTLET_ENTRY_OPTIONAL,'Invalid outlet entry')
        text(o['name'],250)
        u=urlparse(o['home'])
        require(u.scheme=='https' and u.hostname and not u.username and not u.password and u.port in (None,443),'Outlet home must be public HTTPS')
        require(u.hostname not in seen,'Duplicate outlet host');seen.add(u.hostname)
        require(bool(o['layers']) and set(o['layers'])<=set(LAYERS),'Outlet needs reviewed layers')
        if 'status' in o:
            require(o['status'] in {'registered','rejected'},'Invalid outlet status')
            require(('source_id' in o)==(o['status']=='registered'),'Registered outlet needs a source_id, rejected needs none')
            require(('reason' in o)==(o['status']=='rejected'),'Rejected outlet needs a reason, registered needs none')
            if 'reason' in o:text(o['reason'],500)
            if 'source_id' in o:text(o['source_id'],140)
        if 'checked_at' in o:timestamp(o['checked_at'])
    return True


def load_outlets(path=None):
    """The reviewed candidate list deliverable 1/4 probes and registers from. path defaults to
    ROOT/'research/news-outlets.json' read at call time (never OUTLETS_PATH's def-time value),
    so a caller that patches find_feeds.ROOT for an isolated tempdir is honored."""
    data=load(path or ROOT/'research/news-outlets.json')
    validate_outlets_file(data)
    return data


class FeedLinks(HTMLParser):
    def __init__(self):super().__init__();self.feeds=[];self.anchors=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='link' and (a.get('rel') or '').lower().find('alternate')>=0 and (a.get('type') or '').lower() in FEED_TYPES and a.get('href'):self.feeds.append(a['href'])
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
        try:
            page=probe(fetcher,host,root_url)
        except HTTPError as e:
            # Deliverable 2: a single 4xx does not blackball an outlet -- one retry before it counts.
            if not (400<=e.code<500):raise
            page=probe(fetcher,host,root_url)
        p=FeedLinks();p.feed(page)
        for href in p.feeds+p.anchors:
            u=urljoin(root_url,href)
            if urlparse(u).scheme=='https':candidates.append(u)
    except Exception as e:
        # An unresponsive or blocking host gets no well-known-path probing: each miss costs a
        # timeout. detail carries the HTTP code when there is one, or a short message for any
        # other ValueError (the safety checks in research.get/allowed_url -- an oversized
        # homepage, an off-host redirect), so a caller reporting why can say something more
        # useful than the bare exception type.
        detail=e.code if isinstance(e,HTTPError) else (str(e)[:150] if isinstance(e,ValueError) else None)
        log.append({'host':host,'stage':'root','error':type(e).__name__,'detail':detail})
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


def root_robots_decision(fetcher,host):
    """allowed/disallowed/unavailable for a host's own root, purely for reporting -- reuses
    Fetcher's per-host robots cache, so this never costs a second robots.txt fetch once
    discover()/validate_feed() have already resolved it for the same host."""
    try:
        fetcher.check_robots(f'https://{host}/')
        return 'allowed'
    except Exception as e:
        return 'disallowed' if str(e).startswith('Blocked by robots') else 'unavailable'


def probe_feed(fetcher,url,host):
    """Validate one candidate feed URL, reporting HTTP status, robots decision and entries
    parsed alongside the eligibility verdict (deliverable 1). Deliverable 2: an outlet that
    answers 4xx is retried once before being rejected for it -- a single bad response is not
    a verdict on a live outlet."""
    def attempt():
        record=validate_feed(fetcher,url)
        feed_host=urlparse(url).hostname
        record['eligible']=bool(record['entries']>=1 and record['same_host_links']>=1 and record['same_host_links']*2>=record['links'] and feed_host==host and record['top_prefix'])
        record.update(status='eligible' if record['eligible'] else 'ineligible',http_status=200,robots='allowed')
        return record
    try:
        return attempt()
    except CollectionGap as e:
        return dict(status='unsupported_format',detail=e.kind,eligible=False,http_status=200,robots='allowed',entries=0)
    except HTTPError as e:
        if 400<=e.code<500:
            try:return attempt()  # deliverable 2: reject a 4xx outlet only once it answers twice
            except HTTPError as e2:return dict(status='http_error',detail=e2.code,eligible=False,http_status=e2.code,robots='allowed',entries=0)
            except Exception:pass  # falls through to the generic classification below
        return dict(status='http_error',detail=e.code,eligible=False,http_status=e.code,robots='allowed',entries=0)
    except (URLError,TimeoutError) as e:
        return dict(status='network_error',detail=type(e).__name__,eligible=False,http_status=None,robots=None,entries=0)
    except ValueError as e:
        blocked=str(e).startswith('Blocked by robots')
        return dict(status='robots_blocked' if blocked else 'error',detail=str(e)[:200],eligible=False,http_status=None,robots='disallowed' if blocked else 'unavailable',entries=0)
    except Exception as e:
        return dict(status='error',detail=type(e).__name__,eligible=False,http_status=None,robots=None,entries=0)


def probe_host(fetcher,host,publisher,log,existing_urls):
    """Autodiscover + validate every feed candidate on one host; not tied to a directory company."""
    rows=[]
    for url in discover(fetcher,host,log)[:5]:
        if url in existing_urls:continue
        record={'publisher':publisher,'host':host,'feed_url':url,'checked_at':now()}
        record.update(probe_feed(fetcher,url,host))
        rows.append(record)
        print(f"{record['status']:19s} {publisher[:28]:28s} {url}",flush=True)
    if not rows:
        # No autodiscovered/well-known-path candidate at all: report the host's own robots
        # decision and, when the homepage fetch itself failed, its HTTP status -- so a total
        # block reads distinctly from "this outlet simply has no feed".
        root_error=next((e for e in reversed(log) if e.get('host')==host and e.get('stage')=='root'),None)
        row={'publisher':publisher,'host':host,'feed_url':None,'eligible':False,'robots':root_robots_decision(fetcher,host),'http_status':None,'entries':None}
        detail=root_error.get('detail') if root_error else None
        if isinstance(detail,int):
            row.update(status='http_error',detail=detail,http_status=detail)
        elif root_error and root_error.get('error') in ('TimeoutError','socket.timeout'):
            row.update(status='network_error',detail=root_error['error'])
        elif detail:
            row.update(status='fetch_error',detail=detail)
        else:
            row['status']='no_candidate_feed'
        rows.append(row)
        print(f"{row['status']:19s} {publisher[:28]:28s} {host}",flush=True)
    return rows


def run_outlets(outlets=None,out=None):
    """Deliverable 1/4: probe the reviewed research/news-outlets.json candidate list (or an
    explicit override, mainly for tests) for a public feed. A host already carrying a
    registered index source is reported, not re-probed -- registration is idempotent per host
    (see register_outlets) and repeating the request costs nothing but the outlet's own
    server. Registration itself is separate (register_outlets) and only ever acts on rows
    this probe marks eligible."""
    candidates=outlets if outlets is not None else load_outlets()['outlets']
    registry=load(ROOT/'research/sources.json')
    fetcher=Fetcher();results=[];log=[]
    existing_urls={s['url'] for s in registry['sources']}
    hosts_registered={urlparse(s['url']).hostname for s in registry['sources'] if s.get('index')}
    target=out or research.LOCAL/'feed-candidates-outlets.json'
    def checkpoint():
        save(target,{'generated_at':now(),'complete':False,'errors':log,'candidates':results})
    for o in candidates:
        host=urlparse(o['home']).hostname;publisher=o['name'];layers=o['layers']
        checkpoint()
        if host in hosts_registered:
            results.append({'publisher':publisher,'host':host,'feed_url':None,'status':'already_registered','eligible':False,'layers':layers})
            print(f"{'already_registered':19s} {publisher[:28]:28s} {host}",flush=True)
            continue
        for record in probe_host(fetcher,host,publisher,log,existing_urls):
            results.append(dict(record,layers=layers))
    payload={'generated_at':now(),'complete':True,'errors':log,'candidates':results,
             'note':'Eligible means the feed parsed, its entries link to the same host, and a path prefix exists for discovery. Registration is a reviewed change.'}
    save(target,payload)
    return payload


# Deliverable 1: a human-readable reason for every way a probed candidate failed to earn a
# registration -- used both for the printed report and for the reviewed outlets file's
# recorded 'reason' (deliverable 4). Order-independent, deterministic: no model input.
_OUTLET_REJECTIONS={
    'no_candidate_feed':lambda r:'no feed link discovered on the homepage or well-known feed paths (fetched fine, nothing pointed to a feed)',
    'robots_blocked':lambda r:f"robots.txt disallows {r.get('feed_url') or 'this host'}",
    'http_error':lambda r:(f"feed answered HTTP {r.get('detail')} twice" if r.get('feed_url')
                            else f"the homepage answered HTTP {r.get('detail')} twice; never reached a candidate feed"),
    'unsupported_format':lambda r:f"feed content could not be read as RSS/Atom ({r.get('detail')})",
    'network_error':lambda r:(f"network error reaching the feed ({r.get('detail')})" if r.get('feed_url')
                               else f"network error reaching the homepage twice ({r.get('detail')}); never reached a candidate feed"),
    'ineligible':lambda r:'feed fetched but did not parse as a genuine, same-host article feed with a stable path',
    'error':lambda r:f"probe error ({r.get('detail')})",
    'fetch_error':lambda r:f"the homepage could not be safely fetched ({r.get('detail')})",
}


def outlet_rejection_reason(rows):
    """The most informative failure across every feed URL (or bare homepage probe) a host's
    probe tried. A row that actually reached a candidate feed explains more than a bare
    no_candidate_feed row, so it wins when both exist for the same host. Checked first: a
    disallowed or unreadable robots policy explains *why* nothing was found, so it outranks
    the generic "nothing found" story from the same row."""
    tried=[r for r in rows if r.get('feed_url')]
    row=tried[0] if tried else rows[0]
    if row.get('robots')=='disallowed':
        return f"robots.txt disallows crawling {row.get('feed_url') or row['host']}"
    if row.get('robots')=='unavailable' and row.get('status')=='no_candidate_feed':
        return "robots.txt could not be read as a usable policy (bot-protection challenge page, unreachable, or an off-host redirect); fails closed per RFC 9309"
    make=_OUTLET_REJECTIONS.get(row.get('status'))
    return make(row) if make else f"probe did not find an eligible feed ({row.get('status')})"


def record_outlet_outcomes(outcomes,root=None):
    """Deliverable 4: write each outlet's registered/rejected decision back into the reviewed
    research/news-outlets.json, keyed by host, so a later run sees what already answered
    instead of re-probing blindly. A no-op when there is no reviewed file to update -- e.g. a
    payload assembled directly in a test, never sourced from one.

    root defaults to the module's own ROOT read at call time (not def time), so callers that
    patch find_feeds.ROOT for an isolated tempdir (see tests/test_reports.py) are honored
    exactly like every other ROOT-relative path in this module -- never the real checkout."""
    path=(root or ROOT)/'research/news-outlets.json'
    if not outcomes or not path.exists():return
    data=load(path)
    at=now()
    for o in data.get('outlets',[]):
        host=urlparse(o['home']).hostname
        if host not in outcomes:continue
        status,detail=outcomes[host]
        o['checked_at']=at;o['status']=status
        o.pop('reason',None);o.pop('source_id',None)
        o.update(detail)
    save(path,data)


def register_outlets(payload):
    """Add eligible independent-news-outlet feeds as rank-4 claim_type: news, excerpts: true
    sources (deliverable 4) -- grade C, never a company's own channel (source_policy.grade_for).
    Also records every outcome, registered or rejected with its reason, back onto the reviewed
    research/news-outlets.json candidate file (deliverable 4) when one is present."""
    registry=load(ROOT/'research/sources.json');ledger=load(ROOT/'site/data/ledger.json')
    existing={s['url'] for s in registry['sources']};added=[]
    hosts_done={urlparse(s['url']).hostname for s in registry['sources'] if s.get('index')}
    by_host={}
    for r in payload['candidates']:
        by_host.setdefault(r['host'],[]).append(r)
    outcomes={}
    for host,rows in by_host.items():
        if host in hosts_done:
            sid=next((s['id'] for s in registry['sources'] if s.get('index') and urlparse(s['url']).hostname==host),None)
            if sid:outcomes[host]=('registered',{'source_id':sid})
            continue  # already registered (this run or an earlier one): never re-added, never re-rejected
        r=next((row for row in rows if row.get('eligible') and row['feed_url'] not in existing),None)
        if r is None:
            outcomes[host]=('rejected',{'reason':outlet_rejection_reason(rows)})
            continue
        sid='outlet-'+re.sub(r'[^a-z0-9]+','-',r['host'].lower()).strip('-')+'-'+digest(r['feed_url'])[:6]
        source={'id':sid,'publisher':r['publisher'],'title':f"{r['publisher']} feed · {r['host']}",'url':r['feed_url'],'published':None,'layers':r['layers'],'license':'Original source rights apply','index':True}
        policy={'rank':4,'region_book':'global','company_id':None,'claim_type':'news','cadence':'daily','weekday':0,'path_prefixes':[r['top_prefix']],'topics':TOPICS,'excerpts':True}
        hosts_done.add(r['host'])
        registry['sources'].append(source);registry['collection'][sid]=policy;ledger['sources'].append(dict(source))
        registry['region_books']['global']['sources'].append(sid)
        existing.add(r['feed_url']);added.append(sid)
        outcomes[host]=('registered',{'source_id':sid})
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
    record_outlet_outcomes(outcomes)
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
    p.add_argument('--outlets',action='store_true',help="Deliverable 1/4: probe research/news-outlets.json's reviewed independent-news-outlet candidates instead of directory companies")
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
