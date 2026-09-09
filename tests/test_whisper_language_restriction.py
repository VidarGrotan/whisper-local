# test_whisper_language_restriction.py
# Regression coverage for constraining automatic language detection to the
# languages a user actually dictates, without changing explicit language mode.

import sys
import unittest
from unittest import mock
from types import SimpleNamespace
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))


class AllowedLanguageSelectionTests(unittest.TestCase):
    def test_selects_norwegian_when_swedish_has_the_highest_probability(self):
        from whisper_key.whisper_engine import _select_allowed_language

        detected_language, probability = _select_allowed_language(
            [("sv", 0.80), ("no", 0.15), ("en", 0.05)],
            ["en", "no"],
            fallback_language="en",
        )

        self.assertEqual(detected_language, "no")
        self.assertEqual(probability, 0.15)

    def test_selects_english_when_it_is_the_most_likely_allowed_language(self):
        from whisper_key.whisper_engine import _select_allowed_language

        detected_language, probability = _select_allowed_language(
            [("en", 0.60), ("no", 0.35), ("sv", 0.05)],
            ["en", "no"],
            fallback_language="en",
        )

        self.assertEqual(detected_language, "en")
        self.assertEqual(probability, 0.60)

    def test_defaults_to_english_when_english_and_norwegian_are_close(self):
        from whisper_key.whisper_engine import _select_allowed_language

        detected_language, probability = _select_allowed_language(
            [("no", 0.38), ("en", 0.34), ("sv", 0.28)],
            ["en", "no"],
            fallback_language="en",
        )

        self.assertEqual(detected_language, "en")
        self.assertEqual(probability, 0.34)

    def test_auto_mode_decodes_using_the_most_likely_allowed_language(self):
        from whisper_key.whisper_engine import WhisperEngine

        class FakeModel:
            def __init__(self):
                self.transcribe_language = None

            def detect_language(self, audio):
                return "sv", 0.80, [("sv", 0.80), ("no", 0.15), ("en", 0.05)]

            def transcribe(self, audio, **kwargs):
                self.transcribe_language = kwargs["language"]
                segments = iter([SimpleNamespace(text=" Dette er norsk.")])
                info = SimpleNamespace(language="no", language_probability=1.0)
                return segments, info

        engine = WhisperEngine.__new__(WhisperEngine)
        engine.model = FakeModel()
        engine.language = None
        engine.allowed_languages = ["en", "no"]
        engine.fallback_language = "en"
        engine.beam_size = 5
        engine.initial_prompt = None
        engine.hotwords = None
        engine.task = "transcribe"
        engine.vad_manager = None
        engine.last_detected_language = None
        engine.log_transcriptions = False
        engine.logger = __import__("logging").getLogger(__name__)

        text = engine.transcribe_audio(np.zeros(16000, dtype=np.float32))

        self.assertEqual(text, "Dette er norsk.")
        self.assertEqual(engine.model.transcribe_language, "no")
        self.assertEqual(engine.last_detected_language, "no")

    def test_faster_whisper_setup_forwards_allowed_languages(self):
        from whisper_key import main

        config = {
            "backend": "faster_whisper",
            "model": "large-v3-turbo",
            "device": "cuda",
            "compute_type": "float16",
            "language": "auto",
            "allowed_languages": ["en", "no"],
            "fallback_language": "en",
            "beam_size": 5,
        }

        with mock.patch.object(main, "WhisperEngine", return_value="engine") as engine:
            result = main.setup_whisper_engine(config, None, None)

        self.assertEqual(result, "engine")
        self.assertEqual(engine.call_args.kwargs["allowed_languages"], ["en", "no"])
        self.assertEqual(engine.call_args.kwargs["fallback_language"], "en")


if __name__ == "__main__":
    unittest.main()
