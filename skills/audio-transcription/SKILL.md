---
name: audio-transcription
description: Reusable audio and video speech-to-text workflow. Use when the user asks to transcribe audio, voice notes, videos, meetings, seminars, lectures, interviews, or recordings; when a timecoded transcript, speaker diarization, searchable archive, metadata card, summary placeholder, keywords, or Mistral/Voxtral STT pipeline is needed.
---

# Audio Transcription

## Goal

Transcribe audio/video into readable text and, when requested, archive complete timecoded transcripts with metadata, speaker labels, summaries, and searchable cards.

Example archive layouts (not canonical defaults):

- `memory/audio-transcripts/<year>/<YYYY-MM-DD>-<slug>/` for ordinary archives.
- `memory/seminars/<year>/<YYYY-MM-DD>-<slug>/` for seminar/meeting archives.

For durable archives, prefer an explicit `--output-dir` or a destination resolved from the current workspace's routing policy. Keep workspace-specific routing rules outside this shared skill, then pass the resolved destination into the helper with `--output-dir`, `--archive-root`, or `--seminar-collection`.

## Privacy gate

Mistral/Voxtral transcription sends audio to Mistral cloud. Before using cloud STT:

- Confirm cloud upload is acceptable when audio is sensitive, private, clinical/medical, legal/financial, unpublished research, student discussion, or contains third-party voices.
- Never store or print API keys. Use `MISTRAL_API_KEY` or another env var supplied at runtime.
- Do not persist raw or normalized audio unless the user explicitly asks.
- Record access level in `card.md`: `public`, `internal`, `sensitive`, or `private`.

If the user needs private/local transcription, treat it as a future/private-local backend unless a local STT tool such as `whisper.cpp` or `faster-whisper` is actually installed and wired.

## Modes

Implemented by `scripts/transcribe_audio.py`:

- `quick`: return transcript in chat/stdout; no durable archive.
- `archive`: create a full archive at an explicit or workspace-routed destination.
- `seminar`: create a full archive and update the selected collection's `index.md` and `index.jsonl`.

Planned, not yet implemented in the helper:

- `private-local`: local-only STT backend.
- `resume`, `refresh`, `correct`: revision workflows that preserve original provider output/provenance.
- full semantic summary generation: `summary.md` is currently a placeholder/excerpt for an agent to improve after review.

## Workflow

1. Identify source audio/video path or staged media path.
2. Decide mode: use `seminar` for seminar/meeting recordings; `quick` for short throwaway voice notes.
3. Gather optional metadata before transcription when available:
   - title, date, location/platform;
   - known speaker names;
   - keywords, lab/project names, paper titles, acronyms;
   - related slides, source documents, notes, abstracts.
4. Inspect media with `ffprobe`.
5. Normalize audio with `ffmpeg` unless there is a reason to send the original supported file directly.
6. Call the backend. First backend: Mistral/Voxtral.
7. Preserve raw provider JSON separately from cleaned Markdown.
8. For durable archives, resolve the destination explicitly or through the current workspace's local routing policy; do not silently rely on personal or workspace-specific defaults.
9. Write complete timecoded transcript and metadata archive.
10. For `seminar`, update the selected collection index.
11. Report paths and quality warnings.

## Helper script

Use the bundled script for deterministic inspect/normalize/transcribe/archive work:

```bash
python3 scripts/transcribe_audio.py recording.wav \
  --mode seminar \
  --title "Seminar title" \
  --date YYYY-MM-DD \
  --output-dir path/to/archive-folder \
  --cloud-ok \
  --model voxtral-mini-latest
```

Collection-routed seminar folder:

```bash
python3 scripts/transcribe_audio.py recording.wav \
  --mode seminar \
  --seminar-collection lab_seminars \
  --require-destination \
  --title "Seminar title" \
  --cloud-ok
```

For sensitive/private audio sent to Mistral, the command must also include:

```bash
--access-level sensitive --confirm-sensitive-cloud
```

Dry-run without upload:

```bash
python3 scripts/transcribe_audio.py recording.wav --mode seminar --title "Title" --dry-run
```

Test/archive from a saved provider JSON without calling the API:

```bash
python3 scripts/transcribe_audio.py sample.wav --mode seminar --title "Test" --mock-response response.json
```

### Useful script options

- `--mode quick|archive|seminar`
- `--title`, `--date`, `--slug`, `--recorded-at`, `--main-speaker`
- `--archive-root`, `--seminar-collection`, `--output-dir`, `--require-destination`
- `--speaker "Speaker 1=Name"` or repeat `--speaker "Name"`
- `--keyword term` and `--related path-or-url`
- `--context-bias term` or `--context-file terms.txt`
- `--timestamp-granularities segment word` for segment/word timestamps
- `--multipart-array-style repeated|brackets|json` if provider multipart array encoding needs adjustment after a live smoke test
- `--quality-flag flag` to add manual quality/provenance flags
- `--max-direct-duration-seconds` and `--allow-long-audio` for long-recording guardrails
- `--no-diarize` to disable speaker diarization
- `--access-level public|internal|sensitive|private`
- `--save-audio` only when the user explicitly wants raw audio preserved

## Mistral/Voxtral backend

Default model:

- `voxtral-mini-latest` for freshness during prototyping.
- Pin `voxtral-mini-2602` for reproducible runs.

Use diarization and segment timestamps by default for archives. Request word timestamps when alignment/search requires it.

Important quirks:

- Current docs say `timestamp_granularities` is not compatible with `language`; prefer timestamps and omit the language hint when both are requested.
- Diarization gives labels like `Speaker 1`; it does not reliably identify real names.
- Context bias can improve names/technical terms; provide speaker names, project names, paper titles, and acronyms when known.
- Long recordings should not be blindly uploaded as one request; the helper refuses cloud upload above the direct-duration guard unless `--allow-long-audio` is passed.

For more details, read `references/mistral-voxtral.md`.

## Archive contract

For `archive` and `seminar`, create:

- `card.md` — searchable description card and entry point.
- `transcript.md` — complete timecoded transcript with speaker labels.
- `transcript.clean.md` — complete lightly cleaned transcript.
- `summary.md` — initial summary/excerpt; replace with agent-written summary after review when needed.
- `metadata.json` — machine-readable provenance.
- `speakers.json` — diarization labels, real-name mappings, confidence/notes.
- `keywords.txt` — one searchable keyword per line.
- `source-info.json` — ffprobe/source metadata, no raw audio by default.
- `provider-response.json` — raw returned provider JSON.
- optional `segments.json`, `words.json`, `diarization.json` when returned.

For the full schema, read `references/archive-schema.md`.

## Speaker policy

- Treat diarization labels as provisional speaker labels.
- Map real names only when supplied by the user, present in metadata, self-introduced in the transcript, or manually reviewed.
- Record mapping confidence in `speakers.json`.
- Do not claim voiceprint identity matching.
- Flag overlapping speech or uncertain speaker turns for review.

## Quality policy

Mark or report:

- noisy audio;
- overlapping speech;
- low-confidence or garbled transcript sections;
- multilingual/code-switching issues;
- missing timestamps;
- chunk boundaries/gaps if a separate chunking workflow is used.

The helper automatically adds basic flags such as missing segment end timestamps, unknown speakers, no segments, and over-duration direct requests.
