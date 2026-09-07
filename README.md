# Stack Ledger

**A public ledger of the AI buildout.** Energy → chips → infrastructure → models → applications. Global coverage with a U.S. focus, 2030 as the main horizon, and explicit longer-term targets.

**[Read the site](https://reedos.github.io/stack_ledger/)** · [Research constitution](research/CONSTITUTION.md) · [Methodology](research/METHODOLOGY.md) · [Public dataset](site/data/ledger.json)

## Our premise

AI can help reindustrialize America: abundant power and domestic manufacturing support AI factories, models and agent systems; useful applications can turn that capability into business productivity, physical work and discovery. We follow the opportunity from local investment, purchasing and jobs to digital workers, productive robots, medicine, engineering, climate research and clean energy.

This is our guiding ambition, tested against evidence. Announced investment is not delivered capacity, a robot demo is not an operating workforce, and a promising drug candidate is not a patient outcome. The constitution directs the daily researcher to look for these connections without inventing benefits or suppressing constraints.

## What is included

- An expanding company directory with 38 annual revenue records, two annualized run rates and five explicit revenue coverage gaps; product-role sources are linked separately.
- A searchable datacenter component map covering compute, memory, DSPs, SerDes, copper, optical modules, CPO, fiber, switching, assembly and electrical infrastructure.
- Electrical workforce evidence and clean-energy manufacturing cases, distinguishing reported employment, projected openings, hiring plans and investment stages.

- An original interactive five-layer illustration, responsive landing page and five dedicated dashboards.
- Attributed observations, forecast charts, explicit units, accessible data tables, research notes and a source library.
- Search, layer filters, CSV and JSON downloads, an Atom feed and correction links.
- A daily Ollama research runner scheduled by OpenClaw. Model proposals pass deterministic validation and a separate evidence-screening pass before publication.
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

Open http://127.0.0.1:4173. Website source is in `site/`; `docs/` is the deterministic GitHub Pages build. GitHub Pages serves `main:/docs`, with `.nojekyll`. All links support the `/stack_ledger/` project prefix and direct visits to individual layer pages. There are no runtime server services, analytics or API keys in the public site. Google Fonts is optional; system font fallbacks work offline.

The homepage hero, isometric layer links, five evidence cards, navigation and runtime footer are rendered into HTML by `scripts/render.py`. Charts and directory filters progressively load in the browser. The static snapshot and raw-data links remain usable without JavaScript or after a data-request failure. The reviewed stack artwork lives in `site/partials/stack.html`.

Headline cards retain metric scope, units, periods, status and publisher. Applications deliberately shows a research gap until a measured-outcome metric is reviewed; the adoption survey remains in the applications research. Reindustrialization is a question below the evidence, and government targets, company commitments and independent projections retain separate books.

Daily builds refresh these deterministic HTML snapshots from the ledger. The publisher permits only the reviewed generated page paths in addition to ledger JSON and the feed; it cannot change source templates, navigation, styles, metric definitions or governance. Browser acceptance checks the homepage with JavaScript disabled, failed dataset requests and keyboard navigation as well as all routes at three viewport widths.

## Research runtime

Configuration lives in [`research/runtime.json`](research/runtime.json):

- Ollama model: `muse-glimmer:30b-q4_K_M-dflash` (public label: muse glimmer:30B dflash).
- Endpoint: `http://127.0.0.1:11434`, reachable only on the local host.
- Scheduler: OpenClaw, **19:00 America/Los_Angeles daily**, following Pacific daylight-saving changes.
- Hardware: Ryzen 9 9950X3D, RTX 5090, 64 GB DDR5 (owner-provided configuration).
- At most 24 documents, one discovered link per approved source page, bounded context, bounded generation and network timeouts. Unchanged successfully screened documents reuse their recorded content hash.

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

Daily publication changes only approved ledger/excerpt data, the feed and the maintained generated HTML pages. The exact boundary is enforced by `ALLOWED_CHANGES` in `scripts/research.py`. The reviewed catalog and source registry must match public data. Newly discovered source URLs must retain an approved host and publisher. The agent may add numeric observations and source-supported research notes. It cannot change templates, code, metric definitions, targets, source policy or its constitution.

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
| `scripts/validate.py` | Data invariants, source boundaries and integrity checks |
| `scripts/build.py` | Reproducible static pages, feed and sitemap |
| `scripts/schedule.py` | Idempotent OpenClaw command-job installation |
| `tests/` | Meaningful integrity and runner regression tests |
| `docs/` | Committed static GitHub Pages output |
| `.local/` | Ignored evidence, proposals, caches, run logs and local screenshots |

## Attribution and license

The organizing concept is inspired by [Jensen Huang’s five-layer AI framework](https://blogs.nvidia.com/blog/ai-5-layer-cake/). Stack Ledger is independent and unaffiliated with NVIDIA. Site code and original graphics are MIT licensed. Original source content retains its rights; factual records preserve attribution. IEA material is attributed under its stated CC BY 4.0 license where applicable. This repository does not redistribute complete source articles.

## Energy and infrastructure delivery

The `/projects/` tracker follows ten selected projects across generation, storage, transmission and AI infrastructure. Filter by stage, layer, owner or location. Each card separates reported quantities from plans, retains an evidence timeline, records grid context and identifies the next missing evidence. The site also includes new research on accelerator delivery, HBM, packaging, model reliability, inference price-performance, workplace productivity and scientific prediction.

Tracker definitions live in `research/delivery.json`; numeric evidence lives in the main ledger. Validate with `python scripts/validate_delivery.py` (also run by the build). Stages are reviewed snapshots, while the daily runner can append screened observations and notes. For a fresh, focused local research pass: `python scripts/research.py --apply --refresh --max-documents 6 --sources fervo-q2-2026 eia-additions-2026 aws-delivery-2026`. Use `--publish` instead of `--apply` only with a clean working tree. A focused pass may be partial because its coverage is intentionally limited.

## Company and industry research

The company directory covers 45 representative businesses across the five layers. Company roles and jobs/factory snapshots are reviewed metadata in `research/ecosystem.json`, mirrored to `site/data/ecosystem.json`. Revenue and chip-capacity observations use the main ledger and reviewed metric catalog. Annual revenue, AWS segment sales and private-company annualized run rates are labeled separately.

The `/industry/` page includes the chip supply chain, capacity charts, project stages, jobs disclosures and BLS employment context. The chips page embeds the supply chain and capacity views; every layer links to its companies. These snapshots are dated; a daily research run does not imply that all financial statements or workforce claims were refreshed.

Run `python scripts/validate_ecosystem.py` for reference and provenance checks; the build also runs this validation. Browser acceptance covers all eleven routes, company search, layer and revenue-basis filters, and three viewport widths. The daily 24-document budget retains five baseline sources and rotates the expanded source registry in seven-source steps so later sources are not permanently starved. Dated reports and PDFs may still require reviewed source additions or curated updates; see the methodology.

The infrastructure and chips pages include a searchable component map and optical-technology milestones. The energy and industry pages show solar manufacturing and transformer investment cases; industry also tracks electrical workforce evidence. These reviewed snapshots live in `research/fabric.json`. Validate with `python scripts/validate_fabric.py`, also required by the build. Missing verified revenue is explicit, and is excluded from annual and run-rate views.


## Local research readiness and downtime sessions

See [the operating guide](research/OPERATING_GUIDE.md), [current research agenda](research/RESEARCH_AGENDA.md) and [September 7 readiness audit](research/READINESS-2026-09-07.md). Both extraction and verification receive the constitution and operating guide. Source-linked context is assembled from current reviewed company, project, fabric, expansion, agenda and claims snapshots.

Repeated sessions prioritize never-attempted and oldest-attempted sources. Weekly sources become eligible on their scheduled day, when never checked, or after seven days without an attempt. Focused `--sources` runs override the queue using approved IDs only. Content caches also include policy, instructions, context and metric definitions, so changed guidance can trigger a new screening. First runs after this update may therefore use more GPU time.

The existing 19:00 Pacific job remains unchanged. A separate downtime session is **not scheduled or running**. Its default command prints a plan without checking GPU usage or calling Ollama:

```powershell
python scripts/research_loop.py

# When you choose to start: a two-hour session, eight documents per batch.
python scripts/research_loop.py --start --publish --min-minutes 120 --minutes 120 --batch-documents 8
```

The session waits for three low-utilization GPU samples before each batch. This is a utilization heuristic, not a reservation: it does not detect keyboard inactivity or preempt inference when a game starts. The model may remain loaded for five minutes. The time budget stops new documents; an active document can finish beyond the deadline. A batch error or an existing research lock stops the session. The daily job and downtime batches share the same runner lock.

To request a stop before the next batch, create `.local/stop-research-loop`; remove that exact file yourself before a later session. There is no auto-restart. Without `--publish`, results remain private, and each batch is retained under `.local/proposals/` as well as the latest proposal files. Neither mode permits the model to change code or its own source policy.

Private `.local/coverage/` receipts list source attempts and never-attempted IDs; `.local/coverage-progress.json` carries rotation across sessions. Attempted is not successfully reviewed. Read run failures alongside coverage. `.local/discovery-leads/` retains secondary evidence and selected external pointers for review without automatically fetching new hosts. `.local/metric-candidates/` retains source-supported notes that lack a reviewed metric. `.local/review-candidates/` queues accepted notes for possible updates to curated companies, projects, claims and agenda cards.

HTML-only collection, limited discovery, undated pages, inaccessible filings and JavaScript-only job listings remain coverage gaps. A local model is not an unrestricted web-search service. Curated company pages, project stages, claims verdicts and chart definitions remain review-controlled; new evidence can appear in the ledger before those snapshots are updated.

The downtime session now defaults to a 120-minute minimum and maximum elapsed-time window. The cycle cap cannot end it before the minimum. GPU waits count toward elapsed time; errors, stop requests and conflicts can still end it early. An active document may finish after the window. Use `--min-minutes 0` to restore a cycle-limited session. This setting does not change the daily scheduler.
