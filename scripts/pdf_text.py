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
from urllib.parse import unquote, urlparse

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
        _require(isinstance(row, dict) and set(row) in ({'host', 'path_prefix', 'why'}, {'host', 'path_prefix', 'why', 'topics'})
                 and isinstance(row['why'], str) and row['why'], 'Invalid approved PDF prefix')
        _require(re.fullmatch(r'[a-z0-9.-]+\.[a-z]{2,}', row['host'] or '') is not None, 'Invalid approved PDF host')
        topics = row.get('topics', [])
        _require(isinstance(topics, list) and all(isinstance(t, str) and 2 <= len(t) <= 40 for t in topics)
                 and ('topics' not in row or topics), 'Approved PDF topics must be a non-empty list of words')
        # A folder that holds only the reports may stand alone; a shared store ('/media/' on
        # spp.org, '/files/docs/' on ercot.com) must name the report in its file path as well.
        _require(isinstance(row['path_prefix'], str) and row['path_prefix'].startswith('/') and '..' not in row['path_prefix']
                 and len(row['path_prefix']) >= (6 if topics else 8), 'Approved PDF prefix must be a specific path')


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
    # Compared the way source_policy.discoverable compares an index page's children: decoded and
    # lowercased, so '/DotCom/' and a '%20' in MISO's paths match the reviewed prefix either way.
    path = unquote(u.path).lower()
    from source_policy import topical
    return u.scheme == 'https' and not u.query and not u.fragment and path.endswith('.pdf') and '..' not in path and any(
        u.hostname == row['host'] and path.startswith(unquote(row['path_prefix']).lower())
        and (not row.get('topics') or topical(path, row['topics'])) for row in policy['prefixes'])


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
        drawn = 0
        for number, page in enumerate(reader.pages, 1):
            # pypdf decodes ToUnicode maps with surrogatepass, so a malformed symbol font can leave
            # a lone surrogate that no later step can encode or hash. Pair what pairs, replace the rest.
            text = (page.extract_text() or '').encode('utf-16', 'surrogatepass').decode('utf-16', 'replace')
            drawn += len(text.strip())
            parts.append(f'<section><p>[Page {number}]</p><pre>{html.escape(text)}</pre></section>')
    except CollectionGap:
        raise
    except Exception as error:
        # An AES-encrypted PDF (Alphabet's assurance letters) opens with an empty password, but pypdf
        # needs the 'cryptography' package for it; without that it is not a corrupt file, say so.
        if type(error).__name__ == 'DependencyError':
            raise CollectionGap('pdf_needs_cryptography') from error
        raise CollectionGap('pdf_unreadable') from error
    # The page marks alone would clear the runner's 250-character floor for a scanned report.
    if drawn < 250:
        raise CollectionGap('pdf_no_text')
    return '\n'.join(parts)


def is_pdf_text(document):
    """Readable text that came from pdf_html: it always opens on the first page mark."""
    return document.startswith('[Page 1]\n')


def has_page_mark(evidence):
    """Evidence that runs across a runner-inserted page mark: the mark's digits are not source text."""
    return PAGE_MARK.search(evidence) is not None


def page_in_windows(document, windows, evidence):
    """The page of `evidence` in the full PDF text, found through the window that exposed it.

    A window after the first usually starts mid-page, so its own text carries no page mark for
    what precedes its first break; the position has to be mapped back to the whole document.
    """
    for w in windows:
        at = w['text'].find(evidence)
        if at >= 0:
            return page_of(document, w['start'] + at)
    return page_of(document, document.find(evidence))


def page_of(document, evidence_at):
    """The page number a character offset in a PDF's readable text falls on, or None."""
    if evidence_at < 0:
        return None
    pages = [m for m in PAGE_MARK.finditer(document) if m.start() <= evidence_at]
    return int(pages[-1].group(1)) if pages else None


# One table cell alone on a line: a number, optionally with a short unit ('61.7', '87.6%', '-2,564 MW').
_CELL = re.compile(r'^' + _NUMBER + r'(?:[ \t]*[A-Za-z%]{1,4})?$')
# The small words that hold a sentence together; a table row has none of them.
_FUNCTION_WORDS = {'a', 'an', 'the', 'of', 'in', 'to', 'by', 'and', 'or', 'for', 'from', 'with', 'at', 'on', 'is', 'are',
                   'was', 'were', 'will', 'be', 'as', 'than', 'that', 'this', 'its', 'our', 'we', 'it', 'could', 'would', 'up'}


def _row(line):
    """Two or more numbers on a line with no function word: '2026 27,218 MW', 'Summer Peak (MW) 2036 222,106'."""
    tokens = line.split()
    numbers = sum(1 for t in tokens if re.fullmatch(_NUMBER + r'[A-Za-z%]{0,4}[.,;:]?', t))
    return numbers >= 2 and not any(t.strip('.,;:()').lower() in _FUNCTION_WORDS for t in tokens)


def looks_tabular(evidence):
    """Evidence drawn from a table or chart as pypdf flattens it, whose figures may have lost their headings.

    pypdf mostly emits one cell per line ('61.7' then '66.5'), label-year-value rows
    ('2026 27,218 MW') or runs of numbers ('2024 122 152 186'). Any of those in the quote holds
    the figure for review. Prose with several numbers keeps its function words and passes.
    """
    lines = [line.strip() for line in evidence.splitlines() if line.strip() and not PAGE_MARK.match(line.strip())]
    if len(lines) >= 2 and any(_CELL.match(line) for line in lines):
        return True
    return TABLE_ROW.search(evidence) is not None or any(_row(line) for line in lines)
