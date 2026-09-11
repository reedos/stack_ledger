"""Maintainer importer for EIA electricity data via the EIA API v2 (needs a registered key).
No model calls.

Four series, all public domain (U.S. government work):

  * `eia-net-generation-monthly` -- all-fuels monthly net generation, electric power sector
    total (facet sectorid=99), from `/v2/electricity/electric-power-operational-data/data/`.
  * `eia-operating-capacity-additions-monthly-<source>` -- monthly nameplate MW newly reporting
    operating status, one metric per tracked energy source (solar, wind, battery storage,
    natural gas, nuclear), from `/v2/electricity/operating-generator-capacity/data/`.
  * `eia-steo-generation-outlook` -- EIA's Short-Term Energy Outlook total generation, from
    `/v2/steo/data/`, a machine-readable companion to the PDF-curated `us-utility-generation-
    history` metric (never a replacement for it). Status is `observation` for a fully elapsed
    year and `forecast` otherwise, matching this project's existing STEO convention (a current,
    still-elapsing year stays a forecast).
  * `eia-retail-price-<state>-{residential,all}` -- average monthly retail electricity price
    (cents/kWh) from `/v2/electricity/retail-sales/data/`, one pair of metrics per state where
    the catalog places a project (`project_states`, the same reviewed-map derivation
    `import_qcew.project_counties` uses for counties) plus `eia-retail-price-us-{...}` for the
    national figure. This is deliverable A of the grid-interface tracking work (2026-09-10):
    the site's own premise -- whether the AI buildout raises costs for people who live near it
    -- needs a price series next to the load and policy trackers, not just generation and
    capacity context.

`.local/api-keys.json` has no owner-registered EIA key in this environment. Per the owner's
scope for this importer: with no key, this script prints the exact registration URL and exits
0 without making any network call at all -- not even the keyless SEC-style paths some other
importers use, because every EIA v2 route requires the key. The four record-building
functions above are still fully implemented and unit-tested against hand-written fixtures
built from EIA's published API v2 documentation, so the importer is ready the moment the owner
registers a key; nothing here has been exercised against EIA's real response shape.

CONFIRM AGAINST A LIVE PULL BEFORE THE FIRST --apply ONCE A KEY EXISTS:
  * The exact facet/column names below (`fueltypeid`, `sectorid`, `energy_source_code`,
    `operating-year-month`, `nameplate-capacity-mw`) follow EIA API v2's documented general
    conventions but are not confirmed against this project's own live response.
  * STEO_SERIES_ID is a placeholder ("ELGEN"); the real total-generation series id in the
    ELGEN family must be read from a live `/v2/steo/data/facet/seriesId` call.
  * `operating-generator-capacity` is NOT confirmed to be usable as an additions feed. The
    2026-09-10 response retained under `.local/eia/capacity-additions-*.json` is EIA's whole
    operable-generator inventory, one row per generator per month, 4,808,947 rows, of which the
    request took the first 5,000 -- all of them 2008-01 -- and not one carried an
    `operating-year-month` field, because EIA returns only the `data[]` columns a request names.
    Both defects are fixed in `capacity_url()` (the column is requested, the window starts at
    SERIES_START_YEAR), but neither the column name nor a viable way to read one month of a
    4.8-million-row inventory inside EIA's 5,000-row JSON cap has been confirmed against a live
    response. Until it is, `capacity_failures()` makes the run fail with the reason instead of
    reporting ok -- which is how five advertised capacity metrics reached 2026-09 with zero
    observations and zero catalog entries.
  * Retail-sales facets: this module assumes `facets[stateid][]` (two-letter state code, plus
    `US` for the national row) and `facets[sectorid][]` (`RES` residential, `ALL` all sectors)
    and a `data[0]=price` column named `price` in cents/kWh on the response rows, following EIA
    API v2's documented general facet-naming convention for this route -- not confirmed against
    a live response. Confirm the exact facet/column names and that `US` is a valid `stateid`
    value (EIA's documentation describes it as such) before the first `--apply`.

    python scripts/import_eia.py            # with a key: fetch, snapshot, report; without one: print registration URL, exit 0
    python scripts/import_eia.py --apply    # register the source, add metrics and records, rebuild
"""
import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import research
from importer_common import DEGRADED_EXIT

from research import load, save, now, require, UA
import api_access

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOTS = ROOT/'research/eia'
SOURCE_ID = 'eia-api-v2-electricity'
SOURCE = {'id': SOURCE_ID, 'publisher': 'U.S. Energy Information Administration', 'title': 'EIA API v2 · electricity data',
          'url': 'https://www.eia.gov/opendata/documentation.php', 'published': None, 'layers': ['energy'],
          'license': 'Public domain (U.S. government work)', 'provenance': 'official'}

REGISTRATION_URL = 'https://www.eia.gov/opendata/register.php'

NET_GENERATION_ROUTE = 'https://api.eia.gov/v2/electricity/electric-power-operational-data/data/'
CAPACITY_ROUTE = 'https://api.eia.gov/v2/electricity/operating-generator-capacity/data/'
STEO_ROUTE = 'https://api.eia.gov/v2/steo/data/'
RETAIL_PRICE_ROUTE = 'https://api.eia.gov/v2/electricity/retail-sales/data/'
PAGE_LIMIT = 5000          # EIA API v2's JSON row cap; a response at the cap is a truncated page
RETAIL_START_YEAR = 2019   # the site's reviewed history start; EIA publishes back to 2001
SERIES_START_YEAR = 2019   # the same start for every EIA series, so no record precedes its metric

# USPS state abbreviation -> full name, for every state (plus DC) a reviewed project map
# location can resolve to; 'US' (national) is handled separately, never through this map.
STATE_NAMES = {'AL':'Alabama','AK':'Alaska','AZ':'Arizona','AR':'Arkansas','CA':'California','CO':'Colorado',
    'CT':'Connecticut','DE':'Delaware','DC':'District of Columbia','FL':'Florida','GA':'Georgia','HI':'Hawaii',
    'ID':'Idaho','IL':'Illinois','IN':'Indiana','IA':'Iowa','KS':'Kansas','KY':'Kentucky','LA':'Louisiana',
    'ME':'Maine','MD':'Maryland','MA':'Massachusetts','MI':'Michigan','MN':'Minnesota','MS':'Mississippi',
    'MO':'Missouri','MT':'Montana','NE':'Nebraska','NV':'Nevada','NH':'New Hampshire','NJ':'New Jersey',
    'NM':'New Mexico','NY':'New York','NC':'North Carolina','ND':'North Dakota','OH':'Ohio','OK':'Oklahoma',
    'OR':'Oregon','PA':'Pennsylvania','RI':'Rhode Island','SC':'South Carolina','SD':'South Dakota',
    'TN':'Tennessee','TX':'Texas','UT':'Utah','VT':'Vermont','VA':'Virginia','WA':'Washington',
    'WV':'West Virginia','WI':'Wisconsin','WY':'Wyoming'}
# (EIA sectorid, our metric-id slug)
RETAIL_SECTORS = [('RES', 'residential'), ('ALL', 'all')]
STATE_LABEL_RE = re.compile(r',\s*([A-Za-z]{2})\b')
# Placeholder: EIA's STEO API groups series by a seriesId facet. The real mnemonic for total
# electricity generation in the ELGEN family is confirmed only once a live key exists.
STEO_SERIES_ID = 'ELGEN'

# EIA energy_source_code -> our metric slug/label. Tracked sources named in the reviewed scope.
CAPACITY_SOURCES = [('SUN', 'solar', 'Solar'), ('WND', 'wind', 'Wind'), ('BAT', 'battery-storage', 'Battery storage'),
                     ('NG', 'natural-gas', 'Natural gas'), ('NUC', 'nuclear', 'Nuclear')]

YEAR_RE = re.compile(r'20\d\d')
MONTH_RE = re.compile(r'20\d\d-(0[1-9]|1[0-2])')


def net_generation_url():
    # The route returns one row per state per month; the national aggregate is location 'US'
    # (confirmed against a live pull 2026-09-10). Without this facet every state's row carried the
    # national record id and 4,978 duplicate records were produced.
    return (f'{NET_GENERATION_ROUTE}?frequency=monthly&data[0]=generation&facets[location][]=US'
            f'&facets[sectorid][]=99&facets[fueltypeid][]=ALL&start={SERIES_START_YEAR}-01'
            f'&sort[0][column]=period&sort[0][direction]=asc')


def capacity_url():
    # 2026-09-10 response: 5,000 rows of 4,808,947, every one 2008-01 and none carrying
    # operating-year-month, so capacity_addition_records discarded all of them. EIA returns only
    # the data[] columns a request names, and an unwindowed request starts at the series start.
    return (f'{CAPACITY_ROUTE}?frequency=monthly&data[0]=nameplate-capacity-mw&data[1]=operating-year-month'
            f'&start={SERIES_START_YEAR}-01&sort[0][column]=period&sort[0][direction]=asc')


def steo_url():
    return f'{STEO_ROUTE}?frequency=annual&data[0]=value&facets[seriesId][]={STEO_SERIES_ID}'


def project_states(delivery):
    """2-letter state code -> state name, from the same reviewed Census map locations
    import_qcew.project_counties reads off accepted projects: a county (census-map-counties)
    or place (census-map-places) location's own label always ends "<name>, <ST>". A
    geonames-map location (used for non-U.S. places) is never a U.S. state and is ignored."""
    states = {}
    for p in delivery['projects']:
        locs = [p['map_location']] if p.get('map_location') else [e.get('location', e) for e in p.get('map_locations', [])]
        for l in locs:
            if l.get('source') not in ('census-map-counties', 'census-map-places'):
                continue
            m = STATE_LABEL_RE.search(l.get('label') or '')
            if not m:
                continue
            code = m.group(1).upper()
            if code in STATE_NAMES:
                states[code] = STATE_NAMES[code]
    return states


def retail_price_url(codes, sector):
    facets = ''.join(f'&facets[stateid][]={code}' for code in codes)
    return (f'{RETAIL_PRICE_ROUTE}?frequency=annual&data[0]=price{facets}'
            f'&facets[sectorid][]={sector}&start={RETAIL_START_YEAR}&sort[0][column]=period&sort[0][direction]=asc')


def response_meta(body):
    """(rows, truncated, total). EIA caps a JSON response at PAGE_LIMIT rows and says so in
    `warnings`; a truncated page silently answers a different question from the one asked."""
    payload = json.loads(body.decode('utf-8'))
    require(isinstance(payload, dict) and isinstance((payload.get('response') or {}).get('data'), list), 'Unexpected EIA API v2 response shape')
    rows = payload['response']['data']
    warnings = [str((w or {}).get('warning', '')) for w in (payload.get('warnings') or [])]
    return rows, bool(any('incomplete return' in w for w in warnings) or len(rows) >= PAGE_LIMIT), payload['response'].get('total')


def capacity_failures(rows, call):
    """Why the capacity route produces nothing, in the words of the response itself. Read off the
    retained 2026-09-10 pull; both conditions must be gone before this route can be trusted."""
    out = []
    if call.get('truncated'):
        out.append(f"capacity-additions returned a truncated page ({call.get('rows')} rows of {call.get('total')}). "
                    "operating-generator-capacity is the whole operable-generator inventory, one row per generator per "
                    "month, so an additions figure cannot be read off an unwindowed request; window or page it against "
                    "a live pull before trusting this route.")
    if rows and not any('operating-year-month' in r for r in rows):
        out.append("capacity-additions rows carry no 'operating-year-month' field, so no generator can be dated to the "
                    "month it came online and every row is discarded. Confirm the column name against a live pull.")
    return out


def net_generation_metric():
    return {'id': 'eia-net-generation-monthly', 'layer': 'energy', 'title': 'U.S. net electricity generation, all fuels (EIA, monthly)',
            'unit': 'TWh', 'geography': 'United States',
            'scope': "EIA electric-power-sector monthly net generation, all fuels combined (sector 99, electric power total), "
                     "from the EIA API v2 electric-power-operational-data route. National context, not AI-only demand. "
                     "Source thousand MWh divided by 1,000 to express TWh.",
            'direction': 'context', 'min': 0, 'max': 2_000_000,
            'note': "EIA API v2, public domain (U.S. government work); requires the owner's registered key, never recorded. "
                    "Annual series from 2019; each import appends newly published years and never rewrites earlier ones.",
            'source_ids': [SOURCE_ID], 'company': None, 'measurement_type': 'eia_net_generation_twh', 'project': None,
            'allowed_statuses': ['observation'], 'period_basis': 'month', 'geography_code': None,
            'series_start_year': SERIES_START_YEAR, 'chart_default_start': SERIES_START_YEAR, 'chart_default_end': 2027, 'definition_stable': True,
            'pre_period_note': "Series begins once the owner registers an EIA API key and the first live import runs; "
                                "earlier months exist in EIA's API and can be imported on review. Missing months are unpublished, not zero."}


def net_generation_records(rows, retrieved_at):
    """Monthly all-fuels total generation (fueltypeid ALL), thousand MWh converted to TWh."""
    observations = []
    for r in rows:
        if r.get('fueltypeid') != 'ALL' or r.get('location') != 'US':
            continue
        if str(r.get('period') or '')[:4].isdigit() and int(str(r['period'])[:4]) < SERIES_START_YEAR:
            continue   # no record may precede its metric's reviewed series start
        period = r.get('period')
        if not period or not MONTH_RE.fullmatch(period):
            continue
        raw = r.get('generation')
        if raw in (None, '', 'NA', 'w', 'ND'):
            continue
        try:
            thousand_mwh = float(raw)
        except (TypeError, ValueError):
            continue
        if thousand_mwh < 0:
            continue
        value = round(thousand_mwh/1000, 3)
        observations.append({'id': f'eia-net-generation-monthly-{period}', 'metric': 'eia-net-generation-monthly', 'year': int(period[:4]),
                              'period': period, 'value': value, 'upper': None, 'status': 'observation', 'source': SOURCE_ID,
                              'precision': 'eq', 'retrieved_at': retrieved_at, 'method': 'curated',
                              'note': f"EIA API v2 electric-power-operational-data, sector 99 (electric power total), all fuels, {period}: {thousand_mwh:,.1f} thousand MWh."[:300]})
    return observations


def capacity_metric(slug, label):
    return {'id': f'eia-operating-capacity-additions-monthly-{slug}', 'layer': 'energy',
            'title': f'U.S. {label.lower()} generator capacity additions (EIA, monthly)',
            'unit': 'MW added in month', 'geography': 'United States',
            'scope': f"Nameplate capacity of {label.lower()} generators newly reporting operating status in the month, from EIA's "
                     f"operating-generator-capacity route (EIA-860M derived). A monthly capacity flow (additions), not a cumulative fleet total.",
            'direction': 'context', 'min': 0, 'max': 100_000,
            'note': "EIA API v2, public domain (U.S. government work); requires the owner's registered key, never recorded. "
                    "Monthly series; each import appends newly published months and never rewrites earlier ones.",
            'source_ids': [SOURCE_ID], 'company': None, 'measurement_type': 'eia_capacity_additions_mw', 'project': None,
            'allowed_statuses': ['observation'], 'period_basis': 'month', 'geography_code': None,
            'series_start_year': SERIES_START_YEAR, 'chart_default_start': SERIES_START_YEAR, 'chart_default_end': 2027, 'definition_stable': True,
            'pre_period_note': "Series begins once the owner registers an EIA API key and the first live import runs; "
                                "earlier months exist in EIA's API and can be imported on review. Missing months are unpublished, not zero."}


def capacity_addition_records(rows, retrieved_at):
    """Sum nameplate MW of generators whose operating-year-month equals the row's own period,
    grouped by energy source, for the five tracked sources. Rows for other sources are ignored.
    Metrics are keyed by metric id, like retail_price_records: keyed by slug they never matched
    run()'s `mid in with_records` filter, so even a working route could not have registered one.
    """
    metrics = {}
    totals = {}   # (slug, period) -> MW
    slug_by_code = {code: (slug, label) for code, slug, label in CAPACITY_SOURCES}
    for r in rows:
        code = r.get('energy_source_code')
        if code not in slug_by_code:
            continue
        period = r.get('period')
        online = r.get('operating-year-month')
        if not period or not MONTH_RE.fullmatch(period) or online != period:
            continue   # only count a generator in the month it newly came online
        raw = r.get('nameplate-capacity-mw')
        if raw in (None, '', 'NA'):
            continue
        try:
            mw = float(raw)
        except (TypeError, ValueError):
            continue
        if mw <= 0:
            continue
        slug, label = slug_by_code[code]
        totals[(slug, period)] = totals.get((slug, period), 0.0) + mw
        metrics.setdefault(f'eia-operating-capacity-additions-monthly-{slug}', capacity_metric(slug, label))
    observations = []
    for (slug, period), mw in sorted(totals.items()):
        mid = f'eia-operating-capacity-additions-monthly-{slug}'
        observations.append({'id': f'{mid}-{period}', 'metric': mid, 'year': int(period[:4]), 'period': period, 'value': round(mw, 1),
                              'upper': None, 'status': 'observation', 'source': SOURCE_ID, 'precision': 'eq', 'retrieved_at': retrieved_at,
                              'method': 'curated', 'note': f"EIA API v2 operating-generator-capacity, generators newly operating {period}: {round(mw,1):,} MW nameplate."[:300]})
    return metrics, observations


def steo_metric():
    return {'id': 'eia-steo-generation-outlook', 'layer': 'energy', 'title': 'U.S. electricity generation outlook (EIA STEO, annual)',
            'unit': 'TWh', 'geography': 'United States',
            'scope': "EIA Short-Term Energy Outlook total electricity generation, from the EIA API v2 STEO route (the ELGEN-family "
                     "series; the exact live series id is confirmed only once the owner registers a key -- see the code comment on "
                     "STEO_SERIES_ID). A machine-readable companion to the PDF-curated us-utility-generation-history metric, not a replacement for it.",
            'direction': 'context', 'min': 0, 'max': 2_000_000,
            'note': "EIA API v2 Short-Term Energy Outlook, public domain (U.S. government work); requires the owner's registered key, "
                    "never recorded. Yearly series; each import appends newly published years and never rewrites earlier ones.",
            'source_ids': [SOURCE_ID], 'company': None, 'measurement_type': 'eia_steo_generation_twh', 'project': None,
            'allowed_statuses': ['observation', 'forecast'], 'geography_code': None,
            'series_start_year': SERIES_START_YEAR, 'chart_default_start': SERIES_START_YEAR, 'chart_default_end': 2030, 'definition_stable': True,
            'pre_period_note': "Series begins once the owner registers an EIA API key and the first live import runs. "
                                "Missing years are unpublished, not zero."}


def steo_records(rows, retrieved_at, today=None):
    """Yearly STEO total generation. A fully elapsed year is an observation; the current
    (still-elapsing) year and later years are a forecast, matching this project's existing
    STEO convention for us-utility-generation-history."""
    today = today or datetime.now(timezone.utc).date()
    observations = []
    for r in rows:
        period = r.get('period')
        if not period or not re.fullmatch(r'20\d\d', str(period)):
            continue
        raw = r.get('value')
        if raw in (None, '', 'NA'):
            continue
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        year = int(period)
        status = 'observation' if year < today.year else 'forecast'
        observations.append({'id': f'eia-steo-generation-outlook-{year}', 'metric': 'eia-steo-generation-outlook', 'year': year,
                              'period': str(year), 'value': round(value, 3), 'upper': None, 'status': status, 'source': SOURCE_ID,
                              'precision': 'eq' if status == 'observation' else 'approx', 'retrieved_at': retrieved_at, 'method': 'curated',
                              'note': f"EIA STEO, series {STEO_SERIES_ID} (placeholder id, confirm live), {year}: {value:,.1f}."[:300]})
    return observations


def retail_price_metric(code, name, slug):
    sector_label = 'residential' if slug == 'residential' else 'all-sector'
    geography = 'United States' if code == 'US' else name
    return {'id': f'eia-retail-price-{code.lower()}-{slug}', 'layer': 'energy',
            'title': f'{geography} · retail electricity price, {sector_label} (EIA, annual)',
            'unit': 'cents/kWh', 'geography': geography,
            'scope': f"EIA API v2 electricity/retail-sales average retail electricity price, {sector_label} customers, "
                     f"{geography}, annual average. Grid-interface tracking (2026-09-10): the price people near the buildout pay, "
                     "not a claim about what caused a change in it.",
            'direction': 'context', 'min': 0, 'max': 100,
            'note': "EIA API v2, public domain (U.S. government work); requires the owner's registered key, never recorded. "
                    "Monthly series; each import appends newly published months and never rewrites earlier ones.",
            'source_ids': [SOURCE_ID], 'company': None, 'measurement_type': 'retail_electricity_price_cents_kwh', 'project': None,
            'allowed_statuses': ['observation'], 'period_basis': None, 'geography_code': code,
            'series_start_year': RETAIL_START_YEAR, 'chart_default_start': RETAIL_START_YEAR, 'chart_default_end': 2027, 'definition_stable': True,
            'pre_period_note': "Series begins once the owner registers an EIA API key and the first live import runs; "
                                "2019 onward exists in EIA's API. Missing months are unpublished, not zero."}


def retail_price_records(rows, retrieved_at, states):
    """states: {2-letter code -> name}, including 'US' -> 'United States'. Rows outside the
    tracked states/sectors, or without a usable numeric price, are skipped."""
    slug_by_sectorid = dict(RETAIL_SECTORS)
    metrics = {}
    observations = []
    for r in rows:
        code = r.get('stateid')
        sector_id = r.get('sectorid')
        if code not in states or sector_id not in slug_by_sectorid:
            continue
        period = str(r.get('period') or '')
        if not YEAR_RE.fullmatch(period) or int(period) < RETAIL_START_YEAR:
            continue   # annual frequency: the period is a bare year
        raw = r.get('price')
        if raw in (None, '', 'NA', 'w', 'ND'):
            continue
        try:
            value = round(float(raw), 2)
        except (TypeError, ValueError):
            continue
        if value <= 0:
            continue
        slug = slug_by_sectorid[sector_id]
        mid = f'eia-retail-price-{code.lower()}-{slug}'
        metrics.setdefault(mid, retail_price_metric(code, states[code], slug))
        observations.append({'id': f'{mid}-{period}', 'metric': mid, 'year': int(period[:4]), 'period': period, 'value': value,
                              'upper': None, 'status': 'observation', 'source': SOURCE_ID, 'precision': 'eq', 'retrieved_at': retrieved_at,
                              'method': 'curated',
                              'note': f"EIA API v2 electricity/retail-sales annual average, state {code}, sector {sector_id}, {period}: {value:g} cents/kWh."[:300]})
    return metrics, observations


def run(apply=False, today=None):
    key = api_access.key('eia')
    if not key:
        message = (f"No EIA API key registered. Register one at {REGISTRATION_URL}, save it to .local/api-keys.json "
                    f"under \"eia\", then re-run this importer. No network calls made.")
        print(message, flush=True)
        return {'status': 'no_key', 'registration_url': REGISTRATION_URL}

    from importer_common import apply_changes, check_floors, redacted_body, report_drift, DEGRADED_EXIT
    retrieved = now()
    private = research.LOCAL/'eia'; private.mkdir(parents=True, exist_ok=True)
    calls = []

    def pull(name, url):
        try:
            body = redacted_body(api_access.fetch(url, UA))
        except Exception as e:
            calls.append({'call': name, 'status': type(e).__name__}); return []
        sha = hashlib.sha256(body).hexdigest()
        (private/f'{name}-{sha[:12]}.json').write_bytes(body)
        try:
            rows, truncated, total = response_meta(body)
        except ValueError:
            calls.append({'call': name, 'status': 'unparseable'}); return []
        calls.append({'call': name, 'status': 'ok', 'sha256': sha, 'rows': len(rows), 'truncated': truncated, 'total': total})
        return rows

    gen_rows = pull('net-generation', net_generation_url())
    cap_rows = pull('capacity-additions', capacity_url())
    steo_rows = pull('steo', steo_url())
    states = project_states(load(ROOT/'research/delivery.json'))
    codes = sorted(states) + ['US']
    # One call per state: a request naming several stateid facets comes back with a single state's
    # rows (checked live 2026-09-10 -- ['TX','VA'] returned 306 Virginia rows), which silently
    # dropped every project state and left only the national series.
    retail_rows = {}
    for sector, _ in RETAIL_SECTORS:
        rows = []
        for code in codes:
            rows += pull(f'retail-price-{sector.lower()}-{code.lower()}', retail_price_url([code], sector))
        retail_rows[sector] = rows

    all_metrics = {}
    all_obs = []
    gen_obs = net_generation_records(gen_rows, retrieved)
    if gen_obs:
        all_metrics['eia-net-generation-monthly'] = net_generation_metric()
        all_obs += gen_obs
    cap_metrics, cap_obs = capacity_addition_records(cap_rows, retrieved)
    all_metrics.update(cap_metrics); all_obs += cap_obs
    steo_obs = steo_records(steo_rows, retrieved, today)
    if steo_obs:
        all_metrics['eia-steo-generation-outlook'] = steo_metric()
        all_obs += steo_obs
    retail_states = dict(states, US='United States')
    retail_obs_count = 0
    for sector, _ in RETAIL_SECTORS:
        retail_metrics, retail_obs = retail_price_records(retail_rows[sector], retrieved, retail_states)
        all_metrics.update(retail_metrics); all_obs += retail_obs; retail_obs_count += len(retail_obs)

    counts = {'rows:net-generation': len(gen_rows), 'records:net-generation': len(gen_obs),
              'rows:capacity-additions': len(cap_rows), 'records:capacity-additions': len(cap_obs),
              'rows:steo': len(steo_rows), 'records:steo': len(steo_obs),
              'rows:retail-price': sum(len(r) for r in retail_rows.values()), 'records:retail-price': retail_obs_count}
    failures = capacity_failures(cap_rows, next((c for c in calls if c['call'] == 'capacity-additions'), {}))
    for failure in failures:
        print('ROUTE '+failure, file=sys.stderr, flush=True)
    failures += check_floors(ROOT, 'eia', counts)

    SNAPSHOTS.mkdir(exist_ok=True)
    snapshot = {'dataset': 'EIA API v2 electricity data', 'source_id': SOURCE_ID, 'retrieved_at': retrieved, 'calls': calls,
                'metrics': sorted(all_metrics), 'records': len(all_obs), 'license': 'Public domain (U.S. government work)',
                'key': 'owner-registered, not recorded', 'steo_series_id_placeholder': STEO_SERIES_ID,
                'retail_price_states': sorted(retail_states), 'counts': counts, 'failures': failures}
    save(SNAPSHOTS/'eia.json', snapshot)

    registry = load(ROOT/'research/sources.json'); ledger = load(ROOT/'site/data/ledger.json'); catalog = load(ROOT/'research/catalog.json')
    existing_ids = {o['id'] for o in ledger['observations']}
    new_obs = [o for o in all_obs if o['id'] not in existing_ids]
    with_records = {o['metric'] for o in all_obs}
    known = {m['id'] for m in catalog['metrics']}
    new_metrics = [m for mid, m in sorted(all_metrics.items()) if mid not in known and mid in with_records]
    drift = report_drift(ROOT, 'eia', all_obs, ledger['observations'])

    ok = sum(1 for c in calls if c['status'] == 'ok')
    print(f"api calls ok {ok}/{len(calls)} · metrics {len(all_metrics)} ({len(new_metrics)} new) · records {len(all_obs)} ({len(new_obs)} new) · drift {len(drift)}", flush=True)
    result = {'status': 'failed' if failures else 'ok', 'metrics': new_metrics, 'records': new_obs, 'calls': calls,
              'floor_failures': failures, 'drift': drift}
    if not apply:
        return result
    # The records that were built are still valid records, so they land; the run reports failure
    # afterwards rather than throwing away the routes that worked.
    collection_entries = {SOURCE_ID: {'rank': 1, 'region_book': 'united-states', 'company_id': None, 'claim_type': 'other', 'cadence': 'manual', 'weekday': 0, 'path_prefixes': [], 'topics': [], 'excerpts': False}}
    apply_changes(ROOT, importer_id='eia', new_sources=[SOURCE] if SOURCE_ID not in {s['id'] for s in registry['sources']} else (),
                  collection_entries=collection_entries, region_book='united-states',
                  new_metrics=new_metrics, new_observations=new_obs, snapshot=snapshot)
    print('catalog, registry and ledger updated; site rebuilt', flush=True)
    return result


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0]); p.add_argument('--apply', action='store_true')
    a = p.parse_args(argv); return DEGRADED_EXIT if run(apply=a.apply).get('floor_failures') else 0


if __name__ == '__main__': sys.exit(main())
