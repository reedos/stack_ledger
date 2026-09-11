// Enough DOM to build panel nodes in node --test: the panel scripts only create elements, set text
// and wire handlers, so nothing here lays out, matches selectors or dispatches events.
const fs=require('fs'),path=require('path');
const PANEL=path.join(__dirname,'..','tools','research-control');

function element(tag){
  const el={tagName:String(tag).toUpperCase(),children:[],attributes:{},listeners:{},
    textContent:'',className:'',value:'',hidden:false,disabled:false,checked:false,
    classList:{add(){},remove(){},toggle(){return false;},contains(){return false;}},
    append(...kids){for(const k of kids)if(k&&typeof k==='object')el.children.push(k);},
    replaceChildren(...kids){el.children.length=0;el.append(...kids);},
    setAttribute(name,value){el.attributes[name]=String(value);},
    getAttribute(name){return el.attributes[name];},
    addEventListener(type,fn){(el.listeners[type]=el.listeners[type]||[]).push(fn);},
    querySelector(){return element('div');},
    contains(){return false;}};
  return el;
}

// Ids come from the page itself, so a renamed element fails the test instead of silently passing.
function stubDocument(){
  const html=fs.readFileSync(path.join(PANEL,'index.html'),'utf8');
  const byId={};
  for(const m of html.matchAll(/ id="([^"]+)"/g))byId[m[1]]=element('div');
  return {byId,body:element('body'),activeElement:null,
    createElement:tag=>element(tag),
    getElementById:id=>byId[id]||null,
    querySelectorAll:()=>[]};
}

function* walk(el){
  yield el;
  for(const kid of el.children||[])yield* walk(kid);
}
const nodes=el=>[...walk(el)];
const texts=el=>nodes(el).map(n=>n.textContent).filter(Boolean);
const byTag=(el,tag)=>nodes(el).filter(n=>n.tagName===tag.toUpperCase());
const source=name=>fs.readFileSync(path.join(PANEL,name),'utf8');

module.exports={element,stubDocument,nodes,texts,byTag,source};
