# Exhaustive research — Stack Ledger · 2026-09-22

Public-source pass (PDFs / IR / Federal Register / White House). No invented numbers. Reeds-PC offline (no Muse). Companion to `CORE_FEEDBACK-2026-09-22.md` and `GAP_FILL-2026-09-22/`.

## Publish now (curated apply target)

| Area | Finding | Primary source |
|------|---------|----------------|
| PJM LTF | Summer peak 222,106 MW (2036), 253,077 MW (2046); +65,733 / +96,704 MW | [2026 Load Report](https://www.pjm.com/-/media/DotCom/library/reports-notices/load-forecast/2026-load-report.pdf) |
| PJM LTF | Firm vs non-firm large-load derate language (no single DC GW in LTF) | same |
| SPP ITP | Peak 56 GW → could rise to 109 GW within ~10 years; Fig 2.1 path 61.7 / 66.5 / 69.8 / 76.4 GW | [2025 ITP](https://www.spp.org/media/2429/2025-itp-report-v10.pdf) |
| ERCOT | TSP 218 GW vs studied 159 GW (2031); confirms ~238.6 GW LLI / 7,502 MW approved | [Constraints & Needs Dec 2025](https://www.ercot.com/files/docs/2025/12/23/2025-Report-on-Existing-and-Potential-Electric-System-Constraints-and-Needs.pdf) |
| MISO LTLF | Peak 122 GW (2024) → 152–186 GW (2044); DC energy +42–80 TWh by 2030, +149–241 by 2044 | [Dec 2024 LTLF whitepaper](https://cdn.misoenergy.org/MISO%20Long-Term%20Load%20Forecast%20Whitepaper_December%202024667166.pdf) |
| Alphabet | CY2026 CapEx guidance **$195–205B** (up from $180–190B) | [Q2’26 IR transcript](https://abc.xyz/investor/events/event-details/2026/2026-Q2-Earnings-Call-2026-GgTAq7Is0z/default.aspx) |
| Amazon | CY2026 CapEx **about $200B** (written IR) | [Q4 results release](https://ir.aboutamazon.com/news-release/news-release-details/2026/Amazon-com-Announces-Fourth-Quarter-Results/) |
| Microsoft | CY2026 CapEx **~$175B** after finance→operating lease reclass; Q1 FY27 CapEx >$50B | [FY26 Q4 earnings](https://www.microsoft.com/en-us/investor/events/fy-2026/earnings-fy-2026-q4) |
| BIS Entity List | FR 2025-17893, 19001, 19508, 19846, 19858; 2026-17230, 17231 | Federal Register |
| White House | EO accelerating federal permitting of DC infrastructure (2025-07-23); >100 MW AI load definition | [EO page](https://www.whitehouse.gov/presidential-actions/2025/07/accelerating-federal-permitting-of-data-center-infrastructure/) |
| Apps | Dell’Acqua jagged frontier RCT: +12.2% tasks, +25.1% faster; −19% outside frontier | DOI 10.1287/orsc.2025.21838 |
| Apps | Brynjolfsson/Li/Raymond QJE: +15% issues resolved per hour | [PDF](https://danielle.li/assets/docs/GenerativeAIatWork.pdf) |
| TSMC | CapEx $52–56B (2026); advanced packaging CapEx 10–20%; packaging revenue ~10%→low-teens | [4Q25 transcript](https://investor.tsmc.com/english/encrypt/files/encrypt_file/reports/2026-01/51d09df96cd89ac19d65af39032b038dc2896a24/TSMC%204Q25%20Transcript.pdf) |
| SK hynix | ~54T KRW fab CapEx commitment (Y2+M17); not shipped HBM volume | [fab investment](https://news.skhynix.com/en/fab-facility-investment-2026/) |
| Water | Microsoft fleet WUE 0.27 L/kWh (FY25); Google campus consumption Mgal (Council Bluffs 1346, The Dalles 469, Mayes Co. 1081.4, New Albany 835.7); Google WUE Cat2 1.15 | MSFT / Alphabet assurance |

## Conditional (hold)

- MISO “163 GW by 2035” / 8–14 GW near-term — news only until Apr/May 2026 LTLF PDF
- Amazon **$220B** — not in written IR/SEC this pass
- Epoch 13.2 GW IT rollup — estimate; do not invent delivery %
- SK hynix “HBM revenue doubled” without absolute $
- Meta / Oracle CapEx — primary not secured
- DOE Speed to Power / FERC large-load — need single dated primary

## Blocked

- EIA live series (API key)
- Samsung / Micron primary HBM shipped volumes
- TSMC CoWoS wafer-start capacity (not in primary transcript)
- CAISO / NYISO / ISO-NE large-load PDFs (none clear this pass)
- Muse overnight (Reeds-PC offline)

## Corrections to earlier feedback

- Alphabet $195–205B **confirmed** on primary IR transcript (upgrades AP gap).
- Amazon primary supports **~$200B** only; $220B remains a gap.
- SPP 56→109 GW **verbatim** in 2025 ITP (grid-operators note was accurate).
- No contradiction to ERCOT ~239 GW / 7,502 MW / ~410 GW board figures.

## Application status · 2026-09-22 (PT)

**PUBLISH NOW list above: applied** to catalog + ledger via `scripts/curated_exhaustive_20260922.py`.

| Bucket | Count |
|--------|------:|
| Sources added | 19 |
| Metrics added | 17 |
| CapEx metrics replaced (primary IR) | 3 |
| Observations written (incl. CapEx upserts) | 28 |
| Events added | 10 |
| Failures skipped | 0 |

Notes:
- Hyperscaler CapEx guidance kept `status=forecast` / `allowed_statuses=['forecast']` to satisfy `validate_explorers` capital contract; observation notes state company IR commitment. TSMC CapEx and SK hynix fab investment use `company-commitment`.
- Amazon observation upserted **200** (removed prior AP **220**).
- Dell'Acqua landed as event grade **B** (independent-research provenance).
- Conditional / blocked lists above remain unapplied by design.
- `research/grid-operators.json` notes updated for PJM, MISO, SPP, ERCOT.

