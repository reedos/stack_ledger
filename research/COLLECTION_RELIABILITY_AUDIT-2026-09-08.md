# Collection reliability and evidence quality

Implementation and evaluation: 8 September 2026, Pacific time. This is a maintainer report, not an accepted-data update or publication approval.

## Findings from the completed run

The retained seven-hour session contains 262 discovery searches, 255 search errors, 77 empty-result attempts, 36 inaccessible attempts and one failed screen. The offline evaluator matched 76 of the empty attempts to unambiguous saved documents. Ten matched documents were longer than the old 18,000-character opening-only context. The unmatched attempt remains unknown; no body version was invented.

Eight ECMWF quarantines passed a repaired numeric prose check: the original regex failed to recognize a year followed by a sentence-ending period. This clears a specific numeric defect, not every other requirement on those notes. Other quarantines still include missing evidence, unsupported quantities and unsupported scope. No quarantine was automatically accepted.

A purposive review of eight saved documents found five follow-up candidates, two documents with insufficient outcome evidence and one reasonable empty result. These are not a representative sample or a recall estimate. Existing Milam coverage, inconsistent release dates, renewable procurement versus hourly supply, material versus whole-campus carbon reductions, and research versus operational weather forecasting remain explicit review questions. The saved-case labels are in `collection-audit-cases.json`.

## Implemented changes

- Reuse private collection health across batches: bounded robots-policy caching, page/provider cooldowns, Retry-After, and no-work waits. A failed provider does not receive another request merely because the next topic changed. Robots failures still fail closed.
- Seed registered primary indexes regularly, independent of GDELT status, within existing discovery budgets. This reduces dependency on one news provider without pretending to provide a second general search engine.
- Separate private discovery eligibility from public monitoring's approved-metric rule in model instructions. The model may propose an unregistered project or measure; only maintained code and human review can register it.
- Clarify that `supported=true` means textual support, not permission to publish. A correctly attributed company commitment need not be an operating asset. The model must still reject wrong scope, unsupported quantities, inferred outcomes and incorrect measurement basis.
- Require an explanation for empty results; retain rejected candidate text and screening reasons privately. New proposals carry the actual contribution layer, subject to operator layer filters. Old review-inbox records remain readable.
- Select opening, tail and relevant contiguous source sections within existing context budgets. Extraction and verification share those sections, with exact quote containment and original offsets. Exposed characters are not a comprehension measure. Partial coverage stays explicit; remaining sections still need targeted review.
- Add inert RSS/Atom and textual CSV/TSV/JSON adapters, retaining existing URL, DNS, redirect, robots, time and byte restrictions. Reject XML entity declarations. Unsupported formats and insufficient static text receive private collection-gap records.
- Add question-level private progress reports that reuse the existing queue and human resolution log. Linked proposals, empty screens and inaccessible evidence do not automatically resolve a question. Completion receipts distinguish actual findings from monitoring-only pushes and repeat fetches.

## Evaluation

`evaluate_collection.py --session c400decb4b844a618e853548c795835b` inventories the actual saved run and rechecks quarantine numbers entirely offline. Its detailed JSON and Markdown stay under `.local/evaluations/`.

An explicit, bounded Ollama replay of two saved documents exposed two interpretation errors: the model treated "never approve" as "always reject," and treated the absence of a registered metric as a reason to discard private discovery. After clarifying those distinctions, the final replay used three model calls: Project Jupiter produced a textually supported commitment candidate, while the economist biography returned an explained empty result. Results stayed in the private evaluation directory; the replay did not enqueue or publish anything. Earlier calibration attempts were rejected or empty, so this is evidence of a corrected test case rather than a claim of perfect reliability.

Validation commands:

```text
python -m unittest discover -s tests
python scripts/validate.py
python scripts/build.py
python scripts/evaluate_editorial.py
python scripts/evaluate_collection.py --session c400decb4b844a618e853548c795835b
python scripts/evaluate_discovery_model.py --run
node tests/research_control.cjs
node tests/browser.cjs
```

The Python suite covers 200 tests. The local controller and public browser checks pass, including 24 public routes at three viewport sizes. Repository validation and the 107-page build pass. The accepted site data, generated pages, runtime/hardware block, source registry and publication permissions are unchanged. No new overnight production run, commit or push was performed.

## Remaining work and limits

PDF extraction, Excel workbook parsing, OCR, JavaScript-only pages and query-bearing statistical APIs still need individually reviewed adapters. The repository currently requires the Python standard library; no unreviewed parser dependency or browser execution was added. The large weather-research paper in the sample also exceeds the existing response-size cap. Unsupported files are now explicit follow-up work rather than unexplained repeated failures.

The eight registered primary indexes are a supplementary collection route, not comprehensive primary-source coverage. Broader issuer feeds, original statistical series and employer sources need evidence-led expansion. Network access restrictions and provider outages cannot be eliminated by local code.

Two local-model cases cannot establish recall across 77 empty screens or guarantee a productive six-hour run. Expand the maintained evaluation set with reviewed positive, empty, conflicting and misleading examples. Do not optimize merely for more proposals, longer GPU activity or fewer legitimate rejections. Review the next production receipt for actual question progress, useful proposals, access health and unexamined evidence.
