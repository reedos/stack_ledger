# Stack Ledger — Editorial Recommender and Homepage Evolution

**Implementation handoff for Reed's GPT-6 Astra coding agent**  
**Version:** 1.0  
**Decision date:** September 7, 2026  
**Repository:** `https://github.com/reedos/stack_ledger`  
**Status:** User-approved direction; proposed implementation details and initial tuning parameters remain testable defaults.

## 1. Purpose and authority

Implement a bounded editorial recommender that periodically compares the homepage's current featured indicators with approved alternatives. Improve the homepage's ability to show change over time, distinguish promised from delivered capacity, and surface consequential reviewed developments.

The product question is:

> Given the evidence Stack Ledger has accepted, which indicators and visualizations best explain the state of each layer, what is changing, and what remains uncertain?

This is an implementation brief, not a fresh code audit. Earlier conversation included repository-specific observations that may be outdated or incompletely verified. Inspect the current checkout and its instructions before treating any path, missing feature, metric, or implementation claim as authoritative. Do not reproduce an earlier problem if it has already been fixed.

The user has approved the development direction in this brief. Proceed with implementation of the agreed features without requiring approval for every ordinary coding step. That is **not** permission for the unattended researcher or recommender to make future editorial decisions, deploy to production, change credentials, or weaken existing publication restrictions.

The development-time Astra agent and the operational local research model are different roles. The coding agent may implement approved templates, configuration, and tests. The operational model must remain a constrained evidence/proposal producer.

## 2. Non-negotiable decisions

### Preserve the runtime/hardware block as-is

Keep its content structure, fields, labels, hardware/model detail, styling, expanded visibility, and existing section placement. Do not compress it into a status line, hide it behind a disclosure, move it to another page, remove it, or reclaim its space for another graphic.

Preserve its normal dynamic updates: run times, statuses, model/hardware values, and counters may continue to change through the existing pipeline. “As-is” protects presentation and behavior; it does not freeze old data. New homepage modules may change the page's overall length but must not relocate or redesign this block.

### Preserve the five-layer structure and incumbents initially

Keep Energy, Chips, Infrastructure, Models, and Applications. Do not replace the current approved featured metrics merely because this brief proposes a recommender. First improve the presentation of comparable historical evidence, where available.

The discussion baseline was:

| Layer | Featured indicator discussed | Agreed direction |
|---|---|---|
| Energy | Global data-center electricity demand | Keep; prioritize defensible historical context and clearly separated projections. |
| Chips | TSMC CoWoS packaging capacity | Keep; show comparable history and preserve estimate/source qualifications. |
| Infrastructure | Estimated operating IT power at Stargate Abilene | Keep; a well-supported delivery-state snapshot can remain valuable without a long history. |
| Models | A named model's API input-token list price | Keep for now; highest priority for a more defensible price-performance successor. |
| Applications | Waymo paid trips per week | Keep; strengthen its time series and explore supporting outcomes beyond one company/industry. |

These descriptions are not instructions to overwrite a newer reviewed homepage configuration. Verify the current metric IDs and definitions. If they differ, report the difference and preserve the current reviewed state until the discrepancy is resolved. Do not hard-code the numerical values or dates mentioned in the conversation.

### Preserve editorial and publishing boundaries

The daily researcher supplies evidence and proposes records. Trusted code validates records. The recommender proposes editorial changes. The owner or an explicitly authorized human reviewer approves those changes. The renderer builds the approved configuration.

A model must never approve its own proposal. A second model pass, including one from Astra, is assistance to review—not human authorization.

Existing data refreshes within an already approved metric and display rule may continue through the normal constrained publisher. This is different from replacing a metric, changing the chart definition, promoting a forecast into an observed-value slot, changing a claim verdict, or redesigning a section. Those require editorial approval. Do not broaden automatic publication permissions in this project.

## 3. Discover the implementation before changing it

Read `AGENTS.md` and any nested instructions that exist. Inspect the actual metric registry, observation schemas, source policy, governance, homepage configuration, templates, render/build pipeline, publication allowlists, research scheduler, caches, and tests.

The conversation mentioned areas such as `research/`, `scripts/`, `site/`, `docs/`, `tests/`, and private metric/review-candidate queues. Verify their existence and semantics. Prefer extending a working review architecture over creating a parallel workflow or database.

Produce a brief implementation map covering:

- Where homepage metric selection and chart configuration are controlled.
- Where accepted observations, estimates, forecasts, revisions, and source references are stored.
- How data become eligible for public display, and which changes require human review.
- Existing proposal queues and their approval/application behavior.
- Current local-model interface, scheduling, runtime reporting, and publication boundaries.
- Actual historical coverage and comparability for each featured metric.
- Existing tests, CI, and documented validation/build commands.

Then implement incrementally. Reuse the repository's language, dependencies, naming, configuration style, and CLI conventions. The file names and schemas below express contracts; adapt them to the actual codebase rather than imposing a new framework.

Keep a version-controlled copy of this brief in the repository's existing planning or source-documentation area, not in generated website output. Record significant implementation-policy changes there so future agents inherit the same decisions.

## 4. Target architecture

```text
Question-driven research / scheduled monitoring
    -> retrieved evidence
    -> validated, accepted ledger observations
    -> frozen editorial evaluation snapshot
    -> eligibility and deterministic feature extraction
    -> bounded incumbent-versus-challenger model review
    -> structured recommendation validation
    -> private review queue + readable digest
    -> human approval with recorded rationale
    -> guarded application of approved homepage configuration
    -> existing deterministic renderer and constrained publisher
```

The recommender must not browse or broaden research scope during scoring. It evaluates a supplied evidence snapshot. When evidence is missing, it may propose a research question to the existing bounded research queue. New metrics or sources must pass their existing approval process before becoming homepage challengers.

A dry run must be useful without any live model call. It should report incumbents, eligible candidates, missing evidence, freshness, chart readiness, and reasons for ineligibility. When model review is unavailable, do not invent editorial judgments or report that a completed review occurred.

## 5. Recommender workflow

### 5.1 Assemble a reproducible evidence snapshot

Use the same evaluation time, metric definitions, source rules, and scoring policy for incumbents and challengers. Include current homepage configuration, eligible observations, series segments, relevant prior decisions, provenance, and supported uncertainty.

Record snapshot/configuration hashes and policy/schema versions. Keep operational output private until explicitly approved for publication. The model sees only bounded input and a schema; it does not receive publishing credentials or arbitrary filesystem/shell access.

### 5.2 Generate candidates

Consider approved metrics in the relevant layer. Include the incumbent as a real candidate rather than an untouchable baseline. Candidate discovery must distinguish:

- A newer eligible observation of the same metric.
- Better visualization of the existing metric.
- An eligible competing metric.
- A supporting indicator that adds context without replacing the incumbent.
- An interesting but unapproved metric, which belongs in a research/metric-review queue first.

Do not count the same underlying observation or announcement repeatedly because multiple publishers repeat it.

### 5.3 Apply hard eligibility gates

A homepage contender needs a reviewed definition, a clear layer/use case, understandable units, entity and scope, an observation period, traceable support, compatible evidence type, and appropriate review status. It must not be quarantined, retracted, superseded by a correction, or otherwise barred by policy.

Reject or segment incompatible units, entities, project phases, methodologies, cumulative/incremental bases, and reporting periods. A favorable score cannot compensate for a failed evidence gate.

Distinguish two display profiles:

**Trajectory indicator:** Requires enough comparable, adequately spaced evidence to support the claimed visual interpretation. Do not impose one universal minimum such as four observations for every chart, and do not assert an inflection from a merely drawable series.

**Delivery-state indicator:** May be a single important, well-supported snapshot or phase/milestone comparison. Do not automatically reject it for lacking a long history. Its scope and uncertainty must be visible.

Select the profile according to the approved metric/display purpose, not whichever profile yields a higher score. An editor reviews a change in profile.

### 5.4 Compute features in code; reserve judgment for the model

Code computes dates, release-cadence status, coverage span, independent observation count, gaps, compatible-series counts, source lineage, numeric changes, and display/ledger lag. Code validates all referenced IDs and quantitative claims.

The model evaluates layer relevance, explanatory usefulness, significance, scope tradeoffs, and the strongest argument for retaining the incumbent. It must support those judgments with supplied evidence. Model judgments are not objective measurements, and scores are not calibrated probabilities.

Return `KEEP` or `INSUFFICIENT_EVIDENCE` when the case for change is not established. Do not reward proposal volume.

### 5.5 Initial scoring rubric

Use this as the configurable **version-one trajectory profile**, reflecting the latest discussion. The percentages are starting policy choices, not scientifically established optimal weights.

| Dimension | Weight | Interpretation |
|---|---:|---|
| Layer fidelity | 15% | Represents what this layer delivers or constrains, with honest scope. |
| Delivered versus promised | 15% | Distinguishes realized evidence from announced or projected quantities; preserves estimate qualifications. |
| Evidence quality | 15% | Traceable support, appropriate attribution, comparability, limitations, and independent corroboration where relevant. |
| Trajectory / visual explanatory value | 20% | Comparable history reveals meaningful change, persistence, a plateau, reversal, constraint, or divergence. |
| Freshness | 15% | Current relative to source cadence and the question; not merely recently scraped. |
| Physical/economic significance | 10% | Movement or lack of movement matters for the layer's actual function. |
| Interpretability | 10% | Readers can understand the quantity, scope, change, and uncertainty. |

Calculate the final weighted score in code from validated dimension scores and preserve each component's basis. Avoid double-counting the same weakness across multiple dimensions without explanation.

For the delivery-state profile, a proposed implementation is to replace the 20% trajectory dimension with **delivery-state explanatory value**, retaining the other weights. Document this explicitly as an implementation choice: how clearly does the evidence distinguish current usable capacity from commitments, and does the visualization explain that distinction? Do not silently compare scores from different profiles as if they measured the same thing. Cross-profile replacement requires a direct editorial comparison of the homepage slot's purpose.

Do not display these scores as an overall public “AI progress” index.

### 5.6 Compare challenger and incumbent directly

For each proposal, answer:

1. What specific reader question does the challenger answer better?
2. What evidence or visual insight is gained?
3. What scope, continuity, reliability, or interpretability is lost?
4. Could refreshing or recharting the incumbent achieve the benefit without replacement?
5. What is the strongest evidence-based case for keeping the incumbent?
6. What evidence is still missing?

A configurable replacement margin of approximately 10 points was discussed as a starting heuristic, not a proof of superiority. Use it only within compatible profiles and with adequate evidence. Add configurable cooldown/reconsideration rules to prevent churn. A discovered critical flaw must be surfaced promptly even when the margin or cooldown would otherwise block a routine recommendation; it still does not authorize autonomous editing.

A second model critique is useful but is not independent corroboration and is not approval.

## 6. Freshness: compare the right clocks

Store or derive separate timestamps rather than using one generic “updated” field:

| Time/reference | Meaning |
|---|---|
| Observation period / effective date | When the quantity applies. |
| Source publication date | When the source released the claim. |
| Retrieval / verification time | When the system successfully checked the relevant source. |
| Acceptance time | When the record passed the existing ledger acceptance process. |
| Editorial review time | When the displayed interpretation/configuration was adjudicated. |
| Displayed observation ID / build reference | What the current homepage actually presents. |

Use an explicit evaluation `as_of` time and timezone. Do not interpret a future forecast period as a historical observation.

Support annual, quarterly, frequent, and event-driven sources with release schedules or configurable refresh expectations, grace windows, and unknown-cadence handling. An annual observation can remain the latest available after many months. An old list price can still be current if the official source was recently checked and it remains unchanged. Conversely, fetching an old report today does not make its observation new.

Separate:

- **Evidence age:** How old the applicable observation is.
- **Monitoring freshness:** Whether the relevant source was successfully checked on schedule.
- **Editorial freshness:** Whether the displayed interpretation has been reviewed against eligible evidence.
- **Display lag:** Whether an eligible, semantically compatible update is already accepted but not reflected by the approved rendering rule.

A failed fetch is an access problem, not proof that the source has not changed. Absence of public confirmation is not proof that a project is delayed. Preserve `no_new_evidence`, `source_inaccessible`, `conflicting_evidence`, and `explicitly_reported_delay` as distinct outcomes.

When the existing metric has a newer eligible observation, prefer `REFRESH_DATA` over `REPLACE_METRIC`. Check scope, period, units, methodology, evidence type, and headline eligibility first. A forecast must not replace a historical headline solely because its date is later. A new actual must not be spliced into a different estimate methodology without a reviewed comparability decision.

If refreshes are already automatic under approved rules, diagnose and fix stale selection/rendering behavior rather than inventing an unnecessary approval loop. Where a specific featured observation is pinned or curated, create a review candidate instead. Preserve the existing authorization semantics.

## 7. Time-series quality and visual signal

The user's explicit preference is for graphics where readers can see a parameter changing over time, including a meaningful transition from a stable baseline to faster growth. Favor useful **series**, not just impressive latest values.

However, a dramatic curve is not sufficient evidence of importance. This recommender must not become a selector for the fastest-growing or most optimistic series.

### Required series assessment

Assess temporal coverage, actual observation spacing, comparability, gaps, independent data points, uncertainty, persistence, material changes, and whether an apparent break is attributable to changed methodology, scope, or reporting. Repeated quotes of one observation do not deepen the history.

Compute descriptive changes over actual elapsed time. CAGR requires valid positive endpoints and a meaningful interval; zero or negative bases need alternative reporting. Do not treat irregular observations as evenly spaced. Do not infer smooth annual values from a few checkpoints unless a separate, explicitly labeled derived series is approved.

A plateau, deterioration, persistent shortage, or divergence between promised and delivered capacity can be just as informative as acceleration. Increasing electricity use is not automatically better; decreasing cost or resource intensity may be meaningful. Keep direction-of-desirability separate from magnitude of change.

Inflection measures should be optional, descriptive, and conservative initially. Require enough comparable evidence on both sides of a proposed change, show the windows used, and report `insufficient_history` when appropriate. Do not force sophisticated change-point detection into the first release. If scanning many series for unusually large movements, avoid interpreting the most extreme result as automatically significant; flag sensitivity and selection effects.

### Observations, estimates, and forecasts

As of the decision date, September 7, 2026, 2027–2029 values are future-facing. Evaluate dates relative to the run's `as_of` time rather than permanently hard-coding this boundary.

Keep the following distinct in records and rendering:

- Measured or reported historical observations, with attribution.
- Historical estimates, including known uncertainty or ranges.
- Forecasts/projections/scenarios, including issue date and horizon.

“Reported by a company” and “forecast” can both be true; source attribution and epistemic status should be separate fields rather than mutually exclusive concepts.

Observed trend scoring uses compatible historical observations and explicitly identified historical estimates. Forecasts may provide useful supporting context but must not count as realized acceleration or as additional historical depth. Do not claim exponential growth merely because a projected curve bends upward.

Render future series with distinct line treatment, markers, labels, or panels and a clear boundary; do not rely on color alone. Keep scenario and vintage separate. Do not stitch together successive forecasts into a fictitious realized trajectory. Show uncertainty bands only when evidence supplies bounds or a documented, approved method derives them; do not invent precision or confidence intervals.

### Chart integrity

Use true time axes. Preserve visible methodology breaks and meaningful data gaps. Never interpolate operating milestones into unsupported smooth ramps. Use step/bar/state representations when more faithful than a line.

Do not choose axis limits, starting dates, or log scales to exaggerate a result. Explain normalization and logarithmic scales; do not connect zero/negative values on a log scale. Avoid dual-axis combinations that imply unsupported relationships. Label cropped ranges and relevant baselines honestly.

A mini-chart must still communicate metric, units, latest eligible value, observation period, scope, evidence type, and a route to sources/full history. Provide an accessible text equivalent or data table through existing site conventions. Support mobile screens and missing-data states. A series too weak to interpret should remain a snapshot or research gap, not receive synthetic history.

## 8. Recommendation actions and lifecycle

Use a small validated action set, adapting names to existing conventions:

| Action | Purpose |
|---|---|
| `KEEP` | Incumbent remains appropriate; no editorial change proposed. |
| `REFRESH_DATA` | Same approved metric, newer eligible data or correction; respect existing display authorization. |
| `IMPROVE_VISUALIZATION` | Same metric, better approved representation or historical context. |
| `REPLACE_METRIC` | A materially stronger eligible challenger should take the slot. |
| `ADD_SUPPORTING_CHART` | Add necessary context without replacing the headline. |
| `DEMOTE` | Evidence or representativeness no longer supports the incumbent's featured role. |
| `INSUFFICIENT_EVIDENCE` | No defensible decision; optionally open a bounded research question. |

Promoting a new metric into an empty slot can reuse existing promotion semantics if the repo supports them; do not add redundant action types simply to mirror conversation wording.

### Required proposal information

Use a schema that requires action-appropriate fields. At minimum capture:

```yaml
# Illustrative contract; replace placeholders with validated repository IDs.
recommendation_id: <deterministic_id>
created_at: <timestamp>
evaluation_as_of: <timestamp>
action: REPLACE_METRIC
layer_id: <approved_layer_id>
incumbent_metric_id: <approved_metric_id>
challenger_metric_id: <approved_metric_id>
incumbent_display_observation_ids: []
supporting_observation_ids: []
contradicting_observation_ids: []
source_lineage_refs: []
evidence_snapshot_hash: <hash>
base_homepage_config_hash: <hash>
metric_definition_versions: {}
policy_version: <version>
scoring_profile: trajectory
feature_values: {}
incumbent_dimension_scores: {}
challenger_dimension_scores: {}
score_difference: <computed_by_code>
advantages: []
tradeoffs: []
case_for_keeping_incumbent: []
uncertainties_and_missing_evidence: []
proposed_display: <allowlisted_chart_config_or_null>
research_followups: []
model_run_ref: <recorded_run_or_null>
```

Evidence-backed narrative claims should point to the relevant observation/source IDs, not merely share one undifferentiated bibliography. Validate that the cited records support the relevant quantity, entity, period, scope, and evidence status. Do not fabricate confidence, scores, publisher counts, or observation IDs.

The model must not set the authoritative review status, reviewer identity, approval time, or application authorization. A trusted queue writer creates `pending_review` status after validation. Model output containing authorization fields should be rejected or handled according to an explicit safe schema policy.

Use the existing persistent review queue if possible. If an append-only store is used, append review/application events rather than editing historical lines. Derive current status from those events. Support pending, approved, rejected, deferred, applied, and superseded states as appropriate. Approval is not the same as successful application.

### Review and application

Produce a human-readable digest per proposed change: current versus proposed indicator, displayed and candidate dates, chart/data preview when feasible, eligibility and score breakdown, supporting and contradictory evidence, information gained/lost, strongest case to keep, and recommended action.

Approval/rejection/deferral must record an authorized reviewer, timestamp, and rationale. A simple CLI or existing review file/process is enough; do not build a new web application merely to add buttons. Provide an exact approved diff and a reversible configuration/history change.

Before applying an approved proposal, recheck evidence eligibility, metric definitions, and the homepage configuration hash. A materially changed incumbent, revised evidence, or changed policy makes the approval stale and requires reconsideration. Do not apply a recommendation that was approved against a different state without a defined safe revalidation policy.

Deduplicate by action, layer/slot, incumbent/challenger, and material evidence/configuration changes. Do not re-present identical rejected proposals every run. Honor deferrals; reconsider after their date or a material change. Treat past decisions as explicit review context, not hidden model learning or automatic permanent policy changes.

### Cadence and triggers

Run the full editorial comparison monthly by default and on demand. Allow material accepted evidence or a newly approved mature metric to trigger targeted reconsideration. Debounce these triggers and avoid nightly homepage churn. A deterministic freshness/eligibility check may run more often without invoking a full model review.

Use configurable model-call, candidate, token, and research budgets. A run with no changes recommended is a valid success. Source failure, missing evidence, and model failure must be visible as different conditions.

## 9. Agreed homepage changes

### 9.1 Keep the hero and five-layer organization

Retain the existing overall identity and the selected-indicators framing. The homepage is not a comprehensive or causal index of AI progress. Avoid replacing the current design with a dashboard framework or adding widgets solely because data exist.

### 9.2 Add historical context to eligible layer cards

Keep the latest eligible value prominent. Add compact, readable trajectories where the actual accepted data support them. Reuse existing chart primitives and source links. Do not replace the incumbent metric to get a more dramatic chart.

Energy, Chips, Models, and Applications should be assessed for useful series. Infrastructure may remain a delivery-state snapshot. These are hypotheses to check against the actual ledger, not assertions that sufficient histories already exist.

When comparability or coverage is inadequate, preserve the current card and record a specific research gap. Do not fabricate history, scrape unapproved sources during rendering, or silently combine different products/scopes.

### 9.3 Develop “Pledged is not built” into an evidence-backed graphic

Build a phase-aware delivery visualization **only if the data can support it**. Otherwise retain the existing textual explanation/link and report what is missing.

Prefer a stage-distribution graphic, milestone table, or cohort view whose semantics match the available data. Do not force a literal conversion funnel: financed, constructed, commissioned, and operating are not always a universally ordered, mutually exclusive sequence.

Before aggregating quantities, enforce:

- Stable project and phase identifiers; no parent-campus plus included-phase double-counting.
- Comparable units and capacity definitions; facility electrical power is not automatically IT load.
- Distinction between known non-operating capacity and unknown operational status; unknown is not zero.
- Explicit tracked-project scope, coverage, date, and exclusions; no implied worldwide completeness.
- Separate plans, targets, estimates, reported commissioning, and operational evidence.
- A defined accounting basis: mutually exclusive present-state quantities, overlapping cumulative milestone quantities, or a fixed cohort. Label it and never sum overlapping categories.
- Quantitative comparability before calculating an “announced-to-operating” percentage. A ratio across mismatched scopes or periods is not a conversion rate.

For partial delivery, show the phase-specific operating amount and remaining known/unknown quantities rather than assigning an entire campus one misleading status. Attach source references. Retain the project-tracker route for details.

### 9.4 Add “What changed recently?”

Show a small set of consequential, newly reviewed developments rather than a stream of raw research output. A sensible initial display limit is three, configurable to fit the design.

Each item should show what changed, previous versus new state/value when comparable, event/observation date, review date when different, scope, why it matters, and evidence links. Include material corrections, confirmed delays, reversals, and resolutions of uncertainty—not only growth or good news.

Use existing editorial-review semantics. Do not silently promote any machine-accepted note to a public editorial headline. Deduplicate developments that share the same underlying event and avoid crowding out all layers with one frequently reporting company. Explain old events newly entered into the ledger rather than presenting them as breaking news.

The module should have a truthful empty state. Do not fill it with stale or unreviewed items merely to reach the configured count. Use deterministic selection among eligible reviewed items, with optional explicit editorial pins and recorded priority.

### 9.5 Evolve the communities/claims area toward measurable outcomes

Retain the existing analysis and links. Reframe the transition from infrastructure into downstream economic/community outcomes without removing legitimate contested questions or prescribing a predetermined positive/negative narrative.

Lead with one or two reviewed outcome indicators when evidence permits. Otherwise retain a clear question/evidence-gap treatment. Examples of research directions include productivity, employment, tax receipts, water, and power-cost effects, but none should become a homepage claim without suitable scope and evidence.

Do not equate activity with benefit, customer adoption with productivity, temporary construction jobs with permanent operations jobs, projected taxes with collected revenue, or association with causation. Preserve tradeoffs and uncertainty.

### 9.6 Runtime/hardware is protected

Leave this block unchanged in presentation, placement, detail, and behavior. Add a targeted regression test or snapshot, normalizing only dynamic values. Do not add recommender fields to this block by default; use the existing private receipt/methodology infrastructure or another appropriate location for new diagnostics.

## 10. Research agenda supporting better recommendations

The recommender should create bounded follow-up questions when a promising metric is immature, an incumbent is stale, or a proposed chart lacks historical evidence. Extend an existing research-job mechanism rather than building a separate unrestricted browsing agent.

### Priority lanes

**Models:** Seek a defensible cost-of-useful-work or fixed-capability price-performance series. Evaluate successful standardized tasks at stated quality, latency, and total cost, including output/reasoning tokens, tools, retries, and other material charges when applicable. Preserve benchmark/task versions and quality thresholds. Different input-token prices alone are not a normalized capability-per-dollar comparison. Keep the incumbent until a reviewed successor is ready.

**Applications:** Keep the narrow, concrete paid-trip indicator while researching independent physical, digital, scientific, and other useful outcomes. Strengthen the incumbent history before replacing it for breadth alone. Treat company-reported trips as attributed activity, not an independently verified measure of overall economic benefit. Prefer a small set of separate outcome indicators to an arbitrary synthetic “AI productivity” index. Do not use code volume as a stand-in for successful useful work.

**Energy and Chips:** Backfill comparable historical series and preserve methodology, estimate ranges, source lineage, and forecast vintage. Do not manufacture AI-specific precision from all-data-center totals or equate packaging capacity with actual shipped accelerator output.

**Infrastructure:** Verify phase-level delivery milestones, quantities, and capacity definitions. An inaccessible source or missing public confirmation triggers research, not a confirmed delay or zero operating capacity. Broader aggregation is a later evidence-supported improvement, not an immediate requirement to replace the featured project.

### Bounded research-job contract

Represent the question, layer, exact entity/phase, current interpretation, target evidence, excluded evidence, eligible sources, contradiction search, review cadence, budget, and stop conditions. Require separate outcomes for resolved, no new evidence, source inaccessible, conflicting evidence, and insufficient evidence.

Example objective:

> Determine whether the specified project phase has progressed from construction to energized or operating IT capacity. Find dated, phase-specific evidence. Distinguish utility availability, building commissioning, equipment installation, and customer workloads. Preserve quotes and source locations. Report uncertainty; do not infer a delay from silence.

Prioritize important unresolved questions, relevant publication schedules, plausible resolution, and research cost. A numeric research-debt score is optional and must be transparent. The earlier 50/25/15/10 research-budget allocation and “five sources checked” stopping rule were illustrative, not mandatory settings.

Permit proposals for new topics/sources through review so the system can discover blind spots. Do not allow the operational model to redefine its own evidence policy or expand approved scope unattended.

## 11. Reliability, security, and provenance

Treat all retrieved documents and quoted source material as untrusted content. Embedded instructions must not change policy, tool permissions, scores, schemas, or publication rules. Escape/sanitize model/source text used in HTML. Restrict model output to an allowlisted proposal schema; chart suggestions are declarative configurations, never executable code.

Enforce authorization in trusted code. Keep publisher credentials unavailable to research/editorial model calls. Do not rely on prompts as the only restriction. Preserve CI/publication restrictions for untrusted branches and pull requests.

For recommender caches and replay, include the evidence snapshot, incumbent configuration, approved metric definitions, source policy, scoring policy, prompt and schema versions, model identity, relevant generation settings, and relevant implementation version. A change in one of these must not silently reuse incompatible decisions. Verify equivalent safeguards in existing research caches when needed for this feature.

Record captured model outputs, validated features, reviewer actions, and source/observation references. Replay deterministic features and rendering against recorded inputs; do not claim a stochastic model will generate byte-identical output on repeated live calls.

Preserve observation and recommendation histories with revisions and supersession rather than silent replacement. Do not publish copyrighted source dumps or private queue/model traces accidentally; use the project's existing source-excerpt and publication policy.

### Adjacent improvements: inspect, do not blindly implement

Earlier discussion raised document truncation, numeric-token-only support, cache identity, CI, and end-to-end testing. Verify the current code before treating these as defects. Add narrow fixes needed for this feature; record unrelated issues as follow-ups rather than turning this into an unbounded research-engine rewrite.

Where relevant, prefer retrieving passages with headings/table context and explicit truncation information over simply increasing model context. Test number meaning—entity, unit, scope, period, operational status—not just numerical presence. An accepted ledger record and an accurate editorial conclusion remain different validation problems.

## 12. Required tests and evaluation

Use offline fixtures for correctness and safety tests. Live websites and GPU/model availability should not be prerequisites for the ordinary test suite. Add or extend CI using actual repository commands; do not claim tests pass unless run.

The following scenarios are acceptance requirements:

| Scenario | Expected behavior |
|---|---|
| Recently retrieved old report | Retrieval time does not reset observation age. |
| Annual series within its publication window | Not marked stale merely because no monthly release exists. |
| Old event-driven price successfully reverified unchanged | Monitoring is fresh; original effective date remains accurate. |
| Source unavailable | Access failure is not “no change,” “delay,” or zero capacity. |
| New eligible same-metric observation | Refresh/update follows existing approved selection rules; no unnecessary metric replacement. |
| Pinned reviewed observation | New evidence creates the appropriate review candidate rather than bypassing the pin. |
| Later forecast versus latest historical value | Forecast does not displace historical headline or count as realized acceleration. |
| Dramatic unsupported challenger | Fails gates; cannot win by chart shape or weighted score. |
| Slow, flat, or declining but important series | Remains eligible and can be editorially valuable. |
| Sparse history or duplicate reports | No unsupported inflection and no artificial observation depth. |
| Changed units, scope, period, or methodology | Segment, reject, or require reviewed reconciliation; no silent splice. |
| Parent campus and included phase | No double-counting in quantities or stage summaries. |
| Unknown versus non-operating status | Remain distinct; unknown is not treated as zero. |
| Unsupported observation IDs or narrative claims | Reject proposal or route to explicit insufficient-evidence handling. |
| Model attempts self-approval, file writes, or policy changes | Denied by schema/tool/code boundaries. |
| Source contains malicious instructions or markup | Cannot change authorization; safe rendering is preserved. |
| Repeated identical evidence/proposal | Idempotent output and no repeated review spam. |
| Rejected/deferred proposal | Reconsider only under recorded rules or material new evidence. |
| Changed incumbent/evidence after approval | Application blocked or safely revalidated under explicit policy. |
| Changed model/prompt/schema/policy/config | Cache invalidation behaves as documented. |
| `KEEP`, abstention, or no reviewed changes | Valid truthful output; no invented recommendations or news items. |
| Runtime/hardware regression | Same fields, structure, visual treatment, placement, and dynamic behavior. |
| Homepage rendering | Responsive, accessible, deterministic, evidence-linked, with distinct estimates/forecasts. |
| Full offline path | Fixture evidence -> eligibility/features -> mocked editorial response -> validation -> queue -> human-review event -> guarded config application -> build. |

Add a small human-reviewable evaluation set for recommendation quality, not just schema validity. Include justified keep, refresh, rechart, replacement, demotion, and insufficient-evidence cases. Include a flashy but unsupported forecast and a useful plateau. Evaluate incorrect acceptance, missed valid evidence, appropriate abstention, unsupported replacement, recommendation churn, and meaningful question resolution. Model-based graders must not be the sole authority.

## 13. Implementation sequence and deliverables

### Phase 1 — Inventory, configuration, and deterministic foundations

Map actual repo components and historical coverage. Protect the runtime block. Define action schemas, versioned policy, freshness semantics, compatibility checks, snapshot/replay, and dry-run output. Extend existing tests/CI as needed.

### Phase 2 — Recommender and human-review integration

Add bounded model evaluation, incumbent/challenger comparison, critique, schema validation, private queue, digest, idempotency, approval/rejection/deferral, and stale-approval protection. Integrate a monthly/on-demand entry point and material-change triggers using the existing scheduler. Do not create an unnecessary new daemon or external service.

### Phase 3 — Homepage presentation

Add mini-series where data permit, the reviewed changes module, and the outcome-oriented transition. Implement the delivery graphic only when accounting and evidence gates pass. Keep the current featured metrics and runtime/hardware presentation. Follow the current design system and inspect the rendered result on desktop and mobile.

### Phase 4 — Evaluation and first real-data assessment

Run offline integration tests, existing validation/tests/build, and the recommender against the current accepted ledger. Report each layer's actual eligible history, incumbent status, best credible challenger if any, recommended action, and evidence gaps. `KEEP` is an acceptable result; do not prejudge that every metric must be retained if a material error is discovered. Surface errors for review rather than silently swapping indicators.

Do not fabricate scores, chart previews, observation histories, model runs, or passing results. Clearly separate executed checks from suggested/manual checks. Leave deployment/publication permissions unchanged.

### Definition of done

Deliver working code in the actual repository conventions, migrations/backward compatibility where required, automated tests and fixtures, sample proposal/digest outputs, policy/schema documentation, and exact verified commands for dry-run, evaluation, review, guarded application, validation, and build.

Provide a final implementation report with changed files, reuse versus new components, current-data assessment by layer, tests/commands actually run, blocked data-dependent features, security boundaries, runtime-block regression result, and remaining follow-ups. Use small logical commits or reviewable patches according to the project's workflow. Do not claim a production deployment occurred unless it was explicitly authorized and completed.

## 14. Superseded ideas and explicit non-goals

Do not implement earlier suggestions that conflict with this brief:

- Compressing, relocating, hiding, or redesigning the runtime/hardware block is rejected.
- A universal minimum of three or four historical points for every homepage metric is rejected; state indicators remain supported.
- Freshest publication always wins, fastest growth always wins, and forecast growth equals realized progress are rejected.
- Weighted scores and an approximately 10-point margin are configurable heuristics, not objective truth or automatic approval.
- Replacing the Models metric now without a qualified successor is not approved.
- Replacing Waymo solely to gain breadth, or blending unrelated application outcomes into an arbitrary index, is not approved.
- Adding a new model judgment or a second model pass is not independent evidence and is not human approval.
- A literal capacity funnel with overlapping stages or mismatched quantities is not an acceptable substitute for accounting.
- No broad site redesign, new agent framework, new public progress score, autonomous homepage redesign, or unrestricted source exploration is required.

**North star:** Each layer should show clear, trustworthy evidence of what exists and what is changing. The recommender should improve that explanation—not maximize novelty, optimism, chart drama, or autonomous output.
