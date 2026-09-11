"""Render the reviewed claims snapshot without requiring JavaScript or network data."""
from html import escape as e


PRECISION_PREFIX = {'eq': '', 'approx': 'about ', 'gt': 'more than '}


def survey_value_html(point):
    """The bar's own figure. The number stays the large element and the qualifier rides in front of
    it, small and unbreakable: at the bar's 24px, "more than 33%" wrapped onto two lines and made
    that row twice the height of its neighbours (reported from a phone, 2026-09-11)."""
    prefix = PRECISION_PREFIX.get(point.get('precision', 'eq'), '')
    lead = f'<span class="qualifier">{prefix.strip()}</span>' if prefix else ''
    return f"{lead}{point['value']:g}%"


def survey_value(point):
    """A survey answer the source states loosely stays loose on the page.

    The New York Fed reports "just over a third of service firms" retrained workers and gives no
    exact percentage in its text, so the bar is drawn at its floor and labelled "more than 33%".
    Printing 34% would invent a digit the source never published.
    """
    return f"{PRECISION_PREFIX.get(point.get('precision', 'eq'), '')}{point['value']:g}%"


def employment_feature(data, citations):
    cards=''.join(f'<article class="employment-card"><div class="eyebrow">{e(c["title"])}</div><h3>{e(c["headline"])}</h3><p class="claim-scope">{e(c["scope"])}</p><p>{e(c["body"])}</p>{citations(c["sources"])}</article>' for c in data['cards'])
    s=data['survey']
    # A common 0–100% scale measures firms, never jobs or net employment.
    bars=''.join(f'<div class="evidence-bar-row"><div><span>{e(p["label"])}</span><strong>{survey_value_html(p)}</strong></div><div class="evidence-bar-track"><span class="evidence-bar" style="width:{p["value"]:g}%"></span></div></div>' for p in s['points'])
    rows=''.join(f'<tr><th scope="row">{e(p["label"])}</th><td>{survey_value(p)}</td></tr>' for p in s['points'])
    return f'''<section class="section employment-feature" id="ai-employment"><div class="eyebrow">AI & JOBS / THE EVIDENCE SO FAR</div><h2>Is AI causing mass unemployment?</h2><p class="employment-verdict">{e(data['verdict'])}</p><p class="section-intro">{e(data['summary'])}</p><div class="employment-grid">{cards}</div><div class="employment-detail"><figure class="evidence-graphic"><h3>{e(s['title'])}</h3><p>{e(s['scope'])}</p><p class="evidence-unit">{e(s['unit'])} · Reported {e(s['status'])}</p><div aria-hidden="true">{bars}<div class="employment-axis"><span>0%</span><span>50%</span><span>100%</span></div></div><details><summary>Data & scope</summary><table><caption>{e(s['unit'])}</caption><thead><tr><th>Reported action</th><th>Share</th></tr></thead><tbody>{rows}</tbody></table></details><figcaption>{e(s['note'])}</figcaption>{citations([s['source']])}</figure><div class="employment-reading"><h3>What these numbers can establish</h3><p><strong>Some displacement can happen without mass unemployment.</strong> Reduced entry-level hiring can matter before layoffs or unemployment rise. Different samples, exposure measures and time windows can produce different findings.</p><p><strong>Layoff announcements are a separate signal.</strong> Employer references to AI do not independently establish causation, actual separations or economy-wide net losses. See the <a href="#article-review">Challenger reconciliation and jobs-article audit</a>.</p><p><strong>The buildout creates demand for work.</strong> The construction and recruiting evidence below helps document that opportunity. Job postings are not filled jobs; construction roles and displaced office roles are not automatically interchangeable. We cannot subtract these different datasets into a net AI jobs total.</p><h3>What would change the assessment?</h3><p>{e(data['future'])}</p><a class="source-inline" href="#young-workers">Examine the entry-level study and its limits →</a></div></div></section>'''


def resident_values(r):
    return (r['real_rate_2016']-r['real_rate_2026'])/r['real_rate_2016']*100, r['example_vehicles']*r['vehicle_saving_example']-r['average_home_bill_increase']


def resident_feature(r,citations):
    reduction,net=resident_values(r)
    return f'''<section class="section resident-context" id="resident-benefit"><div class="eyebrow">LOUDOUN / WHAT IT MEANS FOR RESIDENTS</div><h2>Public revenue. Household consequences.</h2><p>Loudoun credits data-center revenue with helping fund public services and lower residential tax rates. Its adopted-budget examples show how that can reach a household, alongside the effect of rising home values.</p><div class="resident-grid"><div><span>Real-property tax rate</span><strong>{reduction:.1f}% lower</strong><p>${r['real_rate_2016']:.3f} in 2016 → ${r['real_rate_2026']:.3f} in 2026 per $100 assessed value. A rate reduction, not a measured reduction in every homeowner’s bill.</p></div><div><span>County’s vehicle example · TY2026</span><strong>${r['vehicle_saving_example']:,.0f} less</strong><p>Annual vehicle tax for a car assessed at ${r['vehicle_assessed_value']:,.0f}, according to the county’s adopted-budget release. Actual bills depend on assessment and applicable relief.</p></div><div><span>Illustrative home + two vehicles</span><strong>${net:,.0f} less</strong><p>{r['example_vehicles']} × ${r['vehicle_saving_example']:,.0f} vehicle savings − ${r['average_home_bill_increase']:,.0f} average-home tax increase = ${net:,.0f} lower combined annual tax. A constructed household example, not the average savings for all households.</p></div></div><p><strong>The home bill itself can rise.</strong> For tax year 2026, the county projects a ${r['average_home_bill_increase']:,.0f} increase for its average homeowner despite the unchanged real-property rate. Vehicle rates fall from ${r['vehicle_rate_before']:.2f} to ${r['vehicle_rate_2026']:.2f} per $100 assessed value. We use the county’s published vehicle-bill example, which should not be reconstructed from the rate difference alone.</p><p><strong>What we can attribute:</strong> the county identifies data-center revenue as supporting tax relief and services. This evidence does not isolate the amount each household saved solely because of data centers. Renters, households without cars, and households with different assessments will have different outcomes; the example covers these property taxes, not every tax or fee.</p>{citations(r['sources'])}</section>'''

def water_values(w):
    """US liquid gallon and international avoirdupois pound; no rounded intermediates."""
    almond_liters=w['blue_gallons_per_pound']*w['almond_grams']/453.59237*3.785411784
    query_ml=w['query_gallons']*3785.411784
    return almond_liters,query_ml,almond_liters*1000/query_ml


def water_feature(w, citations):
    liters,ml,ratio=water_values(w)
    return f'''<section class="section" id="water-perspective"><div class="eyebrow">WATER IN PERSPECTIVE / A CONDITIONAL CALCULATION</div><h2>One almond. An explicit comparison.</h2><p class="section-intro">Using a historical irrigation estimate, an assumed {w['almond_grams']:g}-gram kernel and Sam Altman’s reported ChatGPT average, the arithmetic gives <strong>about {round(ratio/1000)*1000:,} queries per almond</strong>. This is a conditional volume comparison, not a verified equivalence of water footprints.</p><div class="water-equation"><div><span>Estimated irrigation consumption</span><strong>{liters:.1f} L</strong><p>Per assumed {w['almond_grams']:g} g almond<br>{e(w['almond_period'])}</p></div><span class="water-operator" aria-hidden="true">÷</span><div><span>Altman-reported query average</span><strong>{ml:.2f} mL</strong><p>Per query<br>{e(w['query_period'])}</p></div><span class="water-operator" aria-hidden="true">≈</span><div><span>Calculated ratio, rounded</span><strong>{round(ratio/1000)*1000:,}</strong><p>Queries per assumed almond<br>Conditional on the reported query figure</p></div></div><p><strong>The almond side uses blue water only:</strong> irrigation water consumed. Rainfall (green water) and the pollution-assimilation indicator (grey water) are excluded. The report is hosted by the Almond Board and concerns historical California production, not today’s worldwide average.</p><p><strong>The unresolved part is the query measurement:</strong> Altman’s post does not disclose sufficient model, task, location, period or water-accounting methodology to verify a like-for-like comparison. The number does not establish how much water your prompt uses or whether a particular watershed can support a campus.</p><details class="water-method"><summary>See the calculation and assumptions</summary><p>{w['blue_gallons_per_pound']:g} US gallons of blue water per pound of kernels × {w['almond_grams']:g} g ÷ 453.59237 g per pound = {liters:.3f} liters per assumed kernel.</p><p>{w['query_gallons']:g} US gallons per reported average query × 3,785.411784 mL per US gallon = {ml:.6f} mL.</p><p>Divide the unrounded almond volume by the unrounded query volume: {ratio:,.0f}. The display rounds to the nearest thousand. The kernel mass is an illustrative assumption, not a measured average from this report. A larger kernel increases the ratio proportionally; a more water-intensive query reduces it.</p><p>These are different products with different benefits. A volume comparison does not rank their social value or imply that water conserved in one location is available in another.</p></details>{citations(w['sources'])}<p><a class="source-inline" href="#water-national-context">See national data-center and golf context ↓</a></p></section>'''

def render_claims(data, sources, base='../'):
    sources = {s['id']: s for s in sources}

    def citations(ids):
        return '<ul class="claim-sources">' + ''.join(
            f'<li><a href="{e(sources[s]["url"], quote=True)}">{e(sources[s]["publisher"])} · {e(sources[s]["title"])} ↗</a>'
            f'<span>Published {e(sources[s]["published"] or "date not disclosed")} · reviewed {e(data["reviewed_at"][:10])}</span></li>' for s in ids) + '</ul>'

    topics = list(dict.fromkeys(c['topic'] for c in data['claims']))
    graphics = ''
    for g in data['highlights']:
        maximum = max(p['value'] for p in g['points']) * 1.12
        bars = ''.join(f'<div class="evidence-bar-row"><div><span>{e(p["period"])}</span><strong>{p["value"]:g}</strong></div>'
                       f'<div class="evidence-bar-track"><span class="evidence-bar {p["status"]}" style="width:{p["value"]/maximum*100:.3f}%"></span></div>'
                       f'<small>{e(p["status"].capitalize())}</small></div>' for p in g['points'])
        rows = ''.join(f'<tr><th scope="row">{e(p["period"])}</th><td>{p["value"]:g}</td><td>{e(p["status"])}</td></tr>' for p in g['points'])
        consequence='<div class="resident-card-note"><strong>So what for residents?</strong><p>Lower tax rates and funded services. The county reports a $352 vehicle-tax reduction in its $30,000-car example.</p><a class="source-inline" href="#resident-benefit">See the household calculation ↓</a></div>' if g['id']=='tax' else ''
        graphics += f'<figure class="evidence-graphic"><div class="eyebrow">BENEFITS IN VIEW</div><h3>{e(g["title"])}</h3><p>{e(g["scope"])}</p><p class="evidence-unit">{e(g["unit"])}</p><div aria-hidden="true">{bars}</div><details><summary>Data & scope</summary><table><caption>{e(g["title"])} · {e(g["unit"])}</caption><thead><tr><th>Period</th><th>Value</th><th>Status</th></tr></thead><tbody>{rows}</tbody></table></details><figcaption>{e(g["note"])}</figcaption>{citations([g["source"]])}{consequence}</figure>'
    cards = ''
    for c in data['claims']:
        cards += f'<article class="claim-card" id="{e(c["id"])}" data-topic="{e(c["topic"], quote=True)}"><div class="claim-meta"><span>{e(c["topic"])}</span><a href="#{e(c["id"])}" aria-label="Link to this claim">#</a></div><h3>{e(c["claim"])}</h3><p class="claim-verdict">{e(c["verdict"])}</p><p class="claim-scope">{e(c["scope"])}</p><h4>What the evidence says</h4><p>{e(c["evidence"])}</p><div class="claim-future"><h4>What future projects should show</h4><p>{e(c["future"])}</p></div><details><summary>Limits & sources</summary><p>{e(c["gap"])}</p>{citations(c["sources"])}</details></article>'
    audits = ''.join(f'<article class="article-check"><div><h3>{e(a["claim"])}</h3><span class="claim-verdict">{e(a["status"])}</span></div><p>{e(a["finding"])}</p>{citations(a["sources"])}</article>' for a in data['article_audit'])
    options = ''.join(f'<option>{e(t)}</option>' for t in topics)
    return f'''<section class="page-hero claims-hero"><div class="eyebrow">CLAIMS & EVIDENCE / THE PUBLIC BENEFIT</div><h1>Build more.<br>Know what it delivers.</h1><p>The opportunity is substantial: skilled work, local revenue, more power and useful intelligence. Examine the evidence behind both the benefits and the concerns.</p><div class="claims-jump"><a href="#ai-employment">AI and jobs</a><a href="#evidence-review">Explore {len(data['claims'])} claims ↓</a><a href="#water-perspective">Water in perspective</a><a href="#article-review">The linked article, checked ↓</a><a href="{base}projects/">Follow the projects ↗</a></div><p class="claim-scope">Reviewed {e(data['reviewed_at'][:10])} · {e(data['reviewer'])}</p></section>
    {employment_feature(data['employment_context'],citations)}
    <section class="section evidence-highlights" aria-label="Sourced indicators of economic benefit">{graphics}</section>
    {resident_feature(data['resident_context'],citations)}
    {water_feature(data['water_comparison'], citations)}
    <aside class="reading-note"><strong>A growing evidence file, not a final verdict on every project.</strong><p>This review covers recurring public claims and the material quantitative arguments in the linked article. Local findings stay local; estimates, forecasts and reported outcomes stay distinct. “Not established” means the evidence reviewed does not settle the claim. Future-project criteria are Stack Ledger’s research recommendations.</p></aside>
    <section class="section" id="evidence-review"><div class="section-top"><div><div class="eyebrow">POWER → FACTORIES → USEFUL WORK</div><h2>The claims, examined.</h2></div></div><form class="claims-controls" hidden role="search"><label>Topic<select id="claim-topic"><option value="">All topics</option>{options}</select></label><label>Search claims<input id="claim-search" type="search" placeholder="Try water, wages or taxes"></label><button type="reset">Clear filters</button></form><p id="claims-count" role="status" aria-live="polite">{len(data['claims'])} claims</p><div class="claims-grid">{cards}</div><p id="claims-empty" hidden>No matching claims. Try another topic or search term.</p></section>
    <section class="section" id="article-review"><div class="eyebrow">SOURCE AUDIT / SEPTEMBER 2026</div><h2>What the jobs article establishes.</h2><p class="section-intro">The BizNews article republishes The Economist. Some headline figures match primary releases; other estimates need underlying datasets and methods. Unresolved items remain visible and are excluded from benefit charts.</p>{citations(['claims-biznews'])}<div class="article-checks">{audits}</div></section>
    <section class="manifesto"><div><h2>Turn the opportunity into receipts.</h2><p>Follow projects from announcement to operation, then measure local hires, paid contracts, tax collections, delivered power and completed work. These outcomes will determine how much reindustrialization reaches the community.</p></div><a href="{base}projects/">Track delivery ↗</a></section><p class="reading-note"><a href="{base}data/claims.json">Download this reviewed evidence file</a> · <a href="https://github.com/reedos/stack_ledger/issues">Submit a claim or correction ↗</a></p>'''
