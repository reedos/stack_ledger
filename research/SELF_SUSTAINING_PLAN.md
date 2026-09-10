# Self-sustaining Stack Ledger · plan of record

Owner intent, September 9, 2026: the site should update itself from daily local-model research and from credible machine-readable datasets, regenerating every page, chart, number and map, with the owner deciding only headline content and figure replacements. This plan states where the pipeline is today, the principles that make hands-off operation safe, the work in priority order, and the definition of done. It is a maintainer document, not model instruction.

## 1. Where the pipeline stands (September 9, 2026, updated for the nightly orchestrator)

Working today, all on `main`:

- Collection: 495 registered sources plus 21 official RSS/Atom feeds as index sources; robots handling per RFC 9309; cooldown health file; contact address in the agent string.
- Extraction and screening: shared evidence and screening rules supplied to the model; quotes snapped to source bytes; numbers checked against evidence; checklist verdicts with defect codes; a model brief (`research/MODEL_BRIEF.md`) behind `runtime.json` `instructions`.
- Publication: commit per finding or per session; preflight validates any pending delta. `publication-policy.json`'s `eligible()` rule was fully coded but, until this change, never invoked by anything scheduled — a person had to run `--apply` by hand. It is now wired: `scripts/nightly.py`'s `policy` stage calls `publication_policy.apply_admitted` every night, so additions from credible authorities (Epoch site records, series, sources, notes) publish without a person, each one a recorded approval with its commit; headline content and figure replacement still need a human. A magnitude sanity rule now also rejects an auto-apply observation whose value falls outside 10x the metric's trailing observed range either way, even from an admitted author.
- Stale-lock recovery now exists. `scripts/nightly.py`'s `locks` stage reads the recorded pid of `.local/research.lock`, `.local/research-session.lock` and `.local/review-candidates/editorial.lock` (ctypes `OpenProcess`/`GetExitCodeProcess` on Windows, `os.kill(pid,0)` elsewhere): a dead pid's lock is removed with a receipt, a live one blocks only the stages that need it and says so, and a lock with no recorded pid at all is removed once it is more than 12 hours old.
- Datasets: Epoch AI data centers, GPU clusters, chip components, chip sales, companies and (added September 9, 2026) Notable AI Models imported as vintage-stamped snapshots with per-site, per-designer and yearly models-layer estimate series; the Epoch Capabilities Index snapshot behind `/explorers/` now refreshes on the same vintage discipline instead of a single hand-run pull; 876+ Epoch-cited primary URLs queued as leads. Census BTOS AI-use share (national plus NAICS 51/54) is a second Census-family importer alongside QCEW/QWI. `scripts/importer_common.py` is the shared apply lane (register/promote/validate/save/build) the four direct-apply importers now call, each landing as a recorded `importer_apply` receipt in the same event log the panel reads.
- One nightly orchestrator: `scripts/nightly.py` is now the OpenClaw job's only entry point, `30 1 * * *` Pacific with a six-hour ceiling (`scripts/schedule.py`). Time budget decision: pre-stages (`locks`, `importers`) get at most 25 minutes so the model research session still starts by 02:00; the session keeps its own 2-7 AM Pacific window unchanged (`research_loop.py --overnight`); post-stages (`policy`, `health`, `prune`, `digest`) run after the session returns, inside the remaining cron ceiling. Each stage writes its own receipt (`.local/nightly/<date>/<stage>.json`), commits at most once, and a failed stage is recorded and skipped rather than stopping the night; the run always ends with a digest sent through the existing Telegram route.
- Disk: F2 is rescoped to its real driver. `.local/catalog-previews` was 615 of 828 MB (74%), not `.local/evidence`/`.local/epoch` as this plan originally named; the `prune` stage now deletes a package's preview folder once its last editorial event is `applied` or `rejected` and at least 7 days old, reports bytes freed, and never touches evidence, receipts or hashes.
- Deployment verification gap closed: `catalog_review.publish_package`'s 90-second deploy-check can time out on a slow Pages build, leaving a package `deployment_pending` with a real pushed commit but no `applied` event — invisible in the panel's default view even though it is already live. `catalog_review.verify_pending_deployments` (also reachable as `python scripts/catalog_review.py --check-deployments`) finishes that one check against the live data on the next run; the `policy` stage calls it every night, after `apply_admitted`.
- Chip capacity: `scripts/chip_capacity.py` turns a reviewed configuration (`research/chip-capacity.json`) into one capacity metric per configured chips project (wafer starts, advanced-packaging wafer starts or HBM stacks per month), with an illustrative Epoch-ratio compute equivalent shown only once a base figure is disclosed; every project starts at zero observations and the daily monitoring lane attaches disclosures independently.
- Review surface: Research Control panel with inline previews, status toggles, bulk actions, applied-package outcomes, and a launcher that reuses a live server.

Known weaknesses that remain:

1. Metric conflicts: a second value for a metric-year is a conflict unless the metric has a period basis. 204 of 276 observed metrics already hold a 2026 value, so monitoring yield is capped by design. Quarter and snapshot bases exist in the validator but no existing metric uses them, and charts plot one point per year.
2. Chart, map and company-page rendering are hand-configured: headline metrics are named in `homepage.json` and `catalog.json`, map pins need reviewed coordinates, company pages show revenue only.
3. Discovery still routes through GDELT, which fails most of the time. Feeds are registered but the discovery lane does not yet prefer them.
4. Panel servers accumulated because each launch started a new one; fixed today, but the tailnet server is still the old process.
5. Instruction changes invalidate every cached review; `screening_version` is manual.
6. GPU contention is live, not hypothetical: the production research session still runs with `--ignore-gpu-busy` (now configurable per night in `research/importers.json`'s `research_ignore_gpu_busy`, defaulting to today's flag), and nothing here can see whether another OpenClaw/Ara job is scheduled inside the 2-7 AM Pacific window. **Owner action:** confirm no other OpenClaw job runs 02:00-07:00 Pacific on this machine before relying on the dedicated window; a local plan cannot verify another tool's cron configuration.
7. The model does not join `publication-policy.json`'s `auto_apply.authors` allowlist until a real precision/recall calibration gate clears an owner-set floor (D5, expanded to score every labeled case against its ground truth, not today's 2-of-8 tool). Today only `"Epoch import (maintainer tool)"` is listed, and that stays true after this change; QCEW and QWI do not need the allowlist because they write directly, following Epoch's own maintainer-tool pattern, not through the model.
8. E3's kill switches already exist and are documented, not new work: `.local/stop-research-loop` halts the `research` stage (`scripts/nightly.py` checks it before starting `research_loop.py`); `research/publication-policy.json`'s `auto_apply.enabled:false` halts the `policy` stage the same way, without stopping collection.

## 2. Principles for hands-off operation

- Structured data beats scraped prose. Every quantity that a credible authority publishes as a table or API is ingested by an importer with a vintage and a hash, never by the model reading a page.
- The model reads what has no table: announcements, filings prose, milestones, constraints. Its output is validated deterministically before a second model pass, and both passes are told the rules they will be judged by.
- Additions apply automatically. Replacements need a person. "Replacement" means changing a figure already displayed, a headline, a metric definition, a source permission or a company or product object.
- Every automatic action is a recorded event with the rule that admitted it, and every night ends with one commit per stage and one digest that lists only decisions a person must make.
- Failure is loud and self-healing where safe: stale locks from dead processes clear themselves; unreachable sources cool down; a failed stage does not block the others; the deployed site is verified against the data after every publish.
- Presentation follows data. Charts, maps and cards read their configuration from the catalog, not from code, so new series and new sites appear without an edit.

## 3. Work plan, in priority order

Effort is in maintainer-hours. "Owner" marks items that need a decision from the owner beyond approving the code.

### Phase A · One nightly orchestrator (this week, ~6 h)

A1. `scripts/nightly.py` runs the night as stages, each with its own lock, timeout, receipt and single commit: (1) dataset importers due tonight; (2) feed and registry maintenance; (3) the model research session; (4) publication-policy application; (5) health and stale-figure report; (6) digest. A failed stage is reported and skipped, not fatal. The OpenClaw job calls this one script.
A2. Stale-lock recovery: any `*.lock` whose recorded pid is dead is removed with a receipt; a live pid blocks as today.
A3. Importer schedules in a reviewed `research/importers.json`: Epoch weekly on its publication day, EIA and BLS on release calendars, SEC filings daily for directory companies (XBRL companyfacts API, no scraping), IEA and Census on release.
A4. Deployment verification after every push already exists for catalog packages; apply the same check to the session commit, and retry the push once before reporting.

### Phase B · Structured authorities first (~10 h)

B1. Importers, each following the Epoch pattern (download, hash, vintage, snapshot, promote, leads): SEC XBRL companyfacts for annual and quarterly revenue and capex of every directory company with a CIK; EIA electricity generation, capacity additions and the 860M generator inventory; BLS occupational employment for electricians and construction; Census construction spending; FERC and ISO interconnection queues where a CSV is published (ERCOT large-load list, PJM queue export). **Delivered in part, September 9, 2026:** two more importers reached this pattern — Epoch Notable AI Models (`import_epoch.py notable-models`, three yearly models-layer series) and Census BTOS AI-use share (`import_btos.py`, applications layer, national + NAICS 51/54) — reusing the exact registered Census API host/key infrastructure QWI already has. **SEC XBRL companyfacts: done, September 9, 2026.** `import_sec.py` covers the 13 ecosystem companies whose `filings_jurisdiction` is exactly `SEC` (nvidia, amd, intel, micron, microsoft, alphabet, meta, marvell, tesla, constellation, merck, moderna, recursion), adding quarterly and annual revenue/capex as new company-attributed series alongside the existing curated revenue records, never replacing them; foreign private issuers (tsmc, asml, nebius, alibaba, Form 20-F) and aws (no reviewed `amazon` parent entity yet) are skipped and reported, as scoped. Built, unit-tested (12 tests against a realistic companyfacts fixture) and registered in `research/importers.json` (weekly); the live `--apply` run itself did not complete this session because SEC's Akamai edge returned HTTP 403 to every request from this machine's network connection, confirmed independent of the importer's own code with plain `curl` — a network-environment limitation, not a code defect; run it for real once the host is reachable. **EIA: built and tested, pending an owner-registered key.** `import_eia.py` covers monthly all-fuels net generation, monthly generator-capacity additions by energy source, and a machine-readable STEO generation outlook; every route needs an EIA API v2 key, none exists in `.local/api-keys.json`, so the importer prints the registration URL and exits 0 without a network call, exactly as scoped, and its record-building logic is unit-tested against hand-written fixtures pending a live pull to confirm the exact facet/column shapes. BLS occupational employment, Census construction spending and FERC/ISO queues remain not started.
B2. Refresh semantics for series: a new vintage of the same source and metric supersedes the previous snapshot automatically, keeping history, because nothing a person chose is replaced. **Delivered, September 9, 2026, at the direct-import layer** (not as a `publication-policy.json` rule, which governs the separate catalog-package/human-review lane): `scripts/importer_common.py`'s `apply_changes()` upserts observations by id, so a later run's revised reading for the same period replaces rather than duplicates, and `import_epoch.py promote()`'s wholesale-replace-per-vintage already did this for the quarterly chip-supply series. Publication-policy-governed catalog packages (the Epoch site-addition/capacity lane) still refresh one human decision at a time; extending "same-source refresh" to that lane is unstarted.
B3. Company revenue and capex switch from curated annual records to the SEC importer where a filing exists; curated records remain for private companies and non-filers. This retires most of the "38 revenue records" hand maintenance. **Owner:** confirm that filing figures replace curated ones for filers.
B4. Epoch imports move to the orchestrator: weekly data centers and GPU clusters with reconciliation and capacity records; monthly chip components, chip sales and companies. Ambiguous matches accumulate in one weekly review item instead of appearing per site.

### Phase C · Presentation follows data (~12 h)

C1. Per-period charts: the shared chart renderer plots quarter and snapshot series correctly (multiple points per year, x-axis by date), so periodic metrics can be displayed and existing yearly metrics can adopt a basis where sources publish more often. **Owner:** which existing metrics become quarterly or snapshot.
C2. Card configuration in the catalog: each layer's headline slot, supporting metric and per-company output metric live in `homepage.json` and `ecosystem.json` (the company `output_metric` field is added in this cycle). The editorial recommender proposes headline changes; a person approves them in the panel. No card label lives in code.
C3. Map from data: projects with an address but no coordinates are geocoded by a reviewed importer against the Census geocoder for U.S. addresses and GeoNames for others, both already used as map sources, with precision recorded. Pins appear for every accepted project automatically. **Owner:** approve the two geocoding hosts.
C4. Company pages render output, capacity, contracts and jobs from records linked to the company, with revenue as one section among several.
C5. Layer pages list every metric in the layer from the catalog, grouped by measurement type, so new series appear without a template edit.

### Phase D · Model research that pays for itself (~8 h)

D1. Discovery reads feeds first: new feed entries are the discovery queue; GDELT is a fallback capped at a handful of searches per night.
D2. Stale-figure tasks: metrics whose latest record is older than their expected cadence produce targeted research questions for the model (source, metric, last period), replacing the broad topic rotation.
D3. Private notes for sources without excerpt permission are surfaced in the panel and, when a source has produced three accepted-quality notes, the digest proposes excerpt permission for that source. **Owner:** approve or reject in the panel.
D4. Switch `instructions` to `brief` after the owner and Astra review the brief; keep the full guide for maintainers. Bump `screening_version` from the orchestrator when the brief or validators change, so cache invalidation is deliberate and logged.
D5. Weekly calibration: replay saved quarantines through the validators (exists) and replay 20 frozen documents through the model with expected outcomes; report precision and recall in the digest; never relax validators to raise yield.

### Phase E · Oversight that fits in five minutes (~4 h)

E1. One weekly digest, Telegram plus a panel page: what applied automatically (counts and links), what needs a decision (headline candidates, figure replacements, ambiguous site matches, new source hosts), health (sources cooling, failures by host, model precision), and what changed on the site.
E2. Panel: a "Decisions" tab that shows only items needing a person, with bulk actions; everything automatic is in a log tab.
E3. Kill switches: `.local/stop-research-loop` already halts research; add `publication-policy.json` `enabled:false` to halt automatic publication without stopping collection.

### Phase F · Hardening (~4 h)

F1. Retire the stale tailnet panel server and start it from the orchestrator so it always runs current code.
F2. Disk: prune `.local/evidence` and `.local/epoch` archives older than 90 days that no accepted record references; keep hashes.
F3. CI runs the full suite nightly against `main`, not only on push, and the digest reports a red CI.
F4. Tests for every importer using saved fixtures; a fixture refresh command with a diff so upstream format changes are caught before a live import.

## 4. What the owner still does

- Approve or reject headline changes and figure replacements the recommender proposes, in one weekly sitting.
- Confirm ambiguous site matches and new source hosts when the digest lists them.
- Read the brief and the constitution amendments when they change.
- Nothing else. Collection, extraction, validation, dataset refreshes, additions, charts, maps, company pages and deployment run without a person.

## 5. Definition of done

- Seven consecutive nights complete every stage with no manual command and no stale lock.
- Every quantity on the site traces to an importer vintage or a validated model record with source hash; no hand-entered figure remains for a metric that a registered dataset covers.
- The weekly digest lists fewer than ten decisions and each takes under a minute in the panel.
- New Epoch sites, SEC filings and EIA releases appear on the site within one nightly cycle of publication, with estimates labelled as such.
- Charts render periodic series; the map shows every accepted project with a location; company pages show output and capacity alongside revenue.

## 6. Sequence and estimate

Phase A first, because everything else needs the orchestrator to be hands-off. Then B1 to B3 (SEC and EIA carry most of the site's numbers), then C1 and C2 (so the new series are visible), then D, then E and F. About 44 maintainer-hours in total; roughly two weeks of sessions like today's, after which the owner's role is the weekly sitting in section 4.
