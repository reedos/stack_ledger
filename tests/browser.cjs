// Optional browser acceptance test. Set PLAYWRIGHT_MODULE to an installed module path.
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname,'../docs');
const evidence = path.resolve(__dirname,'../.local/browser');
fs.mkdirSync(evidence,{recursive:true});
const mime={'.html':'text/html','.css':'text/css','.js':'application/javascript','.svg':'image/svg+xml','.json':'application/json','.xml':'application/xml'};
const server=http.createServer((req,res)=>{
 const pathname=new URL(req.url,'http://localhost').pathname;
 if(!pathname.startsWith('/stack_ledger/')){res.writeHead(404);res.end();return;}
 let filename=path.resolve(root,decodeURIComponent(pathname.slice('/stack_ledger/'.length)) || '.');
 if(filename!==root && !filename.startsWith(root+path.sep)){res.writeHead(403);res.end();return;}
 if(fs.existsSync(filename)&&fs.statSync(filename).isDirectory())filename=path.join(filename,'index.html');
 if(!fs.existsSync(filename)){res.writeHead(404);res.end();return;}
 res.setHeader('Content-Type',mime[path.extname(filename)]||'text/plain');fs.createReadStream(filename).pipe(res);
});
(async()=>{
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const origin=`http://127.0.0.1:${server.address().port}/stack_ledger/`;
 const browser=await chromium.launch({channel:'chrome',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1000}});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  const routes=['','energy/','chips/','infrastructure/','models/','applications/','companies/','industry/','projects/','ledger/','methodology/'];
  for(const route of routes){
   const response=await page.goto(origin+route,{waitUntil:'networkidle'});assert.equal(response.status(),200);
   await page.locator('#runtime strong').first().waitFor();
   assert.equal(await page.locator('h1').count(),1);
   assert.deepEqual(await page.locator('[id]').evaluateAll(els=>{const ids=els.map(el=>el.id);return ids.filter((id,i)=>ids.indexOf(id)!==i);}),[],route+' duplicate IDs');
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,route+' desktop overflow');
   const links=await page.locator('a[href]').evaluateAll(as=>as.map(a=>new URL(a.getAttribute('href'),location.href).href).filter(u=>u.startsWith(location.origin)&&!u.includes('#')));
   for(const href of new Set(links)){assert.equal((await page.request.get(href)).status(),200,href);}
  }
  await page.goto(origin+'projects/');await page.locator('#project-count').waitFor();
  const signedChart=await page.evaluate(()=>{
   const observation=data.observations.find(o=>o.metric==='us-generation-growth-h1'),original=observation.value;
   try{observation.value=-37;const box=document.createElement('div');box.innerHTML=chart(observation.metric);const bar=box.querySelector('.bar rect');return {y:Number(bar.getAttribute('y')),height:Number(bar.getAttribute('height')),zero:Number(box.querySelector('.zero-baseline').getAttribute('d').match(/M\S+ ([\d.]+)/)[1]),text:box.textContent};}
   finally{observation.value=original;}
  });
  assert.equal(signedChart.y,signedChart.zero);assert.ok(signedChart.height>0&&signedChart.y+signedChart.height<=227);assert.match(signedChart.text,/-37/);
  assert.equal(await page.locator('.delivery-card').count(),10);
  await page.locator('[data-project-layer="energy"]').click();assert.equal(await page.locator('.delivery-card').count(),5);
  await page.selectOption('#project-stage','operating');assert.equal(await page.locator('.delivery-card').count(),2);
  await page.locator('#project-search').fill('Quebec');assert.equal(await page.locator('.delivery-card').count(),1);
  await page.locator('.delivery-history summary').click();assert.match(await page.locator('.delivery-history').innerText(),/1,250|transmission/i);
  await page.locator('#project-search').fill('missing-project');assert.equal(await page.locator('.delivery-card').count(),0);
  await page.locator('#project-search').fill('');await page.selectOption('#project-stage','all');await page.locator('[data-project-layer="infrastructure"]').click();
  assert.match(await page.locator('#project-fairwater-one .unknown').innerText(),/Not quantified/);
  assert.equal(await page.locator('#project-abilene .planned').count(),1);
  await page.locator('[data-project-layer="all"]').click();await page.screenshot({path:path.join(evidence,'projects.png'),fullPage:true});
  await page.goto(origin+'companies/?layer=chips');await page.locator('#company-count').waitFor();
  assert.equal(await page.locator('[data-company-filter="chips"]').getAttribute('aria-pressed'),'true');
  assert.ok(await page.locator('.company-card').count()>=10);
  await page.locator('#company-search').fill('lithography');
  assert.equal(await page.locator('.company-card').count(),1);
  assert.match(await page.locator('.company-card').innerText(),/ASML/);
  await page.locator('#company-search').fill('');await page.locator('[data-company-filter="all"]').click();
  await page.selectOption('#revenue-basis','run-rate');assert.equal(await page.locator('.company-card').count(),2);
  assert.equal(await page.locator('.company-revenue.run-rate').count(),2);
  await page.selectOption('#revenue-basis','annual');assert.equal(await page.locator('.company-card').count(),19);
  await page.selectOption('#revenue-basis','all');await page.screenshot({path:path.join(evidence,'companies.png'),fullPage:true});
  await page.goto(origin+'industry/');await page.locator('.industry-verdict').waitFor();
  assert.equal(await page.locator('.project-card .operating').count(),1);
  assert.equal(await page.locator('.supply-step').count(),5);
  assert.equal(await page.locator('.capacity-grid .chart-wrap').count(),3);
  assert.match(await page.locator('.employment-chart').innerText(),/-23,000/);
  await page.screenshot({path:path.join(evidence,'industry.png'),fullPage:true});
  await page.goto(origin);await page.locator('.layer-card').first().waitFor();
  assert.equal(await page.locator('.stack-svg a.slab').count(),5);
  await page.locator('.stack-svg a[aria-label="Explore layer 01: Energy"]').click();
  await page.waitForURL('**/energy/');await page.locator('#metric-select').waitFor();
  await page.selectOption('#metric-select','us-dc-electricity');
  assert.match(await page.locator('#metric-chart').innerText(),/325–580/);
  await page.locator('#metric-chart summary').click();assert.equal(await page.locator('#metric-chart tbody tr').count(),3);
  await page.selectOption('#metric-select','us-nuclear');assert.match(await page.locator('#metric-chart').innerText(),/2050/);
  await page.goto(origin+'ledger/?layer=chips');await page.locator('#research-search').waitFor();
  assert.equal(await page.locator('[data-layer="chips"]').getAttribute('aria-pressed'),'true');
  await page.locator('#research-search').fill('zz-no-such-record');assert.match(await page.locator('#result-count').innerText(),/0 research notes and 0 observations/);
  await page.locator('#research-search').fill('');await page.locator('[data-layer="all"]').click();
  const downloaded=page.waitForEvent('download');await page.locator('#download-csv').click();const csv=await downloaded;await csv.saveAs(path.join(evidence,'observations.csv'));
  assert.match(fs.readFileSync(path.join(evidence,'observations.csv'),'utf-8'),/source_url/);
  await page.goto(origin);await page.locator('.hero').waitFor();await page.screenshot({path:path.join(evidence,'desktop.png'),fullPage:true});
  for(const width of [390,768]){
   await page.setViewportSize({width,height:844});
   for(const route of routes){await page.goto(origin+route);await page.locator('#runtime strong').first().waitFor();assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,route+' overflow at '+width);}
  }
  await page.setViewportSize({width:390,height:844});await page.goto(origin);await page.locator('.hero').waitFor();await page.screenshot({path:path.join(evidence,'mobile.png'),fullPage:true});
  await page.keyboard.press('Tab');assert.equal(await page.evaluate(()=>document.activeElement.className),'skip');
  assert.deepEqual(errors,[]);
  console.log('Browser acceptance passed: 11 routes, 3 viewports, project stage/layer/search filters, unknown versus planned capacity, source timelines, company filters, charts, navigation, ledger search, CSV, keyboard access, no page errors.');
 }finally{await browser.close();server.close();}
})().catch(e=>{console.error(e);server.close();process.exitCode=1;});
