#!/usr/bin/env python3
"""Regression tests for audio-transcription archive repair/provenance behavior.

These tests intentionally use only stdlib and a tiny synthetic provider fixture.
They do not call external STT services and do not require ffmpeg.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

SKILL_DIR = Path(__file__).resolve().parents[1]
HELPER_PATH = SKILL_DIR / "scripts" / "transcribe_audio.py"
FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"

spec = importlib.util.spec_from_file_location("transcribe_audio", HELPER_PATH)
assert spec and spec.loader
transcribe_audio = importlib.util.module_from_spec(spec)
spec.loader.exec_module(transcribe_audio)


class AudioTranscriptionRegressionTests(unittest.TestCase):
    def test_repair_alignment_removes_replacement_characters(self) -> None:
        provider = json.loads((FIXTURE_DIR / "repaired-provider-ko.json").read_text(encoding="utf-8"))
        clean_text = (FIXTURE_DIR / "repaired-clean-ko.txt").read_text(encoding="utf-8")
        repaired, ratio = transcribe_audio.repair_segments_from_clean_text(provider["segments"], clean_text)

        self.assertGreaterEqual(ratio, 0.85)
        self.assertEqual([item["text"] for item in repaired], ["안녕하세요", "세계입니다."])
        rendered = transcribe_audio.render_repaired_transcript("Fixture", repaired, {}, ratio)
        self.assertIn("안녕하세요", rendered)
        self.assertNotIn("�", rendered)

    def test_archive_preserves_raw_provider_bytes_and_repair_outputs(self) -> None:
        provider_raw = (FIXTURE_DIR / "repaired-provider-ko.json").read_bytes()
        response: dict[str, Any] = json.loads(provider_raw.decode("utf-8"))

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            clean_path = root / "clean.txt"
            clean_path.write_bytes((FIXTURE_DIR / "repaired-clean-ko.txt").read_bytes())
            archive_dir = root / "archive"

            args = argparse.Namespace(
                input=str(root / "staged-source.mp3"),
                mode="archive",
                output_dir=str(archive_dir),
                archive_root=None,
                seminar_collection=None,
                title="Regression Fixture",
                date="2026-01-02",
                slug=None,
                timezone="UTC",
                recorded_at=None,
                language=None,
                access_level="internal",
                cloud_ok=True,
                privacy_note=None,
                backend="mistral",
                model="voxtral-mini-latest",
                diarize=True,
                timestamp_granularities=["segment"],
                speaker=[],
                main_speaker=None,
                keyword=[],
                related=[],
                quality_flag=[],
                max_direct_duration_seconds=10800,
                save_audio=False,
                staged_input=True,
                repair_from_clean_transcript=str(clean_path),
                repair_alignment_threshold=0.85,
            )
            source_info = {
                "source_name": "staged-source.mp3",
                "source_path_recorded": False,
                "duration_seconds": 1.0,
            }
            normalize_info = {"normalized": False}

            transcribe_audio.save_archive(args, response, source_info, normalize_info, provider_raw)

            raw_path = archive_dir / "provider-response.raw.json"
            self.assertEqual(raw_path.read_bytes(), provider_raw)

            metadata = json.loads((archive_dir / "metadata.json").read_text(encoding="utf-8"))
            self.assertEqual(metadata["provider_raw_response"]["sha256"], hashlib.sha256(provider_raw).hexdigest())
            self.assertEqual(metadata["provider_raw_response"]["size_bytes"], len(provider_raw))
            self.assertTrue(metadata["input_was_staged_copy"])
            self.assertIn("unicode_replacement_characters_in_provider_response", metadata["quality_flags"])
            self.assertTrue(metadata["repair"]["created"])

            repaired = (archive_dir / "transcript.repaired.md").read_text(encoding="utf-8")
            self.assertIn("안녕하세요", repaired)
            self.assertNotIn("�", repaired)
            self.assertTrue((archive_dir / "segments.repaired.json").exists())


if __name__ == "__main__":
    unittest.main()
