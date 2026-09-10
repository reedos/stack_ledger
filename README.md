# Stack Ledger

**A public ledger of the AI buildout.** Energy → chips → infrastructure → models → applications. Global coverage with a U.S. focus, 2030 as the main horizon, and explicit longer-term targets.

**[Read the site](https://reedos.github.io/stack_ledger/)** · [Research constitution](research/CONSTITUTION.md) · [Methodology](research/METHODOLOGY.md) · [Public dataset](site/data/ledger.json)

## Our premise

AI can help reindustrialize America: abundant power and domestic manufacturing support AI factories, models and agent systems; useful applications can turn that capability into business productivity, physical work and discovery. We follow the opportunity from local investment, purchasing and jobs to digital workers, productive robots, medicine, engineering, climate research and clean energy.

This is our guiding ambition, tested against evidence. Announced investment is not delivered capacity, a robot demo is not an operating workforce, and a promising drug candidate is not a patient outcome. The constitution directs the daily researcher to look for these connections without inventing benefits or suppressing constraints.

## What is included

- An expanding company directory with annual revenue records, annualized run rates and explicit revenue coverage gaps, each linked to its own reviewed observation; see the [live company directory](https://reedos.github.io/stack_ledger/companies/) for current counts. Product-role sources are linked separately.
- A searchable datacenter component map covering compute, memory, DSPs, SerDes, copper, optical modules, CPO, fiber, switching, assembly and electrical infrastructure.
- Electrical workforce evidence and clean-energy manufacturing cases, distinguishing reported employment, projected openings, hiring plans and investment stages.

- An original interactive five-layer illustration, responsive landing page and five dedicated dashboards.
- Attributed observations, forecast charts, explicit units, accessible data tables, research notes and a source library.
- Search, layer filters, CSV and JSON downloads, an Atom feed and correction links.
- A daily Ollama research runner scheduled by OpenClaw. Model proposals pass deterministic validation and a separate evidence-screening pass before publication. The monitoring lane can append screened automated observations once accepted; as of September 2026 the published ledger holds none yet, only nine automated research notes (see Automated updates in the methodology).
- A public runtime line showing the model, owner-reported hardware, actual last attempt, last successful complete research run and source failures.

The initial dataset is curated from IEA, DOE/LBNL, Stanford HAI, TSMC and Microsoft. It is a starting collection, not a complete accounting of global AI capacity. The charts retain their observation periods; historical prices or forecasts are never presented as current measurements. Every layer explains the next research priorities and known gaps in target tracking.

## Local development

Requires Python 3.11+; the application and research pipeline use the standard library. Node is only needed for optional browser verification and the installed OpenClaw CLI.

```powershell
python scripts/validate.py
python -m unittest discover -s tests
python scripts/build.py
python -m http.server 4173 --directory docs --bind 127.0.0.1
```

Open http://127.0.0.1:4173. Website source is in `site/`; `docs/` is the deterministic GitHub Pages build. GitHub Pages serves `main:/docs`, with `.nojekyll`. All links support the `/stack_ledger/` project prefix and direct visits to individual layer pages. There are no runtime server services or API keys in the public site; analytics are optional and controlled entirely by `site/analytics.json` (see Website analytics below). Google Fonts is optional; system font fallbacks work offline.

The homepage hero, isometric layer links, five evidence cards, navigation and runtime footer are rendered into HTML by `scripts/render.py`. Charts and directory filters progressively load in the browser. The static snapshot and raw-data links remain usable without JavaScript or after a data-request failure. The reviewed stack artwork lives in `site/partials/stack.html`.

Headline cards retain metric scope, units, periods, status and publisher. Applications deliberately shows a research gap until a measured-outcome metric is reviewed; the adoption survey remains in the applications research. Reindustrialization is a question below the evidence, and government targets, company commitments and independent projections retain separate books.

Daily builds refresh these deterministic HTML snapshots from the ledger. The publisher permits only the reviewed generated page paths in addition to ledger JSON and the feed; it cannot change source templates, navigation, styles, metric definitions or governance. Browser acceptance checks the homepage with JavaScript disabled, failed dataset requests and keyboard navigation as well as all routes at three viewport widths.

## Research runtime

Configuration lives in [`research/runtime.json`](research/runtime.json):

- Ollama model: `muse-glimmer:30b-q4_K_M-dflash` (public label: muse glimmer:30B dflash).
- Endpoint: `http://127.0.0.1:11434`, reachable only on the local host.
- Scheduler: OpenClaw runs `scripts/nightly.py` daily at **01:30 America/Los_Angeles**, following Pacific daylight-saving changes. The model research session itself keeps its own **02:00-07:00** window unchanged (`research_loop.py --overnight`); the earlier start gives the orchestrator's pre-research stages up to 25 minutes.
- Hardware: Ryzen 9 9950X3D, RTX 5090, 64 GB DDR5 (owner-provided configuration).
- At most 24 documents, one discovered link per approved source page, bounded context, bounded generation and network timeouts. Unchanged successfully screened documents reuse their recorded content hash.
- Generation requests a 32,768-token context. The runner refuses a prompt that would not fit, shrinks the document window to fit first, and fails closed if `/api/ps` shows the model already loaded with a smaller context by another process. Measured prompts reached 16k–20k tokens under the earlier 16,384 setting and survived only because the keep-alive had loaded the model larger.
- `python scripts/replay_quarantine.py` re-runs retained quarantines through the current deterministic evidence checks without any model call, to measure validator changes before a live session.
- `python scripts/evaluate_extraction.py --documents 24 --seed 1` replays saved `.local/evidence` documents through the same extraction and screening code paths offline (no fetch, publication or ledger write) and writes a `report.md` for a human grader plus a `grades.template.json`; `--grade` turns filled-in grades into `scored.md` with accepted-record precision and validator/reviewer false-reject and false-accept rates, to measure whether the model can do the task before changing a prompt or validator to chase yield.
- `instructions` in `runtime.json` chooses `full` (constitution and operating guide) or `brief` (`research/MODEL_BRIEF.md`) as the model's system instruction. Since September 10, 2026, a private review ledger (`.local/reviews.json`) replaces the old single-identity cache with two independent lane identities: `metric_rules_version` and `note_rules_version` (runtime.json), each bumped only when that lane's own prompt or validator changes meaning, so a note-rules bump never forces a re-review of the metrics lane or vice versa. See OPERATING_GUIDE.md for the full mechanism, including conditional fetches (ETag/Last-Modified, a 304 costs no download or model call) and adaptive per-source cadence.
- `python scripts/registry_lint.py --retire-dated` prints dated one-off document sources (a report or press release, never a rolling reference page) that are candidates for `cadence: manual`; `--apply` writes exactly that cadence change, a reviewed, maintainer-run action never invoked automatically.
- Publication happens when a batch accepts a finding and once more in the session's closing summary. Receipts-only batches leave their output in the working tree; preflight validates that pending delta before any push. `research.py --publish --flush` pushes it on demand.
- robots.txt handling follows RFC 9309: a 4xx response permits crawling and is recorded in the collection health file; 429, 5xx and HTML challenge pages fail closed. The agent string carries a contact address as SEC and BLS require.
- `python scripts/import_epoch.py all` downloads Epoch AI's CC BY datasets (data centers, GPU clusters, chip components, chip sales, companies, Notable AI Models, the AI Benchmarking Hub), keeps a vintage-stamped snapshot under `research/epoch/`, writes a data-center reconciliation report against the projects catalog (matches, proposed additions, accepted projects without an Epoch row), exports Epoch's cited primary sources as private discovery leads, and cross-checks Epoch revenue reports. `--apply` registers the dataset sources and promotes the reviewed quarterly and yearly series as estimates, including Notable AI Models' three yearly series (models released, largest training compute, models at or above 1e25 FLOP) into the models layer, and mechanically refreshes the Epoch Capabilities Index snapshot behind `/explorers/` from the same archive. Per-site "current" records use Epoch's own status-table reading date as the period when this vintage's archive states one (the dataset pull date otherwise, with the note saying so) -- never the dataset pull/publish date alone, which is only a refresh timestamp, not a measurement date. Epoch figures are estimates and are labelled as such; a new vintage replaces a series through this importer, never by appending competing values, and a corrected reading date for an already-published record is queued as a `catalog_change` package (`--enqueue-period-corrections`), never written in place. Additions that meet `research/publication-policy.json` (new objects only, from a policy-listed tool, evidence on registered rank-1/2 hosts, passing preview) are published by `python scripts/publication_policy.py --apply` without per-item review and recorded as approvals by "publication-policy"; everything else waits in the panel. Accepting the reconciliation is two steps: `--confirm-suggested-matches` (with `--reject "Epoch name"` for wrong pairings) records site aliases in `research/epoch/aliases.json`; `--enqueue-additions --min-mw 100` drafts unmatched Epoch sites as status-unverified projects in catalog packages, which are then validated, approved and applied from the Research Control panel's Review tab like any other catalog change.
- `python scripts/import_qcew.py --apply` imports BLS Quarterly Census of Employment and Wages open data (public domain) for NAICS 518210 data processing and hosting and 238210 electrical contractors: quarterly private employment for every county where an accepted project has a reviewed county location, plus the national total, from 2024 Q1 onward. Suppressed quarters are omitted, never zero. `python scripts/import_qwi.py --apply` adds Census QWI stable hires and average monthly earnings for the same counties at the 4-digit industry level through the Census Data API under the owner's registered key (`research/api-access.json`, keys in `.local/api-keys.json`). Project cards in those counties show a "Local labor market" block with employment and its year-earlier change, hires and earnings; measured county jobs sit beside the project's own promised and reported figures without being attributed to it. `python scripts/import_btos.py --apply` adds the Census Bureau's Business Trends and Outlook Survey AI-use share (public domain): a national applications-layer metric plus NAICS 51 (Information) and NAICS 54 (Professional, Scientific and Technical Services) sector breakdowns, one snapshot per published biweekly reference period. BTOS is not in the keyed Census API's dataset catalog, so this reads the small public JSON files behind the BTOS data page's own chart directly, robots-checked, the same way `import_epoch.py` reads Epoch's downloads.
- `python scripts/import_sec.py --apply` imports SEC EDGAR XBRL company facts (public domain) for the ecosystem companies whose `filings_jurisdiction` is exactly `SEC` (U.S. domestic 10-K/10-Q filers: nvidia, amd, intel, micron, microsoft, alphabet, meta, marvell, tesla, constellation, merck, moderna, recursion). It adds new, company-attributed quarterly and annual revenue and capex series (`sec-revenue-<company>-{quarterly,annual}`, `sec-capex-<company>-{quarterly,annual}`) built from SEC's own deduplicated, period-aligned `frame` values (`CY2025Q4`, `CY2025`) -- never the existing curated annual revenue records, which stay sourced from stockanalysis.com until a later reviewed step chooses between them. CIK lookup goes through SEC's own `company_tickers.json` against a reviewed ticker map (`research/sec-companies.json`), so it fails loudly rather than guessing on a missing ticker. Foreign private issuers (tsmc, asml, nebius, alibaba) file Form 20-F annually, not 10-Q, so XBRL companyfacts cannot give them this importer's cadence; they are skipped and reported, as is `aws` (no reviewed `amazon` parent entity exists yet in `research/ecosystem.json` to attach Amazon's consolidated filings to without misattributing them as the AWS segment). `python scripts/import_eia.py --apply` is the EIA API v2 counterpart (monthly all-fuels net generation, monthly generator-capacity additions by energy source, and a machine-readable STEO generation outlook alongside the PDF-curated `us-utility-generation-history`); every route in EIA's v2 API needs a registered key, so with none in `.local/api-keys.json` this importer prints the registration URL and makes no network call at all, exiting 0. Both hold to the shared `api_access.fetch` host throttle and the ≤4 requests/second ceiling the owner set for SEC's keyless fair-access paths.
- `scripts/importer_common.py`'s `apply_changes()` is the shared lane `import_qcew.py`, `import_qwi.py`, `import_sec.py`, `import_eia.py`, `chip_capacity.py` and `import_epoch.py`'s apply path all call: register a source, add or replace catalog metrics, land observations, validate the whole ledger with restore-on-failure, save and rebuild. Every successful call also appends a receipt (importer, sources/metrics/records touched, snapshot hashes, invoking account) to `.local/review-candidates/editorial-events.jsonl` as an `importer_apply` event, so a direct-lane import -- one that publishes without per-record human review, unlike a catalog package -- is still a recorded, panel-visible action (surfaced under `importer_events` in the findings-review payload).
- Sources with neither a metric link nor excerpt permission are still read; their notes stay private in `.local/review-candidates/`. `python scripts/registry_lint.py` lists them and the sources that fail most often. `python scripts/find_feeds.py` discovers and validates official RSS/Atom feeds for directory companies; `--register` adds eligible feeds as daily index sources (a reviewed registry change). Feed/index sources win a batch-queue tie over other due sources and read up to `max_discovered_per_feed` (runtime.json, default 12) new entries per run, versus `max_discovered_per_source` (1) for an ordinary page's own child-page discovery.
- `python scripts/nightly.py` is what the scheduled job actually calls: stale-lock recovery, the importers due tonight per `research/importers.json`, the research session above, `publication_policy.py`'s auto-apply plus `catalog_review.py --check-deployments`, a health/stale-figure report, preview pruning and a digest, each stage timed and receipted under `.local/nightly/<date>/`. `python scripts/nightly.py --dry-run` prints the plan without changing or writing anything; `python scripts/nightly.py --only <stage>` runs one stage by hand. See [the operating guide's "Nightly orchestrator" section](research/OPERATING_GUIDE.md) for receipts, the digest, and the rollback runbook.

The machine must be awake, with Ollama and the OpenClaw gateway running, and GitHub credentials available to the account running OpenClaw. This project does not change your other OpenClaw jobs or deliver messages to chat channels. After a missed or interrupted schedule, use the manual command below; do not assume a missed run will be replayed.

```powershell
# Dry run: propose updates into .local/ without changing the site or Git.
python scripts/research.py

# Save validated research and regenerate the site locally.
python scripts/research.py --apply

# Full daily operation: research, validate, build, test, commit and push.
python scripts/research.py --publish

# Inspect the scheduler configuration, or install it idempotently.
python scripts/schedule.py
python scripts/schedule.py --install
```

The daily job invokes the maintained Python runner as a command. Ollama extracts evidence inside that runner; the model is never given arbitrary shell or Git access. No paid search API is required. Public HTML sources are read directly; robots rules, paywalls, HTTP restrictions and oversized documents are respected. Index pages enable bounded discovery of current articles on approved hosts. Add source domains and new quantitative measures through reviewed catalog changes.

The model emits JSON using [Ollama structured outputs](https://docs.ollama.com/capabilities/structured-outputs). The adapter handles the DFlash model’s observed literal trailing end-of-turn marker without repairing malformed JSON. Two passes of the same model are fallible screening, not independent fact-checking. Public automated records have source links, retrieval times and evidence hashes; full fetched text and candidate evidence stay in ignored `.local/evidence/`.

## Publication boundaries

Daily publication changes only approved ledger/excerpt data, the feed and the maintained generated HTML pages. The exact boundary is enforced by `ALLOWED_CHANGES` in `scripts/research.py`. The reviewed catalog and source registry must match public data. Newly discovered **public** source URLs must retain an approved host and publisher. The private discovery lane can investigate unfamiliar public hosts under a separate reviewed collection policy; those findings cannot be published until the source and relevant definitions receive human review. The agent may add approved-source numeric observations and screened research notes. It cannot change templates, code, metric definitions, targets, source policy or its constitution.

The publisher requires a clean working tree, the exact expected repository and branch, no unexpected staged or untracked files, passing integrity tests and an ordinary fast-forward push. It stops on divergence and never force-pushes. GitHub code changes should be made through reviewed pull requests; this local publisher enforces its own narrower file boundary even though the owner’s Git credential can access other files.

Source failures produce a **partial** run when usable research remains. A model failure or zero usable documents produces **failed**. Only a complete run covering all five layers without source failures advances `last_success`. Validated findings from an otherwise partial run can still publish. Run receipts record the scope actually checked. A no-change day is a valid outcome; numbers and stories are never invented to fill the feed.

## Recovery and maintenance

- **Quarantined proposals:** Inspect `.local/runs/` and `.local/evidence/`. Conflicting metric/year values need reviewed corrections; never overwrite history silently.
- **Interrupted run:** `.local/research.lock` contains a PID and start time. Verify that process has stopped before removing that specific lock file. Concurrent invocations fail closed.
- **Push failed after commit:** The next invocation can retry exactly one pending daily commit after checking its file list and data. Other local commits or divergence require manual synchronization.
- **Interrupted local apply/build:** Inspect `git diff`, run validation, tests and build, then commit the reviewed data changes or restore only those known generated/data files. The daily publisher will stop on the dirty tree.
- **New sources or measures:** Edit `research/sources.json` or `research/catalog.json`, update their copies in the public ledger, add sourced evidence and run checks through a reviewed change. Never let the daily model widen its own scope.
- **Corrections:** Retain the original observation, set its `superseded_by`, and add a replacement with `correction_of` and `correction_reason`. Charts hide superseded points; the raw data and Git history retain them.
- **Daily errors:** Inspect the OpenClaw job run history and `.local/runs/`. Preflight or network-push failures can only be reported locally if publishing is unavailable; the existing public run timestamp will remain unchanged.

## Repository map

| Location | Purpose |
| --- | --- |
| `site/` | HTML template, original SVG artwork, CSS, interactive chart and page renderer |
| `site/data/ledger.json` | Published, versioned research records and runtime receipts |
| `research/` | Constitution, methodology, reviewed metrics, source registry and runtime configuration |
| `scripts/research.py` | Retrieval, discovery, model extraction, screening and controlled publication |
| `scripts/nightly.py` | Nightly orchestrator: locks, importers, research, policy, health, prune, digest |
| `scripts/validate.py` | Data invariants, source boundaries and integrity checks |
| `scripts/build.py` | Reproducible static pages, feed and sitemap |
| `scripts/schedule.py` | Idempotent OpenClaw command-job installation, now scheduling `nightly.py` |
| `research/importers.json` | Reviewed cadence and CLI for each maintainer dataset importer |
| `tests/` | Meaningful integrity and runner regression tests |
| `docs/` | Committed static GitHub Pages output |
| `.local/` | Ignored evidence, proposals, caches, run logs and local screenshots |

## Attribution and license

The organizing concept is inspired by [Jensen Huang’s five-layer AI framework](https://blogs.nvidia.com/blog/ai-5-layer-cake/). Stack Ledger is independent and unaffiliated with NVIDIA. Site code and original graphics are MIT licensed. Original source content retains its rights; factual records preserve attribution. IEA material is attributed under its stated CC BY 4.0 license where applicable. This repository does not redistribute complete source articles.

## Energy and infrastructure delivery

The `/projects/` tracker follows a growing set of selected projects across generation, storage, transmission and AI infrastructure; see the [live tracker](https://reedos.github.io/stack_ledger/projects/) for the current count. Filter by stage, layer, owner or location. Each card separates reported quantities from plans, retains an evidence timeline, records grid context and identifies the next missing evidence. The site also includes new research on accelerator delivery, HBM, packaging, model reliability, inference price-performance, workplace productivity and scientific prediction.

Tracker definitions live in `research/delivery.json`; numeric evidence lives in the main ledger. Validate with `python scripts/validate_delivery.py` (also run by the build). Stages are reviewed snapshots, while the daily runner can append screened observations and notes. For a fresh, focused local research pass: `python scripts/research.py --apply --refresh --max-documents 6 --sources fervo-q2-2026 eia-additions-2026 aws-delivery-2026`. Use `--publish` instead of `--apply` only with a clean working tree. A focused pass may be partial because its coverage is intentionally limited.

## Chip capacity quantification

Every chips-layer project card (fabs, packaging sites, HBM plants) shows a capacity quantification tied to compute, not a bare "not quantified" placeholder. `research/chip-capacity.json` is a reviewed configuration: four measurement classes (logic fab, advanced packaging, HBM packaging, memory fab), the Nvidia GH100 (H100) reference die used for the logic-fab conversion, and one entry per configured project naming its class, node/scope, company and the registered sources being watched for a disclosure. `scripts/chip_capacity.py` turns that configuration into one metric per configured project (id `{project}-capacity`), following the same save/validate/register/rebuild pattern as `scripts/import_qcew.py`; run it with `--apply` to register the reference-die source, create or update the metrics and rebuild. Two chips projects are deliberately excluded: the TSMC Arizona program envelope (capacity is tracked per phase, not at the program level) and GlobalFoundries Singapore (no reviewed company entry yet, so no metric).

Where a project has no disclosed base figure, the card states that plainly, names the figure that would quantify it (for example "wafer starts per month by node") and links every source being watched — unknown is not zero, and nothing is invented. Where a base figure exists, the card adds an illustrative compute equivalent, always labeled as illustrative: advanced-packaging wafer starts convert to accelerators/year and H100e/year using Epoch AI's latest Nvidia CoWoS-consumption and cumulative-shipment ratios; logic-fab wafer starts convert to a gross-die-per-wafer ceiling (perfect yield, full allocation to one reticle-scale accelerator die) using the H100 reference die. Memory fabs and HBM packaging sites show the base figure only, with a sentence on why no compute conversion is offered (stack height, die size and yields per generation are undisclosed). No project's compute equivalent is summed into a site-wide total. The conversion functions are pure and DOM-free in `site/assets/chip-conversions.js`, unit-tested under `node:test` in `tests/chip_conversions.cjs`, and exercised end to end (including the refusal of an unknown project or an unregistered source) in `tests/test_chip_capacity.py`.

## Company and industry research

The company directory covers a growing set of representative businesses across the five layers; see the [live company directory](https://reedos.github.io/stack_ledger/companies/) for the current count. Company roles and jobs/factory snapshots are reviewed metadata in `research/ecosystem.json`, mirrored to `site/data/ecosystem.json`. Revenue and chip-capacity observations use the main ledger and reviewed metric catalog. Annual revenue, AWS segment sales and private-company annualized run rates are labeled separately.

The `/industry/` page includes the chip supply chain, capacity charts, project stages, jobs disclosures and BLS employment context. The chips page embeds the supply chain and capacity views; every layer links to its companies. These snapshots are dated; a daily research run does not imply that all financial statements or workforce claims were refreshed.

Run `python scripts/validate_ecosystem.py` for reference and provenance checks; the build also runs this validation. Browser acceptance covers all eleven routes, company search, layer and revenue-basis filters, and three viewport widths. The daily 24-document budget retains five baseline sources and rotates the expanded source registry in seven-source steps so later sources are not permanently starved. Dated reports and PDFs may still require reviewed source additions or curated updates; see the methodology.

The infrastructure and chips pages include a searchable component map and optical-technology milestones. The energy and industry pages show solar manufacturing and transformer investment cases; industry also tracks electrical workforce evidence. These reviewed snapshots live in `research/fabric.json`. Validate with `python scripts/validate_fabric.py`, also required by the build. Missing verified revenue is explicit, and is excluded from annual and run-rate views.


## Local research readiness and downtime sessions

See [the operating guide](research/OPERATING_GUIDE.md), [current research agenda](research/RESEARCH_AGENDA.md), [private discovery guide](research/DISCOVERY.md) and historical [September 7 readiness audit](research/READINESS-2026-09-07.md). Both extraction and verification receive the constitution and operating guide. Source-linked monitoring context is assembled from current reviewed company, project, fabric, expansion, agenda and claims snapshots. Private discovery also receives the live agenda's broad evidence questions and layer coverage; named products are examples rather than limits.

Repeated sessions prioritize never-attempted and oldest-attempted sources, with a feed/index source winning a same-staleness tie (its entries are what discovers everything else that batch) rather than an absolute always-first partition. Weekly sources become eligible on their scheduled day, when never checked, or after seven days without an attempt; a registered-daily source unchanged for long enough is checked less often on its own (adaptive cadence), reverting the moment it actually changes. Focused `--sources` runs override the queue using approved IDs only, and never receive the extra overdue-metric sources described below. The review ledger's ids are the document text hash plus each lane's own rule version only, so changed instructions/policy/coverage no longer trigger a new screening by themselves -- only a maintainer bumping `metric_rules_version` or `note_rules_version` does, and only for that lane.

A batch that finds nothing due, unchanged or not already reviewed exits idle rather than as a failure; three such batches in a row end an overnight session early as `completed (nothing new)`. Before the ordinary due list, every batch also queues metrics whose latest reading has aged past their own cadence (quarter/month/snapshot/yearly thresholds), even when their sources are not otherwise due, with a hint in the extraction prompt naming the target period. See OPERATING_GUIDE.md for both mechanisms.

The daily OpenClaw job runs a duration-driven overnight session from 2 AM to 7 AM Pacific, with active work finalized safely at the deadline. Manual sessions are optional. Double-click `Research-Control.cmd` for the control panel — one implementation, usable on the PC over loopback and, when a private `.local/research-control.json` names this machine's Tailscale hostname, from the owner's phone over the tailnet, with every feature including editorial decisions available there too (see [session controls and operating details](research/RESEARCH_SESSIONS.md)). Opening the panel does not start research. The default CLI command also only prints a plan:

Reviewing a catalog package on a phone is one tap: a pending package validates itself automatically in the background (`scripts/catalog_jobs.py`'s single FIFO worker, mirrored to `.local/catalog-jobs.json` so a panel restart still shows the last known state), each card leads with a compact before/after change table with a "Show" link into the exact changed element instead of a homepage-landing preview link, and **Approve and publish** records the decision then queues publication — polling for the research lock to clear rather than refusing the tap — so the owner never waits mid-review. A **Publishing** strip tracks everything already approved through to live, with a Retry for anything that failed. See ["One tap: automatic validation, background publication"](research/RESEARCH_SESSIONS.md#one-tap-automatic-validation-background-publication) and [CATALOG_FEEDBACK_LOOP.md](research/CATALOG_FEEDBACK_LOOP.md).

```powershell
python scripts/research_loop.py

# When you choose to start: a two-hour session, eight documents per batch.
python scripts/research_loop.py --start --publish --min-minutes 120 --minutes 120 --batch-documents 8
```

The session waits for three low-utilization GPU samples before each batch. This is a utilization heuristic, not a reservation: it does not detect keyboard inactivity or preempt inference when a game starts. The model may remain loaded for five minutes. The time budget stops new documents; an active document can finish beyond the deadline. A batch error or an existing research lock stops the session. The daily job and downtime batches share the same runner lock.

To request a stop before the next batch, create `.local/stop-research-loop`; remove that exact file yourself before a later session. There is no auto-restart. Without `--publish`, results remain private, and each batch is retained under `.local/proposals/` as well as the latest proposal files. Neither mode permits the model to change code or its own source policy.

Private `.local/coverage/` receipts list source attempts and never-attempted IDs; `.local/coverage-progress.json` carries rotation across sessions. Attempted is not successfully reviewed. Read run failures alongside coverage. `.local/discovery-leads/` retains secondary evidence and selected external pointers. The bounded discovery lane imports eligible leads and investigates new public hosts privately, alongside rotating broad GDELT news searches. Balanced mode reserves 25% of general-run work units: 18 monitoring + 6 discovery in the daily 24-unit budget, or 6 + 2 in an eight-unit downtime batch. Searches count toward that cap. No new schedule or publication permission is added.

Preview with `python scripts/discovery.py`; monitor `python scripts/discovery.py --status` and `.local/discovery/digest.md`. These inspection commands do not start research. Persistent URL/content memory and retry backoff avoid repeatedly screening unchanged evidence. `.local/review-candidates/` now also holds structured `coverage_expansion` proposals, with human triage in the existing editorial event log. New sources, companies, projects, metrics and topics remain proposals until separately reviewed and implemented. `.local/metric-candidates/` and accepted-note review candidates retain their existing roles.

HTML-only collection, limited discovery, undated pages, inaccessible filings and JavaScript-only job listings remain coverage gaps. A local model is not an unrestricted web-search service. Curated company pages, project stages, claims verdicts and chart definitions remain review-controlled; new evidence can appear in the ledger before those snapshots are updated.

Sessions have no default batch-count cap and retry failed batches within the chosen duration. Manual CLI duration defaults to 120 minutes; the panel and scheduled job default to 360. Optional GPU waits count toward elapsed time. Publication conflicts remain blocked without unsafe cleanup. The panel provides duration, direction, layer and source-category selections, publication mode, keep-awake, live logs and graceful stop. Normal nightly operation uses dedicated GPU time. See [research sessions](research/RESEARCH_SESSIONS.md) for sleep prerequisites, DST behavior, private proposal memory and bounded per-batch checks.

## Website analytics

GoatCounter integration is controlled by `site/analytics.json`. `goatcounter_site: null` disables it. Set that field to the confirmed site code (for example `your-stack-ledger-code`, without a URL), then run `python scripts/build.py` to include it on the maintained pages. The site code is public; no API key or account credentials belong in this repository. The research model and daily publisher cannot change this configuration.

Use a separate site under the existing GoatCounter login via **Settings → Sites**, so Stack Ledger traffic stays distinct from other projects. See [multiple-site setup](https://www.goatcounter.com/help/domains) and [tracking setup](https://www.goatcounter.com/help/start). View results in that site's GoatCounter dashboard after deployment.

The loader runs only on `reedos.github.io/stack_ledger/`, loads asynchronously and disables automatic click-event tracking. Existing canonical URLs keep filter/search query strings out of the page paths. Local previews and browser tests do not load GoatCounter. Blocking analytics does not block site rendering. Verify configuration with the Python tests and the loader with `node tests/analytics.cjs`. Enabling analytics does not run local-model research or alter the runtime block.
