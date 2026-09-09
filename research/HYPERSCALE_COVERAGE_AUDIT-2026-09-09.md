# Hyperscale and map coverage audit · September 9, 2026

Prometheus was absent from the accepted catalog. This was a research coverage gap, not merely a missing coordinate. This maintainer review adds 45 project/locality records and reconciles all 33 localities in Meta's current public global directory. It does **not** establish an exhaustive worldwide hyperscale census.

## Accepted changes

- Meta Prometheus / New Albany: the February 9 engineering disclosure describes a planned **1 GW** cluster. The current New Albany information sheet describes future capacity of over 1 GW. Retain the dated 1 GW design quantity; do not infer completion from older operational buildings in the same locality.
- Meta Lebanon and El Paso: each has a **1 GW company-commitment** record. Lebanon's February 11 release reports groundbreaking; El Paso's July 28 release reports construction and an initial 2028 delivery target.
- Galaxy Helios: **133 MW delivered critical IT load**, reported July 6, with the campus partly operating. Approved power and later phases are separate from delivered IT load.
- Crusoe's Microsoft Abilene development: separate from the original Stargate campus; planned critical IT load is **672 MW**, explicitly derived from two 336 MW buildings. The 900 MW generation rating and 2.1 GW combined-site figure are not additive IT quantities.
- Nscale Monarch and Narvik, Fairwater Atlanta, Stargate UAE, Google Visakhapatnam, NEXTDC S7 and eight AWS county-level entries are added with source-linked stages, scope limits and follow-up questions. Narvik's April 2026 Microsoft agreement is retained rather than assuming the older OpenAI offtake ambition remains its current customer allocation.
- Frontier is added as an alias to the existing Shackelford record, not as another project.

Primary evidence: [Meta global directory](https://datacenters.atmeta.com/all-locations/), [Prometheus engineering](https://engineering.fb.com/2026/02/09/data-center-engineering/building-prometheus-how-backend-aggregation-enables-gigawatt-scale-ai-clusters/), [Lebanon groundbreaking](https://about.fb.com/news/2026/02/metas-new-data-center-lebanon-indiana-marks-milestone-ai-investment/), [El Paso venture](https://about.fb.com/news/2026/07/meta-announces-new-venture-with-blackrock-to-develop-data-center-in-el-paso/), [Helios delivery](https://www.galaxy.com/newsroom/galaxy-completes-phase-i-of-its-helios-data-center-campus), [Abilene expansion](https://www.crusoe.ai/resources/newsroom/crusoe-announces-new-900-mw-ai-factory-campus-in-abilene-texas-to-support-microsoft-ai-infrastructure). Other primary URLs remain attached to each accepted project.

## Coverage assessment

| Operator / group | Result in this review | Remaining work |
| --- | --- | --- |
| Meta | All 33 directory localities resolve to accepted IDs, including previously tracked Hyperion, Temple, Tulsa and Sturgeon County. A retained review fixture checks the mapping. | Verify current stages for directory-only entries; resolve Clonee and Sturgeon coordinates. Directory completeness is not phase/capacity completeness. |
| Amazon / AWS | Eight county entries added in Pennsylvania, North Carolina, Georgia and Mississippi; existing Louisiana and New Carlisle coverage retained. | Reconcile the full regional portfolio, named campus boundaries, Rainier overlap, latest stages and local economic evidence. Statewide budgets/jobs are not per-county allocations. |
| Microsoft | Atlanta and the separate Crusoe Abilene development added; Wisconsin retained; Narvik customer update captured. | Reconcile broader global campuses and leased facilities, including unknown delivery stages. |
| Google | Visakhapatnam added to the previously reviewed location sample. | Complete the global directory and newer announcements; cloud support is not proof of AI-only allocation. |
| OpenAI / Oracle / partners | Existing named U.S. Stargate projects retained; UAE and NEXTDC S7 added; Frontier alias resolved. | Current UAE commissioning evidence; UK status; other country initiatives and partner campuses; avoid treating an MoU as a delivered project. |
| Neoclouds / developers | Helios, Monarch and Narvik added to existing CoreWeave and Nebius coverage. | Reconcile Nscale, CoreWeave, Crusoe, Vantage, STACK, QTS, Digital Realty, Equinix and other inventories, including campus/tenant overlaps. |
| Other regions / builders | Explicitly incomplete. | Saudi Arabia, China, Korea, Japan, broader India, Southeast Asia, Africa and Latin America need further operator/permit-level reconciliation. Unfamiliar developers remain in scope. |

The next review should report accepted matches, proposed additions, duplicates and unresolved entries against a named, dated operator inventory. No worldwide coverage percentage is supported. A search returning no missing sites is not proof of completeness.

## Map behavior and counting

The catalog contains **154 project/program/locality records**: 144 have reviewed coordinates and produce 182 project locality placements. Twelve separately switchable developer-office locations cover eleven organizations and do not increase project or capacity totals. Of the projects, 28 have **stage needs verification**; these are excluded from both operating and development counts. Known locality and unknown current stage are compatible.

Waymo contributes 14 currently listed service markets and 18 Up Next locations to one program record. Tesla contributes six listed limited-area markets and one explicitly dated Bay Area safety-driver locality. None of these placements allocates the entire program's vehicles, trips, investment or jobs to each city.

Markers preserve layer colors in shared rings, vary size with the number of mapped entries, and distinguish operating, buildout, planned, pilot, delayed and unverified stages. Size is a record count, not megawatts. City/county coordinates are orientation points, not facility boundaries. The new unknown-stage treatment avoids fabricating operation or construction merely to fill the map.

## Research controls and verification

Two questions were added to the **existing infrastructure discovery rotation** for operator-directory reconciliation and missing large campuses. The playbook documents alias matching, quantitative scope and complete-catalog comparison. No new scheduler, crawler, model approval mechanism, credential or publication permission was introduced. New source registrations have manual cadence. Inference was not started, and this research is not attributed to Muse Glimmer.

Validation and build passed. The full Python suite passed 244 tests; browser acceptance passed 24 routes at three viewports, and explorer checks covered filters, map interaction, static fallbacks and 320/390-pixel layouts. Offline editorial and catalog evaluation results are retained privately. Existing runtime data, run receipts, prior observations, events, targets and the five-layer configuration were compared with HEAD and remain unchanged. Runtime/footer presentation files are untouched.

The remaining coverage and stage work above is follow-up research, not an implemented claim of complete global coverage. Source timestamps remain distinct from this review date; known source dates were retained and undated information sheets remain undated.
