"""A dated launch from the company that shipped it is a development, not marketing to discard.

Measured 2026-09-12, from one 20-minute session: the note lane answered "document outside scope"
for openai.com/index/gpt-6-astra-next-generation-work, openai.com/index/introducing-the-agents-api
and a blog.google post about Google's global network. Every one was fully exposed to the model
(complete: True), so nothing was truncated -- the prompt told it to reject "promotional claims",
and a frontier model launch read as promotional.

The owner's call: a launch without figures still belongs in the ledger, because being current is
part of the point. `Company announcement` was already a valid event kind with 23 entries, so the
home existed; the prompt was refusing to fill it.

What must NOT follow from that: the note lane still refuses conferences, investment advice,
unattributed superlatives and inferred benefits, and every other guard is untouched -- evidence
is still a quoted passage from the document, every number in a note must still be supported, and
grade is still derived from the registered source.
"""
import json
import re
import sys
import unittest
from unittest import mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import research

# provenance matters here: grade is derived from it, and a grade C or D source turns any note
# into a labelled report (News report / Social post) instead of a Company announcement. A source
# with no provenance fails closed to D, which is how the first draft of these tests got a
# 'News report' out of an OpenAI launch.
SOURCE = {'id': 'src-launch', 'publisher': 'OpenAI', 'title': 'OpenAI news', 'provenance': 'company-channel',
          'url': 'https://openai.com/index/gpt-6-astra/', 'layers': ['models'], 'published': '2026-09-11'}
OUTLET = dict(SOURCE, id='src-outlet', publisher='TechCrunch', provenance='news',
              url='https://techcrunch.com/2026/09/11/openai-ships-gpt-6-astra/')
LAUNCH_DOC = ('Introducing GPT-6 Astra. GPT-6 Astra is available today in the API and in ChatGPT for '
              'all paid tiers. It is our most capable model for long-running agentic work, and replaces '
              'GPT-5.6 as the default for new conversations. ') * 4


def prompt_task():
    """The task sentence the note lane actually sends."""
    src = (ROOT/'scripts/research.py').read_text(encoding='utf-8')
    m = re.search(r"'task':f'Produce at most one concise research note(.*?)','evidence_rules'", src, re.S)
    assert m, 'the note task prompt has moved'
    return m.group(1)


class PromptContractTests(unittest.TestCase):
    def setUp(self):
        self.task = prompt_task()

    def test_a_launch_is_named_as_a_development(self):
        for phrase in ('launch', 'Company announcement'):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.task)

    def test_it_says_a_launch_without_figures_still_counts(self):
        self.assertRegex(self.task, r'even when it carries no figures|without figures|no figures')

    def test_the_blanket_refusal_of_promotional_claims_is_gone(self):
        """This exact wording is what rejected a GPT-6 launch."""
        self.assertNotIn('No generic announcements about conferences, promotional claims', self.task)

    def test_genuine_junk_is_still_refused(self):
        for junk in ('conferences', 'investment advice', 'inferred'):
            with self.subTest(junk=junk):
                self.assertIn(junk, self.task)

    def test_the_surviving_guards_are_untouched(self):
        for guard in ('Attribute company claims', 'contiguous passage copied exactly',
                      'Do not repeat existing_notes', 'empty_reason'):
            with self.subTest(guard=guard):
                self.assertIn(guard, self.task)


class RulesVersionTests(unittest.TestCase):
    """A cached review keyed on the old rules would keep a rejected launch rejected forever."""

    def test_the_note_rules_version_moved_with_the_prompt(self):
        runtime = json.loads((ROOT/'research/runtime.json').read_text(encoding='utf-8'))
        self.assertNotEqual(runtime['note_rules_version'], '2026-09-09.4',
                            'the prompt changed; documents cached under the old version would not be re-judged')

    def test_a_version_bump_changes_the_review_identity(self):
        sha = 'a'*64
        self.assertNotEqual(research.note_identity(sha, '2026-09-09.4'),
                            research.note_identity(sha, '2026-09-12.1'))

    def test_the_metrics_lane_identity_is_independent_of_the_note_rules(self):
        """Bumping note rules must not invalidate metrics-lane work; they are separate lanes."""
        sha = 'a'*64
        self.assertEqual(research.metrics_identity(sha, ['m'], '7'), research.metrics_identity(sha, ['m'], '7'))


class LaunchNoteTests(unittest.TestCase):
    """Drive the lane with a stubbed model: a launch note must survive every downstream guard."""

    def config(self):
        return {'_instructions': 'inst', '_coverage': 'cov', 'document_window_chars': 20000}

    def run_note(self, response, document=LAUNCH_DOC, existing=(), supported=True):
        """A note that survives the deterministic guards goes to a second-pass verifier, which is
        a separate model call. Both are stubbed: `response` is the extraction, `supported` is the
        reviewer's verdict, so a test can exercise either gate on its own."""
        run = {'model_calls': 0}; quarantine = []; collection = {}
        # The reviewer's real shape: a defect from the reviewed vocabulary plus every checklist
        # box as a bool. normalize_verdict derives `supported` from those, so a stub that sets
        # `supported` directly would test a code path the model never takes.
        from model_rules import CHECKLIST
        verdict = {'verdicts': [dict({k: supported for k in CHECKLIST}, index=0,
                                     defect='none' if supported else 'wrong_scope',
                                     reason='' if supported else 'the passage does not support the claim')]}
        with mock.patch.object(research, 'ollama', side_effect=[response, verdict]):
            note = research.extract_note(self.config(), SOURCE, document, list(existing), run, quarantine,
                                         collection, {})
        return note, quarantine

    def test_a_launch_note_carrying_no_figures_of_its_own_is_accepted(self):
        # "Figureless" means no capacity, spend or count -- but a version name is still a number to
        # the evidence guard (see test_a_version_number_is_a_number below), so the quoted passage
        # covers both versions the summary names.
        evidence = ('GPT-6 Astra is available today in the API and in ChatGPT for all paid tiers. It is our '
                    'most capable model for long-running agentic work, and replaces GPT-5.6 as the default '
                    'for new conversations.')
        note, quarantine = self.run_note({'notes': [{
            'title': 'GPT-6 Astra released', 'kind': 'Company announcement', 'layer': 'models',
            'summary': ('OpenAI released GPT-6 Astra, available in the API and ChatGPT for paid tiers, '
                        'replacing GPT-5.6 as the default for new conversations. The company describes it '
                        'as its most capable model for long-running agentic work.'),
            'evidence': evidence}]})
        self.assertEqual(quarantine, [], 'a launch with no capacity or spend figure must not be quarantined')
        self.assertIsNotNone(note)
        self.assertEqual(note['kind'], 'Company announcement')

    def test_a_version_number_is_a_number_to_the_evidence_guard(self):
        """Found while writing these tests: "GPT-5.6" parses as 5.6 and needs evidence like any
        other figure. Worth pinning -- it is the likeliest way a genuine launch note gets
        quarantined, and the fix is always a longer quoted passage, never a weaker guard."""
        note, quarantine = self.run_note({'notes': [{
            'title': 'GPT-6 Astra released', 'kind': 'Company announcement', 'layer': 'models',
            'summary': ('OpenAI released GPT-6 Astra, available in the API and ChatGPT for paid tiers, '
                        'replacing GPT-5.6 as the default for new conversations across the product.'),
            'evidence': 'GPT-6 Astra is available today in the API and in ChatGPT for all paid tiers.'}]})
        self.assertIsNone(note, 'the passage does not mention 5.6')
        self.assertEqual([q['reason'] for q in quarantine], ['Note includes an unsupported number'])

    def test_a_number_in_the_note_must_still_be_supported_by_the_document(self):
        """Admitting launches must not admit unsupported figures."""
        note, quarantine = self.run_note({'notes': [{
            'title': 'GPT-6 Astra released', 'kind': 'Company announcement', 'layer': 'models',
            'summary': ('OpenAI released GPT-6 Astra to 900 million users today, available in the API and '
                        'in ChatGPT for all paid tiers, replacing GPT-5.6 as the default model.'),
            'evidence': 'GPT-6 Astra is available today in the API and in ChatGPT for all paid tiers.'}]})
        self.assertIsNone(note)
        self.assertTrue(quarantine, 'an unsupported number must still be refused')

    def test_evidence_must_still_come_from_the_document(self):
        note, quarantine = self.run_note({'notes': [{
            'title': 'GPT-6 Astra released', 'kind': 'Company announcement', 'layer': 'models',
            'summary': ('OpenAI released GPT-6 Astra, available in the API and in ChatGPT for paid tiers, '
                        'replacing GPT-5.6 as the default for new conversations across the product.'),
            'evidence': 'A sentence that appears nowhere in the source document at all.'}]})
        self.assertIsNone(note)
        self.assertTrue(quarantine)

    def test_the_same_launch_from_an_outlet_is_labelled_a_report(self):
        """A launch covered by a news outlet is grade C, so it publishes as a News report carrying
        the outlet and an unconfirmed state -- never as the company's own announcement."""
        evidence = ('GPT-6 Astra is available today in the API and in ChatGPT for all paid tiers. It is our '
                    'most capable model for long-running agentic work, and replaces GPT-5.6 as the default '
                    'for new conversations.')
        run = {'model_calls': 0}; quarantine = []
        from model_rules import CHECKLIST
        verdict = {'verdicts': [dict({k: True for k in CHECKLIST}, index=0, defect='none', reason='')]}
        proposal = {'notes': [{
            'title': 'GPT-6 Astra released', 'kind': 'Company announcement', 'layer': 'models',
            'summary': ('OpenAI released GPT-6 Astra, available in the API and ChatGPT for paid tiers, '
                        'replacing GPT-5.6 as the default for new conversations. The company describes it '
                        'as its most capable model for long-running agentic work.'),
            'evidence': evidence}]}
        with mock.patch.object(research, 'ollama', side_effect=[proposal, verdict]):
            note = research.extract_note(self.config(), OUTLET, LAUNCH_DOC, [], run, quarantine, {}, {})
        self.assertIsNotNone(note, quarantine)
        self.assertEqual(note['kind'], 'News report')
        self.assertEqual(note['grade'], 'C')
        self.assertEqual(note['confirmation'], 'unconfirmed')
        self.assertEqual(note['outlet'], 'TechCrunch')

    def test_the_reviewer_can_still_reject_a_launch_note(self):
        """Admitting launches does not bypass the second pass: the skeptical reviewer is the last
        gate and its refusal must still quarantine the note."""
        evidence = ('GPT-6 Astra is available today in the API and in ChatGPT for all paid tiers. It is our '
                    'most capable model for long-running agentic work, and replaces GPT-5.6 as the default '
                    'for new conversations.')
        note, quarantine = self.run_note({'notes': [{
            'title': 'GPT-6 Astra released', 'kind': 'Company announcement', 'layer': 'models',
            'summary': ('OpenAI released GPT-6 Astra, available in the API and ChatGPT for paid tiers, '
                        'replacing GPT-5.6 as the default for new conversations. The company describes it '
                        'as its most capable model for long-running agentic work.'),
            'evidence': evidence}]}, supported=False)
        self.assertIsNone(note)
        self.assertTrue(quarantine)

    def test_an_empty_answer_still_records_its_reason(self):
        note, _ = self.run_note({'notes': [], 'empty_reason': 'document outside scope'})
        self.assertIsNone(note)


if __name__ == '__main__':
    unittest.main()
