#!/usr/bin/env python3
"""Reusable audio transcription helper for AgentSkills.

This helper intentionally uses only Python stdlib plus system ffmpeg/ffprobe.
It can inspect media, normalize audio, call Mistral/Voxtral STT, and write a
seminar-style archive folder with timecoded transcript and metadata.
"""

from __future__ import annotations

import argparse
import datetime as dt
import difflib
import email.utils
import hashlib
import http.client
import json
import mimetypes
import os
import random
import re
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Iterator
from urllib import request, error
from zoneinfo import ZoneInfo

MISTRAL_ENDPOINT = "https://api.mistral.ai/v1/audio/transcriptions"
DEFAULT_MODEL = "voxtral-mini-latest"
DEFAULT_MAX_DIRECT_DURATION_SECONDS = 3 * 60 * 60
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_RETRY_BACKOFF_SECONDS = 2.0
DEFAULT_MAX_RETRY_DELAY_SECONDS = 60.0
DEFAULT_MAX_RESPONSE_BYTES = 64 * 1024 * 1024
DEFAULT_IO_CHUNK_BYTES = 1024 * 1024
DEFAULT_CHUNK_SECONDS = 45 * 60
DEFAULT_CHUNK_OVERLAP_SECONDS = 2.0
DEFAULT_TIMEZONE = "UTC"
DEFAULT_ARCHIVE_ROOT = "memory"
DEFAULT_SEMINAR_COLLECTION = "seminars"
SUPPORTED_DIRECT_SUFFIXES = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".opus"}


def eprint(*args: Any) -> None:
    print(*args, file=sys.stderr)


def run_json(cmd: list[str]) -> dict[str, Any]:
    proc = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        raise RuntimeError(f"Command failed ({proc.returncode}): {' '.join(cmd)}\n{proc.stderr.strip()}")
    try:
        return json.loads(proc.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Command did not return JSON: {' '.join(cmd)}") from exc


def inspect_media(path: Path, record_source_path: bool = False) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"Input file not found: {path}")
    info = run_json([
        "ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)
    ])
    stat = path.stat()
    duration = None
    try:
        duration = float(info.get("format", {}).get("duration"))
    except (TypeError, ValueError):
        pass
    audio_streams = [s for s in info.get("streams", []) if s.get("codec_type") == "audio"]
    format_info = dict(info.get("format", {}))
    ffprobe_raw = json.loads(json.dumps(info))
    if not record_source_path:
        # ffprobe includes the input filename, often as a full local path. Keep
        # only the basename unless the caller explicitly opted into path logging.
        if "filename" in format_info:
            format_info["filename"] = path.name
        if isinstance(ffprobe_raw.get("format"), dict) and "filename" in ffprobe_raw["format"]:
            ffprobe_raw["format"]["filename"] = path.name
    return {
        "source_name": path.name,
        "source_path": str(path.resolve()) if record_source_path else None,
        "source_path_recorded": bool(record_source_path),
        "size_bytes": stat.st_size,
        "duration_seconds": duration,
        "audio_stream_count": len(audio_streams),
        "audio_streams": audio_streams,
        "format": format_info,
        "ffprobe_raw": ffprobe_raw,
    }


def normalize_audio(input_path: Path, out_dir: Path, fmt: str = "mp3", sample_rate: int = 16000) -> tuple[Path, list[str]]:
    fmt = fmt.lower().lstrip(".")
    out_path = out_dir / f"normalized.{fmt}"
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(input_path),
        "-map", "0:a:0", "-vn", "-map_metadata", "-1", "-map_chapters", "-1",
        "-ac", "1", "-ar", str(sample_rate),
    ]
    if fmt == "mp3":
        cmd += ["-b:a", "64k", str(out_path)]
    elif fmt == "m4a":
        cmd += ["-c:a", "aac", "-b:a", "64k", str(out_path)]
    elif fmt == "wav":
        cmd += ["-c:a", "pcm_s16le", str(out_path)]
    else:
        raise ValueError("Unsupported normalize format. Use mp3, m4a, or wav.")
    proc = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg normalization failed ({proc.returncode}):\n{proc.stderr.strip()}")
    return out_path, cmd


def redacted_ffmpeg_command(fmt: str, sample_rate: int) -> list[str]:
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", "<source>",
        "-map", "0:a:0", "-vn", "-map_metadata", "-1", "-map_chapters", "-1",
        "-ac", "1", "-ar", str(sample_rate),
    ]
    if fmt == "mp3":
        cmd += ["-b:a", "64k", "<normalized.mp3>"]
    elif fmt == "m4a":
        cmd += ["-c:a", "aac", "-b:a", "64k", "<normalized.m4a>"]
    elif fmt == "wav":
        cmd += ["-c:a", "pcm_s16le", "<normalized.wav>"]
    return cmd


class AudioChunkPlan:
    def __init__(
        self,
        index: int,
        media_start: float,
        media_end: float,
        ownership_start: float,
        ownership_end: float,
        is_last: bool = False,
    ) -> None:
        self.index = index
        self.media_start = media_start
        self.media_end = media_end
        self.ownership_start = ownership_start
        self.ownership_end = ownership_end
        self.is_last = is_last
        self.path: Path | None = None

    @property
    def duration(self) -> float:
        return self.media_end - self.media_start


def plan_audio_chunks(
    duration: float,
    *,
    chunk_seconds: float = DEFAULT_CHUNK_SECONDS,
    overlap_seconds: float = DEFAULT_CHUNK_OVERLAP_SECONDS,
) -> list[AudioChunkPlan]:
    if duration <= 0:
        raise ValueError("Audio duration must be positive for chunk fallback.")
    if chunk_seconds <= 0 or overlap_seconds < 0 or overlap_seconds * 2 >= chunk_seconds:
        raise ValueError("Chunk duration/overlap values are invalid.")
    plans: list[AudioChunkPlan] = []
    ownership_start = 0.0
    index = 1
    while ownership_start < duration:
        ownership_end = min(duration, ownership_start + chunk_seconds)
        media_start = max(0.0, ownership_start - overlap_seconds)
        media_end = min(duration, ownership_end + overlap_seconds)
        plans.append(
            AudioChunkPlan(
                index,
                media_start,
                media_end,
                ownership_start,
                ownership_end,
                is_last=ownership_end >= duration,
            )
        )
        ownership_start = ownership_end
        index += 1
    return plans


def split_audio_chunks(
    input_path: Path,
    out_dir: Path,
    duration: float,
    *,
    fmt: str,
    sample_rate: int,
    chunk_seconds: float,
    overlap_seconds: float,
) -> list[AudioChunkPlan]:
    out_dir.mkdir(parents=True, exist_ok=True)
    plans = plan_audio_chunks(duration, chunk_seconds=chunk_seconds, overlap_seconds=overlap_seconds)
    for plan in plans:
        out_path = out_dir / f"chunk-{plan.index:04d}.{fmt}"
        cmd = [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-ss", f"{plan.media_start:.6f}", "-i", str(input_path),
            "-t", f"{plan.duration:.6f}", "-map", "0:a:0", "-vn",
            "-map_metadata", "-1", "-map_chapters", "-1", "-ac", "1", "-ar", str(sample_rate),
        ]
        if fmt == "mp3":
            cmd += ["-b:a", "64k", str(out_path)]
        elif fmt == "m4a":
            cmd += ["-c:a", "aac", "-b:a", "64k", str(out_path)]
        elif fmt == "wav":
            cmd += ["-c:a", "pcm_s16le", str(out_path)]
        else:
            raise ValueError("Unsupported chunk format.")
        proc = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg chunk creation failed ({proc.returncode}):\n{proc.stderr.strip()}")
        plan.path = out_path
    return plans


def _numeric_time(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _shift_chunk_item(item: dict[str, Any], plan: AudioChunkPlan) -> dict[str, Any] | None:
    start = _numeric_time(segment_start(item)) + plan.media_start
    local_end = segment_end(item)
    end = _numeric_time(local_end, _numeric_time(segment_start(item))) + plan.media_start
    midpoint = (start + end) / 2
    if midpoint < plan.ownership_start or (not plan.is_last and midpoint >= plan.ownership_end):
        return None
    shifted = dict(item)
    shifted["start"] = start
    shifted["end"] = end
    shifted["timestamp"] = [start, end]
    speaker = segment_speaker(item)
    if speaker != "Unknown speaker":
        shifted["speaker"] = f"Chunk {plan.index:04d} / {speaker}"
    shifted["_chunk_index"] = plan.index
    return shifted


def _dedupe_adjacent_segments(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    for segment in sorted(segments, key=lambda item: (_numeric_time(segment_start(item)), _numeric_time(segment_end(item)))):
        text_key = re.sub(r"\W+", " ", segment_text(segment).casefold()).strip()
        if deduped:
            previous = deduped[-1]
            previous_key = re.sub(r"\W+", " ", segment_text(previous).casefold()).strip()
            close = _numeric_time(segment_start(segment)) <= _numeric_time(segment_end(previous)) + 1.0
            if text_key and text_key == previous_key and close:
                continue
        deduped.append(segment)
    return deduped


def _sum_usage(responses: list[dict[str, Any]]) -> dict[str, Any]:
    totals: dict[str, Any] = {}
    for response in responses:
        for key, value in (response.get("usage") or {}).items():
            if isinstance(value, (int, float)):
                totals[key] = totals.get(key, 0) + value
    return totals


def stitch_chunk_responses(
    parts: list[tuple[AudioChunkPlan, dict[str, Any]]],
    *,
    duration: float,
    diarized: bool = True,
) -> dict[str, Any]:
    segments: list[dict[str, Any]] = []
    words: list[dict[str, Any]] = []
    responses = [response for _plan, response in parts]
    for plan, response in parts:
        for item in get_segments(response, plan.duration):
            shifted = _shift_chunk_item(item, plan)
            if shifted is not None:
                segments.append(shifted)
        for item in response.get("words") or response.get("word_timestamps") or []:
            if isinstance(item, dict):
                shifted = _shift_chunk_item(item, plan)
                if shifted is not None:
                    words.append(shifted)
    segments = _dedupe_adjacent_segments(segments)
    words = _dedupe_adjacent_segments(words)
    aggregate: dict[str, Any] = {
        "model": next((response.get("model") for response in responses if response.get("model")), None),
        "language": next((response.get("language") for response in responses if response.get("language")), None),
        "text": " ".join(segment_text(segment) for segment in segments if segment_text(segment)),
        "segments": segments,
        "usage": _sum_usage(responses),
        "_openclaw_transcription": {
            "strategy": "chunked_diarized" if diarized else "chunked",
            "derived_aggregate": True,
            "chunk_count": len(parts),
            "duration_seconds": duration,
            "speaker_labels_namespaced_per_chunk": True,
        },
    }
    if words:
        aggregate["words"] = words
    return aggregate


def guess_mime(path: Path) -> str:
    return mimetypes.guess_type(path.name)[0] or "application/octet-stream"


class MultipartStream:
    """Replayable multipart body that never loads the source file into memory."""

    def __init__(
        self,
        *,
        prefix: bytes,
        file_path: Path,
        suffix: bytes,
        content_type: str,
        chunk_size: int = DEFAULT_IO_CHUNK_BYTES,
    ) -> None:
        self.prefix = prefix
        self.file_path = file_path
        self.suffix = suffix
        self.content_type = content_type
        self.chunk_size = chunk_size

    @property
    def content_length(self) -> int:
        return len(self.prefix) + self.file_path.stat().st_size + len(self.suffix)

    def __iter__(self) -> Iterator[bytes]:
        yield self.prefix
        with self.file_path.open("rb") as source:
            while chunk := source.read(self.chunk_size):
                yield chunk
        yield self.suffix


class MistralRequestError(RuntimeError):
    """Safe, typed request failure used by retry policy and workflow circuits."""

    def __init__(
        self,
        message: str,
        *,
        category: str,
        retryable: bool,
        status: int | None = None,
        attempts: int = 1,
        retry_after_seconds: float | None = None,
    ) -> None:
        super().__init__(message)
        self.category = category
        self.retryable = retryable
        self.status = status
        self.attempts = attempts
        self.retry_after_seconds = retry_after_seconds

    def as_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "retryable": self.retryable,
            "status": self.status,
            "attempts": self.attempts,
            "retry_after_seconds": self.retry_after_seconds,
            "message": str(self),
        }


def multipart_stream(
    fields: list[tuple[str, str]],
    file_field: str,
    file_path: Path,
    *,
    boundary: str | None = None,
    chunk_size: int = DEFAULT_IO_CHUNK_BYTES,
) -> MultipartStream:
    boundary = boundary or f"----agent-skill-{uuid.uuid4().hex}"
    chunks: list[bytes] = []
    for name, value in fields:
        chunks.append(f"--{boundary}\r\n".encode())
        chunks.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        chunks.append(str(value).encode())
        chunks.append(b"\r\n")
    chunks.append(f"--{boundary}\r\n".encode())
    chunks.append(
        f'Content-Disposition: form-data; name="{file_field}"; filename="{file_path.name}"\r\n'.encode()
    )
    chunks.append(f"Content-Type: {guess_mime(file_path)}\r\n\r\n".encode())
    return MultipartStream(
        prefix=b"".join(chunks),
        file_path=file_path,
        suffix=b"\r\n" + f"--{boundary}--\r\n".encode(),
        content_type=f"multipart/form-data; boundary={boundary}",
        chunk_size=chunk_size,
    )


def multipart_body(fields: list[tuple[str, str]], file_field: str, file_path: Path) -> tuple[bytes, str]:
    """Compatibility helper for small tests; production calls use multipart_stream()."""
    stream = multipart_stream(fields, file_field, file_path)
    return b"".join(stream), stream.content_type


def parse_retry_after(value: str | None, *, now: float | None = None) -> float | None:
    if not value:
        return None
    raw = value.strip()
    try:
        return max(0.0, float(raw))
    except ValueError:
        pass
    try:
        parsed = email.utils.parsedate_to_datetime(raw)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        return max(0.0, parsed.timestamp() - (time.time() if now is None else now))
    except (TypeError, ValueError, OverflowError):
        return None


def is_retryable_transport_error(exc: BaseException) -> bool:
    reason = exc.reason if isinstance(exc, error.URLError) else exc
    if isinstance(
        reason,
        (
            TimeoutError,
            socket.timeout,
            ConnectionResetError,
            ConnectionAbortedError,
            BrokenPipeError,
            http.client.RemoteDisconnected,
            http.client.IncompleteRead,
            ssl.SSLEOFError,
        ),
    ):
        return True
    message = str(reason).lower()
    return any(
        marker in message
        for marker in (
            "eof occurred in violation of protocol",
            "remote end closed connection",
            "connection reset",
            "connection aborted",
            "broken pipe",
            "timed out",
        )
    )


def read_response_bytes(
    response: Any,
    *,
    max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
    chunk_size: int = DEFAULT_IO_CHUNK_BYTES,
) -> bytes:
    """Capture a complete bounded response through a temporary file."""
    content_length_raw = response.headers.get("Content-Length") if response.headers else None
    expected: int | None = None
    if content_length_raw:
        try:
            expected = int(content_length_raw)
        except (TypeError, ValueError):
            expected = None
    if expected is not None and expected > max_response_bytes:
        raise MistralRequestError(
            f"Mistral response exceeds configured limit ({expected} > {max_response_bytes} bytes)",
            category="response_too_large",
            retryable=False,
        )

    total = 0
    with tempfile.TemporaryFile(prefix="agent-stt-response-") as captured:
        while True:
            try:
                chunk = response.read(chunk_size)
            except http.client.IncompleteRead as exc:
                if exc.partial:
                    captured.write(exc.partial)
                    total += len(exc.partial)
                raise MistralRequestError(
                    f"Mistral response body truncated after {total} bytes",
                    category="incomplete_response",
                    retryable=True,
                ) from exc
            if not chunk:
                break
            captured.write(chunk)
            total += len(chunk)
            if total > max_response_bytes:
                raise MistralRequestError(
                    f"Mistral response exceeds configured limit ({total} > {max_response_bytes} bytes)",
                    category="response_too_large",
                    retryable=False,
                )
        if expected is not None and total != expected:
            raise MistralRequestError(
                f"Mistral response body truncated ({total} of {expected} bytes)",
                category="incomplete_response",
                retryable=True,
            )
        captured.seek(0)
        return captured.read()


def retry_delay_seconds(
    attempt: int,
    *,
    retry_after_seconds: float | None,
    backoff_seconds: float,
    max_delay_seconds: float,
    random_value: float,
) -> float:
    base = backoff_seconds * (2 ** max(0, attempt - 1))
    requested = max(base, retry_after_seconds or 0.0)
    jitter = min(1.0, requested * 0.25) * max(0.0, min(1.0, random_value))
    return min(max_delay_seconds, requested + jitter)


def call_mistral(
    audio_path: Path,
    api_key: str,
    model: str,
    diarize: bool,
    timestamp_granularities: list[str],
    language: str | None,
    context_bias: list[str],
    temperature: float | None,
    timeout: int,
    multipart_array_style: str,
    *,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    retry_backoff_seconds: float = DEFAULT_RETRY_BACKOFF_SECONDS,
    max_retry_delay_seconds: float = DEFAULT_MAX_RETRY_DELAY_SECONDS,
    max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
    urlopen_fn: Callable[..., Any] | None = None,
    sleep_fn: Callable[[float], None] | None = None,
    random_fn: Callable[[], float] | None = None,
) -> tuple[dict[str, Any], bytes]:
    if max_attempts < 1 or max_attempts > DEFAULT_MAX_ATTEMPTS:
        raise ValueError(f"max_attempts must be between 1 and {DEFAULT_MAX_ATTEMPTS}")
    urlopen_fn = urlopen_fn or request.urlopen
    sleep_fn = sleep_fn or time.sleep
    random_fn = random_fn or random.random

    fields: list[tuple[str, str]] = [("model", model), ("diarize", "true" if diarize else "false")]
    # Mistral docs note timestamp_granularities is not compatible with language. Prefer timestamps.
    add_array_fields(fields, "timestamp_granularities", timestamp_granularities, multipart_array_style)
    if language and not timestamp_granularities:
        fields.append(("language", language))
    add_array_fields(
        fields,
        "context_bias",
        [term.strip() for term in context_bias[:100] if term.strip()],
        multipart_array_style,
    )
    if temperature is not None:
        fields.append(("temperature", str(temperature)))

    body = multipart_stream(fields, "file", audio_path)
    last_error: MistralRequestError | None = None
    for attempt in range(1, max_attempts + 1):
        req = request.Request(MISTRAL_ENDPOINT, data=body, method="POST")
        req.add_header("Authorization", f"Bearer {api_key}")
        req.add_header("Content-Type", body.content_type)
        req.add_header("Content-Length", str(body.content_length))
        try:
            with urlopen_fn(req, timeout=timeout) as resp:
                raw_bytes = read_response_bytes(resp, max_response_bytes=max_response_bytes)
        except error.HTTPError as exc:
            try:
                error_body = exc.read(65536)
            except http.client.IncompleteRead as body_exc:
                error_body = body_exc.partial or b""
            except Exception:
                error_body = b""
            raw = error_body.decode("utf-8", errors="replace")
            retryable = exc.code == 429 or 500 <= exc.code <= 599
            last_error = MistralRequestError(
                f"Mistral API HTTP {exc.code}: {raw[:2000]}",
                category=f"http_{exc.code}",
                retryable=retryable,
                status=exc.code,
                attempts=attempt,
                retry_after_seconds=parse_retry_after(exc.headers.get("Retry-After") if exc.headers else None),
            )
        except MistralRequestError as exc:
            exc.attempts = attempt
            last_error = exc
        except Exception as exc:
            last_error = MistralRequestError(
                f"Mistral transport failure: {type(exc).__name__}: {exc}",
                category="transport",
                retryable=is_retryable_transport_error(exc),
                attempts=attempt,
            )
        else:
            try:
                raw = raw_bytes.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise MistralRequestError(
                    "Mistral API response was not valid UTF-8",
                    category="invalid_utf8",
                    retryable=False,
                    attempts=attempt,
                ) from exc
            try:
                return json.loads(raw), raw_bytes
            except json.JSONDecodeError as exc:
                raise MistralRequestError(
                    "Mistral API did not return complete JSON",
                    category="invalid_json",
                    retryable=False,
                    attempts=attempt,
                ) from exc

        assert last_error is not None
        if not last_error.retryable or attempt >= max_attempts:
            raise last_error
        delay = retry_delay_seconds(
            attempt,
            retry_after_seconds=last_error.retry_after_seconds,
            backoff_seconds=retry_backoff_seconds,
            max_delay_seconds=max_retry_delay_seconds,
            random_value=random_fn(),
        )
        eprint(
            f"RETRY_MISTRAL attempt={attempt + 1}/{max_attempts} "
            f"category={last_error.category} delay_seconds={delay:.3f}"
        )
        sleep_fn(delay)

    assert last_error is not None
    raise last_error


def add_array_fields(fields: list[tuple[str, str]], name: str, values: list[str], style: str) -> None:
    """Append multipart fields for provider array parameters.

    Providers disagree on multipart array encoding. Mistral docs define arrays,
    but real API/client behavior can drift; keep the default simple repeated-key
    style and allow agents to switch if a live smoke test shows otherwise.
    """
    values = [v for v in values if v]
    if not values:
        return
    if style == "repeated":
        fields.extend((name, value) for value in values)
    elif style == "brackets":
        fields.extend((f"{name}[]", value) for value in values)
    elif style == "json":
        fields.append((name, json.dumps(values, ensure_ascii=False)))
    else:
        raise ValueError(f"Unsupported multipart array style: {style}")


def slugify(text: str, fallback: str = "recording") -> str:
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9가-힣一-龥ぁ-んァ-ン\s._-]+", "", text)
    text = re.sub(r"[\s._-]+", "-", text).strip("-")
    return text[:80] or fallback


def fmt_time(value: Any) -> str:
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        seconds = 0.0
    if seconds < 0:
        seconds = 0.0
    ms = int(round((seconds - int(seconds)) * 1000))
    total = int(seconds)
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def segment_start(seg: dict[str, Any]) -> Any:
    return seg.get("start") or seg.get("start_time") or seg.get("timestamp", [0, None])[0]


def segment_end(seg: dict[str, Any]) -> Any:
    ts = seg.get("timestamp")
    return seg.get("end") or seg.get("end_time") or (ts[1] if isinstance(ts, list) and len(ts) > 1 else None)


def segment_text(seg: dict[str, Any]) -> str:
    return str(seg.get("text") or seg.get("word") or seg.get("transcript") or seg.get("content") or "").strip()


def normalize_speaker(value: Any) -> str:
    if value in (None, ""):
        return "Unknown speaker"
    s = str(value).strip()
    if re.fullmatch(r"\d+", s):
        return f"Speaker {s}"
    if re.fullmatch(r"speaker_?\d+", s, re.I):
        n = re.findall(r"\d+", s)[0]
        return f"Speaker {n}"
    return s


def segment_speaker(seg: dict[str, Any]) -> str:
    for key in ("speaker", "speaker_id", "speaker_label", "speaker_number"):
        if key in seg:
            return normalize_speaker(seg.get(key))
    return "Unknown speaker"


def get_segments(response: dict[str, Any], duration: float | None = None) -> list[dict[str, Any]]:
    for key in ("segments", "chunks"):
        value = response.get(key)
        if isinstance(value, list) and value:
            return [x for x in value if isinstance(x, dict)]
    text = str(response.get("text") or "").strip()
    if text:
        return [{"start": 0, "end": duration, "text": text}]
    return []


def render_transcript(title: str, segments: list[dict[str, Any]], speaker_names: dict[str, str]) -> str:
    lines = [f"# Transcript — {title}", ""]
    if not segments:
        lines += ["_No transcript segments were returned._", ""]
        return "\n".join(lines)
    for seg in segments:
        spk = segment_speaker(seg)
        mapped = speaker_names.get(spk)
        display = f"{spk} / {mapped}" if mapped else spk
        start = fmt_time(segment_start(seg))
        end_value = segment_end(seg)
        end = fmt_time(end_value) if end_value is not None else "??:??:??.???"
        text = segment_text(seg)
        lines.append(f"[{start} - {end}] {display}")
        lines.append(text or "[inaudible / empty segment]")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def clean_transcript(markdown: str) -> str:
    lines = []
    for line in markdown.splitlines():
        if line.startswith("["):
            lines.append(line)
        else:
            lines.append(re.sub(r"\s+", " ", line).strip())
    return "\n".join(lines).rstrip() + "\n"


def normalize_alignment_text(text: str) -> str:
    """Normalize transcript text for segment-level alignment.

    Accepts plain text or Markdown. Heading/commentary/code-fence lines are
    removed; timestamp-only lines are dropped so a clean untimed transcript can
    be aligned against timed provider segments.
    """
    lines: list[str] = []
    in_fence = False
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("```"):
            in_fence = not in_fence
            continue
        if not in_fence and (line.startswith("#") or line.startswith(">")):
            continue
        if re.match(r"^\[[0-9?:.\-–—\s]+\].*$", line):
            # Helper transcript timestamp lines also contain speaker labels;
            # drop the whole line instead of aligning labels as spoken text.
            continue
        if line:
            lines.append(line)
    return re.sub(r"\s+", " ", " ".join(lines)).strip()


def count_replacement_chars(value: Any) -> int:
    if isinstance(value, str):
        return value.count("\ufffd")
    if isinstance(value, dict):
        return sum(count_replacement_chars(v) for v in value.values())
    if isinstance(value, list):
        return sum(count_replacement_chars(v) for v in value)
    return 0


def repair_segments_from_clean_text(
    segments: list[dict[str, Any]],
    clean_text: str,
) -> tuple[list[dict[str, Any]], float]:
    """Align cleaner untimed text to timed provider segments.

    This fallback is useful when a provider returns usable timestamps/speaker
    labels but transcript text contains mojibake or replacement characters, and
    a second transcription pass produced cleaner plain text without timings.
    """
    clean_body = normalize_alignment_text(clean_text)
    if not segments or not clean_body:
        return [], 0.0

    parts: list[str] = []
    spans: list[tuple[int, int]] = []
    pos = 0
    for seg in segments:
        txt = re.sub(r"\s+", " ", segment_text(seg)).strip()
        if parts:
            parts.append(" ")
            pos += 1
        start = pos
        parts.append(txt)
        pos += len(txt)
        spans.append((start, pos))
    direct_body = "".join(parts)
    if not direct_body:
        return [], 0.0

    matcher = difflib.SequenceMatcher(None, direct_body, clean_body, autojunk=False)
    blocks = matcher.get_matching_blocks()
    ratio = matcher.ratio()

    def map_index(idx: int) -> int:
        prev: difflib.Match | None = None
        nxt: difflib.Match | None = None
        for block in blocks:
            if block.size and block.a <= idx < block.a + block.size:
                return block.b + (idx - block.a)
            if block.a + block.size <= idx:
                prev = block
            elif block.a > idx:
                nxt = block
                break
        if prev and nxt:
            a0 = prev.a + prev.size
            b0 = prev.b + prev.size
            a1 = nxt.a
            b1 = nxt.b
            if a1 == a0:
                return b0
            frac = (idx - a0) / (a1 - a0)
            return round(b0 + frac * (b1 - b0))
        if prev:
            return prev.b + prev.size + (idx - (prev.a + prev.size))
        if nxt:
            return max(0, nxt.b - (nxt.a - idx))
        return min(idx, len(clean_body))

    repaired: list[dict[str, Any]] = []
    for seg, (start, end) in zip(segments, spans):
        clean_start = max(0, min(len(clean_body), map_index(start)))
        clean_end = max(clean_start, min(len(clean_body), map_index(end)))
        text = clean_body[clean_start:clean_end].strip()
        if not text:
            text = segment_text(seg)
        item = dict(seg)
        item["text"] = text
        repaired.append(item)
    return repaired, ratio


def render_repaired_transcript(title: str, segments: list[dict[str, Any]], speaker_names: dict[str, str], ratio: float) -> str:
    transcript = render_transcript(title, segments, speaker_names)
    note = (
        f"# Transcript — {title} (repaired text)\n\n"
        "> Timestamps and provisional speaker labels are preserved from the timed provider response. "
        "Segment text was aligned from a cleaner untimed transcript. "
        f"Automatic alignment ratio: {ratio:.3f}. Verify against audio before quoting.\n\n"
    )
    # Drop the default H1 from render_transcript and keep the body.
    body = "\n".join(transcript.splitlines()[2:]).lstrip()
    return note + body


def parse_speaker_mappings(items: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    unnamed = 1
    for item in items:
        if "=" in item:
            label, name = item.split("=", 1)
            out[normalize_speaker(label.strip())] = name.strip()
        elif item.strip():
            out[f"Speaker {unnamed}"] = item.strip()
            unnamed += 1
    return out


CONTEXT_BIAS_PATTERN = re.compile(r"^[^,\s]+$")


def expand_context_bias_term(term: str) -> list[str]:
    """Return provider-valid context_bias terms.

    Mistral currently rejects context_bias entries containing commas or
    whitespace. Accept human-friendly phrases in CLI metadata, but send only
    token-like terms that satisfy the provider schema.
    """
    raw = term.strip()
    if not raw:
        return []
    if CONTEXT_BIAS_PATTERN.match(raw):
        return [raw]
    pieces = [piece.strip(" \t\r\n,.;:()[]{}<>\"'") for piece in re.split(r"[,\s]+", raw)]
    return [piece for piece in pieces if piece and CONTEXT_BIAS_PATTERN.match(piece)]


def collect_context_bias(args: argparse.Namespace, speaker_names: dict[str, str]) -> list[str]:
    terms: list[str] = []
    terms.extend(args.context_bias or [])
    if args.context_file:
        for p in args.context_file:
            path = Path(p)
            if path.exists():
                terms.extend([line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()])
    terms.extend([v for v in speaker_names.values() if v])
    terms.extend(args.keyword or [])
    if args.title:
        terms.append(args.title)
    deduped = []
    seen = set()
    for term in terms:
        for expanded in expand_context_bias_term(term):
            key = expanded.casefold().strip()
            if key and key not in seen:
                deduped.append(expanded.strip())
                seen.add(key)
    return deduped[:100]


def summarize_placeholder(text: str, title: str) -> str:
    plain = re.sub(r"\[[^\]]+\]\s*", "", text)
    plain = re.sub(r"\s+", " ", plain).strip()
    excerpt = plain[:900] + ("…" if len(plain) > 900 else "")
    return (
        f"# Summary — {title}\n\n"
        "## Status\n"
        "Automatic transcript archive created. Replace this with an agent-written semantic summary after reviewing the transcript.\n\n"
        "## Transcript excerpt\n"
        f"{excerpt or '_No transcript text available._'}\n"
    )


def write_json(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def safe_failure_record(exc: BaseException) -> dict[str, Any]:
    if isinstance(exc, MistralRequestError):
        record = exc.as_dict()
    else:
        record = {
            "category": "unexpected",
            "retryable": False,
            "status": None,
            "attempts": 1,
            "retry_after_seconds": None,
            "message": f"{type(exc).__name__}: {exc}",
        }
    record["message"] = re.sub(
        r"https?://[^/@\s]+@",
        "https://<redacted>@",
        str(record.get("message") or ""),
    )[:4000]
    return record


def write_failure_report(path: Path, exc: BaseException) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    write_json(tmp, {"status": "failed", "failure": safe_failure_record(exc)})
    tmp.replace(path)


def duration_hms(seconds: float | None) -> str:
    if seconds is None:
        return "unknown"
    total = int(round(seconds))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def create_archive_dir(args: argparse.Namespace, title: str, tz: ZoneInfo) -> Path:
    today = dt.datetime.now(tz).date().isoformat()
    date = args.date or today
    year = date[:4]
    slug = args.slug or slugify(title)
    if args.output_dir:
        return Path(args.output_dir)
    root = Path(args.archive_root)
    if args.mode == "seminar":
        return root / args.seminar_collection / year / f"{date}-{slug}"
    return root / "audio-transcripts" / year / f"{date}-{slug}"


def card_markdown(args: argparse.Namespace, title: str, archive_dir: Path, metadata: dict[str, Any], speakers: list[dict[str, Any]], keywords: list[str], summary_excerpt: str) -> str:
    speaker_lines = "\n".join(
        f"  - {s['label']}: {s.get('name') or s['display_name']} ({s.get('confidence', 'unknown')})" for s in speakers
    ) or "  - Unknown"
    related_lines = "\n".join(f"  - {r}" for r in (args.related or [])) or "  - none recorded"
    repaired_line = "  - Repaired timecoded transcript: `transcript.repaired.md`\n" if (metadata.get("repair") or {}).get("created") else ""
    return f"""# {title}

- Date: {metadata.get('date') or 'unknown'}
- Recorded at: {args.recorded_at or 'unknown'}
- Duration: {metadata.get('duration_hms') or 'unknown'}
- Language(s): {metadata.get('language') or args.language or 'auto/unknown'}
- Access level: {args.access_level}
- Cloud transcription approved: {'yes' if args.cloud_ok else 'no/mock/dry-run'}
- Speakers:
{speaker_lines}
- Main speaker: {args.main_speaker or 'unknown'}
- Source audio: {metadata.get('source_audio')}
- Transcription backend: {metadata.get('backend')} / {metadata.get('model')}
- Diarization: {metadata.get('diarization')}
- Word timestamps: {metadata.get('word_timestamps')}
- Archived at: {metadata.get('archived_at')}
- Privacy: {metadata.get('privacy_note')}
- Summary: {summary_excerpt or 'Summary pending after transcript review.'}
- Keywords: {', '.join(keywords) if keywords else 'none recorded'}
- Related materials:
{related_lines}
- Related files:
  - Full transcript: `transcript.md`
  - Clean transcript: `transcript.clean.md`
{repaired_line}  - Summary: `summary.md`
  - Metadata: `metadata.json`
  - Speakers: `speakers.json`
"""


def extract_speakers(segments: list[dict[str, Any]], speaker_names: dict[str, str]) -> list[dict[str, Any]]:
    labels: list[str] = []
    for seg in segments:
        label = segment_speaker(seg)
        if label not in labels:
            labels.append(label)
    if not labels:
        labels = list(speaker_names.keys()) or ["Unknown speaker"]
    out = []
    for label in labels:
        name = speaker_names.get(label)
        out.append({
            "label": label,
            "name": name,
            "display_name": name or label,
            "confidence": "user-provided" if name else "diarization-label-only",
            "notes": "Real speaker identity requires user mapping/self-introduction/manual review." if not name else "Mapped from user-provided metadata.",
        })
    return out


def keywords(args: argparse.Namespace, title: str, transcript_text: str) -> list[str]:
    base = list(args.keyword or [])
    base.extend([w for w in re.split(r"[-\s]+", title) if len(w) > 2])
    # Tiny fallback keyword extraction for searchability; agents can improve later.
    words = re.findall(r"[A-Za-z가-힣][A-Za-z가-힣0-9_-]{3,}", transcript_text)
    stop = {"this", "that", "with", "from", "have", "were", "there", "their", "about", "would", "could", "should", "speaker", "unknown"}
    counts: dict[str, int] = {}
    for w in words:
        key = w.casefold()
        if key not in stop:
            counts[w] = counts.get(w, 0) + 1
    base.extend([w for w, _ in sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:20]])
    out, seen = [], set()
    for item in base:
        key = item.strip().casefold()
        if key and key not in seen:
            out.append(item.strip())
            seen.add(key)
    return out[:40]


def update_indices(archive_dir: Path, card: dict[str, Any], seminar_root: Path) -> None:
    seminar_root.mkdir(parents=True, exist_ok=True)
    rel = archive_dir.as_posix()
    index_jsonl = seminar_root / "index.jsonl"
    rows = []
    if index_jsonl.exists():
        for line in index_jsonl.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if obj.get("archive_path") != rel:
                rows.append(obj)
    rows.append(card)
    index_jsonl.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")

    index_md = seminar_root / "index.md"
    header = f"# {seminar_root.name} transcript index\n\n| Date | Title | Duration | Speakers | Keywords | Path |\n|---|---|---:|---|---|---|\n"
    lines = [header]
    for r in sorted(rows, key=lambda x: (x.get("date") or "", x.get("title") or "")):
        speakers = ", ".join(r.get("speakers", [])) or "unknown"
        kws = ", ".join(r.get("keywords", [])[:8])
        lines.append(f"| {r.get('date','')} | {r.get('title','')} | {r.get('duration_hms','')} | {speakers} | {kws} | `{r.get('archive_path','')}` |\n")
    index_md.write_text("".join(lines), encoding="utf-8")


def save_archive(
    args: argparse.Namespace,
    response: dict[str, Any],
    source_info: dict[str, Any],
    normalize_info: dict[str, Any],
    provider_raw_bytes: bytes | None = None,
    provider_raw_chunks: list[tuple[str, bytes]] | None = None,
    transcription_strategy: dict[str, Any] | None = None,
) -> Path:
    tz = ZoneInfo(args.timezone)
    now = dt.datetime.now(tz)
    title = args.title or Path(args.input).stem
    archive_dir = create_archive_dir(args, title, tz)
    archive_dir.mkdir(parents=True, exist_ok=True)

    speaker_names = parse_speaker_mappings(args.speaker or [])
    duration = source_info.get("duration_seconds")
    segments = get_segments(response, duration)
    transcript = render_transcript(title, segments, speaker_names)
    clean = clean_transcript(transcript)
    speakers = extract_speakers(segments, speaker_names)
    kws = keywords(args, title, transcript)
    language = response.get("language") or response.get("detected_language") or args.language
    words = response.get("words") or response.get("word_timestamps")
    usage = response.get("usage")
    quality_flags = infer_quality_flags(args, segments, duration)
    provider_replacement_count = count_replacement_chars(response)
    segment_replacement_count = count_replacement_chars(segments)
    if provider_replacement_count:
        quality_flags.append("unicode_replacement_characters_in_provider_response")
    repair_info: dict[str, Any] | None = None
    repaired_segments: list[dict[str, Any]] = []
    repaired_transcript = ""
    if args.repair_from_clean_transcript:
        clean_source_path = Path(args.repair_from_clean_transcript)
        clean_source_text = clean_source_path.read_text(encoding="utf-8")
        repaired_segments, alignment_ratio = repair_segments_from_clean_text(segments, clean_source_text)
        repair_info = {
            "source": clean_source_path.as_posix(),
            "alignment_ratio": alignment_ratio,
            "threshold": args.repair_alignment_threshold,
            "created": bool(repaired_segments and alignment_ratio >= args.repair_alignment_threshold),
            "method": "aligned cleaner untimed transcript text to timed provider segments",
        }
        if repaired_segments and alignment_ratio >= args.repair_alignment_threshold:
            repaired_transcript = render_repaired_transcript(title, repaired_segments, speaker_names, alignment_ratio)
        else:
            quality_flags.append("repaired_transcript_alignment_below_threshold")
    raw_chunks = provider_raw_chunks or []
    raw_chunk_manifest = [
        {
            "path": f"provider-responses.raw/{name}",
            "sha256": hashlib.sha256(raw).hexdigest(),
            "size_bytes": len(raw),
        }
        for name, raw in raw_chunks
    ]
    metadata = {
        "title": title,
        "date": args.date or now.date().isoformat(),
        "recorded_at": args.recorded_at,
        "duration_seconds": duration,
        "duration_hms": duration_hms(duration),
        "archive_mode": args.mode,
        "seminar_collection": args.seminar_collection if args.mode == "seminar" else None,
        "language": language,
        "access_level": args.access_level,
        "backend": args.backend,
        "model": args.model,
        "endpoint": MISTRAL_ENDPOINT if args.backend == "mistral" else None,
        "diarization": "enabled" if args.diarize else "disabled",
        "word_timestamps": bool(words or "word" in args.timestamp_granularities),
        "timestamp_granularities_requested": args.timestamp_granularities,
        "archived_at": now.isoformat(),
        "privacy_note": args.privacy_note or ("cloud Mistral API" if args.backend == "mistral" else args.backend),
        "source_audio": source_info.get("source_name"),
        "source_path_recorded": source_info.get("source_path_recorded", False),
        "input_was_staged_copy": bool(args.staged_input),
        "usage": usage,
        "provider_text_quality": {
            "unicode_replacement_characters_in_response": provider_replacement_count,
            "unicode_replacement_characters_in_segments": segment_replacement_count,
        },
        "provider_raw_response": {
            "preserved": bool(provider_raw_bytes is not None or raw_chunks),
            "path": "provider-response.raw.json" if provider_raw_bytes is not None else None,
            "sha256": hashlib.sha256(provider_raw_bytes).hexdigest() if provider_raw_bytes is not None else None,
            "size_bytes": len(provider_raw_bytes) if provider_raw_bytes is not None else None,
            "aggregate_is_derived": bool(raw_chunks),
            "chunks": raw_chunk_manifest,
        },
        "transcription_strategy": transcription_strategy or {"name": "direct", "chunk_count": 0},
        "repair": repair_info,
        "quality_flags": quality_flags,
        "related": args.related or [],
        "notes": [
            "Diarization labels are not verified real identities unless mapped in speakers.json.",
            "Raw audio is not preserved unless --save-audio is used.",
        ],
    }
    summary = summarize_placeholder(transcript, title)
    summary_excerpt = re.sub(r"\s+", " ", segment_text(segments[0]) if segments else "").strip()[:350]
    card = card_markdown(args, title, archive_dir, metadata, speakers, kws, summary_excerpt)

    (archive_dir / "card.md").write_text(card, encoding="utf-8")
    (archive_dir / "transcript.md").write_text(transcript, encoding="utf-8")
    (archive_dir / "transcript.clean.md").write_text(clean, encoding="utf-8")
    if repaired_transcript and repaired_segments:
        (archive_dir / "transcript.repaired.md").write_text(repaired_transcript, encoding="utf-8")
        write_json(archive_dir / "segments.repaired.json", repaired_segments)
    (archive_dir / "summary.md").write_text(summary, encoding="utf-8")
    write_json(archive_dir / "metadata.json", metadata)
    write_json(archive_dir / "speakers.json", speakers)
    (archive_dir / "keywords.txt").write_text("\n".join(kws) + ("\n" if kws else ""), encoding="utf-8")
    write_json(archive_dir / "source-info.json", {"source": source_info, "normalization": normalize_info})
    if provider_raw_bytes is not None:
        (archive_dir / "provider-response.raw.json").write_bytes(provider_raw_bytes)
    if raw_chunks:
        raw_dir = archive_dir / "provider-responses.raw"
        raw_dir.mkdir(exist_ok=True)
        for name, raw in raw_chunks:
            (raw_dir / name).write_bytes(raw)
    write_json(archive_dir / "provider-response.json", response)
    if segments:
        write_json(archive_dir / "segments.json", segments)
    if words:
        write_json(archive_dir / "words.json", words)
    if response.get("diarization"):
        write_json(archive_dir / "diarization.json", response.get("diarization"))

    if args.save_audio:
        source_dir = archive_dir / "source"
        source_dir.mkdir(exist_ok=True)
        shutil.copy2(args.input, source_dir / Path(args.input).name)

    if args.mode == "seminar":
        idx_card = {
            "date": metadata["date"],
            "title": title,
            "duration_hms": metadata["duration_hms"],
            "speakers": [s.get("name") or s.get("label") for s in speakers],
            "keywords": kws,
            "archive_path": archive_dir.as_posix(),
            "card": (archive_dir / "card.md").as_posix(),
            "access_level": args.access_level,
            "backend": args.backend,
            "model": args.model,
        }
        seminar_root = archive_dir.parent if args.output_dir else Path(args.archive_root) / args.seminar_collection
        update_indices(archive_dir, idx_card, seminar_root)
    return archive_dir


def infer_quality_flags(args: argparse.Namespace, segments: list[dict[str, Any]], duration: float | None) -> list[str]:
    flags: list[str] = list(args.quality_flag or [])
    if duration and duration > args.max_direct_duration_seconds:
        flags.append("duration_exceeds_default_direct_request_limit")
    if not segments:
        flags.append("no_segments_returned")
    else:
        if any(segment_end(seg) is None for seg in segments):
            flags.append("missing_segment_end_timestamps")
        if any(segment_speaker(seg) == "Unknown speaker" for seg in segments):
            flags.append("unmapped_or_unknown_speakers")
    out: list[str] = []
    seen = set()
    for flag in flags:
        key = str(flag).strip()
        if key and key not in seen:
            out.append(key)
            seen.add(key)
    return out


class TranscriptionResult:
    def __init__(
        self,
        response: dict[str, Any],
        *,
        raw_bytes: bytes | None,
        raw_chunks: list[tuple[str, bytes]],
        effective_diarize: bool,
        strategy: dict[str, Any],
        quality_flags: list[str],
    ) -> None:
        self.response = response
        self.raw_bytes = raw_bytes
        self.raw_chunks = raw_chunks
        self.effective_diarize = effective_diarize
        self.strategy = strategy
        self.quality_flags = quality_flags


def call_mistral_for_args(
    audio_path: Path,
    args: argparse.Namespace,
    context_bias: list[str],
    *,
    diarize: bool,
) -> tuple[dict[str, Any], bytes]:
    return call_mistral(
        audio_path,
        os.environ[args.api_key_env],
        args.model,
        diarize,
        args.timestamp_granularities,
        args.language,
        context_bias,
        args.temperature,
        args.timeout,
        args.multipart_array_style,
        max_attempts=args.max_attempts,
        retry_backoff_seconds=args.retry_backoff_seconds,
        max_retry_delay_seconds=args.max_retry_delay_seconds,
        max_response_bytes=args.max_response_bytes,
    )


def transcribe_with_fallback(
    request_audio: Path,
    args: argparse.Namespace,
    *,
    duration: float,
    temp_dir: Path,
    context_bias: list[str],
) -> TranscriptionResult:
    try:
        response, raw = call_mistral_for_args(request_audio, args, context_bias, diarize=args.diarize)
        return TranscriptionResult(
            response,
            raw_bytes=raw,
            raw_chunks=[],
            effective_diarize=args.diarize,
            strategy={"name": "direct", "chunk_count": 0},
            quality_flags=[],
        )
    except MistralRequestError as direct_error:
        if not args.chunk_on_failure or not direct_error.retryable:
            raise
        direct_failure = direct_error

    try:
        plans = split_audio_chunks(
            request_audio,
            temp_dir / "chunks",
            duration,
            fmt=args.normalize_format,
            sample_rate=args.sample_rate,
            chunk_seconds=args.chunk_seconds,
            overlap_seconds=args.chunk_overlap_seconds,
        )
        parts: list[tuple[AudioChunkPlan, dict[str, Any]]] = []
        raw_chunks: list[tuple[str, bytes]] = []
        for plan in plans:
            assert plan.path is not None
            response, raw = call_mistral_for_args(plan.path, args, context_bias, diarize=args.diarize)
            parts.append((plan, response))
            raw_chunks.append((f"chunk-{plan.index:04d}.raw.json", raw))
        response = stitch_chunk_responses(parts, duration=duration, diarized=args.diarize)
        return TranscriptionResult(
            response,
            raw_bytes=None,
            raw_chunks=raw_chunks,
            effective_diarize=args.diarize,
            strategy={
                "name": "chunked_diarized" if args.diarize else "chunked",
                "chunk_count": len(plans),
                "chunk_seconds": args.chunk_seconds,
                "chunk_overlap_seconds": args.chunk_overlap_seconds,
                "direct_failure": safe_failure_record(direct_failure),
            },
            quality_flags=(
                ["chunked_transcription", "cross_chunk_speaker_labels_unreconciled"]
                if args.diarize
                else ["chunked_transcription"]
            ),
        )
    except MistralRequestError as chunk_error:
        if not args.allow_non_diarized_fallback or not chunk_error.retryable:
            raise
        chunk_failure = chunk_error

    response, raw = call_mistral_for_args(request_audio, args, context_bias, diarize=False)
    return TranscriptionResult(
        response,
        raw_bytes=raw,
        raw_chunks=[],
        effective_diarize=False,
        strategy={
            "name": "explicit_non_diarized_fallback",
            "chunk_count": 0,
            "direct_failure": safe_failure_record(direct_failure),
            "chunk_failure": safe_failure_record(chunk_failure),
        },
        quality_flags=["diarization_disabled_after_explicit_fallback"],
    )


def fallback_policy_error(args: argparse.Namespace) -> str | None:
    if args.chunk_on_failure and args.no_normalize:
        return "--chunk-on-failure requires normalization; remove --no-normalize."
    if args.allow_non_diarized_fallback and not args.chunk_on_failure:
        return "--allow-non-diarized-fallback requires --chunk-on-failure."
    if args.chunk_seconds <= 0:
        return "--chunk-seconds must be positive."
    if args.chunk_overlap_seconds < 0 or args.chunk_overlap_seconds * 2 >= args.chunk_seconds:
        return "--chunk-overlap-seconds must be non-negative and less than half the chunk duration."
    return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Transcribe audio/video and optionally create a seminar archive.")
    parser.add_argument("input", help="Audio/video file path")
    parser.add_argument("--mode", choices=["quick", "archive", "seminar"], default="quick")
    parser.add_argument("--backend", choices=["mistral"], default="mistral")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--api-key-env", default="MISTRAL_API_KEY")
    parser.add_argument("--cloud-ok", action="store_true", help="Confirm audio may be sent to the cloud backend.")
    parser.add_argument("--confirm-sensitive-cloud", action="store_true", help="Confirm sensitive/private audio may be sent to cloud STT.")
    parser.add_argument("--access-level", choices=["public", "internal", "sensitive", "private"], default="internal")
    parser.add_argument("--privacy-note", default=None)
    parser.add_argument("--title", default=None)
    parser.add_argument("--date", default=None, help="Recording date YYYY-MM-DD")
    parser.add_argument("--timezone", default=DEFAULT_TIMEZONE)
    parser.add_argument("--recorded-at", default=None)
    parser.add_argument("--main-speaker", default=None)
    parser.add_argument("--speaker", action="append", default=[], help="Speaker mapping, e.g. 'Speaker 1=Speaker Name' or just 'Speaker Name'. Repeatable.")
    parser.add_argument("--keyword", action="append", default=[], help="Keyword to include in card/index. Repeatable.")
    parser.add_argument("--related", action="append", default=[], help="Related material path/URL/note. Repeatable.")
    parser.add_argument("--context-bias", action="append", default=[], help="Mistral context-bias term. Repeatable, max 100 sent.")
    parser.add_argument("--context-file", action="append", default=[], help="File containing one context-bias term per line.")
    parser.add_argument("--language", default=None, help="Optional language hint. Omitted when timestamp_granularities are requested.")
    parser.add_argument("--timestamp-granularities", nargs="*", default=["segment"], choices=["segment", "word"], help="Timestamp granularities. Use no values to disable.")
    parser.add_argument("--multipart-array-style", choices=["repeated", "brackets", "json"], default="repeated", help="Multipart encoding for provider array fields.")
    parser.add_argument("--no-diarize", dest="diarize", action="store_false", default=True)
    parser.add_argument("--temperature", type=float, default=None)
    parser.add_argument("--archive-root", default=None, help="Base archive folder. Pass explicitly from workspace routing for durable archives; example default is used only with --allow-default-destination.")
    parser.add_argument("--seminar-collection", default=None, help="Folder under archive-root for seminar mode, e.g. event_transcripts or meeting_notes.")
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--allow-default-destination", action="store_true", help="Allow durable archive modes to use the helper's example default destination when no routed destination was provided.")
    parser.add_argument("--slug", default=None)
    parser.add_argument("--normalize-format", choices=["mp3", "m4a", "wav"], default="mp3")
    parser.add_argument("--sample-rate", type=int, default=16000)
    parser.add_argument("--no-normalize", action="store_true")
    parser.add_argument("--record-source-path", action="store_true")
    parser.add_argument("--save-audio", action="store_true", help="Persist original source audio in archive/source/. Off by default.")
    parser.add_argument("--quality-flag", action="append", default=[], help="Add a quality flag to metadata.json. Repeatable.")
    parser.add_argument("--max-direct-duration-seconds", type=int, default=DEFAULT_MAX_DIRECT_DURATION_SECONDS, help="Soft limit for one direct cloud STT request; default 10800 seconds / 3 hours.")
    parser.add_argument("--allow-long-audio", action="store_true", help="Allow cloud upload even if duration exceeds max-direct-duration-seconds.")
    parser.add_argument("--dry-run", action="store_true", help="Inspect and show planned request without uploading/transcribing.")
    parser.add_argument("--mock-response", default=None, help="Use a local JSON response instead of calling the API; useful for tests.")
    parser.add_argument("--staged-input", action="store_true", help="Mark the input as a temporary staged copy of source media, not the durable original.")
    parser.add_argument("--delete-staged-input-after-archive", action="store_true", help="After a successful durable archive, delete the staged input file. Requires --staged-input and is ignored for quick mode.")
    parser.add_argument("--repair-from-clean-transcript", default=None, help="Path to a cleaner untimed transcript to align onto timed provider segments; writes transcript.repaired.md and segments.repaired.json when alignment is good enough.")
    parser.add_argument("--repair-alignment-threshold", type=float, default=0.85, help="Minimum alignment ratio required to write transcript.repaired.md.")
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--max-attempts", type=int, default=DEFAULT_MAX_ATTEMPTS, help="Total attempts for one equivalent Mistral request; hard-capped at 3.")
    parser.add_argument("--retry-backoff-seconds", type=float, default=DEFAULT_RETRY_BACKOFF_SECONDS)
    parser.add_argument("--max-retry-delay-seconds", type=float, default=DEFAULT_MAX_RETRY_DELAY_SECONDS)
    parser.add_argument("--max-response-bytes", type=int, default=DEFAULT_MAX_RESPONSE_BYTES)
    parser.add_argument("--failure-report", default=None, help="Optional path for a safe machine-readable failure record.")
    parser.add_argument("--chunk-on-failure", action="store_true", help="After normalized direct retries exhaust, retry as overlapping diarized chunks.")
    parser.add_argument("--chunk-seconds", type=float, default=DEFAULT_CHUNK_SECONDS)
    parser.add_argument("--chunk-overlap-seconds", type=float, default=DEFAULT_CHUNK_OVERLAP_SECONDS)
    parser.add_argument("--allow-non-diarized-fallback", action="store_true", help="Explicitly permit a final non-diarized pass after chunked diarization also fails.")
    args = parser.parse_args()
    args.archive_root_defaulted = args.archive_root is None
    args.seminar_collection_defaulted = args.seminar_collection is None
    if args.archive_root is None:
        args.archive_root = DEFAULT_ARCHIVE_ROOT
    if args.seminar_collection is None:
        args.seminar_collection = DEFAULT_SEMINAR_COLLECTION
    return args


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)
    try:
        ZoneInfo(args.timezone)
    except Exception as exc:
        eprint(f"Invalid timezone: {args.timezone}")
        return 2

    if args.delete_staged_input_after_archive and not args.staged_input:
        eprint("Refusing to delete input unless --staged-input is also set.")
        return 2
    if not 1 <= args.max_attempts <= DEFAULT_MAX_ATTEMPTS:
        eprint(f"--max-attempts must be between 1 and {DEFAULT_MAX_ATTEMPTS}.")
        return 2
    if args.retry_backoff_seconds < 0 or args.max_retry_delay_seconds < 0:
        eprint("Retry delays must be non-negative.")
        return 2
    if args.max_response_bytes < 1:
        eprint("--max-response-bytes must be positive.")
        return 2
    policy_error = fallback_policy_error(args)
    if policy_error:
        eprint(policy_error)
        return 2

    if args.mode != "quick" and not args.allow_default_destination:
        has_explicit_destination = bool(args.output_dir)
        if args.mode == "archive":
            has_explicit_destination = has_explicit_destination or not args.archive_root_defaulted
        elif args.mode == "seminar":
            has_explicit_destination = has_explicit_destination or (
                not args.archive_root_defaulted and not args.seminar_collection_defaulted
            )
        if not has_explicit_destination:
            eprint(
                "Refusing durable archive without explicit destination. "
                "Pass --output-dir, or pass --archive-root for archive mode; "
                "for seminar mode pass both --archive-root and --seminar-collection. "
                "Use --allow-default-destination only for intentional use of the helper's example default layout."
            )
            return 2

    try:
        source_info = inspect_media(input_path, args.record_source_path)
        if not source_info.get("audio_stream_count"):
            raise RuntimeError("No audio stream found in input file.")
        duration = source_info.get("duration_seconds")
        long_audio_warning = None
        if duration and duration > args.max_direct_duration_seconds:
            long_audio_warning = (
                f"Input duration {duration_hms(duration)} exceeds the default direct-request guard "
                f"({duration_hms(args.max_direct_duration_seconds)}). Use --allow-long-audio only if the provider supports it, "
                "or chunk/stitch in a separate workflow."
            )
        if args.dry_run:
            plan = {
                "status": "dry-run",
                "input": input_path.name,
                "source_info": {k: v for k, v in source_info.items() if k != "ffprobe_raw"},
                "mode": args.mode,
                "backend": args.backend,
                "model": args.model,
                "diarize": args.diarize,
                "timestamp_granularities": args.timestamp_granularities,
                "multipart_array_style": args.multipart_array_style,
                "language_will_be_sent": bool(args.language and not args.timestamp_granularities),
                "normalization": "disabled" if args.no_normalize else {
                    "format": args.normalize_format,
                    "sample_rate": args.sample_rate,
                    "channels": 1,
                    "bit_rate": "64k" if args.normalize_format in {"mp3", "m4a"} else None,
                    "non_audio_streams_removed": True,
                },
                "fallback_policy": {
                    "chunk_on_failure": args.chunk_on_failure,
                    "chunk_seconds": args.chunk_seconds,
                    "chunk_overlap_seconds": args.chunk_overlap_seconds,
                    "allow_non_diarized_fallback": args.allow_non_diarized_fallback,
                },
                "archive_dir": str(create_archive_dir(args, args.title or input_path.stem, ZoneInfo(args.timezone))) if args.mode != "quick" else None,
                "cloud_upload": False,
                "warnings": [long_audio_warning] if long_audio_warning else [],
            }
            print(json.dumps(plan, ensure_ascii=False, indent=2))
            return 0

        if args.backend == "mistral" and not args.mock_response:
            if not args.cloud_ok:
                eprint("Refusing to send audio to Mistral without --cloud-ok.")
                return 2
            if args.access_level in {"sensitive", "private"} and not args.confirm_sensitive_cloud:
                eprint("Refusing to send sensitive/private audio to cloud STT without --confirm-sensitive-cloud.")
                return 2
            if long_audio_warning and not args.allow_long_audio:
                eprint(f"Refusing long direct cloud STT request. {long_audio_warning}")
                return 2
            if not os.environ.get(args.api_key_env):
                eprint(f"Missing API key environment variable: {args.api_key_env}")
                return 2

        normalize_info: dict[str, Any] = {"normalized": False}
        provider_raw_bytes: bytes | None = None
        provider_raw_chunks: list[tuple[str, bytes]] = []
        transcription_strategy: dict[str, Any] = {"name": "mock" if args.mock_response else "direct", "chunk_count": 0}
        with tempfile.TemporaryDirectory(prefix="agent-stt-") as td:
            request_audio = input_path
            if not args.no_normalize:
                request_audio, _cmd = normalize_audio(input_path, Path(td), args.normalize_format, args.sample_rate)
                normalize_info = {
                    "normalized": True,
                    "format": args.normalize_format,
                    "sample_rate": args.sample_rate,
                    "command_template": redacted_ffmpeg_command(args.normalize_format, args.sample_rate),
                }
            elif input_path.suffix.lower() not in SUPPORTED_DIRECT_SUFFIXES:
                eprint(f"Warning: sending unsupported-looking suffix directly: {input_path.suffix}")

            if args.mock_response:
                provider_raw_bytes = Path(args.mock_response).read_bytes()
                response = json.loads(provider_raw_bytes.decode("utf-8"))
            else:
                if args.language and args.timestamp_granularities:
                    eprint("Note: Mistral docs say timestamp_granularities is not compatible with language; omitting language hint.")
                result = transcribe_with_fallback(
                    request_audio,
                    args,
                    duration=float(duration or 0),
                    temp_dir=Path(td),
                    context_bias=collect_context_bias(args, parse_speaker_mappings(args.speaker or [])),
                )
                response = result.response
                provider_raw_bytes = result.raw_bytes
                provider_raw_chunks = result.raw_chunks
                transcription_strategy = result.strategy
                args.diarize = result.effective_diarize
                args.quality_flag.extend(result.quality_flags)

        if args.mode == "quick":
            print(response.get("text") or render_transcript(args.title or input_path.stem, get_segments(response, source_info.get("duration_seconds")), parse_speaker_mappings(args.speaker or [])))
            return 0

        archive_dir = save_archive(
            args,
            response,
            source_info,
            normalize_info,
            provider_raw_bytes,
            provider_raw_chunks=provider_raw_chunks,
            transcription_strategy=transcription_strategy,
        )
        staged_input_deleted = False
        if args.delete_staged_input_after_archive:
            input_path.unlink()
            staged_input_deleted = True
        print(json.dumps({
            "status": "archived",
            "archive_dir": str(archive_dir),
            "card": str(archive_dir / "card.md"),
            "transcript": str(archive_dir / "transcript.md"),
            "repaired_transcript": str(archive_dir / "transcript.repaired.md") if (archive_dir / "transcript.repaired.md").exists() else None,
            "staged_input_deleted": staged_input_deleted,
        }, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        if args.failure_report:
            try:
                write_failure_report(Path(args.failure_report), exc)
            except Exception as report_exc:
                eprint(f"Warning: could not write failure report: {report_exc}")
        eprint(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
