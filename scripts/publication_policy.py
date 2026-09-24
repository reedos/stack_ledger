"""Apply catalog packages that a reviewed publication policy says need no per-item human review.

Owner decision, September 9, 2026: human review is for headline content and for replacing
figures already on the site; additions from credible authorities flow to the site
automatically. research/publication-policy.json states the exact rules. Every automatic
application still runs the isolated preview, is recorded as an approval event with the
policy label, and publishes through the same path as a human approval, so the review log
and Git history show precisely what happened and why.

    python scripts/publication_policy.py            # list pending packages and whether the policy admits them
    python scripts/publication_policy.py --apply    # apply every admitted package, one at a time
"""
import argparse
import json
import sys
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0,str(Path(__file__).resolve().parent))
from validate import require, text, timestamp

ROOT=Path(__file__).resolve().parents[1]


def policy(root=ROOT):
    p=json.loads((root/'research/publication-policy.json').read_text(encoding='utf-8'))
    require(set(p)=={'version','reviewed_at','owner_decision','auto_apply','always_human'} and p['version']==1,'Unexpected publication policy shape')
    timestamp(p['reviewed_at']);text(p['owner_decision'],1000)
    a=p['auto_apply']
    require(set(a)=={'enabled','reviewer_label','authors','targets','new_entries_only','project_stages','max_source_rank','require_passing_preview','max_changes_per_package','metric_measurement_types','project_updates','same_source_relabel','same_page_revisions'},'Unexpected auto_apply fields')
    r=a['same_page_revisions']
    require(isinstance(r,dict) and set(r)=={'enabled','author','max_ratio','statuses'} and type(r['enabled']) is bool and isinstance(r['author'],str) and r['author'],'Invalid same_page_revisions rule')
    require(isinstance(r['max_ratio'],(int,float)) and 1<r['max_ratio']<=3 and r['author'] not in a['authors'],'Same-page revisions need a ratio ceiling of at most 3 and their own author')
    require(isinstance(r['statuses'],list) and set(r['statuses'])<={'forecast','company-commitment','government-target'},'Same-page revisions apply only to forward-looking figures')
    require(a['project_updates']=='append_observations_only' and all(isinstance(x,str) for x in a['metric_measurement_types']),'Invalid policy update rules')
    require(type(a['enabled']) is bool and a['new_entries_only'] is True and a['require_passing_preview'] is True,'Policy must keep new-entries-only and passing-preview rules')
    require(type(a['same_source_relabel']) is bool,'Invalid same_source_relabel flag')
    require(set(a['targets'])<={'project','source','note','observation','metric'},'Policy may not auto-apply companies or products')
    require(type(a['max_source_rank']) is int and 1<=a['max_source_rank']<=3,'Invalid source rank ceiling')
    require(all(isinstance(x,str) and x for x in a['authors']+a['project_stages']) and type(a['max_changes_per_package']) is int and 1<=a['max_changes_per_package']<=100,'Invalid policy lists')
    text(a['reviewer_label'],60)
    for line in p['always_human']:text(line,300)
    return p


def source_ranks(registry):
    """host -> best (lowest) reviewed collection rank among registered sources on that host."""
    ranks={}
    for s in registry['sources']:
        host=urlparse(s['url']).hostname;rank=registry['collection'].get(s['id'],{}).get('rank')
        if host and rank is not None:ranks[host]=min(ranks.get(host,9),rank)
    return ranks


OBSERVATION_RELABEL_KEEP={'id','metric','value','upper','status','source','precision','method'}
OBSERVATION_RELABEL_MUTABLE={'period','year','note','retrieved_at','correction_of','superseded_by','correction_reason'}


def same_source_relabel(before,after):
    """True when `after` only relabels an existing observation: the figure, its status, source and
    metric are untouched, and only period/year (kept internally consistent), note, retrieved_at or a
    correction-chain field differ. Figure values, statuses and sources always need a person."""
    if not isinstance(before,dict) or not isinstance(after,dict):return False
    if before==after:return False
    if any(before.get(k)!=after.get(k) for k in OBSERVATION_RELABEL_KEEP):return False
    if not set(before)|set(after)<=OBSERVATION_RELABEL_KEEP|OBSERVATION_RELABEL_MUTABLE:return False
    period=str(after.get('period',''))
    return period[:4].isdigit() and int(period[:4])==after.get('year')


def same_page_revision(package,rule):
    """(admitted, reasons) for a package of same-page revisions (forecast_edition.REVISION_AUTHOR).

    Owner decision, 09/23/2026: a page that updates in place may replace its own earlier figure
    without a per-item review. Admitted only when every change is exactly that: a new figure from
    the same registered source, same metric, year, period, status and precision, retiring that
    source's own earlier figure, within max_ratio of it; the earlier figure changes only by gaining
    superseded_by. Anything else, including a value that moved further (a unit or scale slip),
    goes to the owner."""
    changes=package.get('changes',[])
    if not changes:return False,['empty revision package']
    added={c['id']:c['after'] for c in changes if c.get('target')=='observation' and c.get('before') is None}
    retired={c['id']:c for c in changes if c.get('target')=='observation' and c.get('before') is not None}
    if len(added)+len(retired)!=len(changes):return False,['a same-page revision changes only observations']
    for rid,c in retired.items():
        if c['after']!=dict(c['before'],superseded_by=c['after'].get('superseded_by')) or 'superseded_by' in c['before']:
            return False,[f'record {rid} changes more than gaining superseded_by']
    claimed=set()
    for nid,new in added.items():
        olds=new.get('edition_supersedes') or []
        if len(olds)!=1 or olds[0] not in retired:return False,[f'record {nid} must replace exactly one earlier figure in this package']
        old=retired[olds[0]]['before'];claimed.add(olds[0])
        if retired[olds[0]]['after'].get('superseded_by')!=nid:return False,[f'record {olds[0]} is not retired by {nid}']
        if any(new.get(k)!=old.get(k) for k in ('metric','source','year','period','status','precision')):
            return False,[f'record {nid} changes more than the value of {olds[0]}']
        if new.get('status') not in rule['statuses']:return False,[f'record {nid} is not a forward-looking figure']
        if new.get('method')!='automated':return False,[f'record {nid} is not a runner reading']
        for key in ('value','upper'):
            a_,b_=old.get(key),new.get(key)
            if (a_ is None)!=(b_ is None):return False,[f'record {nid} adds or drops an upper bound']
            if a_ is None:continue
            if not (isinstance(a_,(int,float)) and isinstance(b_,(int,float)) and a_>0 and b_>0 and max(a_,b_)/min(a_,b_)<=rule['max_ratio']):
                return False,[f"record {nid}: {key} moved from {a_} to {b_}, beyond {rule['max_ratio']}x; the owner reviews it"]
    if claimed!=set(retired):return False,['every retired figure must be replaced in the same package']
    return True,[f"same-page revision: {len(added)} figure{'s' if len(added)!=1 else ''} updated by their own publishers, each within {rule['max_ratio']}x"]


def eligible(package,p,registry,ledger=None):
    """(admitted, reasons). Every rule must hold; the reasons list explains the first failure or the admission.

    ledger, when supplied, is the current published site/data/ledger.json: a new observation
    whose metric already has three or more trailing non-superseded values is ineligible when
    its value falls outside 10x the trailing range either way (a unit or scale mistake reads as
    an outlier before it reads as a real jump). Omitting ledger skips this one check only."""
    a=p['auto_apply'];reasons=[]
    if not a['enabled']:return False,['auto-apply disabled by policy']
    rule=a['same_page_revisions']
    if package.get('author')==rule['author']:
        return same_page_revision(package,rule) if rule['enabled'] else (False,['same-page revisions are not enabled'])
    if package.get('author') not in a['authors']:return False,[f"author {package.get('author')!r} is not a policy-listed tool"]
    changes=package.get('changes',[])
    if not changes:return False,['0 changes exceeds the per-package ceiling']
    relabel_only=a['same_source_relabel'] and all(c.get('target')=='observation' and c.get('before') is not None
                                                    and same_source_relabel(c['before'],c.get('after',{})) for c in changes)
    if not relabel_only and len(changes)>a['max_changes_per_package']:return False,[f'{len(changes)} changes exceeds the per-package ceiling']
    for c in changes:
        if 'edition_supersedes' in (c.get('after') or {}) or 'edition_supersedes' in (c.get('before') or {}):
            return False,[f"record {c['id']} replaces a forecast edition; the owner reviews every edition change"]
        if c['target'] not in a['targets']:return False,[f"target {c['target']} always needs human review"]
        if c['target']=='metric':
            if c.get('before') is not None:return False,[f"metric {c['id']} already exists; redefining it needs human review"]
            if c['after'].get('measurement_type') not in a['metric_measurement_types']:return False,[f"metric {c['id']} has measurement type {c['after'].get('measurement_type')}, not a policy-listed per-site estimate"]
            if c['after'].get('allowed_statuses')!=['estimate']:return False,[f"metric {c['id']} must be estimate-only"]
            continue
        if c.get('before') is not None:
            if c['target']=='observation' and a['same_source_relabel'] and same_source_relabel(c['before'],c['after']):
                continue
            # The one permitted update: appending records to a project without touching anything else it says.
            b,af=c['before'],c['after']
            if c['target']!='project':return False,[f"{c['target']} {c['id']} already exists; replacing it needs human review"]
            if {k:v for k,v in b.items() if k!='observations'}!={k:v for k,v in af.items() if k!='observations'}:return False,[f"project {c['id']} changes more than its attached records; human review"]
            if af.get('observations',[])[:len(b.get('observations',[]))]!=b.get('observations',[]):return False,[f"project {c['id']} removes or reorders existing records; human review"]
            continue
        if c['target']=='project' and c['after'].get('stage') not in a['project_stages']:return False,[f"project {c['id']} stage {c['after'].get('stage')} needs human review"]
        if c['target']=='observation':
            if c['after'].get('status') not in {'estimate','observation','company-commitment','forecast','government-target'}:return False,[f"record {c['id']} has an unknown status"]
            if ledger is not None and isinstance(c['after'].get('value'),(int,float)):
                trailing=[o['value'] for o in ledger.get('observations',[]) if o.get('metric')==c['after'].get('metric') and not o.get('superseded_by') and isinstance(o.get('value'),(int,float))]
                if len(trailing)>=3:
                    low,high=min(trailing)/10,max(trailing)*10
                    if not low<=c['after']['value']<=high:return False,[f"record {c['id']}: magnitude outside trailing range; human review"]
    ranks=source_ranks(registry)
    for e in package.get('evidence',[]):
        host=urlparse(e['url']).hostname;rank=ranks.get(host)
        if rank is None or rank>a['max_source_rank']:return False,[f"evidence {e['id']} on {host} is not a registered rank ≤{a['max_source_rank']} source"]
    reasons.append(f"policy {p['reviewed_at'][:10]}: additions only, from {a['authors']}, evidence on rank ≤{a['max_source_rank']} hosts, preview must pass")
    return True,reasons


def auto_apply(root,rid,p=None):
    """Preview, record a policy approval and publish one admitted package. Never touches non-admitted ones."""
    import catalog_review as cr
    from editorial_review import append_event, locked
    from research import load, now
    p=p or policy(root);registry=load(root/'research/sources.json');ledger=load(root/'site/data/ledger.json')
    package=cr.package(root,rid)
    prior=cr.last_review(root,rid);label=p['auto_apply']['reviewer_label']
    resuming=bool(prior and prior['status']=='approved' and prior.get('reviewer')==label)   # approved by policy, publication interrupted
    require(resuming or not prior or prior['status'] in {'pending_review','deferred'},f'package {rid} already has a recorded decision ({prior["status"] if prior else "?"})')
    ok,reasons=eligible(package,p,registry,ledger)
    require(ok,'Not admitted by publication policy: '+'; '.join(reasons))
    cr.check_base(root,package);cr.check_evidence(root,package)
    # stage_validate_pending previewed this exact package against these exact files minutes ago.
    try:saved=cr.preview_validation(root,rid)
    except ValueError:saved=None
    same=bool(saved and saved.get('proposal_hash')==cr.digest(package) and saved.get('checkout')==cr.checkout_key(root))
    result=saved if same else cr.preview(root,rid)  # a failure on these exact files is not retried
    require(result['passed'] and result['proposal_hash']==cr.digest(package),'Preview validation failed; left for human review')
    if not resuming:
        with locked(root):
            append_event(root,dict(id=rid,kind='catalog_change',status='approved',reviewer=label,rationale='Auto-approved under research/publication-policy.json: '+'; '.join(reasons),at=now(),proposal_hash=cr.digest(package)))
    decision=cr.last_review(root,rid)
    return cr.publish_package(root,rid,package,decision,label)


def pending(root,label='publication-policy'):
    """Packages the policy may act on: undecided ones, plus its own approvals whose publication was interrupted."""
    import catalog_review as cr
    return [q for q in cr.inbox(root) if q['status'] in {'pending_review','deferred'} or (q['status']=='approved' and (q.get('last_review') or {}).get('reviewer')==label)]


def admissions(root,p,registry,ledger,only=None):
    """(rows, admitted_ids): every package the policy may act on, with its eligibility decision. No side effects."""
    rows=[];admitted=[]
    for q in pending(root):
        if only and q['id'] not in only:continue
        ok,reasons=eligible(q,p,registry,ledger)
        row=dict(q,admitted=ok,reason=reasons[0]);rows.append(row)
        if ok:admitted.append(row['id'])
    return rows,admitted


def apply_admitted(root,p=None,only=None,deadline=None):
    """Preview-checked automatic application of every pending package the policy admits.

    The one function both the CLI and the nightly orchestrator call. A package that fails its
    preview is left for the owner and the rest still go; past `deadline` no package is started, so
    a stage timeout never lands in the middle of a publish.
    """
    from research import load
    p=p or policy(root);registry=load(root/'research/sources.json');ledger=load(root/'site/data/ledger.json')
    rows,admitted=admissions(root,p,registry,ledger,only)
    outcomes={}
    import time
    for rid in admitted:
        # A package that starts must finish: past the deadline the rest wait for the next night.
        if deadline is not None and time.monotonic()>deadline:
            outcomes[rid]='deferred: not enough time left in this stage';continue
        try:
            r=auto_apply(root,rid,p);outcomes[rid]=r['status']
        except Exception as e:
            # One package that fails its preview is left for the owner; the others still go.
            outcomes[rid]='failed: '+type(e).__name__+': '+str(e)[:160]
    return {'pending':len(rows),'rows':rows,'admitted':admitted,'outcomes':outcomes}


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__.splitlines()[0]);ap.add_argument('--apply',action='store_true');ap.add_argument('--only',action='append',default=[],metavar='PACKAGE_ID')
    a=ap.parse_args(argv)
    from research import load
    p=policy(ROOT);registry=load(ROOT/'research/sources.json');ledger=load(ROOT/'site/data/ledger.json')
    rows,admitted=admissions(ROOT,p,registry,ledger,a.only)
    for q in rows:
        print(f"{'ADMIT ' if q['admitted'] else 'HUMAN '} {q['id']} · {q['title'][:70]} · {q['reason'][:110]}",flush=True)
    if not a.apply:
        print(f"\n{len(admitted)} of {len(rows)} pending packages admitted by policy. Run with --apply to publish them.",flush=True);return 0
    result=apply_admitted(ROOT,p,a.only)
    outcomes=result['outcomes']
    for rid,status in outcomes.items():print(f"applied {rid}: {status}",flush=True)
    print(json.dumps(outcomes,indent=1),flush=True)
    return 0 if all(v in {'deployed','deployment_pending','pushed'} for v in outcomes.values()) else 1


if __name__=='__main__':sys.exit(main())
