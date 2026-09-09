"""Test helper only (unittest discovery ignores files that don't match test*.py).

Runs importer_common.apply_changes in its own process, rooted at argv[1], so validate.py's
module-level ROOT resolves to the temp copy under test rather than the real repository that
happens to already be on a parent process's sys.path. Reads a JSON kwargs object from stdin,
writes {'ok': True, 'receipt': ...} or {'ok': False, 'error': ...} as JSON to stdout.
"""
import json
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(root/'scripts'))
import importer_common as ic

kwargs = json.loads(sys.stdin.read())
try:
    receipt = ic.apply_changes(root, **kwargs)
    print(json.dumps({'ok': True, 'receipt': receipt}))
except Exception as e:
    print(json.dumps({'ok': False, 'error': type(e).__name__+': '+str(e)}))
