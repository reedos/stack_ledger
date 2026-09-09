# Research to catalog feedback loop

Research does not end at a news note. Newly accepted monitoring notes and screened discovery findings can produce private, evidence-linked catalog drafts. A draft may propose companies, products and projects; the maintainer package API also supports reviewed sources, metrics, appended observations and correction notes. All use the existing `.local/review-candidates` inbox and editorial audit log.

## Operator path

1. Open Research Control and **Review findings**. Discovery triage still means investigate, defer or reject; it is not publication approval.
2. Under **Catalog updates**, inspect each object's exact before/after values and original sources. Missing publication dates stay unknown. Insufficient evidence and malformed drafts appear among follow-up handoffs.
3. **Validate preview** builds an isolated copy, validates cross-file references, runs Python tests and the offline editorial evaluation. Open its site preview to inspect company pages, product portfolios and project totals.
4. Record an explicit human catalog decision with a rationale. A passing preview is necessary but does not verify the factual truth of a model's interpretation.
5. **Apply and publish** is a separate, explicitly confirmed action. It waits for research to be inactive, requires a clean synchronized repository on the configured branch/remote, checks the approved proposal hash and unchanged edited objects, repeats preview checks, updates canonical JSON and mirrors, builds, commits and pushes only permitted catalog files and generated docs. It then compares the live Pages JSON with the expected snapshots. A push is not labeled deployed until that comparison succeeds.
6. The private publication receipt retains a commit for retry after transport/deployment failure. Changed objects require a fresh package and review. Unrelated run receipts do not invalidate a package. Successful deployment records follow-up evidence questions; new canonical objects also enter the existing research coverage context and registered-source monitoring.

Project counters, filters, company pages and layer lists derive from the reviewed catalogs; nobody edits a separate project count. `company_ids` connects projects with participating companies; optional `parent_project` identifies overlapping programs/phases. These are object counts, not unique sites or additive capacity. A delivery percentage still requires defensible non-overlapping accounting.

Project capital and jobs sections read accepted observations by their metric's project link. The industry jobs table includes newly evidenced projects automatically. Headline project quantities follow the latest year of the reviewed metric for each observation/forecast status, retaining same-year source vintages. Featured selections, new metric definitions and changes to project stage still require review; generic research notes cannot silently change them.

Products reuse `expansion.json`; optional `layers` defaults older products to models. Semiconductor and other products can appear on company and relevant layer pages with explicit announced, sampling, production or roadmap stages. Product specifications are not shipping volume or measured application outcomes.

One discovery search in four rotates through accepted project/product follow-up questions. The other three continue the broad topic sequence without skipping topics. Operator layer filters, the existing news adapter, source-category preferences, cooldowns and work budgets still apply. Search terms are sanitized accepted object names; unreviewed private drafts do not enter this rotation. A search result remains a lead and never resolves a question by itself.

## Boundaries and failure handling

- Retained evidence is content-hashed under `.local/catalog-evidence`. Public output contains attributed structured facts, never cached source bodies or local routing/secrets.
- Researchers may propose object IDs only inside private drafts. They cannot register IDs, approve proposals, edit policies/code/templates, or widen the unattended publisher allowlist.
- Drafting adds at most one model call per newly accepted note/finding; discovery retains its existing call/time budget. Private drafting errors do not turn an otherwise accepted monitoring record into a failed batch. The handoff records the unresolved draft.
- Exact changed objects must still match their before values; full current-catalog validation runs again before application. Existing numerical records and notes remain append-only except explicit observation supersession metadata.
- Human review uses the configured local reviewer identity and the control panel's existing session-token, Host and Origin checks. A model screen never becomes a review event.
- Git/build failures retain evidence. A failure before a commit can leave a dirty working tree for inspection; publication refuses to continue until it is reconciled. It never force-pushes, auto-resets or discards changes.
- The runtime/hardware block, featured homepage selection and local-model run attribution are unchanged. Direct maintainer research must not be reported as an Ollama run.

Implementation: `scripts/catalog_recommender.py`, `scripts/catalog_review.py`, existing discovery/research runners, findings inbox and local control panel. Maintainers can call `catalog_review.enqueue(root, title, changes, evidence, author)` and `preview(root, id)` without approval or publication. There is intentionally no auto-approval command.

For research quality, use the compact worked examples in [OPERATING_GUIDE.md](OPERATING_GUIDE.md), which the runner also supplies to catalog drafting. [MUSE_RESEARCH_PLAYBOOK.md](MUSE_RESEARCH_PLAYBOOK.md) documents follow-up cards using current fields, human calibration, review-rationale conventions and a manual end-of-run oversight checklist. These do not expand schemas or make review logs automatic model training. Offline package validation proves structural/build compatibility, not the factual correctness of a draft or Muse's measured extraction accuracy.
