# Visual recommendations: operation and limits

Implemented September 9, 2026 from [the algorithm draft](VISUAL_RECOMMENDATION_DRAFT.md). This is recommendation-only. It does not permit Muse to swap, remove, add or redesign public graphics, change pins, or approve its own proposals.

## Where to review

Reopen `Research-Control.cmd` after installing these changes; use **Review findings → Visual recommendations**. Reloading an old browser tab cannot update its running Python server. Opening the panel starts no research. The existing session lock, local reviewer mapping, Host/Origin checks and session-token requirement remain in effect.

The section provides status filters, paginated recommendations, original source links, period/status/unit/scope details, fixed calculation traces, uncertainty, model score dimensions, prior decisions and a current-versus-proposed preview link. All narrative is rendered as text. Previews contain trusted server-rendered HTML, no model HTML, scripts or analytics. Source links can open externally when the human chooses them.

- **Accept exact preview** records approval of the immutable proposal. It does not apply, build, commit, push or deploy.
- **Accept direction — implement then preview** endorses a specification that needs a maintained renderer or code/configuration change. It is not final application approval.
- **Decline** retains the reason and suppresses the same material suggestion, including reworded copies.
- **Defer** requires a future date. **Request changes** records what a new revision must address.

There is no visual apply/publish endpoint. A maintainer uses the exact approved package as a separately reviewed implementation handoff, verifies it is still current, makes the change, and runs the existing validation/build/publication workflow. This deliberately separates selection from application while the owner calibrates recommendations. Catalog publication retains its existing separate path; a visual decision does not approve new sources or metrics.

## What runs automatically

`research/visual-policy.json` inventories 19 maintained display areas: five featured layers, construction, hiring demand, workforce plans, Fairwater, capital, map, capability, electricity, claims, companies, chip supply, useful work/medicine, recent developments, and layer diagrams. Each has a reader question, evidence restrictions, accepted dependencies and maintained preview capability. Runtime/hardware is excluded.

After each controller batch, a no-inference dependency checkpoint records changes privately. At a healthy completed session or explicitly capped cycle completion, the controller performs a bounded model assessment before its existing completion receipt. Failed, blocked, interrupted and manually stopped sessions receive an offline assessment only. No new scheduler is installed; the approved 2–7 AM window is unchanged. Final review can add up to the configured assessment budget after collection ends, just as existing final publication checks take time.

The assessment permits at most five local model calls, a 180-second evaluation budget and a maximum 30-second timeout per call. It reuses the existing Ollama JSON adapter with only local endpoint/model settings, no shell, Git or approval tools. Unchanged assessed inputs reuse cached decisions until review is due; failed and unassessed areas rotate fairly through later runs. Oversized packets are reported, not silently truncated. Explicit bounded catalog samples report their limited coverage; evaluating the full dependency hash does not imply a full qualitative audit of every row.

All accepted metrics in the relevant layer can enter a rotating shortlist; incumbent and current full-cohort metrics are retained. Private research proposals are not eligible numeric chart inputs. Unsupported period interpretations remain visible in a separate review-input section, not promoted into valid growth calculations. Historical estimates, forecasts and commitments retain their statuses and source editions.

KEEP and insufficient-evidence outcomes appear in the digest without generating busywork in the pending list. Failed calls and budget-limited areas are explicitly unassessed. Monitoring dates, observation periods, source dates, review dates and unknown display lag remain separate. Accepted-data preview does not certify the currently deployed page is synchronized.

## Current capabilities and intentional limits

The five featured homepage slots support exact previews for eligible same-purpose replacement, pinned refresh and existing snapshot/history configurations. They reuse `render.layer_cards`, `render_editorial`, existing evidence gates and configuration validation. Other display changes currently produce evidence-backed specifications, with current previews where maintained renderers exist. Electricity, company, chip-supply, useful-work and diagram recommendations may require a maintainer-generated final preview; the panel labels this explicitly.

The four maintained calculation families initially cover same-month/same-vintage construction changes, the pinned Indeed posting-share ratio, complete-cohort fiscal capex sums, and map record counts. Fairwater explicitly forbids combining cumulative contributors with on-site employees. No generic model-authored formula execution, automatic inflection detection, new baselines or invented histories were added.

The 10-point replacement margin is reused for comparable homepage profiles. Cross-profile changes become implementation specifications rather than automatic configuration proposals. Rejected identical suggestions do not reappear as pending work. There is no automated visual application, so this path does not yet create applied-change cooldown events; the existing homepage recommender's application cooldown remains in its own workflow. Reconsidering a supported critical flaw still requires human review.

Initial per-batch work is dependency tracking, not a fresh model critique after every source or topic. The session conclusion is the model evaluation point; individual-topic model callbacks remain a follow-up. Review rationales are supplied as bounded untrusted context, not training data or self-modifying policy. A direction endorsement does not authorize changing scoring rules.

## Commands and private outputs

```powershell
# Offline inventory and deterministic evidence/calculation checks:
python scripts/visual_review.py

# Explicit on-demand local model review; refuses while research is active:
python scripts/visual_review.py --model

# Offline disposable-copy approval/preview/build evaluation, no live model:
python scripts/evaluate_visuals.py
python -m unittest discover -s tests -p test_visual_review.py
$env:PLAYWRIGHT_MODULE='C:/Users/reedo/projects/ee-labs/node_modules/playwright'
node tests/visual_review.cjs
```

The panel's **Check accepted data (no model)** button runs the first command's assessment through the existing protected POST boundary; GET never starts inference or saves decisions.

Private outputs reuse the existing queue and editorial log:

- `.local/review-candidates/visual-*.json`: immutable proposals, separate from discovery and catalog kinds.
- `.local/review-candidates/editorial-events.jsonl`: human decisions with proposal hashes.
- `.local/editorial/visual-<snapshot hash>/`: snapshot, captured model packets/responses, assessment, digest and trusted previews.
- `.local/editorial/visual-latest.json` and `visual-state.json`: panel summary and cached evaluation/rotation state.
- `.local/sessions/<id>/visual-dependencies.json` and `visual-recommendations.json`: session-specific results or explicit failure receipt.

Nothing in `.local` is copied to the public site. The runtime/footer, public metrics, approved graphics and publication allowlists are unchanged. Acceptance rechecks the full frozen evidence/configuration, current implementation, saved preview hash and regenerated preview; stale proposals require reassessment. Ordinary monitoring run receipts do not invalidate approval, because they are excluded from the evidence identity.

## Rollout evidence

The first repository assessment was offline: all 19 areas were inventoried and no Muse assessment was claimed. Synthetic tests cover approval without application, direction versus exact-preview decisions, tampering, stale evidence, repeated suggestions, no-change caching, unsupported quantities/references/scores, budgets, rotation, stopped sessions, missing capex cohort members, posting-share versus volume and construction-vintage breaks. The disposable evaluation simulates a separate maintainer applying the exact approved configuration and runs the actual validator/build there. Browser checks use an isolated server and synthetic review decision on desktop and mobile.

These checks establish software behavior, not Muse's live recommendation accuracy. The next healthy research session will populate actual suggestions as evidence permits; it may legitimately KEEP, abstain, or leave some areas unassessed. Owner decisions and reasons should guide the next reviewed refinement.
