// Grade C and D readings are allowed into numeric series on one condition: that we are honest
// about sourcing. Honest means named at the surface, not recorded in a field somewhere.
//
// Measured 2026-09-12: 380 live observations across 123 metrics were analyst, news or social
// sourced, and every one of them was drawn as an ordinary bar and counted in the chart legend's
// "Reported" bucket beside official statistics. A reader had nothing to tell them apart.
//
// This evaluates the expressions as shipped in site/assets/app.js, so it cannot pass against a
// copy that has drifted from the file the browser loads.
const test = require('node:test'); const assert = require('node:assert');
const fs = require('fs'); const path = require('path');

const root = path.join(__dirname, '..');
const src = fs.readFileSync(path.join(root, 'site', 'assets', 'app.js'), 'utf8');

const from = src.indexOf('const PROVENANCE_GRADE=');
const to = src.indexOf('if(typeof module', from);
assert.ok(from > 0 && to > from, 'the provenance helpers are missing from app.js');
const SOURCES = {
  bls: {id: 'bls', provenance: 'official', publisher: 'BLS'},
  filing: {id: 'filing', provenance: 'regulated-filing', publisher: 'SEC'},
  channel: {id: 'channel', provenance: 'company-channel', publisher: 'Anthropic'},
  analyst: {id: 'analyst', provenance: 'analyst', publisher: 'SemiAnalysis'},
  outlet: {id: 'outlet', provenance: 'news', publisher: 'Associated Press'},
  post: {id: 'post', provenance: 'social', publisher: 'Waymo'},
};
const helpers = new Function('sourceOf', 'esc',
  src.slice(from, to) + ' return {lowGrade,sourceClassOf,gradeOf,PROVENANCE_LABEL,PROVENANCE_GRADE,valueGradeBadge};'
)(id => SOURCES[id], s => String(s));
const ob = source => ({source, metric: 'm', status: 'observation', period: '2026', value: 1});

test('a low grade is exactly C or D, and nothing better is flagged', () => {
  assert.equal(helpers.lowGrade(ob('analyst')), true, 'analyst is grade C');
  assert.equal(helpers.lowGrade(ob('outlet')), true, 'news is grade C');
  assert.equal(helpers.lowGrade(ob('post')), true, 'social is grade D');
  for (const clean of ['bls', 'filing', 'channel']) {
    assert.equal(helpers.lowGrade(ob(clean)), false, clean + ' must not be marked low grade');
  }
});

test('a low-grade reading names the kind of source it came from', () => {
  assert.equal(helpers.sourceClassOf(ob('outlet')), 'News report');
  assert.equal(helpers.sourceClassOf(ob('post')), 'Social post');
  assert.equal(helpers.sourceClassOf(ob('analyst')), 'Analyst or trade estimate');
});

// ---- the legend, which is where the conflation actually lived ----
const lfrom = src.indexOf('const legendBucketOf=');
const lto = src.indexOf('const legendHtml=', lfrom);
assert.ok(lfrom > 0 && lto > lfrom, 'the legend expressions are missing from app.js');
const legendFor = obs => new Function('obs', 'attributionLabel', 'lowGrade', 'sourceClassOf',
  src.slice(lfrom, lto) + ' return {legendBucketOf,legendPresent,legendOrder};'
)(obs, () => 'Reported observation', helpers.lowGrade, helpers.sourceClassOf);

test('a news-sourced point is no longer counted as a plain reported observation', () => {
  const l = legendFor([ob('bls'), ob('outlet'), ob('post'), ob('analyst')]);
  assert.equal(l.legendBucketOf(ob('bls')), 'Reported');
  assert.equal(l.legendBucketOf(ob('outlet')), 'News report');
  assert.equal(l.legendBucketOf(ob('post')), 'Social post');
  assert.equal(l.legendBucketOf(ob('analyst')), 'Analyst or trade estimate');
  assert.ok(l.legendPresent.has('News report') && l.legendPresent.has('Reported'),
            'both classes appear in the legend of a mixed chart');
});

test('every low-grade class has its own swatch instead of falling through to the forecast hatch', () => {
  // app.js gives an unlisted legend label 'legend-swatch forecast' -- a hatched swatch that means
  // projection. A news reading wearing it would be mislabelled, not merely unlabelled.
  const l = legendFor([ob('outlet')]);
  const listed = new Map(l.legendOrder);
  for (const [provenance, grade] of Object.entries(helpers.PROVENANCE_GRADE)) {
    if (grade !== 'C' && grade !== 'D') continue;
    const label = helpers.PROVENANCE_LABEL[provenance];
    assert.ok(listed.has(label), `${label} (grade ${grade}) has no legend swatch`);
    assert.ok(!/forecast/.test(listed.get(label)),
              `${label} would render with the forecast hatch: ${listed.get(label)}`);
  }
});

test('the published script is the one under test', () => {
  // Compared by digest: a full-text assertion on a 100KB bundle buries the one useful fact
  // (that the copies differ) under the whole file.
  const crypto = require('node:crypto');
  const sum = text => crypto.createHash('sha256').update(text).digest('hex').slice(0, 16);
  const shipped = fs.readFileSync(path.join(root, 'docs', 'assets', 'app.js'), 'utf8');
  assert.equal(sum(src), sum(shipped),
               `docs/assets/app.js is what the public site serves; run scripts/build.py `
               + `(site=${sum(src)} docs=${sum(shipped)})`);
});
