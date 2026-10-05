"""Local storage headroom checks; no collection, publication or cleanup."""
import shutil
from pathlib import Path

MIN_FREE_BYTES = 2 * 1024**3


class LowDiskSpace(OSError):
    pass


def check_storage(root):
    """Check both checkout and private storage (which may be a junction on another disk)."""
    checked = []
    for target in (Path(root), Path(root) / '.local'):
        while not target.exists():
            target = target.parent
        target = target.resolve()
        free = shutil.disk_usage(target).free
        if free < MIN_FREE_BYTES:
            raise LowDiskSpace(f'Insufficient disk space: {free / 1024**3:.2f} GiB free; '
                               '2 GiB required. Research paused; retained evidence is untouched.')
        checked.append({'path': str(target), 'free_bytes': free})
    return checked
