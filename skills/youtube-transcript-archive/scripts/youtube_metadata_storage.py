#!/usr/bin/env python3
"""Lossless, bounded storage helpers for canonical YouTube metadata.

The manifest selects the canonical generation. Legacy archives without a
``metadata_storage`` descriptor continue to read ``metadata.json``. A declared
compressed generation never falls back to plaintext.
"""
from __future__ import annotations

import copy
import gzip
import hashlib
import io
import json
import os
import re
import stat
import tempfile
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Callable, Mapping

SCHEMA = "openclaw.youtube-metadata-storage.v1"
GZIP_CODEC_VERSION = "gzip-6-mtime0-v1"
IDENTITY_CODEC_VERSION = "identity-v1"
DEFAULT_MAX_RAW_BYTES = 64 * 1024 * 1024
DEFAULT_MAX_STORED_BYTES = 64 * 1024 * 1024
_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_GZIP_NAME_RE = re.compile(r"^metadata\.([0-9a-f]{64})\.json\.gz$")


class MetadataStorageError(ValueError):
    """Base class for fail-closed metadata storage errors."""


class MetadataPathError(MetadataStorageError):
    """A selected path is unsafe or outside the video directory."""


class MetadataIntegrityError(MetadataStorageError):
    """Stored or recovered bytes do not match their descriptor."""


class MetadataLimitError(MetadataStorageError):
    """Stored or recovered bytes exceed the configured bound."""


class MetadataCodecError(MetadataStorageError):
    """The descriptor requests an unsupported codec or version."""


class MetadataManifestError(MetadataStorageError):
    """The manifest or metadata_storage descriptor is invalid."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def deterministic_gzip(raw: bytes, *, compresslevel: int = 6) -> bytes:
    """Return one deterministic gzip member with an empty filename and mtime 0."""
    if compresslevel != 6:
        raise MetadataCodecError("only deterministic gzip level 6 is supported")
    buffer = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=buffer, compresslevel=compresslevel, mtime=0) as handle:
        handle.write(raw)
    return buffer.getvalue()


def _require_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise MetadataManifestError(f"{field} must be a non-negative integer")
    return value


def _require_hash(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _HASH_RE.fullmatch(value):
        raise MetadataManifestError(f"{field} must be a lowercase SHA-256 digest")
    return value


def _validate_filename(filename: Any) -> str:
    if not isinstance(filename, str) or not filename or filename in {".", ".."}:
        raise MetadataPathError("canonical_filename must be a non-empty basename")
    if Path(filename).name != filename or "/" in filename or "\\" in filename or "\x00" in filename:
        raise MetadataPathError("canonical_filename must not contain a path")
    return filename


def validate_descriptor(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise MetadataManifestError("metadata_storage must be an object")
    required = {
        "schema",
        "state",
        "canonical_filename",
        "codec",
        "codec_version",
        "raw_bytes",
        "raw_sha256",
        "stored_bytes",
        "stored_sha256",
    }
    missing = sorted(required - value.keys())
    if missing:
        raise MetadataManifestError(f"metadata_storage missing fields: {', '.join(missing)}")
    if value.get("schema") != SCHEMA:
        raise MetadataManifestError(f"unsupported metadata_storage schema: {value.get('schema')!r}")
    state = value.get("state")
    if state not in {"plaintext", "dual", "compressed"}:
        raise MetadataManifestError(f"unsupported metadata_storage state: {state!r}")
    filename = _validate_filename(value.get("canonical_filename"))
    codec = value.get("codec")
    codec_version = value.get("codec_version")
    if codec == "identity":
        if codec_version != IDENTITY_CODEC_VERSION or filename != "metadata.json" or state != "plaintext":
            raise MetadataCodecError("identity metadata must use metadata.json, identity-v1, and plaintext state")
    elif codec == "gzip":
        if codec_version != GZIP_CODEC_VERSION:
            raise MetadataCodecError(f"unsupported gzip codec version: {codec_version!r}")
        match = _GZIP_NAME_RE.fullmatch(filename)
        if not match:
            raise MetadataPathError("gzip canonical_filename must be metadata.<raw_sha256>.json.gz")
        if match.group(1) != value.get("raw_sha256"):
            raise MetadataIntegrityError("canonical filename hash does not match raw_sha256")
        if state not in {"dual", "compressed"}:
            raise MetadataManifestError("gzip metadata state must be dual or compressed")
    else:
        raise MetadataCodecError(f"unsupported metadata codec: {codec!r}")
    _require_int(value.get("raw_bytes"), "raw_bytes")
    _require_int(value.get("stored_bytes"), "stored_bytes")
    _require_hash(value.get("raw_sha256"), "raw_sha256")
    _require_hash(value.get("stored_sha256"), "stored_sha256")
    return dict(value)


def descriptor_for_plaintext(raw: bytes) -> dict[str, Any]:
    digest = sha256_bytes(raw)
    return {
        "schema": SCHEMA,
        "state": "plaintext",
        "canonical_filename": "metadata.json",
        "codec": "identity",
        "codec_version": IDENTITY_CODEC_VERSION,
        "raw_bytes": len(raw),
        "raw_sha256": digest,
        "stored_bytes": len(raw),
        "stored_sha256": digest,
    }


def build_gzip_generation(raw: bytes, *, state: str = "dual") -> tuple[str, bytes, dict[str, Any]]:
    if state not in {"dual", "compressed"}:
        raise MetadataManifestError("gzip generation state must be dual or compressed")
    raw_hash = sha256_bytes(raw)
    stored = deterministic_gzip(raw)
    filename = f"metadata.{raw_hash}.json.gz"
    descriptor = {
        "schema": SCHEMA,
        "state": state,
        "canonical_filename": filename,
        "codec": "gzip",
        "codec_version": GZIP_CODEC_VERSION,
        "raw_bytes": len(raw),
        "raw_sha256": raw_hash,
        "stored_bytes": len(stored),
        "stored_sha256": sha256_bytes(stored),
    }
    validate_descriptor(descriptor)
    return filename, stored, descriptor


def _real_video_directory(video_dir: Path) -> Path:
    try:
        directory_stat = video_dir.lstat()
    except FileNotFoundError as exc:
        raise MetadataPathError(f"video directory is missing: {video_dir}") from exc
    if not stat.S_ISDIR(directory_stat.st_mode) or stat.S_ISLNK(directory_stat.st_mode):
        raise MetadataPathError(f"video directory is not a real directory: {video_dir}")
    base = video_dir.resolve(strict=True)
    if not base.is_dir():
        raise MetadataPathError(f"video directory is not a directory: {base}")
    return base


def _safe_child(video_dir: Path, filename: str) -> Path:
    name = _validate_filename(filename)
    base = _real_video_directory(video_dir)
    candidate = base / name
    if candidate.parent != base:
        raise MetadataPathError("selected metadata path escapes the video directory")
    return candidate


def safe_relative_file(video_dir: Path, relative: Any) -> Path:
    """Return one listed regular file after rejecting path and link traversal."""
    if not isinstance(relative, str) or not relative or "\\" in relative or "\x00" in relative:
        raise MetadataPathError("manifest file path must be a non-empty POSIX relative path")
    posix = PurePosixPath(relative)
    windows = PureWindowsPath(relative)
    if (
        posix.is_absolute()
        or windows.is_absolute()
        or bool(windows.drive)
        or any(part in {"", ".", ".."} for part in posix.parts)
    ):
        raise MetadataPathError(f"unsafe manifest file path: {relative!r}")
    base = _real_video_directory(video_dir)
    current = base
    for index, part in enumerate(posix.parts):
        current = current / part
        try:
            value = current.lstat()
        except FileNotFoundError as exc:
            raise MetadataIntegrityError(f"listed archive file is missing: {relative}") from exc
        if stat.S_ISLNK(value.st_mode):
            raise MetadataPathError(f"listed archive path contains a symlink: {relative}")
        if index < len(posix.parts) - 1:
            if not stat.S_ISDIR(value.st_mode):
                raise MetadataPathError(f"listed archive parent is not a directory: {relative}")
        elif not stat.S_ISREG(value.st_mode) or value.st_nlink != 1:
            raise MetadataPathError(f"listed archive path is not a single-link regular file: {relative}")
    return current


def validate_manifest_files(video_dir: Path, manifest: Mapping[str, Any]) -> list[str]:
    files = manifest.get("files") if isinstance(manifest, Mapping) else None
    if not isinstance(files, list) or not files or not all(isinstance(item, str) and item for item in files):
        raise MetadataManifestError("manifest files must be a non-empty string list")
    for relative in files:
        safe_relative_file(video_dir, relative)
    return list(files)


def _same_file_identity(left: os.stat_result, right: os.stat_result) -> bool:
    fields = ("st_dev", "st_ino", "st_mode", "st_nlink", "st_size", "st_mtime_ns")
    if os.name != "nt":
        fields += ("st_ctime_ns",)
    return all(getattr(left, field) == getattr(right, field) for field in fields)


def _regular_file_stat(path: Path) -> os.stat_result:
    try:
        value = path.lstat()
    except FileNotFoundError as exc:
        raise MetadataIntegrityError(f"selected metadata file is missing: {path.name}") from exc
    if not stat.S_ISREG(value.st_mode) or stat.S_ISLNK(value.st_mode):
        raise MetadataPathError(f"selected metadata path is not a regular file: {path.name}")
    if value.st_nlink != 1:
        raise MetadataPathError(f"selected metadata file has unexpected link count: {path.name}")
    return value


def _read_only_flags() -> int:
    return (
        os.O_RDONLY
        | getattr(os, "O_BINARY", 0)
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )


def read_regular_bytes(path: Path, *, max_bytes: int) -> bytes:
    if max_bytes < 0:
        raise MetadataLimitError("max_bytes must be non-negative")
    before = _regular_file_stat(path)
    if before.st_size > max_bytes:
        raise MetadataLimitError(f"file exceeds configured byte limit: {path.name}")
    flags = _read_only_flags()
    try:
        fd = os.open(path, flags)
    except FileNotFoundError as exc:
        raise MetadataIntegrityError(f"selected metadata file changed while opening: {path.name}") from exc
    except OSError as exc:
        raise MetadataPathError(f"unable to open selected metadata file safely: {path.name}") from exc
    chunks: list[bytes] = []
    total = 0
    try:
        opened = os.fstat(fd)
        if not _same_file_identity(before, opened) or opened.st_nlink != 1 or not stat.S_ISREG(opened.st_mode):
            raise MetadataIntegrityError(f"selected metadata file changed while opening: {path.name}")
        while True:
            chunk = os.read(fd, min(1024 * 1024, max_bytes - total + 1))
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise MetadataLimitError(f"file exceeds configured byte limit: {path.name}")
            chunks.append(chunk)
        after = os.fstat(fd)
        if not _same_file_identity(opened, after) or after.st_size != total:
            raise MetadataIntegrityError(f"selected metadata file changed while reading: {path.name}")
    finally:
        os.close(fd)
    final = _regular_file_stat(path)
    if not _same_file_identity(before, final):
        raise MetadataIntegrityError(f"selected metadata file changed after reading: {path.name}")
    return b"".join(chunks)


def _bounded_gunzip(stored: bytes, *, expected_bytes: int, max_raw_bytes: int) -> bytes:
    if expected_bytes > max_raw_bytes:
        raise MetadataLimitError("declared raw metadata length exceeds configured limit")
    output = bytearray()
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(stored), mode="rb") as handle:
            while True:
                chunk = handle.read(
                    min(
                        1024 * 1024,
                        max_raw_bytes - len(output) + 1,
                        expected_bytes - len(output) + 1,
                    )
                )
                if not chunk:
                    break
                output.extend(chunk)
                if len(output) > max_raw_bytes or len(output) > expected_bytes:
                    raise MetadataLimitError("decompressed metadata exceeds declared or configured limit")
    except MetadataStorageError:
        raise
    except (EOFError, OSError, gzip.BadGzipFile) as exc:
        raise MetadataIntegrityError("invalid or truncated gzip metadata") from exc
    return bytes(output)


def _validate_recovered(raw: bytes, descriptor: Mapping[str, Any]) -> None:
    if len(raw) != descriptor["raw_bytes"]:
        raise MetadataIntegrityError("recovered metadata length does not match raw_bytes")
    if sha256_bytes(raw) != descriptor["raw_sha256"]:
        raise MetadataIntegrityError("recovered metadata SHA-256 does not match raw_sha256")


def read_metadata_bytes(
    video_dir: Path,
    manifest: Mapping[str, Any],
    *,
    max_raw_bytes: int = DEFAULT_MAX_RAW_BYTES,
    max_stored_bytes: int = DEFAULT_MAX_STORED_BYTES,
) -> bytes:
    if not isinstance(manifest, Mapping):
        raise MetadataManifestError("manifest must be an object")
    storage = manifest.get("metadata_storage")
    if storage is None:
        raw = read_regular_bytes(_safe_child(video_dir, "metadata.json"), max_bytes=max_raw_bytes)
        return raw
    descriptor = validate_descriptor(storage)
    if descriptor["raw_bytes"] > max_raw_bytes or descriptor["stored_bytes"] > max_stored_bytes:
        raise MetadataLimitError("declared metadata length exceeds configured limit")
    selected = _safe_child(video_dir, descriptor["canonical_filename"])
    stored = read_regular_bytes(selected, max_bytes=max_stored_bytes)
    if len(stored) != descriptor["stored_bytes"]:
        raise MetadataIntegrityError("stored metadata length does not match stored_bytes")
    if sha256_bytes(stored) != descriptor["stored_sha256"]:
        raise MetadataIntegrityError("stored metadata SHA-256 does not match stored_sha256")
    if descriptor["codec"] == "identity":
        raw = stored
    elif descriptor["codec"] == "gzip":
        raw = _bounded_gunzip(stored, expected_bytes=descriptor["raw_bytes"], max_raw_bytes=max_raw_bytes)
    else:  # validate_descriptor already rejects this branch.
        raise MetadataCodecError(f"unsupported metadata codec: {descriptor['codec']!r}")
    _validate_recovered(raw, descriptor)
    if descriptor["codec"] == "gzip" and deterministic_gzip(raw) != stored:
        raise MetadataIntegrityError("stored metadata does not match deterministic gzip codec version")
    if descriptor["state"] == "dual":
        twin = read_regular_bytes(_safe_child(video_dir, "metadata.json"), max_bytes=max_raw_bytes)
        if len(twin) != descriptor["raw_bytes"] or sha256_bytes(twin) != descriptor["raw_sha256"]:
            raise MetadataIntegrityError("plaintext and compressed metadata twins diverge")
    return raw


def parse_metadata_json(raw: bytes) -> dict[str, Any]:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise MetadataIntegrityError("metadata is not valid UTF-8") from exc
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise MetadataIntegrityError("metadata is not valid JSON") from exc
    if not isinstance(value, dict):
        raise MetadataIntegrityError("metadata JSON must be an object")
    return value


def read_metadata_json(
    video_dir: Path,
    manifest: Mapping[str, Any],
    *,
    max_raw_bytes: int = DEFAULT_MAX_RAW_BYTES,
    max_stored_bytes: int = DEFAULT_MAX_STORED_BYTES,
) -> dict[str, Any]:
    return parse_metadata_json(
        read_metadata_bytes(
            video_dir,
            manifest,
            max_raw_bytes=max_raw_bytes,
            max_stored_bytes=max_stored_bytes,
        )
    )


def _write_all(fd: int, data: bytes, *, write_fn: Callable[[int, bytes], int] = os.write) -> None:
    view = memoryview(data)
    offset = 0
    while offset < len(view):
        written = write_fn(fd, view[offset:])
        if not isinstance(written, int) or written <= 0:
            raise OSError("write returned no progress")
        offset += written


def _fsync_directory(directory: Path) -> None:
    if os.name == "nt":
        return
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_CLOEXEC", 0)
    fd = os.open(directory, flags)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _set_temp_mode(fd: int, path: Path, mode: int) -> None:
    fchmod = getattr(os, "fchmod", None)
    if fchmod is not None:
        fchmod(fd, mode)
    else:
        os.chmod(path, mode)


def durable_atomic_write(path: Path, data: bytes, *, mode: int = 0o600) -> None:
    """Write through a same-directory temp, fsync, replace, and sync the directory where supported.

    The target identity is rechecked immediately before replacement so a
    concurrent writer cannot be overwritten silently.
    """
    unresolved_parent = path.parent.absolute()
    parent = path.parent.resolve(strict=True)
    if not parent.is_dir() or unresolved_parent != parent:
        raise MetadataPathError("target parent is not a stable real directory")
    existing: os.stat_result | None = None
    if path.exists() or path.is_symlink():
        existing = path.lstat()
        if not stat.S_ISREG(existing.st_mode) or stat.S_ISLNK(existing.st_mode) or existing.st_nlink != 1:
            raise MetadataPathError(f"refusing to replace unsafe target: {path.name}")
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.tmp-", dir=parent)
    temp = Path(temp_name)
    try:
        _set_temp_mode(fd, temp, mode)
        _write_all(fd, data)
        os.fsync(fd)
        os.close(fd)
        fd = -1
        try:
            current = path.lstat()
        except FileNotFoundError:
            current = None
        if existing is None and current is not None:
            raise MetadataIntegrityError(f"target appeared during atomic write: {path.name}")
        if existing is not None and (current is None or not _same_file_identity(existing, current)):
            raise MetadataIntegrityError(f"target changed during atomic write: {path.name}")
        os.replace(temp, path)
        _fsync_directory(parent)
    finally:
        if fd >= 0:
            os.close(fd)
        try:
            temp.unlink()
        except FileNotFoundError:
            pass


def write_immutable_generation(video_dir: Path, filename: str, stored: bytes) -> str:
    """Commit one content-named generation, reusing only exact existing bytes."""
    target = _safe_child(video_dir, filename)
    if target.exists() or target.is_symlink():
        existing = read_regular_bytes(target, max_bytes=max(len(stored), 1))
        if existing != stored:
            raise MetadataIntegrityError("immutable generation already exists with different bytes")
        return "reused"
    durable_atomic_write(target, stored)
    verified = read_regular_bytes(target, max_bytes=max(len(stored), 1))
    if verified != stored:
        raise MetadataIntegrityError("immutable generation readback mismatch")
    return "created"


def write_plaintext_metadata(
    video_dir: Path,
    raw: bytes,
    *,
    replace: bool,
    max_raw_bytes: int = DEFAULT_MAX_RAW_BYTES,
) -> bytes:
    """Create or explicitly replace ``metadata.json`` and verify exact bytes.

    When replacement is disabled, an existing valid plaintext record is kept
    byte-for-byte. This preserves the original canonical record on reuse paths.
    """
    if len(raw) > max_raw_bytes:
        raise MetadataLimitError("plaintext metadata exceeds configured byte limit")
    parse_metadata_json(raw)
    target = _safe_child(video_dir, "metadata.json")
    if target.exists() or target.is_symlink():
        existing = read_regular_bytes(target, max_bytes=max_raw_bytes)
        parse_metadata_json(existing)
        if not replace or existing == raw:
            return existing
    durable_atomic_write(target, raw)
    verified = read_regular_bytes(target, max_bytes=max_raw_bytes)
    if verified != raw:
        raise MetadataIntegrityError("plaintext metadata readback mismatch")
    return verified


def prepare_gzip_generation(
    video_dir: Path,
    raw: bytes,
    *,
    state: str,
    max_raw_bytes: int = DEFAULT_MAX_RAW_BYTES,
) -> dict[str, Any]:
    """Write and fully verify an immutable gzip generation without a manifest switch."""
    if len(raw) > max_raw_bytes:
        raise MetadataLimitError("plaintext metadata exceeds configured byte limit")
    parse_metadata_json(raw)
    filename, stored, descriptor = build_gzip_generation(raw, state=state)
    write_immutable_generation(video_dir, filename, stored)
    recovered = read_metadata_bytes(
        video_dir,
        {"metadata_storage": descriptor},
        max_raw_bytes=max_raw_bytes,
    )
    if recovered != raw:
        raise MetadataIntegrityError("compressed metadata generation did not round-trip exact bytes")
    return descriptor


def prepare_dual_generation(
    video_dir: Path,
    raw: bytes,
    *,
    max_raw_bytes: int = DEFAULT_MAX_RAW_BYTES,
) -> dict[str, Any]:
    """Write and fully verify an immutable dual generation without a manifest switch."""
    return prepare_gzip_generation(video_dir, raw, state="dual", max_raw_bytes=max_raw_bytes)


def prepare_compressed_generation(
    video_dir: Path,
    raw: bytes,
    *,
    max_raw_bytes: int = DEFAULT_MAX_RAW_BYTES,
) -> dict[str, Any]:
    """Write and fully verify compressed-canonical metadata without requiring a plaintext twin."""
    return prepare_gzip_generation(video_dir, raw, state="compressed", max_raw_bytes=max_raw_bytes)


def prepare_manifest_with_storage(manifest: Mapping[str, Any], descriptor: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(manifest, Mapping):
        raise MetadataManifestError("manifest must be an object")
    validated = validate_descriptor(dict(descriptor))
    files = manifest.get("files")
    if not isinstance(files, list) or not files or not all(isinstance(item, str) and item for item in files):
        raise MetadataManifestError("manifest files must be a non-empty string list")
    updated = copy.deepcopy(dict(manifest))
    updated["files"] = list(files)
    if validated["canonical_filename"] not in updated["files"]:
        updated["files"].append(validated["canonical_filename"])
    updated["metadata_storage"] = validated
    return updated


def manifest_bytes(manifest: Mapping[str, Any]) -> bytes:
    return (json.dumps(dict(manifest), indent=2, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")


def commit_manifest(video_dir: Path, manifest: Mapping[str, Any]) -> None:
    storage = manifest.get("metadata_storage") if isinstance(manifest, Mapping) else None
    descriptor = validate_descriptor(storage)
    files = manifest.get("files")
    if not isinstance(files, list) or descriptor["canonical_filename"] not in files:
        raise MetadataManifestError("manifest files must include the canonical metadata generation")
    path = _safe_child(video_dir, "manifest.json")
    durable_atomic_write(path, manifest_bytes(manifest))


def read_manifest(video_dir: Path, *, max_bytes: int = 4 * 1024 * 1024) -> dict[str, Any]:
    raw = read_regular_bytes(_safe_child(video_dir, "manifest.json"), max_bytes=max_bytes)
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MetadataManifestError("manifest is not valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise MetadataManifestError("manifest JSON must be an object")
    return value


def write_dual_from_plaintext(
    video_dir: Path,
    manifest: Mapping[str, Any],
    *,
    max_raw_bytes: int = DEFAULT_MAX_RAW_BYTES,
    on_step: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Write and verify a dual generation, committing the manifest last.

    The caller must hold the per-video writer lock. The optional hook is for
    receipts, tests, and interruption injection; it is called after each durable
    step and before the next one.
    """
    notify = on_step or (lambda _step: None)
    raw = read_regular_bytes(_safe_child(video_dir, "metadata.json"), max_bytes=max_raw_bytes)
    parse_metadata_json(raw)
    descriptor = prepare_dual_generation(video_dir, raw, max_raw_bytes=max_raw_bytes)
    notify("generation_committed")
    provisional = prepare_manifest_with_storage(manifest, descriptor)
    recovered = read_metadata_bytes(video_dir, provisional, max_raw_bytes=max_raw_bytes)
    if recovered != raw:
        raise MetadataIntegrityError("compressed generation did not round-trip exact bytes")
    notify("generation_verified")
    commit_manifest(video_dir, provisional)
    notify("manifest_committed")
    committed = read_manifest(video_dir)
    verified = read_metadata_bytes(video_dir, committed, max_raw_bytes=max_raw_bytes)
    if verified != raw:
        raise MetadataIntegrityError("committed manifest did not recover exact metadata bytes")
    notify("manifest_verified")
    return committed
