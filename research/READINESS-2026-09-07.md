# Local research readiness audit — September 7, 2026

## What was checked without running research

- Ollama's local `/api/tags` endpoint responded and lists `muse-glimmer:30b-q4_K_M-dflash`. No inference, model load, research batch or GPU benchmark was requested.
- OpenClaw lists one enabled Stack Ledger command job, invoking the maintained runner with `--publish` at `0 19 * * *`, timezone `America/Los_Angeles`. Its existing schedule was not changed. The gateway answered the read-only job listing.
- The last recorded scheduler execution was command-successful but its underlying research receipt was partial, with access failures and no accepted findings. Scheduler “ok” is not comprehensive research success.
- The latest public research receipt remains September 7, 2026 at 07:42:36 UTC: partial, five documents reviewed, eight model calls, zero accepted, one quarantined. This audit does not replace it or advance last-success.
- Git publication is working for curated changes. The installed scheduler uses this working checkout. The unattended publisher still requires a clean tree and fast-forward Git state when it starts.

## Gaps found and addressed

The registry had grown to 338 sources and 267 metrics, while the guide still described a much smaller site. There were 18 sources without an explicit collection policy and 132 non-index sources with neither a metric mapping nor enabled notes. Merely fetching these was not enough to research them.

The reviewed registry now has 340 sources, explicit policies, and 134 note-enabled sources. Two intentionally retained unmapped sources remain review leads: Epoch's Stargate Michigan estimate and the BizNews article. Primary micro1 trade-training and opportunities pages are registered; the latter has limited readable content.

The runner now passes the constitution and operating guide to extraction and verification, and supplies source-linked context from all six curated coverage snapshots. It rotates across sessions using persistent attempt history, including never-attempted and overdue weekly sources. Cache identity includes instructions, policy, context and metric definitions. Updated documents can produce new evidence notes without replacing earlier records; identical summaries/evidence are deduplicated.

Each accepted note also creates a private review candidate for curated snapshots. New measures without mappings retain metric candidates. Selected external pointers and secondary sources remain private discovery leads and do not automatically expand the network allowlist. Coverage receipts distinguish attempted sources from never-attempted sources; run failures must be read alongside them.

## Optional downtime operation

`python scripts/research_loop.py` only previews a plan. It was previewed, not started. No extra scheduled job was installed.

When the owner elects to run it, `--start --publish` enables bounded batches, with a shared runner lock, three low-utilization GPU samples before each batch, cycle/document/time limits, a stop-file check and stop-on-error behavior. It does not reserve the GPU, measure keyboard inactivity or preempt active inference. Time limits stop new documents; finishing a document can overrun the nominal budget. The existing daily job remains enabled independently.

## Remaining limitations

- The revised live inference/publication path has not been exercised end-to-end, in accordance with the owner's no-run instruction. Automated checks use mocked model/network calls; they are not a substitute for that later acceptance run.
- Collection is readable HTML with bounded approved discovery, not unrestricted web search, PDF-table extraction, complete statistical API ingestion or complete JavaScript-rendered job-board coverage.
- A registered source is not a guarantee of successful access, fresh evidence, numeric extraction or full topic coverage. Weekly review and a finite document budget remain deliberate limits.
- New companies, metrics, source permissions, chart designs, project-stage corrections and curated claim verdicts still require reviewed changes. The local model proposes evidence; it cannot redesign pages or change its own governance.
- Machine sleep, stopped Ollama/gateway, unavailable credentials, a busy GPU, a stale lock or a dirty/divergent checkout can prevent unattended work. The audit verifies current metadata and code, not future availability.

## micro1 follow-up

See the emerging-work section in RESEARCH_AGENDA.md. The official trade-task page supports a recruitment opportunity for paid approved recordings. The linked secondary article's 10,000-person campaign and $50–$90/hour should remain attributed recruitment claims pending original-campaign verification; they do not establish completed hires, guaranteed hours, annual income or economy-wide net job creation.
