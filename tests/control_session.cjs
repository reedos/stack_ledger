const test=require('node:test');const assert=require('node:assert/strict');
const {stubDocument,source}=require('./control_dom.cjs');
// Starting and stopping a session were the only mutations with no toast: on a phone the form's own
// status line sits below the fold, behind the tab bar. Evaluate the real notify() and the real
// handlers together, so a toast has to be produced, not merely a text property set somewhere.
function panel(response){
  const src=source('control.js');
  const code=src.slice(src.indexOf('function notify('),src.indexOf('const PANELS='))
            +src.slice(src.indexOf('async function send('),src.indexOf('async function poll('));
  const document=stubDocument();
  const calls=[];
  const fetchStub=async(action,init)=>{calls.push([action,JSON.parse(init.body),init.headers['X-Session-Key']]);return {ok:response.ok,json:async()=>response.body};};
  new Function('document','$','fetch','setTimeout','clearTimeout','key',code)(
    document,id=>document.getElementById(id),fetchStub,()=>0,()=>{},'fixture-session-key');
  const fire=(id,type)=>document.getElementById(id).listeners[type][0]({preventDefault(){}});
  return {document,calls,fire,toast:()=>document.body.children.at(-1),
          message:()=>document.getElementById('message').textContent};
}

test('starting a session raises a toast, not only the form line',async()=>{
  const p=panel({ok:true,body:{started:true}});
  await p.fire('session-form','submit');
  assert.equal(p.calls[0][0],'start');
  const toast=p.toast();
  assert.ok(toast,'no toast element was created');
  assert.equal(toast.textContent,'Session requested. The controller will report startup below.');
  assert.equal(toast.className,'toast ok');
  assert.equal(p.message(),toast.textContent);
});

test('a refused start raises an error toast and re-enables the button',async()=>{
  const p=panel({ok:false,body:{error:'A session is already active'}});
  await p.fire('session-form','submit');
  assert.equal(p.toast().textContent,'A session is already active');
  assert.equal(p.toast().className,'toast error');
  assert.equal(p.document.getElementById('start').disabled,false);
});

test('stopping a session raises a toast',async()=>{
  const p=panel({ok:true,body:{stop_requested:true}});
  await p.fire('stop','click');
  assert.deepEqual(p.calls[0],['stop',{},'fixture-session-key']);
  assert.equal(p.toast().textContent,'Stop requested. Current work will finish safely.');
  assert.equal(p.toast().className,'toast ok');
});

test('a refused stop raises an error toast',async()=>{
  const p=panel({ok:false,body:{error:'No active session yet; wait for startup'}});
  await p.fire('stop','click');
  assert.equal(p.toast().textContent,'No active session yet; wait for startup');
  assert.equal(p.toast().className,'toast error');
});
