'use strict';
let expansion;
let chipCapacityConfig;
const publicationLabel=d=>d?`Published ${dateLabel(d)}`:"Publication date unlisted";
const moneyKinds=[['Announced investment','capex_announced_usd'],['Contracted compute','compute_contract_usd'],['Capex paid / recognized','capex_recognized_usd'],['Local contracts / procurement','local_procurement_usd'],['Cumulative capital cost · Epoch estimate','estimated_site_capital_cost_usd_bn']];
const jobsKinds=[['Peak construction workers','construction_workers_peak'],['Contractor FTEs','contractor_fte'],['Permanent jobs promised','permanent_jobs_promised'],['Operating jobs reported','permanent_jobs_reported'],['Company-wide headcount','company_headcount']];
const kindOf=o=>metricOf(o.metric).measurement_type;
const evidenceOf=ids=>ids.map(id=>data.observations.find(o=>o.id===id)).filter(Boolean);
const typedRecords=(field,id)=>data.observations.filter(o=>!o.superseded_by&&metricOf(o.metric)[field]===id);
function quantityEvidence(o) {
 const m=metricOf(o.metric),s=sourceOf(o.source);
 return `<div class="scoped-quantity ${historicalStatus(o.status)?'actual':'future'}"><span class="evidence-status">${esc(attributionLabel(o))}</span><strong>${esc(valueOf(o))} <small>${esc(m.unit)}</small></strong><p>${esc(m.title)}</p><p class="chart-footnote">${esc(o.period)} · ${esc(m.geography)}</p><p class="chart-footnote">${esc(m.scope)}</p><p class="chart-footnote">${sourceLink(o.source)} · ${publicationLabel(s.published)} · Accessed ${dateLabel(o.retrieved_at)}</p><details class="record-id"><summary>Record details</summary><p>Company: ${esc(companyOf(m.company)?.name||m.company||'See source')} · Metric: ${esc(m.id)} · Record: ${esc(o.id)} · ${esc(o.method)}</p></details></div>`;
}
function basisRows(obs,kinds) {
 return `<dl class="basis-rows">${kinds.map(([label,kind])=>{const os=obs.filter(o=>kindOf(o)===kind);return `<div><dt>${esc(label)}</dt><dd>${os.length?os.map(quantityEvidence).join(''):'<span class="not-verified">Not verified in this review</span>'}</dd></div>`;}).join('')}</dl>`;
}
function projectMeasures(p) {
 const obs=typedRecords('project',p.id),grouped=[...moneyKinds,...jobsKinds].map(([,kind])=>kind);
 const other=obs.filter(o=>!grouped.includes(kindOf(o)));
 return `${other.length?`<details class="project-measures" ${['colossus-one','colossus-two','waymo-one'].includes(p.id)?'open':''}><summary>Plans, contracts & equipment evidence (${other.length})</summary><div class="scoped-grid">${other.map(quantityEvidence).join('')}</div></details>`:''}<details class="project-measures"><summary>Capital & jobs — separate measurement bases</summary><h3>Project money</h3>${basisRows(obs,moneyKinds)}<h3>Workforce</h3>${basisRows(obs,jobsKinds.slice(0,4))}<p class="chart-footnote">No totals: project investment, local contracts, cash paid and jobs measure different things.</p></details>`;
}
const CHIP_CAPACITY_TYPES=['wafer_starts_per_month','cowos_or_advanced_packaging_wspm','hbm_stack_capacity'];
function chipCapacityNote(text) {
 return `<div class="chip-capacity"><span class="eyebrow">CAPACITY QUANTIFICATION</span><p class="chip-capacity-note">${esc(text)}</p></div>`;
}
function chipCapacityTsmcShare(annualWafers) {
 const obs=data.observations.filter(o=>o.metric==='tsmc-wafer-capacity'&&!o.superseded_by).sort((a,b)=>a.year-b.year);
 if(!obs.length)return '';
 const latest=obs.at(-1),pct=annualWafers/(latest.value*1_000_000)*100;
 return `<div><dt>Share of TSMC company-wide capacity</dt><dd>≈ ${number(pct)}% of TSMC's ${latest.year} company-wide capacity (${number(latest.value)} million 12-inch-equivalent wafers/year) · ${sourceLink(latest.source)}</dd></div>`;
}
// Chips-layer project cards: base disclosure (or what would quantify it) plus, only when a
// base figure exists, an illustrative compute equivalent. Nothing invented: unknown is not zero.
function chipCapacity(p) {
 if(p.id==='tsmc-arizona-program')return chipCapacityNote('Program envelope; capacity is tracked per phase.');
 if(p.id==='globalfoundries-singapore-expansion')return chipCapacityNote('Company entry pending review; no capacity metric yet.');
 const entry=chipCapacityConfig.projects[p.id];
 if(!entry)return '<div class="delivery-quantity unknown"><span>CAPACITY DISCLOSURE</span><strong>Not quantified</strong><p>No reviewed operating quantity for this project. Unknown is not zero.</p></div>';
 const cls=chipCapacityConfig.classes[entry.class];
 const all=typedRecords('project',p.id).filter(o=>CHIP_CAPACITY_TYPES.includes(kindOf(o)));
 const latestPerStatus=all.filter(o=>!all.some(n=>n.status===o.status&&(n.year>o.year||(n.year===o.year&&n.period>o.period))));
 const header=`<span class="eyebrow">CAPACITY QUANTIFICATION</span><span class="chip-capacity-class">${esc(cls.label)}</span>`;
 if(!latestPerStatus.length) {
  return `<div class="chip-capacity">${header}<div class="delivery-quantity unknown"><span>CAPACITY DISCLOSURE</span><strong>Not disclosed</strong><p>Quantifying figure: ${esc(cls.unit)}</p><p>Watching: ${[...new Map(entry.source_ids.map(id=>[sourceOf(id).publisher,id])).values()].map(sourceLink).join(' · ')}</p><p>Unknown is not zero.</p></div></div>`;
 }
 const base=latestPerStatus.find(o=>['observation','estimate'].includes(o.status))||latestPerStatus[0];
 const conditional=!['observation','estimate'].includes(base.status)?' if the plan is delivered':'';
 let computeHtml='';
 if(entry.class==='packaging') {
  const ratios=chipConversions.impliedRatios(data.observations);
  if(ratios) {
   const {acceleratorsPerYear,h100ePerYear}=chipConversions.packagingEquivalent(base.value,ratios);
   computeHtml=`<div class="chip-capacity-compute"><div class="chip-capacity-figures"><div><strong>${number(acceleratorsPerYear)}</strong><span>accelerators / year${conditional}</span></div><div><strong>${number(h100ePerYear)}</strong><span>H100e / year${conditional}</span></div></div><dl class="basis-rows"><div><dt>Accelerators per CoWoS wafer</dt><dd>${number(ratios.acceleratorsPerCowosWafer)} — Epoch, ${esc(ratios.quarter)}</dd></div><div><dt>H100e per accelerator</dt><dd>${number(ratios.h100ePerAccelerator)} — Epoch, ${esc(ratios.quarter)}</dd></div></dl><p class="chart-footnote">${sourceLink('epoch-chip-sales-dataset')} · ${sourceLink('epoch-chip-components-dataset')}</p><p class="chart-footnote">Illustrative scale using Epoch's Nvidia-mix ratios; this site's customers, package types and yields are undisclosed. Not a forecast, not a company disclosure.</p></div>`;
  }
 } else if(entry.class==='logic-fab') {
  const ratios=chipConversions.impliedRatios(data.observations);
  const rd=chipCapacityConfig.reference_die;
  const diePerWafer=chipConversions.grossDiePerWafer(rd.area_mm2,rd.wafer_diameter_mm);
  const {diePerYear}=chipConversions.logicCeiling(base.value,diePerWafer);
  const shareRow=entry.company==='tsmc'?chipCapacityTsmcShare(base.value*12):'';
  computeHtml=`<div class="chip-capacity-compute"><div class="chip-capacity-figures single"><div><strong>${number(diePerYear)}</strong><span>H100-class die / year${conditional} (ceiling)</span></div></div><p class="chart-footnote">A ceiling assuming every wafer carried a reticle-scale accelerator die at perfect yield; actual product mix and yields are undisclosed.</p><dl class="basis-rows"><div><dt>Gross die / 300 mm wafer</dt><dd>${number(diePerWafer)} for the ${esc(rd.name)} (${number(rd.area_mm2)} mm²) · ${sourceLink(rd.source_id)}</dd></div>${ratios&&ratios.shipments?`<div><dt>Scale reference</dt><dd>Nvidia shipped an estimated ${number(ratios.shipments.value)} accelerators in ${ratios.shipments.year} (Epoch) · ${sourceLink('epoch-chip-sales-dataset')}</dd></div>`:''}${shareRow}</dl></div>`;
 } else {
  const hbmSource=metricOf('epoch-hbm-supply-quarterly')?.source_ids?.[0];
  computeHtml=`<p class="chart-footnote">No compute conversion: stack height, die size and yields are undisclosed, so this figure cannot be translated into accelerator or H100e counts. HBM supply consumed by AI accelerators is tracked separately in value terms by Epoch${hbmSource?` (${sourceLink(hbmSource)})`:''}.</p>`;
 }
 return `<div class="chip-capacity">${header}<div class="scoped-grid">${latestPerStatus.map(quantityEvidence).join('')}</div>${computeHtml}</div>`;
}
function companyMeasures(c) {
 const obs=typedRecords('company',c.id),grouped=[...moneyKinds,...jobsKinds].map(([,kind])=>kind);
 return `<details class="company-role-sources company-capital"><summary>Capital, jobs & project evidence</summary><p class="chart-footnote">Each record names its project or company scope. Revenue above is separate from these figures.</p>${basisRows(obs.filter(o=>grouped.includes(kindOf(o))),[...moneyKinds,...jobsKinds])}${[...new Set(obs.map(o=>metricOf(o.metric).project).filter(Boolean))].map(id=>`<p><a class="source-inline" href="${base}projects/#project-${esc(id)}">${esc(delivery.projects.find(p=>p.id===id).name)} ↗</a></p>`).join('')}</details>`;
}
function featuredProjects(id) {
 const projects=(expansion.featured[id]||[]).map(id=>delivery.projects.find(p=>p.id===id));
 if(!projects.length)return '';
 const titles={energy:'Delivering power to the load.',chips:'From wafers to working accelerators.',infrastructure:'The AI factory is a physical place.',applications:'Useful work, with deployment evidence.'};
 return `<section class="section" id="named-projects"><div class="section-top"><div><div class="eyebrow muted">NAMED PROJECTS / REVIEWED EVIDENCE</div><h2>${titles[id]}</h2></div><a class="section-link" href="${base}projects/?layer=${id}">All ${esc(layerOf(id).name.toLowerCase())} projects ↗</a></div><p class="chart-footnote">Reviewed ${dateLabel(expansion.reviewed_at)}. Stages reflect the latest evidence in this snapshot; the source dates below remain visible.</p><div class="featured-grid">${projects.map(p=>{const latest=p.milestones.at(-1);return `<article class="featured-project" style="--accent:${layerOf(id).color}"><span class="stage ${p.stage==='operating'?'operating':''}">${esc(stageNames[p.stage])}</span><h3><a href="${base}projects/#project-${esc(p.id)}">${esc(p.name)} ↗</a></h3><p class="chart-footnote">${esc(p.owner)} · ${esc(p.location)}</p><p>${esc(latest.summary)}</p><p class="chart-footnote">${dateLabel(latest.date)} · ${sourceLink(latest.source)}</p><p class="next-evidence"><strong>Next evidence:</strong> ${esc(p.next_evidence)}</p></article>`;}).join('')}</div></section>`;
}
function agentProducts() {
 return `<section class="section" id="agent-products"><div class="section-top"><div><div class="eyebrow muted">MODELS → AGENT SYSTEMS → DIGITAL WORK</div><h2>From an answer to an attempted task.</h2></div></div><p class="section-intro">Labs and developers package models with tools, memory, execution environments and review steps. Product availability is evidence of a workflow people can use. Reliable completion, paid usage and hours saved need their own measurements.</p><div class="agent-grid">${expansion.products.filter(p=>(p.layers||['models']).includes('models')).map(p=>`<article class="agent-card" id="agent-${esc(p.id)}"><span class="stage">${esc(p.stage)}</span><h3>${esc(p.name)}</h3><p>${esc(p.summary)}</p><p class="chart-footnote">${companyLink(p.company)} · ${sourceLink(p.source)} · ${publicationLabel(sourceOf(p.source).published)} · Reviewed ${dateLabel(expansion.reviewed_at)}</p>${p.observations.length?`<div class="agent-prices">${evidenceOf(p.observations).map(quantityEvidence).join('')}</div>`:'<p class="not-verified">No reviewed quantitative usage or outcome figure.</p>'}<p class="next-evidence"><strong>Next evidence:</strong> ${esc(p.gap)}</p></article>`).join('')}</div><aside class="reading-note"><strong>Availability, usage and outcomes are separate.</strong><p>Named API prices keep their model and vintage. They exclude subscription fees, tool costs and supervision. No national job-displacement claim is inferred from a vendor example or internal coding-agent usage.</p></aside></section>`;
}
function projectJobs() {
 const columns=jobsKinds.slice(0,4);
 const projects=[...new Set([...expansion.jobs_projects,...delivery.projects.filter(p=>typedRecords('project',p.id).some(o=>columns.some(([,kind])=>kind===kindOf(o)))).map(p=>p.id)])];
 return `<section class="section" id="project-jobs"><div class="section-top"><div><div class="eyebrow muted">LOCAL WORK / PROMISED VS REPORTED</div><h2>Which jobs are in the record?</h2></div></div><p class="section-intro">Construction work and lasting operating roles can bring value to a community. This table keeps promised positions separate from reported operating roles. A blank means no verified figure in this edition, never zero.</p><div class="table-scroll" tabindex="0" role="region" aria-label="Project jobs comparison, scroll horizontally"><table class="jobs-comparison"><caption>Selected projects · no combined jobs total</caption><thead><tr><th scope="col">Project</th>${columns.map(([label])=>`<th scope="col">${label}</th>`).join('')}</tr></thead><tbody>${projects.map(id=>{const p=delivery.projects.find(p=>p.id===id),obs=typedRecords('project',id);return `<tr><th scope="row"><a href="${base}projects/#project-${esc(id)}">${esc(p.name)} ↗</a><p class="chart-footnote">${esc(p.location)}</p></th>${columns.map(([,kind])=>{const os=obs.filter(o=>kindOf(o)===kind);return `<td>${os.length?os.map(quantityEvidence).join(''):'<span class="sr-only">Not verified</span>'}</td>`;}).join('')}</tr>`;}).join('')}</tbody></table></div><p class="chart-footnote">Contractor FTEs are not headcounts. Peak construction and future operating roles cannot be added; broader indirect economic-impact claims are excluded.</p></section>`;
}
function capitalEvidence() {
 const ids=['hyperion-local-contracts-baseline','hyperion-investment-baseline','tesla-capex-q2-2026-baseline','nebius-msft-contract-base-baseline'];
 return `<section class="section" id="capital-evidence"><div class="section-top"><div><div class="eyebrow muted">CAPITAL / LOCAL VALUE</div><h2>Follow the dollars to their purpose.</h2></div></div><p class="section-intro">A regional investment plan, contracts awarded locally, company capital expenditures and a compute agreement answer different questions. None is a substitute for the others.</p><div class="capital-grid">${evidenceOf(ids).map(quantityEvidence).join('')}</div></section>`;
}
function catalogProducts(items){
 if(!items.length)return '';
 return `<section class="section" id="product-portfolio"><div class="section-top"><div><div class="eyebrow muted">PRODUCTS / ROLE IN THE BUILDOUT</div><h2>What these products contribute.</h2></div></div><div class="agent-grid">${items.map(p=>`<article class="agent-card" id="product-${esc(p.id)}"><span class="stage">${esc(p.stage)}</span><h3>${esc(p.name)}</h3><p>${esc(p.summary)}</p><p>${companyLink(p.company)} · ${(p.layers||['models']).map(l=>layerOf(l).name).map(esc).join(' / ')}</p><p class="chart-footnote">${sourceLink(p.source)} · ${publicationLabel(sourceOf(p.source).published)}</p>${p.observations.length?evidenceOf(p.observations).map(quantityEvidence).join(''):''}<p class="next-evidence"><strong>Next evidence:</strong> ${esc(p.gap)}</p></article>`).join('')}</div></section>`;
}
function extendWithExpansion() {
 if(page==='company'){const id=root.querySelector('[data-company]')?.dataset.company || location.pathname.split('/').filter(Boolean).at(-1);root.insertAdjacentHTML('beforeend',catalogProducts(expansion.products.filter(p=>p.company===id)));}
 if(layerOf(page)&&page!=='models')root.insertAdjacentHTML('beforeend',catalogProducts(expansion.products.filter(p=>(p.layers||['models']).includes(page))));
 if(layerOf(page)) {
  const section=page==='models'?agentProducts():featuredProjects(page);
  root.querySelector('.layer-nav').insertAdjacentHTML('afterend',section);
  if(page==='energy')root.querySelector('.detail-layout').insertAdjacentHTML('afterend',colossusPowerPath());
  if(page==='applications')root.querySelector('#named-projects').insertAdjacentHTML('afterend','<aside class="reading-note"><strong>Different driving exposure, different evidence.</strong><p>Tesla consumer FSD miles require driver supervision. Tesla Robotaxi supervision differs by city; Waymo rider-only mileage has a separate geography and period. We do not put these in a shared performance ranking. Optimus training builds are separate from Agility’s reported commercial tote handling.</p></aside>');
 } else if(page==='industry')root.querySelector('.industry-verdict').insertAdjacentHTML('afterend',projectJobs()+capitalEvidence());
 else if(page==='projects')root.insertAdjacentHTML('beforeend',`<section class="section"><h2>What we still need to verify.</h2><ul class="research-focus">${expansion.gaps.map(g=>`<li>${esc(g)}</li>`).join('')}</ul></section>`);
}

function powerBasisNote(p) {
 const notes={
  'colossus-one':'Two bases, two dates: Epoch estimates operating IT power; Anthropic describes contracted access with no IT-versus-facility definition. These figures do not establish metered consumption or utilization.',
  'colossus-two':'The June company disclosure covers individual compute clusters. The September Epoch figure estimates the building’s operating IT capacity from equipment evidence. The later end-state is a forecast. These differing scopes and vintages are shown separately, never averaged or added into a consensus.',
  'tesla-cortex-2':'Operating refers to Tesla’s Q2 Production classification and company-defined compute capacity. It does not mean that the later ramp is complete or that compute MW equals measured facility consumption.'
 };
 return notes[p.id]?`<aside class="reading-note power-basis-note"><strong>Read the power basis</strong><p>${esc(notes[p.id])}</p></aside>`:'';
}
function factoryMilestones() {
 const projects=delivery.projects.filter(p=>p.layer==='chips');
 return `<section class="section" id="projects"><div class="section-top"><div><div class="eyebrow muted">FACTORY MILESTONES / DELIVERY TRACKER</div><h2>From plans to production.</h2></div><a class="section-link" href="${base}projects/?layer=chips">Open chip projects ↗</a></div><p class="section-intro">${projects.length} chip projects and program records from the same reviewed tracker. Stages describe the cited evidence. Overlapping program envelopes and individual phases are not added.</p><div class="project-grid">${projects.map(p=>{const m=p.milestones.at(-1);return `<article class="project-card"><span class="stage ${p.stage==='operating'?'operating':''}">${esc(stageNames[p.stage])}</span><h3><a href="${base}projects/#project-${esc(p.id)}">${esc(p.name)}</a></h3><p>${esc(p.location)}</p><strong>${dateLabel(m.date)}</strong><p>${esc(m.summary)}</p>${sourceLink(m.source)}<p class="chart-footnote">${esc(p.horizon)}</p></article>`;}).join('')}</div><p class="chart-footnote">Reviewed ${dateLabel(delivery.reviewed_at)}. Production targets and promised jobs are separate from operating capacity and reported hires.</p></section>`;
}
function colossusPowerPath() {
 const steps=[
  ['01','Existing connection','Paul Lowry · Memphis','MLGW distinguishes the pre-existing connection from the later substation. The original service was not enough to establish the full campus load.','mlgw-may-2025',[]],
  ['02','Temporary generation','Separate behind-the-meter systems','Gas turbines supplement utility service. Utility approval is separate from air permitting; generator equipment does not prove permitted or continuously available output.','mlgw-may-2025',[]],
  ['03','Grid service delivered','Paul Lowry · Memphis','MLGW reports energized service after studies, transmission work and a new substation. This is a dated utility disclosure, not a current metered-load reading.','mlgw-may-2025',['colossus-grid-energized-baseline']],
  ['04','Next grid increment requested','Paul Lowry · Memphis','The requested total already includes existing service. The utility’s conditional schedule is historical; this review has not verified the later increment’s energization.','mlgw-may-2025',['colossus-grid-requested-baseline']],
  ['05','Permanent plant and turbine removal','Southaven · Mississippi · separate Colossus 2 power path','SpaceXAI describes permanent-plant construction and a temporary-turbine removal schedule. Issued permits, actual removals and commissioned generation require separate evidence. This is not another Paul Lowry grid increment.','spacexai-power-july',['southaven-permanent-gas-baseline']]
 ];
 return `<section class="section" id="colossus-power-path"><div class="section-top"><div><div class="eyebrow muted">ENERGY DELIVERY / MEMPHIS CORRIDOR</div><h2>Getting power to the AI factory.</h2></div><a class="section-link" href="${base}projects/?layer=energy">Inspect energy projects ↗</a></div><p class="section-intro">The global electricity chart is context. The Colossus records show the work underneath it: existing connections, temporary generation, utility upgrades and a separately permitted permanent plant.</p><ol class="power-path">${steps.map(([n,title,place,summary,source,ids])=>`<li><span class="path-number" aria-hidden="true">${n}</span><div><h3>${title}</h3><p class="eyebrow muted">${place}</p><p>${summary}</p><p class="chart-footnote">${sourceLink(source)} · ${publicationLabel(sourceOf(source).published)}</p>${evidenceOf(ids).map(quantityEvidence).join('')}</div></li>`).join('')}</ol><aside class="reading-note"><strong>A sequence of dependencies, not one additive power total.</strong><p>Paul Lowry, the Colossus 2 building, Southaven generation and the later Stateline Road building have separate boundaries. Temporary generation can overlap grid service. A company removal timetable is not proof of removal. The filed air-permit complaint remains an allegation, not a final judgment. ${sourceLink('colossus-southaven-complaint')}</p></aside></section>`;
}
