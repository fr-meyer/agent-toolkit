#!/usr/bin/env python3
"""
Run an external AI agent command in a bounded, reusable way.

CLI:
  python scripts/github/run_repo_maintenance_agent.py \
    --repo-path . \
    --prompt-path .tmp/reusable-workflow-ref-sync/prompt.txt \
    --context-path .tmp/reusable-workflow-ref-sync/context.json \
    --out-dir .tmp/reusable-workflow-ref-sync/output

Environment overrides (optional):
  - WORKFLOW_REF_SYNC_AGENT_COMMAND_JSON
  - WORKFLOW_REF_SYNC_AGENT_COMMAND

Exit codes:
  0  – agent ran successfully
  1  – misconfiguration or runtime error
"""

import argparse
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def render_template(value: str, substitutions: Dict[str, str]) -> str:
    try:
        return value.format(**substitutions)
    except KeyError as exc:
        missing = exc.args[0]
        raise ValueError(f"Unknown command template placeholder: {missing}") from exc


def parse_command_spec(substitutions: Dict[str, str]) -> Dict[str, Any]:
    raw_json = os.environ.get("WORKFLOW_REF_SYNC_AGENT_COMMAND_JSON")
    if raw_json:
        parsed = json.loads(raw_json)
        if not isinstance(parsed, list) or not parsed or not all(isinstance(item, str) and item for item in parsed):
            raise ValueError("WORKFLOW_REF_SYNC_AGENT_COMMAND_JSON must be a non-empty JSON array of strings.")
        rendered = [render_template(item, substitutions) for item in parsed]
        return {
            "source": "WORKFLOW_REF_SYNC_AGENT_COMMAND_JSON",
            "command": rendered,
        }

    raw_command = os.environ.get("WORKFLOW_REF_SYNC_AGENT_COMMAND")
    if raw_command:
        rendered = render_template(raw_command, substitutions)
        return {
            "source": "WORKFLOW_REF_SYNC_AGENT_COMMAND",
            "command": shlex.split(rendered, posix=os.name != "nt"),
        }

    return {
        "source": None,
        "command": None,
    }


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def summarize_text(summary: Dict[str, Any]) -> str:
    lines: List[str] = [
        f"status: {summary.get('status')}",
        f"repo path: {summary.get('repoPath')}",
        f"prompt path: {summary.get('promptPath')}",
        f"context path: {summary.get('contextPath')}",
        f"out dir: {summary.get('outDir')}",
    ]
    if summary.get("command"):
        lines.append("command: " + " ".join(summary["command"]))
    if summary.get("note"):
        lines.extend(["", f"note: {summary['note']}"])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run repo maintenance agent.")
    parser.add_argument("--repo-path", required=True, type=Path)
    parser.add_argument("--prompt-path", required=True, type=Path)
    parser.add_argument("--context-path", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)

    args = parser.parse_args()

    out_dir = args.out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    substitutions = {
        "repo_path": str(args.repo_path.resolve()),
        "prompt_path": str(args.prompt_path.resolve()),
        "context_path": str(args.context_path.resolve()),
        "out_dir": str(out_dir),
    }

    try:
        cmd_spec = parse_command_spec(substitutions)
    except Exception as exc:
        summary = {
            "status": "misconfigured",
            "repoPath": str(args.repo_path),
            "promptPath": str(args.prompt_path),
            "contextPath": str(args.context_path),
            "outDir": str(out_dir),
            "command": None,
            "note": str(exc),
        }
        write_json(out_dir / "agent-summary.json", summary)
        (out_dir / "agent-summary.txt").write_text(summarize_text(summary), encoding="utf-8")
        print(f"Agent misconfigured: {out_dir / 'agent-summary.json'}")
        return 1

    if not cmd_spec["command"]:
        summary = {
            "status": "not_configured",
            "repoPath": str(args.repo_path),
            "promptPath": str(args.prompt_path),
            "contextPath": str(args.context_path),
            "outDir": str(out_dir),
            "command": None,
            "note": "No agent command configured. Set WORKFLOW_REF_SYNC_AGENT_COMMAND_JSON (preferred) or WORKFLOW_REF_SYNC_AGENT_COMMAND.",
        }
        write_json(out_dir / "agent-summary.json", summary)
        (out_dir / "agent-summary.txt").write_text(summarize_text(summary), encoding="utf-8")
        print(f"Agent not configured: {out_dir / 'agent-summary.json'}")
        return 0

    stdout_path = out_dir / "agent-raw.stdout.txt"
    stderr_path = out_dir / "agent-raw.stderr.txt"
    command_path = out_dir / "agent-command.json"

    command_path.write_text(json.dumps(cmd_spec, indent=2) + "\n", encoding="utf-8")

    agent_env = os.environ.copy()
    agent_env.update({
        "WORKFLOW_REF_SYNC_REPO_PATH": substitutions["repo_path"],
        "WORKFLOW_REF_SYNC_PROMPT_PATH": substitutions["prompt_path"],
        "WORKFLOW_REF_SYNC_CONTEXT_PATH": substitutions["context_path"],
        "WORKFLOW_REF_SYNC_OUT_DIR": substitutions["out_dir"],
    })

    completed = subprocess.run(
        cmd_spec["command"],
        cwd=args.repo_path,
        env=agent_env,
        text=True,
        capture_output=True,
        check=False,
    )

    stdout_path.write_text(completed.stdout, encoding="utf-8")
    stderr_path.write_text(completed.stderr, encoding="utf-8")

    summary = {
        "status": "completed" if completed.returncode == 0 else "failed",
        "repoPath": str(args.repo_path),
        "promptPath": str(args.prompt_path),
        "contextPath": str(args.context_path),
        "outDir": str(out_dir),
        "command": cmd_spec["command"],
        "commandSource": cmd_spec["source"],
        "exitCode": completed.returncode,
        "note": None,
    }
    write_json(out_dir / "agent-summary.json", summary)
    (out_dir / "agent-summary.txt").write_text(summarize_text(summary), encoding="utf-8")

    if completed.returncode != 0:
        print(f"Agent failed with exit {completed.returncode}: {out_dir / 'agent-summary.json'}")
        return 1

    print(f"Agent completed: {out_dir / 'agent-summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
