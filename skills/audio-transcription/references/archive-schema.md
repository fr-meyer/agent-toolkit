# Audio transcription archive schema

## Destination policy and example layouts

Archive destinations are workspace policy, not shared-skill policy. Pass an explicit `--output-dir`, or pass a destination resolved from local routing with `--archive-root` and collection/subpath options. The helper refuses durable archive modes without an explicit destination unless `--allow-default-destination` is passed intentionally.

Example layouts only:

- Seminar/meeting recordings: `<archive-root>/<collection>/<year>/<YYYY-MM-DD>-<slug>/`
- Generic archives: `<archive-root>/audio-transcripts/<category>/<year>/<YYYY-MM-DD>-<slug>/`

The collection folder is configurable with `--seminar-collection`, so workspaces can use neutral names such as `event_transcripts`, `meeting_notes`, or `audio_archives`.

## Required files

```text
<archive-folder>/
├── card.md
├── transcript.md
├── transcript.clean.md
├── transcript.repaired.md      # optional; aligned clean text + timed segments when needed
├── summary.md
├── metadata.json
├── speakers.json
├── keywords.txt
├── source-info.json
├── provider-response.json      # normalized JSON for review
└── provider-response.raw.json  # exact provider/mock JSON bytes when captured
```

Optional provider/detail files:

```text
├── segments.json
├── segments.repaired.json     # optional companion to transcript.repaired.md
├── words.json
├── diarization.json
└── source/                    # only when user explicitly requested raw audio preservation
```

## card.md fields

Include:

- title
- date
- recorded at / location / platform when known
- duration
- language(s)
- access level: public/internal/sensitive/private
- cloud transcription approval status
- speakers and main speaker
- source audio reference, preferably filename/redacted locator
- backend/model
- diarization status
- word timestamps status
- archived timestamp
- privacy note
- short summary
- keywords
- related materials
- links to transcript, summary, metadata, speakers

## Transcript format

Use complete speaker-turn blocks:

```md
# Transcript — <title>

[00:00:00.000 - 00:00:07.420] Speaker 1 / <name if known>
Text...

[00:00:07.420 - 00:00:12.880] Speaker 2
Text...
```

Keep word-level timestamps in `words.json` unless the user specifically asks for word-by-word Markdown.

If a provider response has usable timestamps/speaker labels but corrupted text, and a second source has cleaner untimed text, create a separate repaired transcript rather than overwriting provider evidence:

```text
transcript.md             # direct timed provider transcript, provenance-preserving
transcript.clean.md       # lightly cleaned direct transcript or readable untimed transcript
transcript.repaired.md    # timed/speaker-labelled transcript with clean text aligned onto segments
segments.repaired.json    # repaired segment text with original timing/speaker metadata
```

Record the alignment method, source file, alignment score, and caveats in `metadata.json`.

## speakers.json policy

Each speaker entry should contain:

```json
{
  "label": "Speaker 1",
  "name": "Speaker Name",
  "display_name": "Speaker Name",
  "confidence": "user-provided | self-introduction | manual-review | diarization-label-only",
  "notes": "..."
}
```

Diarization labels are not real identities by themselves.

## Indexing

For `seminar` mode, update both under the explicitly configured collection root. When `--output-dir` is used, the archive folder's parent is the collection root:

- `<archive-root>/<seminar-collection>/index.md`
- `<archive-root>/<seminar-collection>/index.jsonl`

Index entries should include date, title, duration, speakers, keywords, archive path, access level, backend/model.

## Vital hardening requirements

- Preserve raw provider JSON separately from cleaned Markdown; when available, also write exact captured JSON bytes to `provider-response.raw.json` and record checksum/size in metadata.
- Avoid text-decoding paths that silently introduce replacement characters; capture provider JSON as UTF-8/raw bytes where possible and record Unicode replacement-character counts as quality flags.
- Preserve absolute timecodes when chunking.
- Record chunk boundaries/gaps/overlaps if chunks are used.
- Record quality flags for noise, overlap, code-switching, garbled text, missing timestamps.
- Record model, duration, usage/cost metadata when returned.
- Link related slides, papers, abstracts, source documents, or notes.
- For remote/node-local source media, stage a temporary copy into the processing workspace, run the full archive workflow there, verify durable outputs, then delete the staged copy unless raw audio retention was explicitly requested.
- Do not save raw audio unless explicitly requested; if saved, include checksum and access level in a future hardening pass.
