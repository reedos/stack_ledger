import json
import sys
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import research
import research_loop


class OperationsTests(unittest.TestCase):
    def test_plan_does_not_query_gpu_or_start_research(self):
        with patch.object(research_loop,'gpu_idle') as gpu,patch.object(research_loop.subprocess,'run') as run,patch('builtins.print'):
            self.assertEqual(research_loop.main([]),0)
            gpu.assert_not_called();run.assert_not_called()

    def test_repeated_sessions_reach_unattempted_sources(self):
        registry=json.loads((ROOT/'research/sources.json').read_text(encoding='utf-8'))
        attempted={};day=date(2026,9,8);seen=set()
        for _ in range(len(registry['sources'])):
            batch=research.source_queue(registry,day,attempted=attempted)[:8]
            for s in batch:attempted[s['id']]='2026-09-08T12:00:00Z';seen.add(s['id'])
        self.assertEqual(seen,{s['id'] for s in registry['sources'] if s['layers']})

    def test_context_includes_new_open_model_coverage(self):
        value=research.coverage_context(ROOT,{'id':'open-hf-hub'})
        self.assertIn('Hugging Face',value)
        self.assertLessEqual(len(value),6000)

    def test_unknown_focused_source_still_rejected_with_progress(self):
        registry=json.loads((ROOT/'research/sources.json').read_text(encoding='utf-8'))
        with self.assertRaises(ValueError):research.source_queue(registry,date(2026,9,8),['invented'],{})

    def test_same_document_does_not_call_model_again(self):
        source={'id':'known'};document='Original evidence'
        with patch.object(research,'ollama') as model:
            self.assertIsNone(research.extract_note({},source,document,[{'source':'known','document_sha256':research.digest(document)}],{},[]))
            model.assert_not_called()
