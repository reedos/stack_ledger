"""Reviewed collection boundaries and append-only public evidence excerpts."""
from urllib.parse import urlparse, unquote
from validate import require, text, timestamp, LAYERS, STATUSES

REGIONS = {'united-states','taiwan','korea','japan','china','europe','middle-east','india','canada-latam-africa-anz','global','unknown'}
CLAIMS = {'architecture','shipment','financial','roadmap','safety','clinical','labor','other'}

def collection_for(registry, source):
    return registry.get('collection', {}).get(source.get('parent_source', source['id']), {})

def due(policy, day):
    return policy.get('cadence') != 'weekly' or day.weekday() == policy.get('weekday', 0)

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
        require(p['claim_type'] in CLAIMS and p['cadence'] in {'daily','weekly'}, 'Invalid collection class')
        require(type(p['weekday']) is int and 0<=p['weekday']<=6 and type(p['excerpts']) is bool, 'Invalid collection schedule')
        require(p['rank']!=3 or p['cadence']=='weekly', 'Technical publishing requires weekly cadence')
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
        require(set(e)==fields and e['source_id'] in sources, 'Invalid excerpt fields/source')
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

def append_excerpt(dataset, source, policy, evidence, notes, retrieved_at, status='company-commitment', metric_ids=None):
    # Identity, class and URLs come from reviewed policy, never model text.
    if not policy.get('excerpts') or any(e['url']==source['url'] for e in dataset['excerpts']): return False
    quote=' '.join(evidence.split()[:25])
    dataset['excerpts'].append(dict(source_id=source['id'],company_id=policy['company_id'],url=source['url'],published_at=source['published'],retrieved_at=retrieved_at,layer=source['layers'],region_book=policy['region_book'],claim_type=policy['claim_type'],status=status,metric_ids=metric_ids or [],quote=quote,notes=notes))
    return True
