# Patch proposal · `research/OPERATING_GUIDE.md`

**Version target:** guide with “Research decision routine · September 8 lessons”  
**Risk:** low–medium — teaching examples + CapEx/ISO primary-source doctrine; no publication allowlist change

---

## 1. Extend the teaching-examples table

In § “Research decision routine”, after the existing table rows, **append**:

```markdown
| ISO/RTO large-load *queue* GW (requests seeking interconnection) | Route only to a large-load-queue metric (or private catalog proposal). Never use generation/storage queue metrics or delivered IT MW. |
| MW *approved to energize* with operator caveat that not all are operational | Preserve the milestone and caveat; do not equate to coincident operating load. |
| Studied / Officer-letter / firm vs non-firm *planning* peak vs TSP-provided forecast | Keep as separate forecast observations or notes; do not collapse into the queue total. |
| Exec-summary "could rise to X GW" vs lower labeled figure/table path in the same PDF | Record both when supported; never average; status stays forecast until an actual is disclosed. |
| News/wire story citing an RTO workshop or slide deck without primary PDF text | Private lead + `next_evidence` = official LTLF/ITP/LAS PDF; do not publish the news number. |
| Secondary earnings transcript or Fool/AP CapEx figure vs issuer IR press release | Prefer IR press release, official IR transcript page, or SEC exhibit. Secondary-only CapEx → private lead or reject for `capital-guidance-*`. |
| Official IR: CapEx guidance range for a named calendar/fiscal year | Attributed company-commitment/forecast with vintage; precision `range` when two bounds; do not extend to later years. |
| Federal Register / BIS Entity List / advanced-computing rule; White House EO on data-center permitting | Grade-A *event* candidates (policy spine). No chip tonnage or shipment inference. |
| Method-disclosed RCT with null or negative productivity finding | Preserve with scope (task, population, tools). Do not drop as anti-promotional. |
| Partial HTML extract of a PDF-only report | `partial exposure` + which section/table is needed; do not assert the PDF contains nothing useful. |
| HBM or packaging claim with only YoY qualitative language (e.g. "doubled") and no metric-compatible units | Note or empty; do not invent shipped volumes. |
```

---

## 2. New subsection after “Evidence decisions” (or under Energy bullet in Coverage)

**Insert:**

```markdown
## ISO/RTO and CapEx primary-source rule (September 22, 2026)

Large-load and peak-load figures used for public energy metrics should come from operator-published materials (ERCOT board and Constraints & Needs reports, PJM Load Forecast Report and LAS summaries, SPP ITP, MISO LTLF whitepapers) or from reviewed importers — not from secondary news paraphrases of workshops.

Hyperscaler CapEx *guidance* for `capital-guidance-*` metrics should come from the issuer's IR news release, official earnings-event transcript page, or SEC exhibit that states the figure. A third-party call transcript or news rewrite may seed a private discovery lead and must name the primary IR URL in `next_evidence`; it must not be the sole support for a published CapEx guidance observation.

When HTML collection cannot read a PDF, that is a collection gap (see collection cooldowns: unsupported formats). It is not permission to accept a journalist's restatement onto the metric. Curated PDF import and human-approved `--question` packs remain the path until a reviewed PDF text extraction path exists.
```

---

## 3. Strengthen Energy coverage bullet

Replace or extend the Energy bullet under Coverage:

**Current idea:** actual generation and grid connections; …

**Append:**

```markdown
Distinguish generation/storage interconnection queues from large-load (data-center) interconnection queues; distinguish queue requests, studied/planning peaks, approved-to-energize milestones and observed operating load. Prefer ISO/RTO primary PDFs or importers for those figures.
```

---

## 4. Applications coverage bullet

**Append:**

```markdown
Prefer method-disclosed trials and RCTs (including null/negative results) over vendor productivity claims. Keep study setting, tool vintage and sample in the note.
```

---

## 5. Chips coverage bullet

**Append:**

```markdown
HBM and advanced-packaging *shipped* volumes need issuer units that match a metric; qualitative "doubled" revenue without a compatible number stays a note. CoWoS or packaging wafer-start rumors from analysts are not issuer observations.
```
