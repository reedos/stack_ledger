const test=require('node:test');const assert=require('node:assert/strict');
// reviews.js touches the DOM at load; evaluate only the DOM-free decision span it reserves for this.
const src=require('fs').readFileSync(require('path').join(__dirname,'..','tools','research-control','reviews.js'),'utf8');
const span=src.slice(src.indexOf('function validPreview'),src.indexOf('function buildCatalogCard'));
const {publishState,publishStatusText,publishingPackages,runBulk}=new Function(
  span+'return {publishState,publishStatusText,publishingPackages,runBulk};')();

const pkg=(over={})=>({id:'catalog-'+'a'.repeat(24),title:'Fixture package',status:'pending_review',
  display_status:'pending_review',proposal_hash:'c'.repeat(64),review_hash:'d'.repeat(64),
  validation:null,publication_receipt:null,job:null,...over});
const validated=over=>pkg({validation:{passed:true,proposal_hash:'c'.repeat(64),checks:[]},...over});

function recorder(){
  const posts=[],lines=[];
  return {posts,lines,post:async(route,body)=>{posts.push([route,body]);return {};},report:t=>lines.push(t)};
}

// Deliverable 1: a validate job is queued when it is created, so anything that reads the package
// straight back and demands a passing preview reports failure before any work has been attempted.
test('bulk validate queues every selected package and reports no failure',async()=>{
  const r=recorder();
  const packages={a:pkg({id:'a'}),b:pkg({id:'b'})};
  const outcome=await runBulk('validate',{ids:['a','b'],post:r.post,latest:async id=>packages[id],report:r.report,
    rationale:'',confirmed:false,decision:'deferred'});
  assert.equal(outcome.error,undefined);
  assert.equal(outcome.queued,2);
  assert.deepEqual(r.posts.map(([route])=>route),['catalog-preview','catalog-preview']);
  assert.equal(r.lines.at(-1),'Validation queued for 2 of 2 packages; each card updates when its preview finishes.');
  assert.ok(!r.lines.some(l=>l.includes('Preview failed')));
});

test('bulk approve and publish acts on validated packages and queues validation for the rest',async()=>{
  const r=recorder();
  const packages={ready:validated({id:'ready'}),cold:pkg({id:'cold'})};
  const outcome=await runBulk('approve_publish',{ids:['ready','cold'],post:r.post,latest:async id=>packages[id],
    report:r.report,rationale:' ',confirmed:false,decision:'approved'});
  assert.equal(outcome.error,undefined);
  assert.deepEqual([outcome.done,outcome.queued],[1,1]);
  assert.deepEqual(r.posts.map(([route])=>route),['catalog-review','catalog-publish','catalog-preview']);
  assert.equal(r.posts[0][1].rationale,'Fixture package');   // blank bulk reason falls back to the title
  assert.equal(r.posts[2][1].id,'cold');
  assert.ok(r.lines.at(-1).startsWith('Approved and queued publication for 1 of 2.'));
});

test('a stale passing validation is not treated as a validated preview',async()=>{
  const r=recorder();
  const stale=pkg({id:'stale',validation:{passed:true,proposal_hash:'0'.repeat(64),checks:[]}});
  const outcome=await runBulk('approve_publish',{ids:['stale'],post:r.post,latest:async()=>stale,report:r.report,
    rationale:'',confirmed:false,decision:'approved'});
  assert.deepEqual([outcome.done,outcome.queued],[0,1]);
  assert.deepEqual(r.posts.map(([route])=>route),['catalog-preview']);
});

// Deliverable 2's rule, applied to the bulk bar: a decision never depends on a preview.
test('bulk defer records a decision on an unvalidated package instead of validating it',async()=>{
  const r=recorder();
  const outcome=await runBulk('record',{ids:['a'],post:r.post,latest:async()=>pkg({id:'a'}),report:r.report,
    rationale:'More evidence needed.',confirmed:true,decision:'deferred'});
  assert.deepEqual([outcome.done,outcome.queued],[1,0]);
  assert.deepEqual(r.posts.map(([route])=>route),['catalog-review']);
  assert.equal(r.posts[0][1].decision,'deferred');
});

test('a failing post stops the run and names the package count reached',async()=>{
  const lines=[];
  const outcome=await runBulk('validate',{ids:['a','b'],post:async()=>{throw new Error('server said no');},
    latest:async id=>pkg({id}),report:t=>lines.push(t),rationale:'',confirmed:false,decision:'deferred'});
  assert.equal(outcome.error,'server said no');
  assert.equal(lines.at(-1),'Stopped after 0 of 2: server said no');
});

// Deliverable 3: publication succeeds by appending an 'applied' event, which used to remove the
// package from the strip on the same poll -- the reviewer never saw a confirmation at all.
test('a deployed package stays in the publishing strip and reads live with its commit',()=>{
  const done=pkg({status:'applied',display_status:'applied',
    job:{kind:'publish',status:'done',result:{status:'deployed',commit:'abcdef1234567890'}}});
  assert.deepEqual(publishingPackages([done]),[done]);
  assert.equal(publishState(done),'deployed');
  assert.equal(publishStatusText(done,'deployed'),'live ✓ · commit abcdef1234');
});

test('a package applied after a later deployment check still reads live', ()=>{
  // verify_pending_deployments confirms the commit out of band, so the job result still says pending.
  const late=pkg({status:'applied',display_status:'applied',publication_receipt:{commit:'0123456789abcdef',status:'deployed'},
    job:{kind:'publish',status:'done',result:{status:'deployment_pending',commit:'0123456789abcdef'}}});
  assert.equal(publishState(late),'deployed');
  assert.equal(publishStatusText(late,'deployed'),'live ✓ · commit 0123456789');
});

test('applied packages without a publish job, and rejected ones, stay out of the strip',()=>{
  const policyApplied=pkg({status:'applied',display_status:'applied'});
  const rejected=pkg({status:'rejected',display_status:'rejected',job:{kind:'publish',status:'done',result:{status:'deployed'}}});
  assert.deepEqual(publishingPackages([policyApplied,rejected]),[]);
});

test('queued, running, failed and unpublished states are unchanged',()=>{
  const approved=pkg({status:'approved',display_status:'approved'});
  assert.equal(publishState(approved),'unpublished');
  assert.equal(publishState(pkg({status:'approved',job:{kind:'publish',status:'queued'}})),'queued');
  assert.equal(publishState(pkg({status:'approved',job:{kind:'publish',status:'running',step:'Publishing…'}})),'running');
  assert.equal(publishState(pkg({status:'approved',job:{kind:'publish',status:'failed',error:'push rejected'}})),'failed');
  assert.equal(publishState(pkg({status:'approved',display_status:'deployment_pending'})),'pending');
  assert.equal(publishStatusText(pkg({status:'approved',job:{kind:'publish',status:'failed',error:'push rejected'}}),'failed'),
    'failed: push rejected');
});
