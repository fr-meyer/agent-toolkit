#!/usr/bin/env python3
import argparse
import html
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

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

HEADER_PATTERN = re.compile(r"(?m)^\s*_([^_]+?)_\s*\|\s*_([^_]+?)_\s*$")
DETAILS_SECTION_PATTERN = re.compile(
    r"(?is)<details>\s*<summary>\s*(?P<label>.*?)\s*</summary>(?P<body>.*?)</details>"
)
PROMPT_SECTION_PATTERNS = [
    re.compile(
        r"(?ims)^#{1,6}\s*prompt\s+for\s+ai\s+agents\s*$\n(?P<body>.*?)(?=^#{1,6}\s+\S|\Z)"
    ),
    re.compile(
        r"(?ims)^\*\*prompt\s+for\s+ai\s+agents\*\*: ?\s*$\n(?P<body>.*?)(?=^\*\*|^#{1,6}\s+\S|\Z)"
    ),
    re.compile(
        r"(?ims)^prompt\s+for\s+ai\s+agents\s*: ?\s*$\n(?P<body>.*)$"
    ),
]

HEADING_PREFIX = re.compile(r"^#{1,6}\s+")
LINK_SPAN = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
INLINE_CODE = re.compile(r"`([^`]+)`")
BOLD_OR_ITALIC_SPAN = re.compile(r"(\*\*|__|\*|_)([^*_]+?)\1")
HTML_BREAKS = re.compile(r"(?i)<br\s*/?>")
HTML_TAGS = re.compile(r"(?is)</?(?:p|div|li|ul|ol|blockquote|details|summary|strong|em|code|pre|span|h[1-6])\b[^>]*>")
ANY_HTML_TAG = re.compile(r"(?is)<[^>]+>")
LEADING_LIST_MARKER = re.compile(r"^(?:[-*+]|\d+[.)])\s+")
WHITESPACE = re.compile(r"[ \t]+")
BLANK_LINES = re.compile(r"\n{3,}")
NON_ALNUM = re.compile(r"[^a-z0-9]+")

IGNORED_LABELS = {
    "prompt for ai agents",
    "summary",
    "why this matters",
    "suggestion",
}


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


def normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def is_coderabbit_author(login: Optional[str]) -> bool:
    if not login:
        return False
    lowered = login.strip().lower()
    return any(lowered.startswith(prefix) for prefix in CODERABBIT_PREFIXES)


def clean_inline_text(text: str) -> str:
    return WHITESPACE.sub(" ", clean_multiline_text(text).replace("\n", " ")).strip()


def clean_multiline_text(text: str) -> str:
    text = normalize_newlines(html.unescape(text))
    text = HTML_BREAKS.sub("\n", text)
    text = HTML_TAGS.sub("\n", text)
    text = LINK_SPAN.sub(r"\1", text)
    text = INLINE_CODE.sub(r"\1", text)
    text = BOLD_OR_ITALIC_SPAN.sub(r"\2", text)
    text = ANY_HTML_TAG.sub("", text)

    lines: List[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            lines.append("")
            continue

        if HEADING_PREFIX.match(line):
            line = HEADING_PREFIX.sub("", line).strip()

        line = LEADING_LIST_MARKER.sub("", line)
        line = line.lstrip("> ").strip()
        line = WHITESPACE.sub(" ", line).strip()
        lines.append(line)

    cleaned = "\n".join(lines).strip()
    cleaned = BLANK_LINES.sub("\n\n", cleaned)
    return cleaned.strip()


def split_paragraphs(text: str) -> List[str]:
    cleaned = clean_multiline_text(text)
    if not cleaned:
        return []
    return [paragraph.strip() for paragraph in re.split(r"\n\s*\n", cleaned) if paragraph.strip()]


def normalize_repository_name(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        return cleaned

    for pattern in (
        re.compile(r"^(?:https://|http://)?github\.com/(?P<repo>[^/]+/[^/.]+?)(?:\.git)?/?$", re.IGNORECASE),
        re.compile(r"^git@github\.com:(?P<repo>[^/]+/[^/.]+?)(?:\.git)?$", re.IGNORECASE),
        re.compile(r"^ssh://git@github\.com/(?P<repo>[^/]+/[^/.]+?)(?:\.git)?/?$", re.IGNORECASE),
    ):
        match = pattern.match(cleaned)
        if match:
            return match.group("repo")

    return cleaned.rstrip("/")


def normalize_label(value: str) -> str:
    lowered = clean_inline_text(value).lower()
    return NON_ALNUM.sub(" ", lowered).strip()


def parse_header(body: str) -> Tuple[Optional[str], Optional[str]]:
    match = HEADER_PATTERN.search(normalize_newlines(body))
    if not match:
        return None, None
    return clean_inline_text(match.group(1)), clean_inline_text(match.group(2))


def remove_header(body: str) -> str:
    return HEADER_PATTERN.sub("", normalize_newlines(body), count=1).strip()


def is_prompt_label(label: str) -> bool:
    return "prompt for ai agents" in normalize_label(label)


def extract_prompt_section(body: str) -> Optional[str]:
    normalized = normalize_newlines(body)

    for match in DETAILS_SECTION_PATTERN.finditer(normalized):
        label = match.group("label") or ""
        if not is_prompt_label(label):
            continue
        prompt = clean_multiline_text(match.group("body") or "")
        if prompt:
            return prompt

    for pattern in PROMPT_SECTION_PATTERNS:
        match = pattern.search(normalized)
        if not match:
            continue
        prompt = clean_multiline_text(match.group("body") or "")
        if prompt:
            return prompt

    return None


def remove_prompt_sections(body: str) -> str:
    text = normalize_newlines(body)

    def strip_details(match: re.Match[str]) -> str:
        label = match.group("label") or ""
        return "" if is_prompt_label(label) else match.group(0)

    text = DETAILS_SECTION_PATTERN.sub(strip_details, text)
    for pattern in PROMPT_SECTION_PATTERNS:
        text = pattern.sub("", text)
    return text.strip()


def first_meaningful_line(body: str) -> Optional[str]:
    for raw_line in clean_multiline_text(body).splitlines():
        line = raw_line.strip()
        if not line:
            continue
        lowered = normalize_label(line)
        if lowered in IGNORED_LABELS:
            continue
        if len(line) > 220:
            continue
        return line.rstrip(":")
    return None


def detect_severity(severity_label: Optional[str], body: str) -> str:
    label = normalize_label(severity_label or "")
    combined = f"{label} {normalize_label(body)}".strip()

    if any(keyword in combined for keyword in ("critical", "blocker", "urgent")):
        return "critical"
    if any(keyword in combined for keyword in ("high", "major", "severe")):
        return "high"
    if any(keyword in combined for keyword in ("medium", "moderate")):
        return "medium"
    if any(keyword in combined for keyword in ("low", "minor", "info", "informational", "suggestion", "nitpick", "style")):
        return "low"

    labeled = re.search(r"severity\s*[:\-]\s*(critical|high|medium|low)", combined)
    if labeled:
        return labeled.group(1)

    return "unknown"


def detect_issue_type(issue_label: Optional[str], body: str, title: str) -> str:
    combined = " ".join(
        normalize_label(part)
        for part in (issue_label or "", title, body)
        if part
    )

    if any(word in combined for word in ["security", "vulnerability", "unauthorized", "injection", "xss", "csrf"]):
        return "security"
    if any(word in combined for word in ["test", "coverage", "regression test", "unit test"]):
        return "test"
    if any(word in combined for word in ["performance", "latency", "slow", "inefficient", "allocation"]):
        return "performance"
    if any(word in combined for word in ["docs", "documentation", "comment", "readme"]):
        return "docs"
    if any(word in combined for word in ["nitpick", "refactor", "maintainability", "readability", "cleanup", "style"]):
        return "maintainability"
    return "bug"


def derive_title_and_description(body: str, path: str, line: Optional[int]) -> Tuple[str, str]:
    stripped = remove_prompt_sections(remove_header(body))
    paragraphs = split_paragraphs(stripped)

    fallback_title = f"CodeRabbit issue in {path}:{line}" if line is not None else f"CodeRabbit issue in {path}"

    if not paragraphs:
        return fallback_title, fallback_title

    title = paragraphs[0].rstrip(":")
    if len(title) > 160 and ". " in title:
        title = title.split(". ", 1)[0].rstrip(":")

    if len(paragraphs) > 1:
        description = paragraphs[1]
    else:
        description = paragraphs[0]

    if description == title and len(paragraphs) > 2:
        description = paragraphs[2]

    if len(description) < 20 and len(paragraphs) > 1:
        description = " ".join(paragraphs[1:]).strip()

    if not title:
        title = first_meaningful_line(stripped) or fallback_title
    if not description:
        description = title

    return title, description


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
    for key in ("startLine", "originalStartLine", "line", "originalLine"):
        value = thread.get(key)
        if isinstance(value, int) and value > 0:
            return value
    return None


def preferred_end_line(thread: Dict[str, Any], start_line: Optional[int]) -> Optional[int]:
    for key in ("line", "originalLine", "startLine", "originalStartLine"):
        value = thread.get(key)
        if isinstance(value, int) and value > 0 and (start_line is None or value >= start_line):
            return value
    return start_line


def comments_for_thread(thread: Dict[str, Any]) -> List[Dict[str, Any]]:
    comments = (thread.get("comments") or {}).get("nodes") or []
    return [comment for comment in comments if isinstance(comment, dict)]


def has_coderabbit_root_comment(thread: Dict[str, Any]) -> bool:
    comments = comments_for_thread(thread)
    if not comments:
        return False
    root_login = ((comments[0].get("author") or {}).get("login"))
    return is_coderabbit_author(root_login)


def choose_primary_comment(thread: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    comments = comments_for_thread(thread)
    if not comments:
        return None
    if has_coderabbit_root_comment(thread):
        return comments[0]
    return None


def is_actionable_thread(thread: Dict[str, Any]) -> bool:
    if thread.get("isResolved"):
        return False
    if thread.get("isOutdated"):
        return False
    path = thread.get("path")
    if not isinstance(path, str) or not path.strip():
        return False
    return choose_primary_comment(thread) is not None


def build_issue(thread: Dict[str, Any], index: int) -> Optional[Dict[str, Any]]:
    if not is_actionable_thread(thread):
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

    issue_label, severity_label = parse_header(body)
    line = preferred_line(thread)
    start_line = preferred_start_line(thread)
    end_line = preferred_end_line(thread, start_line)

    title, description = derive_title_and_description(body, path, line)
    agent_prompt = derive_agent_prompt(body, title, description, path)
    severity = detect_severity(severity_label, body)
    issue_type = detect_issue_type(issue_label, body, title)

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
    issues.sort(
        key=lambda issue: (
            SEVERITY_ORDER.get(issue["severity"], 99),
            issue["file"],
            issue.get("line", 0),
            issue["id"],
        )
    )
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
    raw_repo_name = str(raw.get("repository") or "").strip()
    if raw_repo_name:
        repo_name = normalize_repository_name(raw_repo_name)
    else:
        repo_name = normalize_repository_name(git_output(args.repo_path, "remote", "get-url", "origin"))

    repo_path = args.repo_path
    working_tree_must_be_clean = parse_bool(args.working_tree_must_be_clean)

    pr_number = int(pull_request.get("number") or ((raw.get("metadata") or {}).get("requestedPrNumber") or 0))
    if pr_number < 1:
        raise SystemExit("Raw review-thread payload did not include a valid pull request number.")

    branch = pull_request.get("headRefName") or git_output(repo_path, "branch", "--show-current")
    head_sha = pull_request.get("headRefOid") or git_output(repo_path, "rev-parse", "HEAD")
    base_branch = pull_request.get("baseRefName") or None
    pr_title = clean_inline_text(str(pull_request.get("title") or "")) or f"PR #{pr_number}"
    pr_url = pull_request.get("url") or None

    threads = raw.get("reviewThreads") or []
    issues = normalize_issues(threads)

    artifact = {
        "pr": {
            "number": pr_number,
            "title": pr_title,
            "branch": branch,
            "repository": repo_name,
            "url": pr_url,
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

    unresolved_threads = [thread for thread in threads if not thread.get("isResolved")]
    outdated_unresolved_threads = [thread for thread in unresolved_threads if thread.get("isOutdated")]
    coderabbit_root_unresolved_threads = [thread for thread in unresolved_threads if has_coderabbit_root_comment(thread)]
    actionable_threads = [thread for thread in threads if is_actionable_thread(thread)]

    summary = {
        "status": "ok",
        "repository": repo_name,
        "prNumber": pr_number,
        "totalThreads": len(threads),
        "unresolvedThreads": len(unresolved_threads),
        "outdatedUnresolvedThreads": len(outdated_unresolved_threads),
        "coderabbitRootUnresolvedThreads": len(coderabbit_root_unresolved_threads),
        "actionableIssues": len(issues),
        "actionableThreads": len(actionable_threads),
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
