// Offline UI acceptance. Start requests are intercepted; no research is launched.
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
  const stale=await browser.newPage();
  await stale.route('**/reviews.js',route=>route.fulfill({status:404,contentType:'application/json',body:'{}'}));
  await stale.goto(url);await stale.locator('#review-tab').click();
  await stale.locator('#review-panel').waitFor();
  assert.match(await stale.locator('#review-message').innerText(),/Reopen Research-Control.cmd/);
  await stale.locator('#session-tab').click();await stale.locator('#session-panel').waitFor();
  await stale.unroute('**/reviews.js');
  await stale.route('**/findings',route=>route.fulfill({status:404,contentType:'application/json',body:'{}'}));
  await stale.reload();await stale.locator('#review-tab').click();
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
  await page.goto(url);await page.waitForFunction(()=>document.querySelector('#connection').textContent==='Connected locally');
  let reviewed=false,reviewRequest;
  const finding={id:'discovery-'+'a'.repeat(24),layer:'energy',url:'https://example.org/primary-source',
    created_at:'2026-09-08T00:00:00Z',published_at:null,retrieved_at:'2026-09-08T00:00:00Z',
    status:'pending_review',proposal_hash:'a'.repeat(64),review_hash:'b'.repeat(64),
    finding:{kind:'project',subject:'Fixture geothermal project',claim:'Operator reports commissioning. <img src=x onerror=alert(1)>',
      evidence:'The operator states the project is commissioning.',basis:'actual',why_track:'Check dependable power delivery.',next_question:'Verify grid-operator records.'}};
  await page.route('**/findings',route=>route.fulfill({contentType:'application/json',body:JSON.stringify({findings:[{...finding,status:reviewed?'investigate':'pending_review'}],reviewer:'reedos',invalid_files:0})}));
  await page.route('**/review',route=>{reviewRequest=route.request().postDataJSON();reviewed=true;return route.fulfill({contentType:'application/json',body:'{"saved":true,"reviewer":"reedos","status":"investigate","published":false}'});});
  await page.locator('#review-tab').click();await page.locator('.finding-card').waitFor();
  assert.equal(await page.locator('.finding-card img').count(),0);
  assert.match(await page.locator('.finding-card').innerText(),/Source published: unknown/);
  fs.mkdirSync(path.join(root,'.local/browser'),{recursive:true});
  for(const width of [1440,390]){
    await page.setViewportSize({width,height:1100});
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    await page.screenshot({path:path.join(root,'.local/browser',`review-findings-${width}.png`),fullPage:true});
  }
  await page.locator('.finding-review button').click();assert.equal(reviewRequest,undefined);
  await page.locator('.finding-review textarea').fill('Verify the grid-operator record before adoption.');
  await page.locator('.finding-review input[type=checkbox]').check();
  await page.locator('.finding-review button').click();
  await page.waitForFunction(()=>document.querySelector('#review-message').textContent.includes('Nothing published'));
  assert.equal(reviewRequest.confirmed,true);assert.equal(reviewRequest.proposal_hash,finding.proposal_hash);
  assert.equal(await page.locator('.finding-card').count(),0);
  await page.locator('#review-status').selectOption('investigate');assert.equal(await page.locator('.finding-card').count(),1);
  // Catalog workflow stays local here: every mutation and build is intercepted.
  let catalogStatus='pending_review',previewed=false,decisionBody,publishBody;
  const catalog={id:'catalog-'+'c'.repeat(24),title:'Fixture catalog package',author:'fixture researcher',proposal_hash:'c'.repeat(64),review_hash:'d'.repeat(64),
    changes:[{target:'project',id:'fixture-project',before:null,after:{id:'fixture-project',name:'<img src=x onerror=alert(1)>',next_evidence:'x'.repeat(400)}}],
    evidence:[{id:'fixture-source',url:'javascript:alert(1)',published_at:null,retrieved_at:'2026-09-08T00:00:00Z',summary:'Fixture evidence.'}]};
  await page.unroute('**/findings');
  await page.route('**/findings',route=>route.fulfill({contentType:'application/json',body:JSON.stringify({findings:[],reviewer:'reedos',invalid_files:0,catalog_packages:[{...catalog,status:catalogStatus,validation:previewed?{passed:true,checks:[]}:null}]})}));
  await page.route('**/catalog-preview',route=>{previewed=true;return route.fulfill({contentType:'application/json',body:'{"passed":true}'});});
  await page.route('**/catalog-review',route=>{decisionBody=route.request().postDataJSON();catalogStatus='approved';return route.fulfill({contentType:'application/json',body:'{"status":"approved","published":false}'});});
  await page.route('**/catalog-publish',route=>{publishBody=route.request().postDataJSON();catalogStatus='applied';return route.fulfill({contentType:'application/json',body:'{"status":"deployed"}'});});
  await page.locator('#refresh-findings').click();
  const catalogCard=page.locator('#catalog-packages article');await catalogCard.waitFor();
  assert.equal(await catalogCard.locator('img,a[href^="javascript:"]').count(),0);
  await catalogCard.getByRole('button',{name:'Validate preview',exact:true}).click();
  await catalogCard.getByRole('link',{name:'Open site preview'}).waitFor();
  await catalogCard.getByRole('button',{name:'Record catalog decision'}).click();assert.equal(decisionBody,undefined);
  await catalogCard.locator('textarea').fill('Synthetic evidence review only.');await catalogCard.locator('form input[type=checkbox]').check();
  await catalogCard.getByRole('button',{name:'Record catalog decision'}).click();
  await catalogCard.getByRole('button',{name:'Apply and publish'}).waitFor();assert.equal(decisionBody.confirmed,true);assert.equal(publishBody,undefined);
  await catalogCard.getByRole('button',{name:'Apply and publish'}).click();assert.equal(publishBody,undefined);
  await catalogCard.locator(':scope > label input[type=checkbox]').check();await catalogCard.getByRole('button',{name:'Apply and publish'}).click();
  await page.waitForFunction(()=>document.querySelector('#review-message').textContent.includes('deployed'));
  assert.equal(publishBody.proposal_hash,catalog.proposal_hash);assert.equal(publishBody.confirmed,true);
  await catalogCard.locator('details').first().locator('summary').click();
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  await page.locator('#session-tab').click();
  await page.waitForFunction(()=>document.querySelector('#gpu-temperature').textContent==='56 °C');
  assert.equal(await page.locator('#gpu-usage').innerText(),'64%');
  assert.equal((await page.locator('#gpu-usage-chart .gpu-line').getAttribute('d')).split('M').length-1,2);
  assert.equal(await page.locator('input[name=layers]').count(),5);
  assert.equal(await page.locator('#publish').isChecked(),false);
  assert.equal(await page.locator('#minutes').inputValue(),'360');
  let submitted;
  await page.route('**/start',route=>{submitted=route.request().postDataJSON();return route.fulfill({contentType:'application/json',body:'{"started":true}'});});
  await page.locator('#direction').selectOption('discovery');
  await page.locator('input[value=chips]').check();await page.locator('input[value=technical]').check();
  await page.locator('#start').click();await page.waitForFunction(()=>document.querySelector('#message').textContent.includes('Session requested'));
  assert.deepEqual(submitted.layers,['chips']);assert.deepEqual(submitted.source_kinds,['technical']);
  assert.equal(submitted.direction,'discovery');assert.equal(submitted.publish,false);
  fs.mkdirSync(path.join(root,'.local/browser'),{recursive:true});
  for(const width of [1440,390]){
   await page.setViewportSize({width,height:1100});
   assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
   await page.screenshot({path:path.join(root,'.local/browser',`research-control-${width}.png`),fullPage:true});
  }
  unavailable=true;
  await page.waitForFunction(()=>document.querySelector('#gpu-status').textContent==='Telemetry unavailable');
  assert.equal(await page.locator('#gpu-usage').innerText(),'Unavailable');
  await page.route('**/status',route=>route.fulfill({contentType:'application/json',body:JSON.stringify({active:false,launching:false,session:{state:'blocked',failure_reason:'Publication failed. Inspect the batch log.',batches:1,failed_batches:1}})}));
  await page.waitForFunction(()=>document.querySelector('#state').textContent==='blocked — Publication failed. Inspect the batch log.');
  assert.equal(await page.locator('#start').isDisabled(),false);
  assert.deepEqual(errors,[]);
  console.log('Research control passed: desktop/mobile, GPU charts and missing readings, optional filters, private default, mocked start, no live research.');
 }finally{if(browser)await browser.close();child.kill();}
})().catch(error=>{console.error(error);process.exitCode=1;});
