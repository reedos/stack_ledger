"""Static, source-linked graphics from the existing accepted catalogs."""
from datetime import date
from html import escape as e
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
COLORS=['#c5f277','#79ced7','#c1a1f5','#f0c478','#f4939c']

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
    years=[o['year'] for _,rs in series for o in rs];lo,hi=min(years),max(years)
    top=max(50,((int(max(o['value'] for _,rs in series for o in rs))//50)+1)*50)
    xp=lambda year:48+(year-lo)/max(1,hi-lo)*560
    yp=lambda value:260-value/top*220
    svg=svg_start('Global hyperscaler cash capital spending','Annual reported cash investment by company. Fiscal years have different end dates; no combined total. USD billion.')
    for v in range(0,top+1,50):svg+=f'<path class="explorer-grid" d="M48 {yp(v):.2f}H608"/><text x="36" y="{yp(v)+4:.2f}" text-anchor="end">{v}</text>'
    for year in sorted(set(years)):svg+=f'<text x="{xp(year):.2f}" y="285" text-anchor="middle">{year}</text>'
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
    svg+='</svg>'
    outlook=[]
    for row in config['companies']:
        rs=records(ledger,row['guidance_metric']) if row['guidance_metric'] else []
        if rs:outlook.append((row,rs[-1],True))
        else:
            actual=records(ledger,row['history_metric'])[-1]
            outlook.append((row,actual,False))
    ceiling=max(o['upper'] or o['value'] for _,o,_ in outlook)*1.08
    bars=''
    for row,o,forecast in sorted(outlook,key=lambda item:item[1]['value'],reverse=True):
        label=f'{o["value"]:g}–{o["upper"]:g}' if o['upper'] is not None else f'≈{o["value"]:g}' if o['precision']=='approx' else f'{o["value"]:g}'
        bars+=f'<div class="capital-bar-row"><div><strong>{e(row["name"])}</strong><span>${label}B</span></div><div class="capital-bar-track" role="img" aria-label="{e(row["name"]+": "+label+" USD billion · "+o["period"],quote=True)}"><span class="capital-bar {"guidance" if forecast else "actual"}" style="width:{o["value"]/ceiling*100:.3f}%"></span>'
        if o['upper'] is not None:bars+=f'<span class="capital-range" style="left:{o["value"]/ceiling*100:.3f}%;width:{(o["upper"]-o["value"])/ceiling*100:.3f}%"></span>'
        bars+=f'</div><small>{e(o["period"])} · {"Forecast" if forecast else "Reported actual"} · {link(sources,o["source"])}</small></div>'
        if forecast:table+=f'<tr><th scope="row">{e(row["name"])}</th><td>{e(o["period"])}</td><td>{label}</td><td>Forecast / company guidance</td><td>{link(sources,o["source"])}<br>{e(o["note"])}</td></tr>'
    scopes=''.join(f'<li><strong>{e(row["name"])}</strong>: {e(ms[row["history_metric"]]["scope"])}'+(f' Guidance: {e(ms[row["guidance_metric"]]["scope"])}' if row['guidance_metric'] else '')+'</li>' for row in config['companies'])
    return f'''<section id="capital-buildout" class="section explorer-section" data-explorer-snapshot><div class="section-top"><div><div class="eyebrow muted">CAPITAL → INFRASTRUCTURE</div><h2>The investment taking physical shape.</h2></div><a class="section-link" href="{base}infrastructure/#capital-buildout">Explore infrastructure ↗</a></div><p class="section-intro">Building AI factories takes sustained investment in land, power, servers and networks. Follow the capital behind that buildout, with worldwide company spending kept distinct from AI-only or U.S. spending.</p><div class="capital-layout"><article class="explorer-panel"><div class="eyebrow">REPORTED HISTORY · USD BILLION</div><h3>Global hyperscaler capital spending</h3><p class="explorer-subtitle">Cash PP&amp;E · fiscal years ended {lo}–{hi}</p>{svg}<div class="capital-legend">{legend}</div><p class="chart-footnote">Fiscal years end on different dates. Lines join adjacent reported annual observations. No aggregate or missing years are inferred.</p></article><article class="explorer-panel"><div class="eyebrow">SPENDING OUTLOOK · USD BILLION</div><h3>Latest spending &amp; guidance</h3><p class="explorer-subtitle">Hatched = forecast · solid = actual · bars start at zero</p>{bars}<p class="chart-footnote">Oracle is a completed fiscal year; the other bars are calendar-year guidance. Definitions differ, including lease treatment. Amazon and Alphabet outlooks are attributed to AP earnings reporting.</p></article></div><details class="explorer-evidence"><summary>Data, accounting differences &amp; sources</summary><p>{e(config['scope'])}</p><ul>{scopes}</ul><div class="table-scroll"><table><caption>Capital spending · USD billion</caption><thead><tr><th>Company</th><th>Period</th><th>USD billion</th><th>Classification</th><th>Source &amp; scope</th></tr></thead><tbody>{table}</tbody></table></div><p>Reviewed {e(config['reviewed_at'][:10])}. Values retain source precision. No inflation adjustment.</p><ul>{''.join('<li>'+e(g)+'</li>' for g in config['gaps'])}</ul><a class="source-inline" href="{base}data/ledger.json">Download accepted observations ↗</a></details></section>'''

def capability_svg(c,compact=False):
    rs=c['rows'];start=min(date.fromisoformat(r['released']).toordinal() for r in rs);end=max(date.fromisoformat(r['released']).toordinal() for r in rs)
    floor=(int(min(r['score'] for r in rs))//20)*20;ceiling=((int(max(r['high'] or r['score'] for r in rs))//20)+1)*20
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
    for r in rs:
        color='#c5f277' if r['access']=='Open weights' else '#c1a1f5' if r['access']=='Closed weights' else '#b0b9b0'
        interval=f'; 90% interval {r["low"]:g}–{r["high"]:g}' if r['low'] is not None else '; interval not supplied for this anchor'
        svg+=f'<circle class="eci-point" data-model="{r["id"]}" cx="{xp(r["released"]):.2f}" cy="{yp(r["score"]):.2f}" r="{2.5 if compact else 3.8}" fill="{color}" opacity=".7"><title>{e(r["name"])} · {r["released"]} · ECI {r["score"]:g}{interval}</title></circle>'
    return svg+'</svg>'

def capabilities(ledger,x,base):
    if not x.get('capabilities'):return ''
    c=x['capabilities'];sources={s['id']:s for s in ledger['sources']}
    rows=''.join(f'<tr data-model="{r["id"]}"><th scope="row">{e(r["name"])}</th><td>{e(r["organization"])}</td><td>{r["released"]}</td><td>{r["score"]:g}</td><td>{str(r["low"])+"–"+str(r["high"]) if r["low"] is not None else "Anchor; interval not supplied"}</td><td>{e(r["access"])}</td></tr>' for r in sorted(c['rows'],key=lambda r:-r['score']))
    return f'''<section id="model-capabilities" class="section explorer-section" data-explorer-snapshot><div class="section-top"><div><div class="eyebrow muted">MODELS / CAPABILITY THROUGH TIME</div><h2>A broader frontier of capability.</h2></div><a class="section-link" href="https://epoch.ai/eci">Explore Epoch AI ↗</a></div><p class="section-intro">Epoch’s Capabilities Index brings multiple benchmarks onto a common scale. Follow model releases across organizations and open- or closed-weight availability.</p><div class="explorer-panel"><div class="explorer-controls" data-enhanced-controls hidden><label>Developer<select id="eci-developer"><option value="all">All developers</option></select></label><label>Availability<select id="eci-access"><option value="all">All models</option><option>Open weights</option><option>Closed weights</option><option>Other</option></select></label><label class="explorer-check"><input id="eci-frontier-only" type="checkbox">Frontier only</label></div><p class="explorer-subtitle">ECI points · model release date · all scores from one dataset snapshot</p><div id="eci-plot">{capability_svg(c)}</div><div class="capital-legend"><span style="--series:#c5f277"><i></i>Open weights</span><span style="--series:#c1a1f5"><i></i>Closed weights</span><span style="--series:#b0b9b0"><i></i>Other</span></div><div class="explorer-controls" data-enhanced-controls hidden><label>Inspect a model<select id="eci-model"></select></label></div><div id="eci-selection" class="explorer-selection" aria-live="polite">{len(c['rows'])} published model scores. Inspect individual values and uncertainty in the table below.</div><p class="chart-footnote">ECI is an index, not a percentage or a direct measure of reliable work. The step line is the best score by release date within the selected group, not a forecast. No future capability is extrapolated.</p></div><details class="explorer-evidence"><summary>Model scores, uncertainty &amp; methodology</summary><p>Source: {link(sources,c['source'])} · {link(sources,c['method_source'])}. Retrieved {c['retrieved_at'][:10]}. Data © Epoch AI and contributors, reused with attribution. 90% confidence intervals come from the same download; two calibration anchors have no supplied interval.</p><p>Historical scores can change when Epoch refits its index. This page uses one complete snapshot rather than combining vintages. Benchmark coverage and developer-reported results can affect comparability; overlapping intervals do not establish a reliable ranking. Open weights do not necessarily mean unrestricted open source.</p><div class="table-scroll"><table><caption>Epoch Capabilities Index · reviewed snapshot</caption><thead><tr><th>Model</th><th>Developer</th><th>Release date</th><th>ECI</th><th>90% interval</th><th>Availability</th></tr></thead><tbody id="eci-table">{rows}</tbody></table></div><p><a class="source-inline" href="{base}data/expansion.json">Download reviewed model snapshot ↗</a> · <a class="source-inline" href="https://epoch.ai/benchmarks/use-this-data">Dataset licensing &amp; original authors ↗</a></p></details></section>'''

def map_svg(delivery,ledger,compact=False):
    basemap=json.loads((ROOT/'site/data/map-basemap.json').read_text(encoding='utf-8'))
    colors={l['id']:l['color'] for l in ledger['layers']}
    svg=svg_start('Mapped projects in the Stack Ledger sample','Approximate places and counties. Markers do not identify facility boundaries or represent capacity.','155 108 200 95')
    svg=svg.replace('class="explorer-chart"','class="explorer-chart project-map-svg"')
    svg+='<g class="map-land">'+''.join(f'<path d="{p}"/>' for p in basemap['paths'])+'</g><g class="map-points">'
    groups={}
    for p in delivery['projects']:
        if not p.get('map_location'):continue
        g=p['map_location'];key=(g['latitude'],g['longitude']);groups.setdefault(key,[]).append(p)
    for (lat,lon),ps in groups.items():
        color=colors[ps[0]['layer']] if len({p['layer'] for p in ps})==1 else '#edf0e4'
        title=ps[0]['map_location']['label']+' · '+str(len(ps))+' project record(s)'
        svg+=f'<circle cx="{(lon+180)*3:.4f}" cy="{(90-lat)*3:.4f}" r="1.3" fill="{color}" stroke="#0d1512" stroke-width=".4"><title>{e(title)}</title></circle>'
    return svg+'</g></svg>'

def project_map(delivery,ledger,base):
    count=sum('map_location' in p for p in delivery['projects']);sources={s['id']:s for s in ledger['sources']}
    rows=''.join(f'<tr><th scope="row">{e(p["name"])}</th><td>{e(p["map_location"]["label"])}</td><td>{e(p["map_location"]["precision"])}</td><td>{link(sources,p["map_location"]["source"])} · {e(p["map_location"]["source_key"])}</td></tr>' for p in delivery['projects'] if p.get('map_location'))
    legend=''.join(f'<span style="--series:{l["color"]}"><i></i>{e(l["name"])}</span>' for l in ledger['layers'] if any(p['layer']==l['id'] and p.get('map_location') for p in delivery['projects']))
    return f'''<section id="project-map" class="explorer-section" data-explorer-snapshot><div class="section-top"><div><div class="eyebrow muted">THE GEOGRAPHY OF THE BUILDOUT</div><h2>Investment has an address.</h2></div></div><p class="section-intro">Explore the places behind the projects. Colors follow the five layers; records in the same locality share a marker. Select a location to inspect its projects and evidence.</p><div class="explorer-panel"><div class="explorer-controls" data-enhanced-controls hidden><label>Owner / operator<select id="map-company"><option value="all">All owners / operators</option></select></label><label>Location coverage<select id="map-coverage"><option value="all">All records</option><option value="mapped">Mapped records</option><option value="unmapped">Location not mapped</option></select></label><div class="map-navigation" role="group" aria-label="Map navigation"><button type="button" id="map-us">U.S.</button><button type="button" id="map-world">World</button><button type="button" id="map-zoom-in" aria-label="Zoom map in">+</button><button type="button" id="map-zoom-out" aria-label="Zoom map out">−</button></div></div><div id="map-canvas">{map_svg(delivery,ledger)}</div><div class="capital-legend">{legend}<span style="--series:#edf0e4"><i></i>Shared across layers</span></div><p id="map-count" class="chart-footnote" aria-live="polite">{count} of {len(delivery['projects'])} project records have reviewed locations. Remaining records include distributed programs and location gaps.</p><div id="map-selection" class="explorer-selection" aria-live="polite">Markers indicate places or counties, not exact facilities. Marker size does not represent megawatts, investment or jobs.</div></div><details class="explorer-evidence"><summary>Locations, precision &amp; map sources</summary><p>Approximate place/county points from the U.S. Census Bureau and GeoNames (CC BY 4.0). Project disclosures establish the locality; gazetteers supply its coordinates. Multiple phases can occupy one marker without being added into a capacity total. Some records cover several sites and are intentionally unmapped.</p><p>Basemap: <a class="source-inline" href="https://www.naturalearthdata.com/about/terms-of-use/">Natural Earth, public domain</a>. Geographic boundaries are for orientation. Map geometry is served locally; opening this map sends no requests to a map provider.</p><div class="table-scroll"><table><caption>Reviewed map locations</caption><thead><tr><th>Project</th><th>Location</th><th>Precision</th><th>Coordinate source / identifier</th></tr></thead><tbody>{rows}</tbody></table></div><a class="source-inline" href="{base}data/delivery.json">Download project and location data ↗</a></details></section>'''

def previews(delivery,ledger,x,base):
    if not x.get('capabilities'):return ''
    count=sum('map_location' in p for p in delivery['projects'])
    return f'''<section id="buildout-explorers" class="section"><div class="explorer-preview-grid"><a class="explorer-preview" href="{base}projects/#project-map"><div class="eyebrow">WHERE IT IS HAPPENING</div><h3>The buildout, on the map.</h3>{map_svg(delivery,ledger,True)}<p>{count} mapped project records · power, chips and AI factories</p><strong>Explore the project map ↗</strong></a><a class="explorer-preview" href="{base}models/#model-capabilities"><div class="eyebrow">WHAT MODELS CAN DO</div><h3>Follow the capability frontier.</h3>{capability_svg(x['capabilities'],True)}<p>Epoch’s index · {len(x['capabilities']['rows'])} model scores · one reviewed snapshot</p><strong>Explore model capabilities ↗</strong></a></div></section>'''
