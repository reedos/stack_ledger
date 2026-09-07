'use strict';
let ecosystem;
const companyOf = id => ecosystem.companies.find(c => c.id === id);
const latestRevenue = c => records(c.revenue_metric).filter(o => o.status === 'observation').at(-1);
const companyLink = id => `<a href="${base}companies/#${esc(id)}">${esc(companyOf(id).name)}</a>`;
const researchStamp = () => `<p class="chart-footnote">Company roles, projects and jobs reviewed ${dateLabel(ecosystem.reviewed_at)}. Revenue and capacity observations retain their own periods and access dates. Representative coverage; not a complete industry census.</p>`;

function companyCard(c) {
 const o=latestRevenue(c), m=metricOf(c.revenue_metric), accent=layerOf(c.layers[0]).color;
 return `<article class="company-card" id="${esc(c.id)}" style="--accent:${accent}">
  <div class="company-heading"><span class="company-monogram" aria-hidden="true">${esc(c.name.replace('NextEra','NE').split(/\s+/).map(s=>s[0]).join('').slice(0,2))}</span><h3>${esc(c.name)}</h3></div>
  <div class="company-layers">${c.layers.map(id=>`<a href="${base}${id}/" style="--tag:${layerOf(id).color}">${layerOf(id).name}</a>`).join('')}</div>
  <p class="company-role">${esc(c.role)}</p>
  ${c.role_sources?`<details class="company-role-sources"><summary>Sources for company role</summary><div>${c.role_sources.map(id=>`${sourceLink(id)} · ${dateLabel(sourceOf(id).published)}`).join('<br>')}</div></details>`:''}
  ${c.revenue_kind==='unavailable'?`<div class="company-revenue unavailable"><span class="eyebrow">REVENUE COVERAGE GAP</span><strong>Not yet verified</strong><p>No sourced revenue record in this edition. This is not zero revenue; funding and valuation are not substitutes.</p></div><div class="company-source">${sourceLink(c.source)}<span>Company role source · ${dateLabel(sourceOf(c.source).published)}</span></div>`:`<div class="company-revenue ${c.revenue_kind==='run-rate'?'run-rate':''}"><span class="eyebrow">${c.revenue_kind==='run-rate'?'ANNUALIZED RUN RATE':'REPORTED ANNUAL REVENUE'}</span><strong>${esc(valueOf(o))}<small>${esc(m.unit)}</small></strong><p>${esc(o.period)}</p></div>
  <p class="company-scope">${esc(m.scope)}</p><p class="chart-footnote">${esc(o.note || m.note)}</p>
  <div class="company-source">${sourceLink(o.source)}<span>Published ${dateLabel(sourceOf(o.source).published)} · Accessed ${dateLabel(o.retrieved_at)} · ${o.method==='automated'?'Automated':'Curated'}</span></div>`}
 </article>`;
}

function companySection(layer) {
 const cs=ecosystem.companies.filter(c=>c.layers.includes(layer));
 return `<section class="section" id="companies"><div class="section-top"><div><div class="eyebrow muted">THE BUILDERS</div><h2>Who makes this layer possible?</h2></div><a class="section-link" href="${base}companies/?layer=${layer}">Explore ${cs.length} companies ↗</a></div><p class="section-intro">See what each company contributes and the scale of its business. Revenue covers the scope shown on each card; it is not automatically revenue from AI.</p><div class="company-grid">${cs.slice(0,3).map(companyCard).join('')}</div></section>`;
}

function companiesPage() {
 root.innerHTML=`<section class="page-hero ecosystem-hero"><div class="eyebrow">THE COMPANIES BEHIND THE STACK</div><h1>Meet the builders.</h1><p>From electricity to useful intelligence: who contributes, what they provide, and the businesses taking shape across five connected layers.</p>${researchStamp()}</section>
 <div class="ecosystem-map" aria-label="Explore companies by layer">${data.layers.map(l=>`<a href="?layer=${l.id}" data-company-layer="${l.id}" style="--accent:${l.color}"><span class="eyebrow">${l.number}</span><strong>${l.name}</strong><span>${ecosystem.companies.filter(c=>c.layers.includes(l.id)).length} companies <b aria-hidden="true">↗</b></span></a>`).join('')}</div>
 <aside class="reading-note"><strong>Read revenue in context.</strong><p>Annual revenue, segment revenue and annualized run rates measure different things. Fiscal years differ; currencies stay as reported. A company can serve several layers, and suppliers sell to each other. Adding these revenues would double-count the supply chain and would not measure AI’s contribution to GDP.</p></aside>
 <div class="directory-tools"><label for="company-search" class="sr-only">Search companies or capabilities</label><input type="search" class="search" id="company-search" placeholder="Search companies or capabilities: memory, turbines, Claude…"><label for="revenue-basis">Revenue basis <select class="select-control" id="revenue-basis"><option value="all">All disclosures</option><option value="annual">Annual revenue only</option><option value="run-rate">Run rates only</option><option value="unavailable">Revenue not yet verified</option></select></label></div>
 <div class="filters" role="group" aria-label="Filter companies by layer"><button class="filter active" data-company-filter="all" aria-pressed="true">All layers</button>${data.layers.map(l=>`<button class="filter" data-company-filter="${l.id}" aria-pressed="false">${l.name}</button>`).join('')}</div><p class="chart-footnote" id="company-count" aria-live="polite"></p><div id="company-results" class="company-grid"></div>
 <section class="manifesto"><div><div class="eyebrow muted">FOLLOW THE PHYSICAL BUILDOUT</div><h2>From business growth to real-world capacity.</h2><p>Explore operating factories, production plans and evidence on jobs.</p></div><a class="button" href="${base}industry/">Jobs & industry ↗</a></section><p class="chart-footnote"><a class="source-inline" href="${base}data/ecosystem.json">Company and industry metadata ↓</a> · Financial observations are available in the <a class="source-inline" href="${base}ledger/">ledger and CSV export</a>.</p>`;
 let selected=new URLSearchParams(location.search).get('layer') || 'all';
 if(!layerOf(selected))selected='all';
 const update=()=>{
  const q=document.querySelector('#company-search').value.trim().toLowerCase(),basis=document.querySelector('#revenue-basis').value;
  const cs=ecosystem.companies.filter(c=>(selected==='all'||c.layers.includes(selected))&&(basis==='all'||c.revenue_kind===basis)&&`${c.name} ${c.role}`.toLowerCase().includes(q));
  document.querySelector('#company-results').innerHTML=cs.length?cs.map(companyCard).join(''):'<p class="empty">No companies match these filters.</p>';
  document.querySelector('#company-count').textContent=`${cs.length} of ${ecosystem.companies.length} companies · No revenue totals across layers`;
  document.querySelectorAll('[data-company-filter]').forEach(b=>{b.classList.toggle('active',b.dataset.companyFilter===selected);b.setAttribute('aria-pressed',String(b.dataset.companyFilter===selected));});
 };
 const choose=id=>{selected=id;history.replaceState(null,'',`${location.pathname}${id==='all'?'':`?layer=${id}`}`);update();};
 document.querySelectorAll('[data-company-filter]').forEach(b=>b.addEventListener('click',()=>choose(b.dataset.companyFilter)));
 document.querySelectorAll('[data-company-layer]').forEach(a=>a.addEventListener('click',e=>{e.preventDefault();choose(a.dataset.companyLayer);document.querySelector('#company-search').scrollIntoView({block:'center'});}));
 document.querySelector('#company-search').addEventListener('input',update);
 document.querySelector('#revenue-basis').addEventListener('change',update);update();
}

function supplyChain() {
 return `<section class="section" id="supply-chain"><div class="section-top"><div><div class="eyebrow muted">INSIDE THE CHIPS LAYER</div><h2>A design becomes a device.</h2></div></div><p class="section-intro">These are distinct capabilities in a connected supply chain. Memory and equipment support fabrication and assembly; they are not simply additional steps after the chip is finished.</p><div class="supply-chain">${ecosystem.supply_chain.map((s,i)=>`<article class="supply-step"><span class="step-number">0${i+1}</span><h3>${esc(s.title)}</h3><p>${esc(s.role)}</p><div class="supplier-links">${s.companies.map(companyLink).join('')}</div><p class="chart-footnote">${esc(s.note)}</p></article>`).join('')}</div><p class="chart-footnote">Representative companies, with source-linked profiles. Additional design IP, EDA, materials, assembly and test suppliers remain a coverage priority.</p></section>`;
}

function capacitySection() {
 return `<section class="section" id="capacity"><div class="section-top"><div><div class="eyebrow muted">CAPACITY / NOW & NEXT</div><h2>More silicon. More ways to measure it.</h2></div></div><p class="section-intro">The latest measured baseline and each forecast stay separate. TSMC’s annual equivalent-wafer capacity, global advanced-node monthly capacity and global memory capacity have different scopes and cannot be added.</p><div class="capacity-grid">${ecosystem.capacity_metrics.map(id=>`<article class="panel">${chart(id)}</article>`).join('')}<aside class="panel capacity-explainer"><div class="eyebrow">WHAT WAFERS DON’T TELL US</div><h3>Delivered compute depends on the whole system.</h3><p>Process mix, die size, yield, HBM, packaging and networking determine how many working accelerators can ship. Power, cooling and utilization determine how much useful compute they deliver.</p><p>There is no defensible conversion from these wafer figures to a single global count of AI GPUs. Public HBM and packaging capacity series remain a research gap.</p><a class="section-link" href="${base}industry/#projects">See factory milestones ↗</a></aside></div></section>`;
}

function industryPage() {
 const e=ecosystem.employment,max=Math.max(...e.series.map(s=>Math.abs(s.value)));
 root.innerHTML=`<section class="page-hero ecosystem-hero"><div class="eyebrow">JOBS, FACTORIES & THE LONG VIEW</div><h1>Intelligence has<br>a physical footprint.</h1><p>Reindustrialization means building lasting productive capacity. Follow power projects, chip factories and AI infrastructure into local supplier activity, skilled work and stronger communities—and test that ambition against what is actually delivered.</p>${researchStamp()}</section>
 <aside class="industry-verdict"><span class="eyebrow">OUR READING OF THE EVIDENCE</span><h2>Industrial rebuilding is visible.</h2><p>${esc(ecosystem.interpretation)}</p><p class="chart-footnote">Stack Ledger interpretation, based on the project disclosures and BLS release below. Company plans retain company attribution.</p></aside>
 ${supplyChain()}${capacitySection()}
 <section class="section" id="projects"><div class="section-top"><div><div class="eyebrow muted">FACTORY MILESTONES</div><h2>From plans to production.</h2></div></div><div class="project-grid">${ecosystem.projects.map(p=>`<article class="project-card"><span class="stage ${p.stage==='Operating'?'operating':''}">${esc(p.stage)}</span><h3>${esc(p.title)}</h3><strong>${esc(p.period)}</strong><p>${esc(p.detail)}</p>${sourceLink(p.source)}<p class="chart-footnote">Source published ${dateLabel(sourceOf(p.source).published)}</p></article>`).join('')}</div><p class="chart-footnote">Milestones reflect the cited disclosures, reviewed ${dateLabel(ecosystem.reviewed_at)}. A production target is not evidence that a fab is operating.</p></section>
 <section class="section" id="jobs"><div class="section-top"><div><div class="eyebrow muted">WORK & OPPORTUNITY</div><h2>What jobs are being created?</h2></div></div><p class="section-intro">Construction is already putting people to work; factory operation can sustain skilled roles over a longer horizon. These examples use different definitions and timelines, so we show them individually.</p><div class="jobs-grid">${ecosystem.jobs.map(j=>`<article class="job-card"><span class="eyebrow muted">${esc(j.status)}</span><strong class="jobs-value">${esc(valueOf(j))}</strong><h3>${esc(j.title)}</h3><p>${esc(j.period)}</p><p class="chart-footnote">${esc(j.scope)}</p>${sourceLink(j.source)}</article>`).join('')}</div><aside class="reading-note"><strong>No combined “AI jobs” total.</strong><p>Direct operating jobs, peak construction workers and modeled regional impacts overlap and have different time horizons. Announced positions are not verified hires. Net job creation also requires evidence on displacement and jobs that would have existed without these projects.</p></aside></section>
 <section class="section"><div class="section-top"><div><div class="eyebrow muted">THE WIDER LABOR MARKET</div><h2>Growth is uneven across sectors.</h2></div></div><div class="employment-layout"><figure class="panel employment-chart"><figcaption><h3>U.S. payroll change · ${esc(e.period)}</h3><p class="chart-footnote">${esc(e.basis)}</p></figcaption><div class="employment-scale"><span>Decrease</span><span>0</span><span>Increase</span></div>${e.series.map(s=>`<div class="employment-row"><div><strong>${esc(s.name)}</strong><span>${s.value>0?'+':''}${number(s.value)} jobs</span></div><div class="diverging-track" aria-hidden="true"><i class="${s.value<0?'negative':'positive'}" style="width:${Math.abs(s.value)/max*50}%"></i></div></div>`).join('')}<details class="data-details"><summary>View data table</summary><div class="table-scroll"><table><thead><tr><th>Sector</th><th>Monthly change (jobs)</th><th>Period</th></tr></thead><tbody>${e.series.map(s=>`<tr><td>${esc(s.name)}</td><td>${s.value>0?'+':''}${number(s.value)}</td><td>${esc(e.period)}</td></tr>`).join('')}</tbody></table></div></details><p class="chart-footnote">${sourceLink(e.source)} · Published ${dateLabel(sourceOf(e.source).published)}. ${esc(e.note)}</p></figure><aside class="panel"><h3>What would establish a lasting shift?</h3><p class="section-intro">Track sustained manufacturing output, domestic value added, supplier activity and realized employment across several years. Pair investment plans with commissioning and utilization.</p><ul class="research-focus">${ecosystem.gaps.map(g=>`<li>${esc(g)}</li>`).join('')}</ul></aside></div></section>`;
}

function extendWithEcosystem() {
 if(page==='home'){
  const section=`<section class="ecosystem-invitation"><div><span class="eyebrow">MEET THE BUILDERS</span><h2>Who’s building the next era?</h2><p>${ecosystem.companies.length} companies. Five connected layers. Explore their contributions, reported revenue, factory capacity and jobs.</p></div><div><a class="button" href="${base}companies/">Explore companies ↗</a><a class="button outline" href="${base}industry/">Jobs & industry ↗</a></div></section>`;
  const target=root.querySelector('.manifesto');if(target)target.insertAdjacentHTML('beforebegin',section);else root.insertAdjacentHTML('beforeend',section);
 } else if(layerOf(page)) {
  root.insertAdjacentHTML('beforeend',companySection(page)+(page==='chips'?supplyChain()+capacitySection():''));
 }
}
