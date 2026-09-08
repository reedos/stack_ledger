import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch,Mock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import research_notify as notify
import research
import schedule


class NotificationTests(unittest.TestCase):
    def test_summary_distinguishes_private_discovery_and_confirmed_pushes(self):
        with tempfile.TemporaryDirectory() as t:
            folder=Path(t)
            research.save(folder/'batches/a.json',{'monitoring':{'documents_fetched':3,'accepted':2,'quarantined':1,'source_failures':[{}]},'publication':'pushed'})
            research.save(folder/'batches/b.json',{'discovery':{'documents_fetched':2,'proposals_queued':1,'errors':[{}]},'publication':'private'})
            research.save(folder/'batches/c.json',{'monitoring':{'accepted':1},'publication':'pending'})
            totals=notify.summary(folder)
            self.assertEqual(totals['documents'],5);self.assertEqual(totals['accepted'],3)
            self.assertEqual(totals['pushed_batches'],1);self.assertEqual(totals['unpublished_batches'],1)
            text=notify.message({'state':'completed','options':{'publish':True}},totals)
            self.assertIn('1 batches pushed; 1 pending/unconfirmed',text)
            self.assertIn('1 (private review inbox)',text)
            self.assertNotIn('site updated',text.lower())

    def test_disabled_route_never_sends(self):
        with tempfile.TemporaryDirectory() as t,patch.object(notify.subprocess,'run') as send:
            root=Path(t);self.assertEqual(notify.deliver(root,'test',root/'receipt.json')['status'],'disabled')
            send.assert_not_called()

    def test_delivery_reuses_openclaw_and_does_not_repeat_on_failure(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);research.save(root/'.local/telegram-notifications.json',{'enabled':True,'account':'default','target':'12345'})
            with patch.object(schedule,'cli',return_value=['openclaw']),patch.object(notify.subprocess,'run',side_effect=TimeoutError) as send:
                result=notify.deliver(root,'Fixture summary',root/'notification.json')
                self.assertEqual(result['status'],'failed')
                self.assertEqual(notify.deliver(root,'Fixture summary',root/'notification.json')['status'],'already_attempted')
                send.assert_called_once()
                self.assertIn('telegram',send.call_args.args[0]);self.assertNotIn('botToken',str(send.call_args))

    def test_overlap_message_does_not_claim_completed_research(self):
        text=notify.message({'status':'skipped'}, {})
        self.assertIn('skipped',text);self.assertIn('continues unchanged',text)
        self.assertNotIn('accepted',text)
