# Gap fill package · 2026-09-22

Curated maintainer additions (research + ledger), not an overnight Muse session.

## Landed in this PR

| Gap | What landed |
|-----|-------------|
| LBNL 2025 U.S. DC electricity | Source `lbnl-dc-2025-update`; **new metric** `us-dc-electricity-lbnl-2025` (keeps 2024 Report vintage on `us-dc-electricity` uncrowded). Obs: 2024≈192 TWh, 2028 Ref≈464, 2030 Ref≈649; Compounded Uncertainty 521–843 noted on the 2030 observation |
| ERCOT large-load queue | Metrics `ercot-large-load-queue-gw`, `ercot-large-load-queue-datacenter-share-pct`; Dec 2025 ≈239 GW; 2026-03-26 ≈410 GW; DC share 87.6% |
| ERCOT approved-to-energize | Metric `ercot-large-load-approved-to-energize-mw`; 7,502 MW since Jan 2022 (as of Dec 17 2025); **not** all observed operational |
| PJM DC growth planning | Metric `pjm-datacenter-growth-2025-2030-gw`; up to ~30 GW 2025–2030 (LAS Nov 2025); not energized MW |
| BIS export-control spine | Events `policy-2024-28270`, `policy-2025-00636`, `policy-2026-00789` |
| Applications measured outcome | Metric + observation: METR early-2025 RCT (+19% task time with AI allowed) |

## Exhaustive tranche (PUBLISH NOW) · applied 2026-09-22

Script: `scripts/curated_exhaustive_20260922.py`

| Area | What landed |
|------|-------------|
| PJM LTF summer peak | Metric `pjm-rto-summer-peak-mw` 2036=222106 / 2046=253077 MW; event `pjm-2026-ltf-large-load-firm-nonfirm` |
| SPP ITP | `spp-peak-load-itp-gw` 56→109; `spp-itp-coincident-peak-gw` 61.7/66.5/69.8/76.4 |
| ERCOT TSP vs studied | `ercot-tsp-peak-forecast-2031-gw`=218; `ercot-studied-peak-2031-gw`=159 |
| MISO LTLF | `miso-coincident-peak-ltlf-gw` 122 (2024) / 152–186 (2044); `miso-datacenter-energy-twh` 42–80 (2030) / 149–241 (2044) |
| CapEx primary IR | Alphabet 195–205; Amazon **~200** (replaced AP 220); Microsoft ~175 (lease note). Status `forecast` per capital-explorer contract; notes mark company IR commitments |
| BIS Entity List | Events `policy-2025-17893`, `19001`, `19508`, `19846`, `19858`, `policy-2026-17230`, `17231` |
| White House EO | Event `wh-eo-14318-dc-permitting-2025-07-23` (>100 MW AI load definition) |
| Apps | Event `apps-jagged-frontier-orgsci-2026`; metric `apps-customer-support-rph-delta-pct`=+15 |
| Chips | `capital-guidance-tsmc` 52–56; packaging share ~13%; `sk-hynix-fab-investment-krw-trillion`~54 |
| Water | `microsoft-datacenter-wue` 0.27; four Google campus Mgal metrics; `google-wue-category2` 1.15 (2023/2024) |

## Not landed (owner / follow-up)

- EIA API key → `import_eia.py --apply`, `import_grid_demand.py --apply`
- Amazon **$220B** (not in written IR this pass)
- MISO 163 GW news / Epoch 13.2 GW delivery% / Samsung·Micron HBM volumes / CoWoS wafer starts
- Meta / Oracle CapEx primary
- Non-overlapping delivered IT MW rollup

See `research/CORE_FEEDBACK-2026-09-22.md` and `research/EXHAUSTIVE_RESEARCH-2026-09-22.md`.
