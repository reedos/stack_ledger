# Research and live-site reconciliation — September 8, 2026

## Result

The live site matches the deployed accepted data. All nine automated research notes are published, reachable, and backed by retained source documents. There is no evidence in the retained session ledgers of accepted research waiting to be pushed. This is **not an editorial all-clear**: classification, source-date wording, excerpt status, and one incomplete evidence selection need reconciliation.

This audit distinguishes data delivery from scientific or editorial verification. It inventoried all retained research artifacts, checked every public automated note against its retained evidence and reopened source, and inspected the public excerpt ledger. It did not independently fact-check every sentence in all 371 cached documents or re-research all 594 curated numerical observations. A fetched document is not an accepted finding.

## What is public and what remains private

| Item | Finding |
| --- | --- |
| Live deployment | Accepted ledger equals the local ledger. All 151 deployed files match HEAD `3f39bbd9aedadb817f0298036866e95056d5b010`, allowing text line-ending normalization. |
| Public numerical observations | 594; all marked curated. Muse has not added new numerical observations to this snapshot. Unchanged charts are therefore expected. |
| Public notes | 53 total; nine automated. All nine match their private note proof, live ledger, and Atom feed. |
| Evidence integrity | 371 unique retained source bodies; no document hash corruption found. All nine note quotations occur in their retained document and match their stored hashes. |
| Run receipts | 472 local versus 469 public. The three private-only receipts have zero accepted records: two failed and one partial run from September 7 UTC. This is not three missing research publications. |
| Session ledgers | Neither of the two retained session directories contains a private accepted ledger awaiting reconciliation. |
| Quarantine | 40 occurrences representing 33 distinct candidate records across retained history. These are rejected proposals, not accepted facts missing from the website. |
| Discovery | 308 retained discovery run receipts and 78 discovery evidence files. No coverage-expansion proposal in the current private review queue. |
| Review handoffs | Seven note handoffs, seven associated metric-candidate handoffs, and five pending research questions. All seven note handoffs refer to already published notes; their possible incorporation into curated pages remains unresolved. |

The local Review findings panel currently selects discovery coverage-expansion proposals. The seven older note-to-curation handoffs do not appear there. This is a review visibility gap, not a publication failure. Extend the existing panel/queue interpretation in follow-up; do not duplicate the queue or treat an already public note as an approved chart change.

## Review of all nine automated notes

| Note and source | Assessment and disposition |
| --- | --- |
| [NVLink Fusion](https://blogs.nvidia.com/blog/nvlink-fusion-xpu-ai-factory/) — `note-f21b782b05987822e4db` | Source supports the architecture description. Reclassify Research finding to Company announcement. The August 24 article describes the offering; avoid implying this establishes its initial launch or measured deployment gains. Draft below. |
| [Veo 3 video reasoning / Stanford AI Index](https://hai.stanford.edu/ai-index/2026-ai-index-report/technical-performance) — `note-1ea1559ce6e643d86baa` | Keep as a research finding with attribution to Stanford's summary of the study. The 18,000-video experimental evidence does not establish general physical reliability or useful deployment outcomes. Publication date remains unlisted. |
| [Lumentum laser testing](https://www.lumentum.com/en/blog/reliability-becomes-new-currency-how-cpo-rewriting-laser-performance) — `note-191cdc963d3034277350` | Note is supported and attributes the result. Accelerated device hours are not field service hours, and zero observed failures is not a guarantee of zero failure risk. Its public excerpt's commitment status needs review: this is a reported completed test. |
| [Amazon Nova Act SDK](https://www.aboutamazon.com/news/innovation-at-amazon/amazon-nova-website-sdk) — `note-bdf88a88599fdadd3400` | Reclassify Research finding to Company announcement. Research-preview availability is not a measured research result. Keep the unknown publication date; do not imply the preview represents today's product state. |
| [Mortenson Richland Parish scope](https://www.mortenson.com/projects/richland-parish-data-center) — `note-70fe9bd09a1938646026` | Keep. The source supports the contractor's scope of work. The note does not establish completion of those systems. Unknown publication date stays unknown. |
| [Turner / Meta Jeffersonville](https://www.turnerconstruction.com/insights/turner-construction-company-to-build-hyperscale-data-center-for-meta-in-indiana) — `note-96a73a25700c591a9b01` | Keep as a January 25, 2024 announcement collected later. Investment and approximately 100 jobs are attributed prospective figures, not verified current expenditure or hires. |
| [Isomorphic Labs funding](https://www.isomorphiclabs.com/press/isomorphic-labs-funding) — `note-a0f76118e940cbe3b5aa` | Funding amount, date, and investor list are supported. Financing is not clinical efficacy. The excerpt mixes reported financing already raised with future therapeutic work; separate that accounting before using it as an outcome. |
| [Nebius / Microsoft agreement](https://nebius.com/newsroom/nebius-announces-multi-billion-dollar-agreement-with-microsoft-for-ai-infrastructure) — `note-388bb6fc196f6f62b89d` | Reclassify Research finding to Company announcement. The full document supports the 2026 growth statement, but the retained selected excerpt stops before that supporting passage. Prefer the narrower draft below. The source is September 8, 2025, not a new September 2026 agreement or proof of commissioning. |
| [Meta Workforce Academy](https://about.fb.com/news/2026/08/americas-workforce-academy-meta-skilled-trade-training-program/) — `note-6da38e8f55121f0e70a0` | Reclassify Research finding to Company announcement and anchor the relative graduation timing to the August 18 update. The program's job guarantee is not an independently verified placement count. The existing reviewed homepage card already handles these limitations correctly. |

## Concrete correction drafts — not applied to accepted records

Preserve original records and evidence. Use a reviewed correction with a replacement relationship; do not overwrite historic model proofs or manufacture an approval. The current event schema does not provide the observation schema's correction fields, so the correction route itself needs a reviewed implementation. These drafts are review material, not new published notes.

1. **NVLink:** change kind to `Company announcement`; title to “NVIDIA describes NVLink Fusion for custom XPUs”; summary to: “NVIDIA describes NVLink Fusion as a way to connect custom XPUs to its AI infrastructure. The company presents performance and time-to-market benefits for semi-custom AI factories; the article does not establish measured deployment gains.” Preserve source and publication date.
2. **Amazon:** change kind to `Company announcement`; retain the existing attributed preview summary and null publication date. Confirm current availability separately before updating a current-product catalog.
3. **Nebius:** change kind to `Company announcement`; summary to: “In its September 8, 2025 announcement, Nebius said it would deliver dedicated AI infrastructure capacity to Microsoft from its Vineland, New Jersey data center under a multi-year agreement, with delivery planned to begin later in 2025. This records the agreement, not subsequent commissioning.” Retain the original evidence; bind a reviewed replacement to the supporting agreement passage and revalidate it. Do not carry the unsupported-by-selected-excerpt 2026 sentence into the replacement.
4. **Meta:** change kind to `Company announcement`; summary to: “In its August 18, 2026 update, Meta reported that the first America's Workforce Academy cohort had graduated the preceding week. Meta described a free program with credentials and jobs guaranteed through its partners, backed by an initial $115 million first-year investment. This is a company-reported milestone, not a verified placement count.” Preserve the disclosure date; do not infer an exact graduation date.

Reconcile each affected public excerpt's notes alongside its corresponding reviewed replacement. In addition:

- Lumentum: classify the reported completed test as an observation, retaining company attribution and accelerated-test limits.
- Isomorphic: distinguish observed funding announcement from the planned use of proceeds. The `roadmap` collection identity is reviewed policy and must not be silently repurposed.
- Nebius: separate the observed agreement from the future capacity commitment. An observation status on mixed prose must not imply energized capacity.
- Meta: the source registry currently supplies `company_id: null` and region `global`, so the excerpt cannot be assumed to be a correctly mapped Meta company update. Review the registry mapping before relying on company filtering.

Root cause worth addressing: `research.py` derives excerpt status from note kind, mapping every Company announcement to company-commitment and otherwise often defaulting to observation. An announcement can report a completed test or closed financing, while a research-labeled note can describe a future commitment. Claim stage must be assessed separately from editorial category. Public quotes themselves pass the existing aggregate 25-word-per-URL limit.

## Quarantine and coverage reconciliation

Do not replay all quarantines as accepted records. The previous collection audit identifies recoverable numeric-token errors, but passing that check alone is not editorial approval.

- OpenAI annualized revenue pace must not become recognized annual revenue.
- ECMWF operational dates need novelty and existing-coverage checks before adding duplicate notes.
- HBM production readiness, CPO architecture, and proposed fab investment are not shipment or operational capacity.
- Micron literal greater-than markup failures can be re-extracted without changing the evidence basis.
- The Nobel candidate needs the complete prize attribution, including David Baker; the rejected wording must not be restored verbatim.
- Model release dates and disjoint evidence selections require new verification; a marketing or release claim is not a measured outcome.
- Several quarantined sources subsequently produced accepted notes, including Meta, Isomorphic, and Nebius. Counting all rejected attempts as missing site content would overstate the gap.

Across the nine automated notes, the distribution is **infrastructure five, models two, chips one, applications one, energy zero**. Energy coverage on the site remains curated. This distribution is a retained-result count, not a measure of research effort or comprehensive coverage. No new histories or homepage metrics are warranted solely by these notes.

## Live presentation and local fix

The live homepage, all five layers, company directory, projects, industry, claims, ledger, and methodology were checked at desktop and phone widths. Each automated note was also opened through its ledger deep link: 42 route/note checks in total. No page JavaScript errors, broken images, duplicate IDs, horizontal page overflow, or inaccessible note links were found in these checks. The mobile electricity chart fits the viewport; the reviewed developments cards have the intended spacing and collapsible qualifications.

Local change: research-note metadata now distinguishes source publication from collection dates for automated notes, explicitly showing an unlisted publication date when absent. Curated note dates retain a neutral “Dated” label. This makes an old announcement fetched today visibly different from a new development. This change is built locally and **not deployed**.

The runtime/hardware block, footer placement, dynamic behavior, approved homepage metrics, and five-layer organization are preserved. Generated page differences should be build/cache identifiers only; the functional public change is in `site/assets/app.js` and its generated copy.

## Verification and audit artifacts

Live baseline: [validation run](https://github.com/reedos/stack_ledger/actions/runs/34295712596) and [Pages deployment](https://github.com/reedos/stack_ledger/actions/runs/34295711544) both succeeded for the inspected HEAD.

Private artifacts are in `.local/live-audit/`: live ledger snapshot, reconciliation JSON, browser results, screenshots, and the audit scripts. They contain private research inventories and are intentionally excluded from publication.

Local verification:

- `python .local/live-audit/reconcile.py`: 151 deployed files matched; the one note excerpt issue described above remains flagged.
- Live Playwright audit: 42 route/note checks completed; no detected errors. Analytics requests were blocked during browser checks.
- `python -m unittest discover -s tests`: 200 tests passed.
- `python scripts/validate.py`: passed.
- `python scripts/build.py`: built 107 pages.
- `python scripts/evaluate_editorial.py`: all offline cases passed; no incorrect acceptance or unsupported replacement in these fixtures. This is not a live-model quality score.
- `node tests/research_control.cjs`: passed desktop/mobile, GPU chart, filtering, private default, and mocked-start checks.
- Static runtime regression: all 107 runtime footers match HEAD exactly. Generated HTML differs only in build/cache identifiers.

`node tests/browser.cjs` passed: 24 routes, three viewports, filtering/pagination, deep links, keyboard access, no-JavaScript navigation, revenue histories/forecasts, and runtime dynamic behavior. No model inference, research session, commit, push, credential change, or deployment was started for this audit.
