#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "archive_youtube_transcript.py"


def load_module():
    spec = importlib.util.spec_from_file_location("archive_youtube_transcript", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class CaptionSelectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_module()

    def test_best_prefers_source_original_caption_over_english_translation(self) -> None:
        info = {
            "language": "fr",
            "subtitles": {},
            "automatic_captions": {
                "en": [{"url": "https://example.invalid/en"}],
                "fr-orig": [{"url": "https://example.invalid/fr"}],
                "de": [{"url": "https://example.invalid/de"}],
            },
        }

        choices = self.module.caption_candidates(info, "best")

        self.assertEqual(("fr-orig", "automatic"), choices[0][:2])
        self.assertIn(("en", "automatic"), [choice[:2] for choice in choices])

    def test_best_prefers_english_when_source_language_is_english(self) -> None:
        info = {
            "language": "en",
            "subtitles": {},
            "automatic_captions": {
                "en": [{"url": "https://example.invalid/en"}],
                "fr-orig": [{"url": "https://example.invalid/fr"}],
            },
        }

        choices = self.module.caption_candidates(info, "best")

        self.assertEqual(("en", "automatic"), choices[0][:2])

    def test_explicit_language_keeps_requested_language(self) -> None:
        info = {
            "language": "fr",
            "subtitles": {},
            "automatic_captions": {
                "en": [{"url": "https://example.invalid/en"}],
                "fr-orig": [{"url": "https://example.invalid/fr"}],
            },
        }

        choices = self.module.caption_candidates(info, "en")

        self.assertEqual([("en", "automatic")], [choice[:2] for choice in choices])


if __name__ == "__main__":
    unittest.main()
