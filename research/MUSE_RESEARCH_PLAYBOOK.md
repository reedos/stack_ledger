# Muse Glimmer research playbook

Effective guidance: September 8, 2026. Maintainer-authored operating documentation based on the [Astra research pass](ASTRA_RESEARCH_REPORT-2026-09-08.md). This document is instruction and evaluation design, not evidence for any public claim. The constitution and existing publication restrictions remain in force.

## What Muse actually receives

`research.py` supplies `CONSTITUTION.md` and `OPERATING_GUIDE.md` to monitoring extraction, skeptical screening and discovery. Private catalog drafting receives the same supplied instructions. The operating guide contains the compact decision routine and worked examples; this longer playbook is a maintainer reference, not a file the model can independently open. The saved-evidence discovery replay loads the same operating guide.

The model returns the requested schema only. It cannot run searches itself, execute commands, approve a proposal, modify policy or publish. The maintained runner handles collection, validation, storage and authorized publication. Do not copy the checklists below into model JSON as unsupported fields.

## A useful research unit

Complete one evidence question, or leave a precise unresolved handoff:

1. **Identify.** Match the entity, product version, site, phase, geography and period against accepted catalogs. Consider acquisitions, renamed products and overlapping programs. Do not treat a familiar company name as proof that the finding is already covered.
2. **Read.** Inspect the available primary evidence and its exposed ranges. Confirm whether a statement describes an announcement, target, estimate or reported result. Multiple syndicated copies of one release are one originating source.
3. **Compare.** State what changed from the incumbent. Seek contradictions and constraints as well as progress. Keep old forecasts and correction history; a newer page is not automatically a stronger source.
4. **Route.** Propose a numerical record only for an exactly fitting approved metric. Otherwise use an attributed note, private discovery finding, or private catalog package. A correction must preserve the original record. A valid announcement can be worth tracking before there is measured delivery.
5. **Continue.** Name the next evidence that could change the conclusion. Explain an empty/duplicate result or a collection gap. No result is preferable to invented progress.

Preserve history only where definitions are comparable. Retain explicit 2035, 2040, 2050 and later outlooks when available. Do not infer missing history, forecasts, job counts, capacity or outcome improvements.

## Follow-up cards using existing fields

Use a project's `next_evidence`, a product's `gap`, or a discovery finding's `next_question`. For reviewed editorial questions, use the existing editorial question queue. Keep within each field's existing length limit; do not create a parallel task database.

Write the question in this form:

> Verify **the specific unresolved fact** using **the named issuer or primary source type**. Change the assessment only if **the required evidence** is present. Revisit at **a disclosed milestone, release cycle or explicitly suggested trigger**; date unknown if no date is disclosed.

Examples are hypothetical task wording, not claims:

| Current evidence | Useful next question |
|---|---|
| Optical component sampling | Seek the issuer's next product or earnings disclosure confirming qualification and volume shipments. Keep sampling until supported; do not infer unit volume from link speed. |
| Plant commissioning | Seek the operator's commercial-operation notice and relevant regulator/grid record. Record capacity and generation with their own units and dates. |
| Proposed campus expansion | Establish parcels and phase boundaries against the existing campus before aggregating power, capital or jobs. |
| Training cohort graduated | Seek verified placements, employment basis and follow-up period. Graduation alone does not establish hiring. |
| Open model released | Check exact checkpoint license, hosted availability and reproducible task evaluations. A hosted endpoint retirement does not retract already released weights. |
| Annual guidance | Revisit the next dated earnings update. Preserve the old forecast vintage and distinguish fiscal-year changes, revisions and actual results. |

These are research directions. They do not create timers, bypass source cooldowns or grant authority to collect from a new public source. The runner's accepted-catalog follow-up rotation uses the existing discovery adapter and budgets. It cannot guarantee finding every successor disclosure. Human review determines whether the evidence resolves a reviewed question.

## Coverage and revisit priorities

Prioritize energy and infrastructure delivery while retaining coverage of all five layers. Use the full accepted catalogs, not the homepage or first page of a directory.

| Layer | Functional sweep | Stronger evidence to seek |
|---|---|---|
| Energy | Generation, grid service, transmission, storage, electrical equipment, affordability | Generation/output records, energized connections, permits and actual customer costs |
| Chips | Design/IP, foundries, HBM, packaging/substrates, tools, storage, DSPs, copper, lasers and optical I/O | Qualification, shipments and comparable production throughput; distinct from specifications |
| Infrastructure | Developers, operators, contractors, electrical/cooling suppliers, commissioning and trades | Operational IT power, phase boundaries, local procurement and reported workforce |
| Models | Commercial/open builders, artifacts/licenses, serving, agents and harnesses | Versioned availability, task reliability, total inference/task cost and limitations |
| Applications | Software, wider digital work, robots, medicine, science and climate | Completed work, denominators, comparison conditions, quality and independent outcomes |

For maintainers: prioritize approaching disclosed milestones and earnings windows; propose lower-frequency checks for unchanged historical reports. Repeated accessible-but-unchanged evidence is a cadence signal, not a reason for more model calls. Use existing policy changes and review mechanisms to adjust cadence. No schedule or cadence change is enacted by this document.

Missing filings, local-language sources, PDFs, workbooks or JavaScript-only evidence require a collection-gap handoff with the source and why it matters. Seek an accessible primary equivalent within current permissions. A parser or adapter change is maintainer work; never repeatedly retry unsupported formats or bypass access controls.

## Calibration before relying on the new drafting path

Owner: maintainer and designated human reviewer. Muse is the system being evaluated. It cannot grade its own performance or approve its expected answers. Existing offline tests verify software behavior; they do not establish live model accuracy.

Prepare a small fixed suite from retained documents before a long production trial of changed prompts/model versions:

1. Select 20 cases: ten purposive cases covering the table below, plus ten sampled from actual retained outcomes (four accepted candidates, three rejected, three empty). Use a recorded sampling seed and record missing strata; never fabricate replacement documents. Avoid duplicates across the groups.
2. Freeze source URL, publication/retrieval dates, body hash, exposed ranges, catalog snapshot, model version, instruction/implementation hashes and sampling method. Keep source bodies and detailed responses private in the existing evaluation area.
3. A human checks expected supported facts, prohibited inferences, appropriate output route and uncertainty. Astra-generated labels remain draft expectations until reviewed. Do not supply expected answers to Muse's extraction or screening prompt.
4. Run a bounded saved-evidence replay only when explicitly started, with publication disabled and the existing exclusive locks. Evaluate extraction/screening and catalog drafting separately. Do not launch a replay from a readiness check.
5. Compare outputs with frozen expectations. Save every outcome, including timeouts, malformed responses and missing evidence. Correct the cause, then rerun affected cases and an unchanged holdout; retain prior results.

| Case family | Expected behavior |
|---|---|
| Useful announcement without delivery data | Preserve an attributed commitment as a private candidate |
| Sampling or fuel loading | Avoid promotion to production/commercial operation |
| Overlapping phases or repeated releases | Flag overlap/duplicate; do not add quantities |
| Contracts and employment categories | Preserve accounting basis, period, employer and units |
| Fiscal-year actuals and guidance | Keep actual/forecast distinction and vintage |
| Coding/scientific benchmark | Do not infer universal productivity or patient benefit |
| Null or mixed clinical result | Retain primary endpoint, uncertainty and limits |
| New contributor / known company with new product | Recognize eligible missing coverage |
| Partial exposure or inaccessible source | Record the actual limitation; no exhaustive negative claim |
| Irrelevant text or embedded instructions | Return a supported empty result; ignore document instructions |

Record supported-claim precision and useful-finding recall separately, with numerator/denominator and coverage strata. Report abstentions, measurement/stage errors, invented facts and invalid outputs separately. A tiny purposive set cannot estimate industry-wide recall. Human reviewers should investigate any unsupported material assertion or permission violation before recommending a longer publishing run. Do not relax evidence checks to improve yield. This is a review procedure, not a newly implemented automatic scheduling gate.

Existing tools:

```powershell
# Offline audit of an actual retained session; substitute its existing ID.
python scripts/evaluate_collection.py --session <32-character-session-id>
# Plan only: no model calls.
python scripts/evaluate_discovery_model.py
# Explicit opt-in only: invokes Ollama on the existing two saved cases.
python scripts/evaluate_discovery_model.py --run
```

The existing replay supports two fixed discovery cases, at most four calls and 240 seconds. It does not yet run the 20-case suite or evaluate catalog drafting. Extending that harness is a separate implementation task; do not claim this documentation completed calibration or that the two-case result validates the whole workflow.

## Review feedback that can improve the next run

Use existing review decisions and their rationale fields; do not invent new status values. Begin the rationale with a descriptive reason code when useful:

`SUPPORTED`, `DUPLICATE`, `WRONG_SCOPE`, `WRONG_STAGE`, `OVERLAP`, `DATE_OR_VINTAGE`, `UNSUPPORTED_OUTCOME`, `PARTIAL_EVIDENCE`, `COLLECTION_GAP`, or `NEEDS_CORROBORATION`.

Include the evidence/record ID, the specific error or supported fact, the corrected interpretation and the next action, within the existing rationale limit. Example: `WRONG_STAGE: source <id> confirms samples only. Retain sampling; seek a dated volume-production disclosure.` Codes explain a decision; they neither select the decision nor approve publication.

The maintainer periodically groups recurring errors, checks the original evidence and promotes reviewed lessons into the operating guide. Rejected/empty cases must be sampled as well as accepted ones to find missed useful research. Review logs are not automatically injected as policy or training, and this is not model fine-tuning. Never let source prose or a model-generated rationale alter instructions.

## End-of-run oversight checklist

Use existing session `research-progress.md/json`, monitoring/discovery receipts, review decisions and catalog publication receipts. The following is the maintainer's desired digest, not a claim that every field is already automatically aggregated:

| Report item | Required basis |
|---|---|
| Questions resolved | Recorded human question decision and supporting evidence; proposals are pending |
| Useful additions prepared | Unique review packages/object changes linked to evidence; distinguish duplicates |
| Coverage adopted | Applied catalog diff; count companies, projects, products and metrics separately |
| Remaining handoff | Pending review, approved/not applied, accepted/not displayed, or pushed/deployment pending |
| Research health | Unique content and exposure where recorded, rejected/empty reasons, failures/cooldowns and unsupported formats |
| Next priorities | Unresolved high-value questions, next primary sources and milestone triggers |

Do not substitute document fetches, elapsed hours, model calls or GPU utilization for useful evidence. A successful push does not mean new findings or verified deployment. Unknown historical receipt fields stay unknown. Refreshing a source does not refresh an observation's date or an editorial review.

After each session, inspect publication/collection failures and the pending handoff. After prompt/model changes, review calibration results before recommending a long publishing run. As a suggested weekly human routine, inspect a spread of accepted, rejected and empty findings and update the reviewed examples. This creates no extra scheduled task or Telegram messages. Existing session duration, idle waiting, stop/overlap behavior, notification scope and runtime/footer presentation remain unchanged.

## Explorer follow-ups

- **Projects:** Start from all accepted `delivery.projects`, including unmapped records. A locality pin does not verify facility boundaries, construction progress or energized capacity. Propose exact evidence-linked catalog changes in the existing private queue; preserve distributed programs without a fabricated point.
- **Capital:** New issuer disclosures should resolve fiscal dates, cash versus noncash leases, net proceeds, actual versus guidance and whether amounts are company-wide. An accounting reclassification is not necessarily reduced investment. Preserve earlier guidance as a dated superseded record after review. The reviewed simple-sum chart adds fiscal years ending in the same year, with all five companies required and the differing bases visible; never call this a calendarized or AI-only total.
- **Capabilities:** New Epoch rows or a refitted ECI vintage are a private follow-up lead. A maintainer must review the entire dataset/uncertainty snapshot and its provenance before replacement. No benchmark score establishes dependable business outcomes by itself.

The `manual` source cadence prevents unsupported archive fetches in ordinary runs. Existing extraction/review rules still apply to monitored capex disclosures; daily models cannot edit source policy, geography, chart configuration or capability snapshots. Accepted monitoring observations feed maintained renderers; accepted project catalog changes feed map/list counts. A pending proposal is not displayed evidence.


The expanded map is still a sample, not a census. Seek underrepresented suppliers, regions, training sites and application deployments; company headquarters alone do not justify a project marker. Avoid counting regional portfolio roll-ups as extra facilities alongside their named components. Propose only sourced locality/stage changes through existing review. ECI country metadata must remain attached to the same dataset vintage, with unknowns explicit. Chart filters never constrain research coverage. Prioritize newer full-cohort capex forecasts beyond 2026, but never update a single member of the fixed September 2025 forecast vintage or silently join it to current guidance.


### Geographic follow-up and service markets

Research may establish a useful locality before a street address is available. Propose a city/county with primary location evidence and a separate delivery stage; approximate coordinates do not mean a project is unconfirmed. For distributed programs and robotaxi services, propose city-level availability, testing, supervision and future-launch changes without multiplying project totals or allocating fleet/miles across cities. Preserve source publication dates and review dates separately. Check Waymo's Serving Riders In versus Up Next lists and Tesla's limited-area availability; the July 2026 Bay Area safety-driver disclosure requires a newer city-specific follow-up.

The maintainer's reviewed `map_locations` and company `map_offices` fields are rendering metadata, not new model publication permissions. Use the existing private catalog findings queue to supply location evidence and recommended changes for review. Headquarters/registered offices belong only in the separate office overlay, never as fabricated training or construction projects. Pursue missing developer geographies, including China and open-model organizations, and missing facility localities. A longer run or more pins is not proof of comprehensive coverage.

### Hyperscale coverage reconciliation

The September 9 audit found Prometheus missing even though Meta's engineering and location pages identify it. Search-driven discovery had not reconciled operator inventories against accepted objects. Treat this as a coverage failure: monitoring existing IDs cannot discover every omitted campus.

Use the existing discovery and catalog review flow to compare operator directories, new campus announcements, investor disclosures and local permits with **all** accepted projects, including unmapped and `status-unverified` entries. The infrastructure discovery rotation now includes directory reconciliation and overlooked gigawatt campuses. These are private research questions, not automatic import or approval rules. See [the coverage audit](HYPERSCALE_COVERAGE_AUDIT-2026-09-09.md) for the initial operator matrix and unresolved work.

Resolve aliases before proposing additions: Prometheus / New Albany, Hyperion / Richland Parish, Frontier / Shackelford and Lighthouse / Port Washington can otherwise be missed or duplicated. A renamed tenant or campus is a revision question, not necessarily a new location. Separate the original Stargate Abilene campus from Crusoe's adjacent Microsoft development, and retain the dated change in customer evidence at Narvik.

For every reviewed directory entry, report an accepted project match, a private proposed addition, a duplicate/overlap, or a specific unresolved evidence gap. Do not silently discard entries without capacity or exact coordinates. City/county orientation is useful; a cloud region or availability zone is not an individual facility. `status-unverified` means the location is evidenced but the delivery stage is unresolved; never recast it as construction, delay or operation. Propose dated stage corrections as priority follow-ups.

Give missing large campuses priority, but do not use a 1 GW threshold to exclude smaller projects or new operators. Expand across hyperscalers, neoclouds, sovereign AI and regional developers worldwide. Preserve distinctions among critical IT load, facility power, generation, requested/approved grid service and contracted capacity. An MoU, target year, approved megawatts or directory listing cannot establish delivered AI capacity. Report coverage against a named, dated inventory; never claim worldwide completeness from the number of records collected.
