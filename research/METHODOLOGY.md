# Methodology

## Scope and classifications
Energy covers generation, grid delivery, storage and electricity demand. Chips covers accelerators, memory, packaging and manufacturing. Infrastructure covers operational data centers, networking, cooling and construction. Models covers reproducible capability, cost, efficiency and availability. Applications covers adoption and measured practical outcomes.

Records use observation (reported historical measurement), estimate (modeled historical quantity), forecast (future projection), government-target, or company-commitment. Status belongs to each point, not an entire chart. All-data-center measures are contextual indicators, never relabeled as AI-only. Benchmark results remain specific to a benchmark version, model and evaluation protocol; do not generalize one score into universal intelligence.

## Testing the industrial premise

The editorial premise is that abundant power, domestic manufacturing and useful AI can support American reindustrialization. It is a direction for research, not an established national outcome. Trace each supported step from delivered electricity and chip supply to operational AI factories, model and agent reliability, and completed work.

Local value requires local evidence: supplier purchases, wages, realized operating jobs, tax receipts and relevant public costs. Total investment and company sales cannot substitute for these measures. Customer productivity needs a task, comparison, deployment context, quality measure and costs including human oversight where available.

Robotics coverage distinguishes demonstrations, pilots, orders and operational deployments; record task completion, uptime, interventions, physical performance and economics when reported. Medical and drug-discovery coverage distinguishes predictions, laboratory results, trials, approvals and demonstrated patient outcomes. Science, engineering, climate and clean-energy coverage looks for reproducibility and validation beyond a model benchmark or simulation. Preserve negative results and limitations.

Networking coverage includes compute, storage and networking chips, copper and optical links, and the distinction between scale up within systems, scale out across clusters and scale across sites. Record deployed scope, bandwidth and latency in context; do not infer application value from nominal link speed.

The expanded narrative describes research priorities. It does not add observations or imply every topic is covered by the current source registry. New numeric series and sources still require review.

## Reading the charts
Bars start at zero. Solid bars show reported observations or estimates; hatched bars show forecasts or commitments. Separate bars preserve the exact reported periods and avoid fabricated intervening history. Each figure includes a table with value, unit, year, status and source. We show source publication date and access date separately. A newly accessed historical source is not new progress.

Targets are attributed to an owner and retain their announcement date and horizon. Forecasts are planning references, not promises. We display a target gap only with a compatible observation. We do not claim on-track/off-track without a cited intermediate trajectory and observed updates. The 2050 U.S. nuclear target is a broader energy-system goal, not power dedicated to AI. The seed ledger deliberately labels missing evidence about completed capacity or target achievement.

## Automated updates
The approved source list and metric catalog are reviewed code. The daily runner checks approved pages and discovers a small number of relevant same-host links. Sources not available as readable public HTML are logged as unavailable; automation does not bypass restrictions. A local model extracts candidates and separately screens support. Deterministic checks verify shape, evidence presence, numeric support, duplication, bounds and dates. These safeguards cannot prove factual correctness or eliminate correlated model errors. All machine-added observations are visibly labeled automated and retain their source.

Source coverage is a starting collection, not a census. Missing data does not mean no progress. Source failures are exposed in run receipts. To extend coverage, propose source and metric catalog changes through review. Annual reports should remain dated and can be supplemented with approved current release/index pages. The unattended runner can add concise research notes from discovered source articles after evidence and model screening. Numeric series stay within the reviewed metric catalog.

## Companies, revenue and industrial development

The company directory is a representative map, not a ranking or complete census. Companies can serve multiple layers. Company roles and industry snapshots live in the reviewed `research/ecosystem.json`; numeric revenue and capacity observations live in the main ledger, within the reviewed metric catalog. Daily publication can append screened observations; it cannot rewrite company roles or industry interpretations. Snapshot review dates and financial reporting periods are separate from the runtime's last run date.

Annual company revenue, segment revenue and annualized revenue run rates are distinct. Keep original reporting currency, fiscal period and scope. Do not annualize a quarter, treat funding or valuation as revenue, attribute company-wide revenue to AI, or add suppliers' sales into an AI market-size or GDP total. Company revenue is not evidence of measured customer productivity. Run rates retain their original disclosure period and are not represented as current annual results.

Fab capacity, wafer shipments, HBM output, packaging throughput and operational compute are distinct series. Annual 12-inch-equivalent capacity cannot be added to monthly 300mm capacity or advanced-node subsets. Historical forecasts remain forecasts after their target year passes until an observed update is sourced. Do not infer accelerator counts from wafer capacity without a reviewed model and defensible die-size, yield and product-mix assumptions.

Jobs snapshots distinguish reported peak construction workers, expected direct operating positions and broader regional impact estimates. Never sum these into a net AI jobs number. Macroeconomic employment changes are contextual and do not establish AI causation. Industrial rebuilding is an explicitly labeled interpretation supported by operating production, project stages and employment evidence; announced spending alone does not establish a sustained national trend. Negative employment changes use a visible zero-centered axis.

The daily 24-document budget retains five baseline sources and rotates the expanded registry in seven-source steps by UTC day. One relevant same-host child may follow each parent. Dated annual reports remain dated; new filings need discoverable approved links or a reviewed source addition. PDFs and inaccessible pages may require curated review because the unattended fetcher reads public HTML. Same-year run-rate revisions are quarantined by the conservative duplicate/conflict policy rather than automatically replacing the snapshot.

## Components, skilled trades and clean-energy manufacturing

`research/fabric.json`, mirrored to `site/data/fabric.json`, holds the reviewed component map, technology stages, workforce evidence and energy-manufacturing cases. Company-role sources are separate from financial sources where needed. A profile can explicitly have no verified revenue record; that is a coverage gap rather than a claim of zero revenue or universal non-disclosure. Such profiles are excluded from annual and run-rate filters.

Component relationships describe capabilities, not a verified contract network or mandatory bill of materials. Co-packaged optics sampling, demonstrations and reported volume production retain their individual source dates. A newly accessed historical milestone remains historical. Unknown publication dates remain unlisted.

Workforce observations retain the distinction between occupation estimates, industry payroll changes, annual openings and projected staffing. Construction includes nonresidential specialty trades; they cannot be summed. Electrician openings include replacements, while employment growth measures net change. Political and union commentary is attributed and kept separate from statistical findings. Manufacturing investment and module capacity do not establish power generation or an AI-only benefit. These cases and role mappings require review; the unattended researcher may append screened records within approved sources and metrics.

## Project delivery tracker

`research/delivery.json` is a reviewed snapshot, mirrored to `site/data/delivery.json`. Each project has a stable ID, owner, location, scope, stage, dated source-linked milestones, capacity record references, grid context and next evidence needed. Energy and infrastructure pages link to the filtered tracker. A reported operating facility can have unknown electrical capacity; that is not zero. Partly operating campuses do not inherit the full planned rating as delivered capacity. Solar generation, storage discharge power, stored energy, transmission ratings, IT load and accelerator counts remain separate.

Milestone dates preserve source publication dates. A commissioning target does not become an operating event after its date passes. A broad regional regulatory change is labeled context; it cannot establish that a particular operating facility stopped. The tracker currently provides selected-project evidence and national context, not a complete regional resource-adequacy model. Project counts are coverage counts and are never presented as an AI completion rate.

Stage and timeline changes require review; daily automation can append screened numeric records and research notes within approved mappings. If a referenced capacity record is superseded, tracker validation blocks publication until its reference is reviewed. Focused research can use `--sources` with registered source IDs; unknown IDs are rejected. Focused runs retain the normal evidence checks, and are marked partial when they do not cover all five layers, even if all selected sources were accessible.

## Corrections
Open a GitHub issue with the record ID, original source, proposed correction, and supporting evidence. A reviewer marks the incorrect record with superseded_by and adds a replacement with correction_of and a correction_reason. Charts exclude superseded records; the raw ledger and Git history retain them. The daily agent quarantines conflicting values instead of overwriting them.

## Attribution
Concept inspired by Jensen Huang's five-layer AI framework (NVIDIA, March 10, 2026). Stack Ledger is independent and unaffiliated with NVIDIA. Original site design and visualizations. IEA material is attributed under its stated CC BY 4.0 license where applicable; other source material retains its original rights.
