'use strict';
let fabric;
const fabricSources=ids=>ids.map(id=>`${sourceLink(id)} · ${dateLabel(sourceOf(id).published)}`).join('<br>');

function componentMap(){
 return `<section class="section" id="component-map"><div class="section-top"><div><div class="eyebrow muted">THE DATACENTER SUPPLY CHAIN</div><h2>There’s a whole industry between the chips.</h2></div><a class="section-link" href="${base}companies/">All ${ecosystem.companies.length} company profiles ↗</a></div>
 <p class="section-intro">Follow compute, electrical signals and light through the AI factory. Each component has a job; the companies below provide different pieces of the system.</p>
 <div class="fabric-path" aria-label="Illustrative optical data path"><a href="#component-compute">Compute</a><span aria-hidden="true">→</span><a href="#component-signal">Signal processing</a><span aria-hidden="true">→</span><a href="#component-optics">Optical endpoint</a><span aria-hidden="true">→</span><a href="#component-fiber">Fiber link</a><span aria-hidden="true">→</span><a href="#component-switches">Network & destination</a></div>
 <p class="chart-footnote">Conceptual optical path, not a bill of materials or a mandatory sequence. Copper links and different optical architectures use different combinations of these functions.</p>
 <label for="fabric-search" class="eyebrow muted fabric-search-label">FIND A COMPONENT OR SUPPLIER</label><input class="search" id="fabric-search" type="search" placeholder="Try DSP, copper, CPO, Marvell, or fiber…"><p class="chart-footnote" id="fabric-count" aria-live="polite"></p><div class="fabric-grid" id="fabric-results"></div>
 <div class="section-top fabric-milestone-heading"><div><div class="eyebrow muted">OPTICAL TECHNOLOGY / DELIVERY STAGES</div><h2>Sampling is a step. Production is another.</h2></div></div><div class="fabric-milestones">${fabric.milestones.map(m=>`<article class="panel"><span class="pill">${esc(m.stage)}</span><h3>${esc(m.title)}</h3><p>${esc(m.summary)}</p><p class="chart-footnote">${fabricSources([m.source])}</p></article>`).join('')}</div>
 <p class="chart-footnote">Reviewed ${dateLabel(fabric.reviewed_at)}. Company disclosures retain attribution. ${esc(fabric.gaps[0])} ${esc(fabric.gaps[1])}</p></section>`;
}

function bindComponentMap(){
 const input=document.querySelector('#fabric-search');if(!input)return;
 const update=()=>{
  const q=input.value.trim().toLowerCase();
  const items=fabric.components.filter(c=>`${c.title} ${c.role} ${c.watch} ${c.companies.map(id=>companyOf(id).name).join(' ')}`.toLowerCase().includes(q));
  document.querySelector('#fabric-results').innerHTML=items.length?items.map(c=>`<article class="panel component-card" id="component-${esc(c.id)}"><h3>${esc(c.title)}</h3><p>${esc(c.role)}</p><div class="supplier-links">${c.companies.map(companyLink).join('')}</div><p class="component-watch"><strong>What we track</strong>${esc(c.watch)}</p><details><summary>Sources & dates</summary><p class="chart-footnote">${fabricSources(c.sources)}</p></details></article>`).join(''):'<p class="empty">No matching components. Try a company name or another capability.</p>';
  document.querySelector('#fabric-count').textContent=`${items.length} of ${fabric.components.length} component families`;
 };
 input.addEventListener('input',update);update();
 document.querySelectorAll('.fabric-path a').forEach(a=>a.addEventListener('click',()=>{input.value='';update();}));
}

function evidenceTile(id){
 const o=data.observations.find(v=>v.id===id),m=metricOf(o.metric);
 return `<article class="fabric-stat ${historicalStatus(o.status)?'':'planned'}"><span class="eyebrow">${esc(attributionLabel(o))}</span><strong>${esc(valueOf(o))}<small>${esc(m.unit)}</small></strong><h3>${esc(m.title)}</h3><p>${esc(o.period)}</p><p class="chart-footnote">${esc(m.scope)}</p><p class="chart-footnote">${sourceLink(o.source)} · Published ${dateLabel(sourceOf(o.source).published)} · Accessed ${dateLabel(o.retrieved_at)}</p></article>`;
}

function workforceSection(){
 return `<section class="section" id="electrical-work"><div class="section-top"><div><div class="eyebrow muted">BLUE-COLLAR WORK / POWERING THE BUILDOUT</div><h2>The people who make the factory work.</h2></div></div><p class="section-intro">Electricians, line crews, mechanical trades and equipment makers connect the grid to the rack. The opportunity reaches from construction sites into apprenticeships, maintenance and domestic manufacturing.</p>
 <div class="fabric-stats">${fabric.workforce_observations.map(evidenceTile).join('')}</div><p class="chart-footnote">Nonresidential specialty trades are included in construction. Projected openings include replacement needs. These figures cannot be added into an AI jobs total.</p>
 <div class="workforce-layout"><div class="panel">${chart(fabric.workforce_metrics[0])}</div><aside class="panel"><span class="eyebrow muted">ELECTRICAL INFRASTRUCTURE</span><h3>Follow the work and the builders.</h3><p>Generation and grid connections, transformers and distribution equipment, cable installation, cooling, commissioning and maintenance all belong in the research picture.</p><div class="supplier-links">${['eaton','quanta','emcor','schneider','ge-vernova','vertiv','corning'].map(companyLink).join('')}</div><p class="chart-footnote">Profiles explain company roles and reported revenue. Contracting revenue is not payroll or a measure of jobs created.</p></aside></div>
 <div class="workforce-notes">${fabric.workforce_notes.map(n=>`<article><h3>${esc(n.title)}</h3><p>${esc(n.summary)}</p><p class="chart-footnote">${fabricSources([n.source])}</p></article>`).join('')}</div></section>`;
}

function cleanEnergySection(){
 return `<section class="section" id="clean-energy-industry"><div class="section-top"><div><div class="eyebrow muted">GREEN ENERGY & ELECTRICAL MANUFACTURING</div><h2>Build the energy. Build the industry.</h2></div><a class="section-link" href="${base}projects/?layer=energy">Generation & grid projects ↗</a></div><p class="section-intro">Solar manufacturing investments build a domestic supply chain for clean power. Electrical equipment expands the ability to connect generation and new demand. Follow what is operating, what is ramping and what is still planned.</p>
 <div class="energy-case-grid">${fabric.energy_cases.map(c=>`<article class="panel energy-case"><span class="pill">${esc(c.stage)}</span><h3>${esc(c.name)}</h3><p>${esc(c.scope)}</p><div class="case-figures">${c.observations.map(evidenceTile).join('')}</div><details><summary>Project sources & dates</summary><p class="chart-footnote">${fabricSources(c.sources)}</p></details></article>`).join('')}</div><p class="chart-footnote">Solar module manufacturing capacity is not operating generation. Electrical equipment can serve renewable and other power sources. These selected investments are not a national clean-energy total or proof of AI-dedicated electricity supply.</p></section>`;
}

function extendWithFabric(){
 if(page==='infrastructure'||page==='chips'){
  const anchor=root.querySelector(page==='infrastructure'?'#ai-factories':'.layer-nav');
  anchor.insertAdjacentHTML('afterend',componentMap());bindComponentMap();
  root.querySelector('.page-hero').insertAdjacentHTML('beforeend',`<p class="fabric-shortcuts"><a class="section-link" href="#component-map">Explore components & suppliers ↓</a><a class="section-link" href="${base}industry/#electrical-work">Electrical jobs & investment ↗</a></p>`);
 }
 if(page==='industry'){
  root.querySelector('.industry-verdict').insertAdjacentHTML('afterend',workforceSection()+cleanEnergySection());
 }
 if(page==='energy')root.querySelector('.detail-layout').insertAdjacentHTML('afterend',cleanEnergySection());
 if(page==='companies')root.querySelector('.ecosystem-hero').insertAdjacentHTML('beforeend',`<p class="fabric-shortcuts"><a class="section-link" href="${base}infrastructure/#component-map">Explore the datacenter component map ↗</a></p>`);
}
