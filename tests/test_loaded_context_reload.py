"""A model another caller loaded with a smaller context is reloaded, not refused.

Two research sessions on the night of 2026-09-12/13 -- the owner's manual test and the 01:30
nightly -- each failed every batch within three minutes with "Model note extraction or review
failed" and blocked. The real exception was swallowed behind a RuntimeError; reproduced directly
it was:

    Model is loaded with a 16384-token context, below the required 32768; reload it ...

OpenClaw's tools pin the same model in Ollama with an effectively infinite keep_alive, at 8192 or
16384 depending on which tool ran last (lib/docs.py and photo-intake.py send 16384 explicitly), so
a tag-level default of 32768 could not help: a default only applies to a caller that sends nothing.

The refusal existed on the theory that Ollama would silently truncate our prompt to the loaded
size. Measured on Ollama 0.33.2: it does not. A request whose num_ctx exceeds the runner's makes
Ollama reload the runner at the requested size -- 16384 before one such request, 32768 after. The
guard was turning a self-healing condition into a dead night.

These tests stub the HTTP layer and drive ollama() itself, so they prove the request that triggers
the reload is actually sent, not merely that a string changed.
"""
import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from unittest import mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import research

SCHEMA = {'type': 'object', 'properties': {'notes': {'type': 'array'}}, 'required': ['notes']}


def config():
    return {'ollama_url': 'http://127.0.0.1:11434', 'model': 'muse-glimmer:30b-q4_K_M-dflash',
            'model_timeout_seconds': 30}


class FakeResponse:
    def __init__(self, payload):
        self.raw = json.dumps(payload).encode()
    def read(self, n=-1):
        return self.raw
    def __enter__(self): return self
    def __exit__(self, *a): return False


class FakeOpener:
    """Records every request body so a test can assert what was sent to Ollama."""
    def __init__(self, model):
        self.model = model; self.bodies = []
    def open(self, req, timeout=None):
        self.bodies.append(json.loads(req.data.decode()))
        return FakeResponse({'done': True, 'done_reason': 'stop', 'model': self.model,
                             'message': {'role': 'assistant', 'content': json.dumps({'notes': []})}})


def call(loaded):
    """Run ollama() with the runner reported at `loaded` tokens; return (result, sent bodies, stdout)."""
    cfg = config(); opener = FakeOpener(cfg['model']); out = io.StringIO()
    research._LOADED.pop(cfg['model'], None)
    with mock.patch.object(research, 'loaded_context', return_value=loaded), \
         mock.patch.object(research, 'build_opener', return_value=opener), \
         redirect_stdout(out):
        result = research.ollama(cfg, 'system', 'prompt', SCHEMA)
    return result, opener.bodies, out.getvalue()


class ReloadInsteadOfRefuseTests(unittest.TestCase):
    def test_a_smaller_loaded_context_no_longer_raises(self):
        result, bodies, _ = call(loaded=16384)
        self.assertEqual(result, {'notes': []})
        self.assertEqual(len(bodies), 1, 'the request must actually go out; that is what reloads the runner')

    def test_the_request_carries_the_context_that_forces_the_reload(self):
        """Ollama reloads because the requested num_ctx exceeds the runner's. If this ever drops
        below the required size the reload would not happen and the old truncation risk returns."""
        _, bodies, _ = call(loaded=16384)
        self.assertEqual(bodies[0]['options']['num_ctx'], research.GENERATION['num_ctx'])
        self.assertGreater(bodies[0]['options']['num_ctx'], 16384)

    def test_the_batch_log_says_what_happened_and_why(self):
        """The old refusal at least named the condition; a silent reload would hide that another
        caller keeps pinning the model small, which the owner needs to know about."""
        _, _, out = call(loaded=16384)
        self.assertIn('loaded at 16384 tokens by another caller', out)
        self.assertIn('requesting 32768 reloads it', out)

    def test_the_pinned_sizes_openclaw_actually_uses_both_pass(self):
        for pinned in (8192, 16384):
            with self.subTest(loaded=pinned):
                result, bodies, out = call(loaded=pinned)
                self.assertEqual(result, {'notes': []})
                self.assertIn('reloads it', out)

    def test_an_adequate_or_unknown_context_is_silent(self):
        for loaded in (32768, 65536, None):
            with self.subTest(loaded=loaded):
                result, bodies, out = call(loaded=loaded)
                self.assertEqual(result, {'notes': []})
                self.assertNotIn('reloads it', out)

    def test_the_cache_reflects_the_size_the_call_established(self):
        """Without this, the 60-second cache would keep reporting the stale smaller size and the
        notice would print on every call for a minute after the runner had already reloaded."""
        cfg = config()
        call(loaded=16384)
        cached = research._LOADED.get(cfg['model'])
        self.assertIsNotNone(cached)
        self.assertEqual(cached[1], research.GENERATION['num_ctx'])

    def test_the_old_refusal_is_gone_from_the_source(self):
        source = (ROOT/'scripts/research.py').read_text(encoding='utf-8')
        self.assertNotIn('below the required', source,
                         'the hard refusal is still there; two sessions died on it in one night')


class UnchangedGuardsTests(unittest.TestCase):
    """Relaxing one check must not relax its neighbours."""

    def test_a_remote_endpoint_is_still_refused(self):
        cfg = dict(config(), ollama_url='http://example.com:11434')
        with self.assertRaises(ValueError):
            research.ollama(cfg, 'system', 'prompt', SCHEMA)

    def test_an_oversized_prompt_is_still_refused(self):
        cfg = config()
        huge = 'x' * (research.prompt_budget(research.GENERATION) + 1)
        with mock.patch.object(research, 'loaded_context', return_value=None):
            with self.assertRaises(ValueError):
                research.ollama(cfg, huge, '', SCHEMA)

    def test_an_unexpected_served_model_is_still_refused(self):
        cfg = config(); opener = FakeOpener('some-other-model')
        with mock.patch.object(research, 'loaded_context', return_value=32768), \
             mock.patch.object(research, 'build_opener', return_value=opener), \
             redirect_stdout(io.StringIO()):
            with self.assertRaises(ValueError):
                research.ollama(cfg, 'system', 'prompt', SCHEMA)


if __name__ == '__main__':
    unittest.main()
