"""Ensure the existing private control server is available; never launch research."""
import os
import subprocess
import sys
import time
from urllib.request import urlopen

def ensure(root):
    from research_control import tailnet_config, session_token
    cfg = tailnet_config(root/'.local/research-control.json')
    if not cfg:
        return {'status':'not_configured'}
    url = f"http://127.0.0.1:{cfg['port']}/{session_token(root)}/"
    def ready():
        try:
            with urlopen(url, timeout=2) as response:
                return response.status == 200 and b'overnight.js' in response.read()
        except OSError:
            return False
    if ready():
        return {'status':'ready'}
    log = root/'.local/research-control-service.log'
    with log.open('ab') as output:
        child = subprocess.Popen([sys.executable, str(root/'scripts/research_control.py'),
            '--config', str(root/'.local/research-control.json')], cwd=root,
            stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0) | getattr(subprocess,'DETACHED_PROCESS',0))
    for _ in range(20):
        if ready():
            return {'status':'ready','started':True}
        if child.poll() is not None:
            break
        time.sleep(.25)
    return {'status':'unavailable','reason':'The private dashboard did not become ready; research can continue.'}
