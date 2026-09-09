"""Bounded, traceable model context and exact numeric tokens (no inference)."""
import hashlib
import re


def numeric_tokens(text):
    # A full stop may terminate a number. Do not match inside identifiers,
    # malformed grouped numbers, decimals or dotted versions/IP addresses.
    pattern = r'(?<![\w.,])-?\d+(?:,\d{3})*(?:\.\d+)?(?!\w|[.,]\d)'
    return re.findall(pattern, text)


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


def contains_evidence(windows, quote):
    normalized = ' '.join(quote.split())
    return bool(normalized) and any(normalized in ' '.join(w['text'].split()) for w in windows)


def coverage(document, windows):
    exposed = sum(w['end']-w['start'] for w in windows)
    return {'document_characters':len(document),'exposed_characters':exposed,
            'complete':exposed == len(document),
            'ranges':[[w['start'],w['end']] for w in windows],
            'selection':'opening, tail and question-relevant sections; exposure is not comprehension',
            'document_sha256':hashlib.sha256(document.encode('utf-8')).hexdigest()}


def implementation_hash():
    from pathlib import Path
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
