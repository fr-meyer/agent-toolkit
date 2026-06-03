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
from collections.abc import Callable
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


CaptionChoice = tuple[str, str, list[dict[str, Any]]]
CaptionDownloader = Callable[[str, str], Path]


def has_any_captions(info: dict[str, Any]) -> bool:
    subtitles = info.get("subtitles") or {}
    autos = info.get("automatic_captions") or {}
    return any(subtitles.values()) or any(autos.values())


def add_caption_choice(
    out: list[CaptionChoice],
    seen: set[tuple[str, str]],
    lang: str,
    source: str,
    entries: list[dict[str, Any]] | None,
) -> None:
    if entries and (lang, source) not in seen:
        out.append((lang, source, entries))
        seen.add((lang, source))


def caption_candidates(info: dict[str, Any], requested: str) -> list[CaptionChoice]:
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
                return [(found[0], source, found[1])]
        raise SystemExit(f"No captions found for requested language: {requested}")

    candidates: list[CaptionChoice] = []
    seen: set[tuple[str, str]] = set()

    def add_key(key: str, *, allow_prefix: bool = True) -> None:
        for source, pool in (("manual", subtitles), ("automatic", autos)):
            found = exact(pool, key) or (prefix(pool, key) if allow_prefix else None)
            if found:
                add_caption_choice(candidates, seen, found[0], source, found[1])

    source_language = info.get("language")
    source_base = source_language.split("-")[0] if isinstance(source_language, str) and source_language else None
    source_original_preferences = []
    for key in (f"{source_base}-orig" if source_base else None,):
        if key and key not in source_original_preferences:
            source_original_preferences.append(key)

    for key in source_original_preferences:
        add_key(key, allow_prefix=False)

    for source, pool in (("manual", subtitles), ("automatic", autos)):
        for lang in sorted(pool):
            if lang.endswith("-orig"):
                add_caption_choice(candidates, seen, lang, source, pool.get(lang))

    source_plain_preferences = []
    for key in (source_language, source_base):
        if key and key not in source_plain_preferences:
            source_plain_preferences.append(key)

    for key in source_plain_preferences:
        add_key(key)

    preferences = ["en", "fr", "ko"]
    for key in preferences:
        add_key(key)

    for source, pool in (("manual", subtitles), ("automatic", autos)):
        for lang in sorted(pool):
            entries = pool.get(lang) or []
            if entries:
                add_caption_choice(candidates, seen, lang, source, entries)

    if not candidates:
        raise SystemExit("No subtitles or automatic captions found for this video")
    return candidates


def choose_caption(info: dict[str, Any], requested: str) -> CaptionChoice:
    return caption_candidates(info, requested)[0]


def list_subs(yt_dlp: str, url: str) -> str:
    try:
        cp = run([yt_dlp, "--list-subs", url])
        return cp.stdout + (cp.stderr or "")
    except subprocess.CalledProcessError as exc:
        return (exc.stdout or "") + (exc.stderr or "")


def caption_error_summary(exc: subprocess.CalledProcessError | RuntimeError) -> str:
    if isinstance(exc, subprocess.CalledProcessError):
        detail = (exc.stderr or exc.stdout or "").strip()
        detail = detail or f"yt-dlp exited with status {exc.returncode}"
    else:
        detail = str(exc).strip()
    detail = WS_RE.sub(" ", detail)
    if len(detail) > 500:
        detail = detail[:497].rstrip() + "..."
    return detail


def download_caption_vtt(yt_dlp: str, url: str, video_id: str, lang: str, source: str, video_dir: Path) -> Path:
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
        cmd.append(url)
        run(cmd, cwd=tmp)
        candidates = sorted(tmp.glob(f"{video_id}*.vtt")) or sorted(tmp.glob(f"{video_id}*"))
        if not candidates:
            raise RuntimeError(f"yt-dlp did not produce a subtitle file for language {lang}")
        raw_vtt = video_dir / "raw" / lang / f"{video_id}.{lang}.vtt"
        raw_vtt.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(candidates[0], raw_vtt)
        return raw_vtt


def select_caption_vtt(
    choices: list[CaptionChoice],
    requested: str,
    no_caption_fallback: bool,
    download: CaptionDownloader,
) -> tuple[str, str, Path, list[str]]:
    attempt_errors: list[str] = []
    for lang, source, _entries in choices:
        try:
            raw_vtt = download(lang, source)
            return lang, source, raw_vtt, attempt_errors
        except (subprocess.CalledProcessError, RuntimeError) as exc:
            summary = caption_error_summary(exc)
            attempt_errors.append(f"{lang} ({source}): {summary}")
            if requested != "best" or no_caption_fallback:
                raise RuntimeError(f"Caption download failed for {lang} ({source}): {summary}") from exc

    details = "\n".join(f"- {error}" for error in attempt_errors)
    raise RuntimeError(f"Caption download failed for all selected caption candidates:\n{details}")


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


def manifest_path_for(video_dir: Path, lang: str | None) -> Path:
    if lang and lang != "best":
        return video_dir / "manifests" / f"{lang}.json"
    return video_dir / "manifest.json"


def resolve_existing_archive(video_dir: Path, requested_lang: str) -> dict[str, Any] | None:
    manifest_path = manifest_path_for(video_dir, requested_lang)
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


def metadata_only_report_markdown(meta: dict[str, Any], manifest: dict[str, Any]) -> str:
    title = meta.get("title") or meta.get("id") or "Untitled video"
    files = "\n".join(f"- `{p}`" for p in manifest.get("files", []))
    return f"""# YouTube Transcript Archive — {title}

## Metadata
- URL: {manifest.get('url') or meta.get('webpage_url') or meta.get('original_url') or ''}
- Video ID: {meta.get('id') or ''}
- Title: {title}
- Channel: {meta.get('channel') or meta.get('uploader') or 'unknown'}
- Upload date: {meta.get('upload_date') or 'unknown'}
- Duration: {duration_text(meta.get('duration'))}
- Language: {manifest.get('language') or 'unknown'}
- Transcript source: none
- Archived at: {manifest.get('archived_at') or ''}
- yt-dlp version: {manifest.get('yt_dlp_version') or 'unknown'}

## Processing status
- Status: {manifest.get('status') or 'metadata-only-no-captions'}
- Duplicate policy: {manifest.get('duplicate_policy') or 'unknown'}
- Files generated or reused:
{files}
- Notes: no subtitles or automatic captions exposed by YouTube; video/audio media not downloaded

## Summary
Metadata-only archive. YouTube exposed no manual subtitles or automatic captions for this video, so no transcript-based summary is available.

## Detailed summary
- Title: {title}
- Channel: {meta.get('channel') or meta.get('uploader') or 'unknown'}
- This entry is retained as provenance for the shared link, but it should not be treated as a transcript archive.

## Full transcript
No transcript available.
"""


def write_base_artifacts(video_dir: Path, info: dict[str, Any], subtitles_list: str) -> None:
    video_dir.mkdir(parents=True, exist_ok=True)
    safe_write(video_dir / "metadata.json", json.dumps(info, indent=2, ensure_ascii=False, sort_keys=True))
    safe_write(video_dir / "subtitles-list.txt", subtitles_list)


def write_metadata_only_archive(
    video_dir: Path,
    info: dict[str, Any],
    *,
    yt_dlp_version_text: str,
    duplicate_policy: str,
) -> dict[str, Any]:
    video_id = info.get("id") or video_dir.name
    manifest = {
        "status": "metadata-only-no-captions",
        "duplicate_policy": duplicate_policy,
        "video_id": video_id,
        "url": info.get("webpage_url") or info.get("original_url") or "",
        "title": info.get("title"),
        "channel": info.get("channel") or info.get("uploader"),
        "language": info.get("language") or "unknown",
        "transcript_source": "none",
        "archived_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "yt_dlp_version": yt_dlp_version_text,
        "files": [
            "manifest.json",
            "metadata.json",
            "subtitles-list.txt",
            "report.md",
        ],
        "notes": "metadata-only archive; no subtitles or automatic captions exposed by YouTube; video/audio media not downloaded",
    }
    manifest_json = json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True)
    safe_write(video_dir / "report.md", metadata_only_report_markdown(info, manifest))
    safe_write(video_dir / "manifest.json", manifest_json)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="YouTube URL or video ID")
    parser.add_argument("--archive-root", required=True, help="Trusted archive root directory")
    parser.add_argument("--lang", default="best", help="Caption language preference, e.g. en, fr, fr-orig, or best")
    parser.add_argument("--refresh", action="store_true", help="Refresh an existing complete archive in place")
    parser.add_argument("--yt-dlp-bin", default=os.environ.get("YT_DLP", "yt-dlp"), help="yt-dlp binary path")
    parser.add_argument("--summary-file", help="Optional Markdown summary to inject into report.md")
    parser.add_argument(
        "--no-caption-fallback",
        action="store_true",
        help="Do not retry alternate caption tracks when --lang best selects a track that yt-dlp cannot download",
    )
    parser.add_argument(
        "--max-caption-candidates",
        type=int,
        default=12,
        help="Maximum best-mode caption tracks to try before failing; ignored for explicit --lang values",
    )
    parser.add_argument(
        "--metadata-only-on-no-captions",
        action="store_true",
        help="Create a metadata-only archive instead of failing when YouTube exposes no captions",
    )
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
    if not args.refresh:
        existing = resolve_existing_archive(video_dir, args.lang)
        if existing:
            existing["status"] = "reused"
            existing["notes"] = "complete existing archive reused; use --refresh to reprocess"
            print(json.dumps(existing, indent=2, ensure_ascii=False))
            return 0

    subtitles_text: str | None = None

    def ensure_base_artifacts() -> None:
        nonlocal subtitles_text
        if subtitles_text is None:
            subtitles_text = list_subs(yt_dlp, args.url)
        if args.refresh or not (video_dir / "metadata.json").exists() or not (video_dir / "subtitles-list.txt").exists():
            write_base_artifacts(video_dir, info, subtitles_text)

    try:
        choices = caption_candidates(info, args.lang)
    except SystemExit:
        if args.metadata_only_on_no_captions and not has_any_captions(info):
            ensure_base_artifacts()
            manifest = write_metadata_only_archive(
                video_dir,
                info,
                yt_dlp_version_text=yt_dlp_version(yt_dlp),
                duplicate_policy="refresh" if args.refresh else "reuse-existing-complete-archive",
            )
            print(json.dumps(manifest, indent=2, ensure_ascii=False))
            return 0
        raise
    if args.lang == "best":
        max_candidates = max(1, args.max_caption_candidates)
        choices = choices[:max_candidates]

    if args.lang == "best" and not args.refresh:
        for candidate_lang, _candidate_source, _entries in choices:
            existing = resolve_existing_archive(video_dir, candidate_lang)
            if existing:
                existing["status"] = "reused"
                existing["notes"] = "complete existing archive reused after resolving best language; use --refresh to reprocess"
                print(json.dumps(existing, indent=2, ensure_ascii=False))
                return 0

    ensure_base_artifacts()

    def download_selected(candidate_lang: str, candidate_source: str) -> Path:
        return download_caption_vtt(yt_dlp, args.url, video_id, candidate_lang, candidate_source, video_dir)

    try:
        lang, source, raw_vtt, attempt_errors = select_caption_vtt(
            choices,
            args.lang,
            args.no_caption_fallback,
            download_selected,
        )
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc

    transcript_dir = video_dir / "transcript" / lang
    reports_dir = video_dir / "reports"
    manifests_dir = video_dir / "manifests"
    transcript_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(exist_ok=True)
    manifests_dir.mkdir(exist_ok=True)

    clean_lines, timestamped = parse_vtt(raw_vtt)
    timestamped_deduped = deoverlap_caption_stream(dedupe_consecutive(timestamped))
    clean_deduped = [text for _, text in timestamped_deduped]

    safe_write(transcript_dir / "clean.txt", "\n".join(clean_lines).strip() + "\n")
    safe_write(transcript_dir / "clean-deduped.txt", "\n".join(clean_deduped).strip() + "\n")
    safe_write(transcript_dir / "timestamped.txt", "\n".join(f"[{ts}] {text}" for ts, text in timestamped).strip() + "\n")
    safe_write(transcript_dir / "timestamped-deduped.txt", "\n".join(f"[{ts}] {text}" for ts, text in timestamped_deduped).strip() + "\n")

    lang_manifest = manifests_dir / f"{lang}.json"
    lang_report = reports_dir / f"{lang}.md"
    rel_files = [
        "manifest.json",
        "metadata.json",
        "subtitles-list.txt",
        str(lang_manifest.relative_to(video_dir)),
        str(raw_vtt.relative_to(video_dir)),
        str((transcript_dir / "clean.txt").relative_to(video_dir)),
        str((transcript_dir / "clean-deduped.txt").relative_to(video_dir)),
        str((transcript_dir / "timestamped.txt").relative_to(video_dir)),
        str((transcript_dir / "timestamped-deduped.txt").relative_to(video_dir)),
        str(lang_report.relative_to(video_dir)),
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
    if attempt_errors:
        manifest["notes"] += f"; selected {lang} after caption download fallback"
        manifest["caption_fallback_errors"] = attempt_errors
    summary = Path(args.summary_file).read_text(encoding="utf-8") if args.summary_file else None
    report = report_markdown(info, manifest, summary, "\n".join(f"[{ts}] {text}" for ts, text in timestamped_deduped))
    manifest_json = json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True)
    safe_write(lang_report, report)
    safe_write(video_dir / "report.md", report)
    safe_write(lang_manifest, manifest_json)
    safe_write(video_dir / "manifest.json", manifest_json)

    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
