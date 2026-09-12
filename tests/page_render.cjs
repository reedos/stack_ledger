// Every page type renders, at desktop width and at phone width, against the published datasets.
//
// On 2026-09-12 every chart page on the desktop site showed "Interactive research could not be
// loaded". chart() still read `years.length` after the slot-axis refactor (6103b1aae) had removed
// `years`; the reference sat behind `narrow||`, so a phone never evaluated it and a day of phone
// checks passed. app.js catches every render error and swaps in that sentence, so the actual
// ReferenceError only ever existed in a browser console nobody had open.
//
// This loads the page's scripts in the order docs/index.html does, into a stubbed DOM, and drives
// the real promise chain. It asserts two things: no error reached console.error, and the chain
// ran to its last line (data-enhanced="true"). The second matters -- a chain that silently stops
// early leaves a page half-rendered without an exception.
const test = require('node:test'); const assert = require('node:assert');
const fs = require('fs'); const path = require('path'); const vm = require('vm');

const ROOT = path.join(__dirname, '..');
const html = fs.readFileSync(path.join(ROOT, 'docs', 'index.html'), 'utf8');
const SCRIPTS = [...html.matchAll(/<script[^>]*src="([^"]+)"/g)]
  .map(m => m[1].split('?')[0].replace(/^\.\//, ''))
  .filter(p => p.startsWith('assets/'));
assert.ok(SCRIPTS.includes('assets/app.js'), 'docs/index.html no longer loads app.js: ' + SCRIPTS);
const SRC = SCRIPTS.map(rel => fs.readFileSync(path.join(ROOT, 'docs', rel), 'utf8')).join('\n;\n');

const DATA_DIR = path.join(ROOT, 'docs', 'data');
const DATASETS = new Map();          // name -> text, parsed fresh per render since the page mutates it
for (const f of fs.readdirSync(DATA_DIR)) if (f.endsWith('.json')) DATASETS.set(f, fs.readFileSync(path.join(DATA_DIR, f), 'utf8'));

const PAGES = ['home', 'ledger', 'chips', 'energy', 'infrastructure', 'models', 'applications',
               'methodology', 'companies', 'projects', 'industry'];
const WIDTHS = [[1280, 'desktop'], [390, 'phone']];

function element() {
  const el = {
    dataset: {}, style: {}, attributes: {}, children: [],
    classList: { add() {}, remove() {}, toggle() {}, contains: () => false },
    set innerHTML(v) { this._html = v; }, get innerHTML() { return this._html || ''; },
    set outerHTML(v) { this._outer = v; }, get outerHTML() { return this._outer || ''; },
    textContent: '', value: '',
    appendChild(c) { this.children.push(c); return c; }, insertBefore(c) { return c; }, removeChild(c) { return c; },
    prepend() {}, append() {}, before() {}, after() {}, replaceChildren() {}, insertAdjacentHTML() {},
    setAttribute(k, v) { this.attributes[k] = v; }, getAttribute(k) { return this.attributes[k]; }, removeAttribute(k) { delete this.attributes[k]; },
    addEventListener() {}, removeEventListener() {}, dispatchEvent() { return true; },
    focus() {}, scrollIntoView() {}, replaceWith() {}, remove() {},
    closest() { return element(); }, matches() { return false; }, contains: () => false,
    querySelector() { return element(); }, querySelectorAll() { return []; },
    get firstElementChild() { return element(); },
  };
  return el;
}

function render(page, width) {
  const body = element();
  body.dataset = { base: '/', page, build: 'test' };
  const document = {
    body, documentElement: element(), head: element(),
    querySelector() { return element(); }, querySelectorAll() { return []; },
    createElement() { return element(); }, getElementById() { return element(); },
    addEventListener() {}, dispatchEvent() { return true; },
  };
  const matchMedia = () => ({ matches: width <= 800, addEventListener() {}, removeEventListener() {}, addListener() {} });
  const fetch = url => {
    const name = String(url).split('/').pop().split('?')[0];
    if (!DATASETS.has(name)) return Promise.resolve({ ok: false, status: 404 });
    return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(JSON.parse(DATASETS.get(name))) });
  };
  let failure = null;
  const sandbox = {
    document, fetch, matchMedia, location: { hash: '' },
    window: { innerWidth: width, addEventListener() {}, matchMedia },
    navigator: { userAgent: 'node', language: 'en-US' },
    requestAnimationFrame: fn => fn(), setTimeout, clearTimeout, Intl, URL, URLSearchParams, TextEncoder, TextDecoder,
    Blob: class {}, CustomEvent: class {}, Event: class {},
    IntersectionObserver: class { observe() {} disconnect() {} },
    MutationObserver: class { observe() {} disconnect() {} },
    ResizeObserver: class { observe() {} disconnect() {} },
    getComputedStyle: () => ({ getPropertyValue: () => '' }),
    localStorage: { getItem: () => null, setItem() {}, removeItem() {} },
    history: { replaceState() {}, pushState() {} },
    console: { error(e) { failure = failure || e; }, log() {}, warn() {} },
    module: undefined,
  };
  sandbox.globalThis = sandbox;
  vm.createContext(sandbox);
  vm.runInContext(SRC, sandbox, { filename: 'page.js' });   // a top-level throw fails the test outright
  // fetch resolves in microtasks, so the whole chain has settled once the timer fires.
  return new Promise(resolve => setTimeout(() => resolve({ failure, enhanced: body.dataset.enhanced }), 50));
}

for (const [width, label] of WIDTHS) {
  for (const page of PAGES) {
    test(`${page} renders at ${label} width (${width}px)`, async () => {
      const { failure, enhanced } = await render(page, width);
      assert.equal(failure, null, `the page fell back to its error sentence: ${failure && (failure.stack || failure)}`);
      assert.equal(enhanced, 'true', 'the render chain did not run to completion');
    });
  }
}
