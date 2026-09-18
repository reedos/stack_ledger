"""The consumer-coverage screen, against headlines this crawler actually read.

Every case below is a real row from the coverage feed on 2026-09-18, the morning the owner asked
why the Latest page was leading with a DLSS mod. The keeps matter more than the drops: a screen
that quietly thins the models and applications layers is the failure this project has already made
once (see coverage_feed's module docstring), so the rescues are pinned here as tests.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import coverage_feed
import subject_gate


# (title, url) pairs an outlet published that are consumer coverage, not buildout coverage.
DROP = [
    ("AI developer vibe codes DLSS 5 onto Intel CPU's integrated graphics",
     'https://www.tomshardware.com/tech-industry/artificial-intelligence/ai-developer-vibe-codes-dlss-5-onto-intel-arc-140t-integrated-graphics'),
    ('Balatro fan claims they trained Google fruit fly brain simulation to beat the game',
     'https://www.tomshardware.com/tech-industry/artificial-intelligence/balatro-fan-claims-they-trained-google-fruit-fly-brain-simulation'),
    ('My 5 favorite Linux distros for AI', 'https://www.zdnet.com/innovation/ai-linux-distros-favorites/'),
    ('iOS 27 is finally here, with the new Siri AI beta', 'https://www.zdnet.com/business/ios-27-siri-ai-beta-how-to-try/'),
    ('AirPods 5 hands-on: I am glad both models have ANC', 'https://www.zdnet.com/business/airpods-5-hands-on-anc-lower-price/'),
    ('Your AirTag battery can be deadly', 'https://www.zdnet.com/home-and-office/airtag-battery-warning/'),
    ('The iPhone 17 and other older models just got a surprise $100 price hike',
     'https://www.zdnet.com/business/iphone-17-price-hike/'),
    ('The 2.5-hour AI-generated Odyssey movie is 2.5 hours too long',
     'https://www.theverge.com/entertainment/996499/ai-odyssey-movie-review'),
    ("Apple's iPhone 18 Pro adds variable camera aperture and a more powerful chip",
     'https://arstechnica.com/gadgets/2026/09/apples-iphone-18-pro-adds-variable-camera-aperture/'),
    ('Thermalright TR KG750 750W Power Supply Review',
     'https://www.tomshardware.com/pc-components/power-supplies/thermalright-tr-kg750-review'),
    ('We Tested DLSS Multi Frame Generation on RTX 40 Series GPUs',
     'https://www.tomshardware.com/pc-components/gpus/we-tested-dlss-multi-frame-generation'),
]

# Stories that mention a device, a deal or a film and are still about the buildout.
KEEP = [
    ("Apple A20 Pro powers iPhone 18 Pro, the company's first 2-nanometer smartphone chip",
     'https://www.tomshardware.com/tech-industry/apple-a20-pro-2nm'),
    ('Flex Pays $4.4B for EPC Power as AI Data Centers Push 800V DC',
     'https://www.datacenterdynamics.com/en/news/flex-epc-power/'),
    ('Film studio turned data center project gets approval in High Wycombe',
     'https://www.datacenterdynamics.com/en/news/film-studio-data-center-high-wycombe/'),
    ('Fusion power startups find new partners in the defense world',
     'https://techcrunch.com/2026/09/17/fusion-power-startups-defense/'),
    ('Why "Clean Is Cheap, Cheap Is Clean" Is Not Breaking Through',
     'https://heatmap.news/economy/clean-cheap-pricing'),
    ('"Offensively cheap": Solar power is looking up', 'https://arstechnica.com/gadgets/2026/09/solar-power-is-looking-up/'),
    ('Crusoe raises $3.9B to build massive data centers and small modular AI factories',
     'https://techcrunch.com/2026/09/16/crusoe-raises-3-9b/'),
    ('US chip fabs face massive 157,000 worker shortfall',
     'https://www.tomshardware.com/tech-industry/us-chip-fabs-worker-shortfall'),
    ('Apple eyes Nvidia NVLink to power its new custom M8 Ultra AI servers',
     'https://www.tomshardware.com/tech-industry/apple-nvlink-m8-ultra-ai-servers'),
    ('Huawei details AI accelerator roadmap, pulls in next-generation Ascend NPUs',
     'https://www.tomshardware.com/tech-industry/huawei-ascend-roadmap'),
    ('New York State recommends demanding AI data centers pay $1 million per megawatt',
     'https://www.tomshardware.com/tech-industry/new-york-data-center-megawatt'),
    ('Desktop Graphics Card Shipments Hit Four Year High of 12.5 Million',
     'https://www.tomshardware.com/tech-industry/gpu-shipments-four-year-high'),
]


class SubjectGate(unittest.TestCase):
    def test_consumer_coverage_from_an_outlet_is_off_thesis(self):
        for title, url in DROP:
            with self.subTest(title=title):
                self.assertIsNotNone(subject_gate.off_thesis(title, None, url, 'news'), title)

    def test_buildout_coverage_is_kept_however_it_is_worded(self):
        for title, url in KEEP:
            with self.subTest(title=title):
                self.assertIsNone(subject_gate.off_thesis(title, None, url, 'news'), title)

    def test_only_general_interest_outlets_are_screened(self):
        """A reviewed channel is on-thesis by construction; screening one is how the models and
        applications layers got thin the last time this project filtered on topic words."""
        title, url = DROP[0]
        for provenance in ('company-channel', 'independent-research', 'official', 'regulated-filing', 'analyst'):
            with self.subTest(provenance=provenance):
                self.assertIsNone(subject_gate.off_thesis(title, None, url, provenance))
        self.assertIsNotNone(subject_gate.off_thesis(title, None, url, 'social'))

    def test_the_url_alone_is_enough_before_a_fetch(self):
        """What the crawl gate sees: no title, no blurb, just the publisher's own slug."""
        self.assertIsNotNone(subject_gate.off_thesis(url=DROP[0][1], provenance='news'))
        self.assertIsNone(subject_gate.off_thesis(url=KEEP[6][1], provenance='news'))

    def test_a_summary_can_carry_the_signal_the_headline_hides(self):
        self.assertIsNotNone(subject_gate.off_thesis(
            'Intel Arc gets a neural rendering trick',
            "You won't be playing any games with it, but it might be fun to use with photo modes.",
            'https://www.tomshardware.com/tech-industry/artificial-intelligence/arc-neural-rendering', 'news'))


class CoverageFeedIntegration(unittest.TestCase):
    SOURCES = {'outlet': {'id': 'outlet', 'url': 'https://www.zdnet.com/rss/all/', 'publisher': 'ZDNet',
                          'provenance': 'news', 'layers': ['models'], 'index': True},
               'lab': {'id': 'lab', 'url': 'https://lab.example.com/blog', 'publisher': 'Lab',
                       'provenance': 'company-channel', 'layers': ['models']}}

    def document(self, source, url, title, summary=None):
        return {'source': source, 'url': url, 'title': title, 'summary': summary,
                'read_at': '2026-09-18T08:00:00+00:00', 'published': '2026-09-18'}

    def test_an_off_thesis_document_never_becomes_a_row(self):
        docs = [self.document('outlet', 'https://www.zdnet.com/business/airpods-5-hands-on-anc/', 'AirPods 5 hands-on'),
                self.document('outlet', 'https://www.zdnet.com/business/crusoe-data-center-megawatt/',
                              'Crusoe adds 300 megawatts of data center capacity')]
        rows, counts = merge_at(docs, self.SOURCES)
        self.assertEqual([r['title'] for r in rows], ['Crusoe adds 300 megawatts of data center capacity'])
        self.assertEqual(counts['added'], 1)
        self.assertTrue(any('consumer' in reason for reason in counts['dropped']), counts['dropped'])

    def test_a_company_channel_is_never_screened(self):
        docs = [self.document('lab', 'https://lab.example.com/blog/our-game-playing-agent', 'Our game playing agent')]
        rows, _ = merge_at(docs, self.SOURCES)
        self.assertEqual(len(rows), 1)

    def test_rows_already_on_the_feed_are_swept(self):
        existing = [{'url': 'https://www.zdnet.com/business/iphone-17-price-hike/', 'title': 'The iPhone 17 got a $100 price hike',
                     'summary': None, 'source': 'outlet', 'publisher': 'ZDNet', 'provenance': 'news',
                     'layers': ['models'], 'published': '2026-09-17', 'read_at': '2026-09-17T08:00:00+00:00'}]
        rows, counts = merge_at([], self.SOURCES, existing=existing)
        self.assertEqual(rows, [])
        self.assertEqual(counts['swept'], 1)


def merge_at(documents, sources, existing=None):
    from datetime import datetime, timezone
    return coverage_feed.merge(existing or [], documents, sources,
                               now=datetime(2026, 9, 18, 9, tzinfo=timezone.utc))


if __name__ == '__main__':
    unittest.main()
