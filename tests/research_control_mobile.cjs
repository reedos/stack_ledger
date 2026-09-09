// Real mobile emulation for the unified panel: touch input, device pixel ratio, tap-target size,
// no horizontal overflow, the merged Decisions feed, and the live log collapsed on a phone.
// Offline fixtures only; start requests are intercepted; no research is launched.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const {spawn}=require('node:child_process');
const path=require('node:path'),fs=require('node:fs'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
const shots=process.env.PANEL_SHOTS_DIR||path.resolve(__dirname,'..','.local/browser');
const child=spawn('python',['scripts/research_control.py','--ephemeral'],{cwd:root,windowsHide:true});

async function mockPanel(page){
  const finding={id:'discovery-'+'a'.repeat(24),layer:'energy',url:'https://example.org/primary-source',
    created_at:'2026-09-08T00:00:00Z',published_at:null,retrieved_at:'2026-09-08T00:00:00Z',
    status:'pending_review',proposal_hash:'a'.repeat(64),review_hash:'b'.repeat(64),
    finding:{kind:'project',subject:'Fixture geothermal project',claim:'Operator reports commissioning.',
      evidence:'The operator states the project is commissioning.',basis:'actual',why_track:'Check dependable power delivery.',next_question:'Verify grid-operator records.'}};
  const catalog={id:'catalog-'+'c'.repeat(24),title:'Fixture catalog package',author:'fixture researcher',created_at:'2026-09-09T00:00:00Z',
    status:'pending_review',display_status:'pending_review',proposal_hash:'c'.repeat(64),review_hash:'d'.repeat(64),
    auto_apply_eligible:false,auto_apply_reasons:['evidence example.org is not a registered rank <=2 source'],validation:null,publication_receipt:null,
    changes:[{target:'project',id:'fixture-project',before:null,after:{id:'fixture-project',name:'Fixture project',next_evidence:'Check the next dated disclosure.'}}],
    evidence:[{id:'fixture-source',url:'https://example.org/release',published_at:'2026-09-08',retrieved_at:'2026-09-08T00:00:00Z',summary:'Fixture evidence.',source_rank:3}]};
  await page.route('**/gpu',route=>{
    const now=Date.now();
    const samples=Array.from({length:30},(_,i)=>({timestamp_ms:now-(29-i)*2000,name:'Fixture GPU',utilization:20+i,temperature:40+i}));
    return route.fulfill({contentType:'application/json',body:JSON.stringify({latest:{...samples.at(-1),status:'live'},samples})});
  });
  await page.route('**/status',route=>route.fulfill({contentType:'application/json',body:JSON.stringify({active:false,launching:false,session:{}})}));
  await page.route('**/findings',route=>route.fulfill({contentType:'application/json',body:JSON.stringify(
    {findings:[finding],reviewer:'reedos',invalid_files:0,unreadable_events:0,catalog_packages:[catalog],handoffs:[]})}));
  await page.route('**/visuals',route=>route.fulfill({contentType:'application/json',body:JSON.stringify({proposals:[],reviewer:'reedos',assessment:null,invalid_files:0})}));
  await page.route('**/activity',route=>route.fulfill({contentType:'application/json',body:JSON.stringify({policy_events:[],digests:[],unreadable_events:0})}));
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
    await mockPanel(page);
    await page.goto(url);
    await page.waitForFunction(()=>document.querySelector('#connection').textContent==='Connected locally');

    // Decisions is the default-visible tab; the merged feed carries both the pending finding and the pending catalog package.
    await page.locator('#decision-feed .finding-card').first().waitFor();
    assert.equal(await page.locator('#decision-feed .finding-card').count(),2,'Decisions feed merges the pending finding and catalog package');
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),'no horizontal overflow on the Decisions tab at 390px');
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

    assert.deepEqual(errors,[],'no console errors under mobile emulation');
    await phone.close();

    // Desktop-width companions of the same two tabs, for a direct visual comparison.
    const desktop=await browser.newContext({viewport:{width:1280,height:900}});
    const dpage=await desktop.newPage();
    await mockPanel(dpage);
    await dpage.goto(url);
    await dpage.waitForFunction(()=>document.querySelector('#connection').textContent==='Connected locally');
    await dpage.locator('#decision-feed .finding-card').first().waitFor();
    await dpage.screenshot({path:path.join(shots,'panel-v2-decisions-1280.png'),fullPage:false});
    await dpage.click('#session-tab');
    await dpage.locator('#session-panel').waitFor();
    assert.equal(await dpage.locator('#log-details').getAttribute('open'),'','live log defaults open on desktop');
    await dpage.screenshot({path:path.join(shots,'panel-v2-session-1280.png'),fullPage:false});
    await desktop.close();

    console.log('Research control mobile passed: real touch emulation, no overflow, 44px tap targets, merged Decisions feed, log collapsed on phone. Screenshots in '+shots);
  }finally{
    if(browser)await browser.close();
    child.kill();
  }
})().catch(error=>{console.error(error);process.exitCode=1;});
