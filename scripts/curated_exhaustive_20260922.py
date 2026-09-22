#!/usr/bin/env python3
"""Curated 2026-09-22 exhaustive research apply (PUBLISH NOW tranche).

Maintainer / human-reviewed additions only. No model calls. Uses importer_common.apply_changes.
Dry-run by default; pass --apply to write.

Does NOT duplicate already-landed ERCOT LLI / PJM 30 GW / LBNL / METR / BIS 28270·00636·00789.
Replaces Amazon CapEx 220 (AP) with ~200 primary IR; upgrades Alphabet/Microsoft to company-commitment.
"""
from __future__ import annotations

import argparse
import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from research import load, save
from importer_common import apply_changes

ROOT = Path(__file__).resolve().parents[1]
RETRIEVED = '2026-09-22T07:24:01Z'

SOURCES = [
    {
        'id': 'pjm-2026-load-report',
        'publisher': 'PJM Interconnection',
        'title': '2026 PJM Load Forecast Report',
        'url': 'https://www.pjm.com/-/media/DotCom/library/reports-notices/load-forecast/2026-load-report.pdf',
        'published': '2026-01-14',
        'layers': ['energy'],
        'license': 'See original source',
        'provenance': 'official',
    },
    {
        'id': 'spp-2025-itp-report',
        'publisher': 'Southwest Power Pool',
        'title': 'SPP 2025 Integrated Transmission Planning (ITP) Report v10',
        'url': 'https://www.spp.org/media/2429/2025-itp-report-v10.pdf',
        'published': '2025-11-25',
        'layers': ['energy'],
        'license': 'See original source',
        'provenance': 'official',
    },
    {
        'id': 'miso-ltlf-whitepaper-2024-12',
        'publisher': 'MISO',
        'title': 'MISO Long-Term Load Forecast Whitepaper (December 2024)',
        'url': 'https://cdn.misoenergy.org/MISO%20Long-Term%20Load%20Forecast%20Whitepaper_December%202024667166.pdf',
        'published': '2024-12-01',
        'layers': ['energy'],
        'license': 'See original source',
        'provenance': 'official',
    },
    {
        'id': 'capital-alphabet-q2-2026-ir',
        'publisher': 'Alphabet',
        'title': 'Alphabet 2026 Q2 earnings call · CY2026 CapEx guidance',
        'url': 'https://abc.xyz/investor/events/event-details/2026/2026-Q2-Earnings-Call-2026-GgTAq7Is0z/default.aspx',
        'published': '2026-07-22',
        'layers': ['infrastructure'],
        'license': 'Public disclosure; facts paraphrased with attribution.',
        'provenance': 'company-channel',
    },
    {
        'id': 'capital-amazon-q4-2025-ir',
        'publisher': 'Amazon',
        'title': 'Amazon.com Announces Fourth Quarter Results · CY2026 CapEx',
        'url': 'https://ir.aboutamazon.com/news-release/news-release-details/2026/Amazon-com-Announces-Fourth-Quarter-Results/',
        'published': '2026-02-05',
        'layers': ['infrastructure'],
        'license': 'Public disclosure; facts paraphrased with attribution.',
        'provenance': 'company-channel',
    },
    {
        'id': 'federal-register-2025-17893',
        'publisher': 'U.S. Bureau of Industry and Security',
        'title': 'Additions and Revisions to the Entity List (90 FR 44496)',
        'url': 'https://www.federalregister.gov/documents/2025/09/16/2025-17893/additions-and-revisions-to-the-entity-list',
        'published': '2025-09-16',
        'layers': ['chips'],
        'license': 'Public domain (U.S. government work)',
        'provenance': 'official',
    },
    {
        'id': 'federal-register-2025-19001',
        'publisher': 'U.S. Bureau of Industry and Security',
        'title': 'Expansion of End-User Controls To Cover Affiliates of Certain Listed Entities',
        'url': 'https://www.federalregister.gov/documents/2025/09/30/2025-19001/expansion-of-end-user-controls-to-cover-affiliates-of-certain-listed-entities',
        'published': '2025-09-30',
        'layers': ['chips'],
        'license': 'Public domain (U.S. government work)',
        'provenance': 'official',
    },
    {
        'id': 'federal-register-2025-19508',
        'publisher': 'U.S. Bureau of Industry and Security',
        'title': 'Additions to the Entity List (90 FR 48193)',
        'url': 'https://www.federalregister.gov/documents/2025/10/09/2025-19508/additions-to-the-entity-list',
        'published': '2025-10-09',
        'layers': ['chips'],
        'license': 'Public domain (U.S. government work)',
        'provenance': 'official',
    },
    {
        'id': 'federal-register-2025-19846',
        'publisher': 'U.S. Bureau of Industry and Security',
        'title': 'One Year Suspension of Expansion of End-User Controls for Affiliates',
        'url': 'https://www.federalregister.gov/documents/2025/11/12/2025-19846/one-year-suspension-of-expansion-of-end-user-controls-for-affiliates-of-certain-listed-entities',
        'published': '2025-11-12',
        'layers': ['chips'],
        'license': 'Public domain (U.S. government work)',
        'provenance': 'official',
    },
    {
        'id': 'federal-register-2025-19858',
        'publisher': 'U.S. Bureau of Industry and Security',
        'title': 'Revisions to the Entity List (Arrow China removal / alias cleanup)',
        'url': 'https://www.federalregister.gov/documents/2025/11/12/2025-19858/revisions-to-the-entity-list',
        'published': '2025-11-12',
        'layers': ['chips'],
        'license': 'Public domain (U.S. government work)',
        'provenance': 'official',
    },
    {
        'id': 'federal-register-2026-17230',
        'publisher': 'U.S. Bureau of Industry and Security',
        'title': 'Removal From the Entity List (91 FR 54657)',
        'url': 'https://www.federalregister.gov/documents/2026/08/24/2026-17230/removal-from-the-entity-list',
        'published': '2026-08-24',
        'layers': ['chips'],
        'license': 'Public domain (U.S. government work)',
        'provenance': 'official',
    },
    {
        'id': 'federal-register-2026-17231',
        'publisher': 'U.S. Bureau of Industry and Security',
        'title': 'Revisions to the Entity List (Arrow Electronics Hong Kong addresses)',
        'url': 'https://www.federalregister.gov/documents/2026/08/24/2026-17231/revisions-to-the-entity-list',
        'published': '2026-08-24',
        'layers': ['chips'],
        'license': 'Public domain (U.S. government work)',
        'provenance': 'official',
    },
    {
        'id': 'wh-eo-dc-permitting-2025-07-23',
        'publisher': 'The White House',
        'title': 'Accelerating Federal Permitting of Data Center Infrastructure (EO)',
        'url': 'https://www.whitehouse.gov/presidential-actions/2025/07/accelerating-federal-permitting-of-data-center-infrastructure/',
        'published': '2025-07-23',
        'layers': ['infrastructure', 'energy'],
        'license': 'Public domain (U.S. government work)',
        'provenance': 'official',
    },
    {
        'id': 'dellacqua-jagged-frontier-orsc-2026',
        'publisher': 'Organization Science (INFORMS)',
        'title': "Navigating the Jagged Technological Frontier (Dell'Acqua et al.)",
        'url': 'https://doi.org/10.1287/orsc.2025.21838',
        'published': '2026-03-11',
        'layers': ['applications'],
        'license': 'CC BY 4.0 (publisher terms)',
        'provenance': 'independent-research',
    },
    {
        'id': 'brynjolfsson-li-raymond-qje-2025',
        'publisher': 'Quarterly Journal of Economics',
        'title': 'Generative AI at Work (Brynjolfsson, Li, Raymond) · DOI qjae044',
        'url': 'https://danielle.li/assets/docs/GenerativeAIatWork.pdf',
        'published': '2025-02-04',
        'layers': ['applications'],
        'license': 'See original source',
        'provenance': 'independent-research',
    },
    {
        'id': 'tsmc-4q25-earnings-transcript',
        'publisher': 'TSMC',
        'title': 'TSMC 4Q25 earnings conference call transcript',
        'url': 'https://investor.tsmc.com/english/encrypt/files/encrypt_file/reports/2026-01/51d09df96cd89ac19d65af39032b038dc2896a24/TSMC%204Q25%20Transcript.pdf',
        'published': '2026-01-16',
        'layers': ['chips'],
        'license': 'Public disclosure; facts paraphrased with attribution.',
        'provenance': 'company-channel',
    },
    {
        'id': 'microsoft-datacenter-efficiency',
        'publisher': 'Microsoft',
        'title': 'Microsoft Datacenters · sustainability efficiency (WUE)',
        'url': 'https://datacenters.microsoft.com/sustainability/efficiency/',
        'published': None,
        'layers': ['infrastructure', 'energy'],
        'license': 'See original source',
        'provenance': 'company-channel',
    },
    {
        'id': 'alphabet-fy2025-env-indicators-assurance',
        'publisher': 'Alphabet / Google',
        'title': 'Alphabet FY2025 environmental indicators assurance letter',
        'url': 'https://sustainability.google/files/alphabet-fy2025-environmental-indicators-assurance-letter/',
        'published': '2026-06-22',
        'layers': ['infrastructure', 'energy'],
        'license': 'See original source',
        'provenance': 'company-channel',
    },
    {
        'id': 'google-ai-env-impact-scale',
        'publisher': 'Google',
        'title': 'Measuring the environmental impact of delivering AI at Google Scale',
        'url': 'https://services.google.com/fh/files/misc/measuring_the_environmental_impact_of_delivering_ai_at_google_scale.pdf',
        'published': '2025-08-01',
        'layers': ['infrastructure', 'energy', 'applications'],
        'license': 'See original source',
        'provenance': 'company-channel',
    },
]


def new_metrics():
    return [
        {
            'id': 'pjm-rto-summer-peak-mw',
            'layer': 'energy',
            'title': 'PJM RTO non-coincident unrestricted summer peak',
            'unit': 'MW',
            'geography': 'PJM',
            'scope': 'PJM Load Forecast Report non-coincident unrestricted summer peak for the RTO. Distinct from LAS data-center growth planning MW and from EIA-930 daily demand.',
            'direction': 'context',
            'min': 0,
            'max': 1000000,
            'note': '2026 Load Report path: 10y +65,733 MW / 20y +96,704 MW from the report base. Firm vs non-firm large-load derate language is in event pjm-2026-ltf-large-load-firm-nonfirm, not this series.',
            'source_ids': ['pjm-2026-load-report'],
            'series_start_year': 2026,
            'chart_default_start': 2026,
            'chart_default_end': 2046,
            'definition_stable': True,
            'pre_period_note': 'Reviewed catalog begins with the January 2026 Load Forecast Report path (2036/2046 points).',
            'allowed_statuses': ['forecast', 'observation'],
        },
        {
            'id': 'spp-peak-load-itp-gw',
            'layer': 'energy',
            'title': 'SPP peak load (ITP narrative path)',
            'unit': 'GW',
            'geography': 'Southwest Power Pool',
            'scope': 'SPP 2025 ITP executive-summary narrative: current peak load that could rise within about 10 years. Distinct from Figure 2.1 coincident-peak path (spp-itp-coincident-peak-gw).',
            'direction': 'context',
            'min': 0,
            'max': 500,
            'note': 'Exec summary uses "could rise" language (56→109 GW). Do not average with the lower Figure 2.1 coincident-peak trajectory.',
            'source_ids': ['spp-2025-itp-report'],
            'series_start_year': 2025,
            'chart_default_start': 2025,
            'chart_default_end': 2035,
            'definition_stable': True,
            'pre_period_note': 'Reviewed catalog begins with the 2025 ITP Report v10 disclosures.',
            'allowed_statuses': ['observation', 'forecast', 'estimate'],
        },
        {
            'id': 'spp-itp-coincident-peak-gw',
            'layer': 'energy',
            'title': 'SPP ITP coincident peak (Figure 2.1 path)',
            'unit': 'GW',
            'geography': 'Southwest Power Pool',
            'scope': 'SPP 2025 ITP Figure 2.1 coincident peak trajectory. Lower path than the executive-summary 56→109 GW narrative; keep series separate.',
            'direction': 'context',
            'min': 0,
            'max': 500,
            'note': 'One observation per model year from Figure 2.1. Not energized large-load MW.',
            'source_ids': ['spp-2025-itp-report'],
            'series_start_year': 2026,
            'chart_default_start': 2026,
            'chart_default_end': 2044,
            'definition_stable': True,
            'pre_period_note': 'Reviewed catalog begins with 2025 ITP Figure 2.1 years 2026–2044.',
            'allowed_statuses': ['forecast'],
        },
        {
            'id': 'ercot-tsp-peak-forecast-2031-gw',
            'layer': 'energy',
            'title': 'ERCOT TSP peak forecast (2031)',
            'unit': 'GW',
            'geography': 'ERCOT (Texas)',
            'scope': 'Transmission Service Provider (TSP) peak-load forecast for 2031 from the Dec 2025 constraints and needs report. Distinct from studied peak and from LLI queue GW.',
            'direction': 'context',
            'min': 0,
            'max': 1000,
            'note': 'Paired with ercot-studied-peak-2031-gw from the same report. Queue ≠ forecast ≠ energized.',
            'source_ids': ['ercot-constraints-needs-2025-12'],
            'series_start_year': 2031,
            'chart_default_start': 2031,
            'chart_default_end': 2031,
            'definition_stable': True,
            'pre_period_note': 'Single 2031 TSP forecast vintage from the December 2025 constraints report.',
            'allowed_statuses': ['forecast'],
        },
        {
            'id': 'ercot-studied-peak-2031-gw',
            'layer': 'energy',
            'title': 'ERCOT studied peak (2031)',
            'unit': 'GW',
            'geography': 'ERCOT (Texas)',
            'scope': 'Studied peak-load case for 2031 from the Dec 2025 constraints and needs report. Distinct from TSP forecast and from LLI queue GW.',
            'direction': 'context',
            'min': 0,
            'max': 1000,
            'note': 'Paired with ercot-tsp-peak-forecast-2031-gw. Studied ≠ approved-to-energize ≠ queue.',
            'source_ids': ['ercot-constraints-needs-2025-12'],
            'series_start_year': 2031,
            'chart_default_start': 2031,
            'chart_default_end': 2031,
            'definition_stable': True,
            'pre_period_note': 'Single 2031 studied-peak vintage from the December 2025 constraints report.',
            'allowed_statuses': ['forecast'],
        },
        {
            'id': 'miso-coincident-peak-ltlf-gw',
            'layer': 'energy',
            'title': 'MISO coincident peak (LTLF whitepaper)',
            'unit': 'GW',
            'geography': 'MISO',
            'scope': 'MISO Dec 2024 Long-Term Load Forecast whitepaper coincident peak. 2044 uses low–high range from the whitepaper; not the later news 163 GW figure.',
            'direction': 'context',
            'min': 0,
            'max': 500,
            'note': 'Do not merge with unverified 163 GW-by-2035 news claims. Distinct from EIA-930 daily demand.',
            'source_ids': ['miso-ltlf-whitepaper-2024-12'],
            'series_start_year': 2024,
            'chart_default_start': 2024,
            'chart_default_end': 2044,
            'definition_stable': True,
            'pre_period_note': 'Reviewed catalog begins with the December 2024 LTLF whitepaper (2024 observation / 2044 range).',
            'allowed_statuses': ['observation', 'forecast', 'estimate'],
        },
        {
            'id': 'miso-datacenter-energy-twh',
            'layer': 'energy',
            'title': 'MISO incremental data-center energy demand (LTLF)',
            'unit': 'TWh',
            'geography': 'MISO',
            'scope': 'Incremental data-center energy demand growth projections from the Dec 2024 LTLF whitepaper (not total BA energy). Ranges are low–high cases.',
            'direction': 'context',
            'min': 0,
            'max': 1000,
            'note': 'Incremental DC energy growth only—do not treat as MISO total load or as energized IT MW.',
            'source_ids': ['miso-ltlf-whitepaper-2024-12'],
            'series_start_year': 2030,
            'chart_default_start': 2030,
            'chart_default_end': 2044,
            'definition_stable': True,
            'pre_period_note': 'Reviewed catalog begins with whitepaper projection years 2030 and 2044.',
            'allowed_statuses': ['forecast'],
        },
        {
            'id': 'apps-customer-support-rph-delta-pct',
            'layer': 'applications',
            'title': 'Customer-support issues resolved per hour · generative-AI delta',
            'unit': '% change in issues resolved per hour',
            'geography': 'Study sample (Brynjolfsson/Li/Raymond)',
            'scope': 'QJE field study of a generative-AI assistant for customer-support agents. Positive values mean higher issues resolved per hour. Not a population-wide productivity estimate.',
            'direction': 'context',
            'min': -100,
            'max': 100,
            'note': 'Method-first applications outcome alongside METR RCT. Single study vintage; do not stitch to surveys.',
            'source_ids': ['brynjolfsson-li-raymond-qje-2025'],
            'series_start_year': 2025,
            'chart_default_start': 2025,
            'chart_default_end': 2025,
            'definition_stable': True,
            'pre_period_note': 'Single QJE study vintage; no earlier reviewed observations on this metric.',
            'allowed_statuses': ['observation', 'estimate'],
        },
        {
            'id': 'capital-guidance-tsmc',
            'layer': 'chips',
            'title': 'TSMC · capital spending guidance',
            'unit': 'USD billion',
            'geography': 'Global',
            'scope': 'Company-wide CapEx guidance for calendar 2026 from TSMC earnings disclosure. Not a shipped-wafer or CoWoS capacity measure.',
            'direction': 'context',
            'min': 0,
            'max': 10000,
            'note': 'Company-wide spending. Advanced packaging CapEx share language stays in notes; CoWoS wafer starts are not inferred.',
            'source_ids': ['tsmc-4q25-earnings-transcript'],
            'company': 'tsmc',
            'measurement_type': 'capex_announced_usd',
            'project': None,
            'allowed_statuses': ['company-commitment', 'forecast'],
            'series_start_year': 2026,
            'chart_default_start': 2026,
            'chart_default_end': 2030,
            'definition_stable': True,
            'pre_period_note': 'Reviewed catalog begins with 4Q25 transcript CY2026 CapEx guidance.',
        },
        {
            'id': 'tsmc-advanced-packaging-revenue-share-pct',
            'layer': 'chips',
            'title': 'TSMC advanced packaging · revenue share',
            'unit': '% of TSMC revenue',
            'geography': 'Global',
            'scope': 'Company commentary on advanced packaging revenue share (toward low-teens). Not CoWoS wafer-start capacity.',
            'direction': 'context',
            'min': 0,
            'max': 100,
            'note': 'Narrative low-teens outlook stored as approx mid-teens floor (13). Do not invent CoWoS WPM from this share.',
            'source_ids': ['tsmc-4q25-earnings-transcript'],
            'company': 'tsmc',
            'series_start_year': 2026,
            'chart_default_start': 2026,
            'chart_default_end': 2030,
            'definition_stable': True,
            'pre_period_note': 'Reviewed catalog begins with 4Q25 transcript packaging-share commentary for 2026.',
            'allowed_statuses': ['forecast', 'estimate', 'observation'],
        },
        {
            'id': 'sk-hynix-fab-investment-krw-trillion',
            'layer': 'chips',
            'title': 'SK hynix · fab facility investment commitment',
            'unit': 'KRW trillion',
            'geography': 'South Korea (Yongin Y2 + Cheongju M17)',
            'scope': 'Announced fab facility investment totaling ~54T KRW (35.2 + 19.1). Capital commitment, not shipped HBM volume.',
            'direction': 'context',
            'min': 0,
            'max': 1000,
            'note': 'Do not convert to HBM gigabyte shipments. Distinct from revenue-sk-hynix.',
            'source_ids': ['astra-hynix-fabs-20260807'],
            'company': 'sk-hynix',
            'allowed_statuses': ['company-commitment'],
            'series_start_year': 2026,
            'chart_default_start': 2026,
            'chart_default_end': 2030,
            'definition_stable': True,
            'pre_period_note': 'Reviewed catalog begins with the 2026 fab-facility investment announcement.',
        },
        {
            'id': 'microsoft-datacenter-wue',
            'layer': 'infrastructure',
            'title': 'Microsoft datacenter fleet · water usage effectiveness',
            'unit': 'L/kWh',
            'geography': 'Microsoft global datacenter fleet',
            'scope': 'Fleet-wide Water Usage Effectiveness disclosed on Microsoft Datacenters sustainability efficiency page. Not campus-specific withdrawal.',
            'direction': 'context',
            'min': 0,
            'max': 50,
            'note': 'Company fleet WUE; keep separate from Google Category-2 WUE and campus Mgal series.',
            'source_ids': ['microsoft-datacenter-efficiency'],
            'company': 'microsoft',
            'series_start_year': 2025,
            'chart_default_start': 2025,
            'chart_default_end': 2030,
            'definition_stable': True,
            'pre_period_note': 'Reviewed catalog begins with FY25 fleet WUE disclosure.',
            'allowed_statuses': ['observation', 'estimate'],
        },
        {
            'id': 'google-campus-water-council-bluffs-mgal',
            'layer': 'infrastructure',
            'title': 'Google Council Bluffs · annual water consumption',
            'unit': 'Mgal',
            'geography': 'Council Bluffs, Iowa (Google campus)',
            'scope': 'Campus annual water consumption from Alphabet FY2025 environmental indicators assurance. Not fleet WUE.',
            'direction': 'context',
            'min': 0,
            'max': 100000,
            'note': 'Campus Mgal only; do not sum into national DC water headlines without review.',
            'source_ids': ['alphabet-fy2025-env-indicators-assurance'],
            'company': 'alphabet',
            'series_start_year': 2025,
            'chart_default_start': 2025,
            'chart_default_end': 2030,
            'definition_stable': True,
            'pre_period_note': 'Reviewed catalog begins with CY2025 assurance-letter campus figure.',
            'allowed_statuses': ['observation'],
        },
        {
            'id': 'google-campus-water-the-dalles-mgal',
            'layer': 'infrastructure',
            'title': 'Google The Dalles · annual water consumption',
            'unit': 'Mgal',
            'geography': 'The Dalles, Oregon (Google campus)',
            'scope': 'Campus annual water consumption from Alphabet FY2025 environmental indicators assurance. Not fleet WUE.',
            'direction': 'context',
            'min': 0,
            'max': 100000,
            'note': 'Campus Mgal only; do not sum into national DC water headlines without review.',
            'source_ids': ['alphabet-fy2025-env-indicators-assurance'],
            'company': 'alphabet',
            'series_start_year': 2025,
            'chart_default_start': 2025,
            'chart_default_end': 2030,
            'definition_stable': True,
            'pre_period_note': 'Reviewed catalog begins with CY2025 assurance-letter campus figure.',
            'allowed_statuses': ['observation'],
        },
        {
            'id': 'google-campus-water-mayes-county-mgal',
            'layer': 'infrastructure',
            'title': 'Google Mayes County OK · annual water consumption',
            'unit': 'Mgal',
            'geography': 'Mayes County, Oklahoma (Google campus)',
            'scope': 'Campus annual water consumption from Alphabet FY2025 environmental indicators assurance. Not fleet WUE.',
            'direction': 'context',
            'min': 0,
            'max': 100000,
            'note': 'Campus Mgal only; do not sum into national DC water headlines without review.',
            'source_ids': ['alphabet-fy2025-env-indicators-assurance'],
            'company': 'alphabet',
            'series_start_year': 2025,
            'chart_default_start': 2025,
            'chart_default_end': 2030,
            'definition_stable': True,
            'pre_period_note': 'Reviewed catalog begins with CY2025 assurance-letter campus figure.',
            'allowed_statuses': ['observation'],
        },
        {
            'id': 'google-campus-water-new-albany-mgal',
            'layer': 'infrastructure',
            'title': 'Google New Albany OH · annual water consumption',
            'unit': 'Mgal',
            'geography': 'New Albany, Ohio (Google campus)',
            'scope': 'Campus annual water consumption from Alphabet FY2025 environmental indicators assurance. Not fleet WUE.',
            'direction': 'context',
            'min': 0,
            'max': 100000,
            'note': 'Campus Mgal only; do not sum into national DC water headlines without review.',
            'source_ids': ['alphabet-fy2025-env-indicators-assurance'],
            'company': 'alphabet',
            'series_start_year': 2025,
            'chart_default_start': 2025,
            'chart_default_end': 2030,
            'definition_stable': True,
            'pre_period_note': 'Reviewed catalog begins with CY2025 assurance-letter campus figure.',
            'allowed_statuses': ['observation'],
        },
        {
            'id': 'google-wue-category2',
            'layer': 'infrastructure',
            'title': 'Google data centers · WUE Category 2',
            'unit': 'L/kWh',
            'geography': 'Google data centers supporting LLM models',
            'scope': 'ISO WUE Category 2 (consumptive) fleet average cited in Google AI-at-scale environmental paper for prior calendar years.',
            'direction': 'context',
            'min': 0,
            'max': 50,
            'note': 'Category-2 consumptive WUE; distinct from campus Mgal and Microsoft fleet WUE.',
            'source_ids': ['google-ai-env-impact-scale'],
            'company': 'alphabet',
            'series_start_year': 2023,
            'chart_default_start': 2023,
            'chart_default_end': 2030,
            'definition_stable': True,
            'pre_period_note': 'Reviewed catalog begins with 2023–2024 Category-2 values stated in the AI-at-scale paper.',
            'allowed_statuses': ['observation', 'estimate'],
        },
    ]


def replaced_capex_metrics(catalog):
    """Upgrade Alphabet/Amazon/Microsoft CapEx guidance to primary IR + company-commitment."""
    out = []
    patches = {
        'capital-guidance-alphabet': {
            'scope': 'CY2026 company CapEx guidance from Alphabet Q2 2026 IR earnings call ($195–205B). Company-wide, not AI-only.',
            'source_ids': ['capital-alphabet-q2-2026-ir'],
            'allowed_statuses': ['forecast'],
            'note': 'Primary IR company commitment replaces prior AP attribution. Stored as forecast per capital-explorer contract.',
            'pre_period_note': 'Reviewed primary IR series begins with CY2026 guidance from the Q2 2026 call.',
        },
        'capital-guidance-aws': {
            'scope': 'CY2026 cash CapEx guidance of about $200B from Amazon written IR (Q4 results). Company-wide; includes businesses beyond AWS. Do not use unverified $220B figures.',
            'source_ids': ['capital-amazon-q4-2025-ir'],
            'allowed_statuses': ['forecast'],
            'note': 'Primary Amazon IR ~$200B only (company commitment). Prior AP $220B not retained. Forecast status per capital-explorer contract.',
            'pre_period_note': 'Reviewed primary IR series begins with CY2026 guidance in the Feb 2026 Q4 results release.',
        },
        'capital-guidance-microsoft': {
            'scope': 'CY2026 CapEx guidance ~$175B after finance→operating lease reclassification; finance leases included, operating leases excluded.',
            'source_ids': ['capital-msft-outlook'],
            'allowed_statuses': ['forecast'],
            'note': 'Company IR commitment after lease definition change. Forecast status per capital-explorer contract.',
            'pre_period_note': 'Reviewed series begins with CY2026 guidance from the FY26 Q4 earnings disclosure.',
        },
    }
    by_id = {m['id']: m for m in catalog['metrics']}
    for mid, patch in patches.items():
        m = copy.deepcopy(by_id[mid])
        m.update(patch)
        out.append(m)
    return out


def observations():
    o = []

    def add(**kwargs):
        base = {
            'upper': None,
            'retrieved_at': RETRIEVED,
            'method': 'curated',
        }
        base.update(kwargs)
        o.append(base)

    # PJM summer peak
    add(id='pjm-rto-summer-peak-2036', metric='pjm-rto-summer-peak-mw', year=2036, period='2036',
        value=222106, status='forecast', source='pjm-2026-load-report', precision='eq',
        note='Non-coincident unrestricted summer peak from 2026 Load Report. 10y growth +65,733 MW in report.')
    add(id='pjm-rto-summer-peak-2046', metric='pjm-rto-summer-peak-mw', year=2046, period='2046',
        value=253077, status='forecast', source='pjm-2026-load-report', precision='eq',
        note='Non-coincident unrestricted summer peak from 2026 Load Report. 20y growth +96,704 MW in report.')

    # SPP narrative peak
    add(id='spp-peak-load-itp-2025', metric='spp-peak-load-itp-gw', year=2025, period='2025',
        value=56, status='observation', source='spp-2025-itp-report', precision='approx',
        note='ITP exec-summary current peak load (~56 GW). Narrative "could rise" path; not Fig 2.1.')
    add(id='spp-peak-load-itp-2035', metric='spp-peak-load-itp-gw', year=2035, period='2035',
        value=109, status='forecast', source='spp-2025-itp-report', precision='approx',
        note='ITP exec-summary: could rise to ~109 GW within ~10 years. Distinct from Fig 2.1 coincident path.')

    # SPP coincident peaks
    for year, val in [(2026, 61.7), (2029, 66.5), (2034, 69.8), (2044, 76.4)]:
        add(id=f'spp-itp-coincident-peak-{year}', metric='spp-itp-coincident-peak-gw', year=year,
            period=str(year), value=val, status='forecast', source='spp-2025-itp-report', precision='approx',
            note=f'ITP Figure 2.1 coincident peak for {year}. Lower path than exec-summary 56→109 GW narrative.')

    # ERCOT TSP vs studied
    add(id='ercot-tsp-peak-2031', metric='ercot-tsp-peak-forecast-2031-gw', year=2031, period='2031',
        value=218, status='forecast', source='ercot-constraints-needs-2025-12', precision='approx',
        note='TSP peak forecast ~218 GW for 2031 (Dec 2025 constraints report).')
    add(id='ercot-studied-peak-2031', metric='ercot-studied-peak-2031-gw', year=2031, period='2031',
        value=159, status='forecast', source='ercot-constraints-needs-2025-12', precision='approx',
        note='Studied peak ~159 GW for 2031 (Dec 2025 constraints report).')

    # MISO coincident peak
    add(id='miso-coincident-peak-2024', metric='miso-coincident-peak-ltlf-gw', year=2024, period='2024',
        value=122, status='observation', source='miso-ltlf-whitepaper-2024-12', precision='approx',
        note='LTLF whitepaper coincident peak ~122 GW (2024).')
    add(id='miso-coincident-peak-2044', metric='miso-coincident-peak-ltlf-gw', year=2044, period='2044',
        value=152, upper=186, status='forecast', source='miso-ltlf-whitepaper-2024-12', precision='range',
        note='LTLF whitepaper 2044 coincident peak low–high 152–186 GW. Not the news 163 GW figure.')

    # MISO DC energy
    add(id='miso-dc-energy-2030', metric='miso-datacenter-energy-twh', year=2030, period='2030',
        value=42, upper=80, status='forecast', source='miso-ltlf-whitepaper-2024-12', precision='range',
        note='Incremental DC energy demand growth projection by 2030 (42–80 TWh).')
    add(id='miso-dc-energy-2044', metric='miso-datacenter-energy-twh', year=2044, period='2044',
        value=149, upper=241, status='forecast', source='miso-ltlf-whitepaper-2024-12', precision='range',
        note='Incremental DC energy demand growth projection by 2044 (149–241 TWh).')

    # CapEx upgrades (upsert existing obs ids)
    add(id='capital-guidance-alphabet-2026-reviewed', metric='capital-guidance-alphabet', year=2026,
        period='CY2026 guidance', value=195, upper=205, status='forecast',
        source='capital-alphabet-q2-2026-ir', precision='range',
        note='CY2026 CapEx guidance $195–205B from Alphabet Q2 2026 IR (company commitment; forecast per explorer).')
    add(id='capital-guidance-aws-2026-reviewed', metric='capital-guidance-aws', year=2026,
        period='CY2026 guidance', value=200, status='forecast',
        source='capital-amazon-q4-2025-ir', precision='approx',
        note='CY2026 CapEx about $200B from Amazon written IR. $220B not in this primary. Forecast per explorer.')
    add(id='capital-guidance-microsoft-2026-reviewed', metric='capital-guidance-microsoft', year=2026,
        period='CY2026 guidance', value=175, status='forecast',
        source='capital-msft-outlook', precision='approx',
        note='CY2026 ~$175B after lease reclass (finance in; operating out). Company commitment; forecast per explorer.')

    # Apps Brynjolfsson
    add(id='apps-customer-support-rph-2025', metric='apps-customer-support-rph-delta-pct', year=2025,
        period='QJE study', value=15, status='observation',
        source='brynjolfsson-li-raymond-qje-2025', precision='approx',
        note='+15% issues resolved per hour with generative-AI assistant (Brynjolfsson/Li/Raymond QJE).')

    # TSMC
    add(id='capital-guidance-tsmc-2026', metric='capital-guidance-tsmc', year=2026,
        period='CY2026 guidance', value=52, upper=56, status='company-commitment',
        source='tsmc-4q25-earnings-transcript', precision='range',
        note='TSMC CY2026 CapEx guidance $52–56B from 4Q25 transcript.')
    add(id='tsmc-packaging-revenue-share-2026', metric='tsmc-advanced-packaging-revenue-share-pct', year=2026,
        period='2026', value=13, status='forecast',
        source='tsmc-4q25-earnings-transcript', precision='approx',
        note='Advanced packaging revenue share toward low-teens (~13% midpoint of narrative). Not CoWoS WPM.')

    # SK hynix fab
    add(id='sk-hynix-fab-investment-2026', metric='sk-hynix-fab-investment-krw-trillion', year=2026,
        period='2026 announcement', value=54, status='company-commitment',
        source='astra-hynix-fabs-20260807', precision='approx',
        note='~54T KRW fab investment commitment (35.2 + 19.1 for Y2 + M17). Not HBM volume.')

    # Water
    add(id='microsoft-datacenter-wue-fy25', metric='microsoft-datacenter-wue', year=2025,
        period='FY25', value=0.27, status='observation',
        source='microsoft-datacenter-efficiency', precision='approx',
        note='Microsoft fleet WUE 0.27 L/kWh for FY25 from Datacenters efficiency page.')
    add(id='google-water-council-bluffs-2025', metric='google-campus-water-council-bluffs-mgal', year=2025,
        period='CY2025', value=1346.0, status='observation',
        source='alphabet-fy2025-env-indicators-assurance', precision='eq',
        note='Council Bluffs campus water consumption 1,346.0 Mgal (CY2025 assurance).')
    add(id='google-water-the-dalles-2025', metric='google-campus-water-the-dalles-mgal', year=2025,
        period='CY2025', value=469.0, status='observation',
        source='alphabet-fy2025-env-indicators-assurance', precision='eq',
        note='The Dalles campus water consumption 469.0 Mgal (CY2025 assurance).')
    add(id='google-water-mayes-county-2025', metric='google-campus-water-mayes-county-mgal', year=2025,
        period='CY2025', value=1081.4, status='observation',
        source='alphabet-fy2025-env-indicators-assurance', precision='eq',
        note='Mayes County OK campus water consumption 1,081.4 Mgal (CY2025 assurance).')
    add(id='google-water-new-albany-2025', metric='google-campus-water-new-albany-mgal', year=2025,
        period='CY2025', value=835.7, status='observation',
        source='alphabet-fy2025-env-indicators-assurance', precision='eq',
        note='New Albany OH campus water consumption 835.7 Mgal (CY2025 assurance).')
    add(id='google-wue-category2-2023', metric='google-wue-category2', year=2023,
        period='2023', value=1.15, status='observation',
        source='google-ai-env-impact-scale', precision='eq',
        note='Google WUE Category 2 = 1.15 L/kWh for 2023 (AI-at-scale environmental paper).')
    add(id='google-wue-category2-2024', metric='google-wue-category2', year=2024,
        period='2024', value=1.15, status='observation',
        source='google-ai-env-impact-scale', precision='eq',
        note='Google WUE Category 2 = 1.15 L/kWh for 2024 (AI-at-scale environmental paper).')

    return o


EVENTS = [
    {
        'id': 'pjm-2026-ltf-large-load-firm-nonfirm',
        'layer': 'energy',
        'date': '2026-01-14',
        'title': 'PJM 2026 LTF: firm vs non-firm large-load derate language',
        'summary': 'The 2026 PJM Load Forecast Report discusses firm versus non-firm treatment and derate language for large-load additions. No single data-center GW total is taken from this LTF narrative; LAS ~30 GW planning figure remains on pjm-datacenter-growth-2025-2030-gw. Grade A operator disclosure—no invented energized MW.',
        'source': 'pjm-2026-load-report',
        'kind': 'Constraint update',
        'grade': 'A',
    },
    {
        'id': 'policy-2025-17893',
        'layer': 'chips',
        'date': '2025-09-16',
        'title': 'BIS Entity List additions and revisions (Doc. 2025-17893)',
        'summary': 'Final rule (Doc. 2025-17893, 90 FR 44496) adds 32 entities to the Entity List (China 23, Turkey 3, UAE 2, and others), revises one Russia address entry, and corrects typographical errors in 27 listings. Grade A government action only—no chip shipment volumes inferred.',
        'source': 'federal-register-2025-17893',
        'kind': 'Government action',
        'grade': 'A',
    },
    {
        'id': 'policy-2025-19001',
        'layer': 'chips',
        'date': '2025-09-30',
        'title': 'BIS Affiliates rule: 50% ownership Entity List expansion',
        'summary': 'Interim final rule (Doc. 2025-19001) extends Entity List, MEU List, and certain SDN-linked EAR restrictions to foreign affiliates owned 50% or more by listed parties (Affiliates rule), with Temporary General License and Red Flag 29. Grade A government action only—no tonnage.',
        'source': 'federal-register-2025-19001',
        'kind': 'Government action',
        'grade': 'A',
    },
    {
        'id': 'policy-2025-19508',
        'layer': 'chips',
        'date': '2025-10-09',
        'title': 'BIS Entity List additions (Doc. 2025-19508)',
        'summary': 'Final rule (Doc. 2025-19508, 90 FR 48193) adds 29 entries (26 entities and 3 addresses) under China, Turkey, and the UAE. Grade A government action only—no chip shipment volumes inferred.',
        'source': 'federal-register-2025-19508',
        'kind': 'Government action',
        'grade': 'A',
    },
    {
        'id': 'policy-2025-19846',
        'layer': 'chips',
        'date': '2025-11-12',
        'title': 'BIS one-year suspension of Affiliates rule expansion',
        'summary': 'Final rule (Doc. 2025-19846, 90 FR 50857) imposes a one-year suspension of the Affiliates rule (through 2026-11-09) before scheduled reinstatement. Grade A government action only—no tonnage.',
        'source': 'federal-register-2025-19846',
        'kind': 'Government action',
        'grade': 'A',
    },
    {
        'id': 'policy-2025-19858',
        'layer': 'chips',
        'date': '2025-11-12',
        'title': 'BIS Entity List revisions (Arrow China removal)',
        'summary': 'Final rule (Doc. 2025-19858, 90 FR 50858) removes Arrow China Electronics Trading Co., Ltd. and six aliases under Arrow Electronics (Hong Kong) Co., Ltd. Grade A government action only—no tonnage.',
        'source': 'federal-register-2025-19858',
        'kind': 'Government action',
        'grade': 'A',
    },
    {
        'id': 'policy-2026-17230',
        'layer': 'chips',
        'date': '2026-08-24',
        'title': 'BIS Entity List removal (Doc. 2026-17230)',
        'summary': 'Final rule (Doc. 2026-17230, 91 FR 54657) removes one Turkey-destination entity from the Entity List. Grade A government action only—no chip shipment volumes inferred.',
        'source': 'federal-register-2026-17230',
        'kind': 'Government action',
        'grade': 'A',
    },
    {
        'id': 'policy-2026-17231',
        'layer': 'chips',
        'date': '2026-08-24',
        'title': 'BIS Entity List revisions (Doc. 2026-17231)',
        'summary': 'Final rule (Doc. 2026-17231) removes two Hong Kong addresses associated with Arrow Electronics (Hong Kong) Co., Ltd. from the Entity List under China. Grade A government action only—no tonnage.',
        'source': 'federal-register-2026-17231',
        'kind': 'Government action',
        'grade': 'A',
    },
    {
        'id': 'wh-eo-14318-dc-permitting-2025-07-23',
        'layer': 'infrastructure',
        'date': '2025-07-23',
        'title': 'EO: Accelerating Federal Permitting of Data Center Infrastructure',
        'summary': 'Presidential action (2025-07-23) directs agencies to accelerate federal permitting for data-center and related energy/component infrastructure. Defines a Data Center Project as a facility requiring greater than 100 MW of new load dedicated to AI inference, training, simulation, or synthetic data generation. Grade A government action—no MW build totals inferred.',
        'source': 'wh-eo-dc-permitting-2025-07-23',
        'kind': 'Government action',
        'grade': 'A',
    },
    {
        'id': 'apps-jagged-frontier-orgsci-2026',
        'layer': 'applications',
        'date': '2026-03-11',
        'title': "Dell'Acqua et al.: jagged technological frontier RCT",
        'summary': "Organization Science field experiment (758 BCG knowledge workers; DOI 10.1287/orsc.2025.21838): within-frontier tasks +12.2% tasks completed and +25.1% faster with GPT-4 access; outside-frontier complex managerial task −19% correct solutions. Independent research (grade B)—method-first, not a seat-count or universal ROI.",
        'source': 'dellacqua-jagged-frontier-orsc-2026',
        'kind': 'Research finding',
        'grade': 'B',
    },
]


def patch_grid_operators(path: Path):
    data = load(path)
    notes = {
        'pjm': (
            ' Curated 2026 Load Report summer-peak path added 2026-09-22 as pjm-rto-summer-peak-mw '
            '(2036=222,106 MW; 2046=253,077 MW); firm/non-firm derate language in event '
            'pjm-2026-ltf-large-load-firm-nonfirm. LAS ~30 GW figure remains separate.'
        ),
        'miso': (
            ' Curated Dec 2024 LTLF whitepaper peaks and incremental DC energy added 2026-09-22 as '
            'miso-coincident-peak-ltlf-gw (122 GW 2024; 152–186 GW 2044) and miso-datacenter-energy-twh. '
            'News 163 GW-by-2035 remains held.'
        ),
        'spp': (
            ' Curated 2025 ITP figures added 2026-09-22: spp-peak-load-itp-gw (56→109 GW narrative) and '
            'spp-itp-coincident-peak-gw (Fig 2.1: 61.7/66.5/69.8/76.4). Keep narrative vs Fig 2.1 separate.'
        ),
        'ercot': (
            ' Curated TSP vs studied 2031 peaks added 2026-09-22 as ercot-tsp-peak-forecast-2031-gw (218) '
            'and ercot-studied-peak-2031-gw (159) from the Dec 2025 constraints report.'
        ),
    }
    for op in data.get('operators', []):
        oid = op.get('id')
        if oid in notes:
            note = op.get('note') or ''
            marker = {
                'pjm': 'pjm-rto-summer-peak-mw',
                'miso': 'miso-coincident-peak-ltlf-gw',
                'spp': 'spp-peak-load-itp-gw',
                'ercot': 'ercot-tsp-peak-forecast-2031-gw',
            }[oid]
            if marker not in note:
                op['note'] = note + notes[oid]
    data['reviewed_at'] = '2026-09-22T07:24:01Z'
    return data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()
    catalog = load(ROOT / 'research/catalog.json')
    new_m = new_metrics()
    replaced = replaced_capex_metrics(catalog)
    obs = observations()
    print(
        f'Would add {len(SOURCES)} sources (skip existing), {len(new_m)} new metrics, '
        f'{len(replaced)} replaced CapEx metrics, {len(obs)} observations, {len(EVENTS)} events'
    )
    for o in obs:
        print(f'  obs {o["id"]}: {o["metric"]}={o["value"]}'
              + (f'-{o["upper"]}' if o.get('upper') is not None else '')
              + f' ({o["status"]}/{o["precision"]})')
    for e in EVENTS:
        print(f'  event {e["id"]}: {e["title"][:72]}')
    if not args.apply:
        print('Dry-run only. Re-run with --apply to write.')
        return
    receipt = apply_changes(
        ROOT,
        importer_id='curated-exhaustive-20260922',
        new_sources=SOURCES,
        new_metrics=new_m + replaced,
        replace_metric_ids=[m['id'] for m in replaced],
        new_observations=obs,
        new_events=EVENTS,
        snapshot={'label': 'curated-exhaustive-20260922', 'retrieved_at': RETRIEVED},
    )
    grid_path = ROOT / 'research/grid-operators.json'
    save(grid_path, patch_grid_operators(grid_path))
    print('Applied exhaustive tranche and updated grid-operators.json.')
    print('Receipt:', {k: receipt.get(k) for k in (
        'sources_touched', 'metrics_added', 'metrics_replaced', 'records_added', 'events_added')})


if __name__ == '__main__':
    main()
