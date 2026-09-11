// A chart slot is one position on the x-axis. Until 2026-09-11 the axis was keyed on the calendar
// year, so a metric with a sub-annual period_basis stacked every reading of a year into one slot:
// six monthly readings of U.S. data-centre construction drawn as overlapping bars with overlapping
// value labels on a phone, and twelve months in a single slot for each grid-demand series.
//
// This evaluates the expressions as they are shipped in site/assets/app.js, so the test cannot pass
// against a copy that has drifted from the file the browser loads.
const test = require('node:test'); const assert = require('node:assert');
const fs = require('fs'); const path = require('path');

const root = path.join(__dirname, '..');
const src = fs.readFileSync(path.join(root, 'site', 'assets', 'app.js'), 'utf8');
const from = src.indexOf('const subAnnual=');
const to = src.indexOf('const slotIndex=', from);
assert.ok(from > 0 && to > from, 'the slot expressions are missing from app.js');
const expressions = src.slice(from, src.indexOf(';', to) + 1);
const slotsFor = new Function('m', 'obs', expressions + ' return {subAnnual,slots,slotOf,slotIndex};');

const ledger = JSON.parse(fs.readFileSync(path.join(root, 'site', 'data', 'ledger.json'), 'utf8'));
const metrics = new Map(ledger.metrics.map(m => [m.id, m]));
const live = ledger.observations.filter(o => !o.superseded_by);
const byMetric = new Map();
for (const o of live) { if (!byMetric.has(o.metric)) byMetric.set(o.metric, []); byMetric.get(o.metric).push(o); }

test('the chart Reed photographed gets one slot per month, not one per year', () => {
  const m = metrics.get('census-dc-construction-saar');
  const obs = byMetric.get('census-dc-construction-saar');
  const { slots, subAnnual } = slotsFor(m, obs);
  assert.strictEqual(subAnnual, true, 'a monthly metric is sub-annual');
  assert.strictEqual(obs.length, 6);
  assert.strictEqual(slots.length, 6, 'six readings need six slots; they used to share two');
  assert.deepStrictEqual(slots, ['2025-07', '2026-03', '2026-04', '2026-05', '2026-06', '2026-07']);
});

test('no sub-annual metric ever puts two readings in one slot', () => {
  const crowded = [];
  for (const [id, obs] of byMetric) {
    const m = metrics.get(id); if (!m) continue;
    const { slots, slotOf, subAnnual } = slotsFor(m, obs);
    if (!subAnnual) continue;
    const perSlot = new Map();
    for (const o of obs) perSlot.set(slotOf(o), (perSlot.get(slotOf(o)) || 0) + 1);
    const worst = Math.max(...perSlot.values());
    if (worst > 1) crowded.push(`${id}: ${worst} readings share a slot`);
    assert.ok(slots.length >= 1);
  }
  assert.deepStrictEqual(crowded, [], 'every reading needs its own position');
});

test('slots are in chronological order for every period format the validator allows', () => {
  const cases = [
    { basis: 'month', periods: ['2026-07', '2025-07', '2026-03'], expect: ['2025-07', '2026-03', '2026-07'] },
    { basis: 'quarter', periods: ['2024-Q4', '2024-Q1', '2025-Q2'], expect: ['2024-Q1', '2024-Q4', '2025-Q2'] },
    { basis: 'snapshot', periods: ['2026-01-11', '2025-12-28', '2025-11-30'], expect: ['2025-11-30', '2025-12-28', '2026-01-11'] },
  ];
  for (const c of cases) {
    const obs = c.periods.map(p => ({ period: p, year: +p.slice(0, 4) }));
    const { slots } = slotsFor({ period_basis: c.basis }, obs);
    assert.deepStrictEqual(slots, c.expect, c.basis);
  }
});

test('a yearly metric is untouched: still numeric, still one slot per year', () => {
  const obs = [{ year: 2030, period: '2030' }, { year: 2024, period: '2024' }, { year: 2025, period: '2025' }];
  const { slots, subAnnual } = slotsFor({ period_basis: null }, obs);
  assert.strictEqual(subAnnual, false);
  assert.deepStrictEqual(slots, [2024, 2025, 2030], 'years sort numerically, not as text');
});

test('a yearly metric with a free-text period keeps using the year', () => {
  // "Year-end 2023" and "Commercial operation · July 2024" are real periods in this catalog.
  const obs = [{ year: 2024, period: 'Year-end 2024' }, { year: 2023, period: 'Year-end 2023' }];
  const { slots, slotOf } = slotsFor({ period_basis: null }, obs);
  assert.deepStrictEqual(slots, [2023, 2024]);
  assert.strictEqual(slotOf(obs[0]), 2024);
});

test('nothing still groups bars by calendar year', () => {
  assert.ok(!src.includes('obs.filter(o=>o.year===year)'), 'bars must be grouped by slot');
  assert.ok(!src.includes('xOf=year=>'), 'the x position must be keyed on the slot');
});
