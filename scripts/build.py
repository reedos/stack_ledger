"""Deterministic, dependency-free GitHub Pages build."""
import json
import hashlib
import re
import shutil
from pathlib import Path
from xml.etree import ElementTree as ET
from html import escape
from render import HOME_DESCRIPTION, home, navigation, runtime, company_snapshot

ROOT = Path(__file__).resolve().parents[1]

def analytics_tag(config, base):
    """Public endpoint only; analytics configuration is outside research permissions."""
    if not isinstance(config,dict) or set(config)!={'goatcounter_site'}:
        raise ValueError('Unexpected analytics configuration')
    code=config['goatcounter_site']
    if code is None:
        return ''
    if not isinstance(code,str) or not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?',code):
        raise ValueError('Use the GoatCounter site code, without a URL or credentials')
    return f'<script src="{escape(base,quote=True)}assets/analytics.js" data-goatcounter="https://{code}.goatcounter.com/count" defer></script>'

def build():
    from validate_ecosystem import validate_files
    validate_files()
    from validate_delivery import validate_files as validate_delivery_files
    validate_delivery_files()
    from validate_fabric import validate_files as validate_fabric_files
    validate_fabric_files()
    from validate_expansion import validate_files as validate_expansion_files
    validate_expansion_files()
    from validate_chip_capacity import validate_files as validate_chip_capacity_files
    validate_chip_capacity_files()
    from validate_agenda import validate_files as validate_agenda_files
    validate_agenda_files()
    from validate_claims import validate_files as validate_claims_files
    validate_claims_files()
    data = json.loads((ROOT / 'site/data/ledger.json').read_text(encoding='utf-8'))
    from editorial import read, validate_config
    homepage = read(ROOT/'research/homepage.json')
    editorial_policy = read(ROOT/'research/editorial-policy.json')
    validate_config(homepage, data, editorial_policy)
    template = (ROOT / 'site/template.html').read_text(encoding='utf-8')
    analytics = json.loads((ROOT/'site/analytics.json').read_text(encoding='utf-8'))
    analytics_tag(analytics, './')
    digest=hashlib.sha256()
    digest.update(json.dumps(homepage, sort_keys=True).encode())
    digest.update(json.dumps(editorial_policy, sort_keys=True).encode())
    for asset in sorted(p for directory in ['site/assets','site/data'] for p in (ROOT/directory).rglob('*') if p.is_file()):
        digest.update(asset.relative_to(ROOT).as_posix().encode())
        # Line endings differ between a Windows working copy and a fresh checkout; the
        # build stamp must not. Hash the normalized bytes so both agree.
        digest.update(asset.read_bytes().replace(b'\r\n',b'\n'))
    build_version=digest.hexdigest()[:16]
    dest = ROOT / 'docs'
    dest.mkdir(exist_ok=True)
    shutil.copytree(ROOT / 'site/assets', dest / 'assets', dirs_exist_ok=True)
    shutil.copytree(ROOT / 'site/data', dest / 'data', dirs_exist_ok=True)
    pages = [('home', '', 'Stack Ledger — The AI buildout, layer by layer', 'A public record of the AI buildout.', HOME_DESCRIPTION),
             ('ledger','ledger/','The Ledger — Stack Ledger','A record of real progress.','Explore sourced AI buildout research, observations, forecasts, targets and daily local-model research runs.'),
             ('methodology','methodology/','Research Methodology — Stack Ledger','Open by design. Grounded in evidence.','How Stack Ledger sources, validates and publishes research on the five-layer AI buildout.')]
    pages += [('companies','companies/','Companies — Stack Ledger','Meet the builders.','Companies, capabilities and reported revenue across the five layers of AI.'), ('industry','industry/','Jobs & Industry — Stack Ledger','Intelligence has a physical footprint.','Chip capacity, factory milestones, jobs and evidence of industrial rebuilding.')]
    pages += [('projects','projects/','Delivery Tracker — Stack Ledger','From promise to power.','Track power, AI campuses, fabs and physical applications: sourced stages, capacity, capital and jobs.')]
    pages += [('claims','claims/','Claims & Evidence — Stack Ledger','Build more. Know what it delivers.','Evidence on data-center water, electricity bills, jobs, taxes, clean energy and community benefits.')]
    pages += [(l['id'], l['id']+'/', l['name']+' — Stack Ledger', l['tagline'], l['description']) for l in data['layers']]
    companies = json.loads((ROOT / 'research/ecosystem.json').read_text(encoding='utf-8'))['companies']
    profiles = {f'companies/{c["id"]}/': c for c in companies}
    from render_explorers import capital, capabilities, project_map, previews
    expansion = json.loads((ROOT/'research/expansion.json').read_text(encoding='utf-8'))
    delivery = json.loads((ROOT/'research/delivery.json').read_text(encoding='utf-8'))
    pages += [('company', path, c['name']+' — Revenue & research — Stack Ledger', c['name'], c['role']) for path,c in profiles.items()]
    for page,path,title,heading,description in pages:
        rendered=template
        base = '../' * path.count('/') if path else './'
        content = home(data, base, homepage, editorial_policy) if page == 'home' else (f'<section class="page-hero"><div class="eyebrow">STACK LEDGER / OPEN RESEARCH</div><h1>{escape(heading)}</h1><p>{escape(description)}</p></section>')
        if page == 'company': content = company_snapshot(data, profiles[path], base)
        from layer_diagrams import DIAGRAMS, render_layer_diagram
        if page in DIAGRAMS: content += render_layer_diagram(page, data['sources'], next(l['color'] for l in data['layers'] if l['id']==page))
        if page == 'home':
            content = content.replace('<div id="home-details">',capital(data,expansion,base)+previews(delivery,data,expansion,base)+'<div id="home-details">')
        if page == 'models': content += capabilities(data,expansion,base)
        if page == 'infrastructure': content += capital(data,expansion,base)
        if page == 'projects': content += project_map(delivery,data,base)
        if page == 'industry':
            from render_industry import industry_opening
            content += industry_opening(data, base)
        if page == 'claims':
            from render_claims import render_claims
            content = render_claims(json.loads((ROOT/'research/claims.json').read_text(encoding='utf-8')), data['sources'], base)
        for key, value in {'CONTENT': content, 'STACK_NAV': navigation(data, base, page), 'RUNTIME': runtime(data), 'ANALYTICS': analytics_tag(analytics, base)}.items():
            rendered=rendered.replace('{{'+key+'}}', value)
        for key,value in {'TITLE':title,'HEADING':heading,'DESCRIPTION':description,'PAGE':page,'BASE':base,'CANONICAL':path,'BUILD':build_version}.items():
            rendered=rendered.replace('{{'+key+'}}',escape(value,quote=True))
        rendered=re.sub(r'((?:href|src)="[^"<>]*assets/[^"<>]+\.(?:css|js))"',lambda match:match[1]+'?v='+build_version+'"',rendered)
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
    updated=max([data['runtime']['last_attempt'] or max(o['retrieved_at'] for o in data['observations'])]+[e['corrected_at'] for e in data['events'] if e.get('corrected_at')])
    child(feed,'updated',updated)
    child(child(feed,'author'),'name','Stack Ledger')
    sources={s['id']:s for s in data['sources']}
    from validate import current_events
    for event in current_events(data['events']):
        entry=child(feed,'entry')
        child(entry,'id','https://reedos.github.io/stack_ledger/ledger/#'+event['id'])
        child(entry,'title',event['title'])
        child(entry,'link',href=sources[event['source']]['url'])
        child(entry,'updated',event.get('corrected_at',event.get('retrieved_at',data['seed_date']+'T12:00:00Z')))
        if event['date']: child(entry,'published',event['date']+'T12:00:00Z')
        child(entry,'summary',event['summary']+(' Correction: '+event['correction_reason'] if event.get('correction_of') else ''))
        if event.get('correction_of'):
            child(entry,'link',rel='related',href='https://reedos.github.io/stack_ledger/ledger/#'+event['correction_of'])
    for run in data['runs'][-30:]:
        entry=child(feed,'entry')
        child(entry,'id','https://reedos.github.io/stack_ledger/ledger/#'+run['id'])
        child(entry,'title',f"Research run: {run['status']} · {run['accepted']} new research records")
        child(entry,'link',href='https://reedos.github.io/stack_ledger/ledger/')
        child(entry,'updated',run['finished_at'])
        child(entry,'summary',f"Fetched {run['documents_fetched']} documents; accepted {run['accepted']} records; quarantined {run['quarantined']} proposals. {len(run['source_failures'])} source failures.")
    ET.ElementTree(feed).write(dest/'feed.xml',encoding='utf-8',xml_declaration=True)

if __name__=='__main__': build()
