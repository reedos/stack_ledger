"""Maintainer importer for SEC XBRL company facts (public domain). No model calls.

SEC's XBRL "company facts" API republishes every number a company has tagged in its own
10-K/10-Q filings, including a `frame` field on the facts that align exactly with a calendar
period (e.g. `CY2025Q4`, `CY2025`): the deduplicated, period-aligned reading for that period,
picked by SEC itself rather than by us choosing among restatements. This importer reads
revenue and capital expenditure for the ecosystem companies whose `filings_jurisdiction` is
exactly `SEC` -- U.S. domestic filers on Form 10-K/10-Q -- and records them as new,
company-attributed series alongside (never replacing) the existing curated annual revenue
records sourced from stockanalysis.com.

Two groups are deliberately excluded, and this importer reports both:

  * Foreign private issuers (tsmc, asml, nebius, alibaba) file Form 20-F annually, not 10-Q;
    SEC XBRL companyfacts cannot give them the quarterly-or-better cadence this importer wants.
    A separate, filer-specific track is a later project, not this one.
  * aws: the AWS segment is not a distinct SEC filer -- only Amazon.com, Inc. is -- and
    research/ecosystem.json carries no separate "amazon" parent entity today. Recording
    Amazon's whole-company SEC financials under the "aws" company id without a reviewed
    "amazon" entity would misattribute consolidated Amazon figures as the AWS segment, so aws
    is skipped pending that reviewed ecosystem change.

CIK lookup uses SEC's own ticker-to-CIK file (`company_tickers.json`) against a reviewed ticker
map (`research/sec-companies.json`), so the mapping from our company ids to SEC CIKs is
deterministic and reviewed rather than guessed from a company name; a reviewed ticker missing
from SEC's own file fails loudly rather than silently skipping the company.

    python scripts/import_sec.py            # download, snapshot, report what would change
    python scripts/import_sec.py --apply    # register the source, add metrics and records, rebuild
"""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import research
from research import load, save, now, require, UA
import api_access

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOTS = ROOT/'research/sec'
SOURCE_ID = 'sec-xbrl-companyfacts'
SOURCE = {'id': SOURCE_ID, 'publisher': 'U.S. Securities and Exchange Commission', 'title': 'SEC EDGAR XBRL Company Facts API',
          'url': 'https://www.sec.gov/edgar/sec-api-documentation', 'published': None,
          'layers': ['energy', 'chips', 'infrastructure', 'models', 'applications'], 'license': 'Public domain (U.S. government work)', 'provenance': 'regulated-filing'}

TICKERS_URL = 'https://www.sec.gov/files/company_tickers.json'
COMPANYFACTS_URL = 'https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json'

# First match in order: a company may only use one of these tags consistently, but different
# filers (and the same filer over time) choose different ones.
REVENUE_CONCEPTS = ['Revenues', 'RevenueFromContractWithCustomerExcludingAssessedTax', 'SalesRevenueNet']
CAPEX_CONCEPTS = ['PaymentsToAcquirePropertyPlantAndEquipment']
KINDS = [('revenue', REVENUE_CONCEPTS, 10_000), ('capex', CAPEX_CONCEPTS, 2_000)]

FORMS = {'10-K', '10-Q'}
START_YEAR = 2019   # the site's reviewed history start; older frames are not backfilled without review
QUARTER_FRAME = re.compile(r'^CY(20\d\d)Q([1-4])$')
ANNUAL_FRAME = re.compile(r'^CY(20\d\d)$')

# Reported for the owner; this importer makes no attempt to fetch or classify these.
SKIPPED = {
    'foreign_filers': {
        'tsmc': "Files Form 20-F annually (TWSE / SEC); XBRL companyfacts cannot give quarterly-or-better cadence.",
        'asml': "Files Form 20-F/annual accounts (Netherlands annual accounts / SEC); same cadence limitation.",
        'nebius': "Files Form 20-F/annual accounts (Netherlands annual accounts / SEC); same cadence limitation.",
        'alibaba': "Files Form 20-F annually (HKEX / SEC); same cadence limitation.",
    },
    'aws': "No separate 'amazon' parent entity exists in research/ecosystem.json alongside 'aws'; "
           "recording Amazon.com, Inc.'s consolidated SEC financials under the 'aws' company id "
           "without a reviewed 'amazon' entity would misattribute whole-company figures as the "
           "AWS segment. Skipped pending that reviewed ecosystem change.",
}


def fetch(url):
    """data.sec.gov and www.sec.gov are listed statistical API hosts (research/api-access.json);
    api_access.fetch also holds every request to this host one second apart."""
    return api_access.fetch(url, UA)


def load_companies(root=ROOT):
    p = load(root/'research/sec-companies.json')
    require(p.get('version') == 1 and isinstance(p.get('companies'), dict) and p['companies'], 'Unexpected sec-companies shape')
    return p


def ciks_for(tickers_body, wanted_tickers):
    """ticker (uppercase) -> CIK (int), from SEC's own company_tickers.json. Fails loudly on
    any reviewed ticker SEC's file does not carry, rather than silently dropping the company."""
    rows = json.loads(tickers_body.decode('utf-8'))
    require(isinstance(rows, dict), 'Unexpected company_tickers.json shape')
    by_ticker = {str(r['ticker']).upper(): int(r['cik_str']) for r in rows.values()}
    result = {}
    for ticker in wanted_tickers:
        require(ticker.upper() in by_ticker, f'Ticker {ticker} not found in SEC company_tickers.json')
        result[ticker.upper()] = by_ticker[ticker.upper()]
    return result


def select_concept(facts, concepts):
    """The first concept (in priority order) this filer's facts actually carry, and its USD facts."""
    gaap = (facts.get('facts') or {}).get('us-gaap') or {}
    for concept in concepts:
        usd = ((gaap.get(concept) or {}).get('units') or {}).get('USD')
        if usd:
            return concept, usd
    return None, []


def frame_facts(facts_usd):
    """The single best (latest-filed) 10-K/10-Q fact per calendar frame.

    Facts without a `frame` are SEC's non-deduplicated raw tags (restatements, superseded
    values, partial periods) and are ignored entirely, per the reviewed scope: frames are the
    deduplicated, period-aligned values. A frame can carry more than one fact when a later
    filing restates the same period; the most recently filed one wins.
    """
    best = {}
    for f in facts_usd:
        frame = f.get('frame')
        if not frame or f.get('form') not in FORMS:
            continue
        if not (QUARTER_FRAME.fullmatch(frame) or ANNUAL_FRAME.fullmatch(frame)):
            continue
        current = best.get(frame)
        if current is None or (f.get('filed') or '') >= (current.get('filed') or ''):
            best[frame] = f
    return best


def metric_definition(company_id, layer, kind, quarterly, display_name, unit_max):
    cadence = 'quarterly' if quarterly else 'annual'
    label = 'revenue' if kind == 'revenue' else 'capital expenditure'
    basis_note = (" These are calendar-quarter SEC XBRL frames (e.g. CY2025Q4), the periods SEC itself "
                  "deduplicates facts onto; a company's own fiscal quarters can fall on different dates."
                  if quarterly else "")
    return {'id': f'sec-{kind}-{company_id}-{cadence}', 'layer': layer,
            'title': f'{display_name} · {label}, {cadence} (SEC XBRL)',
            'unit': 'USD billion', 'geography': 'Global',
            'scope': f"{display_name}'s own reported {label}, from SEC XBRL company-facts filings (Form 10-K/10-Q), "
                     f"taken from SEC's deduplicated, period-aligned 'frame' value for each period.{basis_note} "
                     f"A new addition, not a replacement for this company's existing curated annual revenue record.",
            'direction': 'context', 'min': 0, 'max': unit_max,
            'note': 'SEC EDGAR XBRL company facts, public domain. Additions only; each import appends newly published frames and never rewrites earlier ones.',
            'source_ids': [SOURCE_ID], 'company': company_id, 'measurement_type': f'sec_{kind}_usd_bn', 'project': None,
            'allowed_statuses': ['observation'], **({'period_basis': 'quarter'} if quarterly else {}),
            'geography_code': None, 'series_start_year': START_YEAR, 'chart_default_start': START_YEAR, 'chart_default_end': 2027,
            'definition_stable': True,
            'pre_period_note': f"Series begins with the earliest 10-K/10-Q frame this importer finds; earlier {'quarters' if quarterly else 'years'} "
                                f"exist in SEC filings and can be imported on review. Missing periods are unpublished, not zero."}


def records_for(company_id, layer, kind, concept, frames, retrieved_at, display_name, unit_max):
    """Metric definitions (quarterly, annual as needed) and observations for one concept's frames."""
    metrics = {}
    observations = []
    for frame, fact in sorted(frames.items()):
        qm = QUARTER_FRAME.fullmatch(frame)
        am = ANNUAL_FRAME.fullmatch(frame)
        quarterly = qm is not None
        mid = f"sec-{kind}-{company_id}-{'quarterly' if quarterly else 'annual'}"
        if mid not in metrics:
            metrics[mid] = metric_definition(company_id, layer, kind, quarterly, display_name, unit_max)
        year = int(qm.group(1)) if quarterly else int(am.group(1))
        if year < START_YEAR:
            continue   # older frames stay in the SEC archive; the ledger's series start is a reviewed choice
        period = f'{year}-Q{qm.group(2)}' if quarterly else f'CY{year}'
        val = fact.get('val')
        if not isinstance(val, (int, float)):
            continue
        value = round(val/1_000_000_000, 3)
        note = (f"SEC XBRL {concept}, frame {frame}: ${val:,.0f} USD. "
                f"Form {fact.get('form')}, filed {fact.get('filed')}, accession {fact.get('accn')}.")[:300]
        observations.append({'id': f'{mid}-{frame.lower()}', 'metric': mid, 'year': year, 'period': period, 'value': value, 'upper': None,
                              'status': 'observation', 'source': SOURCE_ID, 'precision': 'eq', 'retrieved_at': retrieved_at,
                              'method': 'curated', 'note': note})
    return metrics, observations


def run(apply=False):
    ecosystem = load(ROOT/'research/ecosystem.json')
    companies_by_id = {c['id']: c for c in ecosystem['companies']}
    sec_companies = load_companies()['companies']
    registry = load(ROOT/'research/sources.json'); ledger = load(ROOT/'site/data/ledger.json'); catalog = load(ROOT/'research/catalog.json')

    for cid in sec_companies:
        require(cid in companies_by_id, f'{cid} is not a known ecosystem company')
        require(companies_by_id[cid].get('filings_jurisdiction') == 'SEC', f'{cid} is not a reviewed SEC domestic filer')

    retrieved = now()
    private = research.LOCAL/'sec'; private.mkdir(parents=True, exist_ok=True)

    tickers_body = fetch(TICKERS_URL)
    tickers_sha = hashlib.sha256(tickers_body).hexdigest()
    (private/f'company_tickers-{tickers_sha[:12]}.json').write_bytes(tickers_body)
    cik_by_ticker = ciks_for(tickers_body, [c['ticker'] for c in sec_companies.values()])

    all_metrics = {}; all_obs = []; per_company = {}; calls = []
    for company_id, entry in sorted(sec_companies.items()):
        ticker = entry['ticker'].upper()
        cik = cik_by_ticker[ticker]
        layer = companies_by_id[company_id]['layers'][0]
        display_name = companies_by_id[company_id]['name']
        url = COMPANYFACTS_URL.format(cik=cik)
        try:
            body = fetch(url)
        except Exception as e:
            calls.append({'company': company_id, 'ticker': ticker, 'cik': cik, 'status': type(e).__name__})
            continue
        sha = hashlib.sha256(body).hexdigest()
        (private/f'{company_id}-{sha[:12]}.json').write_bytes(body)
        facts = json.loads(body.decode('utf-8'))
        latest_quarter = None; latest_annual = None; company_metrics = 0; company_records = 0
        for kind, concepts, unit_max in KINDS:
            concept, facts_usd = select_concept(facts, concepts)
            if concept is None:
                continue
            frames = frame_facts(facts_usd)
            m, o = records_for(company_id, layer, kind, concept, frames, retrieved, display_name, unit_max)
            all_metrics.update(m); all_obs += o
            company_metrics += len(m); company_records += len(o)
            quarters = sorted(oo['period'] for oo in o if 'Q' in oo['period'])
            annuals = sorted(oo['period'] for oo in o if 'Q' not in oo['period'])
            if quarters: latest_quarter = max(latest_quarter or '', quarters[-1])
            if annuals: latest_annual = max(latest_annual or '', annuals[-1])
        per_company[company_id] = {'ticker': ticker, 'cik': cik, 'sha256': sha, 'metrics': company_metrics,
                                    'records': company_records, 'latest_quarter': latest_quarter, 'latest_annual': latest_annual}
        calls.append({'company': company_id, 'ticker': ticker, 'cik': cik, 'status': 'ok', 'facts_sha256': sha})

    SNAPSHOTS.mkdir(exist_ok=True)
    snapshot = {'dataset': 'SEC XBRL company facts', 'source_id': SOURCE_ID, 'retrieved_at': retrieved,
                'company_tickers_sha256': tickers_sha, 'companies': per_company, 'calls': calls, 'skipped': SKIPPED,
                'metrics': sorted(all_metrics), 'records': len(all_obs), 'license': 'Public domain (U.S. government work)'}
    save(SNAPSHOTS/'companyfacts.json', snapshot)

    existing_ids = {o['id'] for o in ledger['observations']}
    new_obs = [o for o in all_obs if o['id'] not in existing_ids]
    with_records = {o['metric'] for o in all_obs}
    known = {m['id'] for m in catalog['metrics']}
    new_metrics = [m for mid, m in sorted(all_metrics.items()) if mid not in known and mid in with_records]

    ok = sum(1 for c in calls if c['status'] == 'ok')
    print(f"companies {ok}/{len(calls)} · metrics {len(all_metrics)} ({len(new_metrics)} new) · records {len(all_obs)} ({len(new_obs)} new)", flush=True)
    for cid, info in sorted(per_company.items()):
        print(f"  {cid}: latest quarter {info['latest_quarter']}, latest annual {info['latest_annual']}", flush=True)
    print(f"  skipped foreign filers (Form 20-F): {', '.join(sorted(SKIPPED['foreign_filers']))}", flush=True)
    print(f"  skipped aws: {SKIPPED['aws']}", flush=True)

    result = {'metrics': new_metrics, 'records': new_obs, 'per_company': per_company, 'skipped': SKIPPED, 'calls': calls}
    if not apply:
        return result
    from importer_common import apply_changes
    collection_entries = {SOURCE_ID: {'rank': 1, 'region_book': 'united-states', 'company_id': None, 'claim_type': 'financial', 'cadence': 'manual', 'weekday': 0, 'path_prefixes': [], 'topics': [], 'excerpts': False}}
    apply_changes(ROOT, importer_id='sec', new_sources=[SOURCE] if SOURCE_ID not in {s['id'] for s in registry['sources']} else (),
                  collection_entries=collection_entries, region_book='united-states',
                  new_metrics=new_metrics, new_observations=new_obs, snapshot=snapshot)
    print('catalog, registry and ledger updated; site rebuilt', flush=True)
    return result


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0]); p.add_argument('--apply', action='store_true')
    a = p.parse_args(argv); run(apply=a.apply); return 0


if __name__ == '__main__': sys.exit(main())
