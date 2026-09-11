"""Operator-authorized Telegram session receipts through existing OpenClaw routing."""
import json
import re
import subprocess
from pathlib import Path
from datetime import datetime, timezone


def summary(folder):
    totals=dict(documents=0,accepted=0,quarantined=0,source_failures=0,discovery_proposals=0,
                discovery_errors=0,model_calls=0,pushed_batches=0,unpublished_batches=0,
                finding_pushes=0,monitoring_only_pushes=0,search_calls=0,search_errors=0,
                discovery_screened=0,model_documents=0,cooldown_skips=0,idle_checks=0,private_notes=0,
                unchanged_304=0,text_unchanged=0,already_reviewed=0,nothing_new_batches=0,
                # Deliverable 3 (2026-09-10): offered/attempted/met/skipped/backed-off, not a
                # single cumulative "queued" count -- see the 2026-09-10 measured problem
                # (20 offered every batch of a 103-batch session summed to a meaningless 2,060,
                # since nothing was ever met). refresh_expected() and the session back-off state
                # keep each of these small and honest to sum across a whole session's batches.
                stale_tasks_offered=0,stale_tasks_attempted=0,stale_tasks_met=0,
                stale_tasks_skipped_not_refresh_expected=0,stale_tasks_backed_off=0,empty_reasons={},
                # Deliverable 4 (2026-09-10): feed reach and idle-pass top-up, across the batches
                # a session actually ran -- so a quiet night can say whether nothing was
                # published or nothing was reachable, not just how many batches were quiet.
                feeds_polled=0,feed_entries_new=0,feed_entries_already_reviewed=0,
                idle_feeds_polled=0,idle_stale_tasks_run=0,idle_batches=0)
    hashes=set();complete_inventory=True
    for path in (folder/'batches').glob('*.json'):
        item=json.loads(path.read_text(encoding='utf-8'));run=item.get('monitoring',{});private=item.get('discovery') or {}
        totals['documents']+=run.get('documents_fetched',0)+private.get('documents_fetched',0)
        totals['accepted']+=run.get('accepted',0);totals['quarantined']+=run.get('quarantined',0)
        totals['source_failures']+=len(run.get('source_failures',[]))
        totals['discovery_proposals']+=private.get('proposals_queued',0)
        totals['discovery_errors']+=len(private.get('errors',[]))
        totals['model_calls']+=run.get('model_calls',0)+private.get('model_calls',0)
        totals['pushed_batches']+=item.get('publication')=='pushed'
        totals['unpublished_batches']+=item.get('publication')=='pending'
        totals['deferred_batches']=totals.get('deferred_batches',0)+(item.get('publication')=='deferred')
        if item.get('publication')=='pushed':
            totals['finding_pushes']+=run.get('accepted',0)>0
            totals['monitoring_only_pushes']+=not run.get('accepted',0)
        totals['search_calls']+=private.get('search_calls',0)
        totals['search_errors']+=sum(e.get('stage')=='search' for e in private.get('errors',[]))
        totals['discovery_screened']+=private.get('documents_screened',0)
        stats=item.get('collection',{})
        for key in ['model_documents','cooldown_skips','private_notes','unchanged_304','text_unchanged','already_reviewed','stale_tasks_offered',
                    'stale_tasks_skipped_not_refresh_expected','stale_tasks_backed_off',
                    'feeds_polled','feed_entries_new','feed_entries_already_reviewed','idle_feeds_polled','idle_stale_tasks_run']:
            totals[key]+=stats.get(key,0)
        for reason,count in stats.get('empty_reasons',{}).items():totals['empty_reasons'][reason]=totals['empty_reasons'].get(reason,0)+count
        stale=stats.get('stale_tasks',[])
        totals['stale_tasks_met']+=sum(t.get('outcome')=='met' for t in stale)
        totals['stale_tasks_attempted']+=sum(t.get('outcome')!='not_attempted' for t in stale)
        totals['cooldown_skips']+=private.get('cooldown_skips',0)
        totals['idle_checks']+=item.get('status')=='nothing_new'
        totals['nothing_new_batches']+=item.get('status')=='nothing_new'
        totals['idle_batches']+=bool(stats.get('idle_pass'))
        docs=stats.get('documents',[])
        if len(docs)!=run.get('documents_fetched',0):complete_inventory=False
        hashes.update(d['sha256'] for d in docs)
        discovery_docs=[a['document_sha256'] for a in private.get('attempts',[]) if a.get('document_sha256')]
        if len(discovery_docs)!=private.get('documents_fetched',0):complete_inventory=False
        hashes.update(discovery_docs)
    totals['unique_document_versions']=len(hashes) if complete_inventory else None
    totals['collection_detail_available']=complete_inventory
    return totals


def message(report,totals):
    if report.get('status')=='skipped':return 'Stack Ledger: scheduled research skipped.\nAnother research run is active and continues unchanged. Next automatic attempt: the next scheduled night.'
    if report.get('state')=='completed (nothing new)':
        # Deliverable 7: a short receipt for the common, unremarkable "caught up" ending --
        # the full receipt below still exists in the local session record for inspection.
        return '\n'.join([
            'Stack Ledger research: completed (nothing new).',
            f"Elapsed: {round(report.get('elapsed_seconds',0)/60)} min | Batches: {report.get('batches',0)}",
            f"{report.get('consecutive_nothing_new',3)} consecutive batches found no due, unchanged or already-reviewed sources; the session ended early rather than keep polling. Never counted as a failure.",
            'Review findings and details in your local Research Control panel.'
        ])
    top_empty=', '.join(f'{k} ×{v}' for k,v in sorted(totals.get('empty_reasons',{}).items(),key=lambda kv:-kv[1])[:3])
    return '\n'.join([
        'Stack Ledger research: '+report['state']+'.',
        ('Research stopped for maintenance; inspect the local batch log.' if report['state'] in {'blocked','failed','interrupted'} else 'Session receipt; elapsed time includes waits and publication checks.'),
        f"Elapsed: {round(report.get('elapsed_seconds',0)/60)} min | Batches: {report.get('batches',0)} ({report.get('failed_batches',0)} failed, {totals.get('nothing_new_batches',0)} nothing-new)",
        f"Fetches (includes repeats): {totals['documents']} | Unique document versions: {totals.get('unique_document_versions') if totals.get('unique_document_versions') is not None else 'not recorded'} | Model calls: {totals['model_calls']}",
        (f"Monitoring: {totals['model_documents']} model-reviewed, {totals.get('already_reviewed',0)} already reviewed (ledger), {totals.get('unchanged_304',0)} 304 unchanged, {totals.get('text_unchanged',0)} text-unchanged, {totals['cooldown_skips']} cooldown skips"
         if totals.get('collection_detail_available') else 'Older receipts lack unique-document/cache detail.'),
        f"Monitoring records accepted: {totals['accepted']} | Quarantined: {totals['quarantined']}"+(f" | Top empty reasons: {top_empty}" if top_empty else ''),
        (f"Stale-metric tasks: {totals.get('stale_tasks_offered',0)} offered, {totals.get('stale_tasks_attempted',0)} attempted, {totals.get('stale_tasks_met',0)} met"
         f" ({totals.get('stale_tasks_skipped_not_refresh_expected',0)} skipped as not refresh-expected, {totals.get('stale_tasks_backed_off',0)} backed off from an earlier unmet attempt)"
         if totals.get('stale_tasks_offered',0) or totals.get('stale_tasks_skipped_not_refresh_expected',0) or totals.get('stale_tasks_backed_off',0)
         else 'No stale-metric tasks offered this session.'),
        f"Feeds polled: {totals.get('feeds_polled',0)} ({totals.get('feed_entries_new',0)} new entries seen, {totals.get('feed_entries_already_reviewed',0)} already in the review ledger)",
        (f"Idle passes (batch found nothing due, so it force-repolled feeds and retried stale-metric sources before conceding): {report.get('idle_passes',0)}"
         + (f" -- {totals.get('idle_feeds_polled',0)} extra feed checks, {totals.get('idle_stale_tasks_run',0)} extra stale-task retries" if totals.get('idle_batches',0) else '')),
        f"New discovery proposals: {totals['discovery_proposals']} (private review inbox) | Private notes from sources without excerpt permission: {totals.get('private_notes',0)}",
        f"Source failures: {totals['source_failures']} | Discovery errors: {totals['discovery_errors']}",
        f"Discovery searches: {totals.get('search_calls',0)} ({totals.get('search_errors',0)} failed) | Documents screened: {totals.get('discovery_screened',0)}",
        (f"Publication: {totals['pushed_batches']} batches pushed; {totals['unpublished_batches']} pending/unconfirmed. Receipts-only batches deferred to the session commit: {totals.get('deferred_batches',0)}."
         if report.get('options',{}).get('publish') else 'Publication: private proposals only.'),
        (f"Pushes containing new accepted findings: {totals.get('finding_pushes',0)}; monitoring-only: {totals.get('monitoring_only_pushes',0)}." if report.get('options',{}).get('publish') else 'Private findings still require the existing review process.'),
        'Public session summary: '+report.get('session_summary_publication','not attempted')+'.',
        ('Collection needs attention: most discovery searches failed. More runtime alone is unlikely to help.' if totals.get('search_calls',0)>=3 and totals.get('search_errors',0)>totals['search_calls']/2 else 'Completion describes session duration, not research quality.'),
        'Review findings and details in your local Research Control panel.'
    ])


def deliver(root,text,receipt_path):
    config_path=root/'.local/telegram-notifications.json'
    if not config_path.exists():return {'status':'disabled'}
    config=json.loads(config_path.read_text(encoding='utf-8'))
    if config.get('enabled') is not True:return {'status':'disabled'}
    if receipt_path.exists():return {'status':'already_attempted'}
    from research_loop import atomic
    receipt={'status':'attempting','at':datetime.now(timezone.utc).isoformat()}
    atomic(receipt_path,receipt)
    try:
        if set(config)!={'enabled','account','target'} or not re.fullmatch(r'[0-9]{1,20}',config['target']) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}',config['account']):raise ValueError('Invalid local notification route')
        from schedule import cli
        args=cli()+['message','send','--channel','telegram','--account',config['account'],'--target',config['target'],'--message',text,'--json']
        # No model/source text, URLs or credentials are included in this receipt.
        subprocess.run(args,cwd=root,capture_output=True,text=True,encoding='utf-8',check=True,timeout=45)
        receipt['status']='sent'
    except Exception as error:
        receipt.update(status='failed',error_type=type(error).__name__)
    atomic(receipt_path,receipt)
    return receipt


def send_text(root,text,tag='note'):
    """Reuse the exact operator-authorized Telegram route for text outside a session receipt, e.g. the nightly digest.

    No source text, credentials or new routing: same config file, same deliver(), a fresh receipt path.
    """
    receipt_path=root/'.local/notifications'/(tag+'-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'.json')
    return deliver(root,text,receipt_path)


def notify_session(root,report,folder):
    try:
        totals=summary(folder)
        from research_progress import report as progress_report
        try:progress_report(root,folder)
        except Exception as error:totals['question_report_error']=type(error).__name__
        from research_loop import atomic
        atomic(folder/'summary.json',totals)
        from session_receipt import finalize
        publication=finalize(root,report,folder,totals)
        report['session_summary_publication']=publication['status']
        return deliver(root,message(report,totals),folder/'notification.json')
    except Exception as error:
        return {'status':'failed','error_type':type(error).__name__}
