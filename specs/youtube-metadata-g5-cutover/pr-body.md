## Summary

- make deterministic gzip metadata the canonical manifest-selected representation for new archive writes
- preserve existing plaintext twins as rollback evidence during the G5 candidate phase
- retain bounded dual-format reads and exact raw/stored hash validation
- bind this source change to Speculoos task `youtube-metadata-g5-cutover`

Feature PRs target `dev`. Release/promotion PRs target `main`.

## Validation

- 73 focused archive unit tests passed
- Python compile validation passed
- production-surface review classified 30 changed production files with zero plaintext-only readers
- nine compressed-canonical writer and documentation assertions passed
- sealed G5 publication packet SHA-256: `fe1629b5a7b274fbd819b8c095f4a773f26c763f01125cbd875b44d55938c1da`

## Changed Files For Publish

- `.speculoos/manifest.yaml`
- `.speculoos/tasks/youtube-metadata-g5-cutover.yaml`
- `skills/youtube-transcript-archive/SKILL.md`
- `skills/youtube-transcript-archive/scripts/archive_youtube_batch.py`
- `skills/youtube-transcript-archive/scripts/archive_youtube_transcript.py`
- `skills/youtube-transcript-archive/scripts/youtube_metadata_storage.py`
- `skills/youtube-transcript-archive/tests/test_archive_youtube_transcript.py`
- `skills/youtube-transcript-archive/tests/test_youtube_metadata_storage.py`
- `specs/youtube-metadata-g5-cutover/commit-message.txt`
- `specs/youtube-metadata-g5-cutover/pr-body.md`

## Documentation Impact

The user-facing archive skill is already included in this PR and documents manifest-selected canonical metadata. The added Speculoos files are repository-local publication evidence; no separate top-level documentation page is required.

## Safety Boundary

This PR publishes source only. It does not authorize deployment, production cutover, plaintext deletion, G6, worktree retirement, release, settings changes, credentials, billing, or stable promotion.
