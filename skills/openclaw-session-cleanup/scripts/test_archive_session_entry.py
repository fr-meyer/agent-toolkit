#!/usr/bin/env python3
"""Fixture tests for archive_session_entry.py."""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path


SCRIPT = Path(__file__).with_name("archive_session_entry.py")
TARGET_KEY = "agent:test:dashboard:one"
MAIN_KEY = "agent:test:main"
CURRENT_KEY = "agent:test:dashboard:current"


def run_helper(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        text=True,
        capture_output=True,
        check=False,
    )
    if check and result.returncode != 0:
        raise AssertionError(f"helper failed: {result.stderr}\nstdout={result.stdout}")
    return result


def make_fixture() -> tuple[Path, Path]:
    root = Path(tempfile.mkdtemp(prefix="oc-session-archive-test-"))
    session_dir = root / "sessions"
    session_dir.mkdir()
    store = session_dir / "sessions.json"
    transcript = session_dir / "abc123.jsonl"
    topic_transcript = session_dir / "abc123-topic-42.jsonl"
    transcript.write_text('{"type":"session","id":"abc123"}\n', encoding="utf-8")
    topic_transcript.write_text('{"type":"session","id":"abc123-topic"}\n', encoding="utf-8")
    store.write_text(
        json.dumps(
            {
                TARGET_KEY: {"sessionId": "abc123", "updatedAt": 1},
                CURRENT_KEY: {"sessionId": "current123", "updatedAt": 2},
                MAIN_KEY: {"sessionId": "main123", "updatedAt": 3},
            }
        ),
        encoding="utf-8",
    )
    os.chmod(store, 0o640)
    return store, transcript


def test_dry_run_and_apply() -> None:
    store, _ = make_fixture()
    dry = run_helper("--store", str(store), "--key", TARGET_KEY, "--protect-key", CURRENT_KEY, "--json")
    dry_data = json.loads(dry.stdout)
    assert dry_data["dryRun"] is True
    assert dry_data["entryFound"] is True
    assert len(dry_data["archivePlan"]) == 2
    assert TARGET_KEY in json.loads(store.read_text(encoding="utf-8"))

    applied = run_helper(
        "--store",
        str(store),
        "--key",
        TARGET_KEY,
        "--protect-key",
        CURRENT_KEY,
        "--apply",
        "--confirm-key",
        TARGET_KEY,
        "--json",
    )
    applied_data = json.loads(applied.stdout)
    after = json.loads(store.read_text(encoding="utf-8"))
    assert TARGET_KEY not in after
    assert CURRENT_KEY in after
    assert MAIN_KEY in after
    assert applied_data["backupCreated"]
    assert len(applied_data["archived"]) == 2
    assert all(Path(path).exists() for path in applied_data["archived"])
    assert stat.S_IMODE(store.stat().st_mode) == 0o640


def test_protections() -> None:
    store, _ = make_fixture()
    protected = run_helper("--store", str(store), "--key", TARGET_KEY, "--protect-key", TARGET_KEY, check=False)
    assert protected.returncode != 0
    assert "protected session key" in protected.stderr

    main = run_helper("--store", str(store), "--key", MAIN_KEY, check=False)
    assert main.returncode != 0
    assert "main session" in main.stderr


def main() -> int:
    test_dry_run_and_apply()
    test_protections()
    print("archive_session_entry fixture tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
