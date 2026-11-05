## Summary

- stop caption-track fallback when yt-dlp reports Windows session shutdown (`STATUS_DLL_INIT_FAILED_LOGOFF`)
- stop retries for fresh source-wide bot-check, rate-limit, and authentication circuits
- preserve ordinary caption-track fallback behavior
- bound and sanitize public diagnostics before they can expose credentials or signed query values
- add focused offline interruption, circuit, artifact-preservation, and redaction regressions

## Task

`pr-089-youtube-windows-interruption`

This protected replacement supersedes draft PR #89 because the legacy branch was not locally available to Mergeguez for a guarded fast-forward. PR #89 remains unchanged until this replacement is verified and merged.

## Changed Files For Publish

- `.speculoos/manifest.yaml`
- `.speculoos/tasks/pr-089-youtube-windows-interruption.yaml`
- `skills/youtube-transcript-archive/scripts/archive_youtube_transcript.py`
- `skills/youtube-transcript-archive/tests/test_process_interruption.py`
- `specs/pr-089-youtube-windows-interruption/commit-message.txt`
- `specs/pr-089-youtube-windows-interruption/pr-body.md`

## Validation

- 40 focused Linux/Python regressions on the reconciled source
- Python compilation and diff whitespace checks
- native Windows regression remains a source-only acceptance probe and is not an activation or deployment gate
- exact-head Speculoos contract and hosted Pullfrog review required after protected publication

## Documentation Impact

No top-level README or `docs/` page changes are required. The change is internal failure classification with no command or archive-schema change.

## Publication Boundary

This PR changes only the external transcript archiver, focused tests, and PR-bound Speculoos metadata. It does not change credentials, archive formats, metadata migration, media download behavior, retention, release, deployment, settings, billing, fallback activation, or stable branches.

## Release Flow

Feature PRs target `dev`.

Release/promotion PRs target `main`.
