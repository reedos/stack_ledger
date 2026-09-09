"""Private question-level accounting; only existing human review can resolve one."""
import json
from editorial_review import events, queue
from atomic_json import save


def report(root, folder):
    questions = {}
    for path in (folder/'batches').glob('*.json'):
        item = json.loads(path.read_text(encoding='utf-8'))
        for attempt in (item.get('discovery') or {}).get('attempts',[]):
            if not attempt.get('question'):continue  # Do not invent historical attribution.
            key = (attempt['layer'],attempt['question'])
            row = questions.setdefault(key,{'layer':key[0],'question':key[1],'attempts':0,
                'screened':0,'empty':0,'partial_exposures':0,'inaccessible':0,'proposal_ids':set()})
            row['attempts']+=1
            outcome=attempt.get('outcome')
            row['screened']+=outcome in {'no_findings','screen_rejected','pending_review'}
            row['empty']+=outcome=='no_findings'
            row['inaccessible']+=outcome=='source_inaccessible'
            row['partial_exposures']+=attempt.get('screen_coverage',{}).get('complete') is False
            if attempt.get('proposal_id'):row['proposal_ids'].add(attempt['proposal_id'])
    rows=[]
    for row in questions.values():
        row['proposal_ids']=sorted(row['proposal_ids'])
        row['status']='proposals_need_review' if row['proposal_ids'] else 'unresolved'
        rows.append(row)
    # Read the existing question queue and append-only human result log.
    latest={}
    for event in events(root):
        if event.get('kind')=='research_question':latest[event['id']]=event
    reviewed=[]
    for path in queue(root).glob('question-*.json'):
        item=json.loads(path.read_text(encoding='utf-8'))
        reviewed.append({'id':item['id'],'question':item['question']['question'],
                         'latest_review':latest.get(item['id'])})
    result={'session':folder.name,'discovery_questions':rows,'editorial_questions':reviewed,
            'authority':'Collection activity and proposals do not resolve questions. Only the existing human result review does.',
            'historical_limit':'Attempts without recorded question context cannot be attributed.'}
    save(folder/'research-progress.json',result)
    lines=['# Research questions and evidence gaps','',result['authority'],result['historical_limit'],'']
    for row in rows:
        lines.extend(['    '+row['layer']+': '+' '.join(row['question'].split()),
                      f"    {row['status']}; {row['attempts']} attempts; {row['screened']} screens; {row['empty']} empty; {row['partial_exposures']} partial exposures; {row['inaccessible']} inaccessible; {len(row['proposal_ids'])} linked proposals.",''])
    lines.extend(['## Existing editorial question reviews',''])
    for row in reviewed:
        review=row['latest_review'] or {}
        lines.append('    '+row['id']+': '+review.get('status','pending_review')+'; '+' '.join(row['question'].split()))
    (folder/'research-progress.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return result
