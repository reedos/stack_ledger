import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from atomic_json import save
from research_progress import report
from evaluate_collection import evaluate


class ProgressTests(unittest.TestCase):
    def test_proposals_and_partial_screens_never_resolve_questions(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);folder=root/'.local/sessions'/('a'*32)
            save(folder/'batches/a.json',{'discovery':{'attempts':[
                {'layer':'energy','question':'Which plant is operating?','outcome':'pending_review','proposal_id':'candidate-a'},
                {'layer':'energy','question':'Which plant is operating?','outcome':'no_findings','screen_coverage':{'complete':False}},
                {'layer':'models','outcome':'no_findings'}]}})
            value=report(root,folder)
            row=value['discovery_questions'][0]
            self.assertEqual(row['status'],'proposals_need_review')
            self.assertEqual(row['partial_exposures'],1)
            self.assertEqual(row['proposal_ids'],['candidate-a'])
            self.assertEqual(len(value['discovery_questions']),1)
            self.assertFalse((root/'site').exists())
            self.assertTrue((folder/'research-progress.md').exists())

    def test_audit_rejects_path_escape(self):
        with self.assertRaises(ValueError):evaluate(Path('.'),'../../secrets')


if __name__=='__main__':unittest.main()
