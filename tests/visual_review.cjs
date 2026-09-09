// Actual isolated proposal, server and preview; no inference or live review decisions.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const {spawn}=require('node:child_process');
const path=require('node:path'),assert=require('node:assert/strict'),fs=require('node:fs');
const root=path.resolve(__dirname,'..');
const code=`import sys,tempfile
from pathlib import Path
sys.path.insert(0,'scripts')
from evaluate_visuals import fixture
from research_control import server
with tempfile.TemporaryDirectory() as folder:
 root=Path(folder);fixture(root);http,url=server(root);print(url,flush=True)
 try:http.serve_forever()
 finally:http.server_close()
`;
const child=spawn('python',['-u','-c',code],{cwd:root,windowsHide:true});
(async()=>{let browser;try{
 const url=await new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(Error('Server timeout')),30000);let log='';child.stdout.on('data',chunk=>{const m=chunk.toString().match(/http:\/\/127\.0\.0\.1:\d+\/[^\s]+/);if(m){clearTimeout(timer);resolve(m[0]);}});child.stderr.on('data',c=>log+=c);child.on('exit',c=>{clearTimeout(timer);reject(Error('Server exited '+c+' '+log));});});
 browser=await chromium.launch({channel:'chrome',headless:true});const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(url);await page.locator('#review-tab').click();await page.locator('.visual-proposal').waitFor();
 for(const width of [1440,390]){await page.setViewportSize({width,height:1000});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));}
 const href=await page.locator('.visual-proposal a').first().getAttribute('href');const preview=await browser.newPage();await preview.goto(url+href);
 assert.equal(await preview.locator('script').count(),0);assert.equal(await preview.locator('.layer-card').count(),2);
 for(const width of [1440,390]){await preview.setViewportSize({width,height:1000});assert.ok(await preview.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));}
 fs.mkdirSync(path.join(root,'.local/browser'),{recursive:true});await page.screenshot({path:path.join(root,'.local/browser/visual-review-mobile.png'),fullPage:true});await preview.screenshot({path:path.join(root,'.local/browser/visual-preview-mobile.png'),fullPage:true});
 const data=await (await page.request.get(url+'visuals')).json();const item=data.proposals[0];
 const unauthorized=await page.request.post(url+'visual-review',{data:{id:item.id}});assert.equal(unauthorized.status(),403);
 await page.locator('.visual-proposal textarea').fill('Synthetic browser review: retain scope and sources.');await page.locator('.visual-proposal input[type=checkbox]').check();
 await page.locator('.visual-proposal button[type=submit]').count(); // Native form button defaults to submit.
 await page.locator('.visual-proposal button').filter({hasText:'Record visual decision'}).click();
 await page.waitForFunction(()=>document.querySelector('#visual-recommendations').textContent.includes('Decision saved. Nothing applied or published.'));
 await page.getByLabel('Visual recommendation status').selectOption('approved');await page.locator('.visual-proposal').waitFor();
 const after=await (await page.request.get(url+'visuals')).json();assert.equal(after.proposals[0].status,'approved');
 assert.deepEqual(errors,[]);console.log('Visual panel, mobile preview, CSRF and isolated approval passed. No live decisions or inference.');
 }finally{if(browser)await browser.close();child.kill();}
})().catch(e=>{console.error(e);process.exitCode=1;});
