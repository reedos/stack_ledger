"""Static, accessible homepage context. Reviewed configuration only; no private queue access."""
from datetime import datetime, timezone
from html import escape as e

import editorial as ed


def as_of(data):
    # A deterministic accepted-data watermark, not the wall clock during a build.
    stamps = [o['retrieved_at'] for o in data['observations']]
    stamps += [r['finished_at'] for r in data['runs']]
    return max(stamps, default=data['seed_date']+'T00:00:00Z')


def selected(data, slot, policy):
    m = next(m for m in data['metrics'] if m['id'] == slot['metric_id'])
    sources = {s['id']: s for s in data['sources']}
    f = ed.series_features(m, data['observations'], sources, policy, as_of(data))
    oid = slot['pin'] if slot['pin'] in f['historical_ids'] else (None if slot['pin'] else f['latest_id'])
    return next((o for o in data['observations'] if o['id'] == oid), None)


def history(data, slot, policy, base):
    from render import number, link_url, STATUSES
    if slot['visualization'] != 'history':
        return ''
    m = next(m for m in data['metrics'] if m['id'] == slot['metric_id'])
    sources = {s['id']: s for s in data['sources']}
    f = ed.series_features(m, data['observations'], sources, policy, as_of(data))
    if not f['chart_ready']:
        return '<p class="headline-note">Comparable history needs further review. Open the layer for separate historical estimates and outlooks.</p>'
    obs = {o['id']: o for o in data['observations']}
    ids = [i for segment in f['segments'] if segment['chart_ready'] for i in segment['observation_ids']]
    rows = sorted((obs[i] for i in ids), key=lambda o: ed.period_bounds(o)[1])
    if slot['pin']:
        rows = [o for o in rows if ed.period_bounds(o)[1] <= ed.period_bounds(obs[slot['pin']])[1]]
    if len(rows) < 2:
        return ''
    lo = ed.period_bounds(rows[0])[0].toordinal()
    hi = ed.period_bounds(rows[-1])[1].toordinal()
    ceiling = max(o.get('upper') or o['value'] for o in rows)
    floor = min(0, min(o['value'] for o in rows))
    scale = 1000 if m['id'] == 'tsmc-cowos-wpm' else 1
    chart_unit = 'thousand wafers / month' if scale == 1000 else m['unit']
    x = lambda o: 18+184*(ed.period_bounds(o)[1].toordinal()-lo)/max(1, hi-lo)
    y = lambda v: 86-64*(v-floor)/max(1, ceiling-floor)
    title = f'{m["title"]}: historical checkpoints, {chart_unit}'
    svg = [f'<svg viewBox="0 0 220 120" role="img" aria-label="{e(title, quote=True)}"><title>{e(title)}</title>',
           '<path d="M18 16V86H202" fill="none" stroke="currentColor" opacity=".3"/>',
           f'<text x="18" y="12">{ceiling/scale:,.0f}</text><text x="3" y="90">{floor/scale:,.0f}</text>']
    for o in rows:
        px, py = x(o), y(o['value'])
        begin, end, precision = ed.period_bounds(o)
        if precision == 'month':
            left = 18+184*(begin.toordinal()-lo)/max(1,hi-lo)
            svg.append(f'<path d="M{left:.2f} {py:.2f}H{px:.2f}" stroke="currentColor" opacity=".5"/>')
        # Checkpoints/ranges on a true time axis, no inferred between-observation ramp.
        if o['upper'] is not None:
            uy = y(o['upper'])
            svg.append(f'<path d="M{px:.2f} {uy:.2f}V{py:.2f}m-4 0h8M{px-4:.2f} {uy:.2f}h8" stroke="currentColor" stroke-width="3" fill="none"/>')
        elif o['precision'] in {'gt', 'lt'}:
            svg.append(f'<path d="M{px-4:.2f} {py+4:.2f}l4 -8 4 8Z" fill="none" stroke="currentColor"/>')
        else:
            svg.append(f'<circle cx="{px:.2f}" cy="{py:.2f}" r="4" fill="currentColor"/>')
    svg.append(f'<text x="18" y="107">{rows[0]["year"]}</text><text x="202" y="107" text-anchor="end">{rows[-1]["year"]}</text></svg>')
    table = ''.join(f'<tr><th scope="row">{e(o["period"])}</th><td>{e(number(o))}</td><td>{STATUSES[o["status"]]}</td><td><a href="{link_url(sources[o["source"]]["url"])}">{e(sources[o["source"]]["publisher"])}</a></td></tr>' for o in rows)
    qualification = ('Ranges are historical estimates; no annual ramp is inferred.' if any(o['upper'] is not None for o in rows)
                     else 'Reported checkpoints; triangle marks a bound, horizontal mark the disclosed month. Service footprint changes.' if m['id'] == 'waymo-paid-weekly'
                     else 'Historical checkpoints only. No values are interpolated.')
    return (f'<figure class="headline-history">{"".join(svg)}<figcaption>{e(chart_unit)}. {e(qualification)}</figcaption></figure>'
            f'<details class="headline-history-data"><summary>History &amp; sources</summary><p>{e(m["unit"])}. {e(m["scope"])}</p>'
            f'<div class="table-scroll"><table><caption>{e(m["title"])}</caption><thead><tr><th>Period</th><th>Value</th><th>Evidence</th><th>Source</th></tr></thead><tbody>{table}</tbody></table></div></details>')


def recent_changes(config, ledger, base, at=None):
    from render import number, link_url, STATUSES
    # An editorial approval may be newer than the last research receipt. It must
    # become visible without fabricating a research run or waiting for inference.
    cutoff = ed.instant(at or max(as_of(ledger), config['reviewed_at']))
    items = [i for i in config['recent_changes'] if 0 <= (cutoff-ed.instant(i['reviewed_at'])).days <= config['recent_window_days']]
    items.sort(key=lambda i: (not i['pinned'], -i['priority'], -ed.instant(i['reviewed_at']).timestamp(), i['id']))
    # First pass favors layer diversity; second fills remaining slots.
    chosen, layers, keys = [], set(), set()
    for diversify in [True, False]:
        for item in items:
            if len(chosen) >= config['recent_limit']:
                break
            if item['event_key'] in keys or diversify and item['layer'] in layers:
                continue
            chosen.append(item); layers.add(item['layer']); keys.add(item['event_key'])
    content = '<p class="empty">No developments have been approved for this editorial window. Accepted research remains available in the ledger; it is not automatically promoted here.</p>'
    if chosen:
        sources = {s['id']: s for s in ledger['sources']}
        obs = {o['id']: o for o in ledger['observations']}
        cards = []
        for item in chosen:
            values = ''
            for name in ['before_id', 'after_id']:
                if item[name]:
                    o = obs[item[name]]
                    values += f'<p>{"Previous" if name == "before_id" else "New"}: {e(number(o))} · {e(o["period"])} · {STATUSES[o["status"]]}</p>'
            old = 'Historical event, newly reviewed. ' if (ed.instant(item['reviewed_at']).date()-datetime.fromisoformat(item['event_date']).date()).days > config['recent_window_days'] else ''
            links = ' · '.join(f'<a class="source-inline" href="{link_url(sources[s]["url"])}">{e(sources[s]["publisher"])}</a>' for s in item['source_ids'])
            cards.append(f'<article class="panel"><span class="eyebrow">{e(item["layer"])} · {e(item["kind"])}</span><h3>{e(item["title"])}</h3><p>{e(item["what_changed"])}</p>{values}<p><strong>Why it matters:</strong> {e(item["significance"])}</p><p>{e(item["scope"])}</p><p class="chart-footnote">{old}Event: {e(item["event_date"])} · Reviewed: {e(item["reviewed_at"][:10])}</p>{links}</article>')
        content = '<div class="reviewed-change-grid">'+''.join(cards)+'</div>'
    return f'<section class="section" id="recent-changes" aria-labelledby="recent-changes-title"><div class="eyebrow muted">REVIEWED DEVELOPMENTS</div><h2 id="recent-changes-title">What changed recently?</h2>{content}<a class="section-link" href="{base}ledger/">Explore the research ledger ↗</a></section>'


def delivery_context(config, data, base):
    from render import number, link_url, STATUSES
    result = ed.delivery_gate(config['delivery_accounting'], data)
    if not result['eligible']:
        return ''  # Existing explanation and tracker link remain intact.
    a = config['delivery_accounting']
    observations = {o['id']:o for o in data['observations']}
    sources = {s['id']:s for s in data['sources']}
    rows = []
    for p in a['phases']:
        o = observations.get(p['observation_id'])
        value = e(number(o))+' · '+STATUSES[o['status']] if o else 'Unknown; not zero'
        links = ' · '.join(f'<a href="{link_url(sources[s]["url"])}">{e(sources[s]["publisher"])}</a>' for s in p['source_ids'])
        rows.append(f'<tr><th scope="row">{e(p["id"])}</th><td>{e(p["state"])}</td><td>{value}</td><td>{links}</td></tr>')
    return f'<section class="panel"><h2>Delivery in the tracked cohort</h2><p>{e(a["scope"])} · {e(a["as_of"])} · {e(a["unit"])}. Disjoint present-state accounting.</p><div class="table-scroll"><table><caption>Phase evidence; no conversion rate inferred</caption><thead><tr><th>Phase</th><th>State</th><th>Quantity ({e(a["unit"])})</th><th>Evidence</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div><p>Exclusions: {e(a["exclusions"])}</p><a href="{base}projects/">Project tracker</a></section>'
