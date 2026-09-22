#!/usr/bin/env python3
"""Curated 2026-09-22 exhaustive research apply (chunked self-extracting payload).

Runtime-equivalent to the maintainer apply script. Dry-run by default; pass --apply to write.
"""
from __future__ import annotations

import base64
import zlib
from pathlib import Path

_here = Path(__file__).resolve().parent
_parts = sorted(_here.glob("curated_exhaustive_20260922.payload.*.b64"))
if not _parts:
    raise SystemExit("missing curated_exhaustive_20260922.payload.*.b64 next to this script")
_PAYLOAD = "".join(p.read_text(encoding="ascii").strip() for p in _parts)
exec(compile(zlib.decompress(base64.b64decode(_PAYLOAD)), __file__, "exec"), globals())
