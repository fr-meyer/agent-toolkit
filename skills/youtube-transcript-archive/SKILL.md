---
name: youtube-transcript-archive
description: Use this skill when the user wants to archive, refresh, reuse, summarize, or produce a durable Markdown report from a YouTube video's captions or transcript. Apply it for YouTube URL/video ID transcript extraction, caption-only archival with yt-dlp, duplicate/reprocess decisions, stable transcript folder trees, metadata capture, cleaned/timestamped transcript files, and report generation. Do not use it for downloading YouTube video/audio media, non-YouTube transcripts, live-stream monitoring, or copyright-sensitive media mirroring.
---

# YouTube Transcript Archive

## Goal

Archive a YouTube video's captions/transcript into a stable folder with metadata, raw subtitle evidence, cleaned transcript files, and a canonical Markdown report.

Default to caption/subtitle extraction only. Do not download video or audio unless the user explicitly asks for a separate media workflow.

## Portability contract

Resolve `archive_root` from the first trusted source available:
1. explicit caller input
2. project/repository configuration
3. host-agent local environment notes

Do not hardcode workspace-specific paths in this reusable skill. Host-specific files may act as local adapters, but they are not part of the portable skill contract. If no trusted archive root is available, ask before writing files.

## Required inputs

- YouTube URL or video ID
- trusted `archive_root`
- optional language preference, e.g. `en`, `fr`, `fr-orig`, or `best`
- optional duplicate policy: `reuse` (default), `refresh`, or `resume`

## Archive layout

Use this canonical layout under `archive_root/<video_id>/`:

```text
<video_id>/
├── report.md                  # alias for the latest/default language report
├── manifest.json              # alias for the latest/default language manifest
├── metadata.json
├── subtitles-list.txt
├── reports/
│   └── <lang>.md
├── manifests/
│   └── <lang>.json
├── raw/
│   └── <lang>/
│       └── <video_id>.<lang>.vtt
└── transcript/
    └── <lang>/
        ├── clean.txt
        ├── clean-deduped.txt
        ├── timestamped.txt
        └── timestamped-deduped.txt
```

Do not create parallel near-duplicate folders for the same video ID. Language variants belong in language-specific subfolders inside the same video folder unless the user explicitly requests a different archive structure.

## Duplicate policy

Before extracting:
1. resolve the YouTube video ID
2. check `archive_root/<video_id>/manifests/<lang>.json` and `reports/<lang>.md` when a language is explicit; otherwise check the alias `manifest.json` and `report.md`
3. classify the existing archive:
   - `complete`: manifest/report and transcript files exist
   - `partial`: folder exists but required files are missing
   - `absent`: no folder exists

Default behavior:
- `complete` + no refresh request: reuse existing archive and report the path
- `partial`: resume/rebuild missing artifacts
- `refresh`: re-run extraction in the same video/language folder and update that language's manifest/report; do not create a sibling duplicate
- different requested language: keep the same video folder and produce separate language-specific raw/transcript/report artifacts

## Workflow

### 1. Confirm scope and safety

- Verify the input is a YouTube URL/video ID.
- Confirm this is transcript/caption archival, not media downloading.
- Resolve `archive_root`; ask if unavailable.
- Choose language policy: use the user's language if given; otherwise use `best` and document what was selected.

### 2. Extract and normalize artifacts

Preferred deterministic helper:

```bash
python skills/youtube-transcript-archive/scripts/archive_youtube_transcript.py \
  --archive-root "$ARCHIVE_ROOT" \
  --lang best \
  "$YOUTUBE_URL"
```

Useful flags:
- `--refresh` — re-download and update existing artifacts
- `--yt-dlp-bin <path>` — use a non-default yt-dlp binary
- `--summary-file <path>` — inject an already-written Markdown summary into `report.md`

The helper must call `yt-dlp` in skip-download mode and must not download video/audio streams.

### 3. Write or update the report

The canonical `report.md` must contain:

```md
# YouTube Transcript Archive — <title>

## Metadata
- URL:
- Video ID:
- Title:
- Channel:
- Upload date:
- Duration:
- Language:
- Transcript source:
- Archived at:
- yt-dlp version:

## Processing status
- Status:
- Duplicate policy:
- Files generated or reused:
- Notes:

## Summary
<agent-written concise summary>

## Detailed summary
<agent-written bullets or sections>

## Full transcript
<timestamped or clean transcript>
```

If the helper generated a placeholder report, read the transcript and replace the summary placeholders with a real concise summary before presenting the archive as finished, unless the user asked only for raw archival.

### 4. Validate

Before final response:
- confirm `manifest.json`, `metadata.json`, `subtitles-list.txt`, raw subtitle file, cleaned transcript, and `report.md` exist
- confirm `report.md` identifies source URL, video ID, title, channel, language, transcript source, and archival timestamp
- confirm no video/audio file was downloaded for transcript-only requests
- if reusing an existing archive, report that it was reused rather than reprocessed

## Gotchas

- YouTube captions may be manual or automatic; record which source was used.
- Official YouTube APIs are not sufficient for arbitrary public transcript retrieval; `yt-dlp` is the default practical tool.
- `yt-dlp` can break when YouTube changes behavior; record `yt-dlp --version` in the report.
- Auto-caption VTT often contains repeated karaoke-style fragments; keep raw VTT and also produce deduped readable text.
- Do not infer that a transcript is accurate just because extraction succeeded.
- Do not treat local adapter files as part of this skill's portable contract.

## Final response

Report:
- video title and ID
- archive status: created, reused, resumed, refreshed, or blocked
- selected language and transcript source
- report path
- any missing subtitles, ambiguity, or refresh notes
