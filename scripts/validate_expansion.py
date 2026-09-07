"""Reviewed measurement bases and cross-file references for the coverage expansion."""
import json
from pathlib import Path
from validate import require, text, timestamp, STATUSES

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_TYPES={'construction_spending_saar','job_postings_index'}
TYPES = PUBLIC_TYPES | {'training_seats_committed','training_funding_committed','nuclear_ppa_committed','smr_mw_committed','harness_list_price','clinical_trial_enrollment','clinical_endpoint_change',
    'site_it_mw_operating', 'site_it_mw_planned_endstate', 'site_facility_mw',
    'site_compute_mw_reported', 'onsite_generation_mw_temporary',
    'onsite_generation_mw_permanent', 'interconnection_mw_energized',
    'interconnection_mw_requested', 'capex_announced_usd', 'capex_recognized_usd',
    'compute_contract_usd', 'local_procurement_usd', 'annual_revenue_usd',
    'construction_workers_peak', 'contractor_fte', 'permanent_jobs_promised',
    'permanent_jobs_reported', 'company_headcount', 'wafer_starts_per_month',
    'hbm_stack_capacity', 'cowos_or_advanced_packaging_wspm',
    'accelerator_units_installed', 'accelerator_units_contracted',
    'compute_mw_contracted', 'token_price_input_usd_per_m',
    'token_price_output_usd_per_m', 'weekly_paid_agent_or_seat_users',
    'published_task_success_rate', 'hours_automated', 'supervised_driver_miles',
    'unsupervised_or_rider_only_miles', 'paid_trips_per_week',
    'autonomous_trips_per_week', 'operating_vehicle_count', 'operating_metro_count',
    'humanoid_units_in_production_use', 'completed_totes',
}
FUTURE_ONLY = {'training_seats_committed','training_funding_committed','nuclear_ppa_committed','smr_mw_committed','capex_announced_usd', 'compute_contract_usd',
               'site_it_mw_planned_endstate', 'interconnection_mw_requested',
               'permanent_jobs_promised', 'accelerator_units_contracted',
               'compute_mw_contracted'}
HISTORICAL_ONLY = {'site_it_mw_operating', 'capex_recognized_usd',
                   'permanent_jobs_reported', 'annual_revenue_usd',
                   'interconnection_mw_energized', 'accelerator_units_installed',
                   'supervised_driver_miles', 'unsupervised_or_rider_only_miles',
                   'operating_vehicle_count', 'operating_metro_count',
                   'humanoid_units_in_production_use', 'completed_totes'}


def validate_expansion(x, ledger, ecosystem, delivery):
    require(set(x) == {'version', 'reviewed_at', 'products', 'jobs_projects', 'featured', 'gaps'}, 'Unexpected expansion shape')
    require(x['version'] == 1, 'Unsupported expansion version'); timestamp(x['reviewed_at'])
    companies = {c['id'] for c in ecosystem['companies']}
    projects = {p['id']: p for p in delivery['projects']}
    sources = {s['id']: s for s in ledger['sources']}
    metrics = {m['id']: m for m in ledger['metrics']}
    observations = {o['id']: o for o in ledger['observations']}
    for m in metrics.values():
        if 'measurement_type' not in m:
            continue
        require(m['measurement_type'] in TYPES, 'Unreviewed measurement type')
        require(m.get('company') in companies or (m.get('company') is None and m['measurement_type'] in PUBLIC_TYPES), 'Metric needs reviewed company')
        require(m.get('project') is None or m['project'] in projects, 'Unknown metric project')
        for k in ['unit', 'geography', 'scope']: text(m[k], 700)
        require(m.get('allowed_statuses') and set(m['allowed_statuses']) <= set(STATUSES), 'Missing measurement status policy')
        if m['measurement_type'] in FUTURE_ONLY:
            require(set(m['allowed_statuses']) <= {'forecast', 'company-commitment', 'government-target'}, 'Promised measurement allows actual results')
        if m['measurement_type'] in HISTORICAL_ONLY:
            require(set(m['allowed_statuses']) <= {'observation', 'estimate'}, 'Historical measurement allows plans')
        require(m['source_ids'] and set(m['source_ids']) <= sources.keys(), 'Missing approved metric source')
        if m.get('project'):
            require(m['layer'] == projects[m['project']]['layer'], 'Metric/project layer mismatch')
    seen = set()
    for p in x['products']:
        require(set(p) == {'id', 'name', 'company', 'stage', 'source', 'summary', 'observations', 'gap'}, 'Unexpected product fields')
        require(p['id'] not in seen, 'Duplicate product'); seen.add(p['id'])
        require(p['company'] in companies and p['source'] in sources, 'Unknown product attribution')
        require(p['stage'] in {'Paid product', 'Research preview', 'Documented product', 'Local runtime'}, 'Invalid product stage')
        for k in ['id', 'name', 'summary', 'gap']: text(p[k], 600)
        for id in p['observations']:
            require(id in observations and not observations[id].get('superseded_by'), 'Missing or superseded product observation')
            o = observations[id]; m = metrics[o['metric']]
            require(m.get('company') == p['company'], 'Product figure belongs to another company')
            require(m['layer'] == 'models' and o['source'] == p['source'], 'Product metric/source mismatch')
    require(len(x['jobs_projects']) == len(set(x['jobs_projects'])) and set(x['jobs_projects']) <= projects.keys(), 'Unknown or duplicate jobs project')
    require(set(x['featured']) == {l['id'] for l in ledger['layers']}, 'Missing featured layer')
    for layer, ids in x['featured'].items():
        require(len(ids) == len(set(ids)), 'Duplicate featured project')
        require(all(id in projects and projects[id]['layer'] == layer for id in ids), 'Featured project layer mismatch')
    for gap in x['gaps']: text(gap, 600)
    return True


def validate_files():
    read = lambda p: json.loads((ROOT / p).read_text(encoding='utf-8'))
    x = read('site/data/expansion.json')
    require(x == read('research/expansion.json'), 'Reviewed expansion metadata changed')
    return validate_expansion(x, read('site/data/ledger.json'), read('research/ecosystem.json'), read('research/delivery.json'))


if __name__ == '__main__':
    validate_files(); print('Coverage expansion validation passed')
