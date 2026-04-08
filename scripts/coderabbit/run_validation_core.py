#!/usr/bin/env python3
import argparse
import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

SEVERITIES = ('critical', 'high', 'medium', 'low', 'unknown')
AUTH_REQUIRED_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r'not logged in',
        r'not authenticated',
        r'authentication required',
        r'please log in',
        r'run\s+(?:cr|coderabbit)\s+auth\s+login',
        r'auth(?:orization)?\s+required',
        r'invalid token',
        r'authorization failed',
        r'failed to authenticate',
    ]
]
RATE_LIMIT_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r'rate limit',
        r'quota',
        r'reviews? per hour',
        r'too many requests',
        r'retry after',
        r'limit exceeded',
    ]
]
RETRY_AFTER_PATTERN = re.compile(r'retry\s+after\s+(\d+)\s*(seconds?|secs?|s)\b', re.IGNORECASE)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='CodeRabbit validation wrapper with normalized output.'
    )
    parser.add_argument('--repo-path', required=True)
    parser.add_argument('--pr-number', required=True, type=int)
    parser.add_argument('--out-dir', required=True)
    return parser.parse_args()


def read_json_if_exists(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding='utf-8'))


def parse_json_payload(text: str) -> Optional[Any]:
    stripped = text.strip()
    if not stripped:
        return None

    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass

    parsed_lines: List[Any] = []
    for line in stripped.splitlines():
        candidate = line.strip()
        if not candidate:
            continue
        try:
            parsed_lines.append(json.loads(candidate))
        except json.JSONDecodeError:
            continue
    if parsed_lines:
        if len(parsed_lines) == 1:
            return parsed_lines[0]
        return {'events': parsed_lines}

    start_positions = [index for index, char in enumerate(stripped) if char in '{[']
    for start in start_positions:
        for end in range(len(stripped), start, -1):
            candidate = stripped[start:end].strip()
            if not candidate:
                continue
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue
    return None


def detect_cli_binary() -> Optional[str]:
    for env_var in ('CODERABBIT_CLI', 'CR_BINARY'):
        candidate = os.environ.get(env_var)
        if candidate:
            return candidate
    for candidate in ('cr', 'coderabbit'):
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    return None


def run_command(command: List[str], cwd: Optional[Path] = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=str(cwd) if cwd is not None else None,
        text=True,
        capture_output=True,
        check=False,
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')


def normalize_severity(value: Any) -> str:
    text = str(value or '').strip().lower()
    if text in SEVERITIES:
        return text
    if any(token in text for token in ('critical', 'blocker', 'urgent')):
        return 'critical'
    if any(token in text for token in ('high', 'major', 'severe')):
        return 'high'
    if any(token in text for token in ('medium', 'moderate')):
        return 'medium'
    if any(token in text for token in ('low', 'minor', 'suggestion', 'info', 'informational', 'nit')):
        return 'low'
    return 'unknown'


def coerce_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    if isinstance(value, (int, float, bool)):
        return str(value)
    return None


def first_present(mapping: Dict[str, Any], keys: Iterable[str]) -> Any:
    for key in keys:
        if key in mapping and mapping[key] not in (None, ''):
            return mapping[key]
    return None


def maybe_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    text = str(value).strip()
    if text.isdigit():
        return int(text)
    return None


def maybe_path(value: Any) -> Optional[str]:
    text = coerce_text(value)
    if not text:
        return None
    return text.replace('\\', '/')


def extract_candidate_finding_objects(payload: Any) -> List[Dict[str, Any]]:
    found: List[Dict[str, Any]] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            keys = set(node.keys())
            if (
                keys.intersection({'severity', 'priority', 'level'})
                and keys.intersection({'title', 'message', 'summary', 'description', 'body'})
            ):
                found.append(node)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(payload)
    return found


def normalize_finding(raw: Dict[str, Any], index: int) -> Dict[str, Any]:
    title = coerce_text(first_present(raw, ('title', 'message', 'summary'))) or f'Finding {index}'
    description = coerce_text(first_present(raw, ('description', 'body', 'details', 'reason'))) or title
    file_value = first_present(raw, ('file', 'path', 'filename'))
    if file_value is None:
        location = raw.get('location')
        if isinstance(location, dict):
            file_value = first_present(location, ('file', 'path', 'filename'))
    line_value = first_present(raw, ('line', 'lineNumber', 'startLine'))
    if line_value is None:
        location = raw.get('location')
        if isinstance(location, dict):
            line_value = first_present(location, ('line', 'lineNumber', 'startLine'))

    finding: Dict[str, Any] = {
        'id': coerce_text(first_present(raw, ('id', 'findingId', 'commentId'))) or f'vr_{index:03d}',
        'severity': normalize_severity(first_present(raw, ('severity', 'priority', 'level'))),
        'kind': coerce_text(first_present(raw, ('kind', 'type', 'category'))) or 'unknown',
        'status': coerce_text(first_present(raw, ('status',))) or 'open',
        'title': title,
        'description': description,
        'file': maybe_path(file_value),
        'line': maybe_int(line_value),
        'sourceIssueId': coerce_text(first_present(raw, ('sourceIssueId', 'source_issue_id', 'issueId', 'issue_id'))),
    }
    return {key: value for key, value in finding.items() if value is not None}


def summarize_findings(findings: List[Dict[str, Any]]) -> Dict[str, int]:
    counts = {severity: 0 for severity in SEVERITIES}
    blocking_count = 0
    for finding in findings:
        severity = normalize_severity(finding.get('severity'))
        counts[severity] += 1
        status = str(finding.get('status') or 'open').lower()
        if status == 'open' and severity in {'critical', 'high', 'medium'}:
            blocking_count += 1
    counts['totalFindings'] = len(findings)
    counts['blockingCount'] = blocking_count
    return counts


def detect_rate_limit(texts: Iterable[str]) -> Dict[str, Any]:
    combined = '\n'.join(text for text in texts if text).strip()
    if not combined:
        return {'hit': False, 'scope': None, 'retryAfterSeconds': None}

    hit = any(pattern.search(combined) for pattern in RATE_LIMIT_PATTERNS)
    retry_after = None
    match = RETRY_AFTER_PATTERN.search(combined)
    if match:
        retry_after = int(match.group(1))
    scope = 'reviewsPerHour' if re.search(r'reviews? per hour|quota', combined, re.IGNORECASE) else None
    return {
        'hit': hit,
        'scope': scope,
        'retryAfterSeconds': retry_after,
    }


def detect_auth_required(texts: Iterable[str]) -> bool:
    combined = '\n'.join(text for text in texts if text).strip()
    if not combined:
        return False
    return any(pattern.search(combined) for pattern in AUTH_REQUIRED_PATTERNS)


def extract_tool_version(binary: str) -> Optional[str]:
    completed = run_command([binary, '--version'])
    text = (completed.stdout or completed.stderr or '').strip()
    return text or None


def derive_cycle(out_dir: Path) -> Optional[int]:
    match = re.search(r'cycle-(\d+)$', out_dir.name)
    if match:
        return int(match.group(1))
    return None


def main() -> int:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    repo_path = Path(args.repo_path).resolve()

    artifact_path = out_dir / 'actionable-issues.json'
    artifact = read_json_if_exists(artifact_path) or {}
    pr = dict((artifact.get('pr') or {}))
    if 'number' not in pr:
        pr['number'] = args.pr_number

    binary = detect_cli_binary()
    tool_version = extract_tool_version(binary) if binary else None
    cycle = derive_cycle(out_dir)

    raw_stdout_path = out_dir / 'validation-raw.stdout.txt'
    raw_stderr_path = out_dir / 'validation-raw.stderr.txt'
    raw_auth_path = out_dir / 'validation-auth.json'

    if not binary:
        result = {
            'status': 'not_available',
            'validationVersion': '1',
            'tool': {
                'name': 'coderabbit-cli',
                'binary': None,
                'mode': 'review',
                'version': None,
            },
            'repoPath': str(repo_path),
            'pr': pr,
            'cycle': cycle,
            'rateLimit': {
                'hit': False,
                'scope': None,
                'retryAfterSeconds': None,
            },
            'summary': None,
            'findings': [],
            'note': 'CodeRabbit CLI was not found in PATH. Install `cr`/`coderabbit` to enable validation.',
            'metadata': {
                'createdAt': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                'source': 'coderabbit-validation-wrapper',
            },
        }
        (out_dir / 'validation-result.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
        print(f'Validation unavailable: wrote {out_dir / "validation-result.json"}')
        return 0

    auth_command = [binary, 'auth', 'status', '--agent']
    auth_result = run_command(auth_command, cwd=repo_path)
    auth_stdout = auth_result.stdout or ''
    auth_stderr = auth_result.stderr or ''
    auth_payload = parse_json_payload(auth_stdout)
    raw_auth = {
        'command': auth_command,
        'exitCode': auth_result.returncode,
        'stdout': auth_stdout,
        'stderr': auth_stderr,
        'parsed': auth_payload,
    }
    raw_auth_path.write_text(json.dumps(raw_auth, indent=2) + '\n', encoding='utf-8')

    if auth_result.returncode != 0 or detect_auth_required([auth_stdout, auth_stderr]):
        result = {
            'status': 'auth_required',
            'validationVersion': '1',
            'tool': {
                'name': 'coderabbit-cli',
                'binary': binary,
                'mode': 'review',
                'version': tool_version,
            },
            'repoPath': str(repo_path),
            'pr': pr,
            'cycle': cycle,
            'rateLimit': {
                'hit': False,
                'scope': None,
                'retryAfterSeconds': None,
            },
            'summary': None,
            'findings': [],
            'note': 'CodeRabbit CLI is present but authentication is required.',
            'metadata': {
                'createdAt': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                'source': 'coderabbit-validation-wrapper',
            },
        }
        (out_dir / 'validation-result.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
        print(f'Validation auth required: wrote {out_dir / "validation-result.json"}')
        return 0

    review_command = [binary, 'review', '--agent', '--cwd', str(repo_path)]
    base_branch = coerce_text(pr.get('baseBranch'))
    if base_branch:
        review_command.extend(['--base', base_branch])

    review_result = run_command(review_command, cwd=repo_path)
    stdout = review_result.stdout or ''
    stderr = review_result.stderr or ''
    write_text(raw_stdout_path, stdout)
    write_text(raw_stderr_path, stderr)

    payload = parse_json_payload(stdout)
    findings: List[Dict[str, Any]] = []
    if payload is not None:
        findings = [normalize_finding(candidate, index + 1) for index, candidate in enumerate(extract_candidate_finding_objects(payload))]

    summary = summarize_findings(findings) if findings else None
    rate_limit = detect_rate_limit([stdout, stderr, json.dumps(payload) if payload is not None else ''])
    auth_required = detect_auth_required([stdout, stderr])

    if rate_limit['hit']:
        status = 'rate_limited'
    elif auth_required:
        status = 'auth_required'
    elif review_result.returncode == 0:
        status = 'ok'
    else:
        status = 'error'

    note: Optional[str] = None
    if status == 'rate_limited':
        note = 'Validation hit a CodeRabbit review quota or rate limit.'
    elif status == 'auth_required':
        note = 'Validation failed because CodeRabbit CLI authentication is required.'
    elif status == 'error':
        note = 'Validation command failed. Inspect raw stdout/stderr artifacts for details.'

    result = {
        'status': status,
        'validationVersion': '1',
        'tool': {
            'name': 'coderabbit-cli',
            'binary': binary,
            'mode': 'review',
            'version': tool_version,
        },
        'command': review_command,
        'repoPath': str(repo_path),
        'pr': pr,
        'cycle': cycle,
        'rateLimit': rate_limit,
        'summary': summary,
        'findings': findings,
        'raw': {
            'stdoutPath': str(raw_stdout_path),
            'stderrPath': str(raw_stderr_path),
            'authPath': str(raw_auth_path),
            'exitCode': review_result.returncode,
            'parsedAgentOutput': payload is not None,
        },
        'note': note,
        'metadata': {
            'createdAt': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            'source': 'coderabbit-validation-wrapper',
        },
    }

    (out_dir / 'validation-result.json').write_text(
        json.dumps(result, indent=2) + '\n',
        encoding='utf-8',
    )

    print(f'Validation complete: wrote {out_dir / "validation-result.json"}')
    return 0 if status in {'ok', 'rate_limited', 'auth_required'} else 1


if __name__ == '__main__':
    raise SystemExit(main())
