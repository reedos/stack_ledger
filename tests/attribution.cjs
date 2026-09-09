// Loads the real site/assets/app.js in a sandboxed context (stubbed document/window/fetch,
// like tests/analytics.cjs) and exercises the exported pure attributionLabel(o) function.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');

const code=fs.readFileSync(path.join(__dirname,'../site/assets/app.js'),'utf8');

const COMPANIES={
 meta:{id:'meta',name:'Meta',ir_url:'https://investor.atmeta.com/investor-news/press-release-details/2026',blog_urls:[]},
 nvidia:{id:'nvidia',name:'NVIDIA',ir_url:'https://nvidianews.nvidia.com/news/x',blog_urls:[]},
 oracle:{id:'oracle',name:'Oracle',ir_url:'https://investor.oracle.com/x',blog_urls:[]},
};

// A harmless stand-in for any DOM element app.js's top-level code might touch (insertAdjacentHTML,
// classList, addEventListener, ...): any method call is a no-op that returns the stub itself.
const stubElement=new Proxy({dataset:{},classList:{add(){},remove(){},toggle(){}}},{get:(t,p)=>p in t?t[p]:(...a)=>stubElement});
const sandbox={
 document:{body:{dataset:{base:'./',page:'home',build:'test'}},querySelector:()=>stubElement,querySelectorAll:()=>[],addEventListener:()=>{}},
 window:{innerWidth:1200,addEventListener:()=>{}},
 location:{search:'',pathname:'/',hash:''},
 // Reject immediately so app.js's bottom-of-file Promise.all(...).then(...) never runs (it would
 // need a full dataset and DOM to render the whole page) and instead takes its already-graceful
 // .catch() path with an expected, clearly-labeled error.
 fetch:()=>Promise.reject(new Error('attribution.cjs: network disabled, not exercising page render')),
 companyOf:id=>COMPANIES[id],
 module:{exports:{}},
 console,URL,Intl,
};
vm.createContext(sandbox);
vm.runInContext(code,sandbox,{filename:'app.js'});
const {attributionLabel}=sandbox.module.exports;
assert.equal(typeof attributionLabel,'function','app.js must export attributionLabel via module.exports for tests');

const fixture={
 metrics:[
  {id:'m-guidance',company:'meta'},
  {id:'m-nvidia-forecast',company:'nvidia'},
  {id:'m-oracle-forecast',company:'oracle'},
  {id:'m-obs',company:null},
  {id:'m-estimate',company:null},
  {id:'m-commit',company:'meta'},
  {id:'m-govt',company:null},
  {id:'m-guidance-full-name',company:'meta'},
 ],
 sources:[
  {id:'s-meta',publisher:'Meta',url:'https://investor.atmeta.com/investor-news/press-release-details/2026/Meta-Reports-Q2/default.aspx',published:'2026-07-30'},
  {id:'s-meta-full-name',publisher:'Meta Platforms, Inc.',url:'https://example.com/press',published:'2026-07-30'},
  {id:'s-nvidia',publisher:'Stock Analysis / S&P Global',url:'https://stockanalysis.com/stocks/nvda/forecast/',published:'2026-09-07'},
  {id:'s-epoch',publisher:'Epoch AI',url:'https://epoch.ai/data/ai-data-centers',published:'2026-09-03'},
  {id:'s-any',publisher:'X Publisher',url:'https://example.com/',published:null},
 ],
};
// app.js's `data` is a top-level `let`, a lexical binding of the vm context rather than a plain
// property of the sandbox object; assign it with code run inside that same context.
vm.runInContext('data = '+JSON.stringify(fixture)+';',sandbox);

const label=(metric,source,status)=>attributionLabel({metric,source,status});

// capital-guidance-meta-2026-reviewed-style: first-party by exact publisher name and IR host.
assert.equal(label('m-guidance','s-meta','forecast'),'Company guidance');
// "Meta" (company.name) is a prefix of the fuller legal publisher name "Meta Platforms, Inc.".
assert.equal(label('m-guidance-full-name','s-meta-full-name','forecast'),'Company guidance');
// company-finance-revenue-nvidia-forecast-2027-20260907-style: independent analyst consensus.
assert.equal(label('m-nvidia-forecast','s-nvidia','forecast'),'Independent projection');
// Epoch-sourced end-state forecast: independent research org, not the tracked company.
assert.equal(label('m-oracle-forecast','s-epoch','forecast'),'Independent projection');
// Observation/estimate/commitment/government-target keep their own labels, unaffected by company.
assert.equal(label('m-obs','s-any','observation'),'Reported observation');
assert.equal(label('m-estimate','s-any','estimate'),'Historical estimate');
assert.equal(label('m-commit','s-any','company-commitment'),'Company commitment');
assert.equal(label('m-govt','s-any','government-target'),'Government target');

console.log('Attribution checks passed: company guidance vs independent projection, name/host first-party match, other statuses unchanged.');
