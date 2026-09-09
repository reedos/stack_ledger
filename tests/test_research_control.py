"""Loopback/tailnet identity, mount routing, reviewer attribution and install-command construction.

No real Tailscale Serve configuration, schtasks task or live server process is touched; --install-*
commands are only constructed and inspected, never executed with --yes.
"""
import email.message
import http.client
import json
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import research_control as control
import editorial_review


def headers(pairs):
    m = email.message.Message()
    for k, v in pairs: m.add_header(k, v)
    return m


def handler(port, tailnet, client_ip, pairs):
    server = SimpleNamespace(server_port=port, tailnet=tailnet)
    return SimpleNamespace(server=server, client_address=(client_ip, 51000), headers=headers(pairs))


TAILNET = {'hostname': 'reeds-pc.tailf68402.ts.net', 'mount': '/research', 'port': 47393}


class IdentityTests(unittest.TestCase):
    """Pure classification: identity(handler) never touches the network or filesystem."""

    def test_loopback_identity_requires_exact_host_and_no_tailscale_headers(self):
        h = handler(9001, None, '127.0.0.1', [('Host', '127.0.0.1:9001')])
        self.assertEqual(control.identity(h), {'channel': 'loopback', 'login': None})

    def test_loopback_refuses_spoofed_tailscale_header(self):
        h = handler(9001, None, '127.0.0.1', [('Host', '127.0.0.1:9001'), ('Tailscale-User-Login', 'x@example.org')])
        self.assertIsNone(control.identity(h))

    def test_loopback_refuses_duplicate_host(self):
        h = handler(9001, None, '127.0.0.1', [('Host', '127.0.0.1:9001'), ('Host', '127.0.0.1:9001')])
        self.assertIsNone(control.identity(h))

    def test_tailnet_identity_requires_hostname_login_and_loopback_client(self):
        h = handler(9001, TAILNET, '127.0.0.1', [('Host', TAILNET['hostname']), ('Tailscale-User-Login', 'reedosaki@gmail.com')])
        self.assertEqual(control.identity(h), {'channel': 'tailnet', 'login': 'reedosaki@gmail.com'})

    def test_tailnet_refuses_duplicate_login_header(self):
        h = handler(9001, TAILNET, '127.0.0.1', [('Host', TAILNET['hostname']), ('Tailscale-User-Login', 'a@example.org'), ('Tailscale-User-Login', 'b@example.org')])
        self.assertIsNone(control.identity(h))

    def test_tailnet_refuses_missing_login(self):
        h = handler(9001, TAILNET, '127.0.0.1', [('Host', TAILNET['hostname'])])
        self.assertIsNone(control.identity(h))

    def test_tailnet_refuses_wrong_host(self):
        h = handler(9001, TAILNET, '127.0.0.1', [('Host', 'attacker.example'), ('Tailscale-User-Login', 'reedosaki@gmail.com')])
        self.assertIsNone(control.identity(h))

    def test_no_config_never_grants_tailnet_channel(self):
        h = handler(9001, None, '127.0.0.1', [('Host', TAILNET['hostname']), ('Tailscale-User-Login', 'reedosaki@gmail.com')])
        self.assertIsNone(control.identity(h))


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)/'research-control.json'

    def test_absent_config_is_none(self):
        self.assertIsNone(control.tailnet_config(self.path))

    def test_valid_config(self):
        self.path.write_text(json.dumps({'tailnet': TAILNET}), encoding='utf-8')
        self.assertEqual(control.tailnet_config(self.path), TAILNET)

    def test_invalid_hostname_mount_port_rejected(self):
        for bad in [dict(TAILNET, hostname='not-a-tailnet-host'), dict(TAILNET, hostname='UPPER.tailnet.ts.net'),
                    dict(TAILNET, mount='research'), dict(TAILNET, mount='/has space'),
                    dict(TAILNET, port=80), dict(TAILNET, port=99999), dict(TAILNET, port='47393')]:
            self.path.write_text(json.dumps({'tailnet': bad}), encoding='utf-8')
            with self.subTest(bad=bad): self.assertRaises(ValueError, control.tailnet_config, self.path)

    def test_unexpected_shape_rejected(self):
        self.path.write_text(json.dumps({'tailnet': TAILNET, 'extra': 1}), encoding='utf-8')
        self.assertRaises(ValueError, control.tailnet_config, self.path)
        self.path.write_text(json.dumps({'tailnet': {'hostname': TAILNET['hostname']}}), encoding='utf-8')
        self.assertRaises(ValueError, control.tailnet_config, self.path)


class InstallCommandTests(unittest.TestCase):
    """Command construction only; --install-* is never run with --yes here."""

    def test_startup_launcher_uses_the_base_interpreter_and_the_startup_folder(self):
        root = Path('C:/live/stack_ledger')
        path, body = control.startup_launcher(root, root/'.local/research-control.json')
        self.assertEqual(path.name, 'Stack Ledger research control.vbs')
        self.assertTrue(str(path).replace('\\', '/').endswith('Microsoft/Windows/Start Menu/Programs/Startup/Stack Ledger research control.vbs'))
        self.assertIn('research_control.py', body); self.assertIn('--config', body); self.assertIn(control.base_python(), body)
        self.assertNotIn('.venv', control.base_python())
        self.assertTrue(body.rstrip().endswith(', 0, False'))   # hidden window, no wait

    def test_install_startup_without_run_writes_nothing(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        with patch.dict(control.os.environ, {'APPDATA': temp.name}):
            path, body = control.install_startup(Path(temp.name), Path(temp.name)/'cfg.json', False)
            self.assertFalse(path.exists())
            path, body = control.install_startup(Path(temp.name), Path(temp.name)/'cfg.json', True)
            self.assertTrue(path.exists()); self.assertEqual(path.read_bytes().decode('utf-8'), body)

    def test_tailnet_serve_command_construction(self):
        cmd = control.tailnet_serve_command(TAILNET)
        self.assertEqual(cmd, ['tailscale', 'serve', '--bg', '--set-path', '/research', 'http://127.0.0.1:47393'])

    def test_install_tailnet_without_run_never_calls_subprocess(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        with patch.object(control.subprocess, 'run') as run:
            cmd, backup = control.install_tailnet(root, TAILNET, False)
            run.assert_not_called()
        self.assertEqual(cmd, control.tailnet_serve_command(TAILNET))
        self.assertFalse(backup.exists())

    def test_cli_install_startup_prints_without_yes_or_execution(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        result = subprocess.run([sys.executable, str(ROOT/'scripts/research_control.py'), '--install-startup',
            '--research-root', temp.name], cwd=ROOT, capture_output=True, text=True, encoding='utf-8', timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Would write', result.stdout); self.assertIn('research_control.py', result.stdout)
        self.assertFalse((Path(temp.name)/'.local').exists())

    def test_cli_install_tailnet_without_config_errors_and_does_not_run(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        result = subprocess.run([sys.executable, str(ROOT/'scripts/research_control.py'), '--install-tailnet',
            '--research-root', temp.name], cwd=ROOT, capture_output=True, text=True, encoding='utf-8', timeout=15)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((Path(temp.name)/'.local').exists())


class EventsRobustnessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup); self.root = Path(self.temp.name)

    def test_torn_trailing_line_is_dropped_and_counted(self):
        path = editorial_review.queue(self.root)/'editorial-events.jsonl'; path.parent.mkdir(parents=True)
        good = {'id': 'catalog-'+'a'*24, 'kind': 'catalog_change', 'status': 'approved'}
        path.write_text(json.dumps(good)+'\n'+'{"id": "catalog-b", "kind": "catalog_ch', encoding='utf-8')
        report = {}
        rows = editorial_review.events(self.root, report=report)
        self.assertEqual(rows, [good]); self.assertEqual(report['unreadable_events'], 1)

    def test_clean_log_reports_zero(self):
        path = editorial_review.queue(self.root)/'editorial-events.jsonl'; path.parent.mkdir(parents=True)
        path.write_text('{"id": "a"}\n{"id": "b"}\n', encoding='utf-8')
        report = {}
        self.assertEqual(len(editorial_review.events(self.root, report=report)), 2)
        self.assertEqual(report['unreadable_events'], 0)

    def test_verify_log_cli_reports_without_changing_file(self):
        path = editorial_review.queue(self.root)/'editorial-events.jsonl'; path.parent.mkdir(parents=True)
        path.write_text('{"id": "a"}\nnot json\n', encoding='utf-8')
        before = path.read_bytes()
        printed = []
        with patch.object(editorial_review, 'ROOT', self.root), patch.object(sys, 'argv', ['editorial_review.py', '--verify-log']), \
             patch('builtins.print', side_effect=lambda *a, **k: printed.append(' '.join(str(x) for x in a))):
            editorial_review.main()
        self.assertEqual(path.read_bytes(), before)
        self.assertIn('"unreadable_events": 1', printed[0])


class ServerTests(unittest.TestCase):
    """Real loopback server; tailnet requests are simulated with headers (as Tailscale Serve would send)."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup); self.root = Path(self.temp.name)
        policy = {'reviewers': ['reedos'], 'reviewer_accounts': {'reedos': ['fixture-human']},
                  'reviewer_logins': {'reedos': ['reedosaki@gmail.com']}}
        (self.root/'research').mkdir(parents=True)
        (self.root/'research/editorial-policy.json').write_text(json.dumps(policy), encoding='utf-8')
        self.http, self.url = control.server(self.root, config=TAILNET, asset_root=ROOT)
        self.assertEqual(self.http.server_port, TAILNET['port'])
        self.token = self.url.rstrip('/').rsplit('/', 1)[-1]
        self.worker = threading.Thread(target=self.http.serve_forever, daemon=True); self.worker.start()

    def tearDown(self):
        self.http.shutdown(); self.http.server_close(); self.worker.join()

    def get(self, path, extra_headers):
        req = urllib.request.Request(f'http://127.0.0.1:{self.http.server_port}{path}', headers=extra_headers)
        try:
            with urllib.request.urlopen(req, timeout=5) as r: return r.status, r.read()
        except urllib.error.HTTPError as e:
            with e: return e.code, e.read()

    def raw(self, method, path, header_pairs, body=None):
        # http.client.HTTPConnection.request() cannot send a duplicated header name (needs a mapping);
        # putrequest/putheader lets a test send two Host: lines the way a spoofed request would.
        conn = http.client.HTTPConnection('127.0.0.1', self.http.server_port, timeout=5)
        try:
            conn.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
            for name, value in header_pairs: conn.putheader(name, value)
            if body is not None:
                conn.putheader('Content-Length', str(len(body))); conn.endheaders(body)
            else:
                conn.endheaders()
            r = conn.getresponse(); return r.status, dict(r.getheaders()), r.read()
        finally:
            conn.close()

    def tailnet_headers(self, login='reedosaki@gmail.com'):
        return {'Host': TAILNET['hostname'], 'Tailscale-User-Login': login}

    def loopback_headers(self):
        return {'Host': f'127.0.0.1:{self.http.server_port}'}

    def test_loopback_status_works_without_tailnet_headers(self):
        code, body = self.get(f'/{self.token}/status', self.loopback_headers())
        self.assertEqual(code, 200)

    def test_mount_stripped_and_not_stripped_route_identically(self):
        # As if Serve already stripped the /research prefix (matches what this repo's live probe observed):
        code1, body1 = self.get(f'/{self.token}/status', self.tailnet_headers())
        # As if Serve forwarded the mount prefix unchanged:
        code2, body2 = self.get(f'/research/{self.token}/status', self.tailnet_headers())
        self.assertEqual((code1, code2), (200, 200))
        self.assertEqual(json.loads(body1).keys(), json.loads(body2).keys())

    def test_unmapped_tailnet_login_refuses_every_route_not_read_only(self):
        code, _ = self.get(f'/{self.token}/status', self.tailnet_headers(login='stranger@example.org'))
        self.assertEqual(code, 403)
        code, _ = self.get(f'/{self.token}/findings', self.tailnet_headers(login='stranger@example.org'))
        self.assertEqual(code, 403)

    def test_duplicate_host_header_refused(self):
        status, headers_out, _ = self.raw('GET', f'/{self.token}/status', [('Host', TAILNET['hostname']), ('Host', TAILNET['hostname']), ('Tailscale-User-Login', 'reedosaki@gmail.com')])
        self.assertEqual(status, 403)

    def test_origin_mismatch_refused_on_mutation(self):
        headers = dict(self.tailnet_headers(), **{'Origin': 'https://attacker.example', 'X-Session-Key': self.token, 'Content-Type': 'application/json'})
        req = urllib.request.Request(f'http://127.0.0.1:{self.http.server_port}/{self.token}/stop', data=b'{}', headers=headers, method='POST')
        try:
            with urllib.request.urlopen(req, timeout=5) as r: code = r.status
        except urllib.error.HTTPError as e:
            with e: code = e.code
        self.assertEqual(code, 403)

    def test_correct_tailnet_origin_is_accepted_for_mutation(self):
        headers = dict(self.tailnet_headers(), **{'Origin': 'https://'+TAILNET['hostname'], 'X-Session-Key': self.token, 'Content-Type': 'application/json'})
        req = urllib.request.Request(f'http://127.0.0.1:{self.http.server_port}/{self.token}/stop', data=b'{}', headers=headers, method='POST')
        try:
            with urllib.request.urlopen(req, timeout=5) as r: code = r.status
        except urllib.error.HTTPError as e:
            with e: code = e.code
        # No active session -> a handled ValueError (400), not a 403 identity/CSRF rejection.
        self.assertEqual(code, 400)

    def test_redirect_from_mount_root_for_authorized_tailnet_identity(self):
        status, out_headers, _ = self.raw('GET', '/', [('Host', TAILNET['hostname']), ('Tailscale-User-Login', 'reedosaki@gmail.com')])
        self.assertEqual(status, 302)
        self.assertEqual(out_headers.get('Location'), TAILNET['mount']+'/'+self.token+'/')
        status, _, _ = self.raw('GET', TAILNET['mount']+'/', [('Host', TAILNET['hostname']), ('Tailscale-User-Login', 'reedosaki@gmail.com')])
        self.assertEqual(status, 302)

    def test_redirect_refused_for_unmapped_login(self):
        status, _, _ = self.raw('GET', '/', [('Host', TAILNET['hostname']), ('Tailscale-User-Login', 'stranger@example.org')])
        self.assertEqual(status, 403)


class ReviewerAttributionTests(unittest.TestCase):
    """A recorded review over tailnet carries channel/login and resolves to the mapped reviewer id."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup); self.root = Path(self.temp.name)
        policy = {'reviewers': ['reedos'], 'reviewer_accounts': {'reedos': ['fixture-human']},
                  'reviewer_logins': {'reedos': ['reedosaki@gmail.com']}}
        (self.root/'research').mkdir(parents=True)
        (self.root/'research/editorial-policy.json').write_text(json.dumps(policy), encoding='utf-8')
        self.rid = 'discovery-'+'a'*24
        item = {'id': self.rid, 'kind': 'coverage_expansion', 'layer': 'energy', 'url': 'https://example.org/source',
            'created_at': '2026-09-08T00:00:00Z', 'finding': {'kind': 'project', 'subject': 'Fixture plant',
            'claim': 'A company reports operation.', 'evidence': 'Source states operation.',
            'basis': 'actual', 'why_track': 'Investigate dependable power.', 'next_question': 'Verify.'}}
        import research
        research.save(editorial_review.queue(self.root)/(self.rid+'.json'), item)
        self.http, self.url = control.server(self.root, config=TAILNET, asset_root=ROOT)
        self.token = self.url.rstrip('/').rsplit('/', 1)[-1]
        self.worker = threading.Thread(target=self.http.serve_forever, daemon=True); self.worker.start()

    def tearDown(self):
        self.http.shutdown(); self.http.server_close(); self.worker.join()

    def test_tailnet_review_records_channel_and_login(self):
        import findings_review
        with urllib.request.urlopen(urllib.request.Request(
                f'http://127.0.0.1:{self.http.server_port}/{self.token}/findings',
                headers={'Host': TAILNET['hostname'], 'Tailscale-User-Login': 'reedosaki@gmail.com'})) as r:
            data = json.loads(r.read())
        self.assertEqual(data['reviewer'], 'reedos')
        row = data['findings'][0]
        body = json.dumps({'id': self.rid, 'decision': 'investigate', 'rationale': 'Verify the operator report.',
            'proposal_hash': row['proposal_hash'], 'review_hash': row['review_hash'], 'confirmed': True}).encode()
        req = urllib.request.Request(f'http://127.0.0.1:{self.http.server_port}/{self.token}/review', data=body,
            headers={'Host': TAILNET['hostname'], 'Tailscale-User-Login': 'reedosaki@gmail.com',
                     'Origin': 'https://'+TAILNET['hostname'], 'X-Session-Key': self.token, 'Content-Type': 'application/json'},
            method='POST')
        with urllib.request.urlopen(req, timeout=5) as r:
            result = json.loads(r.read())
        self.assertEqual(result['reviewer'], 'reedos')
        event = editorial_review.events(self.root)[-1]
        self.assertEqual(event['reviewer'], 'reedos')
        self.assertEqual(event['channel'], 'tailnet')
        self.assertEqual(event['login'], 'reedosaki@gmail.com')

    def test_loopback_review_has_no_login_field(self):
        with patch('findings_review.getpass.getuser', return_value='fixture-human'):
            with urllib.request.urlopen(f'http://127.0.0.1:{self.http.server_port}/{self.token}/findings') as r:
                data = json.loads(r.read())
            row = data['findings'][0]
            body = json.dumps({'id': self.rid, 'decision': 'investigate', 'rationale': 'Verify the operator report.',
                'proposal_hash': row['proposal_hash'], 'review_hash': row['review_hash'], 'confirmed': True}).encode()
            req = urllib.request.Request(f'http://127.0.0.1:{self.http.server_port}/{self.token}/review', data=body,
                headers={'Host': f'127.0.0.1:{self.http.server_port}', 'Origin': f'http://127.0.0.1:{self.http.server_port}',
                         'X-Session-Key': self.token, 'Content-Type': 'application/json'}, method='POST')
            with urllib.request.urlopen(req, timeout=5) as r: json.loads(r.read())
        event = editorial_review.events(self.root)[-1]
        self.assertEqual(event['channel'], 'loopback')
        self.assertNotIn('login', event)


if __name__ == '__main__':
    unittest.main()


class SessionKeyTests(unittest.TestCase):
    """The page derives its session key from the LAST path segment so the phone's /<mount>/<token>/ URL works."""
    def test_node_session_key_unit_tests(self):
        import shutil
        node = shutil.which('node')
        if not node:
            self.skipTest('node is not installed')
        result = subprocess.run([node, '--test', 'tests/control_key.cjs'], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_no_panel_script_reads_the_first_path_segment_as_the_key(self):
        for name in ['control.js', 'reviews.js', 'visuals.js', 'activity.js']:
            path = ROOT/'tools/research-control'/name
            if path.exists():
                self.assertNotIn("location.pathname.split('/')[1]", path.read_text(encoding='utf-8'), name)
