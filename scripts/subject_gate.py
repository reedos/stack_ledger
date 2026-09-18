"""Consumer-gadget coverage does not belong in a record of the AI buildout.

A general-interest outlet files its AI-buildout reporting and its phone reviews under the same
section. On 2026-09-18 the Latest page led with "AI developer vibe codes DLSS 5 onto Intel CPU's
integrated graphics", whose own blurb says you won't be playing games with it "but it might be fun
to use with photo modes". It reached the crawler legitimately: Tom's Hardware published it under
/tech-industry/artificial-intelligence/, so the registry's path prefix and topic word both matched.
A topic word in a URL says what desk filed the story, not whether it is about the buildout.

So the screen here reads the headline, the blurb and the section, and it is deliberately narrow:

- It runs ONLY for sources whose reviewed provenance is news or social -- the general-interest
  outlets. A company channel, a research institute, a regulator and a filing are never screened.
  This is what keeps the failure recorded in coverage_feed's docstring from repeating: the models
  and applications layers are thin because their vocabulary is software, and their sources are
  company and research channels, which this never touches.
- It is two-sided. A consumer signal alone does not drop a story; the story must also carry no
  buildout signal. "Apple A20 Pro powers iPhone 18 Pro, the company's first 2-nanometer chip"
  keeps its row on `nanometer` -- a node milestone is the chips layer whatever device it ships in.
- Every drop names its reason, and callers count them. A silent filter is how a feed quietly stops
  covering something.

Measured against the 849 rows on the feed the morning of 2026-09-18: 96 dropped, of which 94 are
phone, headphone, gaming, streaming or how-to stories. See tests/test_subject_gate.py, whose cases
are real headlines this crawler actually read.
"""
import re
from urllib.parse import urlparse

SCREENED_PROVENANCE = {'news', 'social'}


def _words(*values):
    """Lowercase word stream of everything we know about a page, URL slug included."""
    text = ' '.join(str(v or '') for v in values)
    return ' ' + ' '.join(w for w in re.split(r'[^a-z0-9]+', text.lower()) if w) + ' '


def _any(stream, phrases):
    return next((p for p in phrases if f' {p} ' in stream), None)


# Consumer hardware, gaming, entertainment and service journalism. Every entry is matched as whole
# words, so `mod` does not fire on `model`, `game` does not fire on `gamechanger`, and `tv` does
# not fire inside a product code.
CONSUMER = [
    # devices a person buys for themselves
    'iphone', 'iphones', 'ipad', 'ipads', 'airpods', 'airtag', 'airtags', 'apple watch', 'macbook',
    'smartphone', 'smartphones', 'phone', 'phones', 'handset', 'handsets', 'tablet', 'tablets',
    'laptop', 'laptops', 'headphone', 'headphones', 'earbuds', 'smartwatch', 'smartwatches',
    'foldable', 'foldables', 'wearable', 'wearables', 'ios', 'ipados', 'android', 'macos',
    # gaming
    'game', 'games', 'gaming', 'gamer', 'gamers', 'dlss', 'fsr', 'ray tracing', 'frame generation',
    'geforce', 'playstation', 'ps5', 'xbox', 'nintendo', 'steam deck', 'esports', 'speedrun',
    'mod', 'mods', 'crypto mining', 'mining rig',
    # service journalism and commerce
    'hands on', 'unboxing', 'buying guide', 'we tested', 'i tested', 'i tried', 'i recommend',
    'price hike', 'price cut', 'best laptops', 'best phones',
]

# Entertainment and service journalism are recognised by shape rather than by a word list, because
# the words themselves are ordinary business vocabulary. Measured on the 2026-09-18 feed: 'deal'
# dropped a $4.4B power-equipment acquisition and a fusion-startup story, 'favorite' dropped a
# Heatmap piece on clean-energy pricing, and 'film' dropped a data-centre conversion of a film
# studio. A headline that OPENS "How to ..." is a guide; one that merely contains the phrase is
# usually a company explaining how to do something real.
SHAPES = [
    (re.compile(r'^\s*how to\b', re.I), 'a how-to guide'),
    (re.compile(r'\bmy \d*\s*favou?rite\b', re.I), 'a personal favourites list'),
    (re.compile(r'\b(?:best|top) \d+\b', re.I), 'a ranked product list'),
    (re.compile(r'\bhands[- ]on\b', re.I), 'a hands-on review'),
]

# A node size is the chips layer whatever device the part ships in: "2nm", "2 nm", "3nm chip".
NODE = re.compile(r'\b\d+\s?nm\b', re.I)

# The section a publisher files a story under, when that section is its whole subject.
CONSUMER_SECTIONS = ('/gadgets/', '/pc-components/', '/entertainment/', '/gaming/', '/games/',
                     '/deals/', '/reviews/', '/how-to/', '/apple/', '/culture/', '/laptops/',
                     '/monitors/', '/peripherals/', '/phones/')

# What the buildout sounds like. Any one of these keeps a row that a consumer word would drop:
# the story is about plant, silicon, power, money or supply, whatever device it mentions.
BUILDOUT = [
    'data center', 'data centre', 'datacenter', 'datacentre', 'data centers', 'data centres',
    'fab', 'fabs', 'foundry', 'foundries', 'wafer', 'wafers', 'nanometer', 'nanometre', 'nm',
    'lithography', 'euv', 'hbm', 'packaging', 'cowos', 'tsmc', 'node',
    'megawatt', 'megawatts', 'gigawatt', 'gigawatts', 'mw', 'gw', 'terawatt', 'twh',
    'grid', 'substation', 'transformer', 'reactor', 'nuclear', 'turbine', 'power plant',
    'capex', 'billion', 'trillion', 'funding', 'raises', 'raised', 'investment', 'acquisition',
    'supply chain', 'export controls', 'export control', 'tariff', 'tariffs', 'shipment',
    'shipments', 'roadmap', 'capacity', 'factory', 'plant', 'cluster', 'clusters',
    'training run', 'supercomputer', 'server', 'servers', 'rack', 'racks', 'inference',
    'solar', 'renewable', 'renewables', 'electricity', 'utility', 'interconnection',
]


def screened(provenance):
    """Only a general-interest outlet is screened; a reviewed channel is taken as on-thesis."""
    return str(provenance or '') in SCREENED_PROVENANCE


def off_thesis(title=None, summary=None, url=None, provenance='news'):
    """The reason this page is consumer coverage rather than buildout coverage, else None.

    Pass whatever is known. Before a fetch that is the URL alone, which still carries the section
    and the publisher's slug; afterwards it is the headline and the publisher's own blurb.
    """
    if not screened(provenance):
        return None
    path = urlparse(str(url or '')).path.lower()
    stream = _words(title, summary, path)
    headline = str(title or '')
    if _any(stream, BUILDOUT) or NODE.search(headline) or NODE.search(path.replace('-', ' ')):
        return None
    section = next((s for s in CONSUMER_SECTIONS if s in path), None)
    if section:
        return 'consumer section ' + section.strip('/')
    hit = _any(stream, CONSUMER)
    if hit:
        return 'consumer subject: ' + hit
    return next((why for pattern, why in SHAPES if pattern.search(headline)), None)
