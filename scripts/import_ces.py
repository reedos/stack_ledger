"""Maintainer importer for BLS Current Employment Statistics, software industries. No model calls.

CES is the monthly payroll survey: employees on nonfarm payrolls, counted from establishment
records rather than a household survey. This importer records quarter-end employment for the
three industries that describe where software labour is counted:

  5132   Software Publishers (formerly 5112)
  5415   Computer Systems Design and Related Services
  50     Information supersector (the total 5132 sits inside)

Why these three together. A single industry's headcount cannot say whether software employment
stopped growing or merely moved: 5132 excludes the custom-software and systems-design workers who
sit in 5415, so the two must be read side by side. Measured 2026-09-13, they broke at the same
time -- 5132 grew 37.4% over 2019-2022 then 2.2% over 2022-2025, while 5415 went +11.8% to -2.2%
and Information overall +6.9% to -6.6%. Labour did not move between them; it stopped being added
to all three at once.

Quarter-end sampling (the third month of each quarter) rather than all twelve months, matching how
this series is conventionally read against quarterly financial data and keeping one industry from
adding 240 rows to the ledger.

Seasonally adjusted. The NSA series was compared over the full window on 2026-09-13 and agrees to
within 0.3k on annual averages, so the adjustment carries no weight here; SA is used because it is
the series BLS headlines and the one a quarter-end sample would otherwise distort.

    python scripts/import_ces.py            # fetch and report what would change
    python scripts/import_ces.py --apply    # register the source, add metrics and records, rebuild
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import research
from research import load, save, now, require, UA

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOTS = ROOT/'research/ces'
SOURCE_ID = 'bls-ces-employment'
SOURCE = {'id': SOURCE_ID, 'publisher': 'U.S. Bureau of Labor Statistics',
          'title': 'Current Employment Statistics · national industry employment',
          'url': 'https://www.bls.gov/ces/', 'published': None,
          'layers': ['applications', 'models'],
          'license': 'Public domain (U.S. government work)', 'provenance': 'official'}

# BLS series id -> (metric id, industry label, NAICS code as published).
SERIES = {
    'CES5051320001': ('ces-us-software-publishers-employment', 'Software Publishers', '5132'),
    'CES6054150001': ('ces-us-computer-systems-design-employment',
                      'Computer Systems Design and Related Services', '5415'),
    'CES5000000001': ('ces-us-information-employment', 'Information supersector', '50'),
}
FIRST_YEAR = 2015
QUARTER_END = {'M03': 1, 'M06': 2, 'M09': 3, 'M12': 4}
API = 'https://api.bls.gov/publicAPI/v2/timeseries/data/'


def fetch(series_id, first_year, last_year):
    """One CES series from the BLS v2 timeseries API, a listed statistical path in
    research/api-access.json. api_access supplies the owner's registered key and redacts it from
    the response; this function never sees it."""
    import api_access
    url = f'{API}{series_id}?startyear={first_year}&endyear={last_year}&catalog=false'
    require(api_access.allowed(url) is not None, 'CES URL is not a listed statistical API path')
    body = api_access.fetch(url, UA)
    payload = json.loads(body)
    status = payload.get('status')
    require(status == 'REQUEST_SUCCEEDED',
            f'BLS API returned {status}: {"; ".join(payload.get("message") or [])[:200]}')
    series = payload.get('Results', {}).get('series') or []
    require(series and series[0].get('data'), f'BLS returned no observations for {series_id}')
    return series[0]['data']


def quarter_points(data):
    """(year, quarter, jobs) for each quarter-end month, newest first in BLS order.

    BLS reports thousands of jobs to one decimal; these are stored as whole jobs. M13 is the
    annual average, not a month, and is skipped. A value BLS has not yet published simply does
    not appear -- absence is never recorded as zero.
    """
    out = []
    for point in data:
        quarter = QUARTER_END.get(point.get('period'))
        if quarter is None:
            continue
        try:
            jobs = int(round(float(point['value'])*1000))
        except (TypeError, ValueError):
            continue
        out.append((int(point['year']), quarter, jobs))
    return sorted(out)


def metric_definition(metric_id, label, naics):
    supersector = naics == '50'
    return {
        'id': metric_id, 'layer': 'applications',
        'title': f'United States · employment, {label}'+('' if supersector else f' (NAICS {naics})'),
        'unit': 'jobs (seasonally adjusted)', 'geography': 'United States',
        'scope': (f'BLS Current Employment Statistics, all employees on nonfarm payrolls in '
                  f'{"the Information supersector" if supersector else f"NAICS {naics} ({label})"}, '
                  'seasonally adjusted, sampled at the third month of each quarter. An establishment '
                  'survey of payroll records covering U.S. employees only, counting jobs rather than '
                  'people: someone holding two payroll jobs is counted twice. Read alongside the '
                  'other two CES industries in this catalog, since one industry alone cannot '
                  'distinguish software employment stopping from software employment moving.'),
        'direction': 'context', 'min': 0, 'max': 10_000_000,
        'note': ('BLS Current Employment Statistics, public domain. CES revises the two most recent '
                 'months with each release and rebenchmarks annually, so recent quarters can change; '
                 'each import replaces a quarter it already holds rather than appending a second '
                 'reading. History is published on the current NAICS basis, so the 5112-to-5132 '
                 'renumbering is not a break in this series.'),
        'source_ids': [SOURCE_ID], 'company': None,
        'measurement_type': 'ces_industry_employment', 'project': None,
        'allowed_statuses': ['observation'], 'period_basis': 'quarter',
        'geography_code': None, 'series_start_year': FIRST_YEAR,
        'chart_default_start': FIRST_YEAR, 'chart_default_end': datetime.now(timezone.utc).year,
        'definition_stable': True,
        'pre_period_note': (f'Series begins {FIRST_YEAR} in this catalog; CES publishes this industry '
                            'back to 1990 and earlier quarters can be imported on review.'),
    }


def run(apply=False, today=None):
    today = today or datetime.now(timezone.utc).date()
    catalog = load(ROOT/'research/catalog.json')
    registry = load(ROOT/'research/sources.json')
    ledger = load(ROOT/'site/data/ledger.json')
    retrieved = now()

    all_metrics, all_obs, routes = {}, [], {}
    for series_id, (metric_id, label, naics) in sorted(SERIES.items()):
        try:
            data = fetch(series_id, FIRST_YEAR, today.year)
        except Exception as exc:
            routes[f'rows:{naics}'] = 0
            print(f'  {series_id} FAILED {type(exc).__name__}: {str(exc)[:160]}', flush=True)
            continue
        points = quarter_points(data)
        routes[f'rows:{naics}'] = len(points)
        metric = metric_definition(metric_id, label, naics)
        all_metrics[metric_id] = metric
        for year, quarter, jobs in points:
            all_obs.append({
                'id': f'{metric_id}-{year}q{quarter}', 'metric': metric_id, 'year': year,
                'period': f'{year}-Q{quarter}', 'value': jobs, 'upper': None,
                'status': 'observation', 'source': SOURCE_ID, 'precision': 'eq',
                'retrieved_at': retrieved, 'method': 'curated',
                'note': (f'BLS CES series {series_id}, {year} Q{quarter} (third month of quarter), '
                         f'all employees, seasonally adjusted.')[:300],
            })
        print(f'  {series_id}  {label}: {len(points)} quarters, '
              f'latest {points[-1][0]} Q{points[-1][1]} = {points[-1][2]:,} jobs', flush=True)

    SNAPSHOTS.mkdir(parents=True, exist_ok=True)
    snapshot = {'dataset': 'BLS Current Employment Statistics', 'source_id': SOURCE_ID,
                'retrieved_at': retrieved, 'series': {k: v[0] for k, v in SERIES.items()},
                'first_year': FIRST_YEAR, 'routes': routes, 'records': len(all_obs),
                'license': 'Public domain (U.S. government work)'}
    save(SNAPSHOTS/'ces.json', snapshot)

    from importer_common import check_floors, report_drift
    counts = dict(routes, records=len(all_obs))
    failures = check_floors(ROOT, 'ces', counts)
    drift = report_drift(ROOT, 'ces', all_obs, ledger['observations'])

    known = {m['id'] for m in catalog['metrics']}
    new_metrics = [m for mid, m in sorted(all_metrics.items()) if mid not in known]
    existing_ids = {o['id'] for o in ledger['observations']}
    new_obs = [o for o in all_obs if o['id'] not in existing_ids]
    print(f'metrics {len(all_metrics)} ({len(new_metrics)} new) · records {len(all_obs)} '
          f'({len(new_obs)} new) · drift {len(drift)}', flush=True)
    if not apply:
        return {'metrics': new_metrics, 'records': new_obs, 'floor_failures': failures, 'drift': drift}

    from importer_common import apply_changes
    collection_entries = {SOURCE_ID: {'rank': 1, 'region_book': 'united-states', 'company_id': None,
                                      'claim_type': 'labor', 'cadence': 'manual', 'weekday': 0,
                                      'path_prefixes': [], 'topics': [], 'excerpts': False}}
    apply_changes(ROOT, importer_id='ces',
                  new_sources=[SOURCE] if SOURCE_ID not in {s['id'] for s in registry['sources']} else (),
                  collection_entries=collection_entries, region_book='united-states',
                  new_metrics=new_metrics, new_observations=all_obs, snapshot=snapshot)
    print('catalog, registry and ledger updated; site rebuilt', flush=True)
    return {'metrics': new_metrics, 'records': new_obs, 'floor_failures': failures, 'drift': drift}


def main(argv=None):
    from importer_common import DEGRADED_EXIT
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('--apply', action='store_true')
    a = p.parse_args(argv)
    return DEGRADED_EXIT if run(apply=a.apply).get('floor_failures') else 0


if __name__ == '__main__':
    sys.exit(main())
