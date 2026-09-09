"""Static, source-linked graphics from the existing accepted catalogs."""
from datetime import date
from html import escape as e
import json
from collections import Counter
from decimal import Decimal
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
COLORS=['#c5f277','#79ced7','#c1a1f5','#f0c478','#f4939c']
DEVELOPER_COLORS=['#70c9ff','#f09b68','#cc9cf5','#f4d06f','#65d6ad','#ff8ea1','#9aa9ff','#c8df75','#c5a68d','#75d5dc','#f49cce','#a8b8c4','#ffa95e','#a4d89a','#d8b5f0','#e9c2ac']

def capital_totals(series):
    """Sum a fixed covered cohort only in years with a record for every member."""
    complete=set.intersection(*(set(o['year'] for o in rows) for _,rows in series))
    return [(year,float(sum((Decimal(str(next(o['value'] for o in rows if o['year']==year))) for _,rows in series),Decimal(0)))) for year in sorted(complete)]

def capital_projections(ledger,config):
    histories={r['company']:{o['year']:o for o in records(ledger,r['history_metric'])} for r in config['companies']}
    forecasts={r['company']:{o['year']:o for o in records(ledger,r['guidance_metric'])} if r['guidance_metric'] else {} for r in config['companies']}
    years=sorted({year for rows in forecasts.values() for year in rows})
    result=[]
    for year in years:
        rows=[(r,forecasts[r['company']].get(year) or histories[r['company']].get(year)) for r in config['companies']]
        if all(o is not None for _,o in rows):result.append((year,rows))
    return result

def developer_palette(c):
    counts=Counter(r['organization'] for r in c['rows'])
    return {name:DEVELOPER_COLORS[i%len(DEVELOPER_COLORS)] for i,name in enumerate(sorted(counts,key=lambda n:(-counts[n],n)))}

def default_models(c):
    counts=Counter(r['organization'] for r in c['rows'])
    return [r for r in c['rows'] if counts[r['organization']]>3 and r['organization']!='Not listed by Epoch']

def link(sources,id):
    s=sources[id]
    return f'<a class="source-inline" href="{e(s["url"],quote=True)}" target="_blank" rel="noopener noreferrer">{e(s["publisher"])} · {e(s["published"] or "publication date unlisted")} ↗</a>'

def records(ledger,id):
    return sorted([o for o in ledger['observations'] if o['metric']==id and not o.get('superseded_by')],key=lambda o:o['year'])

def svg_start(title,desc,view='0 0 640 320'):
    return f'<svg class="explorer-chart" viewBox="{view}" role="img" aria-label="{e(title,quote=True)}"><title>{e(title)}</title><desc>{e(desc)}</desc>'

def capital(ledger,x,base):
    if not x.get('capital'):return ''
    config=x['capital'];sources={s['id']:s for s in ledger['sources']};ms={m['id']:m for m in ledger['metrics']}
    series=[(row,records(ledger,row['history_metric'])) for row in config['companies']]
    projected=capital_projections(ledger,config)
    forecast_totals=[(year,float(sum(Decimal(str(o['value'])) for _,o in rows)),float(sum(Decimal(str(o['upper'] if o['upper'] is not None else o['value'])) for _,o in rows))) for year,rows in projected]
    archived=[(row,records(ledger,row['metric'])) for row in config.get('archived_forecast',{}).get('companies',[])]
    archive_totals=capital_totals(archived) if archived else []
    years=[o['year'] for _,rs in series for o in rs]+[year for year,_,_ in forecast_totals];lo,hi=min(years),max(years)
    totals=capital_totals(series)
    top=max(50,((int(max([o['value'] for _,rs in series for o in rs]+[value for _,value in totals]+[high for _,_,high in forecast_totals]))//50)+1)*50)
    xp=lambda year:48+(year-lo)/max(1,hi-lo)*560
    yp=lambda value:260-value/top*220
    svg=svg_start('Global hyperscaler cash capital spending','Company spending and a simple total of all five covered companies. Total uses fiscal years ending in the labeled year, not aligned calendar years. USD billion.')
    for v in range(0,top+1,100 if top>300 else 50):svg+=f'<path class="explorer-grid" d="M48 {yp(v):.2f}H608"/><text x="36" y="{yp(v)+4:.2f}" text-anchor="end">{v}</text>'
    for year in sorted(set(years)):
        if hi-lo<=6 or (year-lo)%2==0 or year==hi:svg+=f'<text x="{xp(year):.2f}" y="285" text-anchor="middle">{year}</text>'
    legend='';table=''
    for i,(row,rs) in enumerate(series):
        color=COLORS[i%len(COLORS)]
        # Adjacent annual observations only; gaps do not become fabricated histories.
        for a,b in zip(rs,rs[1:]):
            if b['year']==a['year']+1:svg+=f'<path d="M{xp(a["year"]):.2f} {yp(a["value"]):.2f}L{xp(b["year"]):.2f} {yp(b["value"]):.2f}" fill="none" stroke="{color}" stroke-width="2.5"/>'
        for o in rs:
            label=f'{row["name"]}, {o["period"]}: ${o["value"]:g} billion, reported cash expenditure'
            svg+=f'<circle cx="{xp(o["year"]):.2f}" cy="{yp(o["value"]):.2f}" r="4" fill="{color}"><title>{e(label)}</title></circle>'
            table+=f'<tr><th scope="row">{e(row["name"])}</th><td>{e(o["period"])}</td><td>{o["value"]:g}</td><td>Reported cash expenditure</td><td>{link(sources,o["source"])}<br>{e(o["note"])}</td></tr>'
        legend+=f'<span style="--series:{color}"><i></i>{e(row["name"])} <small>FY ends {e(row["year_end"])}</small></span>'
    for a,b in zip(totals,totals[1:]):
        if b[0]==a[0]+1:svg+=f'<path class="capital-total" d="M{xp(a[0]):.2f} {yp(a[1]):.2f}L{xp(b[0]):.2f} {yp(b[1]):.2f}" fill="none" stroke="#ffffff" stroke-width="3.5"/>'
    for year,value in totals:
        svg+=f'<circle class="capital-total" cx="{xp(year):.2f}" cy="{yp(value):.2f}" r="5" fill="#fff"><title>Total · FY{year}: ${value:g} billion · all five companies</title></circle>'
        components=[(row,next(o for o in rs if o['year']==year)) for row,rs in series]
        table+=f'<tr><th scope="row">Total · all five</th><td>Fiscal years ended {year}</td><td>{value:g}</td><td>Derived sum of reported actuals</td><td>'+ ' + '.join(f'{e(row["name"])}: {o["value"]:g} · {link(sources,o["source"])}' for row,o in components)+'</td></tr>'
    legend+='<span style="--series:#ffffff"><i></i><strong>Total · all five</strong><small>Fiscal-year sum; differing end dates</small></span>'
    previous={year:value for year,value in totals}
    for year,value,high in forecast_totals:
        if year-1 in previous:svg+=f'<path d="M{xp(year-1):.2f} {yp(previous[year-1]):.2f}L{xp(year):.2f} {yp(value):.2f}" stroke="#fff" stroke-width="3" stroke-dasharray="7 5" fill="none"/>'
        svg+=f'<path class="capital-forecast-range" d="M{xp(year):.2f} {yp(value):.2f}V{yp(high):.2f}" stroke="#fff" stroke-width="6"><title>{year} total outlook: {value:g}–{high:g} USD billion; mixed fiscal/calendar basis</title></path><circle cx="{xp(year):.2f}" cy="{yp(value):.2f}" r="5" fill="#101a14" stroke="#fff" stroke-width="2"/>'
        previous[year]=value
    for year,rows in projected:
        for row,o in rows:
            if o['status']!='forecast':continue
            prior=next((a for a in records(ledger,row['history_metric']) if a['year']==year-1),None)
            color=COLORS[config['companies'].index(row)%len(COLORS)]
            if prior:svg+=f'<path d="M{xp(year-1):.2f} {yp(prior["value"]):.2f}L{xp(year):.2f} {yp(o["value"]):.2f}" stroke="{color}" stroke-width="2" stroke-dasharray="5 5" fill="none"/>'
            svg+=f'<circle cx="{xp(year):.2f}" cy="{yp(o["value"]):.2f}" r="4" fill="#101a14" stroke="{color}" stroke-width="2"><title>{e(row["name"])} · {e(o["period"])} · forecast {o["value"]:g} USD billion</title></circle>'
    if forecast_totals:legend+='<span style="--series:#fff"><i></i>Dashed / hollow: latest outlook<small>Mixed actual/guidance; fiscal/calendar bases differ</small></span>'
    if archive_totals:
        for year,value in archive_totals:
            table+=f'<tr><th scope="row">Older forecast total · all five</th><td>CY{year}</td><td>{value:g}</td><td>September 2025 consensus forecast</td><td>{link(sources,config["archived_forecast"]["source"])} · Sum of the five published rounded company values.</td></tr>'
        names={r['company']:r['name'] for r in config['companies']}
        for row,rs in archived:
            for o in rs:table+=f'<tr><th scope="row">{e(names[row["company"]])} · older forecast</th><td>{e(o["period"])}</td><td>≈{o["value"]:g}</td><td>Forecast</td><td>{link(sources,o["source"])} · {e(o["note"])}</td></tr>'
    svg+='</svg>'
    outlook=[]
    for row in config['companies']:
        rs=records(ledger,row['guidance_metric']) if row['guidance_metric'] else []
        if rs:outlook.append((row,rs[-1],True))
        else:
            actual=records(ledger,row['history_metric'])[-1]
            outlook.append((row,actual,False))
    ceiling=max(o['upper'] or o['value'] for _,o,_ in outlook)*1.08
    low=sum(Decimal(str(o['value'])) for _,o,_ in outlook);high=sum(Decimal(str(o['upper'] if o['upper'] is not None else o['value'])) for _,o,_ in outlook)
    bars=f'<div class="capital-sum"><span>Total · all five displayed amounts</span><strong>≈${low:,.1f}–${high:,.1f}B</strong><p>Simple sum of these bars: mixes calendar-year guidance and Oracle’s fiscal-year actual. This is not a uniform calendar-year forecast.</p></div>'
    for row,o,forecast in sorted(outlook,key=lambda item:item[1]['value'],reverse=True):
        label=f'{o["value"]:g}–{o["upper"]:g}' if o['upper'] is not None else f'≈{o["value"]:g}' if o['precision']=='approx' else f'{o["value"]:g}'
        bars+=f'<div class="capital-bar-row"><div><strong>{e(row["name"])}</strong><span>${label}B</span></div><div class="capital-bar-track" role="img" aria-label="{e(row["name"]+": "+label+" USD billion · "+o["period"],quote=True)}"><span class="capital-bar {"guidance" if forecast else "actual"}" style="width:{o["value"]/ceiling*100:.3f}%"></span>'
        if o['upper'] is not None:bars+=f'<span class="capital-range" style="left:{o["value"]/ceiling*100:.3f}%;width:{(o["upper"]-o["value"])/ceiling*100:.3f}%"></span>'
        bars+=f'</div><small>{e(o["period"])} · {"Forecast" if forecast else "Reported actual"} · {link(sources,o["source"])}</small></div>'
        if forecast:table+=f'<tr><th scope="row">{e(row["name"])}</th><td>{e(o["period"])}</td><td>{label}</td><td>Forecast / company guidance</td><td>{link(sources,o["source"])}<br>{e(o["note"])}</td></tr>'
    scopes=''.join(f'<li><strong>{e(row["name"])}</strong>: {e(ms[row["history_metric"]]["scope"])}'+(f' Guidance: {e(ms[row["guidance_metric"]]["scope"])}' if row['guidance_metric'] else '')+'</li>' for row in config['companies'])
    return f'''<section id="capital-buildout" class="section explorer-section" data-explorer-snapshot><div class="section-top"><div><div class="eyebrow muted">CAPITAL → INFRASTRUCTURE</div><h2>The investment taking physical shape.</h2></div><a class="section-link" href="{base}infrastructure/#capital-buildout">Explore infrastructure ↗</a></div><p class="section-intro">Building AI factories takes sustained investment in land, power, servers and networks. Follow the capital behind that buildout, with worldwide company spending kept distinct from AI-only or U.S. spending.</p><div class="capital-layout"><article class="explorer-panel"><div class="eyebrow">HISTORY + FORECASTS · USD BILLION</div><h3>Global hyperscaler capital spending</h3><p class="explorer-subtitle">Reported cash PP&amp;E + dated outlooks · {lo}–{hi}</p>{svg}<div class="capital-legend">{legend}</div><p class="chart-footnote">Total sums all five companies by fiscal year ending in the labeled year. Fiscal dates and accounting bases differ. Incomplete years have no total; missing values are never zero. Solid lines show reported spending; dashed lines show the latest outlook. Older forecasts remain in the evidence table below.</p></article><article class="explorer-panel"><div class="eyebrow">SPENDING OUTLOOK · USD BILLION</div><h3>Latest spending &amp; guidance</h3><p class="explorer-subtitle">Hatched = forecast · solid = actual · bars start at zero</p>{bars}<p class="chart-footnote">Oracle is a completed fiscal year; the other bars are calendar-year guidance. Definitions differ, including lease treatment. Amazon and Alphabet outlooks are attributed to AP earnings reporting.</p></article></div><details class="explorer-evidence"><summary>Data, accounting differences &amp; sources</summary><p>{e(config['scope'])}</p><ul>{scopes}</ul><div class="table-scroll"><table><caption>Capital spending · USD billion</caption><thead><tr><th>Company</th><th>Period</th><th>USD billion</th><th>Classification</th><th>Source &amp; scope</th></tr></thead><tbody>{table}</tbody></table></div><p>Reviewed {e(config['reviewed_at'][:10])}. Values retain source precision. No inflation adjustment.</p><ul>{''.join('<li>'+e(g)+'</li>' for g in config['gaps'])}</ul><a class="source-inline" href="{base}data/ledger.json">Download accepted observations ↗</a></details></section>'''

def capability_svg(c,compact=False):
    rs=default_models(c);palette=developer_palette(c);start=min(date.fromisoformat(r['released']).toordinal() for r in c['rows']);end=max(date.fromisoformat(r['released']).toordinal() for r in c['rows'])
    floor=(int(min(r['score'] for r in c['rows']))//20)*20;ceiling=((int(max(r['high'] or r['score'] for r in c['rows']))//20)+1)*20
    xp=lambda day:48+(date.fromisoformat(day).toordinal()-start)/max(1,end-start)*550
    yp=lambda value:260-(value-floor)/max(1,ceiling-floor)*220
    svg=svg_start('Epoch Capabilities Index over model release dates','Published model scores, not productivity or percent intelligence. The frontier follows the highest score available by release date.')
    svg=svg.replace('<svg ',f'<svg data-start="{start}" data-end="{end}" data-floor="{floor}" data-ceiling="{ceiling}" ')
    for v in range(floor,ceiling+1,20):svg+=f'<path class="explorer-grid" d="M48 {yp(v):.2f}H608"/><text x="36" y="{yp(v)+4:.2f}" text-anchor="end">{v}</text>'
    for year in range(date.fromordinal(start).year,date.fromordinal(end).year+1):
        day=max(date(year,1,1).toordinal(),start);px=48+(day-start)/max(1,end-start)*550
        svg+=f'<text x="{px:.2f}" y="286" text-anchor="middle">{year}</text>'
    frontier=[];best=float('-inf')
    for r in sorted(rs,key=lambda r:(r['released'],-r['score'])):
        if r['score']>best:frontier.append(r);best=r['score']
    path=''
    for i,r in enumerate(frontier):path+=f'{"M" if i==0 else "H"}{xp(r["released"]):.2f}'+(f' {yp(r["score"]):.2f}' if i==0 else f'V{yp(r["score"]):.2f}')
    svg+=f'<path class="eci-frontier" d="{path}" fill="none" stroke="#c5f277" stroke-width="2"/>'
    for r in c['rows']:
        color=palette[r['organization']]
        interval=f'; 90% interval {r["low"]:g}–{r["high"]:g}' if r['low'] is not None else '; interval not supplied for this anchor'
        svg+=f'<circle style="{"" if r in rs else "display:none"}" class="eci-point" data-model="{r["id"]}" cx="{xp(r["released"]):.2f}" cy="{yp(r["score"]):.2f}" r="{2 if compact else 2.4}" fill="{color}" opacity=".7"><title>{e(r["name"])} · {r["released"]} · ECI {r["score"]:g}{interval}</title></circle>'
    return svg+'</svg>'

def capabilities(ledger,x,base):
    if not x.get('capabilities'):return ''
    c=x['capabilities'];sources={s['id']:s for s in ledger['sources']}
    rows=''.join(f'<tr data-model="{r["id"]}"><th scope="row">{e(r["name"])}</th><td>{e(r["organization"])}</td><td>{e(r["country"])}</td><td>{r["released"]}</td><td>{r["score"]:g}</td><td>{str(r["low"])+"–"+str(r["high"]) if r["low"] is not None else "Anchor; interval not supplied"}</td><td>{e(r["access"])}</td></tr>' for r in sorted(c['rows'],key=lambda r:-r['score']))
    return f'''<section id="model-capabilities" class="section explorer-section" data-explorer-snapshot><div class="section-top"><div><div class="eyebrow muted">MODELS / CAPABILITY THROUGH TIME</div><h2>A broader frontier of capability.</h2></div><a class="section-link" href="https://epoch.ai/eci">Explore Epoch AI ↗</a></div><p class="section-intro">Epoch’s Capabilities Index brings multiple benchmarks onto a common scale. Follow model releases across organizations and open- or closed-weight availability.</p><div class="explorer-panel"><div class="explorer-controls" data-enhanced-controls hidden><label>Color by<select id="eci-color"><option value="organization">Model developer</option><option value="country">Country of organization</option><option value="access">Weight availability</option></select></label><label>Find models or developers<input id="eci-search" type="search" placeholder="Search names…"></label><label>Availability<select id="eci-access"><option value="all">All models</option><option>Open weights</option><option>Closed weights</option><option>Other</option></select></label><label class="explorer-check"><input id="eci-small" type="checkbox">Include developers with ≤3 models and unlisted</label><label class="explorer-check"><input id="eci-frontier-only" type="checkbox">Frontier only</label></div><p class="explorer-subtitle">ECI points · model release date · all scores from one dataset snapshot</p><div id="eci-plot">{capability_svg(c)}</div><div id="eci-legend" class="eci-legend" aria-label="Toggle chart groups">{''.join(f'<span style="--series:{color}"><i></i>{e(name)}</span>' for name,color in developer_palette(c).items() if name in {r['organization'] for r in default_models(c)})}</div><div class="eci-actions" data-enhanced-controls hidden><button id="eci-show-all" type="button">Show all groups</button><button id="eci-hide-all" type="button">Hide all groups</button><button id="eci-reset" type="button">Reset view</button></div><p id="eci-filter-summary" class="chart-footnote" aria-live="polite">Default: developers with more than three models; unlisted developers hidden. All records remain in the evidence table.</p><div class="explorer-controls" data-enhanced-controls hidden><label>Inspect a model<select id="eci-model" aria-describedby="eci-inspect-hint"><option value="">No model selected</option></select></label></div><p id="eci-inspect-hint" class="chart-footnote">Select a point or choose a model to inspect its score and uncertainty.</p><div id="eci-selection" class="explorer-selection" aria-live="polite" hidden></div><p class="chart-footnote">ECI is an index, not a percentage or a direct measure of reliable work. The step line is the best score by release date within the selected group, not a forecast. No future capability is extrapolated.</p></div><details class="explorer-evidence"><summary>Model scores, uncertainty &amp; methodology</summary><p>Source: {link(sources,c['source'])} · {link(sources,c['method_source'])}. Retrieved {c['retrieved_at'][:10]}. Data © Epoch AI and contributors, reused with attribution. 90% confidence intervals come from the same download; two calibration anchors have no supplied interval.</p><p>Country comes from Epoch’s “Country (of organization)” field; it is not the training location or the nationality of every contributor. Unknown values remain unlisted. Developer labels retain Epoch’s attribution, including collaborations. Historical scores can change when Epoch refits its index. This page uses one complete snapshot rather than combining vintages. Benchmark coverage and developer-reported results can affect comparability; overlapping intervals do not establish a reliable ranking. Open weights do not necessarily mean unrestricted open source.</p><div class="table-scroll"><table><caption>Epoch Capabilities Index · reviewed snapshot</caption><thead><tr><th>Model</th><th>Developer</th><th>Country of organization</th><th>Release date</th><th>ECI</th><th>90% interval</th><th>Availability</th></tr></thead><tbody id="eci-table">{rows}</tbody></table></div><p><a class="source-inline" href="{base}data/expansion.json">Download reviewed model snapshot ↗</a> · <a class="source-inline" href="https://epoch.ai/benchmarks/use-this-data">Dataset licensing &amp; original authors ↗</a></p></details></section>'''

def map_records(delivery,ecosystem=None):
    result=[]
    for p in delivery['projects']:
        if p.get('map_locations'):
            result.extend({**p,'map_location':g['location'],'stage':g['stage'],'map_source':g['source'],'map_note':g['note']} for g in p['map_locations'])
        elif p.get('map_location'):result.append(p)
    if ecosystem:
        for c in ecosystem['companies']:
            result.extend({'id':c['id'],'name':o['name'],'layer':'models','stage':'office','office_kind':o['kind'],'map_location':o['location'],'map_source':o['source'],'map_note':o['note']} for o in c.get('map_offices',[]))
    return result

def map_phase(stage):
    if stage=='status-unverified':return 'unverified'
    if stage in {'office','operating','pilot','delayed'}:return stage
    return 'planned' if stage in {'announced','permitting','site-selected'} else 'delivery'

def map_symbol(ps,colors,r):
    segments=Counter((p['layer'],map_phase(p['stage'])) for p in ps);angle=-math.pi/2
    svg=f'<circle class="map-core" r="{r}" fill="#101d18"/>'
    for (layer,phase),count in segments.items():
        span=count/len(ps)*math.pi*2;gap=.045 if len(segments)>1 else 0;a=angle+gap;b=angle+span-gap;angle+=span
        attrs=f'class="map-segment phase-{phase}" stroke="{colors[layer]}" stroke-width="{r/4}" fill="none"'
        if len(segments)==1:svg+=f'<circle r="{r*.88}" {attrs}/>'
        else:svg+=f'<path d="M{math.cos(a)*r*.88} {math.sin(a)*r*.88} A{r*.88} {r*.88} 0 {int(span>math.pi)} 1 {math.cos(b)*r*.88} {math.sin(b)*r*.88}" {attrs}/>'
        if len(ps)==1:
            if phase=='office':svg+=f'<path class="map-office-glyph" d="M0 {-r*.52}L{r*.52} 0 0 {r*.52} {-r*.52} 0Z" fill="{colors[layer]}"/>'
            else:svg+=f'<circle class="map-stage-fill phase-{phase}" r="{r*.6}" fill="{colors[layer]}"/>'
    if len(ps)>1:svg+=f'<text text-anchor="middle" dy=".35em" style="font-size:{r*.9}px">{len(ps)}</text>'
    return svg

def map_svg(delivery,ledger,compact=False):
    basemap=json.loads((ROOT/'site/data/map-basemap.json').read_text(encoding='utf-8'))
    ecosystem=json.loads((ROOT/'site/data/ecosystem.json').read_text(encoding='utf-8'))
    colors={l['id']:l['color'] for l in ledger['layers']}
    svg=svg_start('Mapped projects and model developer offices','City and county orientation points. Layer colors remain visible in shared markers. Planned locations are outlined. Offices are separate from projects.','155 108 200 95')
    svg=svg.replace('class="explorer-chart"','class="explorer-chart project-map-svg"')
    svg+='<g class="map-land">'+''.join(f'<path d="{p}"/>' for p in basemap['paths'])+'</g><g class="map-points">'
    groups={}
    for p in map_records(delivery,ecosystem):
        g=p['map_location'];groups.setdefault((g['latitude'],g['longitude']),[]).append(p)
    for (lat,lon),ps in groups.items():
        title=ps[0]['map_location']['label']+' · '+str(len(ps))+' mapped records'
        svg+=f'<g transform="translate({(lon+180)*3:.4f} {(90-lat)*3:.4f})"><title>{e(title)}</title>{map_symbol(ps,colors,min(3.6,1.15*math.sqrt(len(ps))))}</g>'
    return svg+'</g></svg>'

def project_map(delivery,ledger,base):
    ecosystem=json.loads((ROOT/'site/data/ecosystem.json').read_text(encoding='utf-8'));points=map_records(delivery,ecosystem)
    count=sum(bool(p.get('map_location') or p.get('map_locations')) for p in delivery['projects']);sources={s['id']:s for s in ledger['sources']}
    rows=''
    for p in points:
        g=p['map_location'];source=p.get('map_source',p.get('milestones',[{}])[-1].get('source'))
        status=p.get('office_kind',p['stage']).replace('-',' ')
        rows+=f'<tr><th scope="row">{e(p["name"])}</th><td>{e(g["label"])}</td><td>{e(status)}</td><td>{e(g["precision"])}</td><td>{link(sources,g["source"])} · {e(g["source_key"])}<br>{link(sources,source)}<br>{e(p.get("map_note","Project disclosure establishes the locality; coordinates provide orientation."))}</td></tr>'
    legend=''.join(f'<span style="--series:{l["color"]}"><i></i>{e(l["name"])}</span>' for l in ledger['layers'])
    stages='<div class="map-stage-legend" aria-label="Marker styles"><span><i class="sample-operating"></i>Operating</span><span><i class="sample-delivery"></i>Buildout / partial operation</span><span><i class="sample-planned"></i>Planned / permitting</span><span><i class="sample-pilot"></i>Pilot</span><span><i class="sample-delayed"></i>Delayed</span><span><i class="sample-unverified"></i>Stage unverified</span><span><i class="sample-office"></i>Developer HQ / office</span></div>'
    return f'''<section id="project-map" class="explorer-section" data-explorer-snapshot><div class="section-top"><div><div class="eyebrow">THE GEOGRAPHY OF THE BUILDOUT</div><h2>Investment has an address.</h2></div></div><p class="section-intro">Explore operating projects, the pipeline taking shape, and the people building models. Layer colors stay visible in shared markers; outlined markers distinguish planned locations. City and county points are useful orientation, even when a precise site or service boundary is unavailable.</p><div class="explorer-panel"><div class="explorer-controls" data-enhanced-controls hidden><label>Owner / developer<select id="map-company"><option value="all">All owners / developers</option></select></label><label>Location coverage<select id="map-coverage"><option value="all">All records</option><option value="mapped">Mapped records</option><option value="unmapped">Location not mapped</option></select></label><label class="explorer-check"><input id="map-offices" type="checkbox" checked>Model developer HQs / offices</label><div class="map-navigation" role="group" aria-label="Map navigation"><button type="button" id="map-us">U.S.</button><button type="button" id="map-world">World</button><button type="button" id="map-zoom-in" aria-label="Zoom map in">+</button><button type="button" id="map-zoom-out" aria-label="Zoom map out">−</button></div></div><div id="map-canvas">{map_svg(delivery,ledger)}</div><div class="capital-legend">{legend}</div>{stages}<p class="chart-footnote">Ring segments preserve every layer. Marker size grows with the number of mapped records (capped), not capacity, spending or jobs. Office diamonds are organizational context, not AI factories. A city-level point does not mean the project itself is tentative; its delivery stage is shown separately.</p><p id="map-count" class="chart-footnote" aria-live="polite">{count} of {len(delivery['projects'])} project records have reviewed locations. Developer offices are additional context and excluded from project totals.</p><div id="map-selection" class="explorer-selection" aria-live="polite">Select a marker to inspect its projects, stages and sources. Unmapped and distributed programs remain in the list below.</div></div><details class="explorer-evidence"><summary>Locations, precision &amp; map sources</summary><p>City/county points are not exact facilities. They come from the U.S. Census Bureau and GeoNames (CC BY 4.0). Project disclosures establish the locality. A program can have several locality markers without becoming several projects. Service cities are not service-area polygons, vehicle counts or evidence of uniform access. Headquarters, offices and registered offices retain their source’s classification and do not establish where models train.</p><p>Basemap: <a class="source-inline" href="https://www.naturalearthdata.com/about/terms-of-use/">Natural Earth, public domain</a>. Geographic boundaries are for orientation; map geometry is served locally.</p><div class="table-scroll"><table><caption>Reviewed project and developer locations</caption><thead><tr><th>Project / developer</th><th>Locality</th><th>Stage / office type</th><th>Precision</th><th>Evidence &amp; scope</th></tr></thead><tbody>{rows}</tbody></table></div><a class="source-inline" href="{base}data/delivery.json">Download project locations ↗</a> · <a class="source-inline" href="{base}data/ecosystem.json">Download developer offices ↗</a></details></section>'''

def previews(delivery,ledger,x,base):
    if not x.get('capabilities'):return ''
    count=sum(bool(p.get('map_location') or p.get('map_locations')) for p in delivery['projects'])
    return f'''<section id="buildout-explorers" class="section"><div class="explorer-preview-grid"><a class="explorer-preview" href="{base}projects/#project-map"><div class="eyebrow">WHERE IT IS HAPPENING</div><h3>The buildout, on the map.</h3>{map_svg(delivery,ledger,True)}<p>{count} mapped project records · power, chips and AI factories</p><strong>Explore the project map ↗</strong></a><a class="explorer-preview" href="{base}models/#model-capabilities"><div class="eyebrow">WHAT MODELS CAN DO</div><h3>Follow the capability frontier.</h3>{capability_svg(x['capabilities'],True)}<p>Epoch’s index · {len(x['capabilities']['rows'])} model scores · one reviewed snapshot</p><strong>Explore model capabilities ↗</strong></a></div></section>'''
