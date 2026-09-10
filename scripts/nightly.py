"""One nightly entry point: stale-lock recovery, dataset imports, the model research session,
automatic publication, a health/stale-figure report, preview pruning and a digest.

The OpenClaw job calls this script alone at 01:30 Pacific. Each stage gets its own timeout and
writes a receipt to `.local/nightly/<date>/<stage>.json`; a failed stage is recorded and skipped,
never fatal to the rest of the night. Pre-stages (locks, importers) get at most 25 minutes so the
model research session still starts by 02:00; the session itself keeps its own 2-7 AM Pacific
window; post-stages (policy, health, prune, digest) run after it, inside the 6-hour cron ceiling.

    python scripts/nightly.py               # run every stage
    python scripts/nightly.py --dry-run      # print the plan; nothing runs, nothing is written
    python scripts/nightly.py --only health  # run one stage by hand
"""
import argparse
import ctypes
import json
import os
import queue
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from atomic_json import save
from validate import validate_importers

ROOT = Path(__file__).resolve().parents[1]
STAGES = ['locks', 'importers', 'research', 'policy', 'health', 'prune', 'digest']
LOCKS = ('.local/research.lock', '.local/research-session.lock', '.local/review-candidates/editorial.lock')
IMPORT_PATH_PREFIXES = ('research/', 'site/', 'docs/')
PRE_STAGE_BUDGET_SECONDS = 25*60      # pre-stages must clear by 02:00 so the session starts on time
TOTAL_CEILING_SECONDS = 6*3600        # matches the cron job's own timeout (schedule.py)
POST_STAGE_RESERVE_SECONDS = 10*60    # left for policy/health/prune/digest after the session returns
STAGE_TIMEOUTS = {'locks': 60, 'policy': 600, 'health': 120, 'prune': 120, 'digest': 120}


# ---------------------------------------------------------------- locks

def pid_alive(pid):
    if not isinstance(pid, int) or pid <= 0: return False
    if os.name == 'nt':
        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle: return False
        try:
            code = ctypes.c_ulong()
            if not ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(code)): return False
            return code.value == 259  # STILL_ACTIVE
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # exists, owned by someone else
    except OSError:
        return False
    return True


def lock_status(path):
    """Read a lock, recover it if its process is dead or it is stale with no pid, and report what happened."""
    if not path.exists():
        return {'path': path.name, 'present': False, 'blocking': False, 'action': 'absent'}
    try:
        raw = path.read_text(encoding='utf-8')
    except OSError as e:
        return {'path': path.name, 'present': True, 'blocking': True, 'action': 'unreadable', 'error': type(e).__name__}
    pid = None
    if raw.strip():
        try:
            data = json.loads(raw)
            if isinstance(data, dict) and isinstance(data.get('pid'), int): pid = data['pid']
        except ValueError:
            pid = None
    if pid is not None:
        if pid_alive(pid):
            return {'path': path.name, 'present': True, 'blocking': True, 'action': 'left_alive', 'pid': pid}
        try: path.unlink()
        except OSError: pass
        return {'path': path.name, 'present': True, 'blocking': False, 'action': 'removed_dead_pid', 'pid': pid}
    try: age_hours = (time.time()-path.stat().st_mtime)/3600
    except OSError: age_hours = 0
    if age_hours > 12:
        try: path.unlink()
        except OSError: pass
        return {'path': path.name, 'present': True, 'blocking': False, 'action': 'removed_stale_no_pid', 'age_hours': round(age_hours, 1)}
    return {'path': path.name, 'present': True, 'blocking': True, 'action': 'left_no_pid_recent', 'age_hours': round(age_hours, 1)}


def stage_locks(root):
    results = [lock_status(root/rel) for rel in LOCKS]
    return {'status': 'ok', 'locks': results,
            'research_blocked': any(r['blocking'] for r in results if 'research' in r['path']),
            'editorial_blocked': any(r['blocking'] for r in results if 'editorial' in r['path']),
            'stop_research_present': (root/'.local/stop-research-loop').exists()}


# ------------------------------------------------------------ importers

def due_importers(config, today):
    return [imp for imp in config['importers'] if imp['cadence'] == 'daily' or (imp['cadence'] == 'weekly' and imp.get('weekday') == today.weekday())]


def changed_paths(root):
    result = subprocess.run(['git', 'status', '--porcelain'], cwd=root, capture_output=True, text=True, check=True, timeout=30)
    out = []
    for line in result.stdout.splitlines():
        path = line[3:].strip().strip('"')
        if path.startswith(IMPORT_PATH_PREFIXES): out.append(path)
    return out


def restore_importer_paths(root):
    """Discard an importer's changes under research/, site/ and docs/ only; scripts/tests/tools are never touched."""
    subprocess.run(['git', 'checkout', '--', 'research', 'site', 'docs'], cwd=root, capture_output=True, text=True, timeout=60)
    subprocess.run(['git', 'clean', '-fd', 'research', 'site', 'docs'], cwd=root, capture_output=True, text=True, timeout=60)


def branch_name(root):
    try: return read_json(root/'research/runtime.json').get('branch', 'main')
    except Exception: return 'main'


def push_origin(root):
    """Push local commits so the research preflight (HEAD must equal origin) and GitHub Pages see them; one retry."""
    branch = branch_name(root); error = ''
    for attempt in (1, 2):
        result = subprocess.run(['git', 'push', 'origin', f'HEAD:{branch}'], cwd=root, capture_output=True, text=True, timeout=180)
        if result.returncode == 0: return {'pushed': True, 'attempts': attempt, 'branch': branch}
        error = (result.stderr or result.stdout)[-400:]
        if attempt == 1: time.sleep(5)
    return {'pushed': False, 'attempts': 2, 'branch': branch, 'error': error}


def commits_ahead(root):
    """Local commits not on origin/<branch>, after a fetch; None when the remote cannot be reached."""
    branch = branch_name(root)
    fetch = subprocess.run(['git', 'fetch', 'origin', branch], cwd=root, capture_output=True, text=True, timeout=120)
    if fetch.returncode != 0: return None
    count = subprocess.run(['git', 'rev-list', '--count', f'origin/{branch}..HEAD'], cwd=root, capture_output=True, text=True, timeout=30)
    return int(count.stdout.strip()) if count.returncode == 0 and count.stdout.strip().isdigit() else None


def run_importer(root, imp):
    command = [sys.executable, str(root/imp['command'][0]), *imp['command'][1:]]
    try:
        result = subprocess.run(command, cwd=root, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=imp['timeout_seconds'], env=dict(os.environ, PYTHONIOENCODING='utf-8'))
    except subprocess.TimeoutExpired:
        restore_importer_paths(root)
        return {'id': imp['id'], 'status': 'failed', 'error': 'timeout', 'timeout_seconds': imp['timeout_seconds']}
    outcome = {'id': imp['id'], 'returncode': result.returncode, 'stdout_tail': result.stdout[-3000:], 'stderr_tail': result.stderr[-2000:]}
    if result.returncode != 0:
        restore_importer_paths(root)
        outcome['status'] = 'failed'
        return outcome
    try:
        changed = changed_paths(root)
    except subprocess.CalledProcessError as e:
        outcome['status'] = 'failed'; outcome['error'] = 'git status failed: '+str(e)[:200]
        return outcome
    if not changed:
        outcome['status'] = 'ok'; outcome['committed'] = False
        return outcome
    try:
        subprocess.run(['git', 'add', '--', *changed], cwd=root, check=True, capture_output=True, text=True, timeout=60)
        summary = next((line for line in reversed(outcome['stdout_tail'].strip().splitlines()) if line.strip()), 'update')[:200]
        subprocess.run(['git', 'commit', '-m', f"nightly(import:{imp['id']}): {summary}"], cwd=root, check=True, capture_output=True, text=True, timeout=60)
        head = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=root, check=True, capture_output=True, text=True, timeout=30).stdout.strip()
        outcome.update(status='ok', committed=True, commit=head, changed_paths=changed)
    except subprocess.CalledProcessError as e:
        restore_importer_paths(root)
        outcome['status'] = 'failed'; outcome['error'] = 'git commit failed: '+str(e.stderr or e)[:300]
    return outcome


def stage_importers(root, soft_budget_seconds):
    config = validate_importers(root)
    due = due_importers(config, datetime.now(timezone.utc).date())
    results = []; start_deadline = time.monotonic()+max(0, soft_budget_seconds)
    for imp in due:
        if time.monotonic() >= start_deadline:
            results.append({'id': imp['id'], 'status': 'skipped', 'reason': 'pre-stage time budget exhausted before this importer started'})
            continue
        results.append(run_importer(root, imp))
    statuses = {r['status'] for r in results}
    status = 'ok' if not due or statuses == {'ok'} else ('skipped' if statuses <= {'skipped'} else ('partial' if 'ok' in statuses else 'failed'))
    push = push_origin(root) if any(r.get('committed') for r in results) else None
    if push and not push['pushed'] and status == 'ok': status = 'partial'   # commits are local until the next push succeeds
    return {'status': status, 'due': [i['id'] for i in due], 'results': results, 'push': push}


def research_ignore_gpu_busy(root):
    try:
        return bool(validate_importers(root).get('research_ignore_gpu_busy', True))
    except Exception:
        return True


# -------------------------------------------------------------- research

def stage_research(root, budget_seconds):
    if (root/'.local/stop-research-loop').exists():
        return {'status': 'skipped', 'reason': '.local/stop-research-loop present'}
    for rel in ('.local/research.lock', '.local/research-session.lock'):
        status = lock_status(root/rel)
        if status['blocking']:
            return {'status': 'skipped', 'reason': f"{status['path']} held by live pid {status.get('pid')}"}
    command = [sys.executable, str(root/'scripts/research_loop.py'), '--start', '--publish', '--minutes', '300', '--overnight', '--keep-awake']
    if research_ignore_gpu_busy(root): command.append('--ignore-gpu-busy')
    timeout = max(60, budget_seconds)
    try:
        result = subprocess.run(command, cwd=root, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=timeout, env=dict(os.environ, PYTHONIOENCODING='utf-8'))
    except subprocess.TimeoutExpired as e:
        return {'status': 'failed', 'error': 'timeout', 'timeout_seconds': timeout, 'stdout_tail': (e.stdout or '')[-3000:]}
    return {'status': 'ok' if result.returncode == 0 else 'failed', 'returncode': result.returncode,
            'stdout_tail': result.stdout[-4000:], 'stderr_tail': result.stderr[-2000:]}


# ---------------------------------------------------------------- policy

def stage_validate_pending(root):
    """Refresh every pending package's preview so its card is ready -- validated, not homepage-bound
    -- when the owner looks in the morning. Skips a package whose validation already passes for its
    current hash; a package that fails here still shows the failure on its card, it is not hidden."""
    import catalog_review as cr
    validated = []; failed = []
    for pkg in cr.inbox(root):
        if pkg['status'] != 'pending_review': continue
        v = pkg.get('validation')
        if v and v.get('passed') and v.get('proposal_hash') == pkg['proposal_hash']: continue
        try:
            result = cr.preview(root, pkg['id'])
            validated.append({'id': pkg['id'], 'passed': result['passed']})
        except Exception as e:
            failed.append({'id': pkg['id'], 'error': f'{type(e).__name__}: {str(e)[:200]}'})
    return validated, failed


def stage_policy(root):
    import publication_policy as pp
    p = pp.policy(root)
    validated, validation_failures = stage_validate_pending(root)
    if not p['auto_apply']['enabled']:
        return {'status': 'partial' if validation_failures else 'skipped', 'reason': 'auto-apply disabled by policy (auto_apply.enabled=false)',
                'validated': validated, 'validation_failures': validation_failures}
    status = lock_status(root/'.local/review-candidates/editorial.lock')
    if status['blocking']:
        return {'status': 'partial' if validation_failures else 'skipped', 'reason': f"editorial.lock held by live pid {status.get('pid')}",
                'validated': validated, 'validation_failures': validation_failures}
    result = pp.apply_admitted(root, p)
    import catalog_review as cr
    deployments = cr.verify_pending_deployments(root)
    failed = [rid for rid, outcome in result['outcomes'].items() if str(outcome).startswith('failed')]
    return {'status': 'partial' if failed or validation_failures else 'ok', 'pending': result['pending'], 'admitted': result['admitted'],
            'outcomes': result['outcomes'], 'deployment_verification': deployments,
            'validated': validated, 'validation_failures': validation_failures}


# ---------------------------------------------------------------- health

CADENCE_DAYS = {'quarter': 120, 'snapshot': 60, 'month': 45, None: 400}


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def collection_summary(root):
    from collection_health import Health
    path = root/'.local/collection-health.json'
    h = Health(path)
    by_kind = {}
    for key, rec in h.records.items():
        kind = key.split(':', 1)[0]
        bucket = by_kind.setdefault(kind, {'total': 0, 'available': 0, 'unavailable': 0})
        bucket['total'] += 1
        bucket['available' if rec.get('status') == 'available' else 'unavailable'] += 1
    return {'present': path.exists(), 'total_records': len(h.records), 'by_kind': by_kind}


def stale_figures(root):
    data = read_json(root/'site/data/ledger.json')
    metrics = {m['id']: m for m in data['metrics']}
    latest = {}
    for o in data['observations']:
        if o.get('superseded_by'): continue
        current = latest.get(o['metric'])
        if current is None or o['retrieved_at'] > current['retrieved_at']: latest[o['metric']] = o
    now = datetime.now(timezone.utc)
    overdue = []
    for mid, o in latest.items():
        m = metrics.get(mid)
        if not m: continue
        days = CADENCE_DAYS.get(m.get('period_basis'), CADENCE_DAYS[None])
        try: retrieved = datetime.fromisoformat(o['retrieved_at'].replace('Z', '+00:00'))
        except ValueError: continue
        age_days = (now-retrieved).total_seconds()/86400
        if age_days > days:
            overdue.append({'metric': mid, 'source': o['source'], 'age_days': round(age_days, 1),
                             'threshold_days': days, 'period_basis': m.get('period_basis') or 'yearly', 'latest_period': o['period']})
    overdue.sort(key=lambda r: -r['age_days'])
    return {'overdue_count': len(overdue), 'most_overdue': overdue[:20]}


def disk_usage_top(root, n=8):
    base = root/'.local'
    if not base.exists(): return []
    sizes = []
    for child in base.iterdir():
        total = 0
        try:
            if child.is_dir():
                for f in child.rglob('*'):
                    if f.is_file():
                        try: total += f.stat().st_size
                        except OSError: pass
            elif child.is_file():
                total = child.stat().st_size
        except OSError:
            pass
        sizes.append({'path': child.name, 'bytes': total})
    sizes.sort(key=lambda r: -r['bytes'])
    return sizes[:n]


def repo_size(root):
    try:
        out = subprocess.run(['git', 'count-objects', '-vH'], cwd=root, capture_output=True, text=True, timeout=30, check=True).stdout
        return {k.strip(): v.strip() for k, v in (line.split(':', 1) for line in out.splitlines() if ':' in line)}
    except Exception as e:
        return {'error': type(e).__name__}


def questions_pending(root):
    from editorial_review import queue as review_queue, events
    latest = {}
    for e in events(root):
        if e.get('kind') == 'research_question': latest[e['id']] = e['status']
    n = 0
    for path in review_queue(root).glob('question-*.json'):
        try: item = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError): continue
        if item.get('kind') == 'research_question' and latest.get(item.get('id'), 'pending_review') == 'pending_review': n += 1
    return n


def pending_decisions(root):
    from findings_review import inbox as findings_inbox
    from visual_review import inbox as visual_inbox
    f = findings_inbox(root); v = visual_inbox(root)
    return {'catalog_packages_pending': sum(1 for p in f['catalog_packages'] if p['status'] == 'pending_review'),
            'discovery_findings_pending': sum(1 for r in f['findings'] if r['status'] == 'pending_review'),
            'visual_recommendations_pending': sum(1 for p in v['proposals'] if p['status'] == 'pending_review'),
            'questions_pending': questions_pending(root)}


def load_receipt(root, date, name):
    path = root/'.local/nightly'/date/(name+'.json')
    if not path.exists(): return None
    try: return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError): return None


def stage_health(root, date):
    result = {'status': 'ok'}
    for key, fn in [('collection_health', collection_summary), ('stale_figures', stale_figures),
                     ('disk_usage_top', disk_usage_top), ('repo_size', repo_size), ('pending_decisions', pending_decisions)]:
        try: result[key] = fn(root)
        except Exception as e:
            result[key] = {'error': f'{type(e).__name__}: {str(e)[:200]}'}; result['status'] = 'partial'
    history = {name: load_receipt(root, date, name) for name in ('locks', 'importers', 'research', 'policy')}
    result['locks_recovered'] = [l for l in (history.get('locks') or {}).get('locks', []) if str(l.get('action', '')).startswith('removed')]
    result['stage_outcomes'] = {k: (v.get('status') if v else 'no receipt') for k, v in history.items()}
    return result


# ----------------------------------------------------------------- prune

def stage_prune(root, dry_run=False):
    import catalog_review as cr
    base = root/'.local/catalog-previews'
    if not base.exists(): return {'status': 'ok', 'deleted': [], 'bytes_freed': 0, 'count': 0, 'dry_run': dry_run}
    now = datetime.now(timezone.utc); deleted = []; freed = 0
    for child in sorted(base.iterdir()):
        if not child.is_dir() or not cr.RID.fullmatch(child.name): continue
        review = cr.last_review(root, child.name)
        if not review or review['status'] not in {'applied', 'rejected'}: continue
        try: at = datetime.fromisoformat(review['at'].replace('Z', '+00:00'))
        except (KeyError, ValueError): continue
        age_days = (now-at).total_seconds()/86400
        if age_days < 7: continue
        size = sum(f.stat().st_size for f in child.rglob('*') if f.is_file())
        if not dry_run: shutil.rmtree(child)
        deleted.append({'id': child.name, 'bytes': size, 'age_days': round(age_days, 1)})
        freed += size
    return {'status': 'ok', 'deleted': deleted, 'bytes_freed': freed, 'count': len(deleted), 'dry_run': dry_run}


# ---------------------------------------------------------------- digest

def site_changes(root, date):
    try:
        out = subprocess.run(['git', 'log', '--since', date+' 00:00:00', '--until', date+' 23:59:59', '--oneline'],
                              cwd=root, capture_output=True, text=True, timeout=30, check=True).stdout
        return [line for line in out.splitlines() if line.strip()]
    except Exception:
        return []


def render_digest_markdown(body):
    lines = [f"# Nightly digest - {body['date']}", '', '## Applied automatically']
    lines += [f"- {row['kind']}: " + ' '.join(f'{k}={v}' for k, v in row.items() if k != 'kind') for row in body['applied']] or ['- Nothing applied automatically tonight.']
    lines += ['', '## Needs a decision']
    lines += [f"- {k.replace('_', ' ')}: {v}" for k, v in body['needs_decision'].items()] or ['- Nothing pending.']
    lines += ['', '## Health', '```json', json.dumps(body['health'], indent=2), '```', '', '## Site changes']
    lines += ['- '+c for c in body['site_changes']] or ['- No commits recorded tonight.']
    lines += ['', '## Stage outcomes']
    lines += [f"- {k}: {v}" for k, v in body['stage_receipts'].items()]
    return '\n'.join(lines)+'\n'


def stage_digest(root, date):
    receipts = {name: load_receipt(root, date, name) for name in ('locks', 'importers', 'research', 'policy', 'health', 'prune')}
    applied = []
    for r in (receipts.get('importers') or {}).get('results', []):
        if r.get('committed'): applied.append({'kind': 'import', 'id': r['id'], 'commit': (r.get('commit') or '')[:10]})
    policy_receipt = receipts.get('policy') or {}
    for rid, outcome in (policy_receipt.get('outcomes') or {}).items():
        applied.append({'kind': 'catalog_change', 'id': rid, 'outcome': outcome})
    for rid in (policy_receipt.get('deployment_verification') or {}).get('applied', []):
        applied.append({'kind': 'deployment_confirmed', 'id': rid})
    health = receipts.get('health') or {}
    body = {'date': date, 'applied': applied, 'needs_decision': health.get('pending_decisions') or {},
            'health': {k: health.get(k) for k in ('stale_figures', 'disk_usage_top', 'repo_size', 'collection_health')},
            'site_changes': site_changes(root, date),
            'stage_receipts': {k: (v.get('status') if v else 'no receipt') for k, v in receipts.items()}}
    save(root/'.local/digest'/(date+'.json'), body)
    markdown = render_digest_markdown(body)
    digest_dir = root/'.local/digest'; digest_dir.mkdir(parents=True, exist_ok=True)
    (digest_dir/(date+'.md')).write_text(markdown, encoding='utf-8')
    ahead = commits_ahead(root); push = push_origin(root) if ahead else None
    body['unpushed_commits'] = ahead; body['final_push'] = push
    save(root/'.local/digest'/(date+'.json'), body)
    from research_notify import send_text
    notice = send_text(root, markdown[:3500], tag='nightly-digest')
    return {'status': 'ok' if not push or push['pushed'] else 'partial', 'applied_count': len(applied), 'needs_decision': body['needs_decision'],
            'notification': notice.get('status'), 'unpushed_commits': ahead, 'final_push': push}


# ------------------------------------------------------------- the runner

def run_with_timeout(fn, timeout_seconds):
    """Run fn() on a daemon thread so a stuck stage cannot hang nightly.py past its own budget."""
    box = queue.Queue(maxsize=1)
    def worker():
        try: box.put(('ok', fn()))
        except Exception as e: box.put(('error', e))
    threading.Thread(target=worker, daemon=True).start()
    try:
        kind, value = box.get(timeout=max(1, timeout_seconds))
    except queue.Empty:
        return {'status': 'timeout', 'error': f'Stage exceeded its {timeout_seconds}s budget'}
    if kind == 'error':
        return {'status': 'error', 'error': type(value).__name__, 'message': str(value)[:600]}
    return {'status': 'ok', 'value': value}


def run_stage(root, date, name, timeout_seconds, fn):
    started = datetime.now(timezone.utc).isoformat(); t0 = time.monotonic()
    outcome = run_with_timeout(fn, timeout_seconds)
    elapsed = round(time.monotonic()-t0, 3); finished = datetime.now(timezone.utc).isoformat()
    if outcome['status'] == 'timeout':
        receipt = {'stage': name, 'status': 'timeout', 'error': outcome['error'], 'timeout_seconds': timeout_seconds}
    elif outcome['status'] == 'error':
        receipt = {'stage': name, 'status': 'failed', 'error': outcome['error'], 'message': outcome['message']}
    else:
        value = outcome['value']
        payload = dict(value) if isinstance(value, dict) else {'result': value}
        status = payload.pop('status', 'ok')
        receipt = {'stage': name, 'status': status, **payload}
    receipt.update(started_at=started, finished_at=finished, elapsed_seconds=elapsed)
    save(root/'.local/nightly'/date/(name+'.json'), receipt)
    return receipt


def dry_run_plan(root, only, date):
    plan = {'date': date, 'stages': [s for s in STAGES if not only or s == only], 'only': only,
            'pre_stage_budget_seconds': PRE_STAGE_BUDGET_SECONDS, 'total_ceiling_seconds': TOTAL_CEILING_SECONDS,
            'locks': [{'path': Path(rel).name, 'present': (root/rel).exists()} for rel in LOCKS]}
    try:
        config = validate_importers(root)
        plan['importers_due'] = [i['id'] for i in due_importers(config, datetime.now(timezone.utc).date())]
        plan['research_ignore_gpu_busy'] = bool(config.get('research_ignore_gpu_busy', True))
    except Exception as e:
        plan['importers_error'] = f'{type(e).__name__}: {e}'
    return plan


def run(root, dry_run=False, only=None):
    date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    if dry_run:
        print(json.dumps(dry_run_plan(root, only, date), indent=2), flush=True)
        return 0
    job_start = time.monotonic()
    pre_deadline = job_start+PRE_STAGE_BUDGET_SECONDS
    overall_deadline = job_start+TOTAL_CEILING_SECONDS
    awake = False
    try:
        if os.name == 'nt':
            awake = bool(ctypes.windll.kernel32.SetThreadExecutionState(0x80000001))  # ES_CONTINUOUS|ES_SYSTEM_REQUIRED
        receipts = {}
        for name in STAGES:
            if only and name != only: continue
            if name == 'locks':
                receipts[name] = run_stage(root, date, name, STAGE_TIMEOUTS['locks'], lambda r=root: stage_locks(r))
            elif name == 'importers':
                try:
                    due = due_importers(validate_importers(root), datetime.now(timezone.utc).date())
                except Exception:
                    due = []
                hard_timeout = (sum(i['timeout_seconds'] for i in due)+120) if due else 60
                soft_budget = max(0, pre_deadline-time.monotonic())
                receipts[name] = run_stage(root, date, name, hard_timeout, lambda r=root, b=soft_budget: stage_importers(r, b))
            elif name == 'research':
                budget = max(60, overall_deadline-time.monotonic()-POST_STAGE_RESERVE_SECONDS)
                receipts[name] = run_stage(root, date, name, budget+180, lambda r=root, b=budget: stage_research(r, b))
            elif name == 'policy':
                receipts[name] = run_stage(root, date, name, STAGE_TIMEOUTS['policy'], lambda r=root: stage_policy(r))
            elif name == 'health':
                receipts[name] = run_stage(root, date, name, STAGE_TIMEOUTS['health'], lambda r=root, d=date: stage_health(r, d))
            elif name == 'prune':
                receipts[name] = run_stage(root, date, name, STAGE_TIMEOUTS['prune'], lambda r=root: stage_prune(r))
            elif name == 'digest':
                receipts[name] = run_stage(root, date, name, STAGE_TIMEOUTS['digest'], lambda r=root, d=date: stage_digest(r, d))
        final = receipts.get('digest')
        return 1 if final and final['status'] in ('failed', 'timeout') else 0
    finally:
        if awake and os.name == 'nt':
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)  # ES_CONTINUOUS


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dry-run', action='store_true', help='Print the plan; run nothing, write nothing')
    p.add_argument('--only', choices=STAGES, help='Run exactly one stage')
    a = p.parse_args(argv)
    return run(ROOT, dry_run=a.dry_run, only=a.only)


if __name__ == '__main__':
    sys.exit(main())
