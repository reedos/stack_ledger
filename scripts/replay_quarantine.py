"""Replay retained quarantines through the deterministic evidence checks. No model calls.

Reads private run receipts and cached documents under .local/, re-runs the current
validator logic (evidence location, numeric support, publication-year allowance,
markup rules) and reports which candidates the *current* code would still reject.
This measures validator behaviour, not model accuracy, and approves nothing.

    python scripts/replay_quarantine.py            # print a summary
    python scripts/replay_quarantine.py --write    # also save .local/evaluations/quarantine-replay.{md,json}
"""
import argparse
import glob
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parent))
from evidence_text import numeric_tokens, locate, select_windows
from research import numeric_support, load
from model_rules import NOTE_EVIDENCE_MAX, METRIC_EVIDENCE_MAX
from validate import text as text_rule

ROOT=Path(__file__).resolve().parents[1]
LOCAL=ROOT/'.local'
DETERMINISTIC=('Note includes an unsupported number','Note evidence not found','Value not supported by exact numeric token','Evidence not found in fetched document','Evidence crosses omitted source text','Markup/control characters are not allowed','Upper bound not supported','Year not found in source')

def documents():
    by_url={}
    for path in glob.glob(str(LOCAL/'evidence'/'*.json')):
        try:d=json.loads(Path(path).read_text(encoding='utf-8'))
        except (OSError,ValueError):continue
        if isinstance(d,dict) and isinstance(d.get('text'),str) and d.get('url'):
            if d.get('retrieved_at','')>=by_url.get(d['url'],{}).get('retrieved_at',''):by_url[d['url']]=d
    return by_url

def sources():
    out={}
    for path in [ROOT/'research/sources.json',ROOT/'site/data/ledger.json']:
        for s in load(path)['sources']:out[s['id']]=s
    return out

def recheck_note(c,document,source):
    windows=select_windows(document,'',24000)
    if not isinstance(c.get('evidence'),str) or len(c['evidence'])<20:return 'evidence length out of range','note'
    located=next((l for l in (locate(w['text'],c['evidence']) for w in windows) if l),None)
    if located is None:return 'evidence not found','note'
    if len(located)>NOTE_EVIDENCE_MAX:return f'evidence located but {len(located)} chars exceeds the new {NOTE_EVIDENCE_MAX} cap','note'
    year=(source.get('published') or '')[:4]
    missing=[t for t in numeric_tokens(c.get('title','')+' '+c.get('summary','')) if not numeric_support(float(t.replace(',','')),located) and t!=year]
    if missing:return 'unsupported number: '+', '.join(missing),'note'
    try:text_rule(c.get('title',''),250);text_rule(c.get('summary',''),1000)
    except ValueError as e:return str(e),'note'
    return 'passes deterministic checks','note'

def recheck_observation(c,document,source):
    windows=select_windows(document,'',24000)
    if not isinstance(c.get('evidence'),str) or len(c['evidence'])<20:return 'evidence length out of range','observation'
    located=next((l for l in (locate(w['text'],c['evidence']) for w in windows) if l),None)
    if located is None:return 'evidence not found','observation'
    if len(located)>METRIC_EVIDENCE_MAX:return f'evidence located but {len(located)} chars exceeds the {METRIC_EVIDENCE_MAX} cap','observation'
    if not isinstance(c.get('value'),(int,float)) or not numeric_support(float(c['value']),located):return 'value not supported','observation'
    if c.get('upper') is not None and not numeric_support(float(c['upper']),located):return 'upper bound not supported','observation'
    if not (str(c.get('year')) in document or (source.get('published') or '').startswith(str(c.get('year')))):return 'year not found','observation'
    try:text_rule(c.get('note') or 'x',500);text_rule(c.get('period',''),80)
    except ValueError as e:return str(e),'observation'
    return 'passes deterministic checks','observation'

def replay():
    docs=documents();srcs=sources();rows=[]
    for path in sorted(glob.glob(str(LOCAL/'runs'/'*.json'))):
        try:d=json.loads(Path(path).read_text(encoding='utf-8'))
        except (OSError,ValueError):continue
        for q in d.get('quarantine',[]) or []:
            c=q.get('candidate') or {};original=str(q.get('reason') or '')
            row={'run':Path(path).stem,'source':q.get('source'),'original_reason':original[:120],'kind':'note' if 'title' in c else 'observation' if 'metric' in c else 'unknown'}
            if not original.startswith(DETERMINISTIC):
                row['replay']='reviewer rejection, not replayed';rows.append(row);continue
            source=srcs.get(q.get('source'));doc=docs.get((source or {}).get('url'))
            if not source or not doc:
                row['replay']='document not cached';rows.append(row);continue
            fn=recheck_note if row['kind']=='note' else recheck_observation
            row['replay']=fn(c,doc['text'],source)[0];rows.append(row)
    return rows

def report(rows):
    deterministic=[r for r in rows if r['replay']!='reviewer rejection, not replayed']
    replayed=[r for r in deterministic if r['replay']!='document not cached']
    passing=[r for r in replayed if r['replay']=='passes deterministic checks']
    lines=['# Quarantine replay through current deterministic checks','',f'Generated {datetime.now(timezone.utc).isoformat(timespec="seconds")}. No model calls. Passing the deterministic checks means the candidate would now reach the reviewer pass; it is not acceptance.','',
           f'Retained quarantines: {len(rows)} · deterministic rejections: {len(deterministic)} · replayable (document cached): {len(replayed)} · now pass deterministic checks: {len(passing)}','','## By original reason','','| Original reason | Total | Now pass | Still fail |','|---|---|---|---|']
    groups=defaultdict(list)
    for r in replayed:groups[r['original_reason']].append(r)
    for reason,items in sorted(groups.items(),key=lambda kv:-len(kv[1])):
        ok=sum(1 for r in items if r['replay']=='passes deterministic checks')
        lines.append(f'| {reason} | {len(items)} | {ok} | {len(items)-ok} |')
    lines+=['','## Remaining failures','']
    remaining=Counter(r['replay'] for r in replayed if r['replay']!='passes deterministic checks')
    lines+=[f'- {n} × {k}' for k,n in remaining.most_common()] or ['- none']
    lines+=['','## Per candidate','','| Source | Kind | Original reason | Replay |','|---|---|---|---|']
    lines+=[f"| {r['source']} | {r['kind']} | {r['original_reason'][:60]} | {r['replay'][:80]} |" for r in deterministic]
    return '\n'.join(lines)

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__.splitlines()[0]);parser.add_argument('--write',action='store_true')
    args=parser.parse_args(argv)
    rows=replay();md=report(rows)
    print(md)
    if args.write:
        out=LOCAL/'evaluations';out.mkdir(parents=True,exist_ok=True)
        (out/'quarantine-replay.md').write_text(md,encoding='utf-8')
        (out/'quarantine-replay.json').write_text(json.dumps(rows,indent=1,ensure_ascii=False),encoding='utf-8')
    return 0

if __name__=='__main__':sys.exit(main())
