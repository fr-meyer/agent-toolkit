#!/usr/bin/env python3
"""Render OpenClaw sessions JSON metadata as a compact Markdown sidecar index.

This script is intentionally metadata-only: it does not read transcripts, mutate
session stores, or call OpenClaw itself. Feed it output from `openclaw sessions
--json` or a compatible JSON object with a `sessions` array.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip() or default
    return str(value).strip() or default


def safe_cell(value: Any, default: str = "n/a", limit: int = 80) -> str:
    raw = text(value, default)
    raw = raw.replace("\r", " ").replace("\n", " ").replace("|", "\\|")
    raw = " ".join(raw.split())
    if len(raw) > limit:
        return raw[: max(1, limit - 1)] + "…"
    return raw


def iso_from_ms(value: Any) -> str:
    if not isinstance(value, (int, float)):
        return "n/a"
    try:
        return datetime.fromtimestamp(value / 1000, tz=timezone.utc).isoformat(timespec="minutes")
    except Exception:
        return "n/a"


def token_summary(session: dict[str, Any]) -> str:
    total = session.get("totalTokens")
    if isinstance(total, (int, float)):
        return f"{int(total):,}"
    input_tokens = session.get("inputTokens")
    output_tokens = session.get("outputTokens")
    if isinstance(input_tokens, (int, float)) or isinstance(output_tokens, (int, float)):
        return f"in:{int(input_tokens or 0):,} out:{int(output_tokens or 0):,}"
    return "n/a"


def title_for(session: dict[str, Any]) -> str:
    for key in ("label", "displayName", "derivedTitle", "subject"):
        value = text(session.get(key))
        if value:
            return value
    key = text(session.get("key"), "unknown")
    if len(key) <= 42:
        return key
    return f"{key[:24]}…{key[-12:]}"


def status_for(session: dict[str, Any], protected_keys: set[str]) -> str:
    key = text(session.get("key"))
    if session.get("isCurrent") or session.get("current"):
        return "current/protect"
    if key in protected_keys:
        return "protected"
    if session.get("hasActiveRun") or session.get("hasActiveSubagentRun"):
        return "active/protect"
    if key.endswith(":main") or key == "main":
        return "main/protect"
    status = text(session.get("status"))
    if status:
        return status
    if session.get("archived") is True:
        return "archived"
    return "review"


def load_json(path_arg: str) -> dict[str, Any]:
    if path_arg == "-":
        data = sys.stdin.read()
    else:
        data = Path(path_arg).read_text(encoding="utf-8")
    parsed = json.loads(data)
    if isinstance(parsed, list):
        return {"sessions": parsed}
    if not isinstance(parsed, dict):
        raise SystemExit("input JSON must be an object or an array")
    if not isinstance(parsed.get("sessions"), list):
        raise SystemExit("input JSON must contain a sessions array")
    return parsed


def render(data: dict[str, Any], *, title: str, max_rows: int, include_store_paths: bool, protected_keys: set[str]) -> str:
    sessions = [s for s in data.get("sessions", []) if isinstance(s, dict)]
    sessions.sort(key=lambda s: s.get("updatedAt") if isinstance(s.get("updatedAt"), (int, float)) else 0, reverse=True)
    if max_rows > 0:
        sessions = sessions[:max_rows]

    generated = datetime.now(timezone.utc).isoformat(timespec="seconds")
    path = data.get("path")
    stores = data.get("stores")
    scope_parts = []
    if path and include_store_paths:
        scope_parts.append(f"store `{safe_cell(path, limit=140)}`")
    elif path:
        scope_parts.append("store path redacted")
    if isinstance(stores, list) and stores:
        scope_parts.append(f"{len(stores)} stores")
    if data.get("allAgents") is True:
        scope_parts.append("all agents")
    scope = ", ".join(scope_parts) or "session JSON input"

    lines: list[str] = []
    lines.append(f"# {title}")
    lines.append("")
    lines.append(f"Generated: {generated}")
    lines.append(f"Scope: {scope}")
    lines.append("Mode: read-only sidecar index starter")
    if "totalCount" in data:
        lines.append(f"Rows: {len(sessions)} shown / {data.get('totalCount')} total")
    else:
        lines.append(f"Rows: {len(sessions)} shown")
    if data.get("hasMore"):
        lines.append("Note: source reported more rows than shown; rerun with a higher limit if needed.")
    lines.append("")
    lines.append("## Notes")
    lines.append("- This file is a sidecar recall aid, not OpenClaw runtime state.")
    lines.append("- Titles come from metadata only; refine manually with minimal history checks when needed.")
    lines.append("- Do not store secrets, private identifiers, or transcript dumps here.")
    lines.append("")
    lines.append("## Sessions")
    lines.append("| Title | Session key | Kind | Agent | Updated | Status | Model | Tokens | Notes |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for session in sessions:
        key = safe_cell(session.get("key"), limit=90)
        lines.append(
            "| "
            + " | ".join(
                [
                    safe_cell(title_for(session), limit=52),
                    f"`{key}`",
                    safe_cell(session.get("kind"), limit=18),
                    safe_cell(session.get("agentId"), limit=24),
                    safe_cell(iso_from_ms(session.get("updatedAt")), limit=28),
                    safe_cell(status_for(session, protected_keys), limit=24),
                    safe_cell(session.get("model"), limit=32),
                    safe_cell(token_summary(session), limit=18),
                    "metadata-only; review before cleanup",
                ]
            )
            + " |"
        )
    lines.append("")
    lines.append("## Cleanup/archive candidates")
    lines.append("| Candidate | Reason | Required confirmation before mutation |")
    lines.append("| --- | --- | --- |")
    lines.append("| _none selected_ | Add candidates after human/agent review. | Explicit confirmation + backup + reversible archive path. |")
    lines.append("")
    lines.append("## Unsaved deltas preserved")
    lines.append("- _none captured by the metadata renderer_; add only unique unsaved decisions, blockers, TODOs, or work products.")
    lines.append("")
    lines.append("## Source provenance")
    lines.append("- Input: OpenClaw sessions JSON metadata.")
    if path and include_store_paths:
        lines.append(f"- Store path from JSON: `{safe_cell(path, limit=180)}`")
    elif path:
        lines.append("- Store path from JSON: redacted by default; rerun with `--include-store-paths` for private local indexes if useful.")
    if isinstance(stores, list) and stores:
        for store in stores[:20]:
            if isinstance(store, dict):
                if include_store_paths:
                    lines.append(f"- Store: `{safe_cell(store.get('agentId'), limit=40)}` -> `{safe_cell(store.get('path'), limit=180)}`")
                else:
                    lines.append(f"- Store: `{safe_cell(store.get('agentId'), limit=40)}` -> path redacted")
    lines.append("- Transcript/history reads: none by this script.")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render OpenClaw sessions JSON as a Markdown sidecar index.")
    parser.add_argument("json_input", help="Path to openclaw sessions --json output, or '-' for stdin")
    parser.add_argument("--output", "-o", help="Markdown output path. Defaults to stdout.")
    parser.add_argument("--title", default=f"OpenClaw session index — {datetime.now().date().isoformat()}")
    parser.add_argument("--max-rows", type=int, default=100, help="Maximum rows to render; use 0 for all rows")
    parser.add_argument("--protect-key", action="append", default=[], help="Session key to mark as protected; can be repeated")
    parser.add_argument("--include-store-paths", action="store_true", help="Include local session store paths in provenance. Defaults to redacted.")
    parser.add_argument("--force", action="store_true", help="Overwrite output path if it already exists")
    args = parser.parse_args(argv)

    data = load_json(args.json_input)
    markdown = render(
        data,
        title=args.title,
        max_rows=args.max_rows,
        include_store_paths=args.include_store_paths,
        protected_keys={text(key) for key in args.protect_key if text(key)},
    )
    if args.output:
        out = Path(args.output)
        if out.exists() and not args.force:
            raise SystemExit(f"output exists (use --force to overwrite): {out}")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(markdown, encoding="utf-8")
    else:
        sys.stdout.write(markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
