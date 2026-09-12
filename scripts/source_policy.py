"""Reviewed collection boundaries and append-only public evidence excerpts."""
import hashlib
import re
from urllib.parse import urlparse, unquote
from validate import require, text, timestamp, LAYERS, STATUSES

REGIONS = {'united-states','taiwan','korea','japan','china','europe','middle-east','india','canada-latam-africa-anz','global','unknown'}
CLAIMS = {'architecture','shipment','financial','roadmap','safety','clinical','labor','other','news'}
GRADES = {'A','B','C','D'}

def spread_weekday(source_id):
    """The night of the week a source is checked, spread evenly and stably by its id.

    `due()` treats a weekly source as due only on this weekday and defaults it to 0, so on
    2026-09-11 155 of 176 weekly sources came due on Monday and Friday, Saturday and Sunday nights
    had none at all. Every daily source sat at the default too, which would have piled them onto
    Monday the moment adaptive promotion made them weekly.

    sha256 rather than hash(): Python randomises string hashing per process, so the same source
    would otherwise land on a different night every time it was registered.
    """
    return int(hashlib.sha256(str(source_id).encode('utf-8')).hexdigest(), 16) % 7


def collection_for(registry, source):
    return registry.get('collection', {}).get(source.get('parent_source', source['id']), {})

# Owner decision, September 10, 2026: provenance is a REVIEWED property of each source, no longer
# derived from its collection rank. Rank is a crawl priority -- it schedules fetches, drives the
# discovery walk and gates unattended auto-apply -- and one integer could not also carry "who
# published this". Deriving from it put Epoch AI's own dataset at grade A and the page rendering a
# row of that same dataset at C, badged Stanford HAI "Official statistics or filings", badged FERC
# and two Federal Reserve banks "Company statement", and left grade D unreachable while three
# social sources read as company statements.
#
# The letter is a coarse solidity scale over the provenance; the site shows the provenance itself,
# so a reader sees "Independent research" rather than a letter standing in for it. The organising
# question is who is speaking, and about whom: A is the authoritative record, B a primary publisher
# speaking about its own work, C a third party characterising someone else's numbers, D unverified.
PROVENANCE_GRADE = {
    'official': 'A',              # statistical agency, regulator, court, central bank, IGO
    'regulated-filing': 'A',      # a company's own disclosure made under a regulatory regime
    'company-channel': 'B',       # a company speaking for itself outside regulation
    'independent-research': 'B',  # a research body publishing its own primary dataset or study
    'analyst': 'C',               # third-party consensus, trade or market analysis
    'news': 'C',                  # a news outlet reporting on someone else
    'social': 'D',                # a person, or an unverified account
}
PROVENANCE = set(PROVENANCE_GRADE)
# What the reader is shown. The letter alone was the thing that misled: "Grade C: News report"
# on an Epoch AI dataset page is false in a way "Independent research" is not.
PROVENANCE_LABEL = {
    'official': 'Official statistics or regulator',
    'regulated-filing': 'Regulated filing',
    'company-channel': 'Company statement',
    'independent-research': 'Independent research',
    'analyst': 'Analyst or trade estimate',
    'news': 'News report',
    'social': 'Social post',
}


def first_party(source, companies=()):
    """The source is published by one of the tracked companies: its host is that company's own
    investor-relations or blog host, or its publisher name is the company name.

    No longer part of grade derivation -- provenance is reviewed, not inferred -- but still the
    check a reviewer uses when deciding whether a page is that company's own channel.
    """
    if not source:
        return False
    host = (urlparse(source.get('url', '')).hostname or '').lower().removeprefix('www.')
    publisher = re.sub(r'[^a-z0-9]+', ' ', str(source.get('publisher', '')).lower()).strip()
    for company in companies or ():
        name = re.sub(r'[^a-z0-9]+', ' ', str(company.get('name', '')).lower()).strip()
        if name and (publisher == name or publisher.startswith(name+' ')):
            return True
        for url in [company.get('ir_url')] + list(company.get('blog_urls') or []):
            owned = (urlparse(url or '').hostname or '').lower().removeprefix('www.')
            if owned and (host == owned or host.endswith('.'+owned)):
                return True
    return False


def provenance_of(source):
    """The source's reviewed provenance, or None when it carries nothing recognized."""
    value = (source or {}).get('provenance')
    return value if value in PROVENANCE else None


def grade_for(policy=None, source=None, companies=()):
    """Deterministic evidence grade, from the source's own reviewed provenance.

    `policy` and `companies` are accepted and ignored: every call site already has them in hand,
    and keeping the signature means the change is one function rather than a sweep. A source with
    no recognized provenance fails closed to D rather than being promoted by silence; validation
    (source_valid) refuses to publish one at all, so that branch is a backstop, not a path.
    """
    provenance = provenance_of(source)
    return PROVENANCE_GRADE[provenance] if provenance else 'D'

# A source unchanged for this many consecutive checks is worth checking less often. Promotion
# only ever loosens the registered cadence in memory; research/sources.json never changes.
#
# Until 2026-09-12 only a registered-daily source could be promoted. Measured that day: 325 of
# the 393 fetchable sources were fixed pages, 169 of them registered weekly, and not one of the
# 325 was backed off -- weekly was exempt by rule, and the streak counts checks rather than
# days, so a weekly page would have needed seven weeks of identical text to earn what a daily
# page earns in seven days. The weekly threshold below is in weeks. Indexes are never promoted
# here: the queue polls them on feed_poll_minutes and skips this rule for them.
PROMOTE_TO_WEEKLY_STREAK = 7                              # daily: seven unchanged days
PROMOTE_TO_MONTHLY_STREAK = PROMOTE_TO_WEEKLY_STREAK + 6  # daily: thirteen unchanged days
PROMOTE_WEEKLY_TO_MONTHLY_STREAK = 4                      # weekly: four unchanged weeks

def effective_cadence(policy, state=None):
    """The cadence actually checked today, given private per-source fetch state.

    `state` is the caller's private per-URL fetch-state record (unchanged_streak and the
    like); pass None (or omit it) to read the plain registered cadence unaffected. Any
    observed change resets the caller's stored streak to zero, so the very next check
    reverts here to the registered cadence -- nothing here is itself persisted.
    """
    cadence = policy.get('cadence')
    if cadence not in ('daily', 'weekly') or not isinstance(state, dict) or not state:
        return cadence
    streak = state.get('unchanged_streak', 0)
    if cadence == 'weekly':
        return 'monthly' if streak >= PROMOTE_WEEKLY_TO_MONTHLY_STREAK else 'weekly'
    if streak >= PROMOTE_TO_MONTHLY_STREAK: return 'monthly'
    if streak >= PROMOTE_TO_WEEKLY_STREAK: return 'weekly'
    return 'daily'

def due(policy, day, state=None):
    cadence = effective_cadence(policy, state)
    if cadence == 'manual': return False
    if cadence == 'weekly': return day.weekday() == policy.get('weekday', 0)
    if cadence == 'monthly': return day.weekday() == policy.get('weekday', 0) and day.day <= 7
    return True

def discoverable(source, url, policy):
    u = urlparse(url)
    path = unquote(u.path).lower()
    if u.scheme != 'https' or u.hostname != urlparse(source['url']).hostname or u.username or u.password or u.port not in (None,443) or u.query or u.fragment:
        return False
    if any(x in path for x in ('..', '/tag/', '/category/', '/author/', '/page/')):
        return False
    prefixes = policy.get('path_prefixes', [])
    if not (prefixes and any(path.startswith(x.lower()) for x in prefixes)):
        return False
    # An empty topic list means the SECTION is the scope. A company writes its posts as human
    # slugs -- x.ai/memphis/our-commitment, datacenters.atmeta.com/2026/07/hello-sturgeon-county --
    # which contain no topic word at all, so matching topics against the URL path silently
    # excluded every company section page (2026-09-12). A whole-site prefix still needs topics;
    # validate_registry refuses '/' without them, because that would walk an entire host.
    topics = policy.get('topics', [])
    if not topics:
        # Defence in depth: validate_registry refuses this combination at registration, and
        # this refuses to act on it if one ever gets through.
        return all(x.strip() != '/' for x in prefixes)
    return topical(path, topics)


def topical(path, topics):
    """A topic matches a whole word of the URL path, never a fragment of one.

    Substring matching let 'ai' match 'aim' and 'chain', so a Snapchat feature story passed the
    filter and cost a model call (measured 2026-09-10). A multi-word topic ('data-center') matches
    as a phrase across adjacent words, so both /data-center/ and /data_center_news/ still match."""
    words = [w for w in re.split(r'[^a-z0-9]+', path.lower()) if w]
    joined = ' '.join(words)
    for topic in topics or []:
        parts = [w for w in re.split(r'[^a-z0-9]+', str(topic).lower()) if w]
        if not parts:
            continue
        if len(parts) == 1:
            if parts[0] in words:
                return True
        elif ' '.join(parts) in joined:
            return True
    return False

def validate_registry(registry, companies):
    sources = {s['id']:s for s in registry['sources']}
    books = registry['region_books']
    require(set(books) == REGIONS, 'Region books missing')
    for book in books.values():
        require(set(book)=={'label','gap','sources'}, 'Unexpected region book')
        text(book['label']); text(book['gap'],1000)
        require(set(book['sources']) <= sources.keys(), 'Unknown regional source')
    for sid, p in registry['collection'].items():
        require(sid in sources, 'Unknown collection source')
        require(set(p)=={'rank','region_book','company_id','claim_type','cadence','weekday','path_prefixes','topics','excerpts'}, 'Unexpected collection policy')
        require(type(p['rank']) is int and 1<=p['rank']<=6, 'Invalid source rank')
        require(p['region_book'] in REGIONS and (p['company_id'] is None or p['company_id'] in companies), 'Invalid source identity')
        require(p['claim_type'] in CLAIMS and p['cadence'] in {'daily','weekly','manual'}, 'Invalid collection class')
        require(type(p['weekday']) is int and 0<=p['weekday']<=6 and type(p['excerpts']) is bool, 'Invalid collection schedule')
        require(p['rank']!=3 or p['cadence'] in {'weekly','manual'}, 'Technical publishing requires weekly or manual cadence')
        require(p['cadence']!='manual' or (not p['path_prefixes'] and not p['excerpts']), 'Manual sources cannot enable unattended discovery or excerpts')
        # Deliverable 3: rank-5 trade/analyst aggregators remain private leads -- an index/feed
        # source is walked for discovered child pages, which auto-publish; only rank <=4 or an
        # official social account (rank 6) may be walked this way.
        require(p['rank']!=5 or not sources[sid].get('index'), 'A rank-5 aggregator cannot be an index/feed source; it must remain a private lead')
        # An index/feed source exists to be walked for child pages, and discoverable() requires
        # BOTH a matching path prefix and a topic match. One with either list empty is therefore
        # re-fetched every cycle and can never yield a child. Measured 2026-09-11: nvidia-news,
        # microsoft-news and google-research were the three most-read documents of a 189-batch
        # overnight session -- 103 of its 600 fetches -- and produced nothing, because the index
        # page itself went to the model, which correctly called it out of scope.
        if sources[sid].get('index'):
            require(p['path_prefixes'], 'An index source with no path prefixes can never discover a child page')
            # Topics may be empty only when the prefix itself scopes the subject: '/memphis/' is
            # about one data centre, '/' is the whole host and needs the topic filter to stay
            # anywhere near the thesis.
            require(p['topics'] or '/' not in p['path_prefixes'], 'A whole-site index needs topics; only a narrower section may rely on its prefix alone')
        for prefix in p['path_prefixes']:
            # A feed source's candidate links come from the feed's own entries, not from walking the
            # site, so a whole-site prefix there means "any article this outlet published" and the
            # reviewed topic words do the filtering. An ordinary page is still walked for same-host
            # links, so '/' would be real wildcard discovery and stays forbidden.
            whole_site=prefix=='/' and sources[sid].get('index')
            require(prefix.startswith('/') and (prefix!='/' or whole_site) and '*' not in prefix and '..' not in prefix, 'Wildcard discovery forbidden')
        # Topics may be empty only when the prefix itself scopes the subject. A company writes
        # its posts as human slugs -- x.ai/memphis/our-commitment, /2026/07/hello-sturgeon-county
        # -- which carry no topic word, so requiring topics excluded every company section page
        # (2026-09-12). A whole-site prefix still needs them: that is real wildcard discovery.
        require(not p['path_prefixes'] or p['topics'] or '/' not in p['path_prefixes'],
                'A whole-site discovery prefix needs reviewed topics; only a narrower section may rely on its prefix alone')
        for topic in p['topics']: text(topic,80)

def validate_excerpts(dataset, ledger, registry):
    require(set(dataset)=={'version','excerpts'} and dataset['version']==1, 'Invalid excerpt dataset')
    sources={s['id']:s for s in ledger['sources']}; metrics={m['id']:m for m in ledger['metrics']}
    totals={}; seen=set()
    fields={'source_id','company_id','url','published_at','retrieved_at','layer','region_book','claim_type','status','metric_ids','quote','notes'}
    for e in dataset['excerpts']:
        require(fields<=e.keys() and e.keys()<=fields|{'correction_history'} and e['source_id'] in sources, 'Invalid excerpt fields/source')
        s=sources[e['source_id']]; p=collection_for(registry,s)
        require(p.get('excerpts') and e['company_id']==p['company_id'] and e['region_book']==p['region_book'] and e['claim_type']==p['claim_type'], 'Excerpt identity differs from review')
        require(e['url']==s['url'] and e['published_at']==s['published'] and e['layer']==s['layers'], 'Excerpt attribution mismatch')
        require(e['status'] in STATUSES and set(e['metric_ids'])<=metrics.keys(), 'Unknown excerpt metric/status')
        for mid in e['metric_ids']: require(s.get('parent_source',s['id']) in metrics[mid]['source_ids'], 'Excerpt metric/source mismatch')
        timestamp(e['retrieved_at']); text(e['quote'],500); text(e['notes'],1000)
        key=(e['url'],e['quote'])
        require(key not in seen, 'Duplicate excerpt'); seen.add(key)
        totals[e['url']]=totals.get(e['url'],0)+len(e['quote'].split())
        require(totals[e['url']]<=25, 'Public quote budget exceeded')
        history=e.get('correction_history',[])
        require(isinstance(history,list),'Invalid excerpt correction history')
        last=timestamp(e['retrieved_at'])
        for revision in history:
            require(set(revision)=={'corrected_at','reason','previous'},'Invalid excerpt correction fields')
            when=timestamp(revision['corrected_at']);require(when>=last,'Excerpt correction chronology reversed');last=when
            text(revision['reason'],500)
            previous=revision['previous']
            require(isinstance(previous,dict) and previous and previous.keys()<={'status','notes','company_id','region_book','claim_type'},'Invalid previous excerpt values')
            if 'status' in previous:require(previous['status'] in STATUSES,'Invalid previous excerpt status')
            if 'notes' in previous:text(previous['notes'],1000)
            if 'company_id' in previous and previous['company_id'] is not None:text(previous['company_id'],140)
            if 'region_book' in previous:require(previous['region_book'] in REGIONS,'Invalid previous region')
            if 'claim_type' in previous:require(previous['claim_type'] in CLAIMS,'Invalid previous claim type')

def append_excerpt(dataset, source, policy, evidence, notes, retrieved_at, status='company-commitment', metric_ids=None):
    # Identity, class and URLs come from reviewed policy, never model text.
    if not policy.get('excerpts') or any(e['url']==source['url'] for e in dataset['excerpts']): return False
    quote=' '.join(evidence.split()[:25])
    dataset['excerpts'].append(dict(source_id=source['id'],company_id=policy['company_id'],url=source['url'],published_at=source['published'],retrieved_at=retrieved_at,layer=source['layers'],region_book=policy['region_book'],claim_type=policy['claim_type'],status=status,metric_ids=metric_ids or [],quote=quote,notes=notes))
    return True
