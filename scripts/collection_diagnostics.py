"""Offline counts from retained batch receipts; never fetches or re-runs research."""
import json
import re
from collections import Counter


def category(item):
    reason = str(item.get('reason', ''))
    if 'robots' in reason.lower():
        return 'robots restriction or unavailable robots'
    if 'approved public host' in reason:
        return 'outside approved host'
    if 'pdf_requires_reviewed_parser' in reason:
        return 'PDF requires reviewed parser'
    if 'insufficient_static_text' in reason:
        return 'insufficient static text'
    status = item.get('http_status')
    match = re.search(r'HTTP(?: Error)?[ :]+([1-5][0-9]{2})', reason)
    if status is None and match:
        status = int(match.group(1))
    if isinstance(status, int) and 100 <= status <= 599:
        return f'HTTP {status}'
    if item.get('stage') == 'screen':
        return 'screening rejected or failed'
    # Keep arbitrary document text and URLs out of the diagnostic output.
    for kind in ('TimeoutError', 'ValueError', 'URLError', 'CollectionGap'):
        if item.get('type') == kind or kind in reason:
            return kind
    return 'other collection gap'


def summarize(folder):
    counts = {'source_failures': Counter(), 'discovery_errors': Counter()}
    files = sorted((folder / 'batches').glob('*.json'))
    unreadable = 0
    for path in files:
        try:
            batch = json.loads(path.read_text(encoding='utf-8'))
            sources = batch.get('monitoring', {}).get('source_failures', [])
            discovery = batch.get('discovery', {}).get('errors', [])
            if not all(isinstance(items, list) and all(isinstance(x, dict) for x in items)
                       for items in (sources, discovery)):
                raise ValueError('invalid receipt shape')
        except (OSError, ValueError, AttributeError):
            unreadable += 1
            continue
        for key, items in (('source_failures', sources), ('discovery_errors', discovery)):
            counts[key].update(category(item) for item in items)
    return {'status': 'partial' if unreadable or not files else 'ok',
            'batches_read': len(files) - unreadable, 'unreadable_batches': unreadable,
            **{key: {'total': sum(value.values()), 'by_category': dict(sorted(value.items()))}
               for key, value in counts.items()}}


def for_session(root, session_id):
    if not isinstance(session_id, str) or not re.fullmatch(r'[0-9a-f]{32}', session_id):
        return {'status': 'unavailable', 'reason': 'no valid research session receipt'}
    return {'session_id': session_id, **summarize(root / '.local/sessions' / session_id)}
