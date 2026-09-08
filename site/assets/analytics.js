/* Page views only, on the published site. Local previews and tests never load GoatCounter. */
(() => {
 'use strict';
 if(location.hostname!=='reedos.github.io'||!location.pathname.startsWith('/stack_ledger/'))return;
 const endpoint=document.currentScript?.dataset.goatcounter;
 if(!/^https:\/\/[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.goatcounter\.com\/count$/.test(endpoint||''))return;
 const script=document.createElement('script');
 script.async=true;script.src='https://gc.zgo.at/count.js';
 script.dataset.goatcounter=endpoint;
 script.dataset.goatcounterSettings=JSON.stringify({no_events:true});
 document.head.append(script);
})();
