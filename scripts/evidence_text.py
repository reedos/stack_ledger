"""Bounded, traceable model context and exact numeric tokens (no inference)."""
import difflib
import hashlib
import re
import unicodedata


def numeric_tokens(text):
    # A full stop may terminate a number. Do not match inside identifiers such as
    # H100, malformed grouped numbers, decimals or dotted versions/IP addresses.
    # A unit or scale letter glued after the number ($2B, 500MW, 65k) is allowed:
    # the token is the number itself, and no scaling is ever inferred from the letter.
    pattern = r'(?<![\w.,])-?\d+(?:,\d{3})*(?:\.\d+)?(?!\d|[.,]\d)'
    return re.findall(pattern, text)


# Typographic variants the model routinely "cleans up" when copying evidence.
_FOLD = {ord(c): r for chars, r in [
    ('‘’‚‛′´`', "'"),   # curly and prime single quotes, acute, backtick
    ('“”„‟″«»', '"'),   # curly and prime double quotes, guillemets
    ('‐‑‒–—―−', '-'),   # hyphens, dashes, minus
    ('…', '...'),
] for c in chars}
# Zero-width and soft characters that survive NFKC but never appear in a model quote.
_STRIP = {ord(c): None for c in '​‌‍⁠﻿­'}


def _fold_map(text):
    """Fold text for comparison and keep a map from folded index to original index."""
    out = []; index = []
    pending_space = False
    for i, ch in enumerate(text):
        folded = unicodedata.normalize('NFKC', ch).translate(_STRIP).translate(_FOLD)
        for f in folded:
            if f.isspace():
                pending_space = True
                continue
            if pending_space and out:
                out.append(' '); index.append(i)
            pending_space = False
            out.append(f); index.append(i)
    return ''.join(out), index


def fold(text):
    return _fold_map(text)[0]


def locate(document, quote, ratio=0.92):
    """Return the document's own contiguous text for a model quote, or None.

    Exact match after folding typographic variants and whitespace is preferred.
    Otherwise one contiguous region may be accepted when its matching blocks cover
    the quote at or above the ratio; a quote stitched from two passages fails because
    no single region resembles it. The returned string is always a slice of the document.
    """
    folded_doc, index = _fold_map(document)
    folded_quote = fold(quote)
    if not folded_quote or not folded_doc:
        return None
    start = folded_doc.find(folded_quote)
    end = start + len(folded_quote)
    if start < 0:
        matcher = difflib.SequenceMatcher(None, folded_doc, folded_quote, autojunk=False)
        anchor = matcher.find_longest_match(0, len(folded_doc), 0, len(folded_quote))
        if anchor.size < min(40, len(folded_quote) // 2):
            return None
        lo = max(0, anchor.a - anchor.b - 16)
        hi = min(len(folded_doc), lo + int(len(folded_quote) * 1.3) + 32)
        region = folded_doc[lo:hi]
        blocks = [b for b in difflib.SequenceMatcher(None, region, folded_quote, autojunk=False).get_matching_blocks() if b.size >= 4]
        if not blocks:
            return None
        start = lo + blocks[0].a
        end = lo + blocks[-1].a + blocks[-1].size
        matched = sum(b.size for b in blocks)
        if 2 * matched / ((end - start) + len(folded_quote)) < ratio:
            return None
    return document[index[start]:index[end - 1] + 1]


def select_windows(document, question, budget):
    """First section plus relevance-ranked sections and a tail, within one call.

    Windows are original contiguous slices, never a fabricated joined quote.
    Coverage describes characters exposed to the model, not comprehension.
    """
    if len(document) <= budget:
        ranges = [(0, len(document))]
    else:
        size = min(4000, budget // 4)
        chunks = []
        start = 0
        while start < len(document):
            end = min(start + size, len(document))
            if end < len(document):
                boundary = document.rfind('\n', start + size // 2, end)
                if boundary > start: end = boundary + 1
            chunks.append((start, end))
            start = end
        ignored = {'which','their','about','there','these','those','with','from','that','this','have','more','than','into','what'}
        terms = set(re.findall(r'\b[a-z]{4,}\b', question.lower())) - ignored
        def score(bounds):
            text = document[bounds[0]:bounds[1]].lower()
            return len(terms & set(re.findall(r'\b[a-z]{4,}\b', text)))
        chosen = [chunks[0], chunks[-1]]
        used = sum(b-a for a,b in chosen)
        for bounds in sorted(chunks[1:-1], key=lambda b: (-score(b), b[0])):
            if used + bounds[1]-bounds[0] <= budget:
                chosen.append(bounds); used += bounds[1]-bounds[0]
        ranges = sorted(chosen)
    # Merge adjacent ranges so evidence may span a genuine section boundary.
    merged = []
    for start,end in ranges:
        if merged and merged[-1][1] == start: merged[-1] = (merged[-1][0],end)
        else: merged.append((start,end))
    return [{'start':a,'end':b,'text':document[a:b]} for a,b in merged]


def context_text(windows):
    return '\n\n[OMITTED SOURCE TEXT — NOT CONTIGUOUS]\n\n'.join(w['text'] for w in windows)


def locate_in_windows(windows, quote):
    """The document's own text for a quote found inside one exposed window, else None."""
    if not isinstance(quote, str) or not quote.strip():
        return None
    for w in windows:
        found = locate(w['text'], quote)
        if found is not None:
            return found
    return None


def contains_evidence(windows, quote):
    return locate_in_windows(windows, quote) is not None


def focus_text(windows, evidence, margin=800):
    """The exposed text surrounding one located evidence passage, for a reviewer pass."""
    for w in windows:
        i = w['text'].find(evidence)
        if i >= 0:
            return w['text'][max(0, i - margin):i + len(evidence) + margin]
    return context_text(windows)


def coverage(document, windows):
    exposed = sum(w['end']-w['start'] for w in windows)
    return {'document_characters':len(document),'exposed_characters':exposed,
            'complete':exposed == len(document),
            'ranges':[[w['start'],w['end']] for w in windows],
            'selection':'opening, tail and question-relevant sections; exposure is not comprehension',
            'document_sha256':hashlib.sha256(document.encode('utf-8')).hexdigest()}


_SENTENCE_BREAK = re.compile(r'(?<=[.!?])\s+|\n+')


def shrink_to_numbers(document, located, numbers, cap):
    """The shortest run of whole sentences inside `located` that still contains every
    number in `numbers` and fits within `cap` characters, or None if no such run exists.

    Sentences split on '.', '!' or '?' followed by whitespace, or a newline. The result
    is always a contiguous substring of `located` (and so of `document`) -- never
    rewritten, joined or reordered. A candidate too long to shrink this way is
    quarantined instead of accepted with truncated or fabricated evidence.
    """
    if not isinstance(located, str) or located not in document:
        return None
    if len(located) <= cap:
        return located
    targets = []
    for n in numbers:
        try:
            targets.append(float(str(n).replace(',', '')))
        except (TypeError, ValueError):
            continue
    def supports(text):
        values = [float(t.replace(',', '')) for t in numeric_tokens(text)]
        return all(any(v == target for v in values) for target in targets)
    spans = []
    start = 0
    for m in _SENTENCE_BREAK.finditer(located):
        spans.append((start, m.end())); start = m.end()
    if start < len(located):
        spans.append((start, len(located)))
    spans = [(a, b) for a, b in spans if b > a]
    best = None
    for i in range(len(spans)):
        for j in range(i, len(spans)):
            piece = located[spans[i][0]:spans[j][1]]
            if len(piece) > cap:
                break
            if supports(piece) and (best is None or len(piece) < len(best)):
                best = piece
                break
    return best


def implementation_hash():
    from pathlib import Path
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
