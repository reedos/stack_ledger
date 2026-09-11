// A collapsed section used to show its title twice: once as the disclosure's own summary and once
// as the heading still sitting inside the panel that opens. Reported from a phone on 2026-09-11,
// on the builder groups and on every collapsed agenda section.
const test = require('node:test'); const assert = require('node:assert');
const fs = require('fs'); const path = require('path');

const src = fs.readFileSync(path.join(__dirname, '..', 'site', 'assets', 'browsing.js'), 'utf8');
const body = src.slice(src.indexOf('function disclosureAround'), src.indexOf('function compactCompanies'));

function element(tag) {
  const el = {
    nodeType: 1, tagName: tag.toUpperCase(), className: '', children: [], parent: null, _text: '',
    append(...nodes) {
      for (const node of nodes) {
        if (node.parent) node.parent.detach(node);
        node.parent = el; el.children.push(node);
      }
    },
    detach(node) { el.children = el.children.filter(c => c !== node); },
    before(node) {
      const parent = el.parent; const at = parent.children.indexOf(el);
      if (node.parent) node.parent.detach(node);
      node.parent = parent; parent.children.splice(at, 0, node);
    },
    get textContent() { return el._text || el.children.map(c => c.textContent).join(''); },
    set textContent(value) { el._text = value; el.children = []; },
  };
  return el;
}
const document = { createElement: element };
const disclosureAround = new Function('document', body + 'return disclosureAround;')(document);

const walk = (el, out = []) => { out.push(el); el.children.forEach(c => walk(c, out)); return out; };
const headings = el => walk(el).filter(n => n.tagName === 'H3');

function tree() {
  const root = element('div'), group = element('section'), heading = element('h3');
  heading.textContent = 'U.S. private data-center construction spending';
  const chart = element('figure');
  group.append(heading, chart); root.append(group);
  return { root, group, heading, chart };
}

test('a heading passed as an element is moved into the summary, not copied', () => {
  const { root, group, heading } = tree();
  disclosureAround([group], heading);
  const found = headings(root);
  assert.strictEqual(found.length, 1, 'the heading must exist exactly once in the document');
  assert.strictEqual(found[0], heading);
  assert.strictEqual(found[0].parent.tagName, 'SUMMARY', 'the heading belongs to the summary now');
});

test('the title is not rendered twice anywhere in the tree', () => {
  const { root, heading, group } = tree();
  const title = heading.textContent;
  disclosureAround([group], heading);
  const showing = walk(root).filter(n => n._text === title);
  assert.strictEqual(showing.length, 1, 'exactly one node may carry the title text');
});

test('the wrapped content still opens under the summary', () => {
  const { root, group, chart } = tree();
  const details = disclosureAround([group], group.children[0]);
  assert.strictEqual(details.tagName, 'DETAILS');
  assert.strictEqual(root.children[0], details, 'the disclosure replaces the group in place');
  assert.strictEqual(details.children[1], group, 'the group sits after the summary');
  assert.ok(walk(details).includes(chart), 'the panel content is still inside');
});

test('a plain string title still works for the literal-label call sites', () => {
  const { root, group } = tree();
  disclosureAround([group], 'Evidence, scope & additional measures');
  const summary = root.children[0].children[0];
  assert.strictEqual(summary.tagName, 'SUMMARY');
  assert.strictEqual(summary.textContent, 'Evidence, scope & additional measures');
});

test('an empty node list makes no disclosure at all', () => {
  assert.strictEqual(disclosureAround([], 'nothing'), undefined);
  assert.strictEqual(disclosureAround([null, undefined], 'nothing'), undefined);
});
