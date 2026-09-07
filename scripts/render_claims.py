"""Render the reviewed claims snapshot without requiring JavaScript or network data."""
from html import escape as e


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
        graphics += f'<figure class="evidence-graphic"><div class="eyebrow">BENEFITS IN VIEW</div><h3>{e(g["title"])}</h3><p>{e(g["scope"])}</p><p class="evidence-unit">{e(g["unit"])}</p><div aria-hidden="true">{bars}</div><details><summary>Data & scope</summary><table><caption>{e(g["title"])} · {e(g["unit"])}</caption><thead><tr><th>Period</th><th>Value</th><th>Status</th></tr></thead><tbody>{rows}</tbody></table></details><figcaption>{e(g["note"])}</figcaption>{citations([g["source"]])}</figure>'
    cards = ''
    for c in data['claims']:
        cards += f'<article class="claim-card" id="{e(c["id"])}" data-topic="{e(c["topic"], quote=True)}"><div class="claim-meta"><span>{e(c["topic"])}</span><a href="#{e(c["id"])}" aria-label="Link to this claim">#</a></div><h3>{e(c["claim"])}</h3><p class="claim-verdict">{e(c["verdict"])}</p><p class="claim-scope">{e(c["scope"])}</p><h4>What the evidence says</h4><p>{e(c["evidence"])}</p><div class="claim-future"><h4>What future projects should show</h4><p>{e(c["future"])}</p></div><details><summary>Limits & sources</summary><p>{e(c["gap"])}</p>{citations(c["sources"])}</details></article>'
    audits = ''.join(f'<article class="article-check"><div><h3>{e(a["claim"])}</h3><span class="claim-verdict">{e(a["status"])}</span></div><p>{e(a["finding"])}</p>{citations(a["sources"])}</article>' for a in data['article_audit'])
    options = ''.join(f'<option>{e(t)}</option>' for t in topics)
    return f'''<section class="page-hero claims-hero"><div class="eyebrow">CLAIMS & EVIDENCE / THE PUBLIC BENEFIT</div><h1>Build more.<br>Know what it delivers.</h1><p>The opportunity is substantial: skilled work, local revenue, more power and useful intelligence. Examine the evidence behind both the benefits and the concerns.</p><div class="claims-jump"><a href="#evidence-review">Explore {len(data['claims'])} claims ↓</a><a href="#article-review">The linked article, checked ↓</a><a href="{base}projects/">Follow the projects ↗</a></div><p class="claim-scope">Reviewed {e(data['reviewed_at'][:10])} · {e(data['reviewer'])}</p></section>
    <section class="section evidence-highlights" aria-label="Sourced indicators of economic benefit">{graphics}</section>
    <aside class="reading-note"><strong>A growing evidence file, not a final verdict on every project.</strong><p>This review covers recurring public claims and the material quantitative arguments in the linked article. Local findings stay local; estimates, forecasts and reported outcomes stay distinct. “Not established” means the evidence reviewed does not settle the claim. Future-project criteria are Stack Ledger’s research recommendations.</p></aside>
    <section class="section" id="evidence-review"><div class="section-top"><div><div class="eyebrow">POWER → FACTORIES → USEFUL WORK</div><h2>The claims, examined.</h2></div></div><form class="claims-controls" hidden role="search"><label>Topic<select id="claim-topic"><option value="">All topics</option>{options}</select></label><label>Search claims<input id="claim-search" type="search" placeholder="Try water, wages or taxes"></label><button type="reset">Clear filters</button></form><p id="claims-count" role="status" aria-live="polite">{len(data['claims'])} claims</p><div class="claims-grid">{cards}</div><p id="claims-empty" hidden>No matching claims. Try another topic or search term.</p></section>
    <section class="section" id="article-review"><div class="eyebrow">SOURCE AUDIT / SEPTEMBER 2026</div><h2>What the jobs article establishes.</h2><p class="section-intro">The BizNews article republishes The Economist. Some headline figures match primary releases; other estimates need underlying datasets and methods. Unresolved items remain visible and are excluded from benefit charts.</p>{citations(['claims-biznews'])}<div class="article-checks">{audits}</div></section>
    <section class="manifesto"><div><h2>Turn the opportunity into receipts.</h2><p>Follow projects from announcement to operation, then measure local hires, paid contracts, tax collections, delivered power and completed work. These outcomes will determine how much reindustrialization reaches the community.</p></div><a href="{base}projects/">Track delivery ↗</a></section><p class="reading-note"><a href="{base}data/claims.json">Download this reviewed evidence file</a> · <a href="https://github.com/reedos/stack_ledger/issues">Submit a claim or correction ↗</a></p>'''
