# Site-wide visual recommendations — algorithm draft

Date: September 9, 2026. Status: proposed design for owner review; not implemented or enabled.

Update: the owner authorized rollout. See [implemented behavior and remaining limits](VISUAL_RECOMMENDATIONS.md); the original design below is retained for comparison and is not a claim that every planned capability is active.

## Purpose and owner control

Evaluate whether new evidence can make Stack Ledger's existing indicators clearer, more informative, or more useful. Muse recommends; Reed chooses. Bigger growth alone is not a reason to replace a graphic. A plateau, delivery constraint, correction, or well-supported outcome can be more informative than a dramatic forecast.

Initially, every editorial change is recommendation-only: replacing or removing a graphic, adding a featured graphic, changing a featured company or case study, changing a baseline, changing a forecast edition, changing chart form, or changing explanatory copy requires human review. Preserve the five layers, approved layout, and runtime/hardware block. The latter is outside the recommendation system's editable scope.

Existing authorized monitoring may continue appending accepted observations and rebuilding indicators that already consume them. This draft grants no new publication permissions. Record those ordinary data refreshes separately from proposed editorial changes. A pinned graphic stays pinned until its exact proposed update is reviewed and applied.

**Accept means approve the exact preview for a separate application step; it does not mean publish immediately, approve future variants, or let Muse edit code.** Decline, defer, request changes, and keep the current graphic are normal outcomes. Silence is never approval.

## Reuse and actual implementation gaps

Build on [EDITORIAL_RECOMMENDER.md](EDITORIAL_RECOMMENDER.md) and [CATALOG_FEEDBACK_LOOP.md](CATALOG_FEEDBACK_LOOP.md), not a second research or publishing architecture.

| Existing component | Reuse | Proposed extension, not yet implemented |
| --- | --- | --- |
| `scripts/editorial.py` | Evidence eligibility, comparable segments, clocks, hashes, scoring | Display-specific dependency and calculation contracts across the site |
| `scripts/editorial_review.py` | Frozen snapshots, bounded optional inference, decisions, private digest, stale-approval checks | Site-wide proposals beyond the five featured homepage slots |
| `research/editorial-policy.json` | Reviewed weights, replacement margin, cooldown, budgets | Explicit contracts and calibrated comparisons for additional display purposes |
| `.local/review-candidates/` and editorial event log | Private proposal identity, lifecycle, decision history | Structured graphic proposals linked to any prerequisite catalog package |
| Catalog preview and review | Isolated validation/build, exact before/after evidence, separate application | Deterministic side-by-side visual previews for supported graphic changes |
| Research Control / Review findings | Local authenticated human review boundary | A visual recommendations view with accept/decline/defer/request-changes controls |
| Research session runner | Existing locks, budgets, receipts, accepted records | Cheap dependency checks and a bounded session-conclusion recommendation pass |

The existing editorial command can assess on demand; comprehensive session-conclusion evaluation and the visual review interface described here are not currently active. Existing catalog publication does not authorize publishing arbitrary visual changes. New application paths require reviewed implementation.

## 1. Inventory each display and define its contract

Give each maintained display a stable identity. Record its page/anchor, reader question, layer, renderer, current configuration, accepted metric/observation/catalog dependencies, and whether values are pinned or dynamically selected. Include all relevant accepted data, even when the public page paginates or collapses it.

Each contract must specify:

- The permitted units, geography, population, period basis, status, accounting basis, source editions, and minimum evidence for its purpose.
- Approved calculations, baseline selection, rounding, range handling, missing-data behavior, and overlap exclusions. A snapshot and a trajectory have different evidence needs.
- Current chart form, accessible table, required qualifications, source links, and supported preview options.
- Data cadence, monitoring cadence, last editorial review, and the accepted evidence currently rendered.
- Human-controlled choices and the narrow automatic data updates already permitted by existing policy.

A new contract or formula is a maintainer-reviewed change. Muse may propose one as a specification, but cannot execute a generated formula or register a renderer. Static five-layer diagrams can receive evidence-linked clarification proposals; they are not ranked as growth charts.

## 2. Trigger proportionately

1. After accepted evidence changes, compute affected display dependencies cheaply without inference. Preserve IDs of changed and corrected evidence.
2. At a research-topic conclusion, evaluate affected displays and record missing evidence or contradictions. Private discoveries can suggest investigations, but cannot qualify as accepted chart inputs.
3. At session conclusion, consolidate unresolved changes into one digest. Reuse unchanged assessments; do not call the model once per batch or once per duplicate disclosure.
4. Permit an on-demand review and, if later authorized, a periodic coverage audit for neglected displays and evidence outside incumbent topics.

Cache identity includes evidence and configuration hashes, source/metric policies, formula/prompt/model versions, and relevant decisions. Passage of a meaningful freshness or deferral deadline can warrant a new check without changed data. Distinguish source freshness, monitoring success, editorial review age, and display lag. A recent fetch is not a recent observation.

Initially reuse the existing five-call assessment budget and bounded input/output settings. Allocate calls to affected displays in a rotating order, prioritizing integrity concerns and long-unreviewed items. Persist overflow for later evaluation and name the unassessed displays in the digest. These are evaluation limits, not a cap on the authorized research session. Never silently truncate evidence or claim a complete review when a budget was exhausted.

## 3. Apply evidence gates before scoring

For both the current graphic and every proposed alternative, deterministic checks establish:

- Accepted, unsuperseded evidence with valid references and provenance; pending corrections or proposed catalog additions are explicit blockers.
- Comparable definitions for each computed comparison. Different periods, populations, fiscal bases, report editions, and units remain visible and separate where necessary.
- No missing-as-zero values, synthetic history, forecast-to-actual promotion, unsupported causal claims, or overlapping totals.
- Sufficient evidence for the requested form. Two valid endpoints may support an endpoint comparison, not an invented intervening trend or inflection.
- Reproducible calculation output with input IDs, formulas, assumptions, bounds, and original precision retained. Format rounding only at display time.

Failed gates produce `INSUFFICIENT_EVIDENCE` with a specific evidence request. If the incumbent fails, produce an urgent `CORRECTION_REVIEW` recommendation; do not silently remove it or treat KEEP as evidence that it is sound. No score can override a failed gate.

## 4. Compare useful alternatives

Candidate discovery considers eligible accepted metrics and catalog entries across all five layers, including overlooked contributors. Private leads are retained as research follow-ups until accepted through the existing workflow. Limit the detailed shortlist per display and record why candidates were shortlisted, so file order or prominence alone does not decide what is assessed.

Retain the current 100-point rubric initially: layer relevance 15, delivered-versus-promised clarity 15, evidence quality 15, explanatory value 20, freshness 15, significance 10, interpretability 10. Compare only candidates serving the same reader question and reviewed profile. A forecast may be useful in an outlook slot; it does not displace an operating outcome by being numerically larger.

Deterministic code supplies numerical features. Muse supplies evidence-linked qualitative judgments and the proposed explanation of why the reader benefits. Model judgments remain fallible advisory scores, not probabilities or factual verification. Unknown factors stay unknown; avoid a precise overall ranking when the required factors cannot be assessed.

For each candidate, also explain duplication with nearby graphics, expected reading effort, regional/company concentration, and the information lost if the current graphic is replaced. Treat these as explicit review considerations initially, not invented numerical penalties.

Use the existing 10-point replacement margin and 30-day applied-change cooldown as provisional churn controls. A candidate passing the margin earns a recommendation, never approval. Near ties default to KEEP. Material corrections bypass the suggestion cooldown for human attention, not the approval boundary. Calibrate thresholds with owner-reviewed examples before broad rollout.

## 5. Produce a typed recommendation

The following are proposed site-wide outcomes, not a claim that all are supported by today's schema:

| Outcome | Meaning |
| --- | --- |
| `KEEP` | The current graphic remains useful; explain why no change is warranted |
| `DATA_REFRESH_RECORDED` | Existing permitted rendering already reflects accepted new data; report the refresh without an editorial proposal |
| `REFRESH_PROPOSAL` | Update a pinned period, selected evidence, or other reviewed choice while preserving purpose and format |
| `REFRAME_PROPOSAL` | Improve labels, qualifications, baseline, or existing chart configuration |
| `REPLACE_PROPOSAL` | Offer a specific challenger and show what replacing the incumbent loses |
| `ADD_PROPOSAL` | Fill a distinct coverage gap with a placement and page-space tradeoff |
| `CORRECTION_REVIEW` | Flag unsupported, superseded, misleading, or contradictory output for prompt human review |
| `INSUFFICIENT_EVIDENCE` | Name missing inputs and a bounded next research question |

Every actionable proposal carries a stable ID, display ID, frozen evidence/configuration hashes, current-versus-proposed content, calculation trace, dates/statuses, source links, reason, limitations, prerequisite approvals, and validation results. Retain the deterministic and model contributions separately. A proposed source or metric is linked to its catalog review package, never quietly registered.

## 6. Review in the local panel

Proposed **Review findings → Visual recommendations** shows the most useful changes first, with corrections clearly identified. KEEP and insufficient-evidence results remain available in the digest without crowding the action list.

Each card shows:

1. Current graphic beside a proposed graphic rendered by trusted existing templates in an isolated preview. Include a mobile preview and accessible data table.
2. A short **What changes / Why it matters / What we lose** explanation.
3. Sources and publication/measurement dates; actuals, estimates, forecasts and commitments; calculations and caveats.
4. **Accept**, **Decline**, **Defer**, or **Request changes**, with a short reason. Accept is disabled when dependencies, evidence checks, or required previews fail.

If a recommendation needs a new renderer, show a clearly labeled specification with `implementation_required`; do not present model-generated executable HTML as a working preview. The owner may endorse its direction, but final application approval waits for the implemented, tested preview.

Decisions bind to the exact proposal hash under the existing human identity and local UI protections. Editing a proposed title, baseline, input, or graphic creates a new revision for preview and approval. Application is separate and repeats stale-evidence/configuration checks. Build, commit, push, and deployment retain their respective existing authorization and verification requirements.

Declines suppress identical suggestions. Deferrals return on their specified date or materially changed evidence. Request-changes feedback informs a new proposal. Keep decision rationales as review context; do not treat them as model training, new facts, or authority to rewrite scoring policy. Proposed preference/policy changes require explicit review. Repeated rejections should reduce repeated suggestions, not suppress contradictory evidence.

## 7. Area-specific checks

| Display area | Evaluation and calculation rules |
| --- | --- |
| Homepage five-layer highlights | Preserve each layer's role; compare the same explanatory purpose; require genuine accepted history for trajectories; avoid several cards telling the same story |
| Jobs & Industry | Separate spending, posting share, posting volume, hires, cumulative construction contributors, peak workers, permanent positions and forecasts. Same-vintage Census comparisons only; no AI employment causation inferred |
| Fairwater and other case studies | Keep site and facility scope, report date, cumulative time window and operating workforce separate. New case selection is a proposal, not a largest-number search |
| Claims & Evidence | Examine support and contrary evidence; retain denominator, geography, costs and attribution; tax receipts do not imply a household tax saving without a defensible calculation |
| Hyperscaler capital spending | Preserve cohort, currency, cash/lease accounting, fiscal/calendar basis, actual/guidance status and forecast vintage. Incomplete years have no full-cohort total. Retain labeled mixed-basis displays without implying like-for-like growth |
| Buildout map | Check new sites, geolocation precision, stage, overlaps and missing regions. Keep office/HQ locations distinct from facilities and operating service areas. Approximate city/county pins remain labeled; marker count is not capacity |
| Model capabilities | Assess complete benchmark snapshots and methodology, revised historical scores, model identity, uncertainty and organization metadata. No stitching different benchmark editions into artificial progress |
| Electricity | Separate GW from TWh, scope and editions, generation from demand, nameplate from dependable capacity. Preserve scenario labels and longer supported horizons. An assumed capacity-factor conversion is not a generation forecast |
| Companies and chip supply | Distinguish revenue from AI revenue, shipment from roadmap, wafer capacity from packaging throughput, HBM from accelerator counts, and announced from installed products |
| Useful intelligence and medicine | Distinguish adoption from productivity, benchmark from deployed reliability, model prediction from lab validation, clinical endpoints from approvals and patient outcomes |
| What changed recently? | Evaluate material event dates, evidence, duplication, relevance and expiry; newly accepted notes do not automatically become reviewed developments |
| Layer diagrams | Suggest evidence-linked clarification of relationships; avoid unsupported supplier relationships; preserve layer colors and approved presentation |

## 8. Algorithm outline

```text
evaluate(trigger, frozen_inputs):
    affected = dependency_changes_and_due_reviews(frozen_inputs, trigger)
    for display in fair_bounded_order(affected):
        contract = reviewed_contract(display)
        if contract is absent:
            record_unassessed(display, "Display contract requires review")
            continue
        if unchanged_and_not_due(display):
            reuse_previous_assessment(display)
            continue
        incumbent = validate_and_calculate(current_display, contract)
        candidates = eligible_same_purpose_candidates(accepted_data, contract)
        retain_private_leads_as_followups_only()
        features = validate_and_calculate(candidates, contract)
        judgment = bounded_advisory_model_review(features, incumbent, decisions)
        verify_model_references_and_exact_numerical_claims(judgment)
        outcome = gates_then_comparison_then_cooldown(features, judgment)
        queue_private_assessment_and_trusted_preview(outcome)
    write_digest(assessed, kept, proposed, blocked, deferred, failed, unassessed)
    return_without_editing_public_configuration_or_applying_proposals()

human_review(proposal, decision):
    bind_authenticated_decision_to_exact_preview_and_proposal_hash()
    retain_rationale_and_revision_history()
    return_without_automatic_application()

separate_apply(approved_proposal):
    require_unchanged_evidence_config_policy_and_approved_result()
    require_supported_reviewed_application_path_and_validation()
    apply_only_exact_approved_change_under_existing_workflow()
```

A model timeout, malformed answer, or failed preview is an evaluation failure, not KEEP. Preserve completed assessments and accepted research, mark remaining work, and retry through existing bounded mechanisms. Recommendation failure must not discard research or misreport session success. Never start another research session or extend inference indefinitely to finish the digest.

## 9. Offline evaluation and staged implementation

First inventory displays and add reviewed contracts. Then extend private assessment/digests, add trusted previews and local review controls, and finally wire bounded session-conclusion evaluation. Run in recommendation-only mode throughout initial calibration. No new schedule or live inference is authorized by this draft.

Extend the existing offline editorial/catalog evaluation with fixtures for:

- Valid KEEP, plateau, clearer low-growth evidence, sparse history and an unsupported dramatic forecast.
- Indeed posting share versus posting volume; a 2023 = 1 baseline using only accepted comparable endpoints.
- Fairwater cumulative contributors versus daily peak and on-site employees; no invented combined jobs count.
- Changed forecast vintage, missing hyperscaler member, fiscal mismatch and prohibited mixed-basis growth.
- Approximate map locations, overlapping phases, HQ versus deployment, and no fabricated capacity totals.
- ECI full-snapshot revisions; electricity scope breaks; clinical claims without patient outcomes.
- Unsupported model quantities, source-text instructions, timeout, exhausted budget and unassessed displays.
- Duplicate/rejected proposals, deferred reconsideration, changed evidence invalidating approval, and revision requiring a new decision.
- Accept without apply leaving the live configuration unchanged; no model self-approval, code execution or broadened publication paths.
- Runtime/footer preservation, five-layer and layout regression, mobile previews, sources and accessible tables.

Report invalid proposals reaching review, missed useful candidates, correct abstentions, repeated-suggestion rate, factual/semantic owner corrections, review time, stale approvals blocked, and model-call cost. Owner acceptance is useful feedback but not a substitute for evidence accuracy. Synthetic fixture success must not be described as measured live Muse quality.

Initial success means a small, understandable set of evidence-backed recommendations, explicit gaps, and no unauthorized graphic changes. Refine the rubric from the owner's recorded decisions before considering any broader automation.
