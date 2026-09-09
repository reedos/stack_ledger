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
                discovery_screened=0,cache_hits=0,model_documents=0,cooldown_skips=0,idle_checks=0)
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
        if item.get('publication')=='pushed':
            totals['finding_pushes']+=run.get('accepted',0)>0
            totals['monitoring_only_pushes']+=not run.get('accepted',0)
        totals['search_calls']+=private.get('search_calls',0)
        totals['search_errors']+=sum(e.get('stage')=='search' for e in private.get('errors',[]))
        totals['discovery_screened']+=private.get('documents_screened',0)
        stats=item.get('collection',{})
        for key in ['cache_hits','model_documents','cooldown_skips']:totals[key]+=stats.get(key,0)
        totals['cooldown_skips']+=private.get('cooldown_skips',0)
        totals['idle_checks']+=item.get('status')=='nothing_due'
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
    return '\n'.join([
        'Stack Ledger research: '+report['state']+'.',
        ('Research stopped for maintenance; inspect the local batch log.' if report['state'] in {'blocked','failed','interrupted'} else 'Session receipt; elapsed time includes waits and publication checks.'),
        f"Elapsed: {round(report.get('elapsed_seconds',0)/60)} min | Batches: {report.get('batches',0)} ({report.get('failed_batches',0)} failed)",
        f"Fetches (includes repeats): {totals['documents']} | Unique document versions: {totals.get('unique_document_versions') if totals.get('unique_document_versions') is not None else 'not recorded'} | Model calls: {totals['model_calls']}",
        (f"Monitoring model documents: {totals['model_documents']} | Cached reviews reused: {totals['cache_hits']} | Cooldown skips: {totals['cooldown_skips']}" if totals.get('collection_detail_available') else 'Older receipts lack unique-document/cache detail.'),
        f"Monitoring records accepted: {totals['accepted']} | Quarantined: {totals['quarantined']}",
        f"New discovery proposals: {totals['discovery_proposals']} (private review inbox)",
        f"Source failures: {totals['source_failures']} | Discovery errors: {totals['discovery_errors']}",
        f"Discovery searches: {totals.get('search_calls',0)} ({totals.get('search_errors',0)} failed) | Documents screened: {totals.get('discovery_screened',0)}",
        (f"Publication: {totals['pushed_batches']} batches pushed; {totals['unpublished_batches']} pending/unconfirmed."
         if report.get('options',{}).get('publish') else 'Publication: private proposals only.'),
        (f"Pushes containing new accepted findings: {totals.get('finding_pushes',0)}; monitoring-only: {totals.get('monitoring_only_pushes',0)}." if report.get('options',{}).get('publish') else 'Private findings still require the existing review process.'),
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


def notify_session(root,report,folder):
    try:
        totals=summary(folder)
        from research_progress import report as progress_report
        try:progress_report(root,folder)
        except Exception as error:totals['question_report_error']=type(error).__name__
        from research_loop import atomic
        atomic(folder/'summary.json',totals)
        return deliver(root,message(report,totals),folder/'notification.json')
    except Exception as error:
        return {'status':'failed','error_type':type(error).__name__}
