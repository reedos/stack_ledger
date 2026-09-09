"""Offline retained-run audit. No network, inference, approvals or publication."""
import argparse
import json
import re
from collections import Counter
from pathlib import Path

from atomic_json import save
from evidence_text import numeric_tokens, select_windows, coverage
from research import digest, numeric_support

ROOT=Path(__file__).resolve().parents[1]


def evaluate(root, session):
    if not re.fullmatch(r'[a-f0-9]{32}',session):raise ValueError('Invalid session ID')
    folder=root/'.local/sessions'/session
    if not (folder/'batches').is_dir():raise ValueError('No retained session batches')
    outcomes=Counter();empty=[];quarantine=[];searches=0;search_errors=0
    for path in sorted((folder/'batches').glob('*.json')):
        batch=json.loads(path.read_text(encoding='utf-8'));private=batch.get('discovery') or {}
        searches+=private.get('search_calls',0)
        search_errors+=sum(e.get('stage')=='search' for e in private.get('errors',[]))
        for attempt in private.get('attempts',[]):
            outcomes[attempt.get('outcome','unknown')]+=1
            if attempt.get('outcome')=='no_findings':empty.append(attempt)
        run_id=(batch.get('monitoring') or {}).get('id')
        saved=root/'.local/runs'/f'{run_id}.json'
        if run_id and saved.exists():
            for item in json.loads(saved.read_text(encoding='utf-8')).get('quarantine',[]):
                c=item.get('candidate',{});evidence=c.get('evidence','')
                text=' '.join(str(c.get(k,'')) for k in ['title','summary'])
                numbers=numeric_tokens(text)
                supported=all(numeric_support(float(t.replace(',','')),evidence) for t in numbers)
                quarantine.append({'run':run_id,'source':item['source'],'original_reason':item.get('reason'),
                    'numeric_prose_recheck':'passes_numeric_only' if numbers and supported else 'not_cleared',
                    'requires_full_review':True})
    # Older attempt receipts did not record body hashes: recover from retained
    # evidence URL only when exactly one saved version exists. Do not guess.
    by_url={}
    for path in (root/'.local/discovery/evidence').glob('*.json'):
        item=json.loads(path.read_text(encoding='utf-8'))
        by_url.setdefault(item['url'],[]).append(item)
    inventory=[]
    for attempt in empty:
        versions=by_url.get(attempt['url'],[])
        h=attempt.get('document_sha256')
        matches=[v for v in versions if not h or v['sha256']==h]
        # Alias URLs may share one evidence file, with the most recent URL stored.
        if h and not matches:
            path=root/'.local/discovery/evidence'/(h+'.json')
            if path.exists():matches=[json.loads(path.read_text(encoding='utf-8'))]
        row={'url':attempt['url'],'layer_at_collection':attempt.get('layer'),'document_available':len(matches)==1}
        if len(matches)==1:
            doc=matches[0];text=doc['text']
            if digest(text)!=doc['sha256']:raise ValueError('Retained evidence hash mismatch')
            row.update(sha256=doc['sha256'],characters=len(text),old_prefix_was_partial=len(text)>18000)
        inventory.append(row)
    labels=json.loads((root/'research/collection-audit-cases.json').read_text(encoding='utf-8'))
    cases=[]
    empty_hashes={r.get('sha256') for r in inventory}
    for label in labels['cases']:
        path=root/'.local/discovery/evidence'/(label['sha256']+'.json')
        case=dict(label,retained_evidence_available=path.exists(),in_session_empty_results=label['sha256'] in empty_hashes)
        if path.exists():
            text=json.loads(path.read_text(encoding='utf-8'))['text']
            if digest(text)!=label['sha256']:raise ValueError('Case hash mismatch')
            case['new_exposure']=coverage(text,select_windows(text,label['rationale'],18000))
        cases.append(case)
    result={'session':session,'searches':searches,'search_errors':search_errors,'outcomes':dict(outcomes),
            'empty_inventory':inventory,'quarantine_numeric_recheck':quarantine,'case_assessments':cases,
            'limits':labels['scope']+' This command does not evaluate the live model; optional model replay has a separate receipt. Numeric rechecks do not validate scope, dates or meaning.'}
    output=root/'.local/evaluations'/('collection-'+session)
    save(output.with_suffix('.json'),result)
    lines=['# Retained research-run audit','',result['limits'],'',
           f'Searches: {searches}; errors: {search_errors}. Empty-result attempts: {len(empty)}.',
           f"Matched saved documents: {sum(v['document_available'] for v in inventory)}; old prefix omitted text: {sum(v.get('old_prefix_was_partial',False) for v in inventory)}.",'',
           '## Purposive saved-document review','']
    for case in cases:lines.extend([f"- {case['id']}: {case['assessment']}. {case['rationale']}"])
    lines.extend(['','## Quarantine diagnostic','',f'{len(quarantine)} retained quarantines examined for numeric prose support only. Full evidence review is still required.',''])
    for q in quarantine:
        lines.append('    '+q['source']+': '+q['original_reason']+' -> '+q['numeric_prose_recheck'])
    output.with_suffix('.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session',required=True)
    args=parser.parse_args()
    result=evaluate(ROOT,args.session)
    print(json.dumps({k:result[k] for k in ['session','searches','search_errors','outcomes','limits']},indent=2))
