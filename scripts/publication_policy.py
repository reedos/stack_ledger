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
    require(set(a)=={'enabled','reviewer_label','authors','targets','new_entries_only','project_stages','max_source_rank','require_passing_preview','max_changes_per_package'},'Unexpected auto_apply fields')
    require(type(a['enabled']) is bool and a['new_entries_only'] is True and a['require_passing_preview'] is True,'Policy must keep new-entries-only and passing-preview rules')
    require(set(a['targets'])<={'project','source','note','observation'},'Policy may not auto-apply companies, products or metrics')
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


def eligible(package,p,registry):
    """(admitted, reasons). Every rule must hold; the reasons list explains the first failure or the admission."""
    a=p['auto_apply'];reasons=[]
    if not a['enabled']:return False,['auto-apply disabled by policy']
    if package.get('author') not in a['authors']:return False,[f"author {package.get('author')!r} is not a policy-listed tool"]
    changes=package.get('changes',[])
    if not changes or len(changes)>a['max_changes_per_package']:return False,[f'{len(changes)} changes exceeds the per-package ceiling']
    for c in changes:
        if c['target'] not in a['targets']:return False,[f"target {c['target']} always needs human review"]
        if c.get('before') is not None:return False,[f"{c['target']} {c['id']} already exists; replacing it needs human review"]
        if c['target']=='project' and c['after'].get('stage') not in a['project_stages']:return False,[f"project {c['id']} stage {c['after'].get('stage')} needs human review"]
        if c['target']=='observation' and c['after'].get('status') not in {'estimate','observation','company-commitment','forecast','government-target'}:return False,[f"record {c['id']} has an unknown status"]
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
    p=p or policy(root);registry=load(root/'research/sources.json')
    package=cr.package(root,rid)
    prior=cr.last_review(root,rid)
    require(not prior or prior['status'] in {'pending_review','deferred'},f'package {rid} already has a recorded decision ({prior["status"] if prior else "?"})')
    ok,reasons=eligible(package,p,registry)
    require(ok,'Not admitted by publication policy: '+'; '.join(reasons))
    cr.check_base(root,package);cr.check_evidence(root,package)
    result=cr.preview(root,rid)
    require(result['passed'] and result['proposal_hash']==cr.digest(package),'Preview validation failed; left for human review')
    label=p['auto_apply']['reviewer_label']
    with locked(root):
        append_event(root,dict(id=rid,kind='catalog_change',status='approved',reviewer=label,rationale='Auto-approved under research/publication-policy.json: '+'; '.join(reasons),at=now(),proposal_hash=cr.digest(package)))
    decision=cr.last_review(root,rid)
    return cr.publish_package(root,rid,package,decision,label)


def pending(root):
    import catalog_review as cr
    return [q for q in cr.inbox(root) if q['status'] in {'pending_review','deferred'}]


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__.splitlines()[0]);ap.add_argument('--apply',action='store_true');ap.add_argument('--only',action='append',default=[],metavar='PACKAGE_ID')
    a=ap.parse_args(argv)
    from research import load
    p=policy(ROOT);registry=load(ROOT/'research/sources.json')
    rows=[q for q in pending(ROOT) if not a.only or q['id'] in a.only]
    admitted=[]
    for q in rows:
        ok,reasons=eligible(q,p,registry)
        print(f"{'ADMIT ' if ok else 'HUMAN '} {q['id']} · {q['title'][:70]} · {reasons[0][:110]}",flush=True)
        if ok:admitted.append(q['id'])
    if not a.apply:
        print(f"\n{len(admitted)} of {len(rows)} pending packages admitted by policy. Run with --apply to publish them.",flush=True);return 0
    outcomes={}
    for rid in admitted:
        try:
            r=auto_apply(ROOT,rid,p);outcomes[rid]=r['status'];print(f"applied {rid}: {r['status']} commit {r.get('commit','')[:10]}",flush=True)
        except Exception as e:
            outcomes[rid]='failed: '+type(e).__name__+': '+str(e)[:160];print(f"stopped at {rid}: {outcomes[rid]}",flush=True);break
    print(json.dumps(outcomes,indent=1),flush=True)
    return 0 if all(v in {'deployed','deployment_pending','pushed'} for v in outcomes.values()) else 1


if __name__=='__main__':sys.exit(main())
