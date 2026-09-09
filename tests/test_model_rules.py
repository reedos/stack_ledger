import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from model_rules import EVIDENCE_RULES, SCREENING_RULES, NOTE_EVIDENCE_MAX, METRIC_EVIDENCE_MAX

ROOT=Path(__file__).resolve().parents[1]


class ModelRuleParityTests(unittest.TestCase):
    """Every deterministic validator rule must be stated to the model before it can be rejected for it."""

    def test_every_validator_rule_has_a_model_facing_sentence(self):
        for phrase in ['contiguous','publication year','digit sequence','> and <','unit letter','convert units','shortest passage']:
            with self.subTest(phrase=phrase):self.assertIn(phrase,EVIDENCE_RULES)

    def test_screening_rules_name_both_outcomes_and_a_specific_defect(self):
        for phrase in ['not the tone of the source','A defect must be specific','Both outcomes are legitimate','never that the outcome occurred','Fill the checklist']:
            with self.subTest(phrase=phrase):self.assertIn(phrase,SCREENING_RULES)

    def test_reviewer_lanes_share_the_screening_rules(self):
        research=(ROOT/'scripts/research.py').read_text(encoding='utf-8')
        discovery=(ROOT/'scripts/discovery.py').read_text(encoding='utf-8')
        # Note reviewer and metric reviewer system prompts, plus both task packets.
        self.assertEqual(research.count("'\\n'+SCREENING_RULES+'\\nYou are a skeptical evidence reviewer"),2)
        self.assertEqual(research.count("'screening_rules':SCREENING_RULES"),2)
        self.assertIn("SCREENING_RULES+'\\nThis task is PRIVATE DISCOVERY",discovery)
        self.assertIn("'evidence_rules':EVIDENCE_RULES",discovery)
        self.assertEqual(research.count("'evidence_rules':EVIDENCE_RULES"),2)

    def test_rules_stay_small_and_grant_nothing(self):
        self.assertLess(len(EVIDENCE_RULES)+len(SCREENING_RULES),2600)
        import re
        self.assertIsNone(re.search(r'\b(approve|approved|approval|push|commit|allowlist)\b',(EVIDENCE_RULES+SCREENING_RULES).lower()))
        self.assertLess(NOTE_EVIDENCE_MAX,METRIC_EVIDENCE_MAX)


if __name__=='__main__':unittest.main()
