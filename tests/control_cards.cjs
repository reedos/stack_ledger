const test=require('node:test');const assert=require('node:assert/strict');
const {stubDocument,texts,byTag,source}=require('./control_dom.cjs');
// reviews.js is one IIFE; evaluate its body up to the load-time wiring, then reach in for the card
// builder. `owner` is the module's own let, assigned from the appended tail rather than by the panel.
function panel(owner){
  const src=source('reviews.js');
  const body=src.slice(src.indexOf('const el=id=>document.getElementById(id);'),src.indexOf("  el('refresh-findings').onclick=refresh;"));
  const document=stubDocument();
  const make=new Function('document','window','fetch','notify','sessionKey','localStorage','setInterval',
    body+'owner=arguments[7];return {buildCatalogCard,drawPublishingStrip};');
  return make(document,{},async()=>({ok:true,json:async()=>({})}),()=>{},()=>'k',
    {getItem:()=>null,setItem:()=>{}},()=>0,owner);
}

const pkg=(over={})=>({id:'catalog-'+'a'.repeat(24),title:'Fixture package',author:'fixture researcher',
  status:'pending_review',display_status:'pending_review',created_at:'2026-09-11T00:00:00Z',
  proposal_hash:'c'.repeat(64),review_hash:'d'.repeat(64),validation:null,publication_receipt:null,job:null,
  auto_apply_eligible:false,auto_apply_reasons:[],evidence:[],
  changes:[{target:'project',id:'fixture-project',before:null,after:{id:'fixture-project',name:'Fixture site',stage:'announced'},evidence:['e1']}],
  ...over});

function card(p,owner='reedos'){return panel(owner).buildCatalogCard(p,{});}

// A validate job is queued or running for at most a minute, but the reviewer's Defer and Reject need
// no preview at all and used to vanish with the Validate button for that whole time.
test('a package under validation keeps Defer, Reject and the decision button',()=>{
  const el=card(pkg({job:{kind:'validate',status:'running',step:'Building and testing the isolated preview…'}}));
  const options=byTag(el,'option').map(o=>o.textContent);
  assert.ok(options.includes('Defer'),'Defer option missing: '+JSON.stringify(options));
  assert.ok(options.includes('Reject'),'Reject option missing: '+JSON.stringify(options));
  const record=byTag(el,'button').find(b=>b.textContent==='Record decision');
  assert.ok(record,'Record decision button missing');
  assert.equal(record.disabled,false);
  assert.ok(texts(el).some(t=>t.startsWith('Validating…')),'validation progress not shown');
});

test('a validating package offers no second validate button',()=>{
  const labels=byTag(card(pkg({job:{kind:'validate',status:'queued',step:'Waiting in queue…'}})),'button').map(b=>b.textContent);
  assert.ok(!labels.includes('Validate preview'),'a second validation must not be offered');
});

test('an idle unvalidated package still offers Validate preview',()=>{
  const labels=byTag(card(pkg()),'button').map(b=>b.textContent);
  assert.ok(labels.includes('Validate preview'));
  assert.ok(labels.includes('Record decision'));
});

test('approval stays unavailable while validation is still running',()=>{
  const approve=byTag(card(pkg({job:{kind:'validate',status:'running'}})),'button').find(b=>b.textContent==='Approve and publish');
  assert.ok(approve,'the approve control must stay on the card');
  assert.equal(approve.disabled,true);
});

test('a read-only account gets the controls but cannot submit them',()=>{
  const record=byTag(card(pkg({job:{kind:'validate',status:'running'}}),null),'button').find(b=>b.textContent==='Record decision');
  assert.equal(record.disabled,true);
});
