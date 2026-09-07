"""Reviewed static presentation. Research records supply values, never markup."""
from datetime import datetime
from html import escape as e
from pathlib import Path
from urllib.parse import urlsplit
import json
import re

ROOT = Path(__file__).resolve().parents[1]
PAGE_IDS = ('home', 'energy', 'chips', 'infrastructure', 'models', 'applications',
            'projects', 'companies', 'industry', 'ledger', 'methodology')
GENERATED_PAGES = {'docs/' + ('' if p == 'home' else p + '/') + 'index.html' for p in PAGE_IDS}
COMPANY_IDS = tuple(c['id'] for c in json.loads((ROOT / 'research/ecosystem.json').read_text(encoding='utf-8'))['companies'])
assert all(re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', cid) for cid in COMPANY_IDS)
GENERATED_PAGES |= {f'docs/companies/{cid}/index.html' for cid in COMPANY_IDS}


def company_snapshot(data, company, base):
    """Useful financial evidence even without JavaScript."""
    sources = {s['id']: s for s in data['sources']}
    metrics = {m['id']: m for m in data['metrics']}
    mid = company.get('revenue_chart_metric') or company['revenue_metric']
    metric = metrics.get(mid)
    mids = {mid, metric.get('chart_companion_metric') if metric else None}
    records = sorted((o for o in data['observations'] if o['metric'] in mids and not o.get('superseded_by')), key=lambda o: (o['year'], o['period']))
    rows = ''.join(f'<tr><td>{e(o["period"])}</td><td>{e(number(o))}</td><td>{STATUSES[o["status"]]}</td><td><a href="{link_url(sources[o["source"]]["url"])}">{e(sources[o["source"]]["publisher"])}</a></td></tr>' for o in records)
    financials = (f'<h2>Revenue history &amp; outlook</h2><p>{e(metric["scope"])} · {e(metric["unit"])}</p><div class="table-scroll"><table><thead><tr><th>Period</th><th>Revenue</th><th>Classification</th><th>Source</th></tr></thead><tbody>{rows}</tbody></table></div>' if records else '<h2>Revenue coverage</h2><p>No reviewed revenue series yet. Missing data does not mean zero revenue. Funding and valuation are not substitutes.</p>')
    return (f'<section class="page-hero" data-company="{e(company["id"])}"><a class="section-link" href="{base}companies/">← All companies</a><div class="eyebrow">THE BUILDERS / COMPANY RESEARCH</div><h1>{e(company["name"])}</h1><p>{e(company["role"])}</p></section><section class="panel">{financials}</section>')
HOME_DESCRIPTION = ('Track energy, chips, infrastructure, models and applications worldwide, '
                    'with deeper U.S. coverage and a horizon of 2030 and beyond.')
LABELS = {
    'energy': ('Generate', 'Global data-center electricity demand (all workloads)', 'TWh / year'),
    'chips': ('Compute', 'TSMC CoWoS packaging capacity (Epoch estimate)', 'thousand wafers / month'),
    'infrastructure': ('Connect', 'Stargate Abilene: estimated operating IT power', 'MW IT'),
    'models': ('Learn', 'GPT-5.3-Codex API input list price', 'USD / million input tokens'),
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
                        + ('<p class="headline-note">Named model, dated price. Excludes tools, subscriptions and oversight.</p>'
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
      <section class="section" id="stack"><div class="section-top"><div><div class="eyebrow muted">FIVE LAYERS. ONE CONNECTED PURPOSE.</div><h2>From power to useful work.</h2></div></div>
      <p class="stack-thesis"><a href="{base}energy/">Power</a> enables <a href="{base}chips/">chips</a> and <a href="{base}infrastructure/">AI factories</a>.<br><a href="{base}models/">Models</a> turn compute into capabilities; <a href="{base}applications/">applications</a> put them to <strong>useful work.</strong></p>
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
