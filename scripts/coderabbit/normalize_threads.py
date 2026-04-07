#!/usr/bin/env python3
import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

SEVERITY_ORDER = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
    "unknown": 4,
}

CODERABBIT_PREFIXES = (
    "coderabbit",
    "coderabbitai",
)

PROMPT_SECTION_PATTERNS = [
    re.compile(
        r"(?ims)^#{1,6}\s*prompt\s+for\s+ai\s+agents\s*$\n(?P<body>.*?)(?=^#{1,6}\s+|\Z)"
    ),
    re.compile(
        r"(?ims)^\*\*prompt\s+for\s+ai\s+agents\*\*:?\s*$\n(?P<body>.*?)(?=^\*\*|^#{1,6}\s+|\Z)"
    ),
    re.compile(
        r"(?ims)prompt\s+for\s+ai\s+agents\s*:?\s*(?P<body>.+)$"
    ),
]

HEADING_PREFIX = re.compile(r"^#{1,6}\s+")
MARKDOWN_DECORATION = re.compile(r"^[>*`\-\s]+|[*_`]+$")
INLINE_CODE = re.compile(r"`([^`]+)`")
BOLD_SPAN = re.compile(r"\*\*([^*]+)\*\*")
LINK_SPAN = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
WHITESPACE = re.compile(r"\s+")


def git_output(repo_path: str, *args: str) -> str:
    return subprocess.check_output(["git", "-C", repo_path, *args], text=True).strip()


def parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"Unsupported boolean value: {value}")


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def is_coderabbit_author(login: Optional[str]) -> bool:
    if not login:
        return False
    lowered = login.strip().lower()
    return any(lowered.startswith(prefix) for prefix in CODERABBIT_PREFIXES)


def strip_markdown(text: str) -> str:
    text = LINK_SPAN.sub(r"\1", text)
    text = INLINE_CODE.sub(r"\1", text)
    text = BOLD_SPAN.sub(r"\1", text)
    lines = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            lines.append("")
            continue
        line = MARKDOWN_DECORATION.sub("", line).strip()
        lines.append(line)
    text = "\n".join(lines)
    text = WHITESPACE.sub(" ", text)
    return text.strip()


def normalize_paragraphs(text: str) -> List[str]:
    cleaned = strip_markdown(text)
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", cleaned) if p.strip()]
    if not paragraphs and cleaned:
        paragraphs = [cleaned]
    return paragraphs


def extract_prompt_section(body: str) -> Optional[str]:
    for pattern in PROMPT_SECTION_PATTERNS:
        match = pattern.search(body)
        if not match:
            continue
        extracted = strip_markdown(match.group("body"))
        if extracted:
            return extracted
    return None


def body_without_prompt(body: str) -> str:
    text = body
    for pattern in PROMPT_SECTION_PATTERNS[:2]:
        text = pattern.sub("", text)
    return text.strip()


def first_meaningful_line(body: str) -> Optional[str]:
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        lowered = line.lower().strip(":")
        if lowered in {"prompt for ai agents", "summary", "why this matters", "suggestion"}:
            continue
        if HEADING_PREFIX.match(line):
            line = HEADING_PREFIX.sub("", line).strip()
        line = strip_markdown(line)
        if not line:
            continue
        if len(line) > 220:
            continue
        return line.rstrip(":")
    return None


def detect_severity(body: str) -> str:
    lowered = body.lower()
    labeled = re.search(r"severity\s*[:\-]\s*(critical|high|medium|low)", lowered)
    if labeled:
        return labeled.group(1)
    for level in ("critical", "high", "medium", "low"):
        if re.search(rf"\b{level}\b", lowered):
            return level
    return "unknown"


def detect_issue_type(body: str, title: str) -> str:
    lowered = f"{title}\n{body}".lower()
    if any(word in lowered for word in ["security", "vulnerability", "unauthorized", "injection", "xss", "csrf"]):
        return "security"
    if any(word in lowered for word in ["test", "coverage", "regression test", "unit test"]):
        return "test"
    if any(word in lowered for word in ["performance", "latency", "slow", "inefficient", "allocation"]):
        return "performance"
    if any(word in lowered for word in ["docs", "documentation", "comment", "readme"]):
        return "docs"
    if any(word in lowered for word in ["refactor", "maintainability", "readability", "cleanup", "style", "nit"]):
        return "maintainability"
    return "bug"


def derive_title(body: str, path: str, line: Optional[int]) -> str:
    line_text = first_meaningful_line(body)
    if line_text:
        return line_text
    if line is not None:
        return f"CodeRabbit issue in {path}:{line}"
    return f"CodeRabbit issue in {path}"


def derive_description(body: str, title: str) -> str:
    cleaned = body_without_prompt(body)
    paragraphs = normalize_paragraphs(cleaned)
    for paragraph in paragraphs:
        if paragraph == title:
            continue
        if len(paragraph) < 20:
            continue
        return paragraph
    if paragraphs:
        return paragraphs[0]
    return title


def derive_agent_prompt(body: str, title: str, description: str, path: str) -> str:
    extracted = extract_prompt_section(body)
    if extracted:
        return extracted
    return f"Address this unresolved CodeRabbit issue in {path}: {title}. {description}".strip()


def sanitize_issue_id(thread_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", thread_id).strip("_") or "thread"


def preferred_line(thread: Dict[str, Any]) -> Optional[int]:
    for key in ("line", "originalLine", "startLine", "originalStartLine"):
        value = thread.get(key)
        if isinstance(value, int) and value > 0:
            return value
    return None


def preferred_start_line(thread: Dict[str, Any]) -> Optional[int]:
    for key in ("startLine", "originalStartLine"):
        value = thread.get(key)
        if isinstance(value, int) and value > 0:
            return value
    return None


def preferred_end_line(thread: Dict[str, Any], start_line: Optional[int]) -> Optional[int]:
    line = thread.get("line")
    if isinstance(line, int) and line > 0:
        if start_line is None or line >= start_line:
            return line
    original_line = thread.get("originalLine")
    if isinstance(original_line, int) and original_line > 0:
        if start_line is None or original_line >= start_line:
            return original_line
    return start_line


def choose_primary_comment(thread: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    comments = (thread.get("comments") or {}).get("nodes") or []
    coderabbit_comments = [c for c in comments if is_coderabbit_author(((c.get("author") or {}).get("login")))]
    if not coderabbit_comments:
        return None
    return coderabbit_comments[-1]


def build_issue(thread: Dict[str, Any], index: int) -> Optional[Dict[str, Any]]:
    if thread.get("isResolved"):
        return None

    path = thread.get("path")
    if not isinstance(path, str) or not path.strip():
        return None

    comment = choose_primary_comment(thread)
    if comment is None:
        return None

    body = (comment.get("body") or "").strip()
    if not body:
        return None

    line = preferred_line(thread)
    start_line = preferred_start_line(thread)
    end_line = preferred_end_line(thread, start_line)

    title = derive_title(body, path, line)
    description = derive_description(body, title)
    agent_prompt = derive_agent_prompt(body, title, description, path)
    severity = detect_severity(body)
    issue_type = detect_issue_type(body, title)

    issue: Dict[str, Any] = {
        "id": f"cr_{index:03d}_{sanitize_issue_id(str(thread.get('id') or index))}",
        "threadId": str(thread.get("id") or f"thread-{index}"),
        "commentId": str(comment.get("id") or ""),
        "author": ((comment.get("author") or {}).get("login") or ""),
        "status": "open",
        "file": path,
        "severity": severity,
        "type": issue_type,
        "title": title,
        "description": description,
        "agentPrompt": agent_prompt,
        "rawBody": body,
    }

    if line is not None:
        issue["line"] = line
    if start_line is not None:
        issue["startLine"] = start_line
    if end_line is not None:
        issue["endLine"] = end_line

    if not issue["commentId"]:
        issue.pop("commentId")
    if not issue["author"]:
        issue.pop("author")

    return issue


def normalize_issues(threads: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    issues: List[Dict[str, Any]] = []
    for index, thread in enumerate(threads, start=1):
        issue = build_issue(thread, index)
        if issue is not None:
            issues.append(issue)
    issues.sort(key=lambda issue: (SEVERITY_ORDER.get(issue["severity"], 99), issue["file"], issue.get("line", 0), issue["id"]))
    return issues


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-path", required=True)
    parser.add_argument("--in-dir", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--max-cycles", required=False, type=int, default=3)
    parser.add_argument("--working-tree-must-be-clean", required=False, default="true")
    args = parser.parse_args()

    in_dir = Path(args.in_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    raw_path = in_dir / "raw" / "raw-review-threads.json"
    raw = load_json(raw_path)

    pull_request = raw.get("pullRequest") or {}
    repo_name = raw.get("repository") or git_output(args.repo_path, "remote", "get-url", "origin")
    repo_path = args.repo_path
    working_tree_must_be_clean = parse_bool(args.working_tree_must_be_clean)

    branch = pull_request.get("headRefName") or git_output(repo_path, "branch", "--show-current")
    head_sha = pull_request.get("headRefOid") or git_output(repo_path, "rev-parse", "HEAD")
    base_branch = pull_request.get("baseRefName") or None

    threads = raw.get("reviewThreads") or []
    issues = normalize_issues(threads)

    artifact = {
        "pr": {
            "number": int(pull_request.get("number") or 0),
            "title": pull_request.get("title") or f"PR #{args.max_cycles}",
            "branch": branch,
            "repository": repo_name,
            "url": pull_request.get("url"),
            "headSha": head_sha,
            "baseBranch": base_branch,
        },
        "constraints": {
            "maxCycles": args.max_cycles,
            "allowCommit": False,
            "allowPush": False,
            "allowPrComment": False,
            "allowThreadResolution": False,
            "allowScopeExpansion": False,
        },
        "context": {
            "repoPath": repo_path,
            "expectedRepository": repo_name,
            "expectedBranch": branch,
            "expectedHeadSha": head_sha,
            "workingTreeMustBeClean": working_tree_must_be_clean,
        },
        "issues": issues,
        "metadata": {
            "artifactVersion": "1",
            "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "source": "github-review-thread-normalizer",
        },
    }

    artifact["pr"] = {k: v for k, v in artifact["pr"].items() if v is not None}

    summary = {
        "status": "ok",
        "repository": repo_name,
        "prNumber": artifact["pr"]["number"],
        "totalThreads": len(threads),
        "actionableIssues": len(issues),
        "unresolvedThreads": sum(1 for thread in threads if not thread.get("isResolved")),
        "coderabbitUnresolvedThreads": sum(
            1
            for thread in threads
            if not thread.get("isResolved") and choose_primary_comment(thread) is not None and isinstance(thread.get("path"), str) and bool(thread.get("path"))
        ),
        "artifactPath": str(out_dir / "actionable-issues.json"),
    }

    (out_dir / "actionable-issues.json").write_text(
        json.dumps(artifact, indent=2) + "\n",
        encoding="utf-8",
    )
    (out_dir / "normalization-summary.json").write_text(
        json.dumps(summary, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"Normalized {len(issues)} actionable CodeRabbit issues into {out_dir / 'actionable-issues.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
