"""Cross-check the reviewed research agenda and source-policy artifacts."""
import json
from pathlib import Path
from validate import require, text, timestamp
from source_policy import validate_registry, validate_excerpts
ROOT=Path(__file__).resolve().parents[1]

def validate_files():
    read=lambda p:json.loads((ROOT/p).read_text(encoding='utf-8'))
    ledger=read('site/data/ledger.json');registry=read('research/sources.json');eco=read('research/ecosystem.json')
    validate_registry(registry,{c['id'] for c in eco['companies']})
    require(read('site/data/source-books.json')=={k:registry[k] for k in ['region_books','collection']},'Source books differ from reviewed policy')
    validate_excerpts(read('site/data/excerpts.json'),ledger,registry)
    from urllib.parse import urlparse
    sources_by_id={s['id']:s for s in ledger['sources']}
    from render import latest_headline
    for layer in ledger['layers']:
        o=latest_headline(ledger,layer)
        if o:
            u=urlparse(sources_by_id[o['source']]['url'])
            require(not ('blog' in u.hostname or '/blog/' in u.path or '/blogs/' in u.path),'Homepage headline cannot rely only on a product blog')
    a=read('research/agenda.json');require(a==read('site/data/agenda.json'),'Reviewed agenda changed')
    require(set(a)=={'version','reviewed_at','sections'} and a['version']==1,'Invalid agenda');timestamp(a['reviewed_at'])
    sources={s['id'] for s in ledger['sources']};obs={o['id'] for o in ledger['observations']};metrics={m['id'] for m in ledger['metrics']};ids=set()
    for s in a['sections']:
        require(set(s)=={'id','pages','title','intro','cards','charts'},'Invalid section')
        require(set(s['pages'])<={'energy','chips','infrastructure','models','applications','industry'},'Invalid agenda route')
        require(set(s['charts'])<=metrics,'Unknown chart')
        for k in ['id','title','intro']:text(s[k],1000)
        for c in s['cards']:
            require(set(c)=={'id','title','stage','body','sources','observations','gap'},'Invalid agenda card')
            require(c['id'] not in ids,'Duplicate agenda card');ids.add(c['id'])
            for k in ['id','title','stage','body','gap']:text(c[k],1400)
            require(c['sources'] and set(c['sources'])<=sources and set(c['observations'])<=obs,'Unknown agenda evidence')
    return True
