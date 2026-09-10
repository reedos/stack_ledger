// Real mobile emulation for the unified panel: touch input, device pixel ratio, tap-target size,
// no horizontal overflow, the merged Decisions feed, the live log collapsed on a phone, and the
// one-tap catalog flow (auto-validation state, the compact change table, the Publishing strip).
// Offline fixtures only; start requests are intercepted; no research is launched.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const {spawn}=require('node:child_process');
const path=require('node:path'),fs=require('node:fs'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
const shots=process.env.PANEL_SHOTS_DIR||path.resolve(__dirname,'..','.local/browser');
const child=spawn('python',['scripts/research_control.py','--ephemeral'],{cwd:root,windowsHide:true});

function makeState(){
  const finding={id:'discovery-'+'a'.repeat(24),layer:'energy',url:'https://example.org/primary-source',
    created_at:'2026-09-08T00:00:00Z',published_at:null,retrieved_at:'2026-09-08T00:00:00Z',
    status:'pending_review',proposal_hash:'a'.repeat(64),review_hash:'b'.repeat(64),
    finding:{kind:'project',subject:'Fixture geothermal project',claim:'Operator reports commissioning.',
      evidence:'The operator states the project is commissioning.',basis:'actual',why_track:'Check dependable power delivery.',next_question:'Verify grid-operator records.'}};
  const catalog={id:'catalog-'+'c'.repeat(24),title:'Fixture catalog package',author:'fixture researcher',created_at:'2026-09-09T00:00:00Z',
    status:'pending_review',display_status:'pending_review',proposal_hash:'c'.repeat(64),review_hash:'d'.repeat(64),
    auto_apply_eligible:false,auto_apply_reasons:['evidence example.org is not a registered rank <=2 source'],validation:null,publication_receipt:null,job:null,
    changes:[{target:'project',id:'fixture-project',before:null,after:{id:'fixture-project',name:'Fixture project',next_evidence:'Check the next dated disclosure.'}}],
    evidence:[{id:'fixture-source',url:'https://example.org/release',published_at:'2026-09-08',retrieved_at:'2026-09-08T00:00:00Z',summary:'Fixture evidence.',source_rank:3}]};
  // Deliverable: promoting a report ("Track this") is one tap, next to Retract; an already
  // promoted report shows queued state instead of the control.
  const trackableReport={id:'note-'+'t'.repeat(20),grade:'C',kind:'News report',layer:'infrastructure',
    title:'Fixture Co secures planning permission for a data center in Fixtureville',
    summary:'Fixture Co secured planning permission for a data center in Fixtureville.',
    outlet:'Fixture Wire',reported_on:'2026-09-09',date:'2026-09-09',about:[],
    quote:'Fixture Co said it secured planning permission.',confirmation:'unconfirmed'};
  const trackedReport={id:'note-'+'q'.repeat(20),grade:'C',kind:'News report',layer:'energy',
    title:'Already Tracked Co breaks ground on a site in Trackedville',
    summary:'Already Tracked Co is building a site in Trackedville.',
    outlet:'Fixture Wire',reported_on:'2026-09-08',date:'2026-09-08',about:[],
    quote:'Already Tracked Co confirmed the groundbreaking.',confirmation:'unconfirmed'};
  const promotions={[trackedReport.id]:{package_id:'catalog-'+'p'.repeat(24),status:'pending_review'}};
  return {finding,catalog,reports:[trackableReport,trackedReport],promotions};
}

async function mockPanel(page,state){
  await page.route('**/gpu',route=>{
    const now=Date.now();
    const samples=Array.from({length:30},(_,i)=>({timestamp_ms:now-(29-i)*2000,name:'Fixture GPU',utilization:20+i,temperature:40+i}));
    return route.fulfill({contentType:'application/json',body:JSON.stringify({latest:{...samples.at(-1),status:'live'},samples})});
  });
  await page.route('**/status',route=>route.fulfill({contentType:'application/json',body:JSON.stringify({active:false,launching:false,session:{}})}));
  await page.route('**/findings',route=>route.fulfill({contentType:'application/json',body:JSON.stringify(
    {findings:[state.finding],reviewer:'reedos',invalid_files:0,unreadable_events:0,catalog_packages:[state.catalog],handoffs:[],
     jobs:state.catalog.job?[state.catalog.job]:[]})}));
  await page.route('**/visuals',route=>route.fulfill({contentType:'application/json',body:JSON.stringify({proposals:[],reviewer:'reedos',assessment:null,invalid_files:0})}));
  await page.route('**/activity',route=>route.fulfill({contentType:'application/json',body:JSON.stringify(
    {policy_events:[],digests:[],unreadable_events:0,reviewer:'reedos',reports:state.reports,promotions:state.promotions})}));
  await page.route('**/report-promote',route=>{
    const body=route.request().postDataJSON();
    state.promotions={...state.promotions,[body.id]:{package_id:'catalog-'+'n'.repeat(24),status:'pending_review'}};
    return route.fulfill({contentType:'application/json',body:JSON.stringify({package_id:state.promotions[body.id].package_id,already_promoted:false,job:{status:'queued'},status:'queued'})});
  });
}

async function tapTargetSizes(page){
  return page.evaluate(()=>{
    const selectors=['.choices label','.toggle-chip','.select-chip','.toggle','select','button','.panel-tabs button'];
    const seen=new Set(),rows=[];
    for(const sel of selectors)for(const el of document.querySelectorAll(sel)){
      if(seen.has(el))continue;seen.add(el);
      const box=el.getBoundingClientRect();
      const style=getComputedStyle(el);
      if(style.display==='none'||style.visibility==='hidden'||box.width===0&&box.height===0)continue;
      rows.push({sel,text:(el.textContent||'').trim().slice(0,40),width:box.width,height:box.height});
    }
    return rows;
  });
}

(async()=>{
  let browser;
  try{
    const url=await new Promise((resolve,reject)=>{
      const timer=setTimeout(()=>reject(new Error('Control startup timeout')),10000);
      child.stdout.on('data',chunk=>{const match=chunk.toString().match(/http:\/\/127\.0\.0\.1:\d+\/[^\s]+/);if(match){clearTimeout(timer);resolve(match[0]);}});
      child.once('error',reject);child.once('exit',code=>{clearTimeout(timer);reject(new Error('Control exited '+code));});
    });
    browser=await chromium.launch({headless:true});
    fs.mkdirSync(shots,{recursive:true});

    // Real mobile emulation, as an actual phone would present the page (not merely a narrow desktop viewport).
    const phone=await browser.newContext({viewport:{width:390,height:844},isMobile:true,hasTouch:true,deviceScaleFactor:3});
    const page=await phone.newPage();
    const errors=[];page.on('pageerror',e=>errors.push(e.message));
    const state=makeState();
    // The server auto-enqueues validation for a pending package; simulate that job already running
    // (deliverable 2/7): no Validate button, no approve button, just a status line, until it finishes.
    state.catalog.job={id:'job-validate-1',rid:state.catalog.id,kind:'validate',status:'running',step:'Building and testing the isolated preview…',error:null,result:null};
    await mockPanel(page,state);
    await page.goto(url);
    await page.waitForFunction(()=>document.querySelector('#connection').textContent==='Connected locally');

    // Decisions is the default-visible tab; the merged feed carries both the pending finding and the pending catalog package.
    await page.locator('#decision-feed .finding-card').first().waitFor();
    assert.equal(await page.locator('#decision-feed .finding-card').count(),2,'Decisions feed merges the pending finding and catalog package');
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),'no horizontal overflow on the Decisions tab at 390px');

    // A pending card without a finished validation shows "Validating..." and no approve/validate button.
    const catalogCard=page.locator('#decision-feed article').filter({hasText:'Fixture catalog package'});
    await catalogCard.waitFor();
    assert.match(await catalogCard.innerText(),/Validating…/);
    assert.equal(await catalogCard.getByRole('button',{name:'Approve and publish',exact:true}).count(),0,'no approve button while validation is in flight');
    assert.equal(await catalogCard.getByRole('button',{name:'Validate preview',exact:true}).count(),0,'no manual re-run button while a validation job is already queued/running');

    // The job finishes: a validated card shows the compact change table and no Validate button.
    state.catalog.job=null;
    state.catalog.validation={passed:true,checks:[],proposal_hash:state.catalog.proposal_hash};
    await page.tap('#refresh-findings');
    await catalogCard.locator('.change-table').waitFor();
    assert.match(await catalogCard.locator('.change-table').innerText(),/next evidence/);
    assert.equal(await catalogCard.getByRole('button',{name:'Validate preview',exact:true}).count(),0,'Validate is hidden once a passing validation exists');
    const approveButton=catalogCard.getByRole('button',{name:'Approve and publish',exact:true});
    await approveButton.waitFor();
    assert.equal(await approveButton.isDisabled(),false);
    const approveBox=await approveButton.boundingBox();
    assert.ok(approveBox.height>=48,'primary action is at least 48px tall: '+approveBox.height);
    const fullWidth=await approveButton.evaluate(el=>el.offsetWidth>=el.parentElement.clientWidth-1);
    assert.ok(fullWidth,'primary action spans the full width of its form, not just part of the card');
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),'no horizontal overflow once the change table and one-tap form render');

    await page.tap('#decisions-tab');
    await page.screenshot({path:path.join(shots,'panel-v2-decisions-390.png'),fullPage:false});

    // Open the history fold and the evidence detail so their touch targets (chips, select) are measured too.
    await page.tap('.decision-history > summary');
    await page.locator('#catalog-packages').waitFor();

    await page.tap('#session-tab');
    await page.locator('#session-panel').waitFor();
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),'no horizontal overflow on the Session tab at 390px');
    // The live batch output starts collapsed on a phone; GPU charts start hidden behind a toggle.
    assert.equal(await page.locator('#log-details').getAttribute('open'),null,'live log is collapsed by default on a phone');
    const gpuChartsBox=await page.locator('#gpu-charts').boundingBox();
    assert.ok(!gpuChartsBox||gpuChartsBox.height===0,'GPU charts stay hidden until the operator asks for them on a phone');
    assert.ok(await page.locator('#gpu-toggle').isVisible(),'a toggle is offered to reveal GPU charts on a phone');
    await page.tap('#gpu-toggle');
    await page.waitForFunction(()=>document.getElementById('gpu-charts').classList.contains('shown'));
    await page.screenshot({path:path.join(shots,'panel-v2-session-390.png'),fullPage:false});

    const sizes=await tapTargetSizes(page);
    assert.ok(sizes.length>10,'collected a meaningful sample of interactive elements: '+sizes.length);
    const undersized=sizes.filter(r=>r.height<44-0.5);
    assert.equal(undersized.length,0,'every interactive element is >=44px tall: '+JSON.stringify(undersized));

    // Activity tab: promoting a report is one tap ("Track this"), next to Retract. An
    // already-promoted report shows queued state instead of the control.
    await page.tap('#activity-tab');
    await page.locator('#activity-panel').waitFor();
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),'no horizontal overflow on the Activity tab at 390px');
    const trackableCard=page.locator('#activity-log .finding-card').filter({hasText:'Fixtureville'});
    await trackableCard.waitFor();
    const trackedCard=page.locator('#activity-log .finding-card').filter({hasText:'Trackedville'});
    assert.equal(await trackedCard.getByRole('button',{name:'Track this'}).count(),0,'an already-promoted report has no Track this control');
    assert.match(await trackedCard.innerText(),/Queued for review/);
    const trackButton=trackableCard.getByRole('button',{name:'Track this'});
    const trackBox=await trackButton.boundingBox();
    assert.ok(trackBox.height>=44,'Track this is at least 44px tall: '+trackBox.height);
    await page.screenshot({path:path.join(shots,'panel-v2-activity-390.png'),fullPage:false});
    await trackButton.tap();
    await trackButton.waitFor({state:'detached'});
    assert.match(await trackableCard.innerText(),/Queued for review/,'one tap replaces the control with the queued state');
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),'no horizontal overflow once a report is queued');
    await page.screenshot({path:path.join(shots,'panel-v2-activity-queued-390.png'),fullPage:false});

    // Back to Decisions: tap Approve and publish -- one tap records the approval, then queues
    // publication in the background. The card leaves the feed and shows up in the Publishing strip.
    await page.tap('#decisions-tab');
    await catalogCard.waitFor();
    let decisionBody,publishBody;
    await page.route('**/catalog-review',route=>{decisionBody=route.request().postDataJSON();state.catalog.status='approved';state.catalog.display_status='approved';return route.fulfill({contentType:'application/json',body:'{"status":"approved","published":false}'});});
    await page.route('**/catalog-publish',route=>{publishBody=route.request().postDataJSON();state.catalog.job={id:'job-publish-1',rid:state.catalog.id,kind:'publish',status:'running',step:'Publishing: validating, building, committing and pushing…',error:null,result:null};return route.fulfill({contentType:'application/json',body:JSON.stringify({job:state.catalog.job,status:'running'})});});
    await catalogCard.locator('.one-tap-form input[type=checkbox]').tap();
    await catalogCard.getByRole('button',{name:'Approve and publish',exact:true}).tap();
    await page.waitForFunction(()=>document.querySelectorAll('#decision-feed .finding-card').length===1,{},{timeout:8000});
    assert.equal(decisionBody.decision,'approved');assert.equal(decisionBody.rationale,state.catalog.title,'reason is pre-filled with the package title');
    assert.equal(publishBody.confirmed,true);
    await page.locator('#publishing-strip .strip-item').waitFor();
    assert.match(await page.locator('#publishing-strip').innerText(),/Fixture catalog package/);
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),'no horizontal overflow with the Publishing strip visible');

    assert.deepEqual(errors,[],'no console errors under mobile emulation');
    await phone.close();

    // Desktop-width companions of the same two tabs, for a direct visual comparison.
    const desktop=await browser.newContext({viewport:{width:1280,height:900}});
    const dpage=await desktop.newPage();
    await mockPanel(dpage,makeState());
    await dpage.goto(url);
    await dpage.waitForFunction(()=>document.querySelector('#connection').textContent==='Connected locally');
    await dpage.locator('#decision-feed .finding-card').first().waitFor();
    await dpage.screenshot({path:path.join(shots,'panel-v2-decisions-1280.png'),fullPage:false});
    await dpage.click('#session-tab');
    await dpage.locator('#session-panel').waitFor();
    assert.equal(await dpage.locator('#log-details').getAttribute('open'),'','live log defaults open on desktop');
    await dpage.screenshot({path:path.join(shots,'panel-v2-session-1280.png'),fullPage:false});
    await dpage.click('#activity-tab');
    await dpage.locator('#activity-log .finding-card').first().waitFor();
    await dpage.screenshot({path:path.join(shots,'panel-v2-activity-1280.png'),fullPage:false});
    await desktop.close();

    console.log('Research control mobile passed: real touch emulation, no overflow, 44px tap targets, merged Decisions feed, auto-validation state, the change table, one-tap approve-and-publish into the Publishing strip, one-tap report promotion and its queued state, log collapsed on phone. Screenshots in '+shots);
  }finally{
    if(browser)await browser.close();
    child.kill();
  }
})().catch(error=>{console.error(error);process.exitCode=1;});
