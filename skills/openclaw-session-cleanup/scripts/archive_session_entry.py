#!/usr/bin/env python3
"""Safely archive one OpenClaw session-store entry as a fallback repair path.

Default mode is dry-run. Apply mode requires --confirm-key equal to --key.
This script does not contact the Gateway and should only be used after a
preview/confirmation workflow when supported Gateway/UI/API deletion is not
available and the operator has confirmed that a direct-store fallback is safe.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def die(message: str, code: int = 1) -> None:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(code)


def resolve_store(args: argparse.Namespace) -> Path:
    if args.store:
        return Path(args.store).expanduser().resolve()
    if not args.agent:
        die("either --agent or --store is required")
    home = Path(os.environ.get("OPENCLAW_HOME", Path.home() / ".openclaw")).expanduser()
    return (home / "agents" / args.agent / "sessions" / "sessions.json").resolve()


def load_store(path: Path) -> dict[str, Any]:
    if not path.exists():
        die(f"session store not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        die(f"invalid JSON in {path}: {exc}")
    if not isinstance(data, dict):
        die("unsupported sessions.json shape: expected an object mapping session keys to entries")
    return data


def is_main_key(key: str) -> bool:
    return key == "main" or key.endswith(":main")


def timestamp() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y%m%dT%H%M%S%z")


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    for i in range(1, 1000):
        candidate = path.with_name(f"{path.name}.{i}")
        if not candidate.exists():
            return candidate
    die(f"could not find unique archive path for {path}")


def candidate_transcripts(store_path: Path, entry: dict[str, Any]) -> list[Path]:
    session_dir = store_path.parent
    paths: list[Path] = []

    session_file = entry.get("sessionFile")
    if isinstance(session_file, str) and session_file.strip():
        p = Path(session_file).expanduser()
        if not p.is_absolute():
            p = session_dir / p
        paths.append(p.resolve())

    session_id = entry.get("sessionId")
    if isinstance(session_id, str) and session_id.strip():
        base = (session_dir / f"{session_id}.jsonl").resolve()
        paths.append(base)
        for p in session_dir.glob(f"{session_id}-topic-*.jsonl"):
            paths.append(p.resolve())

    # Preserve order while deduplicating.
    seen: set[Path] = set()
    unique: list[Path] = []
    for p in paths:
        if p not in seen:
            seen.add(p)
            unique.append(p)
    return unique


def atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    original_mode = path.stat().st_mode & 0o7777 if path.exists() else None
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        if original_mode is not None:
            os.chmod(tmp_name, original_mode)
        os.replace(tmp_name, path)
    finally:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--agent", help="OpenClaw agent id; resolves ~/.openclaw/agents/<agent>/sessions/sessions.json")
    target.add_argument("--store", help="explicit sessions.json path for offline repair")
    parser.add_argument("--key", required=True, help="exact session key to archive")
    parser.add_argument(
        "--protect-key",
        action="append",
        default=[],
        help="additional exact session key to refuse; repeat for current or active keys",
    )
    parser.add_argument("--apply", action="store_true", help="write changes; otherwise dry-run only")
    parser.add_argument("--confirm-key", help="must exactly equal --key in --apply mode")
    parser.add_argument("--allow-main", action="store_true", help="allow archiving a main session (strongly discouraged)")
    parser.add_argument("--keep-transcript", action="store_true", help="remove store entry but do not rename transcript files")
    parser.add_argument("--json", action="store_true", help="print machine-readable result")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    store_path = resolve_store(args)
    key = args.key
    protected_keys = set(args.protect_key or [])

    if key in protected_keys:
        die(f"refusing to archive protected session key: {key}")
    if is_main_key(key) and not args.allow_main:
        die("refusing to archive a main session without --allow-main")

    store = load_store(store_path)
    entry = store.get(key)
    transcript_paths = candidate_transcripts(store_path, entry) if isinstance(entry, dict) else []
    existing_transcripts = [p for p in transcript_paths if p.exists()]
    ts = timestamp()
    backup_path = store_path.with_name(f"{store_path.name}.bak-before-archive-{ts}")
    archive_plan = [
        {
            "source": str(p),
            "archive": str(unique_path(p.with_name(f"{p.name}.deleted.{ts}"))),
        }
        for p in existing_transcripts
    ]

    result: dict[str, Any] = {
        "ok": True,
        "dryRun": not args.apply,
        "storePath": str(store_path),
        "key": key,
        "protectedKeys": sorted(protected_keys),
        "entryFound": entry is not None,
        "backupPath": str(backup_path) if entry is not None else None,
        "transcriptsFound": [str(p) for p in existing_transcripts],
        "archivePlan": [] if args.keep_transcript else archive_plan,
        "warnings": [],
    }

    if entry is None:
        result["warnings"].append("session key not found; no mutation needed")
        print_result(result, args.json)
        return 0

    if args.apply:
        if args.confirm_key != key:
            die("--apply requires --confirm-key exactly equal to --key")
        if not store_path.parent.exists():
            die(f"session store directory missing: {store_path.parent}")
        shutil.copy2(store_path, backup_path)
        mutated = dict(store)
        del mutated[key]
        atomic_write_json(store_path, mutated)
        archived: list[str] = []
        if not args.keep_transcript:
            for item in archive_plan:
                src = Path(item["source"])
                dst = Path(item["archive"])
                if src.exists():
                    src.rename(dst)
                    archived.append(str(dst))
        result["archived"] = archived
        result["backupCreated"] = str(backup_path)
    else:
        result["note"] = "dry-run only; add --apply --confirm-key '<sessionKey>' after explicit confirmation"

    print_result(result, args.json)
    return 0


def print_result(result: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return
    print(f"Mode: {'dry-run' if result['dryRun'] else 'apply'}")
    print(f"Store: {result['storePath']}")
    print(f"Key: {result['key']}")
    print(f"Entry found: {result['entryFound']}")
    if result.get("backupPath"):
        print(f"Backup: {result['backupPath']}")
    if result.get("transcriptsFound"):
        print("Transcripts:")
        for p in result["transcriptsFound"]:
            print(f"  - {p}")
    if result.get("archivePlan"):
        print("Archive plan:")
        for item in result["archivePlan"]:
            print(f"  - {item['source']} -> {item['archive']}")
    if result.get("archived"):
        print("Archived:")
        for p in result["archived"]:
            print(f"  - {p}")
    for warning in result.get("warnings", []):
        print(f"Warning: {warning}")
    if result.get("note"):
        print(result["note"])


if __name__ == "__main__":
    raise SystemExit(main())
