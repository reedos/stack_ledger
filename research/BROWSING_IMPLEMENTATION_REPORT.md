# Browsing and mobile design revision

Implemented the reviewed navigation and page-organization recommendations without changing accepted evidence, featured metrics, source permissions or the runtime/footer contract.

## Changes

- A keyboard-accessible mobile menu replaces compressed navigation links. Destinations have at least 44-pixel-tall touch targets; Escape returns focus to the menu button. Claims & Evidence is in primary navigation. Without JavaScript, navigation remains expanded and usable.
- Shared presentation controls paginate Companies (12), Projects (8), research notes (8), observations (12), research runs (8), source-library entries (12) and company source-book rows (10). Existing collection filters and full exports are retained. Changing a filter resets the corresponding page. All matched records remain available through the controls.
- Company cards retain their role, revenue basis, value, period and profile link; additional scope/source details can expand. Project cards retain stage, owner, location, the first scoped quantity and latest evidence; additional quantities and specifications expand separately. No values or measurement bases are combined.
- Stable evidence IDs now anchor ledger observations and notes. Deep links reveal the correct result page and open ancestor disclosures. Existing company, project and topic anchors remain intact.
- Layer introductions still lead directly into the approved colored diagrams. Tracked indicators follow prominently, with section navigation and expandable contributor groups. Model releases, open builders and subscriptions have a clearer order; AlphaFold is prominent in Applications. Detailed topic sections without charts can expand, with their original evidence intact.
- Jobs & Industry leads with trades, construction and workforce evidence before recruitment examples. Claims retain verdict and scope visibly, with further evidence and sources expandable. Methodology gains source search and pagination.

Implementation lives in `site/assets/browsing.js` and `browsing.css`, loaded by the existing template. Existing renderers, filters, data loaders, charts and exports are reused. This is progressive enhancement: it limits visible results, not downloaded dataset size or initial DOM creation. No performance benchmark or server-side pagination is claimed.

## Research workflow

The operating guide and editorial recommender instructions now explicitly require the full canonical datasets for coverage and recommendation. Collapsed or paginated records are not coverage gaps or editorial rejections. New research still uses the existing structured queues; the model cannot add page sections, change browsing controls or approve its own display changes. UI changes do not advance research timestamps. The public methodology also explains the separately bounded private discovery lane. No new schema, schedule, permission or inference task was needed.

## Verification

`python scripts/validate.py`, all 146 Python tests, and `python scripts/evaluate_editorial.py` passed. The build generated 107 pages. Browser acceptance covers 24 routes at three viewport sizes, plus new checks for mobile menu touch targets and keyboard focus, no-JavaScript navigation, pagination and filter resets, record/project deep links, expanding contributor groups and source search. Existing revenue, forecast, chart, diagram, keyboard and runtime regressions remain in the suite.

At the same 390-pixel-wide review viewport, default page heights changed approximately as follows: Companies 66,814 to 11,473 pixels; Projects 58,925 to 13,685; Ledger 184,213 to 8,703; Methodology 53,470 to 8,399. These are measurements of the current rendered snapshot, not guarantees as future evidence grows. Full evidence remains available. The homepage opening and approved featured metrics are preserved.

No research loop, GPU inference, source registration or factual data migration was performed. The runtime rendering function, footer markup and protected existing styles remain unchanged. Publication/commit status should be checked in Git rather than inferred from this implementation report.
