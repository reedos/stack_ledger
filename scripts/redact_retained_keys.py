"""Redact registered API keys out of the wire snapshots retained under .local/.

EIA API v2 echoes the whole request URL -- api_key and all -- inside every response body, and the
EIA importers keep that wire response as their snapshot: on 2026-09-11 the live key sat in 159
files under .local/eia and .local/grid, 10.7 MB of them. api_access.fetch now redacts every
registered key out of a body before any caller can retain it, so nothing new can land; this
cleans what already did.

Keys are read from .local/api-keys.json and never printed, and the vault itself is never
rewritten. A key found outside .local/ is reported and left alone: that one is a disclosure to
act on (rotate the key), not a file to quietly patch.

    python scripts/redact_retained_keys.py           # report which files hold a key
    python scripts/redact_retained_keys.py --apply   # rewrite the .local/ ones in place
"""
import argparse
import os
import sys
import uuid
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parent))
from api_access import REDACTED, vault

ROOT=Path(__file__).resolve().parents[1]
VAULT=Path('.local/api-keys.json')
SKIP={'.git','node_modules','__pycache__'}


def secrets(root=ROOT):
    """(name, key bytes) per registered key, long ones only: a short vault value would match
    unrelated bytes everywhere and blank them."""
    return sorted((n,v.encode('utf-8')) for n,v in vault(root).items() if isinstance(v,str) and len(v)>=16)


def holders(root=ROOT,keys=None):
    """Every file under root holding a registered key: (relative path, {key name: occurrences}, bytes)."""
    keys=secrets(root) if keys is None else keys
    found=[]
    if not keys:return found
    for path in sorted(root.rglob('*')):
        rel=path.relative_to(root)
        if rel==VAULT or SKIP&set(rel.parts) or not path.is_file():continue
        try:blob=path.read_bytes()
        except OSError:continue
        counts={n:blob.count(v) for n,v in keys if v in blob}
        if counts:found.append((rel,counts,len(blob)))
    return found


def retained(rel):
    return rel.parts[:1]==('.local',)


def rewrite(path,keys):
    """Replace every key with REDACTED through a temp file, so a reader never sees a half file."""
    blob=path.read_bytes()
    for _,v in keys:blob=blob.replace(v,REDACTED)
    temporary=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        temporary.write_bytes(blob);os.replace(temporary,path)
    finally:
        temporary.unlink(missing_ok=True)
    return len(blob)


def run(root=ROOT,apply=False,out=print):
    """Report, and with apply rewrite, every retained .local/ file holding a registered key."""
    keys=secrets(root)
    if not keys:
        out('No registered key in .local/api-keys.json; nothing to search for.')
        return {'files':[],'redacted':0,'outside':[]}
    found=holders(root,keys)
    inside=[f for f in found if retained(f[0])]
    outside=[f[0] for f in found if not retained(f[0])]
    for rel,counts,size in found:
        out(f"{rel.as_posix()} · {size/1e6:.2f} MB · "+', '.join(f'{n} x{c}' for n,c in sorted(counts.items()))
            +('' if retained(rel) else ' · OUTSIDE .local/'))
    out(f'{len(inside)} retained file(s) under .local/ hold {sum(sum(c.values()) for _,c,_ in inside)} key occurrence(s), '
        f'{sum(s for _,_,s in inside)/1e6:.2f} MB'
        +(f'; {len(outside)} file(s) outside .local/ hold one too -- rotate the key, redaction is not enough' if outside else ''))
    if not apply:
        out('Dry run. Pass --apply to rewrite the .local/ files in place.')
        return {'files':[f[0] for f in inside],'redacted':0,'outside':outside}
    for rel,_,_ in inside:rewrite(root/rel,keys)
    left=[f[0] for f in holders(root,keys) if retained(f[0])]
    out(f'Redacted {len(inside)} file(s); {len(left)} still hold a key.')
    return {'files':[f[0] for f in inside],'redacted':len(inside),'outside':outside,'left':left}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__.splitlines()[0]);p.add_argument('--apply',action='store_true')
    a=p.parse_args(argv)
    return 1 if run(ROOT,apply=a.apply)['outside'] else 0


if __name__=='__main__':sys.exit(main())
