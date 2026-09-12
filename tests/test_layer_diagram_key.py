"""A layer diagram's key names the line kinds that diagram actually draws, and no others.

Owner report, 2026-09-12: the key was hard-coded to all four kinds on every layer. The chips
diagram draws one kind and advertised four; the applications diagram offered "Power / energy" and
"Heat removal" swatches for lines that appear nowhere in it. A legend entry for an absent line is
a reader looking for something that is not there.
"""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import layer_diagrams as ld

KINDS = [k for k, _ in ld.KEY_LABELS]
LABELS = dict(ld.KEY_LABELS)


def key_html(markup):
    m = re.search(r'<div class="diagram-key">(.*?)</div>', markup, re.S)
    assert m, 'the diagram has no key at all'
    return m.group(1)


def kinds_in_key(markup):
    return re.findall(r'<span class="key-([a-z]+)">', key_html(markup))


def sources():
    import json
    return json.loads((ROOT/'site/data/ledger.json').read_text(encoding='utf-8'))['sources']


class KeyMatchesDiagramTests(unittest.TestCase):
    def setUp(self):
        self.sources = sources()

    def rendered(self, layer):
        return ld.render_layer_diagram(layer, self.sources)

    def test_every_layer_lists_exactly_the_kinds_it_draws(self):
        for layer, spec in ld.DIAGRAMS.items():
            drawn = {k for _, _, k in spec['edges']}
            with self.subTest(layer=layer):
                self.assertEqual(set(kinds_in_key(self.rendered(layer))), drawn)

    def test_a_single_kind_layer_shows_a_single_entry(self):
        """chips draws only data, energy only power -- each showed four entries."""
        for layer, kind in [('chips', 'data'), ('energy', 'power')]:
            with self.subTest(layer=layer):
                self.assertEqual(kinds_in_key(self.rendered(layer)), [kind])

    def test_applications_no_longer_offers_power_or_cooling(self):
        """The diagram in the owner's screenshot: data and feedback, nothing else."""
        html = self.rendered('applications')
        self.assertEqual(kinds_in_key(html), ['data', 'feedback'])
        for absent in ('Power / energy', 'Heat removal'):
            self.assertNotIn(absent, key_html(html))

    def test_the_key_keeps_one_order_across_layers(self):
        """A kind must not move position between layers; that is what makes a key learnable."""
        for layer in ld.DIAGRAMS:
            with self.subTest(layer=layer):
                shown = kinds_in_key(self.rendered(layer))
                self.assertEqual(shown, [k for k in KINDS if k in shown])

    def test_each_entry_carries_its_reader_facing_label(self):
        for layer in ld.DIAGRAMS:
            html = key_html(self.rendered(layer))
            for kind in kinds_in_key(self.rendered(layer)):
                with self.subTest(layer=layer, kind=kind):
                    self.assertIn(f'<span class="key-{kind}">{LABELS[kind]}</span>', html)


class VocabularyTests(unittest.TestCase):
    def test_every_edge_kind_has_a_label(self):
        """An unlabelled kind would draw a line the key cannot name."""
        drawn = {k for spec in ld.DIAGRAMS.values() for _, _, k in spec['edges']}
        self.assertEqual(drawn - set(KINDS), set())

    def test_every_drawn_kind_has_a_swatch_colour(self):
        """The key's swatch is CSS; a kind with no rule renders an invisible swatch."""
        css = (ROOT/'site/assets/diagrams.css').read_text(encoding='utf-8')
        drawn = {k for spec in ld.DIAGRAMS.values() for _, _, k in spec['edges']}
        for kind in sorted(drawn):
            with self.subTest(kind=kind):
                self.assertRegex(css, r'\.key-%s(:before)?\s*[,{]' % kind)

    def test_the_published_pages_match_what_the_renderer_produces(self):
        """docs/ is what the site serves; a stale build would keep showing four entries."""
        for layer in ld.DIAGRAMS:
            page = ROOT/'docs'/layer/'index.html'
            if not page.exists():
                self.skipTest(f'{layer} page not built')
            with self.subTest(layer=layer):
                self.assertEqual(kinds_in_key(page.read_text(encoding='utf-8')),
                                 kinds_in_key(ld.render_layer_diagram(layer, sources())))


if __name__ == '__main__':
    unittest.main()
