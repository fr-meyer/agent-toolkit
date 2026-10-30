#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


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
                "fr": [{"url": "https://example.invalid/fr"}],
            },
        }

        choices = self.module.caption_candidates(info, "best")

        self.assertEqual(("en", "automatic"), choices[0][:2])

    def test_best_prefers_original_caption_even_when_metadata_language_is_misleading(self) -> None:
        info = {
            "language": "en",
            "subtitles": {},
            "automatic_captions": {
                "en": [{"url": "https://example.invalid/en"}],
                "fr-orig": [{"url": "https://example.invalid/fr"}],
            },
        }

        choices = self.module.caption_candidates(info, "best")

        self.assertEqual(("fr-orig", "automatic"), choices[0][:2])
        self.assertIn(("en", "automatic"), [choice[:2] for choice in choices])

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

        def download(lang: str, source: str) -> tuple[Path, bytes]:
            calls.append((lang, source))
            if lang == "en":
                raise RuntimeError("simulated download failure")
            return Path("/tmp/fr.vtt"), b"WEBVTT\n"

        lang, source, path, caption_bytes, errors = self.module.select_caption_vtt(
            choices,
            "best",
            False,
            download,
        )

        self.assertEqual(("fr-orig", "automatic", Path("/tmp/fr.vtt")), (lang, source, path))
        self.assertEqual(b"WEBVTT\n", caption_bytes)
        self.assertEqual([("en", "automatic"), ("fr-orig", "automatic")], calls)
        self.assertEqual(1, len(errors))
        self.assertIn("simulated download failure", errors[0])

    def test_explicit_language_does_not_retry_after_download_failure(self) -> None:
        choices = [
            ("en", "automatic", [{"url": "https://example.invalid/en"}]),
            ("fr-orig", "automatic", [{"url": "https://example.invalid/fr"}]),
        ]
        calls = []

        def download(lang: str, source: str) -> tuple[Path, bytes]:
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
            self.module.write_base_artifacts(
                video_dir,
                info,
                "no captions listed\n",
                refresh=False,
                metadata_storage_mode="legacy",
            )

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

    def test_dual_metadata_only_archive_is_exact_and_manifest_selected(self) -> None:
        info = {
            "id": "abc123",
            "title": "Unicode café — exact bytes",
            "automatic_captions": {"fr": [{"name": "Français"}]},
        }
        with tempfile.TemporaryDirectory() as tmp_s:
            video_dir = Path(tmp_s) / "abc123"
            descriptor = self.module.write_base_artifacts(
                video_dir,
                info,
                "no captions listed\n",
                refresh=False,
                metadata_storage_mode="dual",
            )
            self.assertIsNotNone(descriptor)
            raw = (video_dir / "metadata.json").read_bytes()

            manifest = self.module.write_metadata_only_archive(
                video_dir,
                info,
                yt_dlp_version_text="test-version",
                duplicate_policy="reuse-existing-complete-archive",
                metadata_descriptor=descriptor,
            )

            self.assertEqual("dual", manifest["metadata_storage"]["state"])
            self.assertIn(manifest["metadata_storage"]["canonical_filename"], manifest["files"])
            recovered = self.module.metadata_storage.read_metadata_bytes(video_dir, manifest)
            self.assertEqual(raw, recovered)
            reused = self.module.resolve_existing_archive(
                video_dir,
                "best",
                metadata_storage_mode="dual",
            )
            self.assertEqual(manifest["metadata_storage"], reused["metadata_storage"])

    def test_declared_dual_archive_never_falls_back_to_plaintext(self) -> None:
        info = {"id": "abc123", "title": "No fallback"}
        with tempfile.TemporaryDirectory() as tmp_s:
            video_dir = Path(tmp_s) / "abc123"
            descriptor = self.module.write_base_artifacts(
                video_dir,
                info,
                "none\n",
                refresh=False,
                metadata_storage_mode="dual",
            )
            manifest = self.module.write_metadata_only_archive(
                video_dir,
                info,
                yt_dlp_version_text="test-version",
                duplicate_policy="reuse-existing-complete-archive",
                metadata_descriptor=descriptor,
            )
            (video_dir / manifest["metadata_storage"]["canonical_filename"]).unlink()
            with self.assertRaises(self.module.metadata_storage.MetadataIntegrityError):
                self.module.resolve_existing_archive(video_dir, "best", metadata_storage_mode="dual")

    def test_language_manifest_key_rejects_path_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_s:
            with self.assertRaises(self.module.metadata_storage.MetadataPathError):
                self.module.manifest_path_for(Path(tmp_s), "../../escape")

    def test_caption_download_rejects_unsafe_language_before_running_yt_dlp(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_s, mock.patch.object(self.module, "run") as runner:
            with self.assertRaises(self.module.metadata_storage.MetadataPathError):
                self.module.download_caption_vtt(
                    "/fixture/yt-dlp",
                    "https://www.youtube.com/watch?v=abc123",
                    "abc123",
                    "../../escape",
                    "automatic",
                    Path(tmp_s) / "abc123",
                )
            runner.assert_not_called()

    def test_caption_download_refuses_symlinked_destination_ancestors(self) -> None:
        def emit_caption(_cmd, *, cwd):
            (Path(cwd) / "abc123.en.vtt").write_text("WEBVTT\n", encoding="utf-8")
            return mock.Mock()

        with tempfile.TemporaryDirectory() as tmp_s:
            root = Path(tmp_s)
            video_dir = root / "abc123"
            outside = root / "outside"
            video_dir.mkdir()
            outside.mkdir()
            (video_dir / "raw").symlink_to(outside, target_is_directory=True)
            with mock.patch.object(self.module, "run", side_effect=emit_caption):
                with self.assertRaises(self.module.metadata_storage.MetadataPathError):
                    self.module.download_caption_vtt(
                        "/fixture/yt-dlp",
                        "https://www.youtube.com/watch?v=abc123",
                        "abc123",
                        "en",
                        "automatic",
                        video_dir,
                    )
            self.assertEqual([], list(outside.iterdir()))

    def test_caption_download_refuses_symlinked_final_file(self) -> None:
        def emit_caption(_cmd, *, cwd):
            (Path(cwd) / "abc123.en.vtt").write_text("WEBVTT\n", encoding="utf-8")
            return mock.Mock()

        with tempfile.TemporaryDirectory() as tmp_s:
            root = Path(tmp_s)
            video_dir = root / "abc123"
            destination = video_dir / "raw" / "en"
            outside = root / "outside.vtt"
            destination.mkdir(parents=True)
            outside.write_text("sentinel\n", encoding="utf-8")
            target = destination / "abc123.en.vtt"
            target.symlink_to(outside)
            with mock.patch.object(self.module, "run", side_effect=emit_caption):
                with self.assertRaises(self.module.metadata_storage.MetadataPathError):
                    self.module.download_caption_vtt(
                        "/fixture/yt-dlp",
                        "https://www.youtube.com/watch?v=abc123",
                        "abc123",
                        "en",
                        "automatic",
                        video_dir,
                    )
            self.assertTrue(target.is_symlink())
            self.assertEqual("sentinel\n", outside.read_text(encoding="utf-8"))

    def test_parse_vtt_rejects_symlink_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_s:
            root = Path(tmp_s)
            outside = root / "outside.vtt"
            outside.write_text("WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nhello\n", encoding="utf-8")
            candidate = root / "candidate.vtt"
            candidate.symlink_to(outside)

            with self.assertRaises(self.module.metadata_storage.MetadataPathError):
                self.module.parse_vtt(candidate)

    def test_caption_parsing_uses_verified_bytes_after_destination_replacement(self) -> None:
        original_vtt = b"WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nverified original\n"
        replacement_vtt = b"WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nreplaced outside\n"

        def emit_caption(_cmd, *, cwd):
            (Path(cwd) / "abc123.en.vtt").write_bytes(original_vtt)
            return mock.Mock()

        with tempfile.TemporaryDirectory() as tmp_s:
            root = Path(tmp_s)
            video_dir = root / "abc123"
            video_dir.mkdir()
            outside = root / "outside.vtt"
            outside.write_bytes(replacement_vtt)
            durable_write = self.module.metadata_storage.durable_atomic_write

            def replace_after_commit(path: Path, data: bytes) -> None:
                durable_write(path, data)
                path.unlink()
                path.symlink_to(outside)

            with mock.patch.object(self.module, "run", side_effect=emit_caption), mock.patch.object(
                self.module.metadata_storage,
                "durable_atomic_write",
                side_effect=replace_after_commit,
            ):
                raw_vtt, caption_bytes = self.module.download_caption_vtt(
                    "/fixture/yt-dlp",
                    "https://www.youtube.com/watch?v=abc123",
                    "abc123",
                    "en",
                    "automatic",
                    video_dir,
                )

            self.assertTrue(raw_vtt.is_symlink())
            self.assertEqual(replacement_vtt, raw_vtt.read_bytes())
            clean_lines, timestamped = self.module.parse_vtt_bytes(caption_bytes)
            self.assertEqual(["verified original"], clean_lines)
            self.assertEqual([("00:00:00.000", "verified original")], timestamped)

    def test_language_manifest_reuse_requires_the_canonical_commit_marker(self) -> None:
        info = {"id": "abc123", "title": "Interrupted language manifest"}
        with tempfile.TemporaryDirectory() as tmp_s:
            video_dir = Path(tmp_s) / "abc123"
            descriptor = self.module.write_base_artifacts(
                video_dir,
                info,
                "captions\n",
                refresh=False,
                metadata_storage_mode="dual",
            )
            self.assertIsNotNone(descriptor)
            language_manifest = video_dir / "manifests" / "en.json"
            language_manifest.parent.mkdir()
            manifest = self.module.metadata_storage.prepare_manifest_with_storage(
                {
                    "language": "en",
                    "files": [
                        "manifest.json",
                        "metadata.json",
                        "subtitles-list.txt",
                        "manifests/en.json",
                    ],
                },
                descriptor,
            )
            self.module.metadata_storage.durable_atomic_write(
                language_manifest,
                self.module.metadata_storage.manifest_bytes(manifest),
            )

            self.assertIsNone(
                self.module.resolve_existing_archive(video_dir, "en", metadata_storage_mode="dual")
            )
            recovered = self.module.write_base_artifacts(
                video_dir,
                info,
                "captions\n",
                refresh=False,
                metadata_storage_mode="dual",
            )
            self.assertEqual(descriptor, recovered)

            self.module.metadata_storage.commit_manifest(video_dir, manifest)
            reused = self.module.resolve_existing_archive(video_dir, "en", metadata_storage_mode="dual")
            self.assertEqual(descriptor, reused["metadata_storage"])

    def test_archive_manifest_publish_is_alias_first_and_byte_identical(self) -> None:
        info = {"id": "abc123", "title": "Canonical last"}
        with tempfile.TemporaryDirectory() as tmp_s:
            video_dir = Path(tmp_s) / "abc123"
            descriptor = self.module.write_base_artifacts(
                video_dir,
                info,
                "captions\n",
                refresh=False,
                metadata_storage_mode="dual",
            )
            self.assertIsNotNone(descriptor)
            manifests_dir = self.module.ensure_real_subdirectories(video_dir, "manifests")
            language_manifest = manifests_dir / "en.json"
            manifest = self.module.metadata_storage.prepare_manifest_with_storage(
                {"language": "en", "files": ["manifest.json", "metadata.json"]},
                descriptor,
            )

            with mock.patch.object(
                self.module.metadata_storage,
                "commit_manifest",
                side_effect=RuntimeError("interrupted canonical commit"),
            ):
                with self.assertRaisesRegex(RuntimeError, "interrupted canonical commit"):
                    self.module.commit_archive_manifests(
                        video_dir,
                        language_manifest,
                        manifest,
                        descriptor,
                    )
            self.assertTrue(language_manifest.exists())
            self.assertFalse((video_dir / "manifest.json").exists())
            self.assertIsNone(
                self.module.resolve_existing_archive(video_dir, "en", metadata_storage_mode="dual")
            )

            self.module.commit_archive_manifests(
                video_dir,
                language_manifest,
                manifest,
                descriptor,
            )
            self.assertEqual(
                (video_dir / "manifest.json").read_bytes(),
                language_manifest.read_bytes(),
            )
            reused = self.module.resolve_existing_archive(video_dir, "en", metadata_storage_mode="dual")
            self.assertEqual(descriptor, reused["metadata_storage"])

    def test_non_replacing_creation_rejects_concurrent_metadata_appearance(self) -> None:
        info = {"id": "abc123", "title": "First writer"}
        conflicting = json.dumps(
            {"id": "abc123", "title": "Concurrent writer"},
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8")
        with tempfile.TemporaryDirectory() as tmp_s:
            video_dir = Path(tmp_s) / "abc123"
            with mock.patch.object(
                self.module.metadata_storage,
                "write_plaintext_metadata",
                return_value=conflicting,
            ):
                with self.assertRaisesRegex(
                    self.module.metadata_storage.MetadataIntegrityError,
                    "changed during non-replacing archive creation",
                ):
                    self.module.write_base_artifacts(
                        video_dir,
                        info,
                        "captions\n",
                        refresh=False,
                        metadata_storage_mode="dual",
                    )

    def test_orphaned_plaintext_mismatch_is_refused_without_replacement(self) -> None:
        original = {"id": "abc123", "title": "Interrupted original"}
        changed = {"id": "abc123", "title": "Changed retry"}
        with tempfile.TemporaryDirectory() as tmp_s:
            video_dir = Path(tmp_s) / "abc123"
            video_dir.mkdir()
            original_raw = json.dumps(
                original,
                indent=2,
                ensure_ascii=False,
                sort_keys=True,
            ).encode("utf-8")
            self.module.metadata_storage.write_plaintext_metadata(
                video_dir,
                original_raw,
                replace=False,
            )

            with self.assertRaisesRegex(
                self.module.metadata_storage.MetadataIntegrityError,
                "orphaned plaintext metadata mismatch",
            ):
                self.module.write_base_artifacts(
                    video_dir,
                    changed,
                    "changed\n",
                    refresh=False,
                    metadata_storage_mode="dual",
                )

            self.assertEqual(original_raw, (video_dir / "metadata.json").read_bytes())
            self.assertEqual([], list(video_dir.glob("metadata.*.json.gz")))
            recovered = self.module.write_base_artifacts(
                video_dir,
                original,
                "captions\n",
                refresh=False,
                metadata_storage_mode="dual",
            )
            self.assertEqual(self.module.metadata_storage.sha256_bytes(original_raw), recovered["raw_sha256"])

    def test_dual_generation_is_fully_validated_before_descriptor_return(self) -> None:
        info = {"id": "abc123", "title": "Round-trip gate"}
        with tempfile.TemporaryDirectory() as tmp_s, mock.patch.object(
            self.module.metadata_storage,
            "prepare_dual_generation",
            side_effect=self.module.metadata_storage.MetadataIntegrityError("fixture corruption"),
        ):
            video_dir = Path(tmp_s) / "abc123"
            with self.assertRaisesRegex(
                self.module.metadata_storage.MetadataIntegrityError, "fixture corruption"
            ):
                self.module.write_base_artifacts(
                    video_dir,
                    info,
                    "none\n",
                    refresh=False,
                    metadata_storage_mode="dual",
                )
            self.assertFalse((video_dir / "manifest.json").exists())

    def test_changed_dual_refresh_is_refused_without_damaging_old_manifest(self) -> None:
        original = {"id": "abc123", "title": "Original"}
        changed = {"id": "abc123", "title": "Changed"}
        with tempfile.TemporaryDirectory() as tmp_s:
            video_dir = Path(tmp_s) / "abc123"
            descriptor = self.module.write_base_artifacts(
                video_dir,
                original,
                "none\n",
                refresh=False,
                metadata_storage_mode="dual",
            )
            manifest = self.module.write_metadata_only_archive(
                video_dir,
                original,
                yt_dlp_version_text="fixture",
                duplicate_policy="reuse-existing-complete-archive",
                metadata_descriptor=descriptor,
            )
            old_manifest = (video_dir / "manifest.json").read_bytes()
            old_plaintext = (video_dir / "metadata.json").read_bytes()

            with self.assertRaisesRegex(
                self.module.metadata_storage.MetadataIntegrityError,
                "non-atomic dual refresh",
            ):
                self.module.write_base_artifacts(
                    video_dir,
                    changed,
                    "changed\n",
                    refresh=True,
                    metadata_storage_mode="dual",
                )

            self.assertEqual(old_manifest, (video_dir / "manifest.json").read_bytes())
            self.assertEqual(old_plaintext, (video_dir / "metadata.json").read_bytes())
            self.assertEqual(old_plaintext, self.module.metadata_storage.read_metadata_bytes(video_dir, manifest))

    def test_changed_dual_reuse_is_refused_without_mixing_metadata_and_report_fields(self) -> None:
        original = {"id": "abc123", "title": "Original"}
        changed = {"id": "abc123", "title": "Changed"}
        with tempfile.TemporaryDirectory() as tmp_s:
            video_dir = Path(tmp_s) / "abc123"
            descriptor = self.module.write_base_artifacts(
                video_dir,
                original,
                "none\n",
                refresh=False,
                metadata_storage_mode="dual",
            )
            self.module.write_metadata_only_archive(
                video_dir,
                original,
                yt_dlp_version_text="fixture",
                duplicate_policy="reuse-existing-complete-archive",
                metadata_descriptor=descriptor,
            )
            old_manifest = (video_dir / "manifest.json").read_bytes()
            old_plaintext = (video_dir / "metadata.json").read_bytes()

            with self.assertRaisesRegex(
                self.module.metadata_storage.MetadataIntegrityError,
                "non-atomic dual refresh/reuse",
            ):
                self.module.write_base_artifacts(
                    video_dir,
                    changed,
                    "changed\n",
                    refresh=False,
                    metadata_storage_mode="dual",
                )

            self.assertEqual(old_manifest, (video_dir / "manifest.json").read_bytes())
            self.assertEqual(old_plaintext, (video_dir / "metadata.json").read_bytes())

    def test_changed_legacy_to_dual_refresh_is_refused_before_plaintext_replace(self) -> None:
        original = {"id": "abc123", "title": "Original legacy"}
        changed = {"id": "abc123", "title": "Changed for dual"}
        with tempfile.TemporaryDirectory() as tmp_s:
            video_dir = Path(tmp_s) / "abc123"
            self.module.write_base_artifacts(
                video_dir,
                original,
                "none\n",
                refresh=False,
                metadata_storage_mode="legacy",
            )
            self.module.write_metadata_only_archive(
                video_dir,
                original,
                yt_dlp_version_text="fixture",
                duplicate_policy="reuse-existing-complete-archive",
            )
            old_manifest = (video_dir / "manifest.json").read_bytes()
            old_plaintext = (video_dir / "metadata.json").read_bytes()

            with self.assertRaisesRegex(
                self.module.metadata_storage.MetadataIntegrityError,
                "legacy-to-dual refresh",
            ):
                self.module.write_base_artifacts(
                    video_dir,
                    changed,
                    "changed\n",
                    refresh=True,
                    metadata_storage_mode="dual",
                )

            self.assertEqual(old_manifest, (video_dir / "manifest.json").read_bytes())
            self.assertEqual(old_plaintext, (video_dir / "metadata.json").read_bytes())
            self.assertFalse(any(video_dir.glob("metadata.*.json.gz")))

    def test_existing_dual_archive_cannot_be_downgraded_by_legacy_writer(self) -> None:
        info = {"id": "abc123", "title": "Original"}
        with tempfile.TemporaryDirectory() as tmp_s:
            video_dir = Path(tmp_s) / "abc123"
            descriptor = self.module.write_base_artifacts(
                video_dir,
                info,
                "none\n",
                refresh=False,
                metadata_storage_mode="dual",
            )
            self.module.write_metadata_only_archive(
                video_dir,
                info,
                yt_dlp_version_text="fixture",
                duplicate_policy="reuse-existing-complete-archive",
                metadata_descriptor=descriptor,
            )
            with self.assertRaisesRegex(
                self.module.metadata_storage.MetadataIntegrityError,
                "refusing to downgrade",
            ):
                self.module.write_base_artifacts(
                    video_dir,
                    info,
                    "none\n",
                    refresh=True,
                    metadata_storage_mode="legacy",
                )

    def test_cli_rejects_unsafe_video_id_before_archive_child_creation(self) -> None:
        info = {
            "id": "../../outside-created",
            "title": "Unsafe identity",
            "subtitles": {},
            "automatic_captions": {},
        }
        with tempfile.TemporaryDirectory() as tmp_s:
            root = Path(tmp_s)
            archive_root = root / "archive"
            with (
                mock.patch.object(self.module.shutil, "which", return_value="/fixture/yt-dlp"),
                mock.patch.object(self.module, "load_json_from_yt_dlp", return_value=info),
                mock.patch.object(
                    sys,
                    "argv",
                    ["archive", "unsafe", "--archive-root", str(archive_root)],
                ),
            ):
                with self.assertRaises(self.module.metadata_storage.MetadataPathError):
                    self.module.main()
            self.assertFalse((root / "outside-created").exists())

    def test_cli_default_is_legacy_and_dual_requires_explicit_opt_in(self) -> None:
        info = {"id": "abc123", "title": "Storage mode", "subtitles": {}, "automatic_captions": {}}
        with tempfile.TemporaryDirectory() as tmp_s:
            root = Path(tmp_s)
            common = ["archive", "https://www.youtube.com/watch?v=abc123", "--metadata-only-on-no-captions"]
            with (
                mock.patch.object(self.module.shutil, "which", return_value="/fixture/yt-dlp"),
                mock.patch.object(self.module, "load_json_from_yt_dlp", return_value=info),
                mock.patch.object(self.module, "list_subs", return_value="none\n"),
                mock.patch.object(self.module, "yt_dlp_version", return_value="fixture"),
                mock.patch.object(sys, "argv", common + ["--archive-root", str(root / "legacy")]),
            ):
                self.assertEqual(0, self.module.main())
            legacy = json.loads((root / "legacy" / "abc123" / "manifest.json").read_text(encoding="utf-8"))
            self.assertNotIn("metadata_storage", legacy)
            self.assertEqual([], list((root / "legacy" / "abc123").glob("metadata.*.json.gz")))

            with (
                mock.patch.object(self.module.shutil, "which", return_value="/fixture/yt-dlp"),
                mock.patch.object(self.module, "load_json_from_yt_dlp", return_value=info),
                mock.patch.object(self.module, "list_subs", return_value="none\n"),
                mock.patch.object(self.module, "yt_dlp_version", return_value="fixture"),
                mock.patch.object(sys, "argv", common + ["--archive-root", str(root / "dual"), "--metadata-storage", "dual"]),
            ):
                self.assertEqual(0, self.module.main())
            dual = json.loads((root / "dual" / "abc123" / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual("dual", dual["metadata_storage"]["state"])
            self.assertTrue((root / "dual" / "abc123" / dual["metadata_storage"]["canonical_filename"]).is_file())

    def test_cli_accepts_queue_owned_carrier_context_without_mutating_it(self) -> None:
        info = {"id": "abc123", "title": "Queue carrier", "subtitles": {}, "automatic_captions": {}}
        with tempfile.TemporaryDirectory() as tmp_s:
            root = Path(tmp_s)
            state_root = root / "state"
            projection_root = root / "projection"
            storage_module = root / "youtube_storage.py"
            storage_module.write_text("# fixture only\n", encoding="utf-8")
            argv = [
                "archive",
                "https://www.youtube.com/watch?v=abc123",
                "--archive-root",
                str(root / "archive"),
                "--metadata-only-on-no-captions",
                "--state-root",
                str(state_root),
                "--projection-root",
                str(projection_root),
                "--storage-module",
                str(storage_module),
                "--writer-lock-held",
            ]
            with (
                mock.patch.object(self.module.shutil, "which", return_value="/fixture/yt-dlp"),
                mock.patch.object(self.module, "load_json_from_yt_dlp", return_value=info),
                mock.patch.object(self.module, "list_subs", return_value="none\n"),
                mock.patch.object(self.module, "yt_dlp_version", return_value="fixture"),
                mock.patch.object(sys, "argv", argv),
            ):
                self.assertEqual(0, self.module.main())
            self.assertFalse(state_root.exists())
            self.assertFalse(projection_root.exists())


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
                "transcript_path": "/archive/captioned/transcript/fr-orig/clean-deduped.txt",
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
                "transcript_path": None,
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
        self.assertIn(
            "| `captioned` | Captioned video | Channel A | transcript archived | `fr-orig` automatic captions | `/archive/captioned/report.md` | `/archive/captioned/transcript/fr-orig/clean-deduped.txt` |",
            index,
        )
        self.assertIn(
            "| `nocaps` | No captions video | Channel B | metadata only | no captions exposed | `/archive/nocaps/report.md` | none |",
            index,
        )
        self.assertIn("- `captioned`: Filled report summary from the per-video archive.", index)
        self.assertIn("- Caption-backed archives: 1", index)
        self.assertIn("- Metadata-only no-caption archives: 1", index)

    def test_validate_entry_uses_manifest_file_list_and_rejects_media(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_s:
            root = Path(tmp_s)
            video_dir = root / "abc123"
            video_dir.mkdir()
            transcript_dir = video_dir / "transcript" / "en"
            transcript_dir.mkdir(parents=True)
            for name in ["manifest.json", "metadata.json", "subtitles-list.txt", "report.md"]:
                (video_dir / name).write_text("{}\n" if name.endswith(".json") else "ok\n", encoding="utf-8")
            (transcript_dir / "clean-deduped.txt").write_text("caption text\n", encoding="utf-8")
            (video_dir / "abc123.mp4").write_text("not real media, but extension is enough\n", encoding="utf-8")
            entry = {
                "status": "created",
                "video_id": "abc123",
                "transcript_source": "automatic",
                "manifest": {
                    "files": [
                        "manifest.json",
                        "metadata.json",
                        "subtitles-list.txt",
                        "report.md",
                        "transcript/en/clean-deduped.txt",
                    ]
                },
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

    def test_summary_status_marks_only_caption_backed_placeholder_reports_as_needing_summary(self) -> None:
        entries = [
            {
                "status": "created",
                "video_id": "captioned",
                "title": "Captioned",
                "transcript_source": "automatic",
                "report_path": "/archive/captioned/report.md",
                "transcript_path": "/archive/captioned/transcript/en/clean-deduped.txt",
                "has_placeholder_summary": True,
                "report_summary": None,
            },
            {
                "status": "metadata-only-no-captions",
                "video_id": "nocaps",
                "title": "No captions",
                "transcript_source": "none",
                "report_path": "/archive/nocaps/report.md",
                "transcript_path": None,
                "has_placeholder_summary": True,
                "report_summary": None,
            },
        ]

        needs_summary = self.module.needs_summary_entries(entries)

        self.assertEqual(["captioned"], [entry["video_id"] for entry in needs_summary])

    def test_validate_entry_reports_declared_compressed_corruption(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_s:
            root = Path(tmp_s)
            video_dir = root / "abc123"
            video_dir.mkdir()
            raw = b'{"id":"abc123"}'
            filename, stored, descriptor = self.module.metadata_storage.build_gzip_generation(raw)
            (video_dir / "metadata.json").write_bytes(raw)
            (video_dir / filename).write_bytes(stored[:-1] + bytes([stored[-1] ^ 1]))
            for name in ["manifest.json", "report.md", "subtitles-list.txt"]:
                (video_dir / name).write_text("{}\n" if name.endswith(".json") else "ok\n", encoding="utf-8")
            manifest = {
                "files": ["manifest.json", "metadata.json", filename, "report.md", "subtitles-list.txt"],
                "metadata_storage": descriptor,
            }
            entry = {
                "status": "metadata-only-no-captions",
                "video_id": "abc123",
                "transcript_source": "none",
                "manifest": manifest,
            }

            errors = self.module.validate_entry(root, entry)

            self.assertEqual(1, len(errors))
            self.assertIn("stored metadata SHA-256", errors[0])

    def test_validate_entry_can_require_filled_summaries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_s:
            root = Path(tmp_s)
            video_dir = root / "abc123"
            transcript_dir = video_dir / "transcript" / "en"
            transcript_dir.mkdir(parents=True)
            (video_dir / "manifest.json").write_text("{}\n", encoding="utf-8")
            (video_dir / "metadata.json").write_text("{}\n", encoding="utf-8")
            (video_dir / "subtitles-list.txt").write_text("ok\n", encoding="utf-8")
            (video_dir / "report.md").write_text(
                "# Report\n\n## Summary\nRaw transcript archival is complete. Summary not yet written; read later.\n\n## Detailed summary\nDetailed summary pending.\n\n## Full transcript\nText\n",
                encoding="utf-8",
            )
            (transcript_dir / "clean-deduped.txt").write_text("caption text\n", encoding="utf-8")
            entry = {
                "status": "created",
                "video_id": "abc123",
                "transcript_source": "automatic",
                "report_path": str(video_dir / "report.md"),
                "manifest": {
                    "files": [
                        "manifest.json",
                        "metadata.json",
                        "subtitles-list.txt",
                        "report.md",
                        "transcript/en/clean-deduped.txt",
                    ]
                },
            }

            errors = self.module.validate_entry(root, entry, require_summaries=True)

            self.assertIn("summary pending in report.md", errors)

    def test_sync_payload_from_reports_updates_summary_and_transcript_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_s:
            root = Path(tmp_s)
            video_dir = root / "abc123"
            transcript_dir = video_dir / "transcript" / "en"
            transcript_dir.mkdir(parents=True)
            for name in ["manifest.json", "metadata.json", "subtitles-list.txt"]:
                (video_dir / name).write_text("{}\n" if name.endswith(".json") else "ok\n", encoding="utf-8")
            (video_dir / "report.md").write_text(
                "# Report\n\n## Summary\nA filled report summary after agent review.\n\n## Detailed summary\n- Detail.\n\n## Full transcript\nText\n",
                encoding="utf-8",
            )
            (transcript_dir / "clean-deduped.txt").write_text("caption text\n", encoding="utf-8")
            payload = {
                "archive_root": str(root),
                "entries": [
                    {
                        "status": "created",
                        "video_id": "abc123",
                        "title": "Captioned",
                        "transcript_source": "automatic",
                        "report_path": str(video_dir / "report.md"),
                        "report_summary": None,
                        "manifest": {
                            "files": [
                                "manifest.json",
                                "metadata.json",
                                "subtitles-list.txt",
                                "report.md",
                                "transcript/en/clean-deduped.txt",
                            ]
                        },
                    }
                ],
            }

            synced = self.module.sync_payload_from_reports(payload=payload, archive_root=root, require_summaries=True)

            self.assertEqual("A filled report summary after agent review.", synced["entries"][0]["report_summary"])
            self.assertEqual(str(transcript_dir / "clean-deduped.txt"), synced["entries"][0]["transcript_path"])
            self.assertEqual([], synced["entries"][0]["validation_errors"])
            self.assertEqual([], synced["needs_summary"])

    def test_extract_batch_title_from_existing_index(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_s:
            index_path = Path(tmp_s) / "batch.md"
            index_path.write_text(
                "# YouTube Batch — YouTube batch 2026-06-03 15:47 KST\n\nInput links: 2\n",
                encoding="utf-8",
            )

            self.assertEqual(
                "YouTube batch 2026-06-03 15:47 KST",
                self.module.extract_batch_title_from_index(index_path),
            )

    def test_timestamp_zone_kst_changes_default_title_and_id_timezone(self) -> None:
        kst_now = self.module.timestamp_now("kst")

        self.assertEqual("KST", kst_now.tzname())
        self.assertTrue(self.module.default_batch_id(kst_now).endswith("-youtube-batch"))
        self.assertIn("KST", self.module.default_batch_title(kst_now))


if __name__ == "__main__":
    unittest.main()
