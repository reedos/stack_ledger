"""Maintainer tool for measured electricity demand by grid operator (EIA-930). No model calls.

PJM's own planning API (Data Miner 2) needs a registered account and its load forecast is a PDF,
so a forecast series is still waiting on the owner (`research/grid-operators.json`). What is
available today, under the owner's already-registered EIA key, is better evidence than a forecast:
EIA-930 publishes each balancing authority's *measured* demand, so the site can show what the grid
in each region actually carried while the data centres were being built.

EIA publishes this route hourly and daily only, never monthly, so this importer derives two monthly
figures from EIA's own published daily values and says so in every record's note:

  * average daily demand  -- the mean of that month's daily totals
  * highest daily demand  -- the largest daily total in that month

Both are a day's energy in MWh, never an instantaneous peak in megawatts.

A month is recorded only when EIA has published every day of it, so a part-month never looks like a
fall in demand. One timezone facet per operator keeps EIA's local-time breakdown from double
counting a day.

    python scripts/import_grid_demand.py            # report what would change
    python scripts/import_grid_demand.py --apply    # register the source, add metrics and records, rebuild
"""
import argparse
import calendar
import collections
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import research
from research import load, save, now, require, UA
import api_access
from importer_common import apply_changes

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOTS = ROOT/'research/grid'
ROUTE = 'https://api.eia.gov/v2/electricity/rto/daily-region-data/data/'
SOURCE_ID = 'eia-930-demand'
SOURCE = {'id': SOURCE_ID, 'publisher': 'U.S. Energy Information Administration',
          'title': 'Hourly and daily electric grid monitor (EIA-930) · demand by balancing authority',
          'url': 'https://www.eia.gov/electricity/gridmonitor/', 'published': None,
          'layers': ['energy', 'infrastructure'], 'license': 'Public domain (U.S. government work)', 'provenance': 'official'}
START_YEAR = 2019
# (EIA respondent code, our slug, display name, the timezone facet that covers the operator's own
# footprint; EIA reports a row per local timezone, so one facet per operator counts each day once)
OPERATORS = [('PJM', 'pjm', 'PJM Interconnection', 'Eastern'),
             ('ERCO', 'ercot', 'ERCOT', 'Central'),
             ('MISO', 'miso', 'MISO', 'Central'),
             ('SWPP', 'spp', 'Southwest Power Pool', 'Central')]
SERIES = [('average', 'grid_monthly_average_daily_demand_mwh', 'average daily demand'),
          ('peak', 'grid_monthly_max_daily_demand_mwh', 'highest daily demand')]
PAGE = 5000


def data_url(respondent, timezone, offset=0):
    return (f'{ROUTE}?frequency=daily&data[0]=value&facets[respondent][]={respondent}&facets[type][]=D'
            f'&facets[timezone][]={timezone}&start={START_YEAR}-01-01&sort[0][column]=period&sort[0][direction]=asc'
            f'&offset={offset}&length={PAGE}')


def parse(body):
    import json
    payload = json.loads(body.decode('utf-8'))['response']
    return payload.get('data') or [], int(payload.get('total') or 0)


def daily_values(rows):
    """{'YYYY-MM-DD': megawatthours}. A duplicate day keeps the first published value."""
    out = {}
    for r in rows:
        period = str(r.get('period') or '')
        if len(period) != 10 or period[:4] < str(START_YEAR):
            continue
        raw = r.get('value')
        if raw in (None, '', 'NA', 'w'):
            continue
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        if value <= 0:
            continue
        out.setdefault(period, value)
    return out


def complete_months(days):
    """{'YYYY-MM': [values]} for months EIA has published in full; a part month is left out."""
    grouped = collections.defaultdict(dict)
    for day, value in days.items():
        grouped[day[:7]][day] = value
    complete = {}
    for month, values in grouped.items():
        year, mon = int(month[:4]), int(month[5:7])
        if len(values) == calendar.monthrange(year, mon)[1]:
            complete[month] = values
    return complete


def metric_definition(slug, name, kind):
    measurement = dict((k, t) for k, t, _ in [(s[0], s[1], s[2]) for s in SERIES])[kind]
    label = dict((s[0], s[2]) for s in SERIES)[kind]
    return {'id': f'grid-demand-{slug}-{kind}-monthly', 'layer': 'energy',
            'title': f'{name} · {label}, by month (EIA-930)',
            'unit': 'MWh per day (daily demand)', 'geography': name,
            'scope': (f'{name} balancing-authority demand as published by EIA-930, aggregated by this importer to the '
                      f'{label} for the month: the {"mean" if kind == "average" else "largest"} of that month\'s daily totals. '
                      "A day's total energy in MWh, never an instantaneous peak in megawatts. "
                      'Measured demand for the whole balancing authority, not a data-centre figure and not a forecast; '
                      'a month is recorded only when every day of it has been published.'),
            'direction': 'context', 'min': 0, 'max': 5_000_000,
            'note': ('EIA-930 hourly electric grid monitor, public domain, through the owner\'s registered EIA key. '
                     'Monthly points derived from EIA\'s own published daily values; each import appends newly '
                     'completed months and never rewrites earlier ones.'),
            'source_ids': [SOURCE_ID], 'company': None, 'measurement_type': measurement, 'project': None,
            'allowed_statuses': ['observation'], 'period_basis': 'month', 'geography_code': None,
            'series_start_year': START_YEAR, 'chart_default_start': START_YEAR, 'chart_default_end': 2027,
            'definition_stable': True,
            'pre_period_note': f'EIA-930 begins in {START_YEAR} in this catalog; a missing month is unpublished or incomplete, not zero.'}


def records_for(slug, name, days, retrieved_at, sha):
    metrics, observations = {}, []
    for month, values in sorted(complete_months(days).items()):
        stats = {'average': round(sum(values.values())/len(values)), 'peak': round(max(values.values()))}
        for kind, _, _ in SERIES:
            mid = f'grid-demand-{slug}-{kind}-monthly'
            metrics.setdefault(mid, metric_definition(slug, name, kind))
            observations.append({'id': f'{mid}-{month}', 'metric': mid, 'year': int(month[:4]), 'period': month,
                                  'value': stats[kind], 'upper': None, 'status': 'observation', 'source': SOURCE_ID,
                                  'precision': 'eq', 'retrieved_at': retrieved_at, 'method': 'curated',
                                  'note': (f'EIA-930 {name} demand, {month}: {kind} of {len(values)} published daily values '
                                           f'({stats[kind]:,} MWh). Response sha256 {sha[:12]}.')[:300]})
    return metrics, observations


def run(apply=False):
    require(api_access.key('eia'), 'EIA API key missing from .local/api-keys.json')
    retrieved = now()
    private = research.LOCAL/'grid'; private.mkdir(parents=True, exist_ok=True)
    all_metrics, all_obs, calls = {}, [], []
    for respondent, slug, name, timezone in OPERATORS:
        rows, offset, total = [], 0, None
        while total is None or offset < total:
            try:
                body = api_access.fetch(data_url(respondent, timezone, offset), UA)
            except Exception as e:
                calls.append({'operator': slug, 'offset': offset, 'status': type(e).__name__}); break
            sha = hashlib.sha256(body).hexdigest()
            (private/f'{slug}-{offset}-{sha[:12]}.json').write_bytes(body)
            page, total = parse(body)
            rows += page
            calls.append({'operator': slug, 'offset': offset, 'status': 'ok', 'rows': len(page), 'total': total, 'sha256': sha})
            offset += PAGE
            if not page:
                break
        if not rows:
            continue
        metrics, observations = records_for(slug, name, daily_values(rows), retrieved, sha)
        all_metrics.update(metrics); all_obs += observations
    SNAPSHOTS.mkdir(exist_ok=True)
    snapshot = {'dataset': 'EIA-930 demand by balancing authority', 'source_id': SOURCE_ID,
                'retrieved_at': retrieved, 'operators': [o[1] for o in OPERATORS], 'calls': calls,
                'metrics': sorted(all_metrics), 'records': len(all_obs),
                'license': 'Public domain (U.S. government work)', 'key': 'owner-registered, not recorded'}
    save(SNAPSHOTS/'demand.json', snapshot)
    ledger = load(ROOT/'site/data/ledger.json'); catalog = load(ROOT/'research/catalog.json')
    known = {m['id'] for m in catalog['metrics']}; existing = {o['id'] for o in ledger['observations']}
    new_metrics = [m for mid, m in sorted(all_metrics.items()) if mid not in known]
    new_obs = [o for o in all_obs if o['id'] not in existing]
    ok = sum(1 for c in calls if c['status'] == 'ok')
    latest = max((o['period'] for o in all_obs), default=None)
    print(f'operators {len(OPERATORS)} · api calls ok {ok}/{len(calls)} · metrics {len(all_metrics)} ({len(new_metrics)} new) · '
          f'records {len(all_obs)} ({len(new_obs)} new) · latest complete month {latest}', flush=True)
    if not apply:
        return {'metrics': new_metrics, 'records': new_obs}
    registry = load(ROOT/'research/sources.json')
    apply_changes(ROOT, importer_id='grid-demand',
                  new_sources=[SOURCE] if SOURCE_ID not in {s['id'] for s in registry['sources']} else (),
                  collection_entries={SOURCE_ID: {'rank': 1, 'region_book': 'united-states', 'company_id': None,
                                                   'claim_type': 'other', 'cadence': 'manual', 'weekday': 0,
                                                   'path_prefixes': [], 'topics': [], 'excerpts': False}},
                  region_book='united-states', new_metrics=new_metrics, new_observations=new_obs,
                  snapshot=snapshot)
    return {'metrics': new_metrics, 'records': new_obs}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0]); p.add_argument('--apply', action='store_true')
    a = p.parse_args(argv); run(apply=a.apply); return 0


if __name__ == '__main__':
    sys.exit(main())
