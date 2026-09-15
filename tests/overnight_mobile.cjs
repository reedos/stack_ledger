// Read-only acceptance against the running local dashboard; no research or messages.
const {webkit}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
(async()=>{
 const root=path.resolve(__dirname,'..');
 const url=fs.readFileSync(path.join(root,'.local/research-control-url.txt'),'utf8').trim();
 const browser=await webkit.launch();
 try {
  for(const width of [390,320,1280]){
   const page=await browser.newPage({viewport:{width,height:844},deviceScaleFactor:1});
   const errors=[];page.on('pageerror',e=>errors.push(e.message));
   await page.route('**/findings',r=>r.fulfill({json:{reviewer:null,findings:[],catalog_packages:[],questions:[],unreadable_events:0}}));
   await page.goto(url+'#run=2026-09-15');
   await page.locator('#night-review .night-hero').waitFor();
   assert.match(await page.locator('#night-review').innerText(),/Tuesday, September 15th, 2026/);
   assert.equal(await page.locator('#night-review a').first().getAttribute('href'),'https://reedos.github.io/stack_ledger/latest/');
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,`overflow at ${width}`);
   await page.getByRole('searchbox',{name:'Search documents read'}).fill('NVIDIA');
   assert.match(await page.locator('.night-document').first().innerText(),/NVIDIA/i);
   await page.getByRole('button',{name:'Session',exact:true}).click();
   assert.equal(await page.locator('#session-panel').isVisible(),true);
   await page.getByRole('button',{name:'Overnight',exact:true}).click();
   assert.equal(await page.locator('#overnight-panel').isVisible(),true);
   if(width===390){fs.mkdirSync(path.join(root,'.local/browser'),{recursive:true});await page.screenshot({path:path.join(root,'.local/browser/overnight-mobile.png'),fullPage:true});}
   assert.deepEqual(errors,[]);await page.close();
  }
  console.log('Overnight dashboard: 320/390/1280px, deep link, document search, navigation and no overflow passed.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
