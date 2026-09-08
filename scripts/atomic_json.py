"""Replace JSON without exposing partial files; tolerate brief Windows sharing locks."""
import json
import os
import time
import uuid


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n', encoding='utf-8')
        for attempt in range(6):
            try:
                os.replace(temporary, path)
                return
            except PermissionError:
                if attempt == 5:
                    raise
                time.sleep(.05 * 2 ** attempt)
    finally:
        temporary.unlink(missing_ok=True)
