const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const assert=require('node:assert/strict'),http=require('node:http'),fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'../docs'),evidence=path.resolve(__dirname,'../.local/browser');
const delivery=JSON.parse(fs.readFileSync(path.join(root,'data/delivery.json'),'utf8'));
const expansion=JSON.parse(fs.readFileSync(path.join(root,'data/expansion.json'),'utf8'));
const server=http.createServer((req,res)=>{
 const url=new URL(req.url,'http://localhost'),name=path.resolve(root,'.'+decodeURIComponent(url.pathname));
 if(!name.startsWith(root+path.sep)&&name!==root){res.writeHead(403);res.end();return;}
 const file=fs.existsSync(name)&&fs.statSync(name).isDirectory()?path.join(name,'index.html'):name;
 if(!fs.existsSync(file)){res.writeHead(404);res.end();return;}
 res.setHeader('Content-Type',({'.html':'text/html','.css':'text/css','.js':'application/javascript','.json':'application/json','.svg':'image/svg+xml'})[path.extname(file)]||'text/plain');fs.createReadStream(file).pipe(res);
});
(async()=>{
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));const origin=`http://127.0.0.1:${server.address().port}/`;
 const browser=await chromium.launch({channel:'chrome',headless:true});
 try{
  fs.mkdirSync(evidence,{recursive:true});const page=await browser.newPage({viewport:{width:1440,height:1100}}),errors=[];
  page.on('pageerror',err=>errors.push(err.message));
  await page.goto(origin);await page.locator('body[data-enhanced="true"]').waitFor();
  assert.equal(await page.locator('#capital-buildout').count(),1);assert.equal(await page.locator('#buildout-explorers a.explorer-preview').count(),2);
  await page.locator('#capital-buildout').screenshot({path:path.join(evidence,'capital-desktop.png')});
  await page.goto(origin+'projects/');await page.locator('body[data-enhanced="true"]').waitFor();
  assert.match(await page.locator('#map-count').innerText(),new RegExp(`${delivery.projects.filter(p=>p.map_location||p.map_locations?.length).length} mapped`));
  const before=await page.locator('#map-canvas svg').getAttribute('viewBox');await page.locator('#map-zoom-in').click();assert.notEqual(await page.locator('#map-canvas svg').getAttribute('viewBox'),before);
  await page.locator('#map-us').click();await page.locator('.map-marker').first().click();assert.match(await page.locator('#map-selection').innerText(),/Approximate county|Nearby locations/);
  await page.locator('#map-selection a[href^="#project-"]').first().click();assert.equal(await page.locator(locationSelector()).count(),1);
  function locationSelector(){return '#project-gemini';}
  const stageUnknown=delivery.projects.filter(p=>p.stage==='status-unverified').length;
  assert.match(await page.locator('.delivery-totals').innerText(),new RegExp(`${stageUnknown}\\s+stage needs verification`));
  await page.selectOption('#project-stage','status-unverified');
  assert.equal(await page.locator('#project-results .delivery-card').count(),stageUnknown);
  assert.equal(await page.locator('.map-segment.phase-delivery').count(),0);
  assert.equal(await page.locator('.map-segment.phase-operating').count(),0);
  await page.selectOption('#project-stage','all');await page.locator('#project-search').fill('Prometheus');
  assert.equal(await page.locator('#project-results .delivery-card').count(),1);
  assert.match(await page.locator('#project-meta-prometheus').innerText(),/1 GW/);
  assert.match(await page.locator('#project-meta-prometheus').innerText(),/Company commitment/i);
  await page.locator('#project-search').fill('');
  await page.selectOption('#map-company','Waymo / Alphabet');await page.selectOption('#project-stage','announced');
  assert.match(await page.locator('#map-count').innerText(),/18 project locality markers/);
  assert.equal(await page.locator('#project-results .delivery-card').count(),1);
  assert.ok(await page.locator('.map-segment.phase-planned').count()>0);
  await page.selectOption('#project-stage','all');await page.locator('#project-search').fill('Seattle');
  assert.match(await page.locator('#map-count').innerText(),/1 project locality markers/);
  await page.locator('.map-marker').first().click();assert.match(await page.locator('#map-selection').innerText(),/Up Next/);
  await page.locator('#project-search').fill('');await page.selectOption('#map-company','OpenAI');
  assert.match(await page.locator('#map-count').innerText(),/0 mapped of 0 matching project records/);
  assert.equal(await page.locator('.map-office-glyph').count(),1);
  await page.locator('#map-offices').uncheck();assert.equal(await page.locator('.map-marker').count(),0);
  await page.locator('#map-offices').check();await page.selectOption('#map-company','all');
  await page.selectOption('#map-coverage','unmapped');assert.equal(await page.locator('.map-marker').count(),0);
  assert.equal(await page.locator('#project-results .delivery-card').count(),delivery.projects.filter(p=>!p.map_location&&!p.map_locations?.length).length);
  await page.selectOption('#map-coverage','all');await page.selectOption('#map-company','Meta');
  assert.equal(await page.locator('#project-results .delivery-card').count(),delivery.projects.filter(p=>p.owner==='Meta').length);
  await page.selectOption('#map-company','all');await page.locator('[data-project-layer="chips"]').click();
  assert.match(await page.locator('#map-count').innerText(),new RegExp(`${delivery.projects.filter(p=>p.layer==='chips'&&(p.map_location||p.map_locations?.length)).length} mapped`));
  await page.locator('#map-world').click();await page.locator('#project-map').screenshot({path:path.join(evidence,'project-map-desktop.png')});
  await page.goto(origin+'models/');await page.locator('body[data-enhanced="true"]').waitFor();
  assert.equal(await page.locator('#model-capabilities').count(),1);
  const all=expansion.capabilities.rows,counts=new Map();for(const r of all)counts.set(r.organization,(counts.get(r.organization)||0)+1);
  const defaultCount=all.filter(r=>counts.get(r.organization)>3&&r.organization!=='Not listed by Epoch').length;
  assert.equal(await page.locator('#eci-model option[value=""]~option').count(),defaultCount);
  assert.equal(await page.locator('#eci-color').inputValue(),'organization');
  assert.equal(await page.locator('#eci-model').inputValue(),'');
  assert.equal(await page.locator('.eci-uncertainty').count(),0);
  assert.equal(await page.locator('#eci-selection').isVisible(),false);
  assert.equal(await page.locator('#eci-developer').count(),0);
  await page.locator('#eci-hide-all').click();await page.locator('#eci-legend button[data-group="OpenAI"]').click();
  const selected=all.filter(r=>r.organization==='OpenAI');
  assert.equal(await page.locator('#eci-model option[value=""]~option').count(),selected.length);
  assert.equal(await page.locator('#eci-table tr').count(),selected.length);
  await page.locator('#eci-frontier-only').check();assert.ok(await page.locator('#eci-model option[value=""]~option').count()<selected.length);
  await page.selectOption('#eci-color','country');assert.ok(await page.locator('#eci-legend button[data-group="China"]').count());
  await page.locator('#eci-frontier-only').uncheck();await page.locator('#eci-small').check();
  await page.locator('#eci-hide-all').click();await page.locator('#eci-legend button[data-group="France"]').click();
  assert.equal(await page.locator('#eci-model option[value=""]~option').count(),all.filter(r=>r.country==='France').length);
  await page.selectOption('#eci-color','access');await page.locator('#eci-show-all').click();
  assert.equal(await page.locator('#eci-model option[value=""]~option').count(),all.length);
  await page.locator('#eci-search').fill('no-such-model');assert.equal(await page.locator('#eci-model option[value=""]~option').count(),0);assert.match(await page.locator('#eci-selection').innerText(),/No models match/);
  await page.locator('#eci-reset').click();assert.equal(await page.locator('#eci-model option[value=""]~option').count(),defaultCount);
  await page.locator('#eci-small').check();
  const anchor=expansion.capabilities.rows.find(r=>r.name==='GPT-5');await page.selectOption('#eci-model',anchor.id);assert.match(await page.locator('#eci-selection').innerText(),/Calibration anchor/);assert.equal(await page.locator('.eci-uncertainty').count(),0);
  const latest=expansion.capabilities.rows[0];await page.selectOption('#eci-model',latest.id);assert.equal(await page.locator('.eci-uncertainty').count(),1);
  await page.selectOption('#eci-color','country');assert.equal(await page.locator('#eci-model').inputValue(),latest.id);
  await page.locator('#eci-search').fill('no-such-model');assert.equal(await page.locator('#eci-model').inputValue(),'');assert.equal(await page.locator('.eci-uncertainty').count(),0);
  await page.locator('#eci-search').fill('');assert.equal(await page.locator('#eci-model').inputValue(),'');
  await page.locator('.eci-point:visible').first().click();assert.notEqual(await page.locator('#eci-model').inputValue(),'');assert.equal(await page.locator('.eci-point.is-selected').count(),1);
  await page.selectOption('#eci-model','');assert.equal(await page.locator('.eci-uncertainty').count(),0);assert.equal(await page.locator('#eci-selection').isVisible(),false);
  await page.selectOption('#eci-model',latest.id);await page.locator('#eci-reset').click();assert.equal(await page.locator('#eci-model').inputValue(),'');assert.equal(await page.locator('.eci-uncertainty').count(),0);
  await page.locator('#model-capabilities').screenshot({path:path.join(evidence,'capabilities-desktop.png')});
  for(const width of [390,320]){
   await page.setViewportSize({width,height:844});
   for(const [route,id] of [['','#capital-buildout'],['projects/','#project-map'],['models/','#model-capabilities']]){
    await page.goto(origin+route);await page.locator('body[data-enhanced="true"]').waitFor();
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,route+' overflow at '+width);
    if(width===390)await page.locator(id).screenshot({path:path.join(evidence,id.slice(1)+'-mobile.png')});
   }
  }
  const context=await browser.newContext({javaScriptEnabled:false}),staticPage=await context.newPage();
  for(const [route,id] of [['','#capital-buildout'],['projects/','#project-map'],['models/','#model-capabilities']]){
   await staticPage.goto(origin+route);assert.equal(await staticPage.locator(id+' svg').count(),1);assert.equal(await staticPage.locator(id+' details').count(),1);
  }
  await context.close();assert.deepEqual(errors,[]);
  console.log('Explorer acceptance passed: static fallbacks, capital sources, map/list filters and zoom, ECI filters/frontier/intervals, 320px and 390px layouts.');
 }finally{await browser.close();await new Promise(resolve=>server.close(resolve));}
})().catch(err=>{console.error(err);process.exitCode=1;server.close();});
