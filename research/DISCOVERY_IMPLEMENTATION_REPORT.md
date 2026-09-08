# Discovery framework implementation and offline evaluation

Implemented against the actual repository after reading its instructions, runner, source policies, review lifecycle and tests. This change adds private exploration to the existing research loop; it does not broaden public publication permissions or change the site.

## File map and reused mechanisms

- `scripts/research.py`: retains its approved-source monitoring, run lock, Ollama adapter, exact-evidence checks, public receipts and publisher allowlist. Calls the private discovery component inside the original budget. The fetcher now exposes a robots-checked JSON method limited to the reviewed GDELT endpoint.
- `research/discovery-policy.json`: reviewed budget and 22 category-wide questions across the five layers, regional rotation and constraint searches. Named companies are not mandatory filters.
- `scripts/discovery.py`: bounded search adapter, retained-lead consumer, safe URL eligibility, persistent attempts/backoff/content memory, two-pass fallible screening, typed proposals and private status/digest. Its standalone CLI only inspects or previews.
- `scripts/editorial_review.py`: extends the existing queue/event log and interactive reviewer-account checks with human coverage triage. It does not approve source registration or publication.
- `scripts/validate.py`: checks discovery configuration and the live agenda section alongside existing validation.
- `tests/test_discovery.py`: 19 offline tests, including a full general-run integration case with mocked network/model responses. Existing monitoring fixtures explicitly isolate monitoring; production policy remains enabled.
- `AGENTS.md`, constitution, operating guide, agenda and README: distinguish monitoring, private discovery, recommendation, human review and publication. The September 7 readiness audit is explicitly historical; its original findings are preserved. `DISCOVERY.md` documents operation and remaining limitations.

The source registry, accepted metrics and evidence, homepage configuration, renderer, runtime identity, schedule, generated site and publisher allowlist are unchanged. Existing editorial questions remain narrowly scoped to their human approvals. Broad discovery has its own reviewed questions and cannot expand an existing question's authorization.

## Actual retained coverage

An in-memory inspection of the 33 existing private lead files found 65 distinct eligible URLs with known registered ancestry: energy 7, chips 8, infrastructure 12, models 20 and applications 18. These are potential investigation leads, not new companies, verified claims or adopted coverage. No URLs were fetched and no persistent discovery state was written during that inspection. Unsupported URLs remain in the original archive.

The first planned broad search is energy, `electricity grid`, using a global delivery lens. Subsequent topics rotate through all layers before changing regional/constraint lenses. The normal 24-unit run splits into 18 monitoring and 6 discovery units; an eight-unit downtime batch splits into 6 and 2. A search counts as one unit. Model calls and elapsed discovery time have separate caps. Focused source/question runs retain their existing scope and skip the general discovery lane.

## Validation actually run

- `python -m unittest discover -s tests`: **146 tests passed**, including the 19 new discovery tests. Cases cover unfamiliar hosts reaching only the private queue, full-run budget separation, prior-lead consumption and one-hop limits, unknown ancestry, unsafe URLs and private DNS, the fixed search endpoint, search/access/model failures, backoff, unchanged-content screening avoidance, changed-policy re-screening, duplicate proposals, malformed or unsupported output, legitimate empty/rejected findings, interactive-review boundaries, all-layer/region/topic rotation, one-unit alternation, time/model budgets, and side-effect-free inspection.
- `python scripts/validate.py`: passed.
- `python scripts/evaluate_editorial.py`: all eight existing decision cases passed; zero incorrect acceptances, unsupported replacements or false question resolutions. This is offline evaluation, not a live-model quality measurement.
- `python scripts/build.py`: built 107 pages successfully, including the repository's existing cross-dataset validations.
- `python scripts/discovery.py` and `python scripts/discovery.py --documents 8`: inspected plans without fetching, inference or state changes.
- `git diff --check`: passed. A separate diff check for `site`, `docs`, `research/runtime.json`, `research/homepage.json` and `research/sources.json` was empty after the build. Existing runtime-block regression tests passed; no presentation or dynamic runtime code was changed. Browser tests were not repeated because no frontend code or assets changed.

No real research loop, GPU inference, new schedule, credential change or publication-permission change was performed for this evaluation. Search parsing and failure handling used mocked responses; live provider availability and local-model discovery quality remain unmeasured. No discovered finding was accepted into the site.

## Remaining evidence and collection gaps

GDELT is a bounded news-discovery adapter, not a comprehensive general web, filings or scholarly search. PDF tables, JavaScript-only job listings, original-paper ingestion and statistical APIs still need reviewed adapters. HTTPS/query/path/robots/redirect restrictions can leave valid sources inaccessible; those gaps do not justify a bypass. English queries with regional lenses do not establish local-language completeness.

Novelty and publisher authority require human assessment. The digest counts attempted URLs, completed screens, queued proposals and human triage separately; it does not infer actual catalog adoption. An `investigate` decision prioritizes a later eligible lead check, not an autonomous new question or source-policy change. Adding a source, company, project, metric or homepage item still requires its existing reviewed implementation workflow. Capacity is capped at 2,000 private leads and flagged rather than silently growing without bound.
