"""PDF text for owner-approved sources only.

Grid-operator load forecasts, earnings-call transcripts and most filings are published only as
PDFs, and until 09/23/2026 every one was logged as a collection gap. This adapter turns an
approved PDF into the same inert text the HTML path produces: no scripts, forms, attachments or
OCR, only the text each page draws, with a "[Page N]" line before each page so a reviewer can
find a quote in the original. Which PDFs may be read is research/pdf-sources.json, never a
model's choice; a PDF anywhere else stays a collection gap.

The parser is pypdf (pure Python). It is optional: without it a PDF stays a collection gap
('pdf_parser_unavailable'), exactly as before, so the rest of the runner remains stdlib-only.
"""
import html
import io
import json
import logging
import re
from pathlib import Path
from urllib.parse import urlparse

from document_formats import CollectionGap

ROOT = Path(__file__).resolve().parents[1]
POLICY = 'research/pdf-sources.json'
# pypdf logs every repaired cross-reference; one malformed report wrote 400 lines to the night log.
logging.getLogger('pypdf').setLevel(logging.ERROR)
PDF_TYPES = {'application/pdf', 'application/octet-stream', 'binary/octet-stream', 'application/x-pdf'}
PAGE_MARK = re.compile(r'^\[Page (\d+)\]$', re.M)
# A table row flattened to text: three or more numbers on one line with nothing but short
# labels, units or separators between them. Its figures may have lost their column headings.
_NUMBER = r'[-+(]?\$?\d[\d,]*(?:\.\d+)?%?\)?'
TABLE_ROW = re.compile(r'(?:^|\n)[^\n]*?' + _NUMBER + r'(?:[ \t]+(?:[A-Za-z/%$]{1,6}[ \t]+)?' + _NUMBER + r'){2,}[^\n]*', re.M)


def load_policy(root=ROOT, registry=None):
    """The reviewed allowlist, checked against the source registry. Returns {} when absent."""
    path = Path(root) / POLICY
    if not path.exists():
        return {}
    policy = json.loads(path.read_text(encoding='utf-8'))
    check_policy(policy, registry)
    return policy


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def check_policy(policy, registry=None):
    _require(isinstance(policy, dict) and set(policy) == {'version', 'owner_decision', 'max_bytes', 'max_pages', 'documents', 'prefixes'},
             'Unexpected PDF policy fields')
    _require(policy['version'] == 1 and isinstance(policy['owner_decision'], str) and len(policy['owner_decision']) >= 40, 'Invalid PDF policy version or decision')
    _require(type(policy['max_bytes']) is int and 100_000 <= policy['max_bytes'] <= 30_000_000, 'Invalid PDF size cap')
    _require(type(policy['max_pages']) is int and 1 <= policy['max_pages'] <= 400, 'Invalid PDF page cap')
    _require(isinstance(policy['documents'], list) and isinstance(policy['prefixes'], list), 'Invalid PDF policy lists')
    sources = {s['id']: s for s in registry['sources']} if registry else None
    seen = set()
    for row in policy['documents']:
        _require(isinstance(row, dict) and set(row) == {'source', 'why'} and isinstance(row['why'], str) and row['why'], 'Invalid approved PDF document')
        _require(row['source'] not in seen, 'Duplicate approved PDF document')
        seen.add(row['source'])
        if sources is not None:
            _require(row['source'] in sources, f"Approved PDF source is not registered: {row['source']}")
            _require(urlparse(sources[row['source']]['url']).scheme == 'https', 'Approved PDF must be https')
    for row in policy['prefixes']:
        _require(isinstance(row, dict) and set(row) == {'host', 'path_prefix', 'why'} and isinstance(row['why'], str) and row['why'], 'Invalid approved PDF prefix')
        _require(re.fullmatch(r'[a-z0-9.-]+\.[a-z]{2,}', row['host'] or '') is not None, 'Invalid approved PDF host')
        _require(isinstance(row['path_prefix'], str) and row['path_prefix'].startswith('/') and len(row['path_prefix']) >= 8
                 and '..' not in row['path_prefix'], 'Approved PDF prefix must be a specific path')


def approved_urls(policy, registry):
    by_id = {s['id']: s for s in registry['sources']}
    return {by_id[row['source']]['url'] for row in policy.get('documents', []) if row['source'] in by_id}


def allowed(url, policy, urls):
    """Whether `url` may be read as a PDF: an approved document, or a PDF under an approved path."""
    if not policy:
        return False
    if url in urls:
        return True
    u = urlparse(url)
    return u.scheme == 'https' and not u.query and u.path.lower().endswith('.pdf') and any(
        u.hostname == row['host'] and u.path.startswith(row['path_prefix']) for row in policy['prefixes'])


def pdf_html(body, max_pages):
    """Inert HTML carrying each page's text, for ReadableHTML. Raises CollectionGap when unreadable."""
    if not body.startswith(b'%PDF-'):
        raise CollectionGap('not_a_pdf')
    try:
        from pypdf import PdfReader
    except ImportError:
        raise CollectionGap('pdf_parser_unavailable') from None
    try:
        reader = PdfReader(io.BytesIO(body))
        if reader.is_encrypted and not reader.decrypt(''):
            raise CollectionGap('pdf_encrypted')
        if len(reader.pages) > max_pages:
            raise CollectionGap('pdf_too_many_pages')
        parts = []
        for number, page in enumerate(reader.pages, 1):
            text = page.extract_text() or ''
            parts.append(f'<section><p>[Page {number}]</p><pre>{html.escape(text)}</pre></section>')
    except CollectionGap:
        raise
    except Exception as error:
        raise CollectionGap('pdf_unreadable') from error
    return '\n'.join(parts)


def is_pdf_text(document):
    """Readable text that came from pdf_html: it always opens on the first page mark."""
    return document.startswith('[Page 1]\n')


def page_of(document, evidence_at):
    """The page number a character offset in a PDF's readable text falls on, or None."""
    if evidence_at < 0:
        return None
    pages = [m for m in PAGE_MARK.finditer(document) if m.start() <= evidence_at]
    return int(pages[-1].group(1)) if pages else None


def looks_tabular(evidence):
    """Evidence that includes a flattened table row, whose figures may have lost their headings."""
    return TABLE_ROW.search(evidence) is not None
