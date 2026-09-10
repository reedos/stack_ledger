import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import registry_lint as rl


def registry(sources,collection):
    return {'sources':sources,'discovery_keywords':[],'region_books':{},'collection':collection}


class DatedOneOffTests(unittest.TestCase):
    """Deliverable 5: id pattern AND index:false AND a fixed-document URL path."""
    def test_matches_id_pattern_index_and_document_path(self):
        sources=[
            {'id':'iea-2026','url':'https://iea.org/reports/key-questions','layers':['energy']},
            {'id':'metr-horizons-2026','url':'https://metr.org/time-horizons/','layers':['models']},  # rolling page, no document path
            {'id':'quarterly-feed-2026','url':'https://x.example/press-release/q1-2026','layers':['chips'],'index':True},  # a feed
            {'id':'no-year-here','url':'https://x.example/press-release/launch','layers':['chips']},  # id has no dated pattern
        ]
        collection={'iea-2026':{'cadence':'daily'},'metr-horizons-2026':{'cadence':'daily'},
                    'quarterly-feed-2026':{'cadence':'daily'},'no-year-here':{'cadence':'daily'}}
        self.assertEqual(rl.dated_one_offs(registry(sources,collection)),['iea-2026'])
    def test_already_manual_is_not_relisted(self):
        sources=[{'id':'iea-2026','url':'https://iea.org/reports/key-questions','layers':['energy']}]
        collection={'iea-2026':{'cadence':'manual'}}
        self.assertEqual(rl.dated_one_offs(registry(sources,collection)),[])


class RetireDatedCommandTests(unittest.TestCase):
    def test_dry_run_prints_and_never_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)
            reg=registry([{'id':'iea-2026','url':'https://iea.org/reports/key-questions','layers':['energy']}],
                          {'iea-2026':{'cadence':'daily'}})
            (path/'research').mkdir();(path/'research/sources.json').write_text(json.dumps(reg),encoding='utf-8')
            original=(path/'research/sources.json').read_bytes()
            with patch.object(rl,'ROOT',path):
                self.assertEqual(rl.main(['--retire-dated']),0)
            self.assertEqual((path/'research/sources.json').read_bytes(),original)
    def test_apply_writes_only_cadence(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)
            reg=registry([{'id':'iea-2026','url':'https://iea.org/reports/key-questions','layers':['energy']},
                          {'id':'metr-horizons-2026','url':'https://metr.org/time-horizons/','layers':['models']}],
                          {'iea-2026':{'cadence':'daily','rank':1,'topics':['x']},
                           'metr-horizons-2026':{'cadence':'daily','rank':2,'topics':['y']}})
            (path/'research').mkdir();(path/'research/sources.json').write_text(json.dumps(reg),encoding='utf-8')
            with patch.object(rl,'ROOT',path):
                self.assertEqual(rl.main(['--retire-dated','--apply']),0)
            written=json.loads((path/'research/sources.json').read_text(encoding='utf-8'))
            self.assertEqual(written['collection']['iea-2026']['cadence'],'manual')
            self.assertEqual(written['collection']['iea-2026']['rank'],1)
            self.assertEqual(written['collection']['iea-2026']['topics'],['x'])
            # The non-matching source (no fixed-document path) is untouched.
            self.assertEqual(written['collection']['metr-horizons-2026']['cadence'],'daily')
    def test_real_registry_selection_is_index_false_and_not_already_manual(self):
        real=json.loads((ROOT/'research/sources.json').read_text(encoding='utf-8'))
        ids=rl.dated_one_offs(real)
        by_id={s['id']:s for s in real['sources']}
        self.assertGreater(len(ids),0)
        for sid in ids:
            self.assertFalse(by_id[sid].get('index'))
            self.assertNotEqual(real['collection'][sid]['cadence'],'manual')


if __name__=='__main__':unittest.main()
