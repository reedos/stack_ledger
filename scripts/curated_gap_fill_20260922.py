#!/usr/bin/env python3
"""Curated 2026-09-22 gap fill: LBNL 2025 DC electricity, ERCOT LLI queue, BIS AI Diffusion event, METR RCT.

Maintainer / human-reviewed additions only. No model calls. Uses importer_common.apply_changes.
Dry-run by default; pass --apply to write.
"""
from __future__ import annotations

import argparse
import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from research import load, now, require
from importer_common import apply_changes

ROOT = Path(__file__).resolve().parents[1]
RETRIEVED = '2026-09-22T07:08:19Z'

SOURCES = [
    {
        'id': 'lbnl-dc-2025-update',
        'publisher': 'Lawrence Berkeley National Laboratory / U.S. Department of Energy',
        'title': 'United States Data Center Energy Usage Report: 2025 Update (LBNL-2001758)',
        'url': 'https://www.energy.gov/documents/united-states-data-center-energy-usage-report-2025-update',
        'published': '2026-06-18',
        'layers': ['energy'],
        'license': 'CC BY 4.0',
        'provenance': 'independent-research',
    },
    {
        'id': 'ercot-lli-board-2026-04',
        'publisher': 'ERCOT',
        'title': 'Board Item 9 · Interconnection and Grid Analysis Update (as of March 26, 2026)',
        'url': 'https://www.ercot.com/files/docs/2026/04/13/9-Interconnection-and-Grid-Analysis-Update.pdf',
        'published': '2026-04-20',
        'layers': ['energy', 'infrastructure'],
        'license': 'See original source',
        'provenance': 'official',
    },
    {
        'id': 'ercot-constraints-needs-2025-12',
        'publisher': 'ERCOT',
        'title': 'Report on Existing and Potential Electric System Constraints and Needs · December 2025',
        'url': 'https://www.ercot.com/files/docs/2025/12/23/2025-Report-on-Existing-and-Potential-Electric-System-Constraints-and-Needs.pdf',
        'published': '2025-12-23',
        'layers': ['energy', 'infrastructure'],
        'license': 'See original source',
        'provenance': 'official',
    },
    {
        'id': 'federal-register-2025-00636',
        'publisher': 'U.S. Bureau of Industry and Security',
        'title': 'Framework for Artificial Intelligence Diffusion (90 FR 4544)',
        'url': 'https://www.federalregister.gov/documents/2025/01/15/2025-00636/framework-for-artificial-intelligence-diffusion',
        'published': '2025-01-15',
        'layers': ['chips'],
        'license': 'Public domain (U.S. government work)',
        'provenance': 'official',
    },
    {
        'id': 'metr-early-2025-os-dev-rct',
        'publisher': 'METR',
        'title': 'Measuring the Impact of Early-2025 AI on Experienced Open-Source Developer Productivity',
        'url': 'https://metr.org/blog/2025-07-10-early-2025-ai-experienced-os-dev-study/',
        'published': '2025-07-10',
        'layers': ['applications', 'models'],
        'license': 'See original source',
        'provenance': 'independent-research',
    },
]

METRICS = [
    {
        'id': 'ercot-large-load-queue-gw',
        'layer': 'energy',
        'title': 'ERCOT large-load interconnection queue',
        'unit': 'GW',
        'geography': 'ERCOT (Texas)',
        'scope': 'Total large-load interconnection (LLI) capacity seeking interconnection at the disclosure date. Queue entry is not an interconnection agreement, financing, or energized service. Distinct from generation/storage interconnection queues.',
        'direction': 'context',
        'min': 0,
        'max': 100000,
        'note': 'ERCOT operator disclosures. Data-center share is recorded separately when the same deck states it. Never sum with U.S. generation queue metrics.',
        'source_ids': ['ercot-lli-board-2026-04', 'ercot-constraints-needs-2025-12'],
        'series_start_year': 2025,
        'chart_default_start': 2025,
        'chart_default_end': 2030,
        'definition_stable': True,
        'pre_period_note': 'Reviewed catalog begins with Dec 2025 constraints report; earlier LLI totals require curated review.',
    },
    {
        'id': 'ercot-large-load-queue-datacenter-share-pct',
        'layer': 'energy',
        'title': 'ERCOT large-load queue · data-center share',
        'unit': '% of LLI queue MW',
        'geography': 'ERCOT (Texas)',
        'scope': 'Share of tracked large-load interconnection capacity attributed to data centers in the same ERCOT disclosure. Not a forecast of energized data-center load.',
        'direction': 'context',
        'min': 0,
        'max': 100,
        'note': 'Percentage from the operator deck that also states total LLI GW. Keep paired with ercot-large-load-queue-gw for the same as-of date.',
        'source_ids': ['ercot-lli-board-2026-04'],
        'series_start_year': 2026,
        'chart_default_start': 2026,
        'chart_default_end': 2030,
        'definition_stable': True,
        'pre_period_note': 'Reviewed catalog begins with the March 26, 2026 as-of snapshot.',
        'allowed_statuses': ['observation', 'estimate'],
    },
    {
        'id': 'metr-os-dev-task-time-delta-pct',
        'layer': 'applications',
        'title': 'METR RCT · experienced OSS developer task-time change with AI allowed',
        'unit': '% change in task completion time',
        'geography': 'Study sample (experienced open-source developers)',
        'scope': 'Randomized controlled trial of early-2025 AI tools (primarily Cursor Pro with Claude 3.5/3.7 Sonnet) on 246 real issues across mature repositories. Positive values mean slower with AI allowed. Not a population-wide productivity estimate, seat count, or 2026 frontier result.',
        'direction': 'context',
        'min': -100,
        'max': 100,
        'note': 'Method-first applications outcome. Developers predicted speedup; measured completion time increased. Late-2025 METR follow-up is not merged here (authors describe it as weak/uninterpretable).',
        'source_ids': ['metr-early-2025-os-dev-rct'],
        'series_start_year': 2025,
        'chart_default_start': 2025,
        'chart_default_end': 2030,
        'definition_stable': True,
        'pre_period_note': 'Single RCT vintage; do not stitch to surveys or later uninterpretable waves.',
        'allowed_statuses': ['observation', 'estimate'],
    },
]


def observations():
    return [
        {
            'id': 'us-dc-lbnl2025-2024',
            'metric': 'us-dc-electricity-lbnl-2025',
            'year': 2024,
            'period': '2024',
            'value': 192,
            'upper': None,
            'status': 'estimate',
            'source': 'lbnl-dc-2025-update',
            'precision': 'approx',
            'retrieved_at': RETRIEVED,
            'method': 'curated',
            'note': 'LBNL 2025 Update historical year: 192 TWh (4.7% of U.S. electricity). Excludes cryptocurrency mining. Distinct vintage from the 2024 Report series also on this metric.',
        },
        {
            'id': 'us-dc-lbnl2025-2028-ref',
            'metric': 'us-dc-electricity-lbnl-2025',
            'year': 2028,
            'period': '2028 Reference Case',
            'value': 464,
            'upper': None,
            'status': 'forecast',
            'source': 'lbnl-dc-2025-update',
            'precision': 'approx',
            'retrieved_at': RETRIEVED,
            'method': 'curated',
            'note': 'LBNL 2025 Update Reference Case for 2028 (464 TWh). Kept beside the older 2024 Report 325–580 TWh range; do not average vintages.',
        },
        {
            'id': 'us-dc-lbnl2025-2030-ref',
            'metric': 'us-dc-electricity-lbnl-2025',
            'year': 2030,
            'period': '2030 Reference Case',
            'value': 649,
            'upper': None,
            'status': 'forecast',
            'source': 'lbnl-dc-2025-update',
            'precision': 'approx',
            'retrieved_at': RETRIEVED,
            'method': 'curated',
            'note': 'Reference Case 649 TWh (11.8% of forecasted 2030 U.S. electricity per NERC LTRA). Compounded Uncertainty bounds 521–843 TWh are documented in the report, not stored as a single range on this Reference Case point.',
        },

        {
            'id': 'ercot-lli-2025-12',
            'metric': 'ercot-large-load-queue-gw',
            'year': 2025,
            'period': '2025-12 constraints report',
            'value': 239,
            'upper': None,
            'status': 'observation',
            'source': 'ercot-constraints-needs-2025-12',
            'precision': 'approx',
            'retrieved_at': RETRIEVED,
            'method': 'curated',
            'note': 'ERCOT: approximately 239 GW of large load seeking interconnection. Queue ≠ energized service.',
        },
        {
            'id': 'ercot-lli-2026-03-26',
            'metric': 'ercot-large-load-queue-gw',
            'year': 2026,
            'period': '2026-03-26',
            'value': 410,
            'upper': None,
            'status': 'observation',
            'source': 'ercot-lli-board-2026-04',
            'precision': 'approx',
            'retrieved_at': RETRIEVED,
            'method': 'curated',
            'note': 'Board deck: approximately 410 GW LLI queue; +178 GW since end-2025. Q1 2026 added 198 new LLI requests.',
        },
        {
            'id': 'ercot-lli-dc-share-2026-03-26',
            'metric': 'ercot-large-load-queue-datacenter-share-pct',
            'year': 2026,
            'period': '2026-03-26',
            'value': 87.6,
            'upper': None,
            'status': 'observation',
            'source': 'ercot-lli-board-2026-04',
            'precision': 'approx',
            'retrieved_at': RETRIEVED,
            'method': 'curated',
            'note': 'Same deck states ~87% / chart label 87.6% of LLI MW are data centers. Not energized data-center load.',
        },
        {
            'id': 'metr-os-dev-slowdown-2025',
            'metric': 'metr-os-dev-task-time-delta-pct',
            'year': 2025,
            'period': 'Feb–Jun 2025 RCT',
            'value': 19,
            'upper': None,
            'status': 'observation',
            'source': 'metr-early-2025-os-dev-rct',
            'precision': 'approx',
            'retrieved_at': RETRIEVED,
            'method': 'curated',
            'note': 'Allowing AI increased completion time by ~19% vs AI-disallowed (16 developers, 246 tasks). Developers had forecast ~24% speedup. Snapshot of early-2025 tools in mature OSS repos—not a universal agent ROI.',
        },
    ]


EVENTS = [
    {
        'id': 'policy-2025-00636',
        'layer': 'chips',
        'date': '2025-01-15',
        'title': 'BIS Framework for Artificial Intelligence Diffusion (advanced computing + model weights)',
        'summary': 'Interim final rule (Doc. 2025-00636, Docket 250107-0007, 90 FR 4544) expands worldwide licensing for advanced computing ICs (ECCNs 3A090.a / 4A090.a and related .z items), adds ECCN 4E091 controls on certain closed-weight AI model weights trained above 10^26 operations, and creates license exceptions and Data Center VEU pathways. Effective 2025-01-13; general compliance 2025-05-15. Grade A government action only—no shipment volumes inferred.',
        'source': 'federal-register-2025-00636',
        'kind': 'Government action',
        'grade': 'A',
    },
]


def patch_us_dc_metric(catalog):
    metrics = catalog['metrics']
    idx = next(i for i, m in enumerate(metrics) if m['id'] == 'us-dc-electricity')
    m = copy.deepcopy(metrics[idx])
    ids = list(m.get('source_ids') or [])
    if 'lbnl-dc-2025-update' not in ids:
        ids.append('lbnl-dc-2025-update')
    m['source_ids'] = ids
    m['scope'] = (
        'All U.S. data centers, excluding cryptocurrency mining. '
        '2024 Report vintage (through 2028 range) and LBNL 2025 Update vintage (through 2030) share this metric id but remain separate source lines—never average vintages.'
    )
    m['note'] = (
        '2024 Report retained: 2014/2023 estimates and 2028 range 325–580 TWh. '
        'LBNL 2025 Update adds 2024≈192 TWh, 2028 Reference≈464 TWh, 2030 Reference 649 TWh '
        '(Compounded Uncertainty 521–843 TWh; upper stored on the 2030 record). Global IEA series stay separate.'
    )
    m['chart_default_end'] = 2030
    metrics[idx] = m
    return [m]


def patch_grid_operators(path: Path):
    data = load(path)
    for op in data.get('operators', []):
        if op.get('id') == 'ercot':
            note = op.get('note') or ''
            addition = (
                ' Curated LLI queue observations from the Dec 2025 constraints report (~239 GW) '
                'and Apr 2026 board deck (~410 GW as of 2026-03-26) were added 2026-09-22 as '
                'ercot-large-load-queue-gw; long-term load-forecast PDF import remains open.'
            )
            if 'ercot-large-load-queue-gw' not in note:
                op['note'] = note + addition
    return data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()
    catalog = load(ROOT / 'research/catalog.json')
    ledger = load(ROOT / 'site/data/ledger.json')
    updated_metric = patch_us_dc_metric(catalog)
    new_metrics = METRICS + updated_metric
    obs = observations()
    print(f'Would add {len(SOURCES)} sources, {len(METRICS)} new metrics, '
          f'1 updated metric, {len(obs)} observations, {len(EVENTS)} events')
    for o in obs:
        print(f'  obs {o["id"]}: {o["metric"]}={o["value"]} ({o["status"]})')
    for e in EVENTS:
        print(f'  event {e["id"]}: {e["title"][:72]}')
    if not args.apply:
        print('Dry-run only. Re-run with --apply to write.')
        return
    apply_changes(
        ROOT,
        importer_id='curated-gap-fill-20260922',
        new_sources=SOURCES,
        new_metrics=new_metrics,
        replace_metric_ids=['us-dc-electricity'],
        new_observations=obs,
        new_events=EVENTS,
        snapshot={'label': 'curated-gap-fill-20260922', 'retrieved_at': RETRIEVED},
    )
    grid_path = ROOT / 'research/grid-operators.json'
    save = __import__('research').save
    save(grid_path, patch_grid_operators(grid_path))
    print('Applied curated gap fill and updated grid-operators.json note for ERCOT.')


if __name__ == '__main__':
    main()
