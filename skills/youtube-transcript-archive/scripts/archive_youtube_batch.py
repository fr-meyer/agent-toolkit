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
KST = dt.timezone(dt.timedelta(hours=9), "KST")
SUMMARY_PLACEHOLDERS = (
    "Raw transcript archival is complete. Summary not yet written",
    "Metadata-only archive. YouTube exposed no manual subtitles or automatic captions",
)
DETAIL_PLACEHOLDERS = (
    "Detailed summary pending.",
)


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


def extract_section(markdown: str, heading: str) -> str | None:
    marker = f"## {heading}\n"
    start = markdown.find(marker)
    if start < 0:
        return None
    start += len(marker)
    next_heading = markdown.find("\n## ", start)
    section = markdown[start:] if next_heading < 0 else markdown[start:next_heading]
    section = section.strip()
    return section or None


def concise_summary(summary: str, *, max_chars: int = 500) -> str:
    first_block = summary.split("\n\n", 1)[0].strip()
    one_line = " ".join(line.strip() for line in first_block.splitlines() if line.strip())
    if len(one_line) <= max_chars:
        return one_line
    return one_line[: max_chars - 3].rstrip() + "..."


def extract_report_summary(report_path: str | None) -> str | None:
    if not report_path:
        return None
    path = Path(report_path)
    if not path.exists():
        return None
    summary = extract_section(path.read_text(encoding="utf-8"), "Summary")
    if not summary:
        return None
    if any(placeholder in summary for placeholder in SUMMARY_PLACEHOLDERS):
        return None
    return concise_summary(summary)


def report_has_placeholder(report_path: str | None) -> bool:
    if not report_path:
        return False
    path = Path(report_path)
    if not path.exists():
        return False
    markdown = path.read_text(encoding="utf-8")
    summary = extract_section(markdown, "Summary") or ""
    detailed = extract_section(markdown, "Detailed summary") or ""
    return any(placeholder in summary for placeholder in SUMMARY_PLACEHOLDERS) or any(
        placeholder in detailed for placeholder in DETAIL_PLACEHOLDERS
    )


def preferred_transcript_path(archive_root: Path, entry: dict[str, Any]) -> str | None:
    if entry.get("status") == "blocked" or entry.get("transcript_source") == "none":
        return None
    video_id = entry.get("video_id")
    if not video_id:
        return None
    folder = archive_root / str(video_id)
    rel_files = entry.get("manifest", {}).get("files") or []
    transcript_files = [rel for rel in rel_files if "/transcript/" in f"/{rel}"]
    preferences = ("clean-deduped.txt", "timestamped-deduped.txt", "clean.txt", "timestamped.txt")
    for suffix in preferences:
        for rel in transcript_files:
            if rel.endswith(suffix) and (folder / rel).exists():
                return str(folder / rel)
    return None


def refresh_entry_report_state(archive_root: Path, entry: dict[str, Any]) -> None:
    if entry.get("status") == "blocked":
        return
    video_id = entry.get("video_id")
    if video_id and not entry.get("report_path"):
        entry["report_path"] = str(archive_root / str(video_id) / "report.md")
    entry["transcript_path"] = preferred_transcript_path(archive_root, entry)
    entry["has_placeholder_summary"] = report_has_placeholder(entry.get("report_path"))
    entry["report_summary"] = extract_report_summary(entry.get("report_path"))


def build_summary_status(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    status: list[dict[str, Any]] = []
    for entry in entries:
        metadata_only = entry.get("transcript_source") == "none"
        blocked = entry.get("status") == "blocked"
        needs_summary = (
            not blocked
            and not metadata_only
            and (entry.get("has_placeholder_summary") or not entry.get("report_summary"))
        )
        status.append(
            {
                "video_id": entry.get("video_id"),
                "title": entry.get("title"),
                "status": entry.get("status"),
                "metadata_only": metadata_only,
                "blocked": blocked,
                "report_path": entry.get("report_path"),
                "transcript_path": entry.get("transcript_path"),
                "has_placeholder_summary": bool(entry.get("has_placeholder_summary")),
                "needs_summary": bool(needs_summary),
            }
        )
    return status


def needs_summary_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [entry for entry in build_summary_status(entries) if entry["needs_summary"]]


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
    entry = {
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
    refresh_entry_report_state(archive_root, entry)
    return entry


def validate_entry(archive_root: Path, entry: dict[str, Any], *, require_summaries: bool = False) -> list[str]:
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
    if entry.get("transcript_source") == "none":
        if entry.get("status") != "metadata-only-no-captions":
            errors.append("transcript_source is none but status is not metadata-only-no-captions")
    elif not preferred_transcript_path(archive_root, entry):
        errors.append("missing cleaned transcript path")
    if require_summaries and entry.get("transcript_source") != "none":
        if report_has_placeholder(entry.get("report_path")) or not extract_report_summary(entry.get("report_path")):
            errors.append("summary pending in report.md")
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
                    f"`{table_escape(entry.get('transcript_path'))}`" if entry.get("transcript_path") else "none",
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
            summary_lines.append(
                f"- `{video_id}`: metadata-only entry for `{entry.get('title')}`; no transcript available because YouTube exposed no captions."
            )
        elif entry.get("report_summary"):
            summary_lines.append(f"- `{video_id}`: {entry['report_summary']}")
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
            "| Video ID | Title | Channel | Status | Language / source | Report | Transcript |",
            "|---|---|---|---|---|---|---|",
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


def default_batch_title(now: dt.datetime) -> str:
    zone = now.tzname() or "UTC"
    return f"{now:%Y-%m-%d %H:%M} {zone}"


def timestamp_now(zone: str) -> dt.datetime:
    now = dt.datetime.now(dt.timezone.utc)
    if zone == "kst":
        return now.astimezone(KST)
    return now


def write_batch_outputs(
    *,
    payload: dict[str, Any],
    batch_index: Path,
    batch_manifest: Path,
) -> None:
    archive_root = Path(payload["archive_root"])
    index_text = build_batch_index(
        title=payload.get("batch_title") or payload.get("batch_id") or "YouTube batch",
        archive_root=archive_root,
        entries=payload["entries"],
        counts=payload["counts"],
    )
    payload["batch_index"] = str(batch_index)
    payload["batch_manifest"] = str(batch_manifest)
    payload["summary_status"] = build_summary_status(payload["entries"])
    payload["needs_summary"] = needs_summary_entries(payload["entries"])
    batch_index.parent.mkdir(parents=True, exist_ok=True)
    batch_manifest.parent.mkdir(parents=True, exist_ok=True)
    batch_index.write_text(index_text, encoding="utf-8")
    batch_manifest.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def load_batch_payload(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or "entries" not in payload:
        raise SystemExit(f"Not a batch manifest: {path}")
    return payload


def sync_payload_from_reports(
    *,
    payload: dict[str, Any],
    archive_root: Path,
    require_summaries: bool,
) -> dict[str, Any]:
    entries = payload.get("entries") or []
    for entry in entries:
        refresh_entry_report_state(archive_root, entry)
        entry["validation_errors"] = validate_entry(archive_root, entry, require_summaries=require_summaries)
    payload["archive_root"] = str(archive_root)
    payload["counts"] = summarize_entries(entries)
    payload["synced_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
    payload["summary_status"] = build_summary_status(entries)
    payload["needs_summary"] = needs_summary_entries(entries)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("urls", nargs="*", help="YouTube URLs or video IDs")
    parser.add_argument("--url-file", action="append", help="File containing one YouTube URL/video ID per line")
    parser.add_argument("--archive-root", help="Trusted archive root directory")
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
    parser.add_argument(
        "--timestamp-zone",
        choices=["utc", "kst"],
        default="utc",
        help="Timezone for default batch ID/title; default: utc",
    )
    parser.add_argument("--batch-id", help="Stable output stem; defaults to a UTC timestamp")
    parser.add_argument("--batch-title", help="Human-readable title in the generated Markdown index")
    parser.add_argument("--batch-index", help="Output Markdown path; defaults under <archive-root>/batches/")
    parser.add_argument("--batch-manifest", help="Output JSON path; defaults next to the Markdown index")
    parser.add_argument("--fail-fast", action="store_true", help="Stop the batch on the first helper failure")
    parser.add_argument(
        "--sync-from-reports",
        action="store_true",
        help="Update an existing batch manifest/index from per-video report.md summaries without re-archiving URLs",
    )
    parser.add_argument(
        "--require-summaries",
        action="store_true",
        help="Treat caption-backed reports with placeholder/missing summaries as validation errors",
    )
    args = parser.parse_args()

    if args.sync_from_reports:
        if not args.batch_manifest:
            raise SystemExit("--sync-from-reports requires --batch-manifest")
        batch_manifest = Path(args.batch_manifest).expanduser().resolve()
        payload = load_batch_payload(batch_manifest)
        archive_root_text = args.archive_root or payload.get("archive_root")
        if not archive_root_text:
            raise SystemExit("--archive-root is required when the batch manifest does not contain archive_root")
        archive_root = Path(archive_root_text).expanduser().resolve()
        batch_index = Path(args.batch_index or payload.get("batch_index") or batch_manifest.with_suffix(".md")).expanduser()
        if not batch_index.is_absolute():
            batch_index = batch_manifest.parent / batch_index
        if args.batch_title:
            payload["batch_title"] = args.batch_title
        payload = sync_payload_from_reports(
            payload=payload,
            archive_root=archive_root,
            require_summaries=args.require_summaries,
        )
        write_batch_outputs(payload=payload, batch_index=batch_index, batch_manifest=batch_manifest)
        print(
            json.dumps(
                {
                    "batch_id": payload.get("batch_id"),
                    "batch_index": str(batch_index),
                    "batch_manifest": str(batch_manifest),
                    "counts": payload["counts"],
                    "needs_summary": payload["needs_summary"],
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 1 if payload["counts"]["validation_errors"] else 0

    urls = collect_urls(args.urls, args.url_file)
    if not urls:
        raise SystemExit("No YouTube URLs or video IDs provided")
    if not args.archive_root:
        raise SystemExit("--archive-root is required")

    archive_root = Path(args.archive_root).expanduser().resolve()
    archive_root.mkdir(parents=True, exist_ok=True)
    now = timestamp_now(args.timestamp_zone)
    batch_id = args.batch_id or default_batch_id(now)
    batch_dir = archive_root / "batches"
    batch_index = Path(args.batch_index).expanduser() if args.batch_index else batch_dir / f"{batch_id}.md"
    batch_manifest = Path(args.batch_manifest).expanduser() if args.batch_manifest else batch_dir / f"{batch_id}.json"
    batch_title = args.batch_title or default_batch_title(now)

    entries: list[dict[str, Any]] = []
    for url in urls:
        entry = archive_one(args, archive_root, url)
        if args.fail_fast and entry.get("status") == "blocked":
            raise SystemExit(entry.get("error") or f"Failed to archive {url}")
        entry["validation_errors"] = validate_entry(archive_root, entry, require_summaries=args.require_summaries)
        entries.append(entry)

    counts = summarize_entries(entries)
    payload = {
        "batch_id": batch_id,
        "batch_title": batch_title,
        "batch_index": str(batch_index),
        "batch_manifest": str(batch_manifest),
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "batch_timestamp": now.isoformat(),
        "timestamp_zone": args.timestamp_zone,
        "archive_root": str(archive_root),
        "counts": counts,
        "entries": entries,
    }
    payload["summary_status"] = build_summary_status(entries)
    payload["needs_summary"] = needs_summary_entries(entries)
    write_batch_outputs(payload=payload, batch_index=batch_index, batch_manifest=batch_manifest)

    print(
        json.dumps(
            {
                "batch_id": batch_id,
                "batch_index": str(batch_index),
                "batch_manifest": str(batch_manifest),
                "counts": counts,
                "needs_summary": payload["needs_summary"],
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 1 if counts["blocked"] or counts["validation_errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
