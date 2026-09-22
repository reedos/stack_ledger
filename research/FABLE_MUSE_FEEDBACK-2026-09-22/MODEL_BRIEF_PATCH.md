# Patch proposal · `research/MODEL_BRIEF.md`

**Version target:** brief dated 2026-09-09 (or successor)  
**Risk:** low — prompt text only; no schema change  
**Bump:** after merge, bump `metric_rules_version` and/or `note_rules_version` in `runtime.json` only if extract/screen meaning changed enough to invalidate the review ledger (these additions should).

---

## 1. Extend § “Distinctions that must survive extraction”

After the existing paragraph (announcement / financing / … / never fill a missing year), **append**:

```markdown
Grid and interconnection tiers are separate measurements: a large-load or data-center interconnection *request* (queue MW/GW) is not a studied or planning peak, is not MW *approved to energize*, and is not observed operating load. Generation and storage interconnection queues are not large-load customer queues; never write a large-load queue figure onto a generation-queue metric or a delivered IT MW metric. Operator "could rise to" executive-summary projections are not the same as a labeled study-case or figure path in the same report — keep both if supported, never collapse them. CapEx guidance is not cash CapEx already spent and not commissioned capacity; prefer the issuer's own IR press release, official earnings transcript page, or SEC exhibit over a secondary news or third-party call transcript. Syndicated copies of one release are one source. Federal Register rules and executive orders are policy *events* (controls, lists, permitting definitions); they are not chip shipment volumes or tonnage. Method-disclosed null or negative productivity results are preserved as observations with their stated scope — not discarded as "bad news" and not generalized beyond the study setting.
```

---

## 2. Extend § “Screening rules for reviewer passes”

After “Do not reject to be safe and do not accept to be helpful.”, **append**:

```markdown
If the document is news or analysis *about* an ISO/RTO, EIA, or company IR figure, and the numeric claim is not taken from the operator/issuer primary text in this document, treat primary follow-up as required: support a private lead or empty result with reason, not a publishable observation on an energy or CapEx metric. CapEx guidance whose only support is a secondary transcript or wire rewrite fails attribution_correct / basis_correct for `capital-guidance-*` metrics. A large-load queue number offered for a delivered-load, generation-queue, or operating-IT metric fails scope_matches.
```

---

## 3. Add rows to § “Worked examples”

Append these rows to the existing table (hypothetical wording, not evidence):

```markdown
| ISO says ~400 GW of large loads seeking interconnection, mostly data centers | Observation on a *large-load queue* metric only; not energized load, not generation queue, not delivered IT MW. |
| Operator: N MW approved to energize since year Y; note says not all observed operational | Record approved-to-energize with the caveat in the note; do not call it operating MW. |
| Exec summary: peak "could rise" from A GW to B GW in ~10 years; a figure shows a lower path | Keep both if both are supported; label statuses; never average or replace the figure with the headline. |
| News article: RTO workshop projects X GW by year Z; no PDF excerpt in the document | Empty or private lead; next evidence is the official load-forecast PDF — do not publish X from the news article onto the peak metric. |
| Secondary site: company "raising CapEx to $220B"; IR press release says "about $200B" | Prefer IR/SEC; reject or private-lead the secondary $220B for capital-guidance metrics. |
| Official IR transcript: CapEx guidance $195–205B for CY2026 | company-commitment or forecast per metric rules; precision range; vintage = this disclosure. |
| Federal Register Entity List addition (doc number + date) | Policy event / note — not a chips volume observation. |
| RCT: developers using AI tools took 19% longer on real issues | Preserve as observation with task, sample, and tool scope; not a universal productivity claim. |
| RCT: AI helps in-frontier tasks and hurts outside-frontier tasks | Preserve both directions; do not publish only the positive arm. |
| HBM "revenue more than doubled" with no absolute $ or units matching a metric | Note or empty; do not invent a volume observation. |
| Analyst CoWoS wafer-start/month figure not in the issuer transcript | Empty / private lead; not a TSMC observation. |
```

---

## 4. Optional one-line addition to § “Decision routine” step 4

After “Never invent metric IDs…”, **append**:

```markdown
If a supported number fits no supplied metric because scope differs (for example large-load queue vs generation queue), return empty for observations and, when the schema allows a private catalog proposal, propose a new metric with unit, geography and why existing IDs are wrong — never force a bad fit.
```

(Only include this bullet if the private catalog-drafting schema is actually in the prompt path for that lane; otherwise keep it in OPERATING_GUIDE only.)
