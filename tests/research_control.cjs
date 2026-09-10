// Offline UI acceptance for the unified desktop/tailnet panel. Start requests are intercepted; no research is launched.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const {spawn}=require('node:child_process');
const path=require('node:path'),fs=require('node:fs'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
const savedURL=path.join(root,'.local/research-control-url.txt');
const previousURL=fs.existsSync(savedURL)?fs.readFileSync(savedURL,'utf8'):null;
const child=spawn('python',['scripts/research_control.py','--ephemeral'],{cwd:root,windowsHide:true});
(async()=>{
 let browser;
 try{
  const url=await new Promise((resolve,reject)=>{
   const timer=setTimeout(()=>reject(new Error('Control startup timeout')),10000);
   child.stdout.on('data',chunk=>{const match=chunk.toString().match(/http:\/\/127\.0\.0\.1:\d+\/[^\s]+/);if(match){clearTimeout(timer);resolve(match[0]);}});
   child.once('error',reject);child.once('exit',code=>{clearTimeout(timer);reject(new Error('Control exited '+code));});
  });
  browser=await chromium.launch({headless:true});
  assert.equal(fs.existsSync(savedURL)?fs.readFileSync(savedURL,'utf8'):null,previousURL,'UI tests must not replace the live panel URL');

  // Stale-server fallback: Decisions is the default-visible tab, so a script that fails to load must be
  // caught by the timeout watcher (not just a click handler) and explained rather than left blank.
  const stale=await browser.newPage();
  await stale.route('**/reviews.js',route=>route.fulfill({status:404,contentType:'application/json',body:'{}'}));
  await stale.goto(url);
  await stale.waitForFunction(()=>document.querySelector('#review-message').textContent.includes('Decisions could not load'),{timeout:6000});
  await stale.locator('#session-tab').click();await stale.locator('#session-panel').waitFor();
  await stale.unroute('**/reviews.js');
  await stale.route('**/findings',route=>route.fulfill({status:404,contentType:'application/json',body:'{}'}));
  await stale.reload();
  await stale.waitForFunction(()=>document.querySelector('#review-message').textContent.includes('predates review findings'));
  await stale.close();

  const page=await browser.newPage({viewport:{width:1440,height:1200}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  let unavailable=false;
  await page.route('**/gpu',route=>{
   const now=Date.now();
   const samples=Array.from({length:120},(_,i)=>({timestamp_ms:now-(119-i)*2000,name:'Fixture GPU',utilization:i===70?null:30+(i%40),temperature:i===70?null:45+i%12}));
   const latest={...samples.at(-1),status:unavailable?'unavailable':'live',utilization:unavailable?null:64,temperature:unavailable?null:56};
   samples[samples.length-1]=latest;
   return route.fulfill({contentType:'application/json',body:JSON.stringify({latest,samples})});
  });
  let reviewed=false,reviewRequest;
  const finding={id:'discovery-'+'a'.repeat(24),layer:'energy',url:'https://example.org/primary-source',
    created_at:'2026-09-08T00:00:00Z',published_at:null,retrieved_at:'2026-09-08T00:00:00Z',
    status:'pending_review',proposal_hash:'a'.repeat(64),review_hash:'b'.repeat(64),
    finding:{kind:'project',subject:'Fixture geothermal project',claim:'Operator reports commissioning. <img src=x onerror=alert(1)>',
      evidence:'The operator states the project is commissioning.',basis:'actual',why_track:'Check dependable power delivery.',next_question:'Verify grid-operator records.'}};
  let catalogStatus='pending_review',previewed=false,catalogJob=null,decisionBody,publishBody;
  // Deliverable: promoting a report is one tap ("Track this"), next to Retract. An
  // already-promoted report shows queued state instead of the control.
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
  let promotions={[trackedReport.id]:{package_id:'catalog-'+'p'.repeat(24),status:'pending_review'}},promoteBody;
  const catalog={id:'catalog-'+'c'.repeat(24),title:'Fixture catalog package',author:'fixture researcher',created_at:'2026-09-09T00:00:00Z',
    proposal_hash:'c'.repeat(64),review_hash:'d'.repeat(64),auto_apply_eligible:false,auto_apply_reasons:['evidence example.org is not a registered rank <=2 source'],
    changes:[{target:'project',id:'fixture-project',before:null,after:{id:'fixture-project',name:'<img src=x onerror=alert(1)>',next_evidence:'x'.repeat(400)}}],
    evidence:[{id:'fixture-source',url:'javascript:alert(1)',published_at:null,retrieved_at:'2026-09-08T00:00:00Z',summary:'Fixture evidence.',source_rank:3}]};
  async function findingsPayload(){
    return {findings:[{...finding,status:reviewed?'investigate':'pending_review'}],reviewer:'reedos',invalid_files:0,unreadable_events:0,
      catalog_packages:[{...catalog,status:catalogStatus,display_status:catalogStatus,validation:previewed?{passed:true,checks:[],proposal_hash:catalog.proposal_hash}:null,publication_receipt:null,job:catalogJob}],
      handoffs:[],jobs:catalogJob?[catalogJob]:[]};
  }
  await page.route('**/findings',async route=>route.fulfill({contentType:'application/json',body:JSON.stringify(await findingsPayload())}));
  await page.route('**/visuals',route=>route.fulfill({contentType:'application/json',body:JSON.stringify({proposals:[],reviewer:'reedos',assessment:null,invalid_files:0})}));
  await page.route('**/activity',route=>route.fulfill({contentType:'application/json',body:JSON.stringify(
    {policy_events:[],digests:[],unreadable_events:0,reviewer:'reedos',reports:[trackableReport,trackedReport],promotions})}));
  await page.route('**/report-promote',route=>{
    promoteBody=route.request().postDataJSON();
    promotions={...promotions,[promoteBody.id]:{package_id:'catalog-'+'n'.repeat(24),status:'pending_review'}};
    return route.fulfill({contentType:'application/json',body:JSON.stringify({package_id:promotions[promoteBody.id].package_id,already_promoted:false,job:{status:'queued'},status:'queued'})});
  });
  await page.route('**/review',route=>{reviewRequest=route.request().postDataJSON();reviewed=true;return route.fulfill({contentType:'application/json',body:'{"saved":true,"reviewer":"reedos","status":"investigate","published":false}'});});
  await page.route('**/catalog-preview',route=>{previewed=true;catalogJob={id:'job-validate-1',rid:catalog.id,kind:'validate',status:'done',step:'Done',error:null,result:{passed:true}};return route.fulfill({contentType:'application/json',body:JSON.stringify({job:catalogJob,status:'done'})});});
  await page.route('**/catalog-review',route=>{decisionBody=route.request().postDataJSON();catalogStatus='approved';return route.fulfill({contentType:'application/json',body:'{"status":"approved","published":false}'});});
  await page.route('**/catalog-publish',route=>{publishBody=route.request().postDataJSON();catalogJob={id:'job-publish-1',rid:catalog.id,kind:'publish',status:'running',step:'Publishing: validating, building, committing and pushing…',error:null,result:null};return route.fulfill({contentType:'application/json',body:JSON.stringify({job:catalogJob,status:'running'})});});

  await page.goto(url);await page.waitForFunction(()=>document.querySelector('#connection').textContent==='Connected locally');
  // Decisions is the default-visible tab; both the finding and the catalog package are pending, so both
  // land in the merged, ranked #decision-feed without any click.
  await page.locator('#decisions-panel').waitFor();
  assert.equal(await page.locator('#session-panel').isHidden(),true);
  await page.locator('#decision-feed .finding-card').first().waitFor();
  assert.equal(await page.locator('#decision-feed .finding-card').count(),2,'catalog + finding both pending');
  assert.equal(await page.locator('#decision-feed img,#decision-feed a[href^="javascript:"]').count(),0,'no unsafe HTML from source-controlled text');
  assert.match(await page.locator('#decision-feed').innerText(),/Source published: unknown/);
  assert.match(await page.locator('#decision-feed').innerText(),/Auto-apply eligible: No/);
  await page.locator('#decision-feed details summary',{hasText:'Evidence: fixture-source'}).click();
  assert.match(await page.locator('#decision-feed').innerText(),/Registered source rank: 3/);
  await page.locator('#decision-feed details summary',{hasText:'Evidence: fixture-source'}).click();

  fs.mkdirSync(path.join(root,'.local/browser'),{recursive:true});
  for(const width of [1440,390]){
    await page.setViewportSize({width,height:1100});
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    await page.screenshot({path:path.join(root,'.local/browser',`review-findings-${width}.png`),fullPage:true});
  }
  await page.setViewportSize({width:1440,height:1200});

  // Record the finding decision from the feed card.
  const findingCard=page.locator('#decision-feed .finding-card').filter({hasText:'Fixture geothermal project'});
  await findingCard.locator('.finding-review button').click();assert.equal(reviewRequest,undefined);
  await findingCard.locator('.finding-review textarea').fill('Verify the grid-operator record before adoption.');
  await findingCard.locator('.finding-review input[type=checkbox]').check();
  await findingCard.locator('.finding-review button').click();
  await page.waitForFunction(()=>document.querySelector('#review-message').textContent.includes('Nothing published'));
  assert.equal(reviewRequest.confirmed,true);assert.equal(reviewRequest.proposal_hash,finding.proposal_hash);
  // Investigated findings are no longer pending, so only the catalog card remains in the feed.
  assert.equal(await page.locator('#decision-feed .finding-card').count(),1);

  // Catalog workflow through the feed card: the compact change table is visible immediately (no
  // hunting for the changed graphic), validate, then one tap to approve and publish.
  const catalogCard=page.locator('#decision-feed article').first();await catalogCard.waitFor();
  assert.equal(await catalogCard.locator('img,a[href^="javascript:"]').count(),0);
  await catalogCard.locator('.change-table').waitFor();
  assert.match(await catalogCard.locator('.change-table').innerText(),/next evidence/);
  assert.equal(await catalogCard.getByRole('button',{name:'Approve and publish',exact:true}).isDisabled(),true,'not validated yet, so publication is not enabled');
  await catalogCard.getByRole('button',{name:'Validate preview',exact:true}).click();
  await catalogCard.locator('.one-tap-form input[type=checkbox]').check();
  await catalogCard.getByRole('button',{name:'Approve and publish',exact:true}).click();assert.equal(publishBody,undefined);
  await page.waitForFunction(()=>document.querySelector('#review-message').textContent.includes('Publishing strip'));
  assert.equal(decisionBody.decision,'approved');assert.equal(decisionBody.rationale,catalog.title,'reason field is pre-filled with the package title');
  assert.equal(publishBody.confirmed,true);
  await page.waitForFunction(()=>document.querySelectorAll('#decision-feed .finding-card').length===0);
  assert.match(await page.locator('#decision-feed').innerText(),/Nothing needs a decision/);

  // Approved and queued, not yet applied: the card leaves the feed and the Publishing strip picks it up.
  await page.locator('#publishing-strip .strip-item').waitFor();
  assert.match(await page.locator('#publishing-strip').innerText(),/Fixture catalog package/);
  assert.match(await page.locator('#publishing-strip').innerText(),/Publishing: validating, building/);

  // History fold: the approved package and the investigated finding are still browsable, collapsed by default.
  assert.equal(await page.locator('.decision-history').getAttribute('open'),null);
  await page.locator('.decision-history').locator(':scope > summary').click();
  await page.locator('#review-status').selectOption('investigate');
  assert.equal(await page.locator('.finding-card').filter({hasText:'Fixture geothermal project'}).count(),1);
  await page.locator('.decision-history').locator(':scope > summary').click();

  // Activity tab is a read-only automated-events log, distinct from Decisions -- except for
  // Track this, the one tap that drafts a private catalog package from a report.
  await page.locator('#activity-tab').click();await page.locator('#activity-panel').waitFor();
  await page.waitForFunction(()=>document.querySelector('#activity-panel').innerText.includes('No automatic approvals'));
  const trackableCard=page.locator('#activity-log .finding-card').filter({hasText:'Fixtureville'});
  await trackableCard.waitFor();
  const trackedCard=page.locator('#activity-log .finding-card').filter({hasText:'Trackedville'});
  // Already promoted: shows queued state instead of the control.
  assert.equal(await trackedCard.getByRole('button',{name:'Track this'}).count(),0,'an already-promoted report has no Track this control');
  assert.match(await trackedCard.innerText(),/Queued for review/);
  await trackedCard.locator('a',{hasText:'Open in Decisions'}).click();
  await page.locator('#decisions-panel').waitFor();
  await page.locator('#activity-tab').click();await page.locator('#activity-panel').waitFor();
  // Not yet promoted: one tap drafts the package and the card flips to the queued state.
  await trackableCard.getByRole('button',{name:'Track this'}).click();
  await trackableCard.getByRole('button',{name:'Track this'}).waitFor({state:'detached'});
  assert.equal(promoteBody.id,trackableReport.id);
  assert.match(await trackableCard.innerText(),/Queued for review/,'the control is replaced once queued');

  // Session tab: unaffected controls, GPU charts, missing-readings handling, mocked start.
  await page.locator('#session-tab').click();
  await page.waitForFunction(()=>document.querySelector('#gpu-temperature').textContent==='56 °C');
  assert.equal(await page.locator('#gpu-usage').innerText(),'64%');
  assert.equal((await page.locator('#gpu-usage-chart .gpu-line').getAttribute('d')).split('M').length-1,2);
  assert.equal(await page.locator('input[name=layers]').count(),5);
  assert.equal(await page.locator('#publish').isChecked(),false);
  assert.equal(await page.locator('#minutes').inputValue(),'360');
  assert.equal(await page.locator('#log-details').getAttribute('open'),'','live log defaults open on desktop');
  let submitted;
  await page.route('**/start',route=>{submitted=route.request().postDataJSON();return route.fulfill({contentType:'application/json',body:'{"started":true}'});});
  await page.locator('#direction').selectOption('discovery');
  await page.locator('input[value=chips]').check();await page.locator('input[value=technical]').check();
  await page.locator('#start').click();await page.waitForFunction(()=>document.querySelector('#message').textContent.includes('Session requested'));
  assert.deepEqual(submitted.layers,['chips']);assert.deepEqual(submitted.source_kinds,['technical']);
  assert.equal(submitted.direction,'discovery');assert.equal(submitted.publish,false);
  for(const width of [1440,390]){
   await page.setViewportSize({width,height:1100});
   assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
   await page.screenshot({path:path.join(root,'.local/browser',`research-control-${width}.png`),fullPage:true});
  }
  await page.setViewportSize({width:1440,height:1200});
  unavailable=true;
  await page.waitForFunction(()=>document.querySelector('#gpu-status').textContent==='Telemetry unavailable');
  assert.equal(await page.locator('#gpu-usage').innerText(),'Unavailable');
  await page.route('**/status',route=>route.fulfill({contentType:'application/json',body:JSON.stringify({active:false,launching:false,session:{state:'blocked',failure_reason:'Publication failed. Inspect the batch log.',batches:1,failed_batches:1}})}));
  await page.waitForFunction(()=>document.querySelector('#state').textContent==='blocked — Publication failed. Inspect the batch log.');
  assert.equal(await page.locator('#start').isDisabled(),false);
  assert.deepEqual(errors,[]);
  console.log('Research control passed: decisions feed, catalog eligibility/source-rank, GPU charts and missing readings, history fold, activity tab, mocked start, no live research.');
 }finally{if(browser)await browser.close();child.kill();}
})().catch(error=>{console.error(error);process.exitCode=1;});
