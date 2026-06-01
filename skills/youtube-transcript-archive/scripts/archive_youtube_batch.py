#!/usr/bin/env python3
"""Archive a batch of YouTube captions/transcripts without downloading media."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


SCRIPT = Path(__file__).with_name("archive_youtube_transcript.py")
MEDIA_EXTENSIONS = {".mp4", ".m4a", ".webm", ".mp3", ".wav", ".mov", ".mkv", ".opus"}


def read_url_file(path: Path) -> list[str]:
    urls: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#"):
            urls.append(line)
    return urls


def collect_urls(cli_urls: list[str], url_files: list[str] | None) -> list[str]:
    urls: list[str] = []
    for url_file in url_files or []:
        urls.extend(read_url_file(Path(url_file).expanduser()))
    urls.extend(cli_urls)
    return urls


def archive_command(args: argparse.Namespace, archive_root: Path, url: str) -> list[str]:
    cmd = [
        sys.executable,
        str(SCRIPT),
        "--archive-root",
        str(archive_root),
        "--lang",
        args.lang,
        "--yt-dlp-bin",
        args.yt_dlp_bin,
        "--max-caption-candidates",
        str(args.max_caption_candidates),
    ]
    if args.refresh:
        cmd.append("--refresh")
    if args.no_caption_fallback:
        cmd.append("--no-caption-fallback")
    if not args.no_metadata_only_on_no_captions:
        cmd.append("--metadata-only-on-no-captions")
    cmd.append(url)
    return cmd


def parse_manifest_stdout(stdout: str) -> dict[str, Any] | None:
    stdout = stdout.strip()
    if not stdout:
        return None
    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        return None


def archive_one(args: argparse.Namespace, archive_root: Path, url: str) -> dict[str, Any]:
    cmd = archive_command(args, archive_root, url)
    cp = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    manifest = parse_manifest_stdout(cp.stdout)
    if cp.returncode != 0 or not manifest:
        detail = (cp.stderr or cp.stdout or "").strip()
        return {
            "input_url": url,
            "status": "blocked",
            "error": detail or f"archive helper exited with status {cp.returncode}",
            "returncode": cp.returncode,
        }

    video_id = manifest.get("video_id")
    report_path = str(archive_root / str(video_id) / "report.md") if video_id else None
    return {
        "input_url": url,
        "status": manifest.get("status"),
        "video_id": video_id,
        "title": manifest.get("title"),
        "channel": manifest.get("channel"),
        "language": manifest.get("language"),
        "transcript_source": manifest.get("transcript_source"),
        "report_path": report_path,
        "notes": manifest.get("notes"),
        "returncode": cp.returncode,
        "manifest": manifest,
    }


def validate_entry(archive_root: Path, entry: dict[str, Any]) -> list[str]:
    if entry.get("status") == "blocked":
        return []
    video_id = entry.get("video_id")
    if not video_id:
        return ["missing video_id"]
    folder = archive_root / str(video_id)
    manifest = entry.get("manifest") or {}
    errors: list[str] = []
    for rel in manifest.get("files") or []:
        if not (folder / rel).exists():
            errors.append(f"missing {rel}")
    for path in folder.rglob("*"):
        if path.is_file() and path.suffix.lower() in MEDIA_EXTENSIONS:
            errors.append(f"media file present: {path.relative_to(folder)}")
    return errors


def summarize_entries(entries: list[dict[str, Any]]) -> dict[str, int]:
    counts = {
        "inputs": len(entries),
        "caption_backed": 0,
        "metadata_only": 0,
        "blocked": 0,
        "validation_errors": 0,
    }
    for entry in entries:
        if entry.get("status") == "blocked":
            counts["blocked"] += 1
        elif entry.get("transcript_source") == "none":
            counts["metadata_only"] += 1
        else:
            counts["caption_backed"] += 1
        if entry.get("validation_errors"):
            counts["validation_errors"] += 1
    return counts


def table_escape(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ")


def status_label(entry: dict[str, Any]) -> str:
    if entry.get("status") == "blocked":
        return "blocked"
    if entry.get("transcript_source") == "none":
        return "metadata only"
    return "transcript archived"


def language_label(entry: dict[str, Any]) -> str:
    if entry.get("status") == "blocked":
        return "n/a"
    if entry.get("transcript_source") == "none":
        return "no captions exposed"
    return f"`{entry.get('language')}` {entry.get('transcript_source')} captions"


def build_batch_index(
    *,
    title: str,
    archive_root: Path,
    entries: list[dict[str, Any]],
    counts: dict[str, int],
) -> str:
    rows = []
    for entry in entries:
        video_id = entry.get("video_id") or "unknown"
        report_path = entry.get("report_path") or ""
        rows.append(
            "| "
            + " | ".join(
                [
                    f"`{table_escape(video_id)}`",
                    table_escape(entry.get("title") or entry.get("input_url")),
                    table_escape(entry.get("channel") or ""),
                    status_label(entry),
                    language_label(entry),
                    f"`{table_escape(report_path)}`" if report_path else "",
                ]
            )
            + " |"
        )

    summary_lines = []
    for entry in entries:
        video_id = entry.get("video_id") or "unknown"
        if entry.get("status") == "blocked":
            summary_lines.append(f"- `{video_id}`: blocked — {entry.get('error') or 'archive failed'}.")
        elif entry.get("transcript_source") == "none":
            summary_lines.append(f"- `{video_id}`: metadata-only entry for `{entry.get('title')}`; YouTube exposed no captions.")
        else:
            summary_lines.append(f"- `{video_id}`: transcript archived for `{entry.get('title')}`.")

    validation_lines = [
        f"- Inputs: {counts['inputs']}",
        f"- Caption-backed archives: {counts['caption_backed']}",
        f"- Metadata-only no-caption archives: {counts['metadata_only']}",
        f"- Blocked entries: {counts['blocked']}",
        f"- Entries with validation errors: {counts['validation_errors']}",
    ]
    for entry in entries:
        for error in entry.get("validation_errors") or []:
            validation_lines.append(f"- `{entry.get('video_id') or entry.get('input_url')}`: {error}")
    if counts["validation_errors"] == 0:
        validation_lines.append("- No video/audio media files were found in successful archive folders.")

    return "\n".join(
        [
            f"# YouTube Batch — {title}",
            "",
            f"Input links: {counts['inputs']}",
            "",
            f"Archive root: `{archive_root}`",
            "",
            "Processing policy: caption/transcript archive only; no video or audio media downloaded.",
            "",
            "## Results",
            "",
            "| Video ID | Title | Channel | Status | Language / source | Report |",
            "|---|---|---|---|---|---|",
            *rows,
            "",
            "## Batch Summary",
            "",
            *summary_lines,
            "",
            "## Validation",
            "",
            *validation_lines,
            "",
        ]
    )


def default_batch_id(now: dt.datetime) -> str:
    return now.strftime("%Y-%m-%d-%H%M-youtube-batch")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("urls", nargs="*", help="YouTube URLs or video IDs")
    parser.add_argument("--url-file", action="append", help="File containing one YouTube URL/video ID per line")
    parser.add_argument("--archive-root", required=True, help="Trusted archive root directory")
    parser.add_argument("--lang", default="best", help="Caption language preference passed to single-video helper")
    parser.add_argument("--refresh", action="store_true", help="Refresh existing archives in place")
    parser.add_argument("--yt-dlp-bin", default=os.environ.get("YT_DLP", "yt-dlp"), help="yt-dlp binary path")
    parser.add_argument("--no-caption-fallback", action="store_true", help="Disable alternate caption retry in best mode")
    parser.add_argument(
        "--max-caption-candidates",
        type=int,
        default=12,
        help="Maximum best-mode caption tracks to try per video",
    )
    parser.add_argument(
        "--no-metadata-only-on-no-captions",
        action="store_true",
        help="Fail no-caption videos instead of creating metadata-only archive entries",
    )
    parser.add_argument("--batch-id", help="Stable output stem; defaults to a UTC timestamp")
    parser.add_argument("--batch-title", help="Human-readable title in the generated Markdown index")
    parser.add_argument("--batch-index", help="Output Markdown path; defaults under <archive-root>/batches/")
    parser.add_argument("--batch-manifest", help="Output JSON path; defaults next to the Markdown index")
    parser.add_argument("--fail-fast", action="store_true", help="Stop the batch on the first helper failure")
    args = parser.parse_args()

    urls = collect_urls(args.urls, args.url_file)
    if not urls:
        raise SystemExit("No YouTube URLs or video IDs provided")

    archive_root = Path(args.archive_root).expanduser().resolve()
    archive_root.mkdir(parents=True, exist_ok=True)
    now = dt.datetime.now(dt.timezone.utc)
    batch_id = args.batch_id or default_batch_id(now)
    batch_dir = archive_root / "batches"
    batch_index = Path(args.batch_index).expanduser() if args.batch_index else batch_dir / f"{batch_id}.md"
    batch_manifest = Path(args.batch_manifest).expanduser() if args.batch_manifest else batch_dir / f"{batch_id}.json"
    batch_title = args.batch_title or batch_id

    entries: list[dict[str, Any]] = []
    for url in urls:
        entry = archive_one(args, archive_root, url)
        if args.fail_fast and entry.get("status") == "blocked":
            raise SystemExit(entry.get("error") or f"Failed to archive {url}")
        entry["validation_errors"] = validate_entry(archive_root, entry)
        entries.append(entry)

    counts = summarize_entries(entries)
    payload = {
        "batch_id": batch_id,
        "generated_at": now.isoformat(),
        "archive_root": str(archive_root),
        "counts": counts,
        "entries": entries,
    }
    index_text = build_batch_index(title=batch_title, archive_root=archive_root, entries=entries, counts=counts)

    batch_index.parent.mkdir(parents=True, exist_ok=True)
    batch_manifest.parent.mkdir(parents=True, exist_ok=True)
    batch_index.write_text(index_text, encoding="utf-8")
    batch_manifest.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")

    print(
        json.dumps(
            {
                "batch_id": batch_id,
                "batch_index": str(batch_index),
                "batch_manifest": str(batch_manifest),
                "counts": counts,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 1 if counts["blocked"] or counts["validation_errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
