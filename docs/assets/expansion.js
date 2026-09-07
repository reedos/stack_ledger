'use strict';
let expansion;
const publicationLabel=d=>d?`Published ${dateLabel(d)}`:"Publication date unlisted";
const moneyKinds=[['Announced investment','capex_announced_usd'],['Contracted compute','compute_contract_usd'],['Capex paid / recognized','capex_recognized_usd'],['Local contracts / procurement','local_procurement_usd']];
const jobsKinds=[['Peak construction workers','construction_workers_peak'],['Contractor FTEs','contractor_fte'],['Permanent jobs promised','permanent_jobs_promised'],['Permanent hires reported','permanent_jobs_reported'],['Company-wide headcount','company_headcount']];
const kindOf=o=>metricOf(o.metric).measurement_type;
const evidenceOf=ids=>ids.map(id=>data.observations.find(o=>o.id===id)).filter(Boolean);
const typedRecords=(field,id)=>data.observations.filter(o=>!o.superseded_by&&metricOf(o.metric)[field]===id);
function quantityEvidence(o) {
 const m=metricOf(o.metric),s=sourceOf(o.source);
 return `<div class="scoped-quantity ${['observation','estimate'].includes(o.status)?'actual':'future'}"><span class="evidence-status">${esc(statusLabel(o.status))}</span><strong>${esc(valueOf(o))} <small>${esc(m.unit)}</small></strong><p>${esc(m.title)}</p><p class="chart-footnote">${esc(o.period)} · ${esc(m.geography)}</p><p class="chart-footnote">${esc(m.scope)}</p><p class="chart-footnote">${sourceLink(o.source)} · ${publicationLabel(s.published)} · Accessed ${dateLabel(o.retrieved_at)}</p><details class="record-id"><summary>Record details</summary><p>Company: ${esc(companyOf(m.company)?.name||m.company||'See source')} · Metric: ${esc(m.id)} · Record: ${esc(o.id)} · ${esc(o.method)}</p></details></div>`;
}
function basisRows(obs,kinds) {
 return `<dl class="basis-rows">${kinds.map(([label,kind])=>{const os=obs.filter(o=>kindOf(o)===kind);return `<div><dt>${esc(label)}</dt><dd>${os.length?os.map(quantityEvidence).join(''):'<span class="not-verified">Not verified in this review</span>'}</dd></div>`;}).join('')}</dl>`;
}
function projectMeasures(p) {
 const obs=evidenceOf(p.measures||[]),grouped=[...moneyKinds,...jobsKinds].map(([,kind])=>kind);
 const other=obs.filter(o=>!grouped.includes(kindOf(o)));
 return `${other.length?`<details class="project-measures"><summary>Plans, contracts & equipment evidence (${other.length})</summary><div class="scoped-grid">${other.map(quantityEvidence).join('')}</div></details>`:''}<details class="project-measures"><summary>Capital & jobs — separate measurement bases</summary><h3>Project money</h3>${basisRows(obs,moneyKinds)}<h3>Workforce</h3>${basisRows(obs,jobsKinds.slice(0,4))}<p class="chart-footnote">No totals: project investment, local contracts, cash paid and jobs measure different things.</p></details>`;
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
 return `<section class="section" id="agent-products"><div class="section-top"><div><div class="eyebrow muted">MODELS → AGENT SYSTEMS → DIGITAL WORK</div><h2>From an answer to an attempted task.</h2></div></div><p class="section-intro">Labs and developers package models with tools, memory, execution environments and review steps. Product availability is evidence of a workflow people can use. Reliable completion, paid usage and hours saved need their own measurements.</p><div class="agent-grid">${expansion.products.map(p=>`<article class="agent-card" id="agent-${esc(p.id)}"><span class="stage">${esc(p.stage)}</span><h3>${esc(p.name)}</h3><p>${esc(p.summary)}</p><p class="chart-footnote">${companyLink(p.company)} · ${sourceLink(p.source)} · ${publicationLabel(sourceOf(p.source).published)} · Reviewed ${dateLabel(expansion.reviewed_at)}</p>${p.observations.length?`<div class="agent-prices">${evidenceOf(p.observations).map(quantityEvidence).join('')}</div>`:'<p class="not-verified">No reviewed quantitative usage or outcome figure.</p>'}<p class="next-evidence"><strong>Next evidence:</strong> ${esc(p.gap)}</p></article>`).join('')}</div><aside class="reading-note"><strong>Availability, usage and outcomes are separate.</strong><p>Named API prices keep their model and vintage. They exclude subscription fees, tool costs and supervision. No national job-displacement claim is inferred from a vendor example or internal coding-agent usage.</p></aside></section>`;
}
function projectJobs() {
 const columns=jobsKinds.slice(0,4);
 return `<section class="section" id="project-jobs"><div class="section-top"><div><div class="eyebrow muted">LOCAL WORK / PROMISED VS REPORTED</div><h2>Which jobs are in the record?</h2></div></div><p class="section-intro">Construction work and lasting operating roles can bring value to a community. This table keeps promised positions separate from reported hires. A blank means no verified figure in this edition, never zero.</p><div class="table-scroll" tabindex="0" role="region" aria-label="Project jobs comparison, scroll horizontally"><table class="jobs-comparison"><caption>Selected projects · no combined jobs total</caption><thead><tr><th scope="col">Project</th>${columns.map(([label])=>`<th scope="col">${label}</th>`).join('')}</tr></thead><tbody>${expansion.jobs_projects.map(id=>{const p=delivery.projects.find(p=>p.id===id),obs=typedRecords('project',id);return `<tr><th scope="row"><a href="${base}projects/#project-${esc(id)}">${esc(p.name)} ↗</a><p class="chart-footnote">${esc(p.location)}</p></th>${columns.map(([,kind])=>{const os=obs.filter(o=>kindOf(o)===kind);return `<td>${os.length?os.map(quantityEvidence).join(''):'<span class="sr-only">Not verified</span>'}</td>`;}).join('')}</tr>`;}).join('')}</tbody></table></div><p class="chart-footnote">Contractor FTEs are not headcounts. Peak construction and future operating roles cannot be added; broader indirect economic-impact claims are excluded.</p></section>`;
}
function capitalEvidence() {
 const ids=['hyperion-local-contracts-baseline','hyperion-investment-baseline','tesla-capex-q2-2026-baseline','nebius-msft-contract-base-baseline'];
 return `<section class="section" id="capital-evidence"><div class="section-top"><div><div class="eyebrow muted">CAPITAL / LOCAL VALUE</div><h2>Follow the dollars to their purpose.</h2></div></div><p class="section-intro">A regional investment plan, contracts awarded locally, company capital expenditures and a compute agreement answer different questions. None is a substitute for the others.</p><div class="capital-grid">${evidenceOf(ids).map(quantityEvidence).join('')}</div></section>`;
}
function extendWithExpansion() {
 if(layerOf(page)) {
  const section=page==='models'?agentProducts():featuredProjects(page);
  root.querySelector('.layer-nav').insertAdjacentHTML('afterend',section);
  if(page==='applications')root.querySelector('#named-projects').insertAdjacentHTML('afterend','<aside class="reading-note"><strong>Different driving exposure, different evidence.</strong><p>Tesla consumer FSD miles require driver supervision. Tesla Robotaxi supervision differs by city; Waymo rider-only mileage has a separate geography and period. We do not put these in a shared performance ranking. Optimus training builds are separate from Agility’s reported commercial tote handling.</p></aside>');
 } else if(page==='industry')root.querySelector('.industry-verdict').insertAdjacentHTML('afterend',projectJobs()+capitalEvidence());
 else if(page==='projects')root.insertAdjacentHTML('beforeend',`<section class="section"><h2>What we still need to verify.</h2><ul class="research-focus">${expansion.gaps.map(g=>`<li>${esc(g)}</li>`).join('')}</ul></section>`);
}
