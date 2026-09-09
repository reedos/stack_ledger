"""Reviewed chip-project capacity quantification configuration."""
import json
from pathlib import Path
from validate import require, text, timestamp

ROOT = Path(__file__).resolve().parents[1]
CLASS_FIELDS = {'label', 'measurement_type', 'unit', 'quantifies', 'conversion'}
PROJECT_FIELDS = {'class', 'scope', 'company', 'source_ids', 'title'}


def validate_chip_capacity(x, delivery, sources, companies):
    require(set(x) == {'version', 'reviewed_at', 'classes', 'reference_die', 'projects'}, 'Unexpected chip capacity shape')
    require(x['version'] == 1, 'Unsupported chip capacity version')
    timestamp(x['reviewed_at'])
    source_ids = {s['id'] for s in sources}
    for cid, cls in x['classes'].items():
        require(set(cls) == CLASS_FIELDS, f'Unexpected class fields for {cid}')
        for k in ['label', 'quantifies', 'conversion']: text(cls[k], 1000)
        text(cls['unit'], 200)
    rd = x['reference_die']
    require(set(rd) == {'name', 'area_mm2', 'wafer_diameter_mm', 'source_id'}, 'Unexpected reference die shape')
    require(isinstance(rd['area_mm2'], (int, float)) and rd['area_mm2'] > 0, 'Invalid reference die area')
    require(isinstance(rd['wafer_diameter_mm'], (int, float)) and rd['wafer_diameter_mm'] > 0, 'Invalid reference wafer diameter')
    require(rd['source_id'] in source_ids, 'Reference die source not registered')
    text(rd['name'], 200)
    projects = {p['id']: p for p in delivery['projects']}
    for pid, entry in x['projects'].items():
        require(set(entry) == PROJECT_FIELDS, f'Unexpected project fields for {pid}')
        require(pid in projects, f'Configured project {pid} is not in delivery.json')
        require(projects[pid]['layer'] == 'chips', f'Configured project {pid} is not a chips project')
        require(entry['class'] in x['classes'], f'Configured project {pid} has an unreviewed class')
        require(entry['source_ids'] and set(entry['source_ids']) <= source_ids, f'Configured project {pid} cites an unregistered source')
        require(entry['company'] is None or entry['company'] in companies, f'Configured project {pid} has an unreviewed company')
        for k in ['scope', 'title']: text(entry[k], 600)
    return True


def validate_files():
    read = lambda p: json.loads((ROOT / p).read_text(encoding='utf-8'))
    x = read('site/data/chip-capacity.json')
    require(x == read('research/chip-capacity.json'), 'Reviewed chip capacity metadata changed')
    ledger = read('site/data/ledger.json')
    companies = {c['id'] for c in read('research/ecosystem.json')['companies']}
    return validate_chip_capacity(x, read('research/delivery.json'), ledger['sources'], companies)


if __name__ == '__main__':
    validate_files(); print('Chip capacity validation passed')
