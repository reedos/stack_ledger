"""Operator-authorized Telegram session receipts through existing OpenClaw routing."""
import json
import re
import subprocess
from pathlib import Path
from datetime import datetime, timezone


def summary(folder):
    totals=dict(documents=0,accepted=0,quarantined=0,source_failures=0,discovery_proposals=0,
                discovery_errors=0,model_calls=0,pushed_batches=0,unpublished_batches=0)
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
    return totals


def message(report,totals):
    if report.get('status')=='skipped':return 'Stack Ledger: scheduled research skipped.\nAnother research run is active and continues unchanged. Next automatic attempt: the next scheduled night.'
    return '\n'.join([
        'Stack Ledger research: '+report['state']+'.',
        ('Research stopped for maintenance; inspect the local batch log.' if report['state'] in {'blocked','failed','interrupted'} else 'Session receipt; elapsed time includes waits and publication checks.'),
        f"Elapsed: {round(report.get('elapsed_seconds',0)/60)} min | Batches: {report.get('batches',0)} ({report.get('failed_batches',0)} failed)",
        f"Documents fetched: {totals['documents']} | Model calls: {totals['model_calls']}",
        f"Monitoring records accepted: {totals['accepted']} | Quarantined: {totals['quarantined']}",
        f"New discovery proposals: {totals['discovery_proposals']} (private review inbox)",
        f"Source failures: {totals['source_failures']} | Discovery errors: {totals['discovery_errors']}",
        (f"Publication: {totals['pushed_batches']} batches pushed; {totals['unpublished_batches']} pending/unconfirmed."
         if report.get('options',{}).get('publish') else 'Publication: private proposals only.'),
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
        from research_loop import atomic
        atomic(folder/'summary.json',totals)
        return deliver(root,message(report,totals),folder/'notification.json')
    except Exception as error:
        return {'status':'failed','error_type':type(error).__name__}
