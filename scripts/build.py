"""Deterministic, dependency-free GitHub Pages build."""
import json
import shutil
from pathlib import Path
from xml.etree import ElementTree as ET
from html import escape
from render import HOME_DESCRIPTION, home, navigation, runtime

ROOT = Path(__file__).resolve().parents[1]

def build():
    from validate_ecosystem import validate_files
    validate_files()
    from validate_delivery import validate_files as validate_delivery_files
    validate_delivery_files()
    from validate_fabric import validate_files as validate_fabric_files
    validate_fabric_files()
    from validate_expansion import validate_files as validate_expansion_files
    validate_expansion_files()
    data = json.loads((ROOT / 'site/data/ledger.json').read_text(encoding='utf-8'))
    template = (ROOT / 'site/template.html').read_text(encoding='utf-8')
    dest = ROOT / 'docs'
    dest.mkdir(exist_ok=True)
    shutil.copytree(ROOT / 'site/assets', dest / 'assets', dirs_exist_ok=True)
    shutil.copytree(ROOT / 'site/data', dest / 'data', dirs_exist_ok=True)
    pages = [('home', '', 'Stack Ledger — The AI buildout, layer by layer', 'A public record of the AI buildout.', HOME_DESCRIPTION),
             ('ledger','ledger/','The Ledger — Stack Ledger','A record of real progress.','Explore sourced AI buildout research, observations, forecasts, targets and daily local-model research runs.'),
             ('methodology','methodology/','Research Methodology — Stack Ledger','Open by design. Grounded in evidence.','How Stack Ledger sources, validates and publishes research on the five-layer AI buildout.')]
    pages += [('companies','companies/','Companies — Stack Ledger','Meet the builders.','Companies, capabilities and reported revenue across the five layers of AI.'), ('industry','industry/','Jobs & Industry — Stack Ledger','Intelligence has a physical footprint.','Chip capacity, factory milestones, jobs and evidence of industrial rebuilding.')]
    pages += [('projects','projects/','Delivery Tracker — Stack Ledger','From promise to power.','Track power, AI campuses, fabs and physical applications: sourced stages, capacity, capital and jobs.')]
    pages += [(l['id'], l['id']+'/', l['name']+' — Stack Ledger', l['tagline'], l['description']) for l in data['layers']]
    for page,path,title,heading,description in pages:
        rendered=template
        base = '../' if path else './'
        content = home(data, base) if page == 'home' else (f'<section class="page-hero"><div class="eyebrow">STACK LEDGER / OPEN RESEARCH</div><h1>{escape(heading)}</h1><p>{escape(description)}</p></section>')
        for key, value in {'CONTENT': content, 'STACK_NAV': navigation(data, base, page), 'RUNTIME': runtime(data)}.items():
            rendered=rendered.replace('{{'+key+'}}', value)
        for key,value in {'TITLE':title,'HEADING':heading,'DESCRIPTION':description,'PAGE':page,'BASE':'../' if path else './','CANONICAL':path}.items():
            rendered=rendered.replace('{{'+key+'}}',escape(value,quote=True))
        folder=dest/path
        folder.mkdir(parents=True,exist_ok=True)
        (folder/'index.html').write_text(rendered,encoding='utf-8')
    (dest/'.nojekyll').write_text('',encoding='utf-8')
    (dest/'404.html').write_text('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Page not found · Stack Ledger</title><body style="background:#101511;color:#f0f1e8;font:20px system-ui;padding:10vw"><h1>This layer hasn’t been built.</h1><p>Return to <a style="color:#c5f277" href="/stack_ledger/">Stack Ledger</a>.</p></body></html>',encoding='utf-8')
    atom(data,dest)
    (dest/'robots.txt').write_text('User-agent: *\nAllow: /\nSitemap: https://reedos.github.io/stack_ledger/sitemap.xml\n',encoding='utf-8')
    urls=''.join(f'<url><loc>https://reedos.github.io/stack_ledger/{path}</loc></url>' for _,path,*_ in pages)
    (dest/'sitemap.xml').write_text(f'<?xml version="1.0" encoding="utf-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>',encoding='utf-8')
    print(f'Built {len(pages)} pages into docs/')

def atom(data,dest):
    ns='http://www.w3.org/2005/Atom'
    ET.register_namespace('',ns)
    def child(parent,name,text=None,**attrs):
        node=ET.SubElement(parent,'{'+ns+'}'+name,attrs)
        if text is not None:node.text=str(text)
        return node
    feed=ET.Element('{'+ns+'}feed')
    child(feed,'title','Stack Ledger')
    child(feed,'id','https://reedos.github.io/stack_ledger/')
    child(feed,'link',href='https://reedos.github.io/stack_ledger/feed.xml',rel='self')
    child(feed,'link',href='https://reedos.github.io/stack_ledger/')
    updated=data['runtime']['last_attempt'] or max(o['retrieved_at'] for o in data['observations'])
    child(feed,'updated',updated)
    child(child(feed,'author'),'name','Stack Ledger')
    sources={s['id']:s for s in data['sources']}
    for event in data['events']:
        entry=child(feed,'entry')
        child(entry,'id','https://reedos.github.io/stack_ledger/ledger/#'+event['id'])
        child(entry,'title',event['title'])
        child(entry,'link',href=sources[event['source']]['url'])
        child(entry,'updated',event.get('retrieved_at',data['seed_date']+'T12:00:00Z'))
        if event['date']: child(entry,'published',event['date']+'T12:00:00Z')
        child(entry,'summary',event['summary'])
    for run in data['runs'][-30:]:
        entry=child(feed,'entry')
        child(entry,'id','https://reedos.github.io/stack_ledger/ledger/#'+run['id'])
        child(entry,'title',f"Research run: {run['status']} · {run['accepted']} new research records")
        child(entry,'link',href='https://reedos.github.io/stack_ledger/ledger/')
        child(entry,'updated',run['finished_at'])
        child(entry,'summary',f"Fetched {run['documents_fetched']} documents; accepted {run['accepted']} records; quarantined {run['quarantined']} proposals. {len(run['source_failures'])} source failures.")
    ET.ElementTree(feed).write(dest/'feed.xml',encoding='utf-8',xml_declaration=True)

if __name__=='__main__': build()
