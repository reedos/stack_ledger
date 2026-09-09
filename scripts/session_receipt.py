"""Public, aggregate-only session receipts derived from private controller records."""
import json
from datetime import datetime, timezone
from pathlib import Path
from validate import require, timestamp

COUNTS=('batches','failed_batches','receipts_recorded','elapsed_seconds','documents_fetched','model_calls','accepted','quarantined','source_failures','discovery_errors')
STATES={'completed','cycle limit reached','stopped','interrupted','blocked','failed'}


def validate_receipt(record):
    require(isinstance(record,dict) and set(record)==set(COUNTS)|{'started_at','reported_at','state'},'Unexpected session receipt fields')
    require(timestamp(record['reported_at'])>=timestamp(record['started_at']),'Session report precedes start')
    require(record['state'] in STATES,'Session receipt must describe a finished attempt')
    for k in COUNTS:require(type(record[k]) is int and record[k]>=0,'Invalid session counter')
    require(record['failed_batches']<=record['batches'],'Too many failed batches')
    require(record['receipts_recorded']<=record['batches'],'Too many batch receipts')


def public_receipt(report,totals,folder,reported_at=None):
    """Explicit fields only: never serialize options, paths, source text or routing."""
    require(report.get('options',{}).get('publish') is True,'Private session cannot publish totals')
    require(report['options'].get('direction')!='discovery','Discovery-only sessions stay private')
    record={k:report[k] for k in ['started_at','state','elapsed_seconds','batches','failed_batches']}
    record.update(reported_at=reported_at or datetime.now(timezone.utc).isoformat(),
                  receipts_recorded=len(list((folder/'batches').glob('*.json'))),
                  documents_fetched=totals['documents'])
    record.update({k:totals[k] for k in ['model_calls','accepted','quarantined','source_failures','discovery_errors']})
    validate_receipt(record)
    return record


def verify_retained_receipt(root,record):
    """Used at publication and retry; a model cannot supply the session totals."""
    from research_notify import summary
    validate_receipt(record)
    for path in (root/'.local/sessions').glob('*/public-summary.json'):
        saved=json.loads(path.read_text(encoding='utf-8'))
        if saved!=record:continue
        report=json.loads((path.parent/'status.json').read_text(encoding='utf-8'))
        require(public_receipt(report,summary(path.parent),path.parent,record['reported_at'])==record,'Session totals differ from retained receipts')
        return
    raise ValueError('No matching retained session summary')


def finalize(root,report,folder,totals):
    """Finalize a publishing session through the existing lock/build/publisher."""
    if not report.get('options',{}).get('publish') or report['options'].get('direction')=='discovery':
        return {'status':'private'}
    if not report.get('batches') or not (folder/'batches').exists():return {'status':'no_receipts'}
    from research_loop import atomic
    prior=folder/'summary-publication.json'
    if prior.exists() and json.loads(prior.read_text(encoding='utf-8')).get('status')=='pushed':
        return {'status':'already_pushed'}
    result={'status':'pending'}
    try:
        import research
        require(root.resolve()==research.ROOT.resolve(),'Session repository mismatch')
        saved=folder/'public-summary.json'
        reported_at=json.loads(saved.read_text(encoding='utf-8'))['reported_at'] if saved.exists() else None
        record=public_receipt(report,totals,folder,reported_at)
        atomic(folder/'public-summary.json',record)
        config=research.load(root/'research/runtime.json')
        with research.lock():
            research.preflight(config)
            data=research.load(root/'site/data/ledger.json')
            previous=data['runtime'].get('latest_session')
            if previous==record:
                atomic(folder/'summary-publication.json',{'status':'pushed'})
                return {'status':'already_pushed'}
            if previous and timestamp(previous['started_at'])>timestamp(record['started_at']):
                return {'status':'newer_summary_present'}
            data['runtime']['latest_session']=record
            research.validate(data)
            research.save(root/'site/data/ledger.json',data)
            research.build()
            require(research.load(root/'docs/data/ledger.json')==data,'Build data mismatch')
            research.publish(config)
        result={'status':'pushed'}
    except Exception as error:
        result={'status':'failed','error_type':type(error).__name__}
    atomic(folder/'summary-publication.json',result)
    return result
