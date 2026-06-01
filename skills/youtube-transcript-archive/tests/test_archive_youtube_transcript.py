#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "archive_youtube_transcript.py"
BATCH_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "archive_youtube_batch.py"


def load_module(script: Path = SCRIPT, name: str = "archive_youtube_transcript"):
    spec = importlib.util.spec_from_file_location(name, script)
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

    def test_best_retries_next_candidate_after_download_failure(self) -> None:
        choices = [
            ("en", "automatic", [{"url": "https://example.invalid/en"}]),
            ("fr-orig", "automatic", [{"url": "https://example.invalid/fr"}]),
        ]
        calls = []

        def download(lang: str, source: str) -> Path:
            calls.append((lang, source))
            if lang == "en":
                raise RuntimeError("simulated download failure")
            return Path("/tmp/fr.vtt")

        lang, source, path, errors = self.module.select_caption_vtt(
            choices,
            "best",
            False,
            download,
        )

        self.assertEqual(("fr-orig", "automatic", Path("/tmp/fr.vtt")), (lang, source, path))
        self.assertEqual([("en", "automatic"), ("fr-orig", "automatic")], calls)
        self.assertEqual(1, len(errors))
        self.assertIn("simulated download failure", errors[0])

    def test_explicit_language_does_not_retry_after_download_failure(self) -> None:
        choices = [
            ("en", "automatic", [{"url": "https://example.invalid/en"}]),
            ("fr-orig", "automatic", [{"url": "https://example.invalid/fr"}]),
        ]
        calls = []

        def download(lang: str, source: str) -> Path:
            calls.append((lang, source))
            raise RuntimeError("simulated download failure")

        with self.assertRaisesRegex(RuntimeError, "Caption download failed for en"):
            self.module.select_caption_vtt(
                choices,
                "en",
                False,
                download,
            )

        self.assertEqual([("en", "automatic")], calls)


class MetadataOnlyArchiveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_module()

    def test_has_any_captions_detects_empty_caption_pools(self) -> None:
        self.assertFalse(self.module.has_any_captions({"subtitles": {}, "automatic_captions": {}}))
        self.assertFalse(self.module.has_any_captions({"subtitles": {"en": []}, "automatic_captions": {}}))
        self.assertTrue(
            self.module.has_any_captions(
                {"subtitles": {}, "automatic_captions": {"fr-orig": [{"url": "https://example.invalid/fr"}]}}
            )
        )

    def test_metadata_only_archive_writes_manifest_and_report(self) -> None:
        info = {
            "id": "abc123",
            "webpage_url": "https://www.youtube.com/watch?v=abc123",
            "title": "No captions here",
            "channel": "Example Channel",
            "upload_date": "20260601",
            "duration": 50,
        }
        with tempfile.TemporaryDirectory() as tmp_s:
            video_dir = Path(tmp_s) / "abc123"
            self.module.write_base_artifacts(video_dir, info, "no captions listed\n")

            manifest = self.module.write_metadata_only_archive(
                video_dir,
                info,
                yt_dlp_version_text="test-version",
                duplicate_policy="reuse-existing-complete-archive",
            )

            self.assertEqual("metadata-only-no-captions", manifest["status"])
            self.assertEqual("none", manifest["transcript_source"])
            self.assertEqual(["manifest.json", "metadata.json", "subtitles-list.txt", "report.md"], manifest["files"])
            self.assertTrue((video_dir / "manifest.json").exists())
            self.assertTrue((video_dir / "metadata.json").exists())
            self.assertTrue((video_dir / "subtitles-list.txt").exists())
            report = (video_dir / "report.md").read_text(encoding="utf-8")
            self.assertIn("Metadata-only archive", report)
            self.assertIn("No transcript available.", report)


class BatchArchiveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_module(BATCH_SCRIPT, "archive_youtube_batch")

    def test_build_batch_index_summarizes_caption_and_metadata_entries(self) -> None:
        entries = [
            {
                "input_url": "https://www.youtube.com/watch?v=captioned",
                "status": "created",
                "video_id": "captioned",
                "title": "Captioned video",
                "channel": "Channel A",
                "language": "fr-orig",
                "transcript_source": "automatic",
                "report_path": "/archive/captioned/report.md",
                "report_summary": "Filled report summary from the per-video archive.",
                "validation_errors": [],
            },
            {
                "input_url": "https://www.youtube.com/watch?v=nocaps",
                "status": "metadata-only-no-captions",
                "video_id": "nocaps",
                "title": "No captions video",
                "channel": "Channel B",
                "language": "unknown",
                "transcript_source": "none",
                "report_path": "/archive/nocaps/report.md",
                "validation_errors": [],
            },
        ]
        counts = self.module.summarize_entries(entries)

        index = self.module.build_batch_index(
            title="Example Batch",
            archive_root=Path("/archive"),
            entries=entries,
            counts=counts,
        )

        self.assertEqual(1, counts["caption_backed"])
        self.assertEqual(1, counts["metadata_only"])
        self.assertIn("| `captioned` | Captioned video | Channel A | transcript archived | `fr-orig` automatic captions |", index)
        self.assertIn("| `nocaps` | No captions video | Channel B | metadata only | no captions exposed |", index)
        self.assertIn("- `captioned`: Filled report summary from the per-video archive.", index)
        self.assertIn("- Caption-backed archives: 1", index)
        self.assertIn("- Metadata-only no-caption archives: 1", index)

    def test_validate_entry_uses_manifest_file_list_and_rejects_media(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_s:
            root = Path(tmp_s)
            video_dir = root / "abc123"
            video_dir.mkdir()
            for name in ["manifest.json", "metadata.json", "subtitles-list.txt", "report.md"]:
                (video_dir / name).write_text("{}\n" if name.endswith(".json") else "ok\n", encoding="utf-8")
            (video_dir / "abc123.mp4").write_text("not real media, but extension is enough\n", encoding="utf-8")
            entry = {
                "status": "created",
                "video_id": "abc123",
                "manifest": {"files": ["manifest.json", "metadata.json", "subtitles-list.txt", "report.md"]},
            }

            errors = self.module.validate_entry(root, entry)

            self.assertIn("media file present: abc123.mp4", errors)
            self.assertEqual(1, len(errors))

    def test_extract_report_summary_ignores_placeholder_and_keeps_filled_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_s:
            root = Path(tmp_s)
            filled = root / "filled.md"
            filled.write_text(
                "# Report\n\n## Summary\nA filled summary.\n\nWith a second paragraph.\n\n## Full transcript\nText\n",
                encoding="utf-8",
            )
            placeholder = root / "placeholder.md"
            placeholder.write_text(
                "# Report\n\n## Summary\nRaw transcript archival is complete. Summary not yet written; read later.\n\n## Full transcript\nText\n",
                encoding="utf-8",
            )

            self.assertEqual("A filled summary.", self.module.extract_report_summary(str(filled)))
            self.assertIsNone(self.module.extract_report_summary(str(placeholder)))

    def test_timestamp_zone_kst_changes_default_title_and_id_timezone(self) -> None:
        kst_now = self.module.timestamp_now("kst")

        self.assertEqual("KST", kst_now.tzname())
        self.assertTrue(self.module.default_batch_id(kst_now).endswith("-youtube-batch"))
        self.assertIn("KST", self.module.default_batch_title(kst_now))


if __name__ == "__main__":
    unittest.main()
