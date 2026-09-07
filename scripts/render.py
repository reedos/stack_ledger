"""Reviewed static presentation. Research records supply values, never markup."""
from datetime import datetime
from html import escape as e
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
PAGE_IDS = ('home', 'energy', 'chips', 'infrastructure', 'models', 'applications',
            'projects', 'companies', 'industry', 'ledger', 'methodology')
GENERATED_PAGES = {'docs/' + ('' if p == 'home' else p + '/') + 'index.html' for p in PAGE_IDS}
HOME_DESCRIPTION = ('Track energy, chips, infrastructure, models and applications worldwide, '
                    'with deeper U.S. coverage and a horizon of 2030 and beyond.')
LABELS = {
    'energy': ('Generate', 'Global data-center electricity demand (all workloads)', 'TWh / year'),
    'chips': ('Compute', 'TSMC CoWoS packaging capacity (Epoch estimate)', 'thousand wafers / month'),
    'infrastructure': ('Connect', 'Stargate Abilene: estimated operating IT power', 'MW IT'),
    'models': ('Learn', 'GPT-3.5-level inference cost (MMLU benchmark)', 'USD / million tokens'),
    'applications': ('Apply', 'Waymo One: reported paid weekly service', 'paid trips / week'),
}
STATUSES = {'observation': 'Observation', 'estimate': 'Estimate', 'forecast': 'Forecast',
            'government-target': 'Government target', 'company-commitment': 'Company commitment'}


def link_url(url):
    return e(url, quote=True) if urlsplit(url).scheme == 'https' else '#'


def number(record):
    def fmt(value):
        return f'{value:,.3f}'.rstrip('0').rstrip('.')
    return ({'approx': '≈', 'gt': '>', 'lt': '<'}.get(record['precision'], '') + fmt(record['value'])
            + ('–' + fmt(record['upper']) if record.get('upper') is not None else ''))


def latest_headline(data, layer):
    records = [o for o in data['observations'] if o['metric'] == layer['headline_metric']
               and not o.get('superseded_by') and o['status'] in ('observation', 'estimate')]
    return max(records, key=lambda o: (o['year'], o['period']), default=None)


def layer_cards(data, base):
    cards = []
    for layer in data['layers']:
        verb, label, unit = LABELS[layer['id']]
        record = latest_headline(data, layer)
        if record:
            source = next(s for s in data['sources'] if s['id'] == record['source'])
            display = record
            if record['metric'] == 'tsmc-cowos-wpm':
                display = dict(record, value=record['value'] / 1000,
                               upper=record['upper'] / 1000 if record['upper'] is not None else None)
            evidence = (f'<div class="layer-value">{e(number(display))}</div>'
                        f'<div class="metric-context"><span>{e(unit)}</span><span>{e(record["period"])}</span></div>'
                        f'<p class="layer-label">{e(label)}</p>'
                        f'<span class="headline-status">{STATUSES[record["status"]]}</span>'
                        f'<a class="headline-source" href="{link_url(source["url"])}">{e(source["publisher"])} ↗</a>'
                        + ('<p class="headline-note">Historical benchmark snapshot; not current pricing.</p>'
                           if layer['id'] == 'models' else ''))
        else:
            evidence = (f'<div class="layer-value research-gap">Research gap</div>'
                        f'<p class="layer-label">{e(label)}</p><span class="headline-status">No headline observation</span>'
                        '<p class="headline-note">No reviewed outcome metric in the catalog yet. Adoption is not productivity.</p>')
        cards.append(f'<article class="layer-card" style="--accent:{e(layer["color"])}" data-layer="{e(layer["id"])}">'
                     f'<div class="layer-card-top"><span class="layer-verb">{verb}</span><span class="ordinal">LAYER {e(layer["number"])}</span></div>'
                     f'<h3><a href="{base}{e(layer["id"])}/">{e(layer["name"])}</a></h3>{evidence}'
                     f'<a class="layer-card-bottom" href="{base}{e(layer["id"])}/"><span>Explore {e(layer["name"].lower())}</span><span>↗</span></a></article>')
    return '<div class="layer-grid">' + ''.join(cards) + '</div>'


def home(data, base):
    stack = (ROOT / 'site/partials/stack.html').read_text(encoding='utf-8').replace('{{BASE}}', base)
    return f'''<section class="hero"><div class="hero-copy">
      <div class="eyebrow"><span class="dot"></span>A PUBLIC LEDGER OF THE AI BUILDOUT</div>
      <h1>A public record of<br><em>the AI buildout.</em></h1>
      <p class="hero-description">{HOME_DESCRIPTION}</p>
      <div class="hero-actions"><a class="button" href="#stack">Explore the stack <span>↓</span></a><a class="text-link" href="{base}ledger/">Read the ledger <span>↗</span></a></div>
      <div class="hero-meta"><span>Global perspective</span><span>U.S. in focus</span><span>2030 &amp; beyond</span></div>
      </div><div class="hero-art">{stack}<div class="art-caption"><span>Five connected layers. Evidence at every step.</span></div></div></section>
      <section class="section" id="stack"><div class="section-top"><div><div class="eyebrow muted">THE BUILDOUT, AT A GLANCE</div><h2>Every layer, with evidence.</h2></div><p>Power enables chips and AI factories. Models turn compute into capabilities; applications put them to work.</p></div>
      {layer_cards(data, base)}
      <p class="chart-footnote">Selected indicators, not an overall progress score. Each figure keeps its own scope, period and publisher. <a class="source-inline" href="{base}data/ledger.json">Inspect the raw ledger ↗</a></p></section>
      <aside class="reading-note homepage-reading"><strong>Pledged is not built.</strong><p>Announced ≠ financed ≠ under construction ≠ commissioned ≠ operating. Follow the evidence for each stage in the <a class="source-inline" href="{base}projects/">project tracker ↗</a>.</p></aside>
      <div id="home-details"></div>'''


def navigation(data, base, page):
    links = ''.join(f'<a href="{base}{e(l["id"])}/" style="--accent:{e(l["color"])}"'
                    + (' aria-current="page"' if page == l['id'] else '')
                    + f'>{e(l["number"])} · {e(l["name"])}</a>' for l in data['layers'])
    return f'<details class="stack-menu"><summary>The stack</summary><div class="stack-destinations">{links}</div></details>'


def runtime(data):
    r = data['runtime']
    def stamp(value):
        if not value:
            return 'Not yet run'
        instant = datetime.fromisoformat(value.replace('Z', '+00:00'))
        # Windows may not ship IANA tzdata. UTC is an explicit, correct fallback;
        # browsers enhance to Pacific time using their bundled timezone data.
        try:
            from zoneinfo import ZoneInfo
            instant = instant.astimezone(ZoneInfo(r['timezone']))
        except (ImportError, KeyError):
            pass
        return instant.strftime('%Y-%m-%d %H:%M %Z')
    last = data['runs'][-1] if data['runs'] else None
    receipt = (f'<li>Latest run: {last["documents_fetched"]} documents, {last["accepted"]} accepted records, '
               f'{last["quarantined"]} quarantined proposals; {len(last["source_failures"])} source failures.</li>' if last else '')
    return (f'<strong>Research runtime:</strong> {e(r["display_model"])} · {e(r["engine"])} · {e(r["hardware"])}<br>'
            f'<strong>Last run:</strong> {e(stamp(r["last_attempt"]))} · <strong>Status:</strong> {e(r["status"])} · '
            f'<strong>Last successful research:</strong> {e(stamp(r["last_success"]))}'
            '<details><summary>Runtime details &amp; provenance</summary><ul>'
            f'<li>Exact model: {e(r["model"])}</li><li>Schedule: {e(r["schedule"])}. Hardware configuration is owner-reported.</li>'
            f'<li>Initial curated dataset: {e(data["seed_date"])}. Automated records are labeled individually.</li>{receipt}</ul></details>')
