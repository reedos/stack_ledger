# Focused editorial correction pass — September 8, 2026

The owner reviewed this correction pass and subsequently authorized verification, commit, push and deployment. This report describes the final changes and checks.

Prepared at: 2026-09-09T03:51:53Z.

## Exact note changes

### NVIDIA describes NVLink Fusion for custom XPUs

[Source](https://blogs.nvidia.com/blog/nvlink-fusion-xpu-ai-factory/) · Publication date: 2026-08-24. Original ID: `note-f21b782b05987822e4db`; replacement: `correction-f21b782b05987822e4db`.

**Classification:** Research finding → Company announcement.

**Previous title:** NVLink Fusion enables XPU integration with NVIDIA AI infrastructure

**Before:** NVIDIA announced NVLink Fusion to connect custom XPUs to its AI infrastructure, aiming to increase performance and accelerate time to market for semi-custom AI factories.

**After:** NVIDIA describes NVLink Fusion as a way to connect custom XPUs to its AI infrastructure. The company presents performance and time-to-market benefits for semi-custom AI factories; the article does not establish measured deployment gains.

**Reason:** Classifies a company architecture announcement; avoids implying an initial launch or measured deployment gains.

### Amazon Nova Act SDK research preview

[Source](https://www.aboutamazon.com/news/innovation-at-amazon/amazon-nova-website-sdk) · Publication date: unlisted. Original ID: `note-bdf88a88599fdadd3400`; replacement: `correction-bdf88a88599fdadd3400`.

**Classification:** Research finding → Company announcement.

**Unchanged summary:** Amazon announced a research preview of the Amazon Nova Act SDK on nova.amazon.com, allowing developers to experiment with an early version of a model trained to perform actions within a web browser.

**Reason:** Classifies research-preview availability as a company announcement rather than a measured research result.

### Nebius multi-billion dollar Microsoft AI infrastructure agreement

[Source](https://nebius.com/newsroom/nebius-announces-multi-billion-dollar-agreement-with-microsoft-for-ai-infrastructure) · Publication date: 2025-09-08. Original ID: `note-388bb6fc196f6f62b89d`; replacement: `correction-388bb6fc196f6f62b89d`.

**Classification:** Research finding → Company announcement.

**Before:** Nebius announced a multi-year agreement to deliver dedicated AI infrastructure capacity to Microsoft from its new Vineland, New Jersey data center starting later in 2025. The company said the deal will support more aggressive growth of its AI cloud business in 2026.

**After:** In its September 8, 2025 announcement, Nebius said it would deliver dedicated AI infrastructure capacity to Microsoft from its Vineland, New Jersey data center under a multi-year agreement, with delivery planned to begin later in 2025. This records the agreement, not subsequent commissioning.

**Reason:** Classifies the agreement as a company announcement and limits the summary to the retained evidence; removes the 2026 growth statement.

### America’s Workforce Academy first cohort graduates

[Source](https://about.fb.com/news/2026/08/americas-workforce-academy-meta-skilled-trade-training-program/) · Publication date: 2026-08-18. Original ID: `note-6da38e8f55121f0e70a0`; replacement: `correction-6da38e8f55121f0e70a0`.

**Classification:** Research finding → Company announcement.

**Before:** Meta reports the first cohort of America’s Workforce Academy graduated last week and will work at Meta construction sites. The free program guarantees jobs for graduates and awards NCCER credential and AWA certificate, funded by an initial $115 million first-year investment.

**After:** In its August 18, 2026 update, Meta reported that the first America’s Workforce Academy cohort had graduated the preceding week. Meta described a free program with credentials and guaranteed jobs, backed by an initial $115 million first-year investment. This is a company-reported milestone, not a verified placement count.

**Reason:** Anchors relative timing to the source publication date and distinguishes a company announcement from verified job placements.

## Excerpt and attribution reconciliation

| Source | Previous → corrected | Meaning |
| --- | --- | --- |
| Lumentum | company-commitment → observation | Reported completed accelerated test; not field exposure or zero future failure risk. |
| Isomorphic | company-commitment / roadmap → observation / financial | Funding reportedly raised is distinct from future therapeutic outcomes. |
| Nebius | observation → company-commitment | Future capacity delivery is not commissioned capacity. Notes use the corrected agreement summary above. |
| Meta | unassigned company / global / other → Meta / United States / labor | Correct source attribution; notes use the dated milestone summary above. |

Each changed excerpt retains the previous changed fields, a reason, and a correction timestamp in `correction_history`. Quotations and retrieval timestamps are unchanged. Isomorphic and Meta collection metadata and the source-book snapshot are synchronized; hosts, paths, cadence, topics, and collection permissions are unchanged.

## Implementation and preserved boundaries

- Four curated replacements use the existing ledger, with `correction_of`, `correction_reason`, and `corrected_at`. All 53 original events are unchanged, including all original model evidence hashes. The four replacement proofs reuse the retained passages, with source publication dates separately preserved. No original proof was overwritten.
- Ordinary ledger and layer views select current records. A Corrected badge, explanation, and expandable original note make the history readable. Old deep links reveal that history rather than disappearing.
- The Atom feed uses replacement entries and related links to originals. Its updated timestamp advances for editorial corrections; source publication dates retain their original meaning. Research runtime timestamps do not advance.
- The daily publisher now checks record-level deltas, including retrying a pending daily commit. It rejects edits to existing records, new curated records, and note/excerpt correction metadata. No model approval or publication permission was added.
- Observations, metrics, targets, existing runtime identity/timestamps, run receipts, approved homepage content, source URLs, and source publication dates are unchanged. The separately requested session aggregate is added below. The four replacements do not count as newly researched findings.
- The broader extraction-classification heuristic and pending-handoff review-panel work remain follow-ups. They are not required for this correction pass and are not represented as fixed here.

## Validation

- `python scripts/validate.py`: passed.
- `python scripts/build.py`: built 107 pages.
- `python -m unittest discover -s tests`: 212 tests passed, including correction/publication boundaries and whole-session summary tests.
- `python scripts/evaluate_editorial.py`: offline scenarios passed.
- `node tests/browser.cjs`: passed 24 routes and three viewport sizes, plus all four correction and original-note deep links at desktop and mobile widths.
- Visual review: corrected Meta card inspected at 1440 and 390 pixels; wording, dates, history control, and spacing are legible.
- All original events are unchanged. The owner-requested footer summary changes the runtime text and adds a validated session aggregate; protected footer template, CSS, hardware identity and existing timestamps remain unchanged.
- `git diff --check`: passed.

An initial build identified the source-book snapshot that also needed synchronization with the corrected collection metadata. An initial browser assertion incorrectly assumed an expanded history panel would close during same-page fragment navigation; the test now loads a fresh page when checking the default collapsed state. Both were resolved before the passing checks above.

No research session was started for verification. Commit/push/deployment were subsequently authorized by the owner. This pass does not claim an independent audit of every curated statistic.


## Follow-up: clarify the footer's batch receipt

The owner flagged the footer's “Latest run” line. It summarizes the final monitoring batch, not the full controller session. The final batch fetched four documents and accepted none; the retained seven-hour session summary contains 1,339 document fetches, three accepted records, 18 quarantines, and 306 batches. Fetch counts are not unique-document counts.

Both the static and enhanced footer now say “Latest monitoring batch” and explicitly state that the counts apply only to that batch. No counter, hardware detail, placement, or runtime timestamp changes. The earlier exact runtime comparison above predates this separately requested wording correction. The subsequent owner request adds an aggregate-only whole-session summary to the footer, reusing all retained batch receipts. Private evidence and routing remain local.


## Final session-summary verification

The footer now reports the latest total session (420 minutes, 306 batches, 1,339 fetches, 282 model calls, three accepted records, 18 quarantines, 575 source failures and 292 discovery errors), alongside a separately labeled final batch. All 306 batch receipts are present. Fetches include repeats; completion is not a claim of error-free research.

Publishing sessions finalize the aggregate through the existing lock, validation/build/test pipeline, and publisher. Private/discovery-only sessions stay private. Receipt verification rejects unsupported totals, errors preserve private state, and successful finalization is idempotent. No extra schedule or credential change is included.

The first full-suite run identified the exact old runtime-text snapshot. It was updated for the owner's explicit whole-session footer request; template/CSS fingerprints were preserved. The subsequent full suite passed all 212 tests. The public browser suite passed 24 routes/three viewports, including static and dynamic totals, corrected-note links and original history. The local control-panel browser suite also passed without starting research.
