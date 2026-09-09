import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import research
import render
import session_receipt as receipt
from research_notify import summary


class SessionReceiptTests(unittest.TestCase):
    def fixture(self,root,publish=True):
        folder=root/'.local/sessions'/('a'*32);(folder/'batches').mkdir(parents=True)
        report=dict(started_at='2026-09-08T01:00:00Z',state='completed',elapsed_seconds=3600,
                    batches=2,failed_batches=1,options={'publish':publish,'direction':'balanced','private_url':'secret'})
        for i,accepted in enumerate([3,0]):
            batch={'monitoring':{'documents_fetched':4,'accepted':accepted,'quarantined':1,'source_failures':[{'reason':'private error'}],'model_calls':2},
                   'discovery':{'documents_fetched':2,'errors':[]},'publication':'pushed'}
            (folder/'batches'/f'{i}.json').write_text(json.dumps(batch),encoding='utf-8')
        (folder/'status.json').write_text(json.dumps(report),encoding='utf-8')
        return folder,report

    def test_aggregates_whole_session_not_final_batch(self):
        with tempfile.TemporaryDirectory() as t:
            folder,report=self.fixture(Path(t));record=receipt.public_receipt(report,summary(folder),folder)
            self.assertEqual(record['documents_fetched'],12)
            self.assertEqual(record['accepted'],3)
            self.assertEqual(record['receipts_recorded'],2)
            self.assertNotIn('secret',json.dumps(record));self.assertNotIn('private error',json.dumps(record))
            self.assertNotIn('options',record)
            for bad in [dict(record,source_urls=['private']),dict(record,batches=True),dict(record,accepted=-1),dict(record,state='researching')]:
                with self.assertRaises(ValueError):receipt.validate_receipt(bad)

    def test_missing_receipt_is_visible_in_static_footer(self):
        with tempfile.TemporaryDirectory() as t:
            folder,report=self.fixture(Path(t));(folder/'batches/1.json').unlink()
            record=receipt.public_receipt(report,summary(folder),folder)
            data=json.loads((ROOT/'site/data/ledger.json').read_text(encoding='utf-8'))
            data['runtime']['latest_session']=record
            html=render.runtime(data)
            self.assertIn('1 of 2 batch receipts',html)
            self.assertNotIn('Latest monitoring batch:',html)
            self.assertIn('Latest research session:',html)
            self.assertIn('3 accepted monitoring records',html)

    def test_private_and_discovery_only_do_not_publish(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);folder,report=self.fixture(root,False)
            with patch.object(research,'preflight') as preflight:
                self.assertEqual(receipt.finalize(root,report,folder,summary(folder))['status'],'private')
                report['options'].update(publish=True,direction='discovery')
                self.assertEqual(receipt.finalize(root,report,folder,summary(folder))['status'],'private')
                preflight.assert_not_called()
            self.assertFalse((folder/'public-summary.json').exists())

    def test_publisher_requires_receipts_and_detects_tampering(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);folder,report=self.fixture(root)
            record=receipt.public_receipt(report,summary(folder),folder)
            with self.assertRaises(ValueError):receipt.verify_retained_receipt(root,record)
            (folder/'public-summary.json').write_text(json.dumps(record),encoding='utf-8')
            receipt.verify_retained_receipt(root,record)
            (folder/'batches/0.json').unlink()
            with self.assertRaises(ValueError):receipt.verify_retained_receipt(root,record)

    def test_finalization_uses_existing_publisher_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);folder,report=self.fixture(root)
            for p in ['site/data','docs/data','research']:(root/p).mkdir(parents=True)
            data=json.loads((ROOT/'site/data/ledger.json').read_text(encoding='utf-8'));data['runtime'].pop('latest_session',None)
            (root/'site/data/ledger.json').write_text(json.dumps(data),encoding='utf-8')
            (root/'research/runtime.json').write_text('{}',encoding='utf-8')
            def build():
                (root/'docs/data/ledger.json').write_bytes((root/'site/data/ledger.json').read_bytes())
            with patch.object(research,'ROOT',root),patch.object(research,'LOCAL',root/'.local'),patch.object(research,'preflight'),patch.object(research,'build',side_effect=build),patch.object(research,'publish') as publish:
                self.assertEqual(receipt.finalize(root,report,folder,summary(folder))['status'],'pushed')
                self.assertEqual(receipt.finalize(root,report,folder,summary(folder))['status'],'already_pushed')
                publish.assert_called_once()
            updated=json.loads((root/'site/data/ledger.json').read_text(encoding='utf-8'))
            self.assertEqual(updated['runtime'].pop('latest_session')['accepted'],3)
            self.assertEqual(updated,data)

    def test_preflight_failure_preserves_public_data(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);folder,report=self.fixture(root)
            (root/'research').mkdir();(root/'research/runtime.json').write_text('{}',encoding='utf-8')
            with patch.object(research,'ROOT',root),patch.object(research,'LOCAL',root/'.local'),patch.object(research,'preflight',side_effect=ValueError('dirty tree')),patch.object(research,'publish') as publish:
                self.assertEqual(receipt.finalize(root,report,folder,summary(folder))['status'],'failed')
                publish.assert_not_called()
            self.assertTrue((folder/'public-summary.json').exists())
            self.assertFalse((root/'site').exists())


if __name__=='__main__':unittest.main()
