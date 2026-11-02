#!/usr/bin/env python3
"""Regression tests for audio-transcription archive repair/provenance behavior.

These tests intentionally use only stdlib and a tiny synthetic provider fixture.
They do not call external STT services and do not require ffmpeg.
"""

from __future__ import annotations

import argparse
import hashlib
import http.client
import importlib.util
import io
import json
import tempfile
import unittest
from urllib import error
from pathlib import Path
from typing import Any

SKILL_DIR = Path(__file__).resolve().parents[1]
HELPER_PATH = SKILL_DIR / "scripts" / "transcribe_audio.py"
FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"

spec = importlib.util.spec_from_file_location("transcribe_audio", HELPER_PATH)
assert spec and spec.loader
transcribe_audio = importlib.util.module_from_spec(spec)
spec.loader.exec_module(transcribe_audio)


class FakeResponse:
    def __init__(self, data: bytes, *, content_length: int | None = None) -> None:
        self.data = data
        self.offset = 0
        self.headers = {}
        if content_length is not None:
            self.headers["Content-Length"] = str(content_length)

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self, size: int = -1) -> bytes:
        if self.offset >= len(self.data):
            return b""
        end = len(self.data) if size < 0 else min(len(self.data), self.offset + size)
        chunk = self.data[self.offset:end]
        self.offset = end
        return chunk


class IncompleteResponse(FakeResponse):
    def read(self, _size: int = -1) -> bytes:
        if self.offset:
            return b""
        self.offset = len(self.data)
        raise http.client.IncompleteRead(self.data, 10)


class AudioTranscriptionRegressionTests(unittest.TestCase):
    def test_multipart_stream_is_bounded_replayable_and_exact_length(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            audio = Path(td) / "sample.mp3"
            audio.write_bytes(b"0123456789")
            stream = transcribe_audio.multipart_stream(
                [("model", "voxtral-mini-latest")],
                "file",
                audio,
                boundary="fixture-boundary",
                chunk_size=4,
            )

            first = list(stream)
            second = list(stream)
            self.assertEqual(first, second)
            self.assertEqual([len(part) for part in first[1:-1]], [4, 4, 2])
            self.assertEqual(sum(map(len, first)), stream.content_length)
            body = b"".join(first)
            self.assertIn(b"0123456789", body)
            self.assertTrue(body.endswith(b"--fixture-boundary--\r\n"))

    def test_response_capture_detects_truncation_and_size_limit(self) -> None:
        exact = transcribe_audio.read_response_bytes(FakeResponse(b"abc", content_length=3), chunk_size=2)
        self.assertEqual(exact, b"abc")

        with self.assertRaises(transcribe_audio.MistralRequestError) as truncated:
            transcribe_audio.read_response_bytes(FakeResponse(b"abc", content_length=8), chunk_size=2)
        self.assertEqual(truncated.exception.category, "incomplete_response")
        self.assertTrue(truncated.exception.retryable)

        with self.assertRaises(transcribe_audio.MistralRequestError) as incomplete:
            transcribe_audio.read_response_bytes(IncompleteResponse(b"partial"), chunk_size=2)
        self.assertEqual(incomplete.exception.category, "incomplete_response")

        with self.assertRaises(transcribe_audio.MistralRequestError) as oversized:
            transcribe_audio.read_response_bytes(FakeResponse(b"abcdef"), max_response_bytes=4, chunk_size=2)
        self.assertEqual(oversized.exception.category, "response_too_large")
        self.assertFalse(oversized.exception.retryable)

    def test_retryable_http_error_replays_stream_and_honors_retry_after(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            audio = Path(td) / "sample.mp3"
            audio.write_bytes(b"audio-fixture")
            response_raw = b'{"text":"ok","segments":[]}'
            uploaded: list[bytes] = []
            calls = 0

            def fake_urlopen(req: object, timeout: int) -> FakeResponse:
                nonlocal calls
                calls += 1
                uploaded.append(b"".join(req.data))  # type: ignore[attr-defined]
                self.assertEqual(timeout, 30)
                if calls == 1:
                    raise error.HTTPError(
                        "https://example.invalid",
                        500,
                        "server error",
                        {"Retry-After": "7"},
                        io.BytesIO(b'{"message":"retry"}'),
                    )
                return FakeResponse(response_raw, content_length=len(response_raw))

            delays: list[float] = []
            response, raw = transcribe_audio.call_mistral(
                audio,
                "not-a-real-key",
                "voxtral-mini-latest",
                True,
                ["segment"],
                None,
                [],
                None,
                30,
                "repeated",
                urlopen_fn=fake_urlopen,
                sleep_fn=delays.append,
                random_fn=lambda: 0.0,
            )

            self.assertEqual(response["text"], "ok")
            self.assertEqual(raw, response_raw)
            self.assertEqual(calls, 2)
            self.assertEqual(delays, [7.0])
            self.assertEqual(uploaded[0], uploaded[1])

    def test_truncated_http_error_body_preserves_status_retry_policy(self) -> None:
        class TruncatedErrorBody(io.BytesIO):
            def read(self, _size: int = -1) -> bytes:
                raise http.client.IncompleteRead(b'{"message":', 50)

        with tempfile.TemporaryDirectory() as td:
            audio = Path(td) / "sample.mp3"
            audio.write_bytes(b"audio-fixture")
            response_raw = b'{"text":"ok","segments":[]}'
            calls = 0

            def fake_urlopen(_req: object, timeout: int) -> FakeResponse:
                self.assertEqual(timeout, 30)
                nonlocal calls
                calls += 1
                if calls == 1:
                    raise error.HTTPError(
                        "https://example.invalid",
                        500,
                        "server error",
                        {},
                        TruncatedErrorBody(),
                    )
                return FakeResponse(response_raw, content_length=len(response_raw))

            response, raw = transcribe_audio.call_mistral(
                audio,
                "not-a-real-key",
                "voxtral-mini-latest",
                True,
                ["segment"],
                None,
                [],
                None,
                30,
                "repeated",
                urlopen_fn=fake_urlopen,
                sleep_fn=lambda _delay: None,
                random_fn=lambda: 0.0,
            )
            self.assertEqual(calls, 2)
            self.assertEqual(response["text"], "ok")
            self.assertEqual(raw, response_raw)

    def test_truncated_json_without_content_length_retries(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            audio = Path(td) / "sample.mp3"
            audio.write_bytes(b"audio-fixture")
            complete = b'{"text":"ok","segments":[]}'
            calls = 0

            def fake_urlopen(_req: object, timeout: int) -> FakeResponse:
                nonlocal calls
                calls += 1
                self.assertEqual(timeout, 30)
                if calls == 1:
                    return FakeResponse(b'{"text":"unterminated')
                return FakeResponse(complete)

            delays: list[float] = []
            response, raw = transcribe_audio.call_mistral(
                audio,
                "not-a-real-key",
                "voxtral-mini-latest",
                True,
                ["segment"],
                None,
                [],
                None,
                30,
                "repeated",
                urlopen_fn=fake_urlopen,
                sleep_fn=delays.append,
                random_fn=lambda: 0.0,
            )
            self.assertEqual(calls, 2)
            self.assertEqual(delays, [2.0])
            self.assertEqual(response["text"], "ok")
            self.assertEqual(raw, complete)

    def test_complete_malformed_json_without_content_length_does_not_retry(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            audio = Path(td) / "sample.mp3"
            audio.write_bytes(b"audio-fixture")
            calls = 0

            def fake_urlopen(_req: object, timeout: int) -> FakeResponse:
                nonlocal calls
                calls += 1
                self.assertEqual(timeout, 30)
                return FakeResponse(b'{"text": invalid}')

            with self.assertRaises(transcribe_audio.MistralRequestError) as failure:
                transcribe_audio.call_mistral(
                    audio,
                    "not-a-real-key",
                    "voxtral-mini-latest",
                    True,
                    ["segment"],
                    None,
                    [],
                    None,
                    30,
                    "repeated",
                    urlopen_fn=fake_urlopen,
                    sleep_fn=lambda _delay: self.fail("must not sleep"),
                )
            self.assertEqual(calls, 1)
            self.assertEqual(failure.exception.category, "invalid_json")
            self.assertFalse(failure.exception.retryable)

    def test_retryable_transport_failure_stops_after_three_attempts(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            audio = Path(td) / "sample.mp3"
            audio.write_bytes(b"audio-fixture")
            calls = 0

            def fake_urlopen(_req: object, timeout: int) -> FakeResponse:
                nonlocal calls
                calls += 1
                self.assertEqual(timeout, 30)
                raise error.URLError(ConnectionResetError("connection reset by peer"))

            delays: list[float] = []
            with self.assertRaises(transcribe_audio.MistralRequestError) as failure:
                transcribe_audio.call_mistral(
                    audio,
                    "not-a-real-key",
                    "voxtral-mini-latest",
                    True,
                    ["segment"],
                    None,
                    [],
                    None,
                    30,
                    "repeated",
                    max_attempts=3,
                    retry_backoff_seconds=2.0,
                    max_retry_delay_seconds=60.0,
                    urlopen_fn=fake_urlopen,
                    sleep_fn=delays.append,
                    random_fn=lambda: 0.0,
                )
            self.assertEqual(calls, 3)
            self.assertEqual(delays, [2.0, 4.0])
            self.assertEqual(failure.exception.attempts, 3)
            self.assertEqual(failure.exception.category, "transport")
            self.assertTrue(failure.exception.retryable)

    def test_failure_report_preserves_safe_typed_fields(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            report = Path(td) / "failure.json"
            failure = transcribe_audio.MistralRequestError(
                "response truncated",
                category="incomplete_response",
                retryable=True,
                attempts=3,
            )
            transcribe_audio.write_failure_report(report, failure)
            data = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(data["status"], "failed")
            self.assertEqual(data["failure"]["category"], "incomplete_response")
            self.assertEqual(data["failure"]["attempts"], 3)
            self.assertTrue(data["failure"]["retryable"])
            self.assertFalse(report.with_suffix(".json.tmp").exists())

    def test_nonretryable_http_error_stops_immediately(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            audio = Path(td) / "sample.mp3"
            audio.write_bytes(b"audio-fixture")
            calls = 0

            def fake_urlopen(_req: object, timeout: int) -> FakeResponse:
                nonlocal calls
                calls += 1
                raise error.HTTPError(
                    "https://example.invalid",
                    400,
                    "bad request",
                    {},
                    io.BytesIO(b'{"message":"invalid"}'),
                )

            with self.assertRaises(transcribe_audio.MistralRequestError) as failure:
                transcribe_audio.call_mistral(
                    audio,
                    "not-a-real-key",
                    "voxtral-mini-latest",
                    True,
                    ["segment"],
                    None,
                    [],
                    None,
                    30,
                    "repeated",
                    urlopen_fn=fake_urlopen,
                    sleep_fn=lambda _delay: self.fail("must not sleep"),
                )
            self.assertEqual(calls, 1)
            self.assertEqual(failure.exception.category, "http_400")
            self.assertFalse(failure.exception.retryable)

    def test_normalization_command_selects_audio_and_strips_metadata(self) -> None:
        command = transcribe_audio.redacted_ffmpeg_command("mp3", 16000)
        self.assertIn("-map", command)
        self.assertIn("0:a:0", command)
        self.assertIn("-vn", command)
        self.assertIn("-map_metadata", command)
        self.assertIn("-map_chapters", command)
        self.assertIn("-ac", command)
        self.assertEqual(command[command.index("-ac") + 1], "1")
        self.assertEqual(command[command.index("-ar") + 1], "16000")
        self.assertIn("64k", command)

    def test_chunk_plan_and_stitch_preserve_absolute_timestamps(self) -> None:
        plans = transcribe_audio.plan_audio_chunks(100.0, chunk_seconds=60.0, overlap_seconds=5.0)
        self.assertEqual(len(plans), 2)
        self.assertEqual(
            [(p.media_start, p.media_end, p.ownership_start, p.ownership_end) for p in plans],
            [(0.0, 65.0, 0.0, 60.0), (55.0, 100.0, 60.0, 100.0)],
        )
        first = {
            "model": "voxtral-mini-latest",
            "segments": [
                {"start": 10.0, "end": 20.0, "speaker": "speaker_0", "text": "first"},
                {"start": 59.0, "end": 61.0, "speaker": "speaker_1", "text": "boundary"},
            ],
            "usage": {"prompt_audio_seconds": 65},
        }
        second = {
            "model": "voxtral-mini-latest",
            "segments": [
                {"start": 4.0, "end": 6.0, "speaker": "speaker_1", "text": "boundary"},
                {"start": 10.0, "end": 20.0, "speaker": "speaker_0", "text": "second"},
            ],
            "usage": {"prompt_audio_seconds": 45},
        }
        stitched = transcribe_audio.stitch_chunk_responses(
            [(plans[0], first), (plans[1], second)],
            duration=100.0,
        )
        self.assertEqual([s["text"] for s in stitched["segments"]], ["first", "boundary", "second"])
        self.assertEqual(
            [(s["start"], s["end"]) for s in stitched["segments"]],
            [(10.0, 20.0), (59.0, 61.0), (65.0, 75.0)],
        )
        self.assertEqual(stitched["segments"][1]["speaker"], "Chunk 0002 / Speaker 1")
        self.assertEqual(stitched["usage"]["prompt_audio_seconds"], 110)
        self.assertTrue(stitched["_openclaw_transcription"]["derived_aggregate"])

    def test_non_diarized_fallback_requires_explicit_chunk_policy(self) -> None:
        args = argparse.Namespace(
            chunk_on_failure=False,
            no_normalize=False,
            allow_non_diarized_fallback=True,
            chunk_seconds=60.0,
            chunk_overlap_seconds=2.0,
        )
        self.assertIn("requires --chunk-on-failure", transcribe_audio.fallback_policy_error(args) or "")
        args.chunk_on_failure = True
        args.no_normalize = True
        self.assertIn("requires normalization", transcribe_audio.fallback_policy_error(args) or "")
        args.no_normalize = False
        self.assertIsNone(transcribe_audio.fallback_policy_error(args))

    def test_retry_exhaustion_uses_chunked_diarization_without_downgrade(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            audio = root / "normalized.mp3"
            audio.write_bytes(b"audio")
            plans = transcribe_audio.plan_audio_chunks(100.0, chunk_seconds=60.0, overlap_seconds=5.0)
            for plan in plans:
                plan.path = root / f"chunk-{plan.index}.mp3"
                plan.path.write_bytes(b"chunk")
            args = argparse.Namespace(
                diarize=True,
                chunk_on_failure=True,
                allow_non_diarized_fallback=False,
                normalize_format="mp3",
                sample_rate=16000,
                chunk_seconds=60.0,
                chunk_overlap_seconds=5.0,
            )
            calls: list[tuple[str, bool]] = []
            original_call = transcribe_audio.call_mistral_for_args
            original_split = transcribe_audio.split_audio_chunks

            def fake_call(path: Path, _args: argparse.Namespace, _bias: list[str], *, diarize: bool) -> tuple[dict[str, Any], bytes]:
                calls.append((path.name, diarize))
                if path == audio:
                    raise transcribe_audio.MistralRequestError(
                        "transient",
                        category="incomplete_response",
                        retryable=True,
                        attempts=3,
                    )
                plan = plans[len(calls) - 2]
                return (
                    {
                        "model": "voxtral-mini-latest",
                        "segments": [{"start": 1.0, "end": 2.0, "speaker": "speaker_0", "text": f"chunk {plan.index}"}],
                    },
                    json.dumps({"chunk": plan.index}).encode(),
                )

            try:
                transcribe_audio.call_mistral_for_args = fake_call
                transcribe_audio.split_audio_chunks = lambda *_a, **_kw: plans
                result = transcribe_audio.transcribe_with_fallback(
                    audio,
                    args,
                    duration=100.0,
                    temp_dir=root,
                    context_bias=[],
                )
            finally:
                transcribe_audio.call_mistral_for_args = original_call
                transcribe_audio.split_audio_chunks = original_split

            self.assertTrue(result.effective_diarize)
            self.assertEqual(result.strategy["name"], "chunked_diarized")
            self.assertEqual(len(result.raw_chunks), 2)
            self.assertEqual(calls, [("normalized.mp3", True), ("chunk-1.mp3", True), ("chunk-2.mp3", True)])
            self.assertNotIn("diarization_disabled_after_explicit_fallback", result.quality_flags)

    def test_explicit_non_diarized_fallback_is_marked(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            audio = root / "normalized.mp3"
            chunk = root / "chunk.mp3"
            audio.write_bytes(b"audio")
            chunk.write_bytes(b"chunk")
            plan = transcribe_audio.AudioChunkPlan(1, 0.0, 10.0, 0.0, 10.0)
            plan.path = chunk
            args = argparse.Namespace(
                diarize=True,
                chunk_on_failure=True,
                allow_non_diarized_fallback=True,
                normalize_format="mp3",
                sample_rate=16000,
                chunk_seconds=60.0,
                chunk_overlap_seconds=2.0,
            )
            calls: list[tuple[str, bool]] = []
            original_call = transcribe_audio.call_mistral_for_args
            original_split = transcribe_audio.split_audio_chunks

            def fake_call(path: Path, _args: argparse.Namespace, _bias: list[str], *, diarize: bool) -> tuple[dict[str, Any], bytes]:
                calls.append((path.name, diarize))
                if len(calls) < 3:
                    raise transcribe_audio.MistralRequestError(
                        "transient",
                        category="transport",
                        retryable=True,
                        attempts=3,
                    )
                return {"text": "fallback", "segments": []}, b'{"text":"fallback","segments":[]}'

            try:
                transcribe_audio.call_mistral_for_args = fake_call
                transcribe_audio.split_audio_chunks = lambda *_a, **_kw: [plan]
                result = transcribe_audio.transcribe_with_fallback(
                    audio,
                    args,
                    duration=10.0,
                    temp_dir=root,
                    context_bias=[],
                )
            finally:
                transcribe_audio.call_mistral_for_args = original_call
                transcribe_audio.split_audio_chunks = original_split

            self.assertEqual(calls, [("normalized.mp3", True), ("chunk.mp3", True), ("normalized.mp3", False)])
            self.assertFalse(result.effective_diarize)
            self.assertEqual(result.strategy["name"], "explicit_non_diarized_fallback")
            self.assertIn("diarization_disabled_after_explicit_fallback", result.quality_flags)

    def test_chunk_raw_responses_are_preserved_separately(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            archive_dir = root / "archive"
            args = argparse.Namespace(
                input=str(root / "staged-source.mp3"), mode="archive", output_dir=str(archive_dir),
                archive_root=None, seminar_collection=None, title="Chunk Fixture", date="2026-01-02",
                slug=None, timezone="UTC", recorded_at=None, language=None, access_level="internal",
                cloud_ok=True, privacy_note=None, backend="mistral", model="voxtral-mini-latest",
                diarize=True, timestamp_granularities=["segment"], speaker=[], main_speaker=None,
                keyword=[], related=[], quality_flag=["chunked_transcription"],
                max_direct_duration_seconds=10800, save_audio=False, staged_input=True,
                repair_from_clean_transcript=None, repair_alignment_threshold=0.85,
            )
            response = {
                "text": "one two",
                "segments": [
                    {"start": 0.0, "end": 1.0, "speaker": "Chunk 0001 / Speaker 0", "text": "one"},
                    {"start": 1.0, "end": 2.0, "speaker": "Chunk 0002 / Speaker 0", "text": "two"},
                ],
                "_openclaw_transcription": {"strategy": "chunked_diarized", "derived_aggregate": True},
            }
            raw_chunks = [("chunk-0001.raw.json", b'{"text":"one"}'), ("chunk-0002.raw.json", b'{"text":"two"}')]
            transcribe_audio.save_archive(
                args,
                response,
                {"source_name": "staged-source.mp3", "source_path_recorded": False, "duration_seconds": 2.0},
                {"normalized": True},
                None,
                provider_raw_chunks=raw_chunks,
                transcription_strategy={"name": "chunked_diarized", "chunk_count": 2},
            )
            metadata = json.loads((archive_dir / "metadata.json").read_text(encoding="utf-8"))
            self.assertTrue(metadata["provider_raw_response"]["aggregate_is_derived"])
            self.assertEqual(len(metadata["provider_raw_response"]["chunks"]), 2)
            self.assertEqual((archive_dir / "provider-responses.raw" / "chunk-0001.raw.json").read_bytes(), raw_chunks[0][1])
            self.assertFalse((archive_dir / "provider-response.raw.json").exists())

    def test_context_bias_terms_are_provider_valid(self) -> None:
        args = argparse.Namespace(
            context_bias=["multi word term", "TokenOnly", "comma,separated"],
            context_file=[],
            keyword=["domain phrase", "example glossary"],
            title="Example Archive Title",
        )
        terms = transcribe_audio.collect_context_bias(args, {"Speaker 1": "Domain Expert"})

        self.assertIn("multi", terms)
        self.assertIn("word", terms)
        self.assertIn("term", terms)
        self.assertIn("TokenOnly", terms)
        self.assertIn("comma", terms)
        self.assertIn("separated", terms)
        self.assertIn("Domain", terms)
        self.assertIn("Expert", terms)
        self.assertNotIn("multi word term", terms)
        self.assertTrue(all(transcribe_audio.CONTEXT_BIAS_PATTERN.match(term) for term in terms))

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
