# Backend / collection notes for Fable · 2026-09-22

Prompt patches alone will not land this week’s fills. These are runner and registry changes.

## Problem

`OPERATING_GUIDE` / README: public HTML only; PDFs are logged as unavailable; **no PDF parser**. Monitoring yield can look healthy (fetches, notes) while numeric observations stay at zero because the numbers live in PDFs.

## High-value PDF / primary hosts (register or question-pack)

| Host / doc class | Why | Example |
|------------------|-----|---------|
| `ercot.com` board + Constraints & Needs PDFs | LLI queue, approved-to-energize, TSP vs studied peaks | Apr 2026 Interconnection update; Dec 2025 Constraints & Needs |
| `pjm.com` Load Forecast Report + LAS PDFs | RTO summer peak path; ~30 GW DC growth planning | 2026 load report; 2025-11-24 LAS summary |
| `spp.org` ITP PDF | 56→109 GW headline + Fig 2.1 path | 2025 ITP report |
| MISO CDN LTLF whitepapers | Peak trajectories; DC TWh growth | Dec 2024 LTLF whitepaper |
| `federalregister.gov` BIS / Entity List | Policy event spine | Docs 2024-28270, 2025-00636, 2026-00789, Entity List 2025-17893… |
| Hyperscaler IR event + news-release pages | CapEx guidance primary | Alphabet Q2’26 transcript page; Amazon Q4 results release; Microsoft FY earnings |
| Google / Microsoft sustainability | Campus water / WUE | Alphabet FY environmental indicators; MSFT datacenter efficiency |

## Recommended backend work (pick a lane)

1. **Curated PDF text import (safest):** maintainer drops extracted text or a reviewed HTML mirror into an approved source; Muse extracts as today. Matches constitution: model never gets arbitrary PDF tooling.
2. **Human-approved `--question` packs:** bounded source list + pre-fetched PDF text for one overnight question (ERCOT LLI, PJM LTF, etc.).
3. **Reviewed PDF→text path (larger):** if added, keep robots/size limits; hash full text; never let the model choose URLs; publish only through existing validators.
4. **Do not:** scrape secondary news to fill ISO metrics; loosen screening to raise overnight numeric yield.

## Catalog coverage (so Muse has somewhere to land)

Without reviewed metrics, correct extractions become notes forever. Series that needed catalog rows this week (now curated in the gap-fill PR):

- Large-load queue GW / DC share (ERCOT)
- Approved-to-energize MW (ERCOT)
- PJM DC growth planning GW; PJM RTO summer peak MW
- SPP ITP peak GW; MISO coincident peak + DC energy TWh
- Campus water consumption; fleet WUE
- Applications RCT deltas (METR-style)

Feedback loop: when private notes repeatedly cite the same operator disclosure with no fitting metric, surface a **catalog proposal** digest for Reed/Fable rather than only dropping empties.

## CapEx hygiene (validator-side optional)

Deterministic hint (optional, not a model change): if source provenance/collection rank is news and metric id starts with `capital-guidance-`, auto-quarantine for human review even if the model accepts — forces IR primary.

## Eval suggestion

Add holdout fixtures from:

- ERCOT Constraints snippet (238.6 GW queue vs 7,502 MW approved)
- Amazon IR “about $200 billion” vs a secondary “$220B” distractor document
- SPP “could rise to 109 GW” vs Fig 2.1 lower path
- News-only MISO “163 GW” → expect empty / private lead

Score reject-on-secondary and correct metric routing, not raw proposal count.

## Reference curated package

Gap-fill branch: `research/gap-fill-2026-09-22`  
Scripts: `scripts/curated_gap_fill_20260922.py`, `scripts/curated_exhaustive_20260922.py`  
Writeups: `research/EXHAUSTIVE_RESEARCH-2026-09-22.md`
