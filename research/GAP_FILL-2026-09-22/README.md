# Gap fill package · 2026-09-22

Curated maintainer additions (research + ledger), not an overnight Muse session.

## Landed in this PR

| Gap | What landed |
|-----|-------------|
| LBNL 2025 U.S. DC electricity | Source `lbnl-dc-2025-update`; **new metric** `us-dc-electricity-lbnl-2025` (keeps 2024 Report vintage on `us-dc-electricity` uncrowded). Obs: 2024≈192 TWh, 2028 Ref≈464, 2030 Ref≈649; Compounded Uncertainty 521–843 noted on the 2030 observation |
| ERCOT large-load queue | Metrics `ercot-large-load-queue-gw`, `ercot-large-load-queue-datacenter-share-pct`; Dec 2025 ≈239 GW; 2026-03-26 ≈410 GW; DC share 87.6% (plain metrics — not expansion `measurement_type`) |
| BIS export-control spine | Event `policy-2025-00636` — Framework for AI Diffusion (90 FR 4544) |
| Applications measured outcome | Metric + observation: METR early-2025 RCT (+19% task time with AI allowed) |

## Not landed (owner / follow-up)

- EIA API key → `import_eia.py --apply`, `import_grid_demand.py --apply`
- PJM / MISO / SPP large-load or peak-load PDF curation
- Primary Amazon / Alphabet CY2026 transcripts (replace AP)
- Additional BIS Entity List / May 2025 policy events
- Non-overlapping delivered IT MW rollup

See `research/CORE_FEEDBACK-2026-09-22.md` for full editorial feedback.
