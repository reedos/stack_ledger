"""Maintainer importer for Census Quarterly Services Survey revenue, software industries. No model calls.

QSS surveys employer firms for quarterly operating revenue by industry. Paired with the BLS CES
employment this catalog already imports, it gives revenue per employee for the same industry --
a ratio of a population to itself.

Why this exists. A widely circulated 3Fourteen Research chart (2026-09) divides trailing-12-month
sales of S&P 1500 GICS Application Software constituents by BLS Software Publishers payrolls and
reads the post-2023 steepening as an AI productivity effect. That numerator cannot be reproduced
here: GICS sub-industry classification and S&P 1500 membership are licensed, a fixed basket of
today's filers carries survivorship bias, and SEC XBRL frames were measured on 2026-09-13 to yield
no complete trailing-twelve-month window at all for 8 of 18 candidate filers, because Q4 is not
separately reported. More to the point, that ratio puts global public-company revenue over
U.S.-establishment headcount: two different populations.

QSS avoids all of it. Both series are official U.S. establishment measures of the same named
industry, free, keyless-capable and reproducible by anyone. Measured on the matched data, the
chart's qualitative finding holds and is sharper: revenue per software-publisher employee moved
+$3,218/year over 2015-2022 (the chart fits +$2,454 on its own construction) and +$105,613/year
over 2023-2026.

Known limitation, stated in the metric note as well. QSS still codes this industry 5112, the
NAICS 2017 number; CES codes it 5132 under NAICS 2022, which moved some software-as-a-service
providers in from data processing. The two are the same industry by name and each series is
internally consistent across this window -- there is no level break in either -- but the ratio's
LEVEL should be read as approximate. Its trend is the claim.

    python scripts/import_qss.py            # fetch and report what would change
    python scripts/import_qss.py --apply    # register the source, add metrics and records, rebuild
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from research import load, save, now, require, UA

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOTS = ROOT/'research/qss'
SOURCE_ID = 'census-qss-api'
SOURCE = {'id': SOURCE_ID, 'publisher': 'U.S. Census Bureau',
          'title': 'Quarterly Services Survey · time series API',
          'url': 'https://www.census.gov/data/developers/data-sets/qss.html', 'published': None,
          'layers': ['applications', 'models'],
          'license': 'Public domain (U.S. government work)', 'provenance': 'official'}

BASE = 'https://api.census.gov/data/timeseries/eits/qss'
# `time` and the predicate columns are appended by the API itself; asking for `time` in get is a 400.
GET = 'cell_value,category_code,data_type_code,time_slot_id,seasonally_adj'
FIRST_YEAR = 2015

# QSS category -> (metric id, label, the CES employment metric to divide by, if any).
CATEGORIES = {
    '5112T': ('qss-us-software-publishers-revenue', 'Software Publishers',
              'ces-us-software-publishers-employment',
              'qss-us-software-publishers-revenue-per-employee'),
    '5415T': ('qss-us-computer-systems-design-revenue', 'Computer Systems Design and Related Services',
              'ces-us-computer-systems-design-employment',
              'qss-us-computer-systems-design-revenue-per-employee'),
}
SUPPRESSED = {'S', 'D', 'N', 'X', ''}


def fetch_revenue(category, last_year, adjusted='yes'):
    """{'YYYY-Qn': revenue in $ millions} for one QSS category, seasonally adjusted.

    Census marks a cell it cannot publish with a letter code; those quarters are omitted, never
    recorded as zero. The response repeats the predicate columns after the requested ones, so
    column positions are taken from each name's FIRST appearance in the header.
    """
    import api_access
    url = (f'{BASE}?get={GET}&for=us:*&category_code={category}'
           f'&data_type_code=QREV&time=from+{FIRST_YEAR}')
    require(api_access.allowed(url) is not None, 'QSS URL is not a listed statistical API path')
    rows = json.loads(api_access.fetch(url, UA))
    require(isinstance(rows, list) and rows and isinstance(rows[0], list), 'Unexpected QSS response shape')
    first = {}
    for i, name in enumerate(rows[0]):
        first.setdefault(name, i)
    for column in ('cell_value', 'seasonally_adj', 'time'):
        require(column in first, f'QSS response has no {column} column')
    out = {}
    for row in rows[1:]:
        if row[first['seasonally_adj']] != adjusted:
            continue
        value = row[first['cell_value']]
        if value in SUPPRESSED:
            continue
        try:
            out[row[first['time']]] = float(value)
        except ValueError:
            continue
    require(out, f'QSS returned no usable quarters for {category}')
    return out


def revenue_metric(metric_id, label, category):
    return {
        'id': metric_id, 'layer': 'applications',
        'title': f'United States · quarterly operating revenue, {label}',
        'unit': 'USD millions per quarter', 'geography': 'United States',
        'scope': (f'Census Quarterly Services Survey estimated quarterly operating revenue for '
                  f'employer firms in {label} (QSS category {category}), seasonally adjusted. A '
                  'sample survey of U.S. employer firms, so every point carries sampling error; '
                  'Census publishes a standard error alongside each estimate. Quarters Census '
                  'suppresses are omitted, never recorded as zero.'),
        'direction': 'context', 'min': 0, 'max': 2_000_000,
        'note': ('Census Quarterly Services Survey, public domain. QSS revises earlier quarters as '
                 'later responses arrive and rebenchmarks annually, so a quarter already held is '
                 'replaced on each import rather than appended twice.'),
        'source_ids': [SOURCE_ID], 'company': None,
        'measurement_type': 'qss_industry_revenue_usd_m', 'project': None,
        'allowed_statuses': ['observation'], 'period_basis': 'quarter',
        'geography_code': None, 'series_start_year': FIRST_YEAR,
        'chart_default_start': FIRST_YEAR, 'chart_default_end': datetime.now(timezone.utc).year,
        'definition_stable': True,
        'pre_period_note': (f'Series begins {FIRST_YEAR} in this catalog; QSS publishes this '
                            'industry earlier and those quarters can be imported on review.'),
    }


def ratio_metric(metric_id, label, category, employment_metric):
    return {
        'id': metric_id, 'layer': 'applications',
        'title': f'United States · revenue per employee, {label}',
        'unit': 'USD per employee per year', 'geography': 'United States',
        'scope': (f'Census QSS quarterly operating revenue for {label} ({category}), annualised by '
                  f'multiplying by four, divided by BLS CES employment in the same industry for the '
                  f'same quarter ({employment_metric}). Both are official U.S. establishment '
                  'measures of the same named industry, so this is one population divided by '
                  'itself. Computed only for quarters where both series publish a value.'),
        'direction': 'context', 'min': 0, 'max': 5_000_000,
        'note': ('Derived from two public-domain federal series, each recorded separately in this '
                 'catalog. Read the TREND, not the level: QSS still codes this industry under the '
                 'NAICS 2017 number (5112) while CES codes it under NAICS 2022 (5132), which moved '
                 'some software-as-a-service providers in from data processing, so the two '
                 'populations may not be identical even though each is internally consistent across '
                 'the window. Annualising one quarter assumes the other three resemble it, which '
                 'seasonal adjustment makes reasonable but does not guarantee.'),
        'source_ids': [SOURCE_ID], 'company': None,
        'measurement_type': 'industry_revenue_per_employee_usd', 'project': None,
        'allowed_statuses': ['observation'], 'period_basis': 'quarter',
        'geography_code': None, 'series_start_year': FIRST_YEAR,
        'chart_default_start': FIRST_YEAR, 'chart_default_end': datetime.now(timezone.utc).year,
        'definition_stable': True,
        'pre_period_note': (f'Series begins {FIRST_YEAR} in this catalog, bounded by the CES and QSS '
                            'quarters imported here rather than by either survey.'),
    }


def run(apply=False, today=None):
    today = today or datetime.now(timezone.utc).date()
    catalog = load(ROOT/'research/catalog.json')
    registry = load(ROOT/'research/sources.json')
    ledger = load(ROOT/'site/data/ledger.json')
    retrieved = now()

    employment = {}
    for observation in ledger['observations']:
        employment.setdefault(observation['metric'], {})[observation['period']] = observation['value']

    all_metrics, all_obs, routes = {}, [], {}
    for category, (rev_id, label, emp_id, ratio_id) in sorted(CATEGORIES.items()):
        try:
            revenue = fetch_revenue(category, today.year)
        except Exception as exc:
            routes[f'rows:{category}'] = 0
            print(f'  {category} FAILED {type(exc).__name__}: {str(exc)[:160]}', flush=True)
            continue
        routes[f'rows:{category}'] = len(revenue)
        all_metrics[rev_id] = revenue_metric(rev_id, label, category)
        for period in sorted(revenue):
            year, quarter = period.split('-Q')
            all_obs.append({
                'id': f'{rev_id}-{year}q{quarter}', 'metric': rev_id, 'year': int(year),
                'period': period, 'value': int(round(revenue[period])), 'upper': None,
                'status': 'observation', 'source': SOURCE_ID, 'precision': 'eq',
                'retrieved_at': retrieved, 'method': 'curated',
                'note': (f'Census QSS category {category}, {period}, estimated quarterly operating '
                         f'revenue, seasonally adjusted.')[:300],
            })

        jobs = employment.get(emp_id, {})
        shared = sorted(set(revenue) & set(jobs))
        routes[f'ratio:{category}'] = len(shared)
        if not shared:
            print(f'  {category} revenue {len(revenue)} quarters; no matching {emp_id} quarters, '
                  'ratio skipped', flush=True)
            continue
        all_metrics[ratio_id] = ratio_metric(ratio_id, label, category, emp_id)
        for period in shared:
            year, quarter = period.split('-Q')
            per_employee = revenue[period]*1_000_000*4/jobs[period]
            all_obs.append({
                'id': f'{ratio_id}-{year}q{quarter}', 'metric': ratio_id, 'year': int(year),
                'period': period, 'value': int(round(per_employee)), 'upper': None,
                'status': 'observation', 'source': SOURCE_ID, 'precision': 'approx',
                'retrieved_at': retrieved, 'method': 'curated',
                'note': (f'QSS {category} revenue ${revenue[period]:,.0f}M for {period}, annualised, '
                         f'over CES employment of {jobs[period]:,} in the same quarter.')[:300],
            })
        print(f'  {category} {label}: {len(revenue)} revenue quarters, {len(shared)} with employment; '
              f'latest {shared[-1]} = ${per_employee:,.0f} per employee', flush=True)

    SNAPSHOTS.mkdir(parents=True, exist_ok=True)
    snapshot = {'dataset': 'Census Quarterly Services Survey', 'source_id': SOURCE_ID,
                'retrieved_at': retrieved, 'categories': {k: v[0] for k, v in CATEGORIES.items()},
                'first_year': FIRST_YEAR, 'routes': routes, 'records': len(all_obs),
                'license': 'Public domain (U.S. government work)'}
    save(SNAPSHOTS/'qss.json', snapshot)

    from importer_common import check_floors, report_drift
    counts = dict(routes, records=len(all_obs))
    failures = check_floors(ROOT, 'qss', counts)
    drift = report_drift(ROOT, 'qss', all_obs, ledger['observations'])

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
    apply_changes(ROOT, importer_id='qss',
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
