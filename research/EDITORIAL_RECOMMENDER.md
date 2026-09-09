# Editorial recommender: operation and review

Site-wide extension: [Visual recommendations: operation and limits](VISUAL_RECOMMENDATIONS.md) documents the implemented recommendation-only session assessment and local panel. [The algorithm draft](VISUAL_RECOMMENDATION_DRAFT.md) retains the broader design, including follow-ups not yet implemented. Neither widens publication permissions.

Implements [the approved handoff](editorial-handoff-v1.md). This is reviewed coding configuration, not permission for a research model to change the site. No extra schedule was installed as part of implementation.

## Repository map and authority

`site/data/ledger.json` is the accepted evidence ledger; `research/catalog.json` and `research/sources.json` remain the reviewed metric and source authorities. Existing observation statuses, correction ancestry, source mappings, research screening, and `research.py`'s exact publication allowlist are reused. Legacy acceptance time is unknown: retrieval time is never substituted for it. No ledger migration fabricates missing timestamps or historical values.

`research/homepage.json` now controls the five featured slots, display mode, optional observation pins, at most one supporting metric per slot, and reviewed recent developments. Its initial metric IDs exactly match the catalog. The catalog continues to define each layer and its default metric for the detailed layer page. `scripts/render.py` uses the approved homepage configuration at build time; `scripts/render_editorial.py` supplies static context and accessible tables. Existing detailed charts in `site/assets/app.js` remain available. Research and recommendation processes cannot alter this configuration through the unattended publisher.

`research/editorial-policy.json` defines per-metric history requirements, cadence, source-edition segmentation, score weights, budgets, local human reviewer accounts, replacement margin and cooldown. Trajectory explanatory value and delivery-state explanatory value occupy the same 20% rubric position but are different purposes: their scores are never compared across profiles. The named API price is explicitly a scoped snapshot in the delivery-state profile, not a measure of intelligence delivered. Metrics without a reviewed trajectory contract can be examined as scoped snapshots; that does not authorize a history, a rank, or promotion.

`scripts/editorial.py` computes eligibility, period intervals, segments, independent point counts, actual elapsed gaps, descriptive changes when permitted, freshness clocks, hashes and weighted scores. Bounds and ranges do not produce exact CAGR. Forecasts retain their status even after their horizon passes. Inflection detection is deliberately not implemented: sparse series report insufficient history, and longer series report not evaluated. Unknown fiscal/compound periods require interpretation rather than an invented calendar date. Source-edition and methodology changes are segmented. Desirability is retained separately from change magnitude.

`scripts/editorial_review.py` freezes inputs, produces deterministic assessments, optionally calls the existing local Ollama JSON adapter, validates comparisons, and extends `.local/review-candidates/`. Existing note and metric-candidate files are untouched. Editorial proposals have a `kind` discriminator; lifecycle events append to `editorial-events.jsonl`. Snapshots, captured model outputs, features, critiques and digests live under `.local/editorial/<snapshot-hash>/`. They are private, ignored by Git, and never copied to `docs/`.

The cache includes accepted evidence, metric definitions, source policy, homepage configuration, prior decisions, evaluation time, timezone, rubric/schema/prompt versions, actual prompts, model identity, generation settings and relevant implementation hashes. Material proposal identity excludes the evaluation clock so identical evidence is not re-presented daily. A rejected identical proposal stays rejected; a deferred proposal can return after its recorded date or as a distinct material revision. Replacement cooldown applies after an application; a claimed critical flaw is surfaced promptly for human adjudication, never autonomously applied. The adjacent research screening cache now also includes model identity, settings, candidate limit and implementation/schema/prompt code.

The same model's optional critique is fallible assistance. Captured responses replay; fresh stochastic inference is not claimed to be byte-reproducible. Model packets have a hard character cap: oversized packets are explicit failures rather than silently truncated evidence. The adapter receives only the loopback model endpoint, model identity, timeout and bounded generation settings, with no Git credentials, shell or fetch tools. Exact numerical facts must reproduce referenced metric, value, bounds, period, status, unit, geography and scope. Free-text quantities and unknown fields are rejected. Qualitative support, relevance, causation and alleged critical flaws still require human semantic review; a schema cannot prove those judgments true.

## Commands

All commands below run from the repository. The assessment and evaluation commands are offline by default.

```powershell
python scripts/editorial_review.py assess --as-of 2026-09-08T00:00:00Z
python scripts/evaluate_editorial.py
python scripts/editorial_review.py questions
python scripts/schedule.py --editorial
```

The first writes an assessment and digest without inference. The second exercises synthetic fixtures, not new public facts. The third creates five bounded, pending research questions in the existing review queue and does not research them. The fourth only previews the optional monthly OpenClaw job (10:00 Pacific on the first); it does not install anything. Scheduling uses the existing installer and requires a separate explicit `--install --editorial` operation. No such operation was run for this implementation.

Optional inference is explicit:

```powershell
python scripts/editorial_review.py assess --model
python scripts/editorial_review.py assess --model --critique
python scripts/editorial_review.py assess --model --trigger material
```

Five calls per run, four candidates per layer, 40,000 input characters, 2,500 output tokens and five follow-up questions are the initial budgets. A critique consumes the same call budget, so fewer layers may be reviewed; the receipt reports reviewed layers, failures and budget limits. Candidate ordering is deterministic review order, not a merit ranking. Monthly and material triggers debounce, with separate offline/model modes. They are on-demand entry points, not a new daemon or a newly enabled evidence callback. All 267 catalog entries are assessed for eligibility before the bounded shortlist. No live inference was used for the first assessment.

Human review is a separate interactive local-terminal command. Replace `ID` with the complete ID from a real validated proposal; it is not a filename or shell fragment supplied by a model.

```powershell
python scripts/editorial_review.py review ID --decision approved --reviewer reedos --rationale "Specific evidence and scope rationale"
python scripts/editorial_review.py review ID --decision rejected --reviewer reedos --rationale "Specific reason"
python scripts/editorial_review.py review ID --decision deferred --reviewer reedos --rationale "Await the next comparable release" --reconsider-after 2026-10-08T00:00:00Z
python scripts/editorial_review.py apply ID
```

The review command checks the authorized local account, prints the comparison and exact diff, and requires typing the full ID. There is no `--yes` or model approval path. It records reviewer, time, rationale and the hash of the entire proposal. Approval is not application. Application checks the immutable snapshot, full proposal, accepted evidence, definitions, source policy, editorial policy, implementation and base config, then atomically writes only `research/homepage.json` and appends an application event. It does not build, commit or push. An interrupted save can recover only if the config equals the exact approved result. A no-change/automatic-refresh decision records review without an unnecessary config edit. The event retains before/after JSON and a reversible diff; restoring an earlier config is another reviewed local change, never automatic history deletion.

Model and source text have no capability to invoke these commands. The filesystem and local operator remain the trust boundary; the event store is not a cryptographic identity service. A person with write access to the repository can make a reviewed code/configuration change under the existing workflow. No claim is made that a JSON reviewer name alone authenticates a human.

## Bounded research questions

`scripts/editorial_questions.py` extends the same review-candidate queue with a question, layer, entity/phase, present interpretation, target and excluded evidence, approved sources, contradiction search, cadence, document budget and stop conditions. Initial lanes cover comparable demand history, CoWoS estimates, Abilene phases, useful-work cost and broader application outcomes. Proposed new sources/metrics still belong in the pre-existing reviewed source/catalog workflow.

```powershell
python scripts/editorial_review.py review-question QUESTION_ID --reviewer reedos --rationale "Specific bounded scope"
python scripts/research.py --question QUESTION_ID --max-seconds 600
python scripts/editorial_review.py resolve-question QUESTION_ID --outcome resolved --observations ACCEPTED_OBSERVATION_ID --reviewer reedos --rationale "Why the evidence answers the question"
```

The middle command **does start real research** when an approved question exists. It was not run here. Existing fetch and model budgets, source checks, record validation and private-proposal default still apply. Question approval binds the source policy and question hash; source selection and document limits cannot exceed that approval. `resolved`, `no_new_evidence`, `source_inaccessible`, `conflicting_evidence` and `insufficient_evidence` remain distinct. Resolution currently requires accepted numeric observation references plus human semantic review; qualitative-only resolutions remain a manual review gap. Repeated calls do not prove resolution. A failed source is not a reported delay. An explicit reported delay can remain source evidence and a separately reviewed recent-change item.

## Homepage treatment

CoWoS receives three historical range checkpoints, with the existing thousand-wafers display conversion clearly stated. Waymo receives two checkpoints with its lower-bound marker, month precision and changing service footprint. Both use real time positions and accessible source tables, no synthetic connecting ramp. IEA editions remain separate segments, so Energy stays a snapshot with a specific history gap; the larger historical/outlook chart is retained. Abilene and the named-model price remain snapshots. No current metric or observation was replaced.

“What changed recently?” reads only the curated `recent_changes` array. A maintainer adds an item through the existing reviewed configuration-change workflow, recording event identity, kind, layer, event and review dates, reviewer/rationale, scope, why it matters, approved source IDs, optional compatible before/after IDs, priority and pin. The config validator rejects duplicate event keys and incompatible quantitative comparisons. The renderer uses review recency, maximum count and layer diversity, labels old events newly reviewed, escapes text and has a truthful empty state. Machine-accepted ledger events cannot populate it. No recent item was approved by this coding implementation; the old automatic homepage research-note selection was removed. Notes remain in the ledger.

The 40-project tracker lacks an explicit disjoint phase cohort. `delivery_gate` requires stable leaf phases, parent exclusions, phase-mapped metric definitions, a common accounting date, compatible units, exact historical quantities and cited scope. Unknown phases are counted as unknown, never zero. It blocks parent/child and duplicate-observation sums. The optional renderer is a phase table, not a conversion funnel. The existing “Pledged is not built” explanation and tracker link remain because no real cohort passes these requirements. No announced-to-operating percentage is computed.

The communities transition retains the Claims & Evidence route and unemployment question, framing downstream benefits as measurable questions. Construction spending, openings, tax budgets, paid trips and code reviews are not promoted to proven causal benefits. No new quantitative outcome claim was approved here.

The runtime/hardware block is untouched: Python renderer, browser updater, footer neighbors/structure and existing runtime styles are checked against a pre-change fixture. Dynamic values and counters remain live. Recommender diagnostics stay private.

## Validation and limits

```powershell
python scripts/validate.py
python -m unittest discover -s tests
python scripts/evaluate_editorial.py
python scripts/build.py
$env:PLAYWRIGHT_MODULE='C:/Users/reedo/projects/ee-labs/node_modules/playwright'
node tests/browser.cjs
```

The new CI job runs the offline Python commands with read-only repository permissions and no publication step. Browser checks use an already installed optional Playwright/Chrome environment. The offline integration test copies the existing repository to a temporary fixture, freezes evidence, validates a mocked comparison, queues it, records a simulated human decision, guards application and runs the actual build there. It never approves the real homepage or starts inference.

Quality fixtures include keep/plateau, pinned refresh, rechart, replacement, demotion, abstention, an unsupported dramatic forecast and a fabricated numerical claim. They are reviewable test expectations, not an independent human audit or a measurement of Muse's live editorial quality. The evaluation reports fixture acceptance errors, missed valid evidence, abstention, unsupported replacement and question-resolution errors. Queue tests check churn. Owner adjudication of the sample comparisons and an explicitly authorized live-model trial remain follow-ups; do not label either as already completed.
## Browsing and display context

Pagination and expandable evidence are maintained presentation controls. They do not remove records from the accepted evidence available to the recommender, change source freshness or imply an editorial rejection. Assess the full frozen dataset. Recommendations must still distinguish a genuinely missing measure from an accepted record on a later page, a collapsed topic or a display lag. Daily researchers cannot create new page sections or change these controls. Reviewed display changes retain stable anchors, scope/status labels, source links and complete exports; the runtime block remains protected.
