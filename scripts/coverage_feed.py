"""What the crawler read, as a dated feed. A coverage row claims nothing except that a page exists.

The ledger's note and observation lanes ask the model whether a document contains a concrete,
evidenced development. Measured over a 5-hour session on 2026-09-13, that question rejected 219 of
294 documents as "document outside scope" and let 4 through. The bar is right for a record of
verified figures and wrong as the only route onto the site: the owner wants the latest of
everything in this space in one place, with lower-grade material included and labelled rather than
discarded.

So this is a second lane with a much smaller promise. A row says: this page exists, this source
published it, here is when we read it, and here is the reviewed provenance of whoever published
it. No extraction, no model call, no claim about what the page says. Trust is expressed the same
way it is everywhere else on the site -- the provenance label and its grade -- so a reader judges
a headline by who wrote it.

Relevance comes from the registry, not from words in a URL. Every document reaches us because a
reviewed source or one of its section indexes led us to it, so it is on-thesis by construction.
The filter here is about SHAPE, not subject: an index page, a section listing, a feed endpoint and
a PDF are not articles. Filtering by topic words instead was measured on the same session and cost
the models and applications layers most -- 10% of their documents passed, against 17-29% for
energy, chips and infrastructure -- because the topic vocabulary describes physical plant and
those layers are software. That is the same physical-buildout assumption that keeps those two
layers thin everywhere else in this project.
"""
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

RETENTION_DAYS = 90
MAX_ROWS = 3000
MAX_TITLE = 300

ROW_FIELDS = {'url', 'title', 'source', 'publisher', 'provenance', 'layers', 'published', 'read_at'}
NON_ARTICLE_SUFFIX = re.compile(r'(?i)\.(pdf|xml|json|csv|zip|rss|atom)$')
FEED_ENDPOINT = re.compile(r'(?i)/(feed|rss|atom|index\.xml)$')
MIN_SLUG = 12          # "/news/" or "/blog" is a section; a real article slug is longer
MIN_DEPTH = 2          # host/<section>/<slug>


def article(url, index_urls):
    """(True, '') when the URL looks like an article, else (False, why).

    The reason is kept because a silent filter is how a coverage feed quietly stops covering
    something. Callers record the counts.
    """
    if not isinstance(url, str) or not url.startswith('https://'):
        return False, 'not a public https URL'
    path = urlparse(url).path.rstrip('/')
    if url.rstrip('/') in index_urls:
        return False, 'the index page itself'
    if NON_ARTICLE_SUFFIX.search(path):
        return False, 'not an HTML article'
    if FEED_ENDPOINT.search(path):
        return False, 'a feed endpoint'
    if path.count('/') < MIN_DEPTH or len(path.rsplit('/', 1)[-1]) < MIN_SLUG:
        return False, 'a section or nav page, not an article'
    return True, ''


# A slug that carries no meaning once un-hyphenated: "default.aspx" and "index.htm" are the
# server's filename, not a headline, and a row titled that is noise a reader has to skip past.
MEANINGLESS_SLUG = re.compile(r'(?i)^(default|index|home|main|page|article|story|view|news|release|\d+)$')


def clean_title(value, url):
    """A readable headline, or None when the page gives us nothing a reader could scan.

    Publishers suffix the site name -- "Introducing Grok 4.6 | SpaceXAI",
    "Introducing Claude Opus 5 \\ Anthropic". The suffix is dropped only when what remains is
    still substantial, so a short title is never truncated to nothing.

    Returning None matters. Seeding this feed from retained receipts on 2026-09-13 -- receipts
    that predate the title capture -- produced 633 rows of which 98% fell back to the URL slug
    and 69 were titled things like "default.aspx" and "empsit 09042026.htm". A row whose headline
    is a filename is worse than no row: this feed exists to be scanned.
    """
    text = re.sub(r'\s+', ' ', str(value or '')).strip()
    for separator in ('|', '\\', ' - ', ' — ', ' · '):
        if separator in text:
            head = text.split(separator)[0].strip()
            if len(head) >= 20:
                text = head
    if len(text) >= 8:
        return text[:MAX_TITLE]
    slug = urlparse(url).path.rstrip('/').rsplit('/', 1)[-1]
    slug = re.sub(r'\.[a-z0-9]{2,5}$', '', slug, flags=re.I)      # a file extension is not a word
    words = re.sub(r'[-_%+]+', ' ', slug).strip()
    if len(words) < 12 or MEANINGLESS_SLUG.match(words) or not re.search(r'[a-z]{3}', words, re.I):
        return None
    return words[:MAX_TITLE]


def row_for(document, source):
    """One coverage row from a fetched document and the registered source it came from."""
    return {'url': document['url'],
            'title': clean_title(document.get('title'), document['url']),
            'source': source['id'],
            'publisher': source.get('publisher', ''),
            'provenance': source.get('provenance', 'social'),
            'layers': list(source.get('layers') or []),
            'published': document.get('published') or source.get('published'),
            'read_at': document.get('read_at')}


def sort_key(row):
    """Newest first on an effective date: the stated publication date, else the day we read it.

    Sorting undated pages last would bury them: plenty of company posts state no date in their
    markup, and those are the frontier-lab announcements this lane exists to surface. Treating
    "first read today" as the date is a fallback, not a claim -- the page shows "read <date>"
    rather than a publication date for those rows, so a reader can tell which they are looking
    at. read_at also breaks ties, so the order is stable between builds.
    """
    read_at = str(row.get('read_at') or '')
    return (str(row.get('published') or read_at[:10]), read_at)


def merge(existing, documents, sources, now=None):
    """Fold this run's documents into the feed. Returns (rows, counts).

    Deduplicated by URL with the newer read winning, so a page re-read every night occupies one
    row and keeps its first publication date. Trimmed by age first and then by count, because the
    cap is a file-size guard and the window is the editorial promise.
    """
    now = now or datetime.now(timezone.utc)
    index_urls = {s['url'].rstrip('/') for s in sources.values() if s.get('index')}
    counts = {'considered': 0, 'added': 0, 'refreshed': 0}
    dropped = {}
    by_url = {row['url']: dict(row) for row in existing}
    for document in documents:
        counts['considered'] += 1
        source = sources.get(document.get('source'))
        if source is None:
            dropped['source not registered'] = dropped.get('source not registered', 0) + 1
            continue
        keep, why = article(document['url'], index_urls)
        if not keep:
            dropped[why] = dropped.get(why, 0) + 1
            continue
        fresh = row_for(document, source)
        if fresh['title'] is None:
            dropped['no readable headline'] = dropped.get('no readable headline', 0) + 1
            continue
        seen = by_url.get(fresh['url'])
        if seen is None:
            by_url[fresh['url']] = fresh
            counts['added'] += 1
        else:
            # Keep the earliest publication date we ever saw; refresh the rest.
            fresh['published'] = seen.get('published') or fresh['published']
            if str(fresh.get('read_at') or '') >= str(seen.get('read_at') or ''):
                by_url[fresh['url']] = fresh
                counts['refreshed'] += 1
    cutoff = (now - timedelta(days=RETENTION_DAYS)).isoformat()
    rows = [r for r in by_url.values() if str(r.get('read_at') or '') >= cutoff]
    counts['expired'] = len(by_url) - len(rows)
    rows.sort(key=sort_key, reverse=True)
    counts['over_cap'] = max(0, len(rows) - MAX_ROWS)
    counts['dropped'] = dropped
    counts['rows'] = min(len(rows), MAX_ROWS)
    return rows[:MAX_ROWS], counts


def validate_rows(rows, sources):
    """Refuse a feed that could mislead. Imported by validate.py; raises ValueError on the first
    problem, like every other validator here.

    A coverage row makes a small claim, so the checks are about identity and labelling rather than
    evidence: a real public URL, a registered source, the provenance that source actually carries
    (never a value chosen here), and no duplicate URLs. The grade a reader sees is derived from
    provenance in the page, so a forged provenance is the one way a row could overstate itself.
    """
    from validate import require, text
    seen = set()
    approved = {s['id']: s for s in sources}
    for row in rows:
        require(isinstance(row, dict) and set(row) == ROW_FIELDS, 'Unexpected coverage row fields')
        require(row['url'].startswith('https://') and ' ' not in row['url'], 'Coverage row needs a public HTTPS URL')
        require(row['url'] not in seen, 'Duplicate coverage URL')
        seen.add(row['url'])
        source = approved.get(row['source'])
        require(source is not None, 'Coverage row from an unregistered source')
        require(row['provenance'] == source.get('provenance'), 'Coverage provenance does not match its registered source')
        require(row['publisher'] == source.get('publisher', ''), 'Coverage publisher does not match its registered source')
        require(list(row['layers']) == list(source.get('layers') or []), 'Coverage layers do not match its registered source')
        text(row['title'], MAX_TITLE)
        for field in ('published', 'read_at'):
            if row[field] is not None:
                require(isinstance(row[field], str) and len(row[field]) <= 40, 'Invalid coverage %s' % field)
    require(len(rows) <= MAX_ROWS, 'Coverage feed above its row cap')
    return len(rows)
