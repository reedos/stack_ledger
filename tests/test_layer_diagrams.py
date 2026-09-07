import json
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from layer_diagrams import DIAGRAMS,render_layer_diagram

class LayerDiagramTests(unittest.TestCase):
    def test_all_layers_have_sourced_navigable_explanations(self):
        sources=json.loads((ROOT/'site/data/ledger.json').read_text(encoding='utf-8'))['sources']
        self.assertEqual(set(DIAGRAMS),{'energy','chips','infrastructure','models','applications'})
        for layer,d in DIAGRAMS.items():
            html=render_layer_diagram(layer,sources)
            for i in range(1,len(d['nodes'])+1):
                self.assertIn(f'href="#diagram-{layer}-{i}"',html)
                self.assertIn(f'id="diagram-{layer}-{i}"',html)
            self.assertIn('not a site plan',html)
            self.assertIn('Technical context:',html)
