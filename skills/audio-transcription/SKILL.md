---
name: audio-transcription
description: Reusable audio and video speech-to-text workflow. Use when the user asks to transcribe audio, voice notes, videos, meetings, seminars, lectures, interviews, or recordings; when a timecoded transcript, speaker diarization, searchable archive, metadata card, summary placeholder, keywords, or Mistral/Voxtral STT pipeline is needed.
---

# Audio Transcription

## Goal

Transcribe audio/video into readable text and, when requested, archive complete timecoded transcripts with metadata, speaker labels, summaries, and searchable cards.

Example layouts: `memory/audio-transcripts/<year>/<date>-<slug>/` or `memory/seminars/<year>/<date>-<slug>/`; neither is a canonical default.

For durable archives, pass an explicit `--output-dir` or a destination resolved from the current workspace's routing policy. Keep workspace-specific routing rules outside this shared skill, then pass the resolved destination into the helper with `--output-dir`, `--archive-root`, or `--seminar-collection`. The helper refuses durable archive modes without an explicit destination unless `--allow-default-destination` is passed intentionally.

## Privacy gate

Mistral/Voxtral transcription sends audio to Mistral cloud. Before using cloud STT:

- Confirm cloud upload is acceptable when audio is sensitive, private, clinical/medical, legal/financial, unpublished research, student discussion, or contains third-party voices.
- Never store or print API keys. Use `MISTRAL_API_KEY` or another env var supplied at runtime.
- Do not persist raw or normalized audio unless the user explicitly asks.
- Record access level in `card.md`: `public`, `internal`, `sensitive`, or `private`.

If the user needs private/local transcription, treat it as a future/private-local backend unless a local STT tool such as `whisper.cpp` or `faster-whisper` is actually installed and wired.

## Modes

Implemented by `scripts/transcribe_audio.py`:

- `quick`: return transcript in chat/stdout; no durable archive. Quick wrappers may return plain text only and should not be treated as archive-grade when timestamps, diarization, provider provenance, or searchable archive files are required.
- `archive`: create a full archive at an explicit or workspace-routed destination.
- `seminar`: create a full archive and update the selected collection's `index.md` and `index.jsonl`; with `--output-dir`, the archive folder's parent is treated as the collection root.

Planned, not yet implemented in the helper:

- `private-local`: local-only STT backend.
- `resume`, `refresh`, `correct`: revision workflows that preserve original provider output/provenance.
- full semantic summary generation: `summary.md` is currently a placeholder/excerpt for an agent to improve after review.

## Source staging workflow

If the source recording is on another machine, paired node, phone export folder, remote workstation, or otherwise not directly accessible from the processing workspace, prefer staging the audio/video file into a temporary processing folder first. Then run the full helper/backend locally in the processing workspace, verify the durable archive, and delete the staged media copy unless the user explicitly asked to preserve raw audio.

Keep staging commands and host-specific paths outside this shared skill. The shared rule is generic:

1. copy or mount the source media into a temporary processing path;
2. run `archive` or `seminar` mode against that staged path;
3. preserve transcripts, metadata, provider response, and indexes in the archive;
4. remove the staged media copy after successful verification when it is only a duplicate.

Use `--staged-input --delete-staged-input-after-archive` only for temporary duplicate inputs; never use it on an original user file.

## Workflow

1. Identify source audio/video path or staged media path. If the source is remote/node-local, stage it into the processing workspace before archive-grade transcription.
2. Decide mode: use `seminar` for seminar/meeting recordings; `quick` for short throwaway voice notes. Do not use quick wrappers as the final path for timecoded/diarized archives.
3. Gather optional metadata before transcription when available:
   - title, date, location/platform;
   - known speaker names;
   - keywords, project/context names, document titles, acronyms;
   - related slides, source documents, notes, abstracts.
4. Inspect media with `ffprobe`.
5. Normalize audio with `ffmpeg` unless there is a reason to send the original supported file directly.
6. Call the backend. First backend: Mistral/Voxtral.
7. Preserve raw provider JSON separately from cleaned Markdown.
8. For durable archives, resolve the destination explicitly or through the current workspace's local routing policy; do not silently rely on personal, workspace-specific, or helper example defaults.
9. Write complete timecoded transcript and metadata archive.
10. If the timed provider transcript contains replacement characters/mojibake but a cleaner untimed transcript exists, create `transcript.repaired.md` by aligning the clean text onto timed segments and record the method in metadata.
11. For `seminar`, update the selected collection index.
12. Report paths and quality warnings.

## Helper script

Run the bundled deterministic helper with an explicit durable destination:

```bash
python3 scripts/transcribe_audio.py recording.wav --mode seminar \
  --title "Recording title" --date YYYY-MM-DD \
  --output-dir path/to/archive-folder --cloud-ok
```

Add `--access-level sensitive --confirm-sensitive-cloud` for an approved sensitive/private upload. Use `--dry-run` to inspect without upload and `--mock-response response.json` for offline archive tests.

Key controls:

- metadata/routing: `--title`, `--date`, `--speaker`, `--keyword`, `--related`, `--output-dir`;
- request: `--timestamp-granularities`, `--context-bias`, `--multipart-array-style`;
- safety: `--max-direct-duration-seconds`, `--allow-long-audio`, `--staged-input`, `--delete-staged-input-after-archive`;
- retries: `--max-attempts` (hard maximum 3), bounded backoff/response limits, and `--failure-report`;
- diarization recovery: `--chunk-on-failure`, chunk duration/overlap controls, then `--allow-non-diarized-fallback` only after explicit approval;
- provenance/repair: `--quality-flag`, `--repair-from-clean-transcript`, `--save-audio`.

Keep normalization and diarization enabled by default. `--no-normalize` and `--no-diarize` are explicit quality/safety changes, not routine optimizations.

## Mistral/Voxtral backend

Default model:

- `voxtral-mini-latest` for all Voxtral Mini transcription runs.

Use diarization and segment timestamps by default for archives. Request word timestamps when alignment/search requires it. Use the underlying provider model id (for example `voxtral-mini-latest`) when calling Mistral directly; provider/model routing strings used by a wrapper are not necessarily the API model id.

Important behavior:

- Normalization selects the first audio stream, removes cover art/video/source metadata, and emits mono 16 kHz audio (64 kbps for MP3/M4A).
- Multipart upload and response capture are streamed; exact complete provider bytes are promoted only after size, length, UTF-8, and JSON checks.
- Retry only classified transient transport failures, HTTP 429/5xx, and incomplete bodies, for at most three equivalent attempts.
- `timestamp_granularities` is incompatible with `language`; the helper prefers timestamps.
- Chunk fallback preserves diarization but namespaces speaker labels per chunk; reconcile identities manually. Non-diarized fallback requires its explicit flag and is quality-marked.
- Diarization labels are provisional, not voice identity. Use context bias sparingly for names/terms.

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
- `provider-response.json` — normalized returned provider JSON.
- `provider-response.raw.json` — exact captured provider/mock JSON bytes when available, with checksum/size in metadata.
- optional `segments.json`, `words.json`, `diarization.json` when returned.
- optional `transcript.repaired.md` and `segments.repaired.json` when cleaner untimed text is aligned to timed provider segments.

For the full schema, read `references/archive-schema.md`.

## Regression tests

For helper maintenance, run the stdlib regression fixture before committing archive/repair changes:

```bash
python3 -m unittest discover -s skills/audio-transcription/tests
```

The fixture covers repaired transcript alignment and raw provider JSON byte preservation without calling external STT services.

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
