# Homepage and editorial recommender implementation

Local implementation of `editorial-handoff-v1.md`, evaluated at **2026-09-08 00:00 UTC / September 7, 17:00 Pacific** against the accepted checkout. No new research, live inference, human editorial approval, schedule installation, commit, push or deployment was performed. The ledger remains unchanged.

## Implemented and reused

The accepted ledger, reviewed catalog/source policy, stdlib build/render pipeline, local Ollama JSON adapter, OpenClaw installer and private review-candidate directory are reused. The unattended publisher's exact allowlist is unchanged. A new reviewed homepage configuration controls the existing five slots, optional supporting context, reviewed news and conditional delivery accounting. No featured metric has been replaced.

The recommender adds frozen snapshots, explicit evaluation clocks, per-metric history contracts, provenance and implementation hashes, deterministic eligibility/features, bounded candidate packets, optional local-model comparison/critique, exact-fact validation, weighted-score calculation, KEEP/insufficient outcomes, readable comparisons and a persistent review lifecycle. Human approval is a separate local-terminal action, binds the full proposal and exact config diff, and does not apply or publish. Application rechecks evidence, policy, implementation and config. Rejections, deferrals, cooldown and trigger debounce limit repeat proposals. The research cache received a narrow model/settings/code identity fix.

The homepage adds CoWoS range history and Waymo checkpoints with sources and accessible tables. Existing larger charts and five-layer diagrams are retained. “What changed recently?” is implemented with reviewed-only input, deterministic limits/diversity and an intentional empty state. Raw machine notes are no longer automatically selected as homepage signals. Community links and the employment question remain, with clearer distinctions between activity, spending and realized outcomes. The project-delivery explanation remains textual because the real data cannot support phase aggregation.

Five structured follow-up questions were created privately, pending human approval. They cover consistent electricity history, packaging, Abilene phases, useful-work cost and broader applications. The existing runner now accepts an approved `--question` while retaining normal source and document restrictions. No question was executed.

## First accepted-data assessment

The actual ledger contains **267 metrics, 594 observations, 344 sources and 40 tracked projects**. Of the catalog metrics, **132** have at least one historical record passing this recommender's current gates at the evaluation time. This is an eligibility count, not a completeness or quality score. Missing records, forecast-only evidence and unresolved period semantics are explicit gaps.

The table below is a coding-time interpretation of accepted evidence plus deterministic triage. **Muse did not review it; there are no invented model scores or approved replacements.** Candidate order is reviewed research focus followed by deterministic ordering, not a computed winner.

| Layer | Accepted incumbent history | Implemented presentation / initial triage | Credible comparison and remaining gap |
|---|---|---|---|
| Energy | `dc-electricity`: 415 TWh (2024) and 485 TWh (2025), both approximate historical estimates, from different IEA editions. The 950 TWh 2030 value is a forecast. | **KEEP** the latest estimate. No edition-spliced mini-trajectory. Existing outlooks remain separate. | `us-utility-generation-history` has 12 historical annual observations, 2014–2025, plus 2026–2027 forecasts and separately scoped longer outlooks. It is already useful supporting context on the homepage; national electricity generation is not a substitute for global data-center demand. Seek within-edition comparable demand history. |
| Chips | `tsmc-cowos-wpm`: 13–16k, 35–40k, 65–75k wafers/month at year-end 2023–2025. All are Epoch estimates. The 90–110k 2026 range is a forecast. | **KEEP**, with a new three-checkpoint range graphic and original source table. No accelerator-shipment conversion or CAGR from range endpoints. | `advanced-wafer-capacity` measures global fabrication at advanced nodes, not CoWoS. Its 2024 estimate and later forecasts cannot establish packaging delivery. TSMC revenue is financially useful but not packaging throughput; fiscal-period interpretation also needs an explicit recommender contract before historical ranking. No stronger replacement established. |
| Infrastructure | `abilene-it-operating`: one September 3, 2026 estimate of 421 MW IT. It is inferred from equipment/cooling evidence, not metered facility draw. | **KEEP** as a scoped state snapshot. | `census-dc-construction-saar` has six accepted monthly spending anchors from July 2025 to July 2026, already reflected elsewhere on the homepage. Nominal annualized construction spending is not operational capacity. Other campus estimates differ in scope and may overlap. A disjoint phase inventory remains the priority. |
| Models | `codex-input-price`: one observed list-price snapshot of USD 1.75/million input tokens, accessed September 7, 2026. Effective price-change date is not separately known. | **KEEP** as the existing named-model snapshot; no fabricated history or capability ranking. | `inference-cost` supplies two GPT-3.5-equivalent MMLU cost checkpoints from November 2022 and October 2024. Its fixed-capability concept is more relevant than comparing unrelated input prices, but it is dated and does not establish current agent-task cost with tools/retries/quality/latency. Current frontier price snapshots also cannot supply that denominator. A reviewed successor is not ready. |
| Applications | `waymo-paid-weekly`: more than 250,000 in May 2025 and 500,000 in March 2026. The commercial footprint expanded. | **KEEP**, with two separate checkpoints, a lower-bound marker, month precision and explicit footprint qualification. | Digit's accepted cumulative tote milestone is a credible supporting physical-work example, already on the homepage. Copilot review-use endpoints establish adoption, not completed useful work or productivity. Neither justifies replacing paid trips for breadth alone. Seek additional independently measured outcomes and more paid-trip disclosures. |

Monitoring remains distinct from evidence age. The retained receipts indicate access failures for relevant Energy and Applications sources; Chips, Infrastructure and Models have retrieved bodies but lack an explicit unchanged-content semantic verification receipt. The assessment reports `source_inaccessible` or `retrieved_change_unknown` rather than inventing “no change” or a delay. The current generated homepage displays the eligible selected IDs in all five slots, so display lag is **none**. Legacy observation acceptance timestamps remain unknown; editorial configuration review time is recorded separately.

## Tests and commands actually run

| Command/check | Result |
|---|---|
| `python scripts/validate.py` | Passed ledger and homepage configuration checks. |
| `python -m unittest discover -s tests` | **126 tests passed**, including the existing 90 and 36 new tests. |
| `python scripts/evaluate_editorial.py` | **8/8 recommendation fixtures passed**; 3 question-outcome fixtures passed. Zero incorrect acceptance, missed valid evidence, unsupported replacement or false resolution in this fixture set. Three identical queue replays added zero proposals; an identical rejected proposal was not requeued. |
| `python scripts/build.py` | Built **107 pages**. A subsequent rebuild produced **148 byte-identical artifacts**. |
| `node tests/browser.cjs` using the installed Playwright module | Passed **24 routes at three viewports**, plus 320/375/390px chart-fit checks, keyboard access, source navigation, data tables and no browser errors. Added runtime dynamic-counter and placement checks passed. |
| `python scripts/editorial_review.py assess --as-of 2026-09-08T00:00:00Z` | Offline assessment completed; no model calls or proposals fabricated, no public config changed. |
| `python scripts/editorial_review.py questions` | Five private pending questions created; no research started. |
| `python scripts/schedule.py --editorial` | Optional monthly job previewed only. |
| `git -c core.safecrlf=false diff --check` | Passed. |

The end-to-end test uses a temporary repository copy: actual accepted fixture evidence → deterministic features → mocked editorial response → schema/evidence validation → existing private review queue → simulated human review event → guarded configuration application → actual site build. It never writes a real approval event. Separate mocked-adapter tests confirm the model-call budget and lack of publication credentials/capabilities. Ordinary tests do not need network access, Ollama or a GPU.

The quality fixtures are explicit reviewable expectations, not a live-Muse quality measurement or an independent human adjudication. Sample proposals and Markdown digests are generated under `.local/editorial-evaluation/`; full assessment data and rejected-record reasons are under `.local/editorial/`. Desktop and mobile card screenshots were inspected under `.local/browser/editorial-cards-*.png`.

## Runtime regression

The runtime Python function, browser update function, footer structure/neighbors and original runtime CSS match the pre-change fixture exactly. The generated homepage runtime block also matches `HEAD` exactly with the current accepted runtime data. Tests change model text, timestamps, status and counters and verify normal updates. The browser opens its existing detail disclosure and verifies updated counters. No recommender status was added to that block; it was not moved or restyled.

## Changed files

New reviewed files: `research/editorial-handoff-v1.md`, `research/homepage.json`, `research/editorial-policy.json`, `research/EDITORIAL_RECOMMENDER.md`, and this report.

New implementation: `scripts/editorial.py`, `scripts/editorial_review.py`, `scripts/editorial_questions.py`, `scripts/render_editorial.py`, `scripts/evaluate_editorial.py`.

Extended existing implementation: `scripts/render.py`, `scripts/build.py`, `scripts/validate.py`, `scripts/research.py`, `scripts/schedule.py`, `site/assets/app.js`, `site/assets/home.css`, `research/METHODOLOGY.md`, `research/OPERATING_GUIDE.md`.

Tests/CI: `tests/test_editorial.py`, `tests/editorial_fixtures.py`, `tests/fixtures/editorial/quality-cases.json`, `tests/fixtures/editorial/runtime-contract.json`, `tests/browser.cjs`, `.github/workflows/validate.yml`.

Generated artifacts: the 107 existing `docs/**/index.html` pages and the mirrored `docs/assets/app.js` and `docs/assets/home.css`. Other pages primarily carry the new build/cache reference. Public data, runtime identity, `site/template.html`, layer diagrams, credentials, Git settings and the publisher allowlist were not changed. Work is left as local reviewable patches, without commits or deployment. The existing unattended publisher will appropriately refuse a dirty checkout until the reviewed code changes enter the normal clean-checkout workflow.

## Data-dependent blocks and follow-ups

- **No delivery-stage graphic yet:** stable phase membership, explicit exclusions, common capacity basis/date and non-overlapping quantities are missing. The gate and optional phase-table renderer exist; no cohort, denominator or operating total was invented.
- **No Energy mini-trajectory:** the two accepted estimates have different IEA editions. No Models history exists for the named-price incumbent. No numerical inflection claims are made.
- **No reviewed recent news entries:** the module is ready, but accepted notes alone are not editorial approval. Add reviewed items through the guarded repository configuration workflow with event/review dates, rationale and sources.
- **No new downstream outcome headline:** scoped supporting analyses remain accessible; adoption, projected hiring and budget revenue do not establish causal benefits.
- **Human adjudication and live model evaluation remain follow-ups:** inspect the fixture comparisons, then explicitly opt into a bounded model trial if desired. Numeric facts/reference integrity are checked in code; qualitative interpretations still require human judgment. Some fiscal and compound periods need reviewed contracts before broader candidate histories qualify. Qualitative-only question resolution currently requires manual review outside the numeric resolution command.
- **No additional schedule is active:** the optional monthly plan and material-trigger entry point are implemented, with debounce. Enabling either automatically was outside this implementation's authorization.

Operational commands and schema conventions are documented in `EDITORIAL_RECOMMENDER.md`.
