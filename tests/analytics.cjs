// No network or browser: verify production-only loading and endpoint isolation.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const code=fs.readFileSync(require('node:path').join(__dirname,'../site/assets/analytics.js'),'utf8');
function execute(hostname,pathname,endpoint){
 const loaded=[];
 vm.runInNewContext(code,{location:{hostname,pathname},document:{currentScript:{dataset:{goatcounter:endpoint}},
  createElement:()=>({dataset:{}}),head:{append:script=>loaded.push(script)}}});
 return loaded;
}
const endpoint='https://example-site.goatcounter.com/count';
for(const [host,path] of [['localhost','/stack_ledger/'],['127.0.0.1','/stack_ledger/'],['reedos.github.io','/other-site/'],['preview.example','/stack_ledger/']]){
 assert.equal(execute(host,path,endpoint).length,0);
}
for(const invalid of [null,'https://attacker.example/count','https://user:secret@example.goatcounter.com/count',endpoint+'?key=secret']){
 assert.equal(execute('reedos.github.io','/stack_ledger/',invalid).length,0);
}
for(const path of ['/stack_ledger/','/stack_ledger/companies/nvidia/']){
 const loaded=execute('reedos.github.io',path,endpoint);
 assert.equal(loaded.length,1);
 assert.equal(loaded[0].src,'https://gc.zgo.at/count.js');
 assert.equal(loaded[0].dataset.goatcounter,endpoint);
 assert.equal(JSON.parse(loaded[0].dataset.goatcounterSettings).no_events,true);
 assert.equal(loaded[0].async,true);
}
console.log('Analytics checks passed: production-only pageviews, no local/test requests, validated endpoint, no click tracking.');
