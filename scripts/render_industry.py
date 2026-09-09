"""Jobs & Industry opening, derived from accepted records at build time."""
from html import escape as e
from datetime import date
from render_explorers import link, records


def industry_opening(ledger, base):
    sources = {s['id']: s for s in ledger['sources']}
    spending = sorted((o for o in records(ledger, 'census-dc-construction-saar')
                       if o['status'] == 'estimate' and o['precision'] == 'eq'),
                      key=lambda o: o['period'])
    # Compare the same month and publication vintage; never invent a baseline.
    latest = spending[-1] if spending else None
    prior_period = f"{int(latest['period'][:4])-1}{latest['period'][4:]}" if latest else None
    prior = next((o for o in spending if o['period'] == prior_period
                  and o['source'] == latest['source']), None)
    if prior and prior['value'] > 0:
        change = (latest['value'] / prior['value'] - 1) * 100
        max_value = max(prior['value'], latest['value']) * 1.12
        bars = ''.join(f'''<div class="industry-spending-row"><div><span>{date.fromisoformat(o['period']+'-01').strftime('%b %Y')}</span><strong>${o['value']/1000:,.1f}B</strong></div><div class="industry-bar-track"><i style="width:{o['value']/max_value*100:.3f}%"></i></div></div>''' for o in [prior, latest])
        spending_view = f'''<div class="industry-big-number">{change:+.0f}% <span>year over year</span></div><p class="industry-chart-unit">U.S. private data-center construction · $ billions, annualized</p><div class="industry-spending-bars" role="img" aria-label="{e(prior['period'])}: {prior['value']/1000:.3f} billion dollars; {e(latest['period'])}: {latest['value']/1000:.3f} billion dollars. Both bars start at zero.">{bars}</div><p class="industry-context">Construction put in place tracks physical building activity, beyond announced investment plans.</p><p class="chart-footnote">Census estimates, seasonally adjusted annual rate (SAAR), in current dollars. An annualized pace, not spending during one month or a completed year; includes non-AI data centers. Bars start at zero. Latest period may be preliminary.</p>{link(sources, latest['source'])}'''
    else:
        spending_view = '<p>A comparable same-month, same-vintage construction baseline is not available. No year-over-year growth is inferred.</p>'

    # This is a share of all postings, separate from the posting-volume index.
    postings = records(ledger, 'indeed-dc-postings-share')
    baseline = next((o for o in postings if o['year'] == 2023 and o['precision'] == 'approx' and o['status'] == 'observation'), None)
    endpoint = next((o for o in postings if o['year'] == 2026 and o['precision'] == 'approx' and o['status'] == 'observation'), None)
    if baseline and endpoint and baseline['value'] > 0 and baseline['source'] == endpoint['source']:
        ratio = endpoint['value'] / baseline['value']
        scale = max(baseline['value'], endpoint['value']) / .8
        hiring_view = f'''<div class="industry-big-number">≈{ratio:g}× <span>the share of U.S. postings</span></div><p class="industry-chart-unit">Relative share of U.S. postings on Indeed · 2023 = 1×</p><div class="industry-postings-bars"><div><span>2023</span><i style="width:{baseline['value']/scale*100:.3f}%"></i><b>1×</b></div><div><span>2026</span><i style="width:{endpoint['value']/scale*100:.3f}%"></i><b>≈{ratio:g}×</b></div></div><p class="industry-context">Using 2023 as the benchmark, data-center roles accounted for roughly {ratio:g} times the share of advertised hiring demand in 2026.</p><p class="chart-footnote">2023 is normalized to 1× from Indeed’s rounded posting shares. This measures relative share, not job counts or hires. Bars start at zero. Indeed inconsistently names May/June 2023; the 2026 point is the level in its July report, not an annual average. No intermediate history is inferred.</p>{link(sources, endpoint['source'])}'''
    else:
        hiring_view = '<p>A comparable hiring-demand share comparison is not available in the accepted record.</p>'

    contributors = next((o for o in records(ledger, 'fairwater-construction-contributors') if o['id'] == 'fairwater-construction-contributors-2026' and o['status'] == 'observation' and o['precision'] == 'approx'), None)
    operating = next((o for o in records(ledger, 'fairwater-onsite-employees') if o['id'] == 'fairwater-onsite-employees-2026' and o['status'] == 'observation' and o['precision'] == 'approx'), None)
    icons = {
        'build': '<path d="M12 55V10h38M8 19h49L40 10M17 10v45M9 55h17M45 19v17h7v7h-7M17 24l-5 8 5 8-5 8"/>',
        'equip': '<rect x="7" y="8" width="20" height="47" rx="3"/><rect x="36" y="8" width="20" height="47" rx="3"/><path d="M12 18h10M12 27h10M41 18h10M41 27h10M27 40h9M17 46v3M46 46v3"/>',
        'operate': '<path d="M5 55V30l18-10v10l18-10v35M41 35h17v20H5M12 42h4m11 0h4M12 49h4m11 0h4M47 44h5"/><path d="M46 9v15m-6-9 6-6 6 6"/>',
    }
    def icon(name):
        return f'<svg viewBox="0 0 64 64" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">{icons[name]}</svg>'
    fairwater = ''
    if contributors and operating and contributors['source'] == operating['source']:
        fairwater = f'''<article class="industry-place"><div class="industry-place-heading"><div><div class="eyebrow">A REAL PLACE / FAIRWATER, WISCONSIN</div><h3>From construction crews to an operating AI campus.</h3></div><a class="section-link" href="{base}projects/#project-fairwater-one">Explore Fairwater ↗</a></div><div class="industry-workflow"><div>{icon('build')}<div><span class="eyebrow">01 / BUILD</span><strong>≈{contributors['value']:,.0f}</strong><p>construction contributors over two years</p></div></div><div>{icon('equip')}<div><span class="eyebrow">02 / COMMISSION</span><strong class="industry-word">Operational</strong><p>first facility · reported June 2026</p></div></div><div>{icon('operate')}<div><span class="eyebrow">03 / OPERATE</span><strong>≈{operating['value']:,.0f}</strong><p>full-time employees on site in June 2026</p></div></div></div><div class="industry-place-note"><p>Microsoft reports nearly {contributors['value']:,.0f} construction contributors across two years and nearly {operating['value']:,.0f} full-time employees on site at the first facility. These are different measures and are not added.</p>{link(sources, contributors['source'])}</div><p class="chart-footnote">Construction participation is cumulative, not a simultaneous workforce or job-years. Employer breakdown for on-site employees is unspecified. Both are company-reported, not independently verified net job creation. Icons illustrate work phases, not quantities.</p></article>'''
    plans = []
    plan_cards = []
    for mid, project, name, caption, symbol in [
        ('hyperion-construction-jobs', 'hyperion', 'Meta Hyperion', 'expected peak construction workers · Louisiana', 'build'),
        ('tsmc-arizona-first-three-jobs', 'tsmc-arizona-program', 'TSMC Arizona', 'future direct high-tech jobs · first three fabs only', 'equip'),
        ('terafab-permanent-promised', 'terafab', 'Tesla + SpaceX Terafab', 'future facility employees · Grimes County, Texas', 'operate'),
    ]:
        candidates = [o for o in records(ledger, mid) if o['status'] == 'company-commitment']
        if not candidates:
            continue
        o = candidates[-1]
        plans.append(o)
        prefix = '&gt;' if o['precision'] == 'gt' else '≈' if o['precision'] == 'approx' else '≥' if mid == 'terafab-permanent-promised' else ''
        plan_cards.append(f'''<article class="industry-plan"><div class="industry-plan-top">{icon(symbol)}<span class="stage">Company workforce plan</span></div><h4>{e(name)}</h4><strong>{prefix}{o['value']:,.0f}</strong><p>{e(caption)}</p>{link(sources,o['source'])}<a class="section-link" href="{base}projects/#project-{project}">Project evidence ↗</a></article>''')
    planned = f'''<section class="industry-plans" aria-labelledby="industry-plans-title"><div class="eyebrow">THE NEXT WAVE / PROPOSED WORKFORCE</div><h3 id="industry-plans-title">Larger projects. Larger workforce plans.</h3><p>Named projects show the scale being proposed across construction and chip manufacturing. These are future workforce commitments, with different scopes and schedules.</p><div class="industry-plans-grid">{''.join(plan_cards)}</div><p class="chart-footnote">No combined jobs total: a construction peak differs from permanent facility roles. Commitments are not verified hires. Terafab's source describes at least 3,000 employees; no verified first-wafer or volume-production date is in this review.</p></section>''' if plan_cards else ''
    used = ([prior, latest] if prior else []) + ([baseline, endpoint] if baseline and endpoint else []) + ([contributors, operating] if contributors and operating else []) + plans
    evidence_rows = ''.join(f'<tr><td>{e(o["metric"])}</td><td>{e(o["period"])}</td><td>{"&gt;" if o["precision"] == "gt" else "&lt;" if o["precision"] == "lt" else "≈" if o["precision"] == "approx" else ""}{o["value"]:,}</td><td>{e(o["status"])}</td><td>{link(sources,o["source"])}</td></tr>' for o in used)
    return f'''<section id="industry-momentum" class="section industry-momentum" data-explorer-snapshot aria-labelledby="industry-momentum-title"><div class="section-top"><div><div class="eyebrow muted">THE BUILDOUT / WORK ON THE GROUND</div><h2 id="industry-momentum-title">More building. More demand for skilled work.</h2></div></div><p class="section-intro">Follow construction activity and hiring demand, then compare future workforce plans with a reported operating-project example. Together they show how digital infrastructure connects to physical work.</p><div class="industry-momentum-grid"><article class="industry-signal"><div class="eyebrow">01 / CONSTRUCTION ACTIVITY</div><h3>The pace of construction.</h3>{spending_view}</article><article class="industry-signal industry-hiring"><div class="eyebrow">02 / HIRING DEMAND</div><h3>The work needs people.</h3>{hiring_view}</article></div>{planned}{fairwater}<details class="explorer-evidence"><summary>Data, definitions &amp; sources</summary><p>These are complementary indicators, not a combined national “AI jobs” estimate. Spending does not establish employment; recruitment does not establish hires; a project’s workforce does not establish economy-wide net gains. Raw values below retain the ledger’s units: construction in USD millions/year (SAAR), postings per 1,000 total postings, construction contributors as workers, and on-site workforce as employees; other workforce plans retain their job units. The separate 2024–2026 posting-volume index remains in the accepted ledger and detailed coverage.</p><div class="table-scroll"><table><thead><tr><th>Metric</th><th>Period</th><th>Value</th><th>Evidence type</th><th>Source</th></tr></thead><tbody>{evidence_rows}</tbody></table></div><a class="source-inline" href="{base}data/ledger.json">Download the accepted ledger ↗</a></details></section>'''
