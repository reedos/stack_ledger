# Research sessions

The owner requested a daily 1–7 AM Pacific session and configurable manual research. This extends the existing runner, discovery lane, evidence checks and private review queues. It does not grant the model approval or publication authority.

## Overnight operation

`research/runtime.json` declares `0 1 * * *` in `America/Los_Angeles`. `python scripts/schedule.py --update` updates the existing OpenClaw daily job in place; it does not create a second nightly job. The payload is:

```powershell
python scripts/research_loop.py --start --publish --minutes 360 --overnight --ignore-gpu-busy --keep-awake
```

The controller aims for 7 AM and preserves a six-hour elapsed minimum. A late start or spring DST transition can finish later; fall DST can require seven elapsed hours. Starts outside 1–7 AM are skipped. OpenClaw allows 7.5 hours for the window and finalization and receives heartbeat output while a batch runs or waits. This is elapsed session time, not a guarantee of six hours of model inference or novel evidence. Source cooldowns, unavailable data, retries and any user-selected GPU waits count as elapsed time. Never manufacture findings to fill the window.

The default session count cap is removed (`--max-cycles 0`). Eight work units per batch, model timeouts, evidence limits, source cooldowns, robots restrictions and discovery's four-call cap remain. Publication/preflight failures (batch exit code 3) stop immediately for maintenance. Other failed batches retry after a minute, up to three consecutive failures; success resets that counter and pauses briefly before another batch. These are failure limits, not a cap on healthy research. A blocked session exits nonzero and immediately attempts its existing Telegram completion receipt. The panel shows the failure reason. A deadline reached with unresolved failures is reported as failed. Every publishing batch repeats the clean-tree/remote preflight. A dirty tree remains blocked until a maintainer resolves it; the controller never resets files or widens permissions. Manual stop, process interruption and machine shutdown can end a session early.

Keep-awake prevents automatic system sleep only while the session controller is running on Windows; it permits display sleep. The PC and OpenClaw gateway must already be awake at 1 AM. No Windows wake timer, startup task or global power setting is changed. An active document/model call or publication finishes safely after a stop/deadline, so the end is not an exact hard cutoff.

## Manual control panel

Double-click `Research-Control.cmd` at the repository root, or run:

```powershell
python scripts/research_control.py --open
```

Opening the UI does not research. Click **Start research session** to start a session. Controls include 1–1440 minutes, balanced/monitoring/mostly exploratory/fully exploratory direction, optional five-layer selections, optional source categories, GPU-idle gating, keep-awake and eligible monitoring publication. Default manual mode saves private proposals and dedicates GPU time; publication is opt-in. An empty layer/category selection means all. The UI shows elapsed time, completed/failed batches, latest discovery counts and live output; **Stop after current work** works for both scheduled and manual controller sessions. Closing the tab does not stop research.

Categories reuse reviewed collection ranks: official/filings, earnings/IR, product/technical/blog, newsroom, news/analyst, social and unclassified. They are broad evidence classes, not perfect URL/content classifiers. In discovery they are search cues and review preferences; GDELT cannot guarantee that each result is of the requested type. Existing source coverage and readable formats limit what can be collected. No arbitrary user/model URL is added to publication permissions.

CLI equivalents:

```powershell
# Preview only; no GPU or model calls:
python scripts/research_loop.py --minutes 360 --direction exploratory --layers energy infrastructure
# Start private chip/technical exploration for three hours:
python scripts/research_loop.py --start --minutes 180 --direction discovery --layers chips --source-kinds technical --ignore-gpu-busy --keep-awake
```

The legacy optional cycle limit remains available only if explicitly requested, for example `--max-cycles 6 --min-minutes 0`. Session-level options cannot alter approved question scope. Pure discovery never updates public runtime counters or commits data, even if publication is selected.

## Progress and trust boundaries

The owner requested a whole-session summary in the public footer. On finalization, `session_receipt.py` derives an aggregate-only `runtime.latest_session` from this session's retained batch receipts, reusing `research_notify.summary`. It includes elapsed time, batch/failure counts, repeated fetches, model calls, accepted monitoring records, quarantine and collection errors. Missing receipts are disclosed. It never includes source text, private URLs, local paths, routing or operator options. The owner subsequently requested removal of the final-batch-only line from both static and dynamic footer rendering. Full-session totals, hardware, placement and runtime timestamps remain intact; batch receipts remain available in the ledger/local records.

Only publishing sessions with monitoring enabled attempt this update. Private and discovery-only sessions stay private. The finalizer uses the existing batch lock, clean-tree/remote preflight, validation, deterministic build, tests and publisher; it does not start inference. It makes one final summary commit rather than treating that commit as another research batch. Publication checks recompute totals from the retained receipts, including retrying an unpushed daily commit. Completion does not imply error-free research. A blocked/failed session can report its actual outcome if publication preflight is healthy; publication failures retain the private summary and are disclosed in the existing completion notification. No forced reset, permission change or extra schedule is used.

`public-summary.json` and `summary-publication.json` in the private session directory retain the proposed public aggregate and its publication outcome. Successfully finalized summaries are idempotent. The owner-authorized September 8 backfill uses all 306 retained receipts, not an inferred sum from public timestamps. The protected runtime fixture was updated for this explicit footer request; footer template and CSS protection remain unchanged.

The local panel includes rolling GPU utilization (%) and temperature (degrees Celsius) plots for GPU 0, sampled read-only through `nvidia-smi` every two seconds while the tab is visible. It retains up to 300 samples in the control-server process (ten minutes at the normal cadence). Multiple tabs share cached readings. Gaps, unsupported sensors and failed requests are not zeros; long unobserved intervals are not connected. The temperature axis expands if readings exceed its initial 100-degree range. Readings cover all activity on the device, not just research. No telemetry is copied into the public site, and GPU inspection does not start inference.

- `.local/session-status.json`: most recent session, state, elapsed duration and batch counts.
- `.local/sessions/<id>/status.json` and `output.log`: retained session status and live batch output.
- `.local/sessions/<id>/ledger.json`, `excerpts.json`, `cache.json`: cumulative private monitoring proposals; never automatically merged into public data by a later publishing session.
- `.local/discovery/latest.json`, `digest.md`, existing run/evidence/review queues: discovery details and proposals.

The controller owns an exclusive `.local/research-session.lock`; each batch retains the original `.local/research.lock`. When an overnight start encounters either existing lock, it records `.local/schedule-overlap.json` and exits successfully as **skipped** without research. It does not interrupt, extend or change the publication mode of the manual run, nor queue a replacement that morning. The next automatic attempt is the next scheduled night. The panel shows the dated skip notice. Manual duplicate starts remain blocked. The panel writes a session-specific stop flag and never clears an active lock. A retained global `.local/stop-research-loop` flag still blocks sessions until deliberately removed by a maintainer. After a crash, inspect the recorded PID and running processes before considering stale-lock cleanup.

The UI binds only to loopback on a random port and private session URL. Mutation requires the local Origin plus a session header; GET cannot start research or record a review. It serves only fixed local assets. User controls become validated argument arrays, never shell text. Source/model text is rendered as plain text, not HTML. The panel is not copied to GitHub Pages. Do not expose the server through a tunnel or copy its private session URL to public data.

Status files use unique temporary paths and bounded retries for Windows sharing errors. The per-session status is authoritative; failure to update the dashboard mirror is logged without aborting research. Run IDs include a random UUID suffix, so same-second private sessions cannot overwrite each other’s receipts. A collision check also protects accepted history. Monitoring and discovery evidence writes share the same bounded, atomic JSON writer as session status. Test fixtures reset execution history and runtime attribution instead of inheriting the latest live run. Three consecutive GPU telemetry errors stop an idle-gated session explicitly; a healthy reading of a busy GPU still waits as requested.

## Review findings

After updating panel code, reopen `Research-Control.cmd` and use the new tab. Refreshing an old tab updates assets but cannot reload its running Python server. Missing review controls or an outdated review endpoint show a restart message. Reopening the panel does not start or stop research. Isolated browser tests use `--ephemeral` so they cannot overwrite `.local/research-control-url.txt` with a temporary server URL.

The **Review findings** tab renders the existing discovery proposal queue as readable HTML cards, with layer/status filters and ten-card pagination. It shows source links, publication/retrieval/proposal dates separately (unknown dates stay unknown), evidence, measurement basis, suggested relevance, next questions, screening limits and the last recorded decision. Empty and unreadable queues are reported explicitly. Refresh loads new findings without starting research.

Investigate / Defer / Reject require a reason and an explicit evidence-review checkbox. The server obtains the reviewer from the existing local-account mapping; the browser cannot choose an identity. It reuses `discovery.record_review`, the editorial lock and append-only event log. Proposal and previous-review hashes prevent saving a stale decision after evidence or another review changes. The CLI remains available. These controls record human triage, never public registration or publication approval. A separate maintained source/catalog diff is still required to adopt new coverage; the tab explains this handoff rather than inventing an approved publication package.

## Telegram completion receipts

The owner authorized completion notifications through Ara's existing OpenClaw Telegram direct-message route. `.local/telegram-notifications.json` holds only enabled/account/target; no bot token is copied into this repository. Set enabled to false there to disable receipts. The route is shared by scheduled and manual controller sessions. It does not change OpenClaw's daily job delivery settings or send a message after each batch.

`research_notify.py` summarizes session-specific batch receipts: elapsed time, finished/failed batches, fetched documents, model calls, accepted monitoring records, quarantine, source errors, new private discovery proposals, confirmed pushed batches and pending/unconfirmed publication. Accepted records do not necessarily mean public records. Full exploration remains private. A skipped overnight collision gets an explicit skip message. Stopped/interrupted/blocked sessions retain their actual state. Blocking publication failures retain saved evidence and uncommitted files; they do not switch publication mode, approve proposals, reset Git, or restart themselves. Resolve the logged cause before restarting.

Each notification is attempted once and saved in a private receipt; ambiguous failures are not automatically retried to avoid duplicate messages. Delivery failure does not undo research. The panel reports completion-notification status, and per-session `notification.json` / `summary.json` retain details. A process kill, power loss or a failure before the controller initializes cannot guarantee a completion message. These are fixed receipt summaries without source/model-authored prose, source excerpts, private local URLs or credentials.

## Validation

`python -m unittest discover -s tests` covers allocation, six-hour virtual-time retry behavior, DST/late starts, source filtering, command validation, exclusive locking, scoped stop, private cache continuity, discovery-only publication isolation, HTTP request guards and existing evidence/runtime contracts. `node tests/research_control.cjs` checks desktop/mobile controls using an intercepted start request; it does not run inference. Use the existing `PLAYWRIGHT_MODULE` setting. Repository validation, editorial evaluation and build remain required for publishing code changes. No six-hour live-model trial is implied by the offline simulation.

## Collection efficiency

See OPERATING_GUIDE.md for persistent robots/page/provider cooldowns. Healthy duration remains unchanged; when no sources are eligible, the controller reports `waiting for eligible sources` and waits five minutes without generating public run updates. Completion summaries distinguish new-findings pushes from monitoring-only pushes, cached reviews from model documents, and repeated fetches from unique content versions when recorded. A provider outage is clearly flagged even if the overall session completed.


Each completed session also retains `research-progress.md` and `research-progress.json` beside its summary. These group recorded discovery attempts by question and link existing proposals; existing human editorial question decisions remain separate. Older runs without per-attempt question metadata cannot be assigned invented progress. The live discovery digest exposes partial text coverage, empty/rejected outcomes and unsupported-document pointers. These diagnostics remain local and do not change public runtime presentation.
## Catalog updates after research

The Review findings tab includes evidence-linked catalog packages and isolated site previews. See [CATALOG_FEEDBACK_LOOP.md](CATALOG_FEEDBACK_LOOP.md). Applying and publishing a reviewed package requires research to be inactive; opening the inbox or preview does not interrupt a run. The monitoring-publication checkbox does not approve catalog changes.

After a session, use [MUSE_RESEARCH_PLAYBOOK.md](MUSE_RESEARCH_PLAYBOOK.md) to review question progress, pending catalog changes, publication/display lag and a sample of rejected/empty findings. Its desired digest includes human reconciliation with existing receipts; these fields are not all automatically aggregated. The broader calibration suite and suggested weekly human review are procedures, not new schedules, automatic stop rules or notification changes. No model evaluation starts merely because the documentation is updated.
