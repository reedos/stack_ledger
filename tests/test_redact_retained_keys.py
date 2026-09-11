import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import redact_retained_keys as rr

# Shaped like a registered EIA key (40 alphanumerics) but not one; no test ever holds a real key.
FAKE='fakeEIAkeyFAKEfakeFAKE0000000000000000ab'


def tree(d):
    """A root shaped like the real one on 2026-09-11: retained EIA snapshots and a nightly receipt
    echoing the key back, the vault itself, one clean snapshot, and one repository file that
    should never have held a key at all."""
    root=Path(d)
    (root/'.local/eia').mkdir(parents=True)
    (root/'.local/nightly/2026-09-11').mkdir(parents=True)
    (root/'research').mkdir()
    (root/'.local/api-keys.json').write_text(json.dumps({'eia':FAKE,'short':'x'}),encoding='utf-8')
    (root/'.local/eia/net-generation-5069dfaaa115.json').write_text(
        json.dumps({'request':{'params':{'api_key':FAKE}},'response':{'data':[{'period':'2026-01'}]}}),encoding='utf-8')
    (root/'.local/eia/capacity-additions-5a6f2c439a44.json').write_text(
        json.dumps({'request':{'params':{'api_key':FAKE}}}),encoding='utf-8')
    (root/'.local/eia/clean-0000.json').write_text(json.dumps({'response':{'data':[]}}),encoding='utf-8')
    (root/'.local/nightly/2026-09-11/importers.json').write_text(
        json.dumps({'stage':'importers','url':f'https://api.eia.gov/v2/steo/data/?api_key={FAKE}'}),encoding='utf-8')
    (root/'research/api-access.json').write_text(json.dumps({'hosts':{'api.eia.gov':{'key':FAKE}}}),encoding='utf-8')
    return root


class RedactRetainedKeysTests(unittest.TestCase):
    def test_reports_every_file_holding_a_key_without_printing_the_key(self):
        with tempfile.TemporaryDirectory() as d:
            root=tree(d);lines=[]
            result=rr.run(root,apply=False,out=lines.append)
            named={p.as_posix() for p in result['files']}
            self.assertEqual(named,{'.local/eia/net-generation-5069dfaaa115.json',
                                     '.local/eia/capacity-additions-5a6f2c439a44.json',
                                     '.local/nightly/2026-09-11/importers.json'})
            self.assertEqual([p.as_posix() for p in result['outside']],['research/api-access.json'])
            self.assertEqual(result['redacted'],0)
            self.assertFalse(any(FAKE in l for l in lines),'the report printed the key it is meant to hide')
            self.assertTrue(any('Dry run' in l for l in lines))

    def test_apply_clears_the_key_from_retained_snapshots_and_receipts_and_keeps_them_readable(self):
        with tempfile.TemporaryDirectory() as d:
            root=tree(d);lines=[]
            result=rr.run(root,apply=True,out=lines.append)
            self.assertEqual(result['redacted'],3);self.assertEqual(result['left'],[])
            for rel in ['.local/eia/net-generation-5069dfaaa115.json','.local/eia/capacity-additions-5a6f2c439a44.json',
                        '.local/nightly/2026-09-11/importers.json']:
                blob=(root/rel).read_bytes()
                self.assertNotIn(FAKE.encode(),blob,f'{rel} still holds the key')
                self.assertIn(b'[redacted]',blob)
                json.loads(blob.decode('utf-8'))   # a redacted snapshot is still the JSON its importer parses
            self.assertEqual(json.loads((root/'.local/eia/net-generation-5069dfaaa115.json').read_text(encoding='utf-8'))
                             ['response']['data'],[{'period':'2026-01'}])
            self.assertFalse(any(FAKE in l for l in lines))

    def test_the_vault_itself_is_never_rewritten(self):
        with tempfile.TemporaryDirectory() as d:
            root=tree(d);before=(root/'.local/api-keys.json').read_bytes()
            rr.run(root,apply=True,out=lambda _:None)
            self.assertEqual((root/'.local/api-keys.json').read_bytes(),before)

    def test_a_key_inside_the_repository_is_reported_not_quietly_patched(self):
        with tempfile.TemporaryDirectory() as d:
            root=tree(d);lines=[]
            result=rr.run(root,apply=True,out=lines.append)
            self.assertIn(FAKE,(root/'research/api-access.json').read_text(encoding='utf-8'))
            self.assertEqual([p.as_posix() for p in result['outside']],['research/api-access.json'])
            self.assertTrue(any('rotate the key' in l for l in lines))

    def test_a_short_vault_value_is_never_searched_for(self):
        with tempfile.TemporaryDirectory() as d:
            root=tree(d)
            self.assertEqual([n for n,_ in rr.secrets(root)],['eia'])   # 'short':'x' would blank every x in the tree

    def test_no_vault_means_nothing_to_scan(self):
        with tempfile.TemporaryDirectory() as d:
            result=rr.run(Path(d),apply=True,out=lambda _:None)
            self.assertEqual(result,{'files':[],'redacted':0,'outside':[]})


class RepositoryInvariantTests(unittest.TestCase):
    def test_no_registered_key_reaches_the_repository_or_a_retained_file(self):
        """The standing rule, asserted against this checkout: keys live in .local/api-keys.json
        and nowhere else. Skipped where no vault exists (a clean clone, a worktree)."""
        if not rr.secrets(ROOT):self.skipTest('no .local/api-keys.json in this checkout')
        self.assertEqual([f[0].as_posix() for f in rr.holders(ROOT)],[])

    def test_a_vault_written_to_the_wrong_directory_is_still_never_committed(self):
        """.local/ is ignored, but a key file saved beside the code would be tracked and pushed."""
        git=shutil.which('git')
        if not git:self.skipTest('git unavailable')
        for candidate in ['api-keys.json','research/api-keys.json','scripts/api-keys.json','.local/api-keys.json']:
            ignored=subprocess.run([git,'check-ignore','-q',candidate],cwd=ROOT).returncode
            self.assertEqual(ignored,0,f'{candidate} would be committed')


if __name__=='__main__':unittest.main()
