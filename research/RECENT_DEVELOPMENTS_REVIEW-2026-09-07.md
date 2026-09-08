# Proposed recent developments — September 7, 2026

Status: approved by owner reedos through the explicit request to commit and push following presentation of these three cards. Approval recorded on 2026-09-08 at 06:02:54 UTC; applied through the existing curated homepage configuration. Original releases were inspected on September 7 Pacific / September 8 UTC. All three sources already exist in the accepted ledger. No local-model inference was run.

## Proposed card 1 — Chips

**Indiana HBM packaging project breaks ground**

SK hynix reports an August 27 groundbreaking for its Indiana advanced-packaging facility. It targets mass production in the second half of 2029.

Why it matters: The project would add U.S. packaging and testing capacity for high-bandwidth memory used in AI systems, using wafers made in Korea.

Scope: Groundbreaking is a reported milestone; production remains a company target. This is packaging and testing, not U.S. wafer fabrication. The company's approximately 1,000 operating positions are projected, not verified hires.

Event: 2026-08-27. Source publication: 2026-08-28.

Source ID: `hynix-indiana-2026`. [Original release](https://news.skhynix.com/en/groundbreaking-ceremony-in-indiana/).

## Proposed card 2 — Infrastructure

**Meta reports its first skilled-trades training graduates**

Meta's August 18 update reports the first graduating cohort of America's Workforce Academy, a four-week program offering training and jobs with its partners.

Why it matters: Fiber-technician and construction training provide a concrete pathway into the workforce building data centers.

Scope: This is a company-reported graduation milestone and job guarantee, not a verified placement count or a measure of net national job creation. The release says graduation occurred the preceding week; it does not establish an exact graduation date.

Event: 2026-08-18 **report**, not the graduation date. Source publication: 2026-08-18.

Source ID: `meta-awa-graduates`. [Original release](https://about.fb.com/news/2026/08/americas-workforce-academy-meta-skilled-trade-training-program/).

## Proposed card 3 — Energy

**Cape Station reports progress toward first power**

In its August 12 update, Fervo reports mechanical completion of Cape Station GeoBlocks 1 and 2 and continuing commissioning. It targets first power from GeoBlock 1 in the fourth quarter of 2026, followed by initial power from GeoBlocks 2 and 3 in early 2027.

Why it matters: Commissioning provides a nearer-term delivery checkpoint for new firm geothermal power.

Scope: These are company-reported construction and commissioning milestones, not confirmation of commercial generation. The update covers the quarter ended June 30 and subsequent outlook; August 12 is the disclosure date, not an inferred completion date.

Event: 2026-08-12 **operational update**. Source publication: 2026-08-12.

Source ID: `fervo-q2-2026`. [Original release](https://fervoenergy.gcs-web.com/news-releases/news-release-details/fervo-energy-reports-second-quarter-2026-results).

## Application after approval

Use the existing `research/homepage.json` curated `recent_changes` mechanism and its validator/renderer. Preserve featured slots, runtime presentation and permissions. Each proposed item is `kind: development`, unpinned, with null before/after observation IDs; no numerical change comparison is proposed. Record the actual owner approval time and rationale only after approval. Keep the scope/date caveats in the displayed cards. Validate, test and rebuild after application; update the browser assertion that currently expects the empty module.

The existing note queue is not automatically promoted. In particular, the June 17 Lumentum note falls outside the 45-day recent-event window. Undated Mortenson and Nova Act candidates do not establish a recent event merely because they were fetched September 7. These remain separate research/review candidates.

Application populates the public homepage on rebuild. It does not change source registrations, accepted observations, research-run timestamps or publication permissions. The existing pending GoatCounter implementation is separate.
