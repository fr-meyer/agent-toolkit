#!/usr/bin/env python3
import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Preflight execution-target checks for CodeRabbit PR automation.'
    )
    parser.add_argument('--repo-path', required=True)
    parser.add_argument('--artifact-path', required=True)
    parser.add_argument('--expected-repository', required=True)
    parser.add_argument('--working-tree-must-be-clean', default='true')
    parser.add_argument('--out-dir', required=True)
    return parser.parse_args()


def parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {'1', 'true', 'yes', 'on'}:
        return True
    if normalized in {'0', 'false', 'no', 'off'}:
        return False
    raise ValueError(f'Unsupported boolean value: {value}')


def normalize_repository_name(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    cleaned = str(value).strip()
    if not cleaned:
        return None

    patterns = [
        re.compile(r'^(?:https://|http://)?github\.com/(?P<repo>[^/]+/[^/.]+?)(?:\.git)?/?$', re.IGNORECASE),
        re.compile(r'^git@github\.com:(?P<repo>[^/]+/[^/.]+?)(?:\.git)?$', re.IGNORECASE),
        re.compile(r'^ssh://git@github\.com/(?P<repo>[^/]+/[^/.]+?)(?:\.git)?/?$', re.IGNORECASE),
    ]
    for pattern in patterns:
        match = pattern.match(cleaned)
        if match:
            return match.group('repo')
    return cleaned.rstrip('/')


class GitRepo:
    def __init__(self, repo_path: Path):
        self.repo_path = repo_path

    def output(self, *args: str, check: bool = True) -> str:
        completed = subprocess.run(
            ['git', '-C', str(self.repo_path), *args],
            text=True,
            capture_output=True,
            check=False,
        )
        if check and completed.returncode != 0:
            stderr = (completed.stderr or completed.stdout).strip()
            raise RuntimeError(stderr or f"git {' '.join(args)} failed with code {completed.returncode}")
        return (completed.stdout or '').rstrip('\r\n')

    def try_output(self, *args: str) -> Optional[str]:
        completed = subprocess.run(
            ['git', '-C', str(self.repo_path), *args],
            text=True,
            capture_output=True,
            check=False,
        )
        if completed.returncode != 0:
            return None
        return (completed.stdout or '').rstrip('\r\n')


def coalesce_consistent(label: str, values: List[Optional[str]], errors: List[str]) -> Optional[str]:
    present = [value for value in values if value not in (None, '')]
    if not present:
        return None
    first = present[0]
    for value in present[1:]:
        if value != first:
            errors.append(f'Conflicting expected {label} values: {present}')
            return first
    return first


def parse_status_entry(line: str) -> Dict[str, Any]:
    status = line[:2]
    payload = line[3:] if len(line) > 3 else ''
    paths = [part.strip() for part in payload.split(' -> ')] if ' -> ' in payload else [payload.strip()]
    return {
        'raw': line,
        'status': status,
        'paths': [path for path in paths if path],
    }


def is_ignored_status_entry(entry: Dict[str, Any], ignored_prefixes: List[str]) -> bool:
    if not ignored_prefixes or not entry['paths']:
        return False

    for path in entry['paths']:
        normalized_path = path.replace('\\', '/')
        matches = False
        for prefix in ignored_prefixes:
            normalized_prefix = prefix.replace('\\', '/').rstrip('/')
            if normalized_path == normalized_prefix or normalized_path.startswith(normalized_prefix + '/'):
                matches = True
                break
        if not matches:
            return False
    return True


def main() -> int:
    args = parse_args()

    repo_path = Path(args.repo_path).resolve()
    artifact_path = Path(args.artifact_path).resolve()
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    summary_path = out_dir / 'preflight-summary.json'

    errors: List[str] = []

    if not repo_path.exists():
        raise SystemExit(f'Repo path does not exist: {repo_path}')
    if not artifact_path.exists():
        raise SystemExit(f'Artifact path does not exist: {artifact_path}')

    repo = GitRepo(repo_path)
    if repo.try_output('rev-parse', '--is-inside-work-tree') != 'true':
        raise SystemExit(f'{repo_path} is not a git working tree')

    artifact = json.loads(artifact_path.read_text(encoding='utf-8'))
    pr = artifact.get('pr') or {}
    context = artifact.get('context') or {}

    expected_repository = coalesce_consistent(
        'repository',
        [
            normalize_repository_name(args.expected_repository),
            normalize_repository_name(pr.get('repository')),
            normalize_repository_name(context.get('expectedRepository')),
        ],
        errors,
    )
    expected_branch = coalesce_consistent(
        'branch',
        [
            (pr.get('branch') or '').strip() or None,
            (context.get('expectedBranch') or '').strip() or None,
        ],
        errors,
    )
    expected_head_sha = coalesce_consistent(
        'head SHA',
        [
            (pr.get('headSha') or '').strip() or None,
            (context.get('expectedHeadSha') or '').strip() or None,
        ],
        errors,
    )

    working_tree_must_be_clean_cli = parse_bool(args.working_tree_must_be_clean)
    context_clean_policy = context.get('workingTreeMustBeClean')
    if context_clean_policy is not None and context_clean_policy != working_tree_must_be_clean_cli:
        errors.append(
            'Conflicting working-tree cleanliness policy between CLI and artifact context: '
            f'{working_tree_must_be_clean_cli} vs {context_clean_policy}'
        )
    working_tree_must_be_clean = working_tree_must_be_clean_cli

    current_sha = repo.output('rev-parse', 'HEAD')
    current_branch = repo.try_output('branch', '--show-current') or ''
    origin_url = repo.try_output('remote', 'get-url', 'origin')
    actual_repository = normalize_repository_name(origin_url)

    detached_head = current_branch == ''
    branch_resolution = 'direct'
    branch_checked_value = current_branch or None
    branch_matched = expected_branch is None

    if expected_branch is not None:
        if current_branch == expected_branch:
            branch_matched = True
            branch_resolution = 'direct'
            branch_checked_value = current_branch
        else:
            local_ref_sha = repo.try_output('rev-parse', '--verify', f'refs/heads/{expected_branch}')
            remote_ref_sha = repo.try_output('rev-parse', '--verify', f'refs/remotes/origin/{expected_branch}')
            if local_ref_sha == current_sha:
                branch_matched = True
                branch_resolution = 'local-ref-at-head'
                branch_checked_value = expected_branch
            elif remote_ref_sha == current_sha:
                branch_matched = True
                branch_resolution = 'remote-ref-at-head'
                branch_checked_value = f'origin/{expected_branch}'
            elif detached_head and expected_head_sha and current_sha == expected_head_sha:
                branch_matched = True
                branch_resolution = 'detached-head-matched-by-sha'
                branch_checked_value = None
            else:
                branch_matched = False

    repository_matched = expected_repository is None or actual_repository == expected_repository
    head_sha_matched = expected_head_sha is None or current_sha == expected_head_sha

    status_lines = repo.output('status', '--porcelain=v1', '--untracked-files=all').splitlines()
    ignored_prefixes: List[str] = []
    try:
        relative_out_dir = os.path.relpath(out_dir, repo_path).replace('\\', '/')
        if relative_out_dir != '..' and not relative_out_dir.startswith('../'):
            ignored_prefixes.append(relative_out_dir)
    except ValueError:
        pass

    status_entries = [parse_status_entry(line) for line in status_lines if line.strip()]
    ignored_entries = [entry for entry in status_entries if is_ignored_status_entry(entry, ignored_prefixes)]
    blocking_entries = [entry for entry in status_entries if not is_ignored_status_entry(entry, ignored_prefixes)]
    working_tree_clean = len(blocking_entries) == 0
    cleanliness_ok = (not working_tree_must_be_clean) or working_tree_clean

    checks: Dict[str, Dict[str, Any]] = {
        'repository': {
            'ok': repository_matched,
            'expected': expected_repository,
            'actual': actual_repository,
            'originUrl': origin_url,
        },
        'branch': {
            'ok': branch_matched,
            'expected': expected_branch,
            'actual': current_branch or None,
            'resolution': branch_resolution,
            'matchedRef': branch_checked_value,
            'detachedHead': detached_head,
        },
        'headSha': {
            'ok': head_sha_matched,
            'expected': expected_head_sha,
            'actual': current_sha,
        },
        'workingTree': {
            'ok': cleanliness_ok,
            'mustBeClean': working_tree_must_be_clean,
            'isClean': working_tree_clean,
            'ignoredPrefixes': ignored_prefixes,
            'ignoredEntryCount': len(ignored_entries),
            'blockingEntries': blocking_entries,
        },
    }

    if not repository_matched:
        errors.append(f'Repository mismatch: expected {expected_repository}, got {actual_repository}')
    if not branch_matched:
        errors.append(f"Branch mismatch: expected {expected_branch}, got {current_branch or '<detached HEAD>'}")
    if not head_sha_matched:
        errors.append(f'HEAD SHA mismatch: expected {expected_head_sha}, got {current_sha}')
    if not cleanliness_ok:
        errors.append('Working tree is not clean under the current policy.')

    summary = {
        'status': 'ok' if not errors else 'failed',
        'repoPath': str(repo_path),
        'artifactPath': str(artifact_path),
        'expectedRepository': expected_repository,
        'expectedBranch': expected_branch,
        'expectedHeadSha': expected_head_sha,
        'workingTreeMustBeClean': working_tree_must_be_clean,
        'checks': checks,
        'errors': errors,
        'metadata': {
            'createdAt': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            'source': 'coderabbit-preflight',
        },
    }
    summary_path.write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')

    if errors:
        print(f'Preflight failed: wrote {summary_path}', file=sys.stderr)
        for error in errors:
            print(f'- {error}', file=sys.stderr)
        return 1

    print(f'Preflight passed: wrote {summary_path}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
