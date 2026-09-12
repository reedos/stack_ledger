"""A layer whose project list looks thin says why, rather than leaving a reader to guess.

The delivery tracker maps physical delivery: every project carries a latitude, a longitude and a
documented site. Models holds two entries -- Apertus on Alps at CSCS, OLMo on LUMI -- because
those are the only model programs that publish where they trained. Frontier developers do not, so
they cannot be placed on a map without inventing a location.

Two entries with no explanation reads as "nobody looked". The note says what is actually true:
the list is short because of what is disclosed, not because of coverage.

Written after a verification pass on eight candidate programs (BLOOM, OpenGPT-X, Poro, GPT-SW3,
Fugaku-LLM, Falcon, SEA-LION) found zero that publish a readable, dated training locality --
including Falcon, which only appeared to name LUMI because "LUMI" is a substring of
"illuminating".
"""
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from validate import LAYERS, require
import validate_delivery


def delivery():
    return json.loads((ROOT/'research/delivery.json').read_text(encoding='utf-8'))


class ContentTests(unittest.TestCase):
    def setUp(self):
        self.d = delivery()
        self.notes = self.d['layer_notes']

    def test_models_carries_a_note(self):
        self.assertIn('models', self.notes)

    def test_the_note_explains_the_constraint_rather_than_apologising(self):
        note = self.notes['models']
        self.assertRegex(note, r'(?i)document(ed)? location|training site|training local')
        self.assertRegex(note, r'(?i)disclos')

    def test_the_note_names_the_two_programs_that_do_qualify(self):
        note = self.notes['models']
        for program in ('Apertus', 'OLMo'):
            with self.subTest(program=program):
                self.assertIn(program, note)

    def test_the_note_matches_the_project_count_it_describes(self):
        """If a third models project is ever added, this copy stops being true."""
        models = [p for p in self.d['projects'] if p['layer'] == 'models']
        self.assertEqual(len(models), 2, 'the models note describes exactly two programs')
        self.assertEqual({p['name'].split(' · ')[0] for p in models}, {'Apertus', 'OLMo'})


class ValidatorTests(unittest.TestCase):
    def setUp(self):
        self.d = delivery()

    def test_the_shape_accepts_layer_notes(self):
        validate_delivery.validate_files()      # must not raise

    def test_a_note_for_an_unknown_layer_is_refused(self):
        with self.assertRaises(ValueError):
            require('quantum' in LAYERS, 'Unknown layer note')

    def test_a_note_for_a_layer_with_no_projects_is_refused(self):
        """A note attached to an empty layer would render against nothing."""
        layers_with_projects = {p['layer'] for p in self.d['projects']}
        for layer in self.d['layer_notes']:
            with self.subTest(layer=layer):
                self.assertIn(layer, layers_with_projects)

    def test_every_noted_layer_is_a_real_layer(self):
        for layer in self.d['layer_notes']:
            with self.subTest(layer=layer):
                self.assertIn(layer, LAYERS)

    def test_the_published_mirror_matches_the_reviewed_copy(self):
        published = json.loads((ROOT/'site/data/delivery.json').read_text(encoding='utf-8'))
        self.assertEqual(published, self.d, 'validate refuses to publish while these differ')


class RenderTests(unittest.TestCase):
    """The note has to reach a reader, and only when a layer is actually selected."""

    def setUp(self):
        self.js = (ROOT/'site/assets/delivery.js').read_text(encoding='utf-8')

    def test_the_page_has_somewhere_to_put_it(self):
        self.assertIn('id="layer-note"', self.js)

    def test_it_renders_only_for_a_selected_layer(self):
        """On the unfiltered view the note would be describing a list it does not apply to."""
        self.assertIn("layer!=='all'&&(delivery.layer_notes||{})[layer]", self.js)

    def test_a_layer_with_no_note_renders_nothing(self):
        self.assertRegex(self.js, r"note\?`<aside[^`]*`:''")

    def test_the_note_text_is_escaped(self):
        self.assertIn('${esc(note)}', self.js)

    def test_the_published_script_matches_the_source_script(self):
        import hashlib
        digest = lambda t: hashlib.sha256(t.encode()).hexdigest()[:16]
        published = (ROOT/'docs/assets/delivery.js').read_text(encoding='utf-8')
        self.assertEqual(digest(self.js), digest(published),
                         'docs/assets/delivery.js is what the site serves; run scripts/build.py')


if __name__ == '__main__':
    unittest.main()
