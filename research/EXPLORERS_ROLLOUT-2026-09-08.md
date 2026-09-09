# Buildout explorers rollout · September 8, 2026

## Implemented and reused

Added a locally served project map, Epoch capability explorer and hyperscaler cash-capex/history comparison. Homepage previews link to the full project and model explorers; capital charts also appear on Infrastructure. Existing homepage featured metrics and runtime/hardware markup, styling, placement and dynamic behavior are preserved.

Data stays in existing reviewed catalogs: optional delivery `map_location`, optional expansion `capital`/`capabilities`, and normal registered metrics/ledger observations. No separate public research database or approval queue was created. Existing discovery/catalog review handles proposals; accepted project changes update map/list counts. Capital observations use the ordinary monitoring/validation path and need reviewed corrections for same-year revisions. Whole ECI snapshots require maintainer review; no automatic ZIP importer is claimed.

Static HTML includes charts, source attribution and accessible tables. Maintained JavaScript adds synchronized filters, map navigation, location inspection, capability selection and uncertainty whiskers. Natural Earth geometry is served locally; map browsing does not contact a tile/geocoding provider. Project details reuse accepted quantity rendering with status, units, period and sources.

## Evidence and coverage

- 50 of 63 projects mapped: 44 U.S. and 6 international records. Distributed or insufficiently located programs remain in the list; no missing capacity is imputed. Census/GeoNames provide locality points, with original project evidence retained.
- Five hyperscalers, 26 actual annual capex records and four CY2026 guidance records. Fiscal years and accounting scope are visible; no misleading aggregate. Oracle's comparison bar is completed FY2026 spending, not calendar-year guidance.
- 264 Epoch ECI scores in a single content-hashed snapshot, including supplied 90% intervals and explicit anchor exceptions. Historical release dates are not evaluation dates.

Amazon and Alphabet's latest guidance remains explicitly attributed to AP original earnings reporting; primary transcript corroboration is a follow-up. No verified later capex outlook was extrapolated. ECI refresh and new geographic assignments remain reviewed maintainer work. The source registry now supports `manual` cadence to exclude archive citations from unattended HTML/text collection, including overdue and focused paths. No publication permission is widened.

## Validation commands

Run `python scripts/validate.py`, `python -m unittest discover -s tests`, `python scripts/evaluate_editorial.py`, `python scripts/evaluate_catalog.py`, and `python scripts/build.py`. Browser acceptance: set `PLAYWRIGHT_MODULE` to an installed Playwright module, then run `node tests/browser.cjs` and `node tests/explorers.cjs`. The latter covers map/list filter agreement, location inspection, zoom, capability filters/intervals/empty states, static fallback and mobile overflow. No inference is needed.

New Python tests check source/manual scheduling boundaries, provenance, unsupported coordinates, actual/forecast separation, revision requirements, later years and uncertainty. Existing publisher restrictions, runtime fixtures and featured selection remain the regression baseline. Generated `docs` are committed with canonical sources.

## Completed local verification

All 238 Python tests passed. Both offline evaluators passed (editorial expectations and disposable catalog apply/publication simulation; no live inference). Both browser suites passed: existing 24-route/three-viewport acceptance plus explorer interactions, static fallbacks and 320/390-pixel overflow checks. The build generated 123 pages. Existing observations, notes, metrics and sources were compared by ID to HEAD with no changes; the additions are 30 observations, nine metrics and 19 sources. Existing project fields are unchanged apart from the added geographic metadata. Runtime/footer markup, dynamic code and rendered homepage footer match the prior version exactly; original regression fixtures remain unchanged. Epoch archive hash matches the accepted snapshot. `git diff --check` passed.
