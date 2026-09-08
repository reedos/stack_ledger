# Broad discovery within the existing research framework

Monitoring maintains accepted series. Discovery investigates what is missing. Recommendation proposes a change; a human reviews it; the maintained renderer and restricted publisher operate only on approved inputs. None of these roles grants itself the next role's authority.

## What runs

`research.py` invokes `discovery.py` inside its existing lock. No extra process, scheduler, credentials or model tools are installed. Normal daily and downtime runs inherit the reviewed policy. Focused source/question runs skip discovery. The 25% reservation includes searches and pages, not just successful retrievals. At most one search runs per batch, five results per search, four local-model calls and 300 seconds of discovery time, further capped at 25% of the original run time. Both model passes are bounded by remaining discovery time. Existing HTTP/robots requests can finish beyond the boundary; this is not hard process preemption. Monitoring keeps its existing public receipt and publication restrictions.

The [GDELT DOC 2.0 adapter](https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/) uses a fixed HTTPS endpoint, JSON article lists, a one-month window and no credentials. Queries come only from reviewed configuration. Search results are untrusted leads, not primary evidence or statements of fact. Missing/invalid responses and access restrictions are recorded; there is no access-control bypass or paid fallback. This is a news index, not an exhaustive web search. Original filings, papers, employer feeds and statistical APIs still need additional reviewed adapters.

Questions cycle through every layer and topic before changing between delivery and constraint lenses and then regions. Named companies are not required search terms. This supports emerging builders and occupations without a model silently rewriting the research mandate. Regional keyword searches do not establish local-language completeness. A one-month search window concerns discovery recency only; source forecasts beyond 2030 remain eligible.

## New hosts and retained leads

The runner imports eligible URLs from the existing `.local/discovery-leads` archive with known registry ancestry. Search results and one-hop links from fetched documents can seed additional private investigations. New hosts must use HTTPS, no credentials/query strings/literal IP addresses, public DNS, supported readable content and robots permission. Login, account, application and download paths are excluded. The existing same-host redirect rule remains: foreign redirects are skipped rather than automatically trusted. PDFs and dynamic content are still collection gaps. Model output never supplies network requests, paths, shell commands or configuration.

The private lead store deduplicates canonical URLs, rotates fresh and backlog priority, retains provenance and hashes, and records the last attempt and next eligible attempt. Unchanged documents skip inference when model, code, agenda, coverage and policy are unchanged. Normal revisits take seven days; failures back off from one day to a maximum of 30. Failed screening is not cached as successful research. Human-prioritized investigation is ordered first when eligible. At 2,000 leads the store flags capacity reached; reviewing/archiving that backlog requires maintenance rather than silent eviction or unbounded crawling. Unsupported pointers remain in their original archive.

## Evidence and review

Each model proposal identifies a company, project, source, metric, occupation or topic; an attributed claim; actual/estimate/forecast/commitment/unknown basis; exact evidence; why it may deserve tracking; and a next question. The latter two are proposals, not proved benefits. The extraction prompt includes current layer company names, metric IDs and the active agenda. Numeric token checks and a second skeptical model pass screen the claim. Publisher authority and novelty remain unverified until human review. Empty findings and rejected screening are valid outcomes.

Proposals extend `.local/review-candidates` as `discovery-*.json` with `kind: coverage_expansion`. They use the same editorial event log and lock. Discovery never appends to the public ledger, creates catalog IDs, registers a source or changes homepage recommendations. Evidence bodies are private. The digest renders untrusted prose as indented text; it is never included in generated site assets.

Human triage uses the existing interactive local-account check:

```powershell
python scripts/editorial_review.py review-discovery discovery-<id> --decision investigate --reviewer reedos --rationale "Verify the original permit and proposed measurement scope"
```

The human types the complete ID. `investigate`, `deferred` and `rejected` are triage decisions; none means approved publication. Priority is applied to later eligible lead checks; this does not run an autonomous custom-question agent. Implementing a new source, company, project or metric remains a separately reviewed repository change with original-source checks, catalog/source updates and normal tests. Homepage selection still goes through its separate incumbent-versus-challenger review on frozen accepted data. Discovery cannot invoke review commands or approve itself.

## Monitoring progress safely

```powershell
python scripts/discovery.py
python scripts/discovery.py --documents 8
python scripts/discovery.py --status
Get-Content .local/discovery/digest.md
```

The first two commands only preview; they do not start inference, search, import or modify state. Status falls back to the plan before the first run. During execution `.local/discovery/latest.json` identifies the topic, attempted pages, counts and errors; the digest is written at the end of each slice. Historical receipts are in `.local/discovery/runs/`. Page/source retrieval, successful screening, queueing, human triage, acceptance and publication are different events. Public hardware attribution and runtime presentation are unchanged.

Assess usefulness by evidence-backed proposals and eventual reviewed additions, with layers, unknowns and rejected/empty results visible. The current digest counts proposals and human triage separately; it does not automatically certify novelty, causal effects or catalog adoption. Fetch counts alone cannot establish expanded coverage. Inspect the actual reviewed catalog diff before reporting an adopted addition.
