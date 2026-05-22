# Audio transcription archive schema

## Destination policy and example layouts

Archive destinations are workspace policy, not shared-skill policy. Pass an explicit `--output-dir`, or pass a destination resolved from local routing with `--archive-root` and collection/subpath options. The helper refuses durable archive modes without an explicit destination unless `--allow-default-destination` is passed intentionally.

Example layouts only:

- Seminar/meeting recordings: `<archive-root>/<collection>/<year>/<YYYY-MM-DD>-<slug>/`
- Generic archives: `<archive-root>/audio-transcripts/<category>/<year>/<YYYY-MM-DD>-<slug>/`

The collection folder is configurable with `--seminar-collection`, so workspaces can use neutral names such as `lab_seminars`, `team_meetings`, or `research_seminars`.

## Required files

```text
<archive-folder>/
├── card.md
├── transcript.md
├── transcript.clean.md
├── summary.md
├── metadata.json
├── speakers.json
├── keywords.txt
├── source-info.json
└── provider-response.json
```

Optional provider/detail files:

```text
├── segments.json
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

## speakers.json policy

Each speaker entry should contain:

```json
{
  "label": "Speaker 1",
  "name": "Dr Kim",
  "display_name": "Dr Kim",
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

- Preserve raw provider JSON separately from cleaned Markdown.
- Preserve absolute timecodes when chunking.
- Record chunk boundaries/gaps/overlaps if chunks are used.
- Record quality flags for noise, overlap, code-switching, garbled text, missing timestamps.
- Record model, duration, usage/cost metadata when returned.
- Link related slides, papers, abstracts, source documents, or notes.
- Do not save raw audio unless explicitly requested; if saved, include checksum and access level in a future hardening pass.
