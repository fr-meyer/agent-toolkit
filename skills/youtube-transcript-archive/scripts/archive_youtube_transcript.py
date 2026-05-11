#!/usr/bin/env python3
"""Archive YouTube captions/transcripts without downloading video/audio media."""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterable

TIMESTAMP_RE = re.compile(r"^(?P<start>\d{2}:\d{2}:\d{2}\.\d{3})\s+-->\s+(?P<end>\d{2}:\d{2}:\d{2}\.\d{3})")
TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")


def run(cmd: list[str], *, capture: bool = True, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        check=True,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
    )


def safe_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def load_json_from_yt_dlp(yt_dlp: str, url: str) -> dict[str, Any]:
    cp = run([yt_dlp, "--skip-download", "-J", url])
    return json.loads(cp.stdout)


def yt_dlp_version(yt_dlp: str) -> str:
    try:
        return run([yt_dlp, "--version"]).stdout.strip()
    except Exception:
        return "unknown"


def choose_caption(info: dict[str, Any], requested: str) -> tuple[str, str, list[dict[str, Any]]]:
    subtitles = info.get("subtitles") or {}
    autos = info.get("automatic_captions") or {}

    def exact(pool: dict[str, Any], key: str) -> tuple[str, list[dict[str, Any]]] | None:
        if key in pool and pool[key]:
            return key, pool[key]
        return None

    def prefix(pool: dict[str, Any], key: str) -> tuple[str, list[dict[str, Any]]] | None:
        base = key.split("-")[0]
        for lang in sorted(pool):
            if lang == base or lang.startswith(base + "-"):
                return lang, pool[lang]
        return None

    if requested and requested != "best":
        for source, pool in (("manual", subtitles), ("automatic", autos)):
            found = exact(pool, requested) or prefix(pool, requested)
            if found:
                return found[0], source, found[1]
        raise SystemExit(f"No captions found for requested language: {requested}")

    preferences = ["en", "en-orig", "fr", "fr-orig"]
    for key in preferences:
        for source, pool in (("manual", subtitles), ("automatic", autos)):
            found = exact(pool, key)
            if found:
                return found[0], source, found[1]

    for source, pool in (("manual", subtitles), ("automatic", autos)):
        for lang in sorted(pool):
            entries = pool.get(lang) or []
            if entries:
                return lang, source, entries

    raise SystemExit("No subtitles or automatic captions found for this video")


def list_subs(yt_dlp: str, url: str) -> str:
    try:
        cp = run([yt_dlp, "--list-subs", url])
        return cp.stdout + (cp.stderr or "")
    except subprocess.CalledProcessError as exc:
        return (exc.stdout or "") + (exc.stderr or "")


def clean_text(text: str) -> str:
    text = html.unescape(text)
    text = TAG_RE.sub("", text)
    text = text.replace("&nbsp;", " ")
    text = WS_RE.sub(" ", text).strip()
    return text


def parse_vtt(vtt_path: Path) -> tuple[list[str], list[tuple[str, str]]]:
    blocks: list[tuple[str, list[str]]] = []
    current_start: str | None = None
    current_lines: list[str] = []

    def flush() -> None:
        nonlocal current_start, current_lines
        if current_start and current_lines:
            joined = clean_text(" ".join(current_lines))
            if joined:
                blocks.append((current_start, [joined]))
        current_start = None
        current_lines = []

    for raw in vtt_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line:
            flush()
            continue
        if line.startswith(("WEBVTT", "Kind:", "Language:", "NOTE")):
            continue
        m = TIMESTAMP_RE.match(line)
        if m:
            flush()
            current_start = m.group("start")
            continue
        if current_start:
            current_lines.append(line)
    flush()

    clean_lines = [text for _, lines in blocks for text in lines]
    timestamped = [(ts, text) for ts, lines in blocks for text in lines]
    return clean_lines, timestamped


def dedupe_consecutive(items: Iterable[Any]) -> list[Any]:
    out: list[Any] = []
    sentinel = object()
    prev: Any = sentinel
    for item in items:
        if item != prev:
            out.append(item)
        prev = item
    return out


def word_key(word: str) -> str:
    return re.sub(r"^\W+|\W+$", "", word.casefold())


def deoverlap_caption_stream(items: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Collapse YouTube karaoke-style repeated fragments into new text only.

    Auto-caption VTT often emits overlapping cues: phrase A, then phrase A+B,
    then phrase B+C. This keeps only the non-overlapping suffix from each cue.
    """
    out: list[tuple[str, str]] = []
    accumulated_keys: list[str] = []
    for ts, text in items:
        words = text.split()
        keys = [word_key(w) for w in words]
        if not any(keys):
            continue
        max_overlap = 0
        max_possible = min(len(accumulated_keys), len(keys))
        for k in range(max_possible, 0, -1):
            if accumulated_keys[-k:] == keys[:k]:
                max_overlap = k
                break
        new_words = words[max_overlap:]
        new_keys = keys[max_overlap:]
        if not any(new_keys):
            continue
        accumulated_keys.extend(new_keys)
        out.append((ts, " ".join(new_words)))
    return out


def duration_text(seconds: Any) -> str:
    if not isinstance(seconds, (int, float)):
        return "unknown"
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def resolve_existing_archive(video_dir: Path, requested_lang: str) -> dict[str, Any] | None:
    manifest_path = video_dir / "manifest.json"
    if not manifest_path.exists():
        return None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None

    existing_lang = manifest.get("language")
    if requested_lang != "best" and existing_lang != requested_lang:
        return None

    rel_files = manifest.get("files") or []
    if not rel_files:
        return None
    missing = [rel for rel in rel_files if not (video_dir / rel).exists()]
    if missing:
        return None
    return manifest


def report_markdown(meta: dict[str, Any], manifest: dict[str, Any], summary: str | None, transcript: str) -> str:
    title = meta.get("title") or meta.get("id") or "Untitled video"
    summary_block = summary.strip() if summary else "Raw transcript archival is complete. Summary not yet written; read the transcript and replace this section when a summarized report is requested."
    detailed_block = "Detailed summary pending. Add bullet points or section-level notes after reading the transcript." if not summary else "See summary above; expand with detailed bullets if needed."
    files = "\n".join(f"- `{p}`" for p in manifest.get("files", []))
    return f"""# YouTube Transcript Archive — {title}

## Metadata
- URL: {meta.get('webpage_url') or meta.get('original_url') or ''}
- Video ID: {meta.get('id') or ''}
- Title: {title}
- Channel: {meta.get('channel') or meta.get('uploader') or 'unknown'}
- Upload date: {meta.get('upload_date') or 'unknown'}
- Duration: {duration_text(meta.get('duration'))}
- Language: {manifest.get('language') or 'unknown'}
- Transcript source: {manifest.get('transcript_source') or 'unknown'}
- Archived at: {manifest.get('archived_at') or ''}
- yt-dlp version: {manifest.get('yt_dlp_version') or 'unknown'}

## Processing status
- Status: {manifest.get('status') or 'unknown'}
- Duplicate policy: {manifest.get('duplicate_policy') or 'unknown'}
- Files generated or reused:
{files}
- Notes: {manifest.get('notes') or 'none'}

## Summary
{summary_block}

## Detailed summary
{detailed_block}

## Full transcript
{transcript}
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="YouTube URL or video ID")
    parser.add_argument("--archive-root", required=True, help="Trusted archive root directory")
    parser.add_argument("--lang", default="best", help="Caption language preference, e.g. en, fr, fr-orig, or best")
    parser.add_argument("--refresh", action="store_true", help="Refresh an existing complete archive in place")
    parser.add_argument("--yt-dlp-bin", default=os.environ.get("YT_DLP", "yt-dlp"), help="yt-dlp binary path")
    parser.add_argument("--summary-file", help="Optional Markdown summary to inject into report.md")
    args = parser.parse_args()

    yt_dlp = shutil.which(args.yt_dlp_bin) or args.yt_dlp_bin
    if not shutil.which(yt_dlp) and not Path(yt_dlp).exists():
        raise SystemExit(f"yt-dlp binary not found: {args.yt_dlp_bin}")

    archive_root = Path(args.archive_root).expanduser().resolve()
    archive_root.mkdir(parents=True, exist_ok=True)

    info = load_json_from_yt_dlp(yt_dlp, args.url)
    video_id = info.get("id")
    if not video_id:
        raise SystemExit("Could not resolve YouTube video ID")

    video_dir = archive_root / video_id
    manifest_path = video_dir / "manifest.json"
    if not args.refresh:
        existing = resolve_existing_archive(video_dir, args.lang)
        if existing:
            existing["status"] = "reused"
            existing["notes"] = "complete existing archive reused; use --refresh to reprocess"
            print(json.dumps(existing, indent=2, ensure_ascii=False))
            return 0

    lang, source, _entries = choose_caption(info, args.lang)
    video_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = video_dir / "raw"
    transcript_dir = video_dir / "transcript"
    raw_dir.mkdir(exist_ok=True)
    transcript_dir.mkdir(exist_ok=True)

    safe_write(video_dir / "metadata.json", json.dumps(info, indent=2, ensure_ascii=False, sort_keys=True))
    safe_write(video_dir / "subtitles-list.txt", list_subs(yt_dlp, args.url))

    with tempfile.TemporaryDirectory(prefix="youtube-transcript-") as tmp_s:
        tmp = Path(tmp_s)
        cmd = [
            yt_dlp,
            "--skip-download",
            "--sub-langs",
            lang,
            "--sub-format",
            "vtt/best",
            "-o",
            f"{video_id}.%(ext)s",
        ]
        cmd.append("--write-subs" if source == "manual" else "--write-auto-subs")
        cmd.append(args.url)
        run(cmd, cwd=tmp)
        candidates = sorted(tmp.glob(f"{video_id}*.vtt")) or sorted(tmp.glob(f"{video_id}*"))
        if not candidates:
            raise SystemExit(f"yt-dlp did not produce a subtitle file for language {lang}")
        raw_vtt = raw_dir / f"{video_id}.{lang}.vtt"
        shutil.copyfile(candidates[0], raw_vtt)

    clean_lines, timestamped = parse_vtt(raw_vtt)
    timestamped_deduped = deoverlap_caption_stream(dedupe_consecutive(timestamped))
    clean_deduped = [text for _, text in timestamped_deduped]

    safe_write(transcript_dir / "clean.txt", "\n".join(clean_lines).strip() + "\n")
    safe_write(transcript_dir / "clean-deduped.txt", "\n".join(clean_deduped).strip() + "\n")
    safe_write(transcript_dir / "timestamped.txt", "\n".join(f"[{ts}] {text}" for ts, text in timestamped).strip() + "\n")
    safe_write(transcript_dir / "timestamped-deduped.txt", "\n".join(f"[{ts}] {text}" for ts, text in timestamped_deduped).strip() + "\n")

    rel_files = [
        "manifest.json",
        "metadata.json",
        "subtitles-list.txt",
        str(raw_vtt.relative_to(video_dir)),
        "transcript/clean.txt",
        "transcript/clean-deduped.txt",
        "transcript/timestamped.txt",
        "transcript/timestamped-deduped.txt",
        "report.md",
    ]
    manifest = {
        "status": "refreshed" if args.refresh else "created",
        "duplicate_policy": "refresh" if args.refresh else "reuse-existing-complete-archive",
        "video_id": video_id,
        "url": info.get("webpage_url") or args.url,
        "title": info.get("title"),
        "channel": info.get("channel") or info.get("uploader"),
        "language": lang,
        "transcript_source": source,
        "archived_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "yt_dlp_version": yt_dlp_version(yt_dlp),
        "files": rel_files,
        "notes": "caption-only archive; video/audio media not downloaded",
    }
    summary = Path(args.summary_file).read_text(encoding="utf-8") if args.summary_file else None
    report = report_markdown(info, manifest, summary, "\n".join(f"[{ts}] {text}" for ts, text in timestamped_deduped))
    safe_write(video_dir / "report.md", report)
    safe_write(manifest_path, json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True))

    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
