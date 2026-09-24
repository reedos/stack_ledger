# Muse research feedback for Fable · 2026-09-22

> **Applied 09/23/2026** to `MODEL_BRIEF.md` (brief version 2026-09-23) and `OPERATING_GUIDE.md`, with the review's corrected CapEx text; calibration before and after is recorded under "Instructions patch · September 23, 2026" in the operating guide.
>
> **Reviewed 09/22/2026: read [REVIEW-2026-09-22.md](REVIEW-2026-09-22.md) before applying.** Most of this package is sound, but its CapEx rule treats a later secondary report as a conflict with an earlier primary release. Applied, it would make the model discard current guidance. Corrected text is in the review.

**Audience:** Fable (backend / research-runner maintainer)  
**From:** curated + exhaustive Stack Ledger gap-fill (Blobby / Grok Bot for Reed Osaki)  
**Companion research:** `research/CORE_FEEDBACK-2026-09-22.md`, `research/EXHAUSTIVE_RESEARCH-2026-09-22.md`

## Intent

Sharpen how the local model (Muse Glimmer via `scripts/research.py`) extracts and screens evidence so overnight runs stop missing ISO/RTO large-load books, CapEx primary IR, and policy spine — **without loosening evidence rules or chasing yield**.

These files are **patch proposals**. Do not treat them as already-applied reviewed instruction. Merge into:

| File | Role |
|------|------|
| `research/MODEL_BRIEF.md` | Injected into Ollama extract + screen prompts |
| `research/OPERATING_GUIDE.md` | Maintainer + model operating doctrine (also partially supplied to the runner) |

## What this week proved

- Almost every publishable fill lived in **operator PDFs**, **official IR transcript / press pages**, or **Federal Register** — not AI-news HTML.
- Secondary CapEx (e.g. Motley Fool ~$220B Amazon) disagreed with written IR (~$200B).
- Queue tiers (request / studied / approved-to-energize / operating) and generation-queue vs large-load-queue were the main scope traps.
- Muse doctrine (pledged ≠ built, contiguous evidence, empty is valid) is already strong; gaps are **collection + catalog coverage + a few missing teaching rows**.

## Do not change

- Contiguous verbatim evidence limits
- Same-model screening = fallible (do not claim independent fact-check)
- No inventing metric IDs / dates / values
- No PDF bypass that publishes without reviewed extraction
- Do not raise `max_candidates_per_document` to chase yield (see OPERATING_GUIDE precision note)

## Suggested merge order

1. Apply `MODEL_BRIEF_PATCH.md` distinctions + worked examples (low risk, prompt-only).
2. Apply `OPERATING_GUIDE_PATCH.md` teaching table + CapEx / ISO primary-source rows.
3. Separately (backend, not prompt): PDF import path or human-approved `--question` packs for ERCOT / PJM / SPP / MISO PDFs; register IR transcript + FR hosts for monitoring — see `BACKEND_COLLECTION_NOTES.md`.

## Files in this folder

- `MODEL_BRIEF_PATCH.md` — exact insert text for `MODEL_BRIEF.md`
- `OPERATING_GUIDE_PATCH.md` — exact insert text for `OPERATING_GUIDE.md`
- `BACKEND_COLLECTION_NOTES.md` — runner/collection work that prompts alone cannot fix
