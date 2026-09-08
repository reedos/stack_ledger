import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import findings_review as review
import research
import discovery
import editorial_review
import research_loop


class FindingsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        research.save(self.root/'research/editorial-policy.json',{'reviewers':['reedos'],'reviewer_accounts':{'reedos':['fixture-human']}})
        self.rid='discovery-'+'a'*24
        self.item={'id':self.rid,'kind':'coverage_expansion','layer':'energy','url':'https://example.org/source',
            'created_at':'2026-09-08T00:00:00Z','finding':{'kind':'project','subject':'Fixture plant',
            'claim':'A company reports operation.','evidence':'Source states that the plant is operating.',
            'basis':'actual','why_track':'Investigate dependable power.','next_question':'Verify operator data.'}}
        research.save(editorial_review.queue(self.root)/(self.rid+'.json'),self.item)

    def payload(self):
        row=review.inbox(self.root)['findings'][0]
        return {'id':self.rid,'decision':'investigate','rationale':'Verify the operator report.',
            'proposal_hash':row['proposal_hash'],'review_hash':row['review_hash'],'confirmed':True}

    def test_recorded_triage_reuses_log_without_public_writes(self):
        with patch.object(review.getpass,'getuser',return_value='fixture-human'):
            row=review.inbox(self.root)['findings'][0]
            self.assertEqual(row['status'],'pending_review');self.assertIsNone(row['published_at'])
            self.assertFalse(review.review(self.root,self.payload())['published'])
            self.assertEqual(review.inbox(self.root)['findings'][0]['status'],'investigate')
            event=editorial_review.events(self.root)[-1]
            self.assertEqual(event['reviewer'],'reedos');self.assertIn('proposal_hash',event)
            self.assertFalse((self.root/'site').exists())

    def test_account_confirmation_and_publication_restrictions(self):
        with patch.object(review.getpass,'getuser',return_value='outsider'):
            with self.assertRaises(ValueError):review.review(self.root,self.payload())
        with patch.object(review.getpass,'getuser',return_value='fixture-human'):
            for extra in [{'confirmed':False},{'decision':'approved'},{'rationale':' '},{'id':'../../secret'}]:
                with self.assertRaises(ValueError):review.review(self.root,dict(self.payload(),**extra))
        self.assertEqual(editorial_review.events(self.root),[])

    def test_stale_evidence_and_concurrent_review_are_rejected(self):
        with patch.object(review.getpass,'getuser',return_value='fixture-human'):
            payload=self.payload()
            modified=copy.deepcopy(self.item);modified['finding']['claim']='Changed claim.'
            research.save(editorial_review.queue(self.root)/(self.rid+'.json'),modified)
            with self.assertRaisesRegex(ValueError,'Finding changed'):review.review(self.root,payload)
            payload=self.payload();review.review(self.root,payload)
            with self.assertRaisesRegex(ValueError,'Review changed'):review.review(self.root,payload)
            self.assertEqual(len(editorial_review.events(self.root)),1)

    def test_overnight_overlap_skips_both_session_and_standalone_batch(self):
        for name in ['research-session.lock','research.lock']:
            with self.subTest(name=name):
                lock=self.root/'.local'/name;lock.parent.mkdir(exist_ok=True);lock.write_text('existing owner')
                with patch.object(research_loop,'ROOT',self.root),patch.object(research_loop,'overnight_seconds',return_value=21600), \
                     patch.object(research_loop.subprocess,'Popen') as spawn,patch.object(research_loop,'gpu_idle') as gpu,patch('builtins.print'):
                    self.assertEqual(research_loop.main(['--start','--overnight','--publish']),0)
                    spawn.assert_not_called();gpu.assert_not_called()
                self.assertEqual(lock.read_text(),'existing owner')
                self.assertEqual(research.load(self.root/'.local/schedule-overlap.json')['status'],'skipped')
                self.assertFalse((self.root/'.local/session-status.json').exists())
                lock.unlink()


if __name__=='__main__':unittest.main()
