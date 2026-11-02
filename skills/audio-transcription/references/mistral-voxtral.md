# Mistral/Voxtral speech-to-text backend reference

## Endpoint

- `POST https://api.mistral.ai/v1/audio/transcriptions`
- Auth: `Authorization: Bearer $MISTRAL_API_KEY`
- Request body: `multipart/form-data`
- Required fields: `model`, `file`

## Models

Use:

- `voxtral-mini-latest` for Voxtral Mini transcription runs.

Older/other identifiers observed in docs/examples may include `voxtral-mini-2507`. Prefer the latest stable model documented by Mistral at run time.

## Features to use for archives

Mistral's current Speech to Text docs describe Voxtral Mini Transcribe V2 as supporting:

- speaker diarization;
- context biasing/custom vocabulary;
- word-level timestamps;
- 13 languages including English, French, Korean, Japanese, Chinese, Spanish, German, Italian, Dutch, Portuguese, Russian, Arabic, Hindi;
- long audio up to about 3 hours in a single request;
- noisy-audio robustness.

## Parameters used by helper script

- `model`: underlying Mistral API model id such as `voxtral-mini-latest`; do not pass provider/router wrapper ids unless that wrapper explicitly expects them.
- `file`: normalized audio file.
- `diarize`: boolean; default enabled for archives.
- `timestamp_granularities`: values from `segment`, `word`; default `segment`.
- `language`: optional language hint, omitted by the helper when timestamps are requested because current docs indicate incompatibility.
- `context_bias`: domain terms/names/acronyms; use sparingly and dedupe. Mistral currently accepts token-like entries only (`^[^,\s]+$`), so the helper splits human-friendly phrases/names before sending.
- `temperature`: optional.
- `multipart_array_style`: `repeated` by default; use `brackets` or `json` only if a live API smoke test shows Mistral expects a different multipart array encoding.

## Expected response fields

Common fields:

- `model`
- `text`
- `language`
- `segments`
- `usage`

When available, preserve:

- word timestamp data;
- diarization data;
- any usage/cost/duration metadata.

Because provider schemas can drift, the helper stores the full `provider-response.json` and uses tolerant extraction for `segments`, `chunks`, `words`, `diarization`, `text`, `language`, and `usage`. Provider JSON should be captured/decoded as UTF-8 without silent replacement, and exact captured bytes should be preserved as `provider-response.raw.json` when available. If the provider text itself contains Unicode replacement characters (`�`), record that as a transcript quality issue rather than overwriting the raw evidence.

## Quick wrapper caveat

Generic or platform-level quick transcription wrappers may return only plain transcript text. They are useful for smoke tests and readable text fallback, but they are not sufficient for archive-grade output unless they expose timestamps, diarization labels, and raw provider provenance.

## Speaker identity caveat

Diarization labels separate voices, but labels such as `Speaker 1` are not verified real people. Only map names from explicit user metadata, self-introduction, or manual review.

## Long-audio reliability

The helper normalizes by default: first audio stream only, mono 16 kHz, 64 kbps for MP3/M4A, with video/cover art, source metadata, and chapters removed. `--no-normalize` is an explicit bypass and must have a recorded reason.

Uploads use a replayable content-length-aware multipart iterator; responses stream through a bounded temporary file and are accepted only after advertised-length, size, strict UTF-8, and JSON validation. `--max-response-bytes` controls the response cap.

One equivalent request is hard-capped at three attempts. Retry SSL EOF/reset/remote-close/timeout, HTTP 429/5xx, and incomplete response bodies with bounded exponential backoff/jitter; honor bounded `Retry-After`. Do not retry schema, authentication, payment/quota, proxy 407, invalid UTF-8, or invalid successful-response JSON failures. `--failure-report` writes safe typed failure evidence for durable workflow circuits.

The direct-request duration guard remains 3 hours (`--max-direct-duration-seconds 10800`). For a normalized retryable direct failure, opt into `--chunk-on-failure`; default chunks are 45 minutes with two seconds of overlap on each ownership boundary. The aggregate shifts timestamps to absolute time and deduplicates overlap. Independent diarization labels are namespaced per chunk and flagged for reconciliation; never infer cross-chunk voice identity.

A non-diarized final pass never happens implicitly. It requires both `--chunk-on-failure` and `--allow-non-diarized-fallback`, runs only after retryable direct and chunk failures, and records `diarization_disabled_after_explicit_fallback`.

For chunked archives, `provider-response.json` is an explicitly derived aggregate. Exact provider bodies are stored separately under `provider-responses.raw/` with hashes and sizes in metadata.

## Repair fallback

If one backend/pass returns clean text without timestamps and another returns timestamps/speaker labels with corrupted text, keep both outputs and create a derived `transcript.repaired.md` by aligning clean text onto the timed segments. Mark it as derived and verify before quoting.

## Privacy note

This backend uploads audio to Mistral cloud. Do not use for sensitive/private/third-party recordings unless the user explicitly approves cloud processing for that recording. Local/private transcription is a separate future backend.
