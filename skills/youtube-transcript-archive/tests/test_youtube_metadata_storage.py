import importlib.util
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "youtube_metadata_storage.py"
SPEC = importlib.util.spec_from_file_location("youtube_metadata_storage", MODULE_PATH)
assert SPEC and SPEC.loader
storage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(storage)


class MetadataStorageTests(unittest.TestCase):
    def make_video(self, raw: bytes = b'{"id":"abcdefghijk","title":"caf\u00e9"}\n'):
        temp = tempfile.TemporaryDirectory()
        video = Path(temp.name) / "abcdefghijk"
        video.mkdir()
        (video / "metadata.json").write_bytes(raw)
        manifest = {
            "video_id": "abcdefghijk",
            "files": ["manifest.json", "metadata.json", "subtitles-list.txt", "report.md"],
        }
        (video / "manifest.json").write_text(json.dumps(manifest) + "\n", encoding="utf-8")
        (video / "subtitles-list.txt").write_text("en\n", encoding="utf-8")
        (video / "report.md").write_text("# report\n", encoding="utf-8")
        return temp, video, manifest, raw

    def write_generation(self, video: Path, raw: bytes, *, state: str = "dual"):
        filename, compressed, descriptor = storage.build_gzip_generation(raw, state=state)
        (video / filename).write_bytes(compressed)
        return filename, compressed, descriptor

    def test_deterministic_gzip_round_trip_and_mtime_zero(self):
        raw = '{"message":"h\u00e9llo \ud55c\uad6d"}\n'.encode()
        first = storage.deterministic_gzip(raw)
        second = storage.deterministic_gzip(raw)
        self.assertEqual(first, second)
        self.assertEqual(b"\x00\x00\x00\x00", first[4:8])
        self.assertEqual(raw, storage._bounded_gunzip(first, expected_bytes=len(raw), max_raw_bytes=len(raw)))

    def test_empty_json_object_is_valid(self):
        raw = b"{}\n"
        temp, video, manifest, _ = self.make_video(raw)
        self.addCleanup(temp.cleanup)
        updated = storage.write_dual_from_plaintext(video, manifest)
        self.assertEqual({}, storage.read_metadata_json(video, updated))

    def test_maximum_sized_valid_input_is_bounded(self):
        raw = json.dumps({"id": "abcdefghijk", "data": "x" * 4000}, separators=(",", ":")).encode()
        temp, video, manifest, _ = self.make_video(raw)
        self.addCleanup(temp.cleanup)
        updated = storage.write_dual_from_plaintext(video, manifest, max_raw_bytes=len(raw))
        self.assertEqual(raw, storage.read_metadata_bytes(video, updated, max_raw_bytes=len(raw)))
        with self.assertRaises(storage.MetadataLimitError):
            storage.read_metadata_bytes(video, updated, max_raw_bytes=len(raw) - 1)

    def test_legacy_plaintext_reader(self):
        temp, video, manifest, raw = self.make_video()
        self.addCleanup(temp.cleanup)
        self.assertEqual(raw, storage.read_metadata_bytes(video, manifest))
        self.assertEqual("abcdefghijk", storage.read_metadata_json(video, manifest)["id"])

    def test_read_flags_include_binary_mode_when_available(self):
        synthetic_binary_flag = 1 << 29
        with mock.patch.object(storage.os, "O_BINARY", synthetic_binary_flag, create=True):
            self.assertEqual(synthetic_binary_flag, storage._read_only_flags() & synthetic_binary_flag)

    def test_windows_identity_ignores_only_unstable_ctime(self):
        fields = {
            "st_dev": 1,
            "st_ino": 2,
            "st_mode": 0o100600,
            "st_nlink": 1,
            "st_size": 20,
            "st_mtime_ns": 30,
        }
        left = mock.Mock(**fields, st_ctime_ns=40)
        right = mock.Mock(**fields, st_ctime_ns=41)
        with mock.patch.object(storage.os, "name", "nt"):
            self.assertTrue(storage._same_file_identity(left, right))
            right.st_size = 21
            self.assertFalse(storage._same_file_identity(left, right))
        right.st_size = 20
        with mock.patch.object(storage.os, "name", "posix"):
            self.assertFalse(storage._same_file_identity(left, right))

    def test_temp_mode_falls_back_when_fchmod_is_unavailable(self):
        temp, video, _manifest, _raw = self.make_video()
        self.addCleanup(temp.cleanup)
        fd, name = tempfile.mkstemp(dir=video)
        path = Path(name)
        self.addCleanup(lambda: path.unlink(missing_ok=True))
        self.addCleanup(lambda: os.close(fd))
        real_chmod = os.chmod
        with mock.patch.object(storage.os, "fchmod", None, create=True):
            with mock.patch.object(storage.os, "chmod", wraps=real_chmod) as chmod:
                storage._set_temp_mode(fd, path, 0o600)
                chmod.assert_called_once_with(path, 0o600)

    def test_directory_fsync_is_skipped_on_windows(self):
        temp, video, _manifest, _raw = self.make_video()
        self.addCleanup(temp.cleanup)
        with mock.patch.object(storage.os, "name", "nt"):
            with mock.patch.object(storage.os, "open", side_effect=AssertionError("directory open attempted")):
                storage._fsync_directory(video)

    def test_short_writes_are_completed(self):
        sink = bytearray()

        def short_write(_fd, value):
            part = bytes(value[:3])
            sink.extend(part)
            return len(part)

        storage._write_all(123, b"0123456789", write_fn=short_write)
        self.assertEqual(b"0123456789", bytes(sink))

    def test_no_progress_write_fails(self):
        with self.assertRaises(OSError):
            storage._write_all(123, b"x", write_fn=lambda _fd, _value: 0)

    def test_unreferenced_interrupted_temp_is_ignored(self):
        temp, video, manifest, raw = self.make_video()
        self.addCleanup(temp.cleanup)
        (video / ".metadata.json.tmp-interrupted").write_bytes(b"partial")
        self.assertEqual(raw, storage.read_metadata_bytes(video, manifest))

    def test_symlink_is_rejected(self):
        temp, video, manifest, _ = self.make_video()
        self.addCleanup(temp.cleanup)
        real = video / "metadata.json"
        outside = Path(temp.name) / "outside.json"
        real.replace(outside)
        real.symlink_to(outside)
        with self.assertRaises(storage.MetadataPathError):
            storage.read_metadata_bytes(video, manifest)

    def test_symlinked_video_directory_is_rejected(self):
        temp, video, manifest, _ = self.make_video()
        self.addCleanup(temp.cleanup)
        linked = Path(temp.name) / "linked-video"
        linked.symlink_to(video, target_is_directory=True)
        with self.assertRaises(storage.MetadataPathError):
            storage.read_metadata_bytes(linked, manifest)

    def test_hard_link_is_rejected(self):
        temp, video, manifest, _ = self.make_video()
        self.addCleanup(temp.cleanup)
        os.link(video / "metadata.json", Path(temp.name) / "metadata-hardlink.json")
        with self.assertRaises(storage.MetadataPathError):
            storage.read_metadata_bytes(video, manifest)

    def test_root_escape_filename_is_rejected(self):
        descriptor = storage.descriptor_for_plaintext(b"{}\n")
        descriptor["canonical_filename"] = "../metadata.json"
        with self.assertRaises(storage.MetadataPathError):
            storage.validate_descriptor(descriptor)

    def test_unsupported_codec_is_rejected(self):
        descriptor = storage.descriptor_for_plaintext(b"{}\n")
        descriptor["codec"] = "xz"
        with self.assertRaises(storage.MetadataCodecError):
            storage.validate_descriptor(descriptor)

    def test_unsupported_gzip_version_is_rejected(self):
        _, _, descriptor = storage.build_gzip_generation(b"{}\n")
        descriptor["codec_version"] = "gzip-9"
        with self.assertRaises(storage.MetadataCodecError):
            storage.validate_descriptor(descriptor)

    def test_truncated_gzip_is_rejected_after_matching_stored_hash(self):
        temp, video, manifest, raw = self.make_video()
        self.addCleanup(temp.cleanup)
        filename, compressed, descriptor = self.write_generation(video, raw)
        truncated = compressed[:-5]
        (video / filename).write_bytes(truncated)
        descriptor["stored_bytes"] = len(truncated)
        descriptor["stored_sha256"] = storage.sha256_bytes(truncated)
        updated = storage.prepare_manifest_with_storage(manifest, descriptor)
        with self.assertRaises(storage.MetadataIntegrityError):
            storage.read_metadata_bytes(video, updated)

    def test_invalid_deflate_is_rejected_after_matching_stored_hash(self):
        temp, video, manifest, raw = self.make_video()
        self.addCleanup(temp.cleanup)
        _filename, _compressed, descriptor = self.write_generation(video, raw)
        invalid_deflate = b"\x1f\x8b\x08\x00\x00\x00\x00\x00\x00\xff\x07" + b"\x00" * 8
        selected = video / descriptor["canonical_filename"]
        selected.write_bytes(invalid_deflate)
        descriptor["stored_bytes"] = len(invalid_deflate)
        descriptor["stored_sha256"] = storage.sha256_bytes(invalid_deflate)
        updated = storage.prepare_manifest_with_storage(manifest, descriptor)
        with self.assertRaises(storage.MetadataIntegrityError):
            storage.read_metadata_bytes(video, updated)

    def test_stored_checksum_mismatch_is_rejected(self):
        temp, video, manifest, raw = self.make_video()
        self.addCleanup(temp.cleanup)
        filename, compressed, descriptor = self.write_generation(video, raw)
        mutated = bytearray(compressed)
        mutated[-1] ^= 1
        (video / filename).write_bytes(mutated)
        updated = storage.prepare_manifest_with_storage(manifest, descriptor)
        with self.assertRaises(storage.MetadataIntegrityError):
            storage.read_metadata_bytes(video, updated)

    def test_nondeterministic_gzip_is_rejected_even_when_descriptor_matches(self):
        temp, video, manifest, raw = self.make_video()
        self.addCleanup(temp.cleanup)
        filename, _compressed, descriptor = self.write_generation(video, raw)
        import gzip

        nondeterministic = gzip.compress(raw, compresslevel=6, mtime=123)
        (video / filename).write_bytes(nondeterministic)
        descriptor["stored_bytes"] = len(nondeterministic)
        descriptor["stored_sha256"] = storage.sha256_bytes(nondeterministic)
        updated = storage.prepare_manifest_with_storage(manifest, descriptor)
        with self.assertRaisesRegex(storage.MetadataIntegrityError, "deterministic gzip"):
            storage.read_metadata_bytes(video, updated)

    def test_filename_raw_hash_mismatch_is_rejected(self):
        _, _, descriptor = storage.build_gzip_generation(b"{}\n")
        descriptor["raw_sha256"] = "0" * 64
        with self.assertRaises(storage.MetadataIntegrityError):
            storage.validate_descriptor(descriptor)

    def test_gzip_bomb_declared_size_is_rejected_before_read(self):
        temp, video, manifest, raw = self.make_video()
        self.addCleanup(temp.cleanup)
        _filename, _compressed, descriptor = self.write_generation(video, raw)
        descriptor["raw_bytes"] = 2 * 1024 * 1024
        updated = storage.prepare_manifest_with_storage(manifest, descriptor)
        with self.assertRaises(storage.MetadataLimitError):
            storage.read_metadata_bytes(video, updated, max_raw_bytes=1024)

    def test_dual_state_plaintext_divergence_is_rejected(self):
        temp, video, manifest, raw = self.make_video()
        self.addCleanup(temp.cleanup)
        _filename, _compressed, descriptor = self.write_generation(video, raw)
        updated = storage.prepare_manifest_with_storage(manifest, descriptor)
        (video / "metadata.json").write_bytes(b'{"id":"abcdefghijk","different":true}\n')
        with self.assertRaises(storage.MetadataIntegrityError):
            storage.read_metadata_bytes(video, updated)

    def test_missing_declared_compressed_file_never_falls_back(self):
        temp, video, manifest, raw = self.make_video()
        self.addCleanup(temp.cleanup)
        _filename, _compressed, descriptor = storage.build_gzip_generation(raw)
        updated = storage.prepare_manifest_with_storage(manifest, descriptor)
        self.assertTrue((video / "metadata.json").is_file())
        with self.assertRaises(storage.MetadataIntegrityError):
            storage.read_metadata_bytes(video, updated)

    def test_invalid_utf8_and_json_are_rejected(self):
        with self.assertRaises(storage.MetadataIntegrityError):
            storage.parse_metadata_json(b"\xff")
        with self.assertRaises(storage.MetadataIntegrityError):
            storage.parse_metadata_json(b"{")
        with self.assertRaises(storage.MetadataIntegrityError):
            storage.parse_metadata_json(b"[]")

    def test_immutable_generation_reuses_exact_bytes_and_rejects_conflict(self):
        temp, video, _manifest, raw = self.make_video()
        self.addCleanup(temp.cleanup)
        filename, compressed, _descriptor = storage.build_gzip_generation(raw)
        self.assertEqual("created", storage.write_immutable_generation(video, filename, compressed))
        self.assertEqual("reused", storage.write_immutable_generation(video, filename, compressed))
        with self.assertRaises(storage.MetadataIntegrityError):
            storage.write_immutable_generation(video, filename, compressed + b"x")

    def test_plaintext_writer_preserves_or_replaces_exact_bytes_explicitly(self):
        temp, video, _manifest, original = self.make_video()
        self.addCleanup(temp.cleanup)
        replacement = b'{"id":"abcdefghijk","title":"replacement"}\n'
        self.assertEqual(
            original,
            storage.write_plaintext_metadata(video, replacement, replace=False),
        )
        self.assertEqual(original, (video / "metadata.json").read_bytes())
        self.assertEqual(
            replacement,
            storage.write_plaintext_metadata(video, replacement, replace=True),
        )
        self.assertEqual(replacement, (video / "metadata.json").read_bytes())

    def test_prepare_dual_generation_fully_validates_before_return(self):
        temp, video, _manifest, raw = self.make_video()
        self.addCleanup(temp.cleanup)
        descriptor = storage.prepare_dual_generation(video, raw)
        self.assertEqual("dual", descriptor["state"])
        self.assertEqual(raw, storage.read_metadata_bytes(video, {"metadata_storage": descriptor}))

    def test_prepare_compressed_generation_does_not_require_plaintext(self):
        temp, video, _manifest, raw = self.make_video()
        self.addCleanup(temp.cleanup)
        (video / "metadata.json").unlink()
        descriptor = storage.prepare_compressed_generation(video, raw)
        self.assertEqual("compressed", descriptor["state"])
        self.assertFalse((video / "metadata.json").exists())
        self.assertEqual(raw, storage.read_metadata_bytes(video, {"metadata_storage": descriptor}))

    def test_atomic_write_refuses_target_that_appears_mid_write(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        target = Path(temp.name) / "target.bin"
        original = storage._write_all

        def race(fd, data, **kwargs):
            original(fd, data, **kwargs)
            target.write_bytes(b"concurrent")

        storage._write_all = race
        self.addCleanup(setattr, storage, "_write_all", original)
        with self.assertRaisesRegex(storage.MetadataIntegrityError, "appeared"):
            storage.durable_atomic_write(target, b"ours")
        self.assertEqual(b"concurrent", target.read_bytes())
        self.assertEqual([], list(Path(temp.name).glob(".target.bin.tmp-*")))

    @unittest.skipIf(os.name == "nt", "POSIX owner/mode validation")
    def test_writer_lock_rejects_a_non_private_lock_root(self):
        with tempfile.TemporaryDirectory() as tmp_s:
            lock_root = Path(tmp_s) / f"openclaw-youtube-metadata-locks-{os.geteuid()}"
            lock_root.mkdir(mode=0o755)
            lock_root.chmod(0o755)
            with mock.patch.object(storage.tempfile, "gettempdir", return_value=tmp_s):
                with self.assertRaisesRegex(storage.MetadataPathError, "owner-only"):
                    storage._lock_path(Path(tmp_s) / "target", "target")

    def test_atomic_write_serializes_contender_started_immediately_before_replace(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        target = Path(temp.name) / "target.bin"
        target.write_bytes(b"old")
        original_replace = storage.os.replace
        main_thread = threading.current_thread()
        contender_started = threading.Event()
        contender_done = threading.Event()
        replacement_order: list[str] = []

        def contender() -> None:
            contender_started.set()
            storage.durable_atomic_write(target, b"concurrent")
            contender_done.set()

        worker = threading.Thread(target=contender, daemon=True)

        def interleaved_replace(source, destination):
            if Path(destination) == target:
                if threading.current_thread() is main_thread:
                    worker.start()
                    self.assertTrue(contender_started.wait(1))
                    self.assertFalse(
                        contender_done.wait(0.05),
                        "contender passed the target lock before the first replace",
                    )
                    replacement_order.append("first")
                else:
                    replacement_order.append("contender")
            return original_replace(source, destination)

        with mock.patch.object(storage.os, "replace", side_effect=interleaved_replace):
            storage.durable_atomic_write(target, b"ours")
            worker.join(2)

        self.assertFalse(worker.is_alive())
        self.assertEqual(["first", "contender"], replacement_order)
        self.assertEqual(b"concurrent", target.read_bytes())

    def test_manifest_file_validation_rejects_backslash_and_symlink_parent(self):
        temp, video, manifest, _raw = self.make_video()
        self.addCleanup(temp.cleanup)
        (video / "report.md").write_text("ok\n", encoding="utf-8")
        listed = dict(manifest)
        listed["files"] = ["manifest.json", "metadata.json", "report.md"]
        (video / "manifest.json").write_text("{}\n", encoding="utf-8")
        self.assertEqual(listed["files"], storage.validate_manifest_files(video, listed))
        listed["files"] = ["report\\evil.md"]
        with self.assertRaises(storage.MetadataPathError):
            storage.validate_manifest_files(video, listed)
        outside = Path(temp.name) / "outside"
        outside.mkdir()
        (outside / "file.txt").write_text("outside\n", encoding="utf-8")
        (video / "linked").symlink_to(outside, target_is_directory=True)
        listed["files"] = ["linked/file.txt"]
        with self.assertRaises(storage.MetadataPathError):
            storage.validate_manifest_files(video, listed)

    def test_manifest_shape_must_be_non_empty_string_list(self):
        descriptor = storage.descriptor_for_plaintext(b"{}\n")
        for files in (None, {}, [], [1]):
            with self.subTest(files=files):
                with self.assertRaises(storage.MetadataManifestError):
                    storage.prepare_manifest_with_storage({"files": files}, descriptor)

    def test_manifest_commit_is_last_and_interruption_preserves_old_manifest(self):
        temp, video, manifest, raw = self.make_video()
        self.addCleanup(temp.cleanup)
        original_manifest = (video / "manifest.json").read_bytes()
        events = []

        def interrupt(step):
            events.append(step)
            if step == "generation_verified":
                raise RuntimeError("forced interruption")

        with self.assertRaisesRegex(RuntimeError, "forced interruption"):
            storage.write_dual_from_plaintext(video, manifest, on_step=interrupt)
        self.assertEqual(["generation_committed", "generation_verified"], events)
        self.assertEqual(original_manifest, (video / "manifest.json").read_bytes())
        self.assertEqual(raw, storage.read_metadata_bytes(video, manifest))
        self.assertEqual(1, len(list(video.glob("metadata.*.json.gz"))))

    def test_successful_commit_order_and_exact_readback(self):
        temp, video, manifest, raw = self.make_video()
        self.addCleanup(temp.cleanup)
        events = []
        committed = storage.write_dual_from_plaintext(video, manifest, on_step=events.append)
        self.assertEqual(
            ["generation_committed", "generation_verified", "manifest_committed", "manifest_verified"],
            events,
        )
        self.assertEqual(raw, storage.read_metadata_bytes(video, committed))
        disk_manifest = storage.read_manifest(video)
        self.assertEqual(committed, disk_manifest)
        selected = committed["metadata_storage"]["canonical_filename"]
        self.assertIn(selected, committed["files"])


if __name__ == "__main__":
    unittest.main()
