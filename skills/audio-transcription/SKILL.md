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

Use the bundled script for deterministic inspect/normalize/transcribe/archive work:

```bash
python3 scripts/transcribe_audio.py recording.wav \
  --mode seminar \
  --title "Recording title" \
  --date YYYY-MM-DD \
  --output-dir path/to/archive-folder \
  --cloud-ok \
  --model voxtral-mini-latest
```

Collection-routed seminar folder:

```bash
python3 scripts/transcribe_audio.py recording.wav \
  --mode seminar \
  --archive-root path/to/archive-root \
  --seminar-collection event_transcripts \
  --title "Recording title" \
  --cloud-ok
```

For sensitive/private audio sent to Mistral, the command must also include:

```bash
--access-level sensitive --confirm-sensitive-cloud
```

Dry-run without upload:

```bash
python3 scripts/transcribe_audio.py recording.wav --mode seminar --title "Title" --output-dir path/to/archive-folder --dry-run
```

Test/archive from a saved provider JSON without calling the API:

```bash
python3 scripts/transcribe_audio.py sample.wav --mode seminar --title "Test" --output-dir path/to/archive-folder --mock-response response.json
```

### Useful script options

- `--mode quick|archive|seminar`
- `--title`, `--date`, `--slug`, `--recorded-at`, `--main-speaker`
- `--archive-root`, `--seminar-collection`, `--output-dir`, `--allow-default-destination`
- `--speaker "Speaker 1=Name"` or repeat `--speaker "Name"`
- `--keyword term` and `--related path-or-url`
- `--context-bias term` or `--context-file terms.txt`; human-friendly phrases are split into provider-valid token-like terms before sending
- `--timestamp-granularities segment word` for segment/word timestamps
- `--multipart-array-style repeated|brackets|json` if provider multipart array encoding needs adjustment after a live smoke test
- `--quality-flag flag` to add manual quality/provenance flags
- `--max-direct-duration-seconds` and `--allow-long-audio` for long-recording guardrails
- `--no-diarize` to disable speaker diarization
- `--access-level public|internal|sensitive|private`
- `--staged-input` and `--delete-staged-input-after-archive` for temporary duplicate media staged into the processing workspace
- `--repair-from-clean-transcript path/to/clean.txt` and `--repair-alignment-threshold 0.85` to create `transcript.repaired.md` from clean untimed text plus timed noisy segments
- `--save-audio` only when the user explicitly wants raw audio preserved

## Mistral/Voxtral backend

Default model:

- `voxtral-mini-latest` for freshness during prototyping.
- Pin `voxtral-mini-2602` for reproducible runs.

Use diarization and segment timestamps by default for archives. Request word timestamps when alignment/search requires it. Use the underlying provider model id (for example `voxtral-mini-latest`) when calling Mistral directly; provider/model routing strings used by a wrapper are not necessarily the API model id.

Important quirks:

- Current docs say `timestamp_granularities` is not compatible with `language`; prefer timestamps and omit the language hint when both are requested.
- Quick transcription wrappers can be useful smoke tests but may not expose `segments`, `words`, diarization, or raw provider provenance; use the full helper/API path for archive-grade output.
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
