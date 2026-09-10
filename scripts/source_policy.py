"""Reviewed collection boundaries and append-only public evidence excerpts."""
from urllib.parse import urlparse, unquote
from validate import require, text, timestamp, LAYERS, STATUSES

REGIONS = {'united-states','taiwan','korea','japan','china','europe','middle-east','india','canada-latam-africa-anz','global','unknown'}
CLAIMS = {'architecture','shipment','financial','roadmap','safety','clinical','labor','other','news'}
GRADES = {'A','B','C','D'}

def collection_for(registry, source):
    return registry.get('collection', {}).get(source.get('parent_source', source['id']), {})

# Owner decision, September 9, 2026 (exploratory intake with graded evidence): every published
# event/note and every automated observation carries a grade derived only from the registry's
# own reviewed rank and claim_type -- never chosen by the model. Rank already carries an
# established meaning (session_options.SOURCE_KINDS): 1 official data/filings, 2 earnings & IR,
# 3 technical/product publishing, 4 press releases & newsrooms, 5 news & analyst leads, 6
# official social accounts. claim_type 'news' marks a registered independent news outlet's own
# feed (deliverable 4 registers those at rank 4, so rank alone cannot tell them apart from an
# ordinary company newsroom feed at the same rank). Total and order-sensitive: rank 1 always
# wins as A; 'news' always reads as a third-party report (C) whatever its rank; every other
# rank 2/3/4/6 source is the company's own channel (B, matching "company statement... official
# account" in the owner decision verbatim); rank 5 is third-party trade/analyst reporting (C);
# anything else -- no policy, or a rank outside the reviewed 1-6 range -- fails closed to D,
# the most conservative grade, rather than silently promoting an unrecognized source.
def grade_for(policy):
    if not policy or not isinstance(policy, dict):
        return 'D'
    rank = policy.get('rank')
    if rank == 1:
        return 'A'
    if policy.get('claim_type') == 'news':
        return 'C'
    if rank in (2, 3, 4, 6):
        return 'B'
    if rank == 5:
        return 'C'
    return 'D'

# A daily source unchanged for this many consecutive checks is worth checking less often.
# Promotion only ever loosens a *registered daily* cadence; weekly and manual sources are
# never promoted, and research/sources.json's own registered cadence never changes for it.
PROMOTE_TO_WEEKLY_STREAK = 7
PROMOTE_TO_MONTHLY_STREAK = PROMOTE_TO_WEEKLY_STREAK + 6

def effective_cadence(policy, state=None):
    """The cadence actually checked today, given private per-source fetch state.

    `state` is the caller's private per-URL fetch-state record (unchanged_streak and the
    like); pass None (or omit it) to read the plain registered cadence unaffected. Any
    observed change resets the caller's stored streak to zero, so the very next check
    reverts here to the registered cadence -- nothing here is itself persisted.
    """
    cadence = policy.get('cadence')
    if cadence != 'daily' or not isinstance(state, dict) or not state:
        return cadence
    streak = state.get('unchanged_streak', 0)
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
    return bool(prefixes and any(path.startswith(p.lower()) for p in prefixes) and any(t.lower() in path for t in policy.get('topics', [])))

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
        for prefix in p['path_prefixes']:
            require(prefix.startswith('/') and prefix!='/' and '*' not in prefix and '..' not in prefix, 'Wildcard discovery forbidden')
        require(not p['path_prefixes'] or p['topics'], 'Discovery needs reviewed topics')
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
