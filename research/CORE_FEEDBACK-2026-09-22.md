# Core feedback — Stack Ledger · 2026-09-22

Curated research pass by Blobby (Grok Bot) for Reed. Complements the gap-fill package in this folder. Does **not** change homepage headlines or replace existing figures without your review.

## What is already unusually strong

- Evidence discipline (A–D grades, reports lane, pledged ≠ built, separate observation/estimate/forecast/commitment books).
- Hyperscaler cash PP&E with fiscal/lease caveats; Apollo older consensus kept separate; JPM Aug 2026 intentionally not merged.
- Claims page hygiene on water, bills, jobs, and taxes — contested discourse handled carefully.
- Epoch importers, ECI snapshot, CoWoS estimate framing, Fairwater build→operate job split.
- Explicit “Applications waits for a measured-outcome metric” rather than inventing one.

## Priority research gaps (ranked)

1. **ISO/RTO large-load queues** (requested vs studied vs energized) — ERCOT LLI + approved-to-energize and PJM ~30 GW LAS planning figure now in this package; MISO/SPP and full PJM LTF peak path still open (`research/grid-operators.json`).
2. **LBNL 2025 (landed on metric `us-dc-electricity-lbnl-2025`, peer to `us-dc-electricity`) U.S. DC electricity update** as a peer series beside IEA global — proposed observations in this package (do not splice into IEA metrics).
3. **Live EIA series** (generation, capacity additions, retail $/kWh by project states, EIA-930 demand) — importers exist; blocked on EIA API key in `.local/api-keys.json`.
4. **BIS / advanced-computing export-control event spine** — Dec 2024 FDP IFR, Jan 2025 AI Diffusion IFR, and Jan 2026 license-review final rule proposed; Entity List / May 2025 statements still open as grade-A events only (no invented chip tonnage).
5. **Non-overlapping delivered IT MW** across the project tracker — still no reviewed phase rollup / delivery %.
6. **Applications measured outcomes** — METR early-2025 RCT proposed (method-first; negative result is still evidence). Late-2025 METR follow-up is weak/uninterpretable; keep out of charts.
7. **2027–2030 company-by-company capex book** from primary IR — Amazon/Alphabet CY2026 guidance still AP-attributed; primary transcripts remain a follow-up.
8. **Local water/permits/WUE** at campus scale beyond national context.
9. **HBM / packaging shipped volumes** vs readiness milestones.
10. **Publication-date hygiene** (“date unlisted” tax on trust) and SEC live import / `amazon` parent for AWS.

## Product / editorial feedback (non-data)

- Homepage Energy card is IEA global; once LBNL 2025 is accepted, consider a U.S. companion card or energy-page lead — never replace IEA with LBNL on the same series.
- `us-grid-queue` is generation/storage interconnection, not large-load customer queues — keep the new ERCOT LLI metric visually distinct so readers do not conflate them.
- Automation yield is still thin (monitoring accepts almost nothing) — curated research and importers are carrying the public record; treat Muse as discovery, not the spine.
- Claims page is richer than the homepage community section; promote one verified local-cost series when EIA retail-by-state lands.
- Do not chase: AI jobs net total, five-layer completion %, STEO→AEO growth stitch, averaging Epoch IT bases, ECI-as-intelligence-%, almond water ratios as headlines, SEMI press as A-grade capacity.

## How to apply this package

```bash
python scripts/curated_gap_fill_20260922.py          # dry-run
python scripts/curated_gap_fill_20260922.py --apply  # register sources, metrics, observations, events; validate; rebuild
python scripts/validate.py
python -m unittest discover -s tests
```

EIA and PJM/MISO/SPP PDF forecasts are **not** auto-applied. After setting the EIA key, run `python scripts/import_eia.py --apply` and `python scripts/import_grid_demand.py --apply`.

## Still blocked / owner actions

| Item | Blocker |
|------|---------|
| EIA generation / additions / retail-by-state | Register key → `.local/api-keys.json` |
| EIA-930 BA demand | Same key; importer ready |
| PJM 2026 LTF summer peak path (2036/2046) | Curated from official load report (LAS ~30 GW already landed) |
| PJM Data Miner / further large-load MW | Account + curated PDF tables |
| MISO / SPP ITP large-load figures | Curated PDF import |
| Primary Amazon / Alphabet CY2026 transcripts | Replace AP attribution |
| Overnight Muse research session | Reeds-PC offline during this pass |

## Sources used for proposed fills

- LBNL / DOE: *United States Data Center Energy Usage Report: 2025 Update* (Smith et al., June 2026; LBNL-2001758; DOI 10.71468/P1RP4F; published 2026-06-18). https://www.energy.gov/documents/united-states-data-center-energy-usage-report-2025-update and https://escholarship.org/uc/item/33m6w3x0
- ERCOT Board Item 9, Interconnection and Grid Analysis Update, Apr 20–21 2026 (as-of Mar 26 2026): ~410 GW LLI; ~87% data centers. https://www.ercot.com/files/docs/2026/04/13/9-Interconnection-and-Grid-Analysis-Update.pdf
- ERCOT *Report on Existing and Potential Electric System Constraints and Needs*, Dec 2025: ~239 GW large-load seeking interconnection. https://www.ercot.com/files/docs/2025/12/23/2025-Report-on-Existing-and-Potential-Electric-System-Constraints-and-Needs.pdf
- BIS Framework for Artificial Intelligence Diffusion, 90 FR 4544, Doc. 2025-00636, published 2025-01-15. https://www.federalregister.gov/documents/2025/01/15/2025-00636/framework-for-artificial-intelligence-diffusion
- PJM LAS Large Load Adjustment Requests Summary (2025-11-24): up to ~30 GW DC growth 2025–2030. https://www.pjm.com/-/media/DotCom/committees-groups/subcommittees/las/2025/20251124/20251124-item-03---large-load-adjustment-requests-summary.pdf
- BIS Doc. 2024-28270 (Dec 5, 2024) and Doc. 2026-00789 (Jan 15, 2026) — Federal Register primary.
- METR: *Measuring the Impact of Early-2025 AI on Experienced Open-Source Developer Productivity* (RCT; 19% longer with AI). https://metr.org/blog/2025-07-10-early-2025-ai-experienced-os-dev-study/

## Exhaustive PUBLISH NOW tranche · applied 2026-09-22

Applied via `scripts/curated_exhaustive_20260922.py` (after the earlier gap-fill). Validates + crowding tests pass.

**Counts (this tranche):** 19 sources · 17 new metrics · 3 CapEx guidance metrics updated (primary IR; Amazon 220→200) · 28 observations (incl. 3 CapEx upserts) · 10 events.

**Corrections vs earlier feedback in this file:**
- Alphabet $195–205B now on primary IR (`capital-alphabet-q2-2026-ir`), not AP.
- Amazon primary supports **~$200B** only; AP $220B removed from `capital-guidance-aws`.
- **Correction, 09/22/2026 (later the same day):** the Amazon change was wrong and has been reverted. The $200B is Amazon’s February 5, 2026 plan; the $220B is the guidance Andy Jassy gave on the July 30, 2026 call, which AP reported as "up from the $200 billion investment plan that was announced in February". They are two vintages, not two sources in conflict. `capital-guidance-aws` is back to $220B, attributed to AP, with the February plan in its note. See `FABLE_MUSE_FEEDBACK-2026-09-22/REVIEW-2026-09-22.md`.
- PJM 2036/2046 summer peak, MISO LTLF peaks + DC TWh, SPP ITP narrative + Fig 2.1 coincident path curated.
- BIS Entity List spine extended (7 FR docs); EO data-center permitting event landed.
- CapEx guidance status remains `forecast` (capital-explorer contract); TSMC/SK hynix new commitments use `company-commitment`.

**Still blocked:** EIA key; Muse offline; HBM shipped volumes; CoWoS wafer starts; Meta/Oracle CapEx primary; MISO 163 GW news.
