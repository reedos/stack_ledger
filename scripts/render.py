"""Reviewed static presentation. Research records supply values, never markup."""
from datetime import datetime
from html import escape as e
from pathlib import Path
from urllib.parse import urlsplit
import json
import re

ROOT = Path(__file__).resolve().parents[1]
PAGE_IDS = ('home', 'energy', 'chips', 'infrastructure', 'models', 'applications',
            'projects', 'companies', 'industry', 'ledger', 'methodology', 'claims')
GENERATED_PAGES = {'docs/' + ('' if p == 'home' else p + '/') + 'index.html' for p in PAGE_IDS}
_ECOSYSTEM_COMPANIES = json.loads((ROOT / 'research/ecosystem.json').read_text(encoding='utf-8'))['companies']
COMPANY_IDS = tuple(c['id'] for c in _ECOSYSTEM_COMPANIES)
COMPANIES = {c['id']: c for c in _ECOSYSTEM_COMPANIES}
assert all(re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', cid) for cid in COMPANY_IDS)
GENERATED_PAGES |= {f'docs/companies/{cid}/index.html' for cid in COMPANY_IDS}


def _normalized_name(value):
    return re.sub(r'[^a-z0-9]+', ' ', (value or '').lower()).strip()


def _normalized_host(url):
    try:
        host = (urlsplit(url).hostname or '').lower()
    except ValueError:
        return ''
    return host[4:] if host.startswith('www.') else host


def is_first_party(source, company):
    """A forecast's source is first-party when its publisher/host is the tracked company's own."""
    if not company:
        return False
    publisher, name = _normalized_name(source.get('publisher')), _normalized_name(company.get('name'))
    if name and (publisher == name or publisher.startswith(name + ' ')):
        return True
    source_host = _normalized_host(source.get('url', ''))
    if not source_host:
        return False
    for url in [company.get('ir_url')] + list(company.get('blog_urls') or []):
        host = _normalized_host(url) if url else ''
        if host and (source_host == host or source_host.endswith('.' + host)):
            return True
    return False


def attribution_label(o, metric, source, company):
    """Reader-facing evidence label: distinguishes a company's own forecast from an independent one."""
    status = o['status']
    if status == 'forecast':
        return 'Company guidance' if is_first_party(source, company) else 'Independent projection'
    return {'observation': 'Reported observation', 'estimate': 'Historical estimate',
            'company-commitment': 'Company commitment', 'government-target': 'Government target'}.get(status, STATUSES.get(status, status))


def company_snapshot(data, company, base):
    """Useful financial evidence even without JavaScript."""
    sources = {s['id']: s for s in data['sources']}
    metrics = {m['id']: m for m in data['metrics']}
    mid = company.get('revenue_chart_metric') or company['revenue_metric']
    metric = metrics.get(mid)
    mids = {mid, metric.get('chart_companion_metric') if metric else None}
    records = sorted((o for o in data['observations'] if o['metric'] in mids and not o.get('superseded_by')), key=lambda o: (o['year'], o['period']))
    published = lambda o: sources[o['source']].get('published') or 'date unlisted'
    rows = ''.join(f'<tr><td>{e(o["period"])}</td><td>{e(number(o))}</td><td>{attribution_label(o, metrics[o["metric"]], sources[o["source"]], COMPANIES.get(metrics[o["metric"]].get("company")))}</td>'
                   f'<td>{e(published(o))}</td><td><a href="{link_url(sources[o["source"]]["url"])}">{e(sources[o["source"]]["publisher"])}</a></td></tr>' for o in records)
    output = ''
    if company.get('output_metric') and company['output_metric'] in metrics:
        om = metrics[company['output_metric']]
        latest = max((o for o in data['observations'] if o['metric'] == om['id'] and not o.get('superseded_by') and o['status'] in ('observation', 'estimate')), key=lambda o: (o['year'], o['period']), default=None)
        if latest:
            output = (f'<section class="company-output"><div class="eyebrow muted">OUTPUT</div><div class="layer-value">{e(number(latest))} <small>{e(om["unit"])}</small></div>'
                      f'<p class="layer-label">{e(om["title"])} · {e(latest["period"])} · {attribution_label(latest, om, sources[latest["source"]], COMPANIES.get(om.get("company")))} · <a href="{link_url(sources[latest["source"]]["url"])}">{e(sources[latest["source"]]["publisher"])} ↗</a></p>'
                      f'<p class="chart-footnote">{e(om["scope"])}</p></section>')
    financials = (f'<h2>Revenue history &amp; outlook</h2><p>{e(metric["scope"])} · {e(metric["unit"])}</p><div class="table-scroll"><table><thead><tr><th>Period</th><th>Revenue</th><th>Classification</th><th>Published</th><th>Source</th></tr></thead><tbody>{rows}</tbody></table></div>' if records else '<h2>Revenue coverage</h2><p>No reviewed revenue series yet. Missing data does not mean zero revenue. Funding and valuation are not substitutes.</p>')
    return (f'<section class="page-hero" data-company="{e(company["id"])}"><a class="section-link" href="{base}companies/">← All companies</a><div class="eyebrow">THE BUILDERS / COMPANY RESEARCH</div><h1>{e(company["name"])}</h1><p>{e(company["role"])}</p></section><section class="panel">{output}{financials}</section>')
HOME_DESCRIPTION = ('Track energy, chips, infrastructure, models and applications worldwide, '
                    'with deeper U.S. coverage and a horizon of 2030 and beyond.')
LABELS = {
    'energy': ('Generate', 'Global data-center electricity demand (all workloads)', 'TWh / year'),
    'chips': ('Compute', 'Nvidia AI accelerators shipped, cumulative since 2022 (Epoch estimate)', 'accelerators'),
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


def layer_cards(data, base, config=None, policy=None):
    cards = []
    for layer in data['layers']:
        verb, label, unit = LABELS[layer['id']]
        slot = config['slots'][layer['id']] if config else None
        if slot:
            from render_editorial import selected, history
            record = selected(data, slot, policy)
            if slot['metric_id'] != layer['headline_metric']:
                metric = next(m for m in data['metrics'] if m['id'] == slot['metric_id'])
                label, unit = metric['title'], metric['unit']
        else:
            record = latest_headline(data, layer)
        if record:
            source = next(s for s in data['sources'] if s['id'] == record['source'])
            record_metric = next(m for m in data['metrics'] if m['id'] == record['metric'])
            display = record
            if record['metric'] == 'tsmc-cowos-wpm':
                display = dict(record, value=record['value'] / 1000,
                               upper=record['upper'] / 1000 if record['upper'] is not None else None)
            evidence = (f'<div class="layer-value">{e(number(display))}</div>'
                        f'<div class="metric-context"><span>{e(unit)}</span><span>{e(record["period"])}</span></div>'
                        f'<p class="layer-label">{e(label)}</p>'
                        f'<span class="headline-status">{attribution_label(record, record_metric, source, COMPANIES.get(record_metric.get("company")))}</span>'
                        f'<a class="headline-source" href="{link_url(source["url"])}">{e(source["publisher"])} ↗</a>'
                        + ('<p class="headline-note">Named model, dated price. Excludes tools, subscriptions and oversight.</p>'
                           if layer['id'] == 'models' else ''))
        else:
            evidence = (f'<div class="layer-value research-gap">Research gap</div>'
                        f'<p class="layer-label">{e(label)}</p><span class="headline-status">No headline observation</span>'
                        '<p class="headline-note">No reviewed outcome metric in the catalog yet. Adoption is not productivity.</p>')
        if slot:
            if slot['visualization'] == 'demoted':
                evidence = '<p class="headline-note">This featured indicator is under editorial reconsideration. Follow the layer for scoped evidence.</p>'
            else:
                evidence += history(data, slot, policy, base)
            for mid in slot['supporting']:
                metric = next(m for m in data['metrics'] if m['id'] == mid)
                from editorial import contract
                supporting_slot = dict(metric_id=mid, profile=contract(metric,policy)['profile'], visualization='history', pin=None, supporting=[])
                supporting_record = selected(data,supporting_slot,policy)
                if supporting_record:
                    source = next(s for s in data['sources'] if s['id']==supporting_record['source'])
                    # Collapsed by default so a supporting series never makes one layer card taller than its neighbours;
                    # the figure stays visible in the summary, the scope, source and history open on demand.
                    evidence += (f'<details class="headline-support"><summary><span class="support-label">Supporting context</span> {e(metric["title"])}'
                                 f'<strong>{e(number(supporting_record))} {e(metric["unit"])} · {e(supporting_record["period"])} · {attribution_label(supporting_record, metric, source, COMPANIES.get(metric.get("company")))}</strong></summary>'
                                 f'<p>{e(metric["scope"])}</p><a href="{link_url(source["url"])}">{e(source["publisher"])}</a>'
                                 + history(data,supporting_slot,policy,base)+'</details>')
        marker = f' data-observation="{e(record["id"])}"' if record else ''
        cards.append(f'<article class="layer-card" style="--accent:{e(layer["color"])}" data-layer="{e(layer["id"])}"{marker}>'
                     f'<div class="layer-card-top"><span class="layer-verb">{verb}</span><span class="ordinal">LAYER {e(layer["number"])}</span></div>'
                     f'<h3><a href="{base}{e(layer["id"])}/">{e(layer["name"])}</a></h3>{evidence}'
                     f'<a class="layer-card-bottom" href="{base}{e(layer["id"])}/"><span>Explore {e(layer["name"].lower())}</span><span>↗</span></a></article>')
    return '<div class="layer-grid">' + ''.join(cards) + '</div>'


def home(data, base, config=None, policy=None):
    stack = (ROOT / 'site/partials/stack.html').read_text(encoding='utf-8').replace('{{BASE}}', base)
    from render_editorial import recent_changes, delivery_context
    reviewed = recent_changes(config, data, base) if config else ''
    delivery = delivery_context(config, data, base) if config else ''
    return f'''<section class="hero"><div class="hero-copy">
      <div class="eyebrow"><span class="dot"></span>A PUBLIC LEDGER OF THE AI BUILDOUT</div>
      <h1>A public record of<br><em>the AI buildout.</em></h1>
      <p class="hero-description">{HOME_DESCRIPTION}</p>
      <div class="hero-actions"><a class="button" href="#stack">Explore the stack <span>↓</span></a><a class="text-link" href="{base}ledger/">Read the ledger <span>↗</span></a></div>
      <div class="hero-meta"><span>Global perspective</span><span>U.S. in focus</span><span>2030 &amp; beyond</span></div>
      </div><div class="hero-art">{stack}<div class="art-caption"><span>Five connected layers. Evidence at every step.</span></div></div></section>
      <section class="section" id="stack"><div class="section-top"><div><div class="eyebrow muted">FIVE LAYERS. ONE CONNECTED PURPOSE.</div><h2>From power to useful work.</h2></div></div>
      <p class="stack-thesis"><a href="{base}energy/">Power</a> enables <a href="{base}chips/">chips</a> and <a href="{base}infrastructure/">AI factories</a>.<br><a href="{base}models/">Models</a> turn compute into capabilities; <a href="{base}applications/">applications</a> put them to <strong>useful work.</strong></p>
      {layer_cards(data, base, config, policy)}
      <p class="chart-footnote">Selected indicators, not an overall progress score. Each figure keeps its own scope, period and publisher. <a class="source-inline" href="{base}data/ledger.json">Inspect the raw ledger ↗</a></p></section>
      <aside class="reading-note homepage-reading"><strong>Pledged is not built.</strong><p>Announced ≠ financed ≠ under construction ≠ commissioned ≠ operating. Follow the evidence for each stage in the <a class="source-inline" href="{base}projects/">project tracker ↗</a>.</p></aside>
      {delivery}{reviewed}
      <aside class="claims-invitation"><div><div class="eyebrow">FROM INFRASTRUCTURE TO OUTCOMES</div><h2>What does the buildout deliver for communities?</h2><p>Follow the evidence from investment and activity to household bills, collected taxes, lasting jobs and useful work. Spending and adoption alone do not establish a benefit.</p><p>Explore AI and employment, skilled jobs, local taxes, water, power bills and clean energy—and what future projects need to demonstrate. Local benefits, public costs and uncertainty belong in the same assessment.</p><p><a href="{base}claims/#ai-employment">Is AI causing mass unemployment? Check the evidence.</a></p></div><a href="{base}claims/">Examine the evidence ↗</a></aside>
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
    session=r.get('latest_session')
    session_receipt='<li>Latest research session: no published session summary yet.</li>'
    if session:
        incomplete=(f' Recorded totals from {session["receipts_recorded"]} of {session["batches"]} batch receipts; missing receipts are not zero activity.'
                    if session['receipts_recorded']!=session['batches'] else '')
        session_receipt=(f'<li>Latest research session: {e(session["state"])} · started {e(stamp(session["started_at"]))} · '
                         f'{session["elapsed_seconds"]//60:,} minutes elapsed · {session["batches"]:,} batches ({session["failed_batches"]:,} failed). '
                         f'{session["documents_fetched"]:,} document fetches (includes repeats), {session["model_calls"]:,} model calls, '
                         f'{session["accepted"]:,} accepted monitoring records, {session["quarantined"]:,} quarantined proposals; '
                         f'{session["source_failures"]:,} source failures and {session["discovery_errors"]:,} discovery errors. '
                         f'Elapsed time includes waits and publication checks.{incomplete}</li>')
    return (f'<strong>Research runtime:</strong> {e(r["display_model"])} · {e(r["engine"])} · {e(r["hardware"])}<br>'
            f'<strong>Last run:</strong> {e(stamp(r["last_attempt"]))} · <strong>Status:</strong> {e(r["status"])} · '
            f'<strong>Last successful research:</strong> {e(stamp(r["last_success"]))}'
            '<details><summary>Runtime details &amp; provenance</summary><ul>'
            f'<li>Exact model: {e(r["model"])}</li><li>Schedule: {e(r["schedule"])}. Hardware configuration is owner-reported.</li>'
            f'<li>Initial curated dataset: {e(data["seed_date"])}. Automated records are labeled individually.</li>{session_receipt}</ul></details>')
