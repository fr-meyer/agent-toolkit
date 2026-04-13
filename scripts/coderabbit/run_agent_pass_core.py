#!/usr/bin/env python3
import argparse
import json
import os
import shlex
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Configurable bounded CodeRabbit remediation agent pass runner.'
    )
    parser.add_argument('--repo-path', required=True)
    parser.add_argument('--shared-root', required=True)
    parser.add_argument('--pr-number', required=True, type=int)
    parser.add_argument('--out-dir', required=True)
    return parser.parse_args()


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))


def parse_command_spec() -> Dict[str, Any]:
    raw_json = os.environ.get('CODERABBIT_AGENT_COMMAND_JSON')
    if raw_json:
        parsed = json.loads(raw_json)
        if not isinstance(parsed, list) or not parsed or not all(isinstance(item, str) and item for item in parsed):
            raise ValueError('CODERABBIT_AGENT_COMMAND_JSON must be a non-empty JSON array of strings.')
        return {
            'source': 'CODERABBIT_AGENT_COMMAND_JSON',
            'command': parsed,
        }

    raw_command = os.environ.get('CODERABBIT_AGENT_COMMAND')
    if raw_command:
        return {
            'source': 'CODERABBIT_AGENT_COMMAND',
            'command': shlex.split(raw_command, posix=os.name != 'nt'),
        }

    return {
        'source': None,
        'command': None,
    }


def substitute_tokens(parts: List[str], mapping: Dict[str, str]) -> List[str]:
    rendered: List[str] = []
    for part in parts:
        rendered_part = part
        for key, value in mapping.items():
            rendered_part = rendered_part.replace('{' + key + '}', value)
        rendered.append(rendered_part)
    return rendered


def git_output(repo_path: Path, *args: str) -> str:
    completed = subprocess.run(
        ['git', '-C', str(repo_path), *args],
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        stderr = (completed.stderr or completed.stdout).strip()
        raise RuntimeError(stderr or f"git {' '.join(args)} failed with code {completed.returncode}")
    return (completed.stdout or '').rstrip('\r\n')


def git_try(repo_path: Path, *args: str) -> Optional[str]:
    completed = subprocess.run(
        ['git', '-C', str(repo_path), *args],
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        return None
    return (completed.stdout or '').rstrip('\r\n')


def git_status_lines(repo_path: Path) -> List[str]:
    output = git_try(repo_path, 'status', '--porcelain=v1', '--untracked-files=all') or ''
    return [line for line in output.splitlines() if line.strip()]


def status_to_paths(lines: Iterable[str]) -> List[str]:
    paths: List[str] = []
    for line in lines:
        payload = line[3:] if len(line) > 3 else ''
        if ' -> ' in payload:
            parts = [part.strip() for part in payload.split(' -> ') if part.strip()]
            paths.extend(parts)
        else:
            path = payload.strip()
            if path:
                paths.append(path)
    return sorted(dict.fromkeys(paths))


def diff_stat(repo_path: Path) -> Optional[str]:
    combined = []
    unstaged = git_try(repo_path, 'diff', '--stat', '--no-ext-diff')
    staged = git_try(repo_path, 'diff', '--stat', '--cached', '--no-ext-diff')
    if unstaged:
        combined.append('UNSTAGED\n' + unstaged)
    if staged:
        combined.append('STAGED\n' + staged)
    text = '\n\n'.join(combined).strip()
    return text or None


def build_prompt(artifact: Dict[str, Any], artifact_path: Path, validation_path: Optional[Path], repo_path: Path) -> str:
    pr = artifact.get('pr') or {}
    constraints = artifact.get('constraints') or {}
    issues = artifact.get('issues') or []

    lines = [
        'Use the CodeRabbit PR automation workflow on the normalized issue artifact at:',
        str(artifact_path),
        '',
        f'Repository path: {repo_path}',
        f'PR: #{pr.get("number")} - {pr.get("title")}',
        f'Branch: {pr.get("branch")}',
        f'Repository: {pr.get("repository")}',
        '',
        'Keep the work bounded to the extracted unresolved CodeRabbit issue set.',
        'Project-local agent context is installed for this run:',
        '- Generic shared skills may be available under .agents/skills/',
        '- Cursor-specific rules may be available under .cursor/rules/',
        '',
        'Use applicable installed skills or rules when supported by your runtime.',
        'Do not rely on them to widen scope beyond the extracted issues.',
        '',
        'Do not commit, push, post PR comments, resolve threads, switch branches, or widen scope beyond the extracted issues.',
    ]

    if validation_path is not None:
        lines.extend([
            '',
            'If validation output exists, use it to decide what still remains in scope:',
            str(validation_path),
        ])

    if constraints:
        lines.extend([
            '',
            'Workflow constraints:',
            f"- maxCycles: {constraints.get('maxCycles')}",
            f"- allowCommit: {constraints.get('allowCommit')}",
            f"- allowPush: {constraints.get('allowPush')}",
            f"- allowPrComment: {constraints.get('allowPrComment')}",
            f"- allowThreadResolution: {constraints.get('allowThreadResolution')}",
            f"- allowScopeExpansion: {constraints.get('allowScopeExpansion')}",
        ])

    lines.extend([
        '',
        f'Actionable issue count: {len(issues)}',
        '',
        'Issues:',
    ])

    for index, issue in enumerate(issues, start=1):
        file_part = issue.get('file') or '<unknown-file>'
        line_part = issue.get('line') or issue.get('startLine')
        location = f'{file_part}:{line_part}' if line_part else file_part
        lines.extend([
            f'{index}. [{issue.get("severity", "unknown")}] {issue.get("id", "unknown-id")} @ {location}',
            f'   Title: {issue.get("title", "")}',
            f'   Description: {issue.get("description", "")}',
            f'   Agent prompt: {issue.get("agentPrompt", "")}',
        ])

    lines.extend([
        '',
        'Return a concise summary of what you changed and what remains unresolved.',
    ])

    return '\n'.join(lines).strip() + '\n'


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2) + '\n', encoding='utf-8')


def summarize_text(summary: Dict[str, Any]) -> str:
    lines = [
        f"status: {summary.get('status')}",
        f"repo path: {summary.get('repoPath')}",
        f"shared root: {summary.get('sharedRoot')}",
        f"PR number: {summary.get('prNumber')}",
        f"artifact path: {summary.get('artifactPath')}",
        f"prompt path: {summary.get('promptPath')}",
        f"validation path: {summary.get('validationPath')}",
        f"issue count: {summary.get('issueCount')}",
        f"changes applied: {summary.get('changesApplied')}",
        f"changed files: {', '.join(summary.get('changedFiles') or []) or 'none'}",
    ]
    if summary.get('command'):
        lines.append('command: ' + ' '.join(summary['command']))
    if summary.get('note'):
        lines.extend(['', f"note: {summary['note']}"])
    return '\n'.join(lines).strip() + '\n'


def main() -> int:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    artifact_path = out_dir / 'actionable-issues.json'
    artifact = load_json(artifact_path) if artifact_path.exists() else {}
    issues = artifact.get('issues') or []
    issue_ids = [issue.get('id') for issue in issues if isinstance(issue, dict) and issue.get('id')]

    validation_path: Optional[Path] = None
    candidate_validation_paths = [
        out_dir / 'validation-result.json',
        out_dir.parent.parent / 'validation-result.json' if len(out_dir.parents) >= 2 else None,
    ]
    for candidate in candidate_validation_paths:
        if candidate is not None and candidate.exists():
            validation_path = candidate
            break

    prompt_path = out_dir / 'agent-pass-prompt.txt'
    prompt_path.write_text(
        build_prompt(artifact, artifact_path, validation_path, Path(args.repo_path)),
        encoding='utf-8',
    )

    stdout_path = out_dir / 'agent-pass-raw.stdout.txt'
    stderr_path = out_dir / 'agent-pass-raw.stderr.txt'
    command_path = out_dir / 'agent-pass-command.json'
    diff_stat_path = out_dir / 'agent-pass-diff.stat.txt'

    try:
        command_spec = parse_command_spec()
    except ValueError as exc:
        summary = {
            'status': 'misconfigured',
            'phase': 'agent_pass',
            'repoPath': args.repo_path,
            'sharedRoot': args.shared_root,
            'prNumber': args.pr_number,
            'artifactPath': str(artifact_path),
            'promptPath': str(prompt_path),
            'validationPath': str(validation_path) if validation_path else None,
            'issueCount': len(issues),
            'issueIds': issue_ids,
            'changesApplied': False,
            'changedFiles': [],
            'command': None,
            'commandSource': None,
            'note': str(exc),
            'metadata': {
                'createdAt': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                'source': 'coderabbit-agent-pass-runner',
            },
        }
        write_json(out_dir / 'agent-pass-summary.json', summary)
        (out_dir / 'agent-pass-summary.txt').write_text(summarize_text(summary), encoding='utf-8')
        print(f'Agent pass misconfigured: wrote {out_dir / "agent-pass-summary.json"}')
        return 1

    if not command_spec['command']:
        summary = {
            'status': 'not_configured',
            'phase': 'agent_pass',
            'repoPath': args.repo_path,
            'sharedRoot': args.shared_root,
            'prNumber': args.pr_number,
            'artifactPath': str(artifact_path),
            'promptPath': str(prompt_path),
            'validationPath': str(validation_path) if validation_path else None,
            'issueCount': len(issues),
            'issueIds': issue_ids,
            'changesApplied': False,
            'changedFiles': [],
            'command': None,
            'commandSource': None,
            'note': 'No agent command configured. Set CODERABBIT_AGENT_COMMAND_JSON (preferred) or CODERABBIT_AGENT_COMMAND.',
            'metadata': {
                'createdAt': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                'source': 'coderabbit-agent-pass-runner',
            },
        }
        write_json(out_dir / 'agent-pass-summary.json', summary)
        (out_dir / 'agent-pass-summary.txt').write_text(summarize_text(summary), encoding='utf-8')
        print(f'Agent pass not configured: wrote {out_dir / "agent-pass-summary.json"}')
        return 0

    token_map = {
        'repo_path': str(Path(args.repo_path).resolve()),
        'shared_root': str(Path(args.shared_root).resolve()),
        'pr_number': str(args.pr_number),
        'artifact_path': str(artifact_path.resolve()),
        'prompt_path': str(prompt_path.resolve()),
        'validation_path': str(validation_path.resolve()) if validation_path else '',
        'out_dir': str(out_dir.resolve()),
    }
    command = substitute_tokens(command_spec['command'], token_map)
    write_json(command_path, {
        'source': command_spec['source'],
        'command': command,
    })

    before_status = git_status_lines(Path(args.repo_path))
    before_paths = status_to_paths(before_status)

    try:
        completed = subprocess.run(
            command,
            cwd=str(Path(args.repo_path).resolve()),
            text=True,
            capture_output=True,
            check=False,
        )
    except FileNotFoundError:
        summary = {
            'status': 'not_available',
            'phase': 'agent_pass',
            'repoPath': args.repo_path,
            'sharedRoot': args.shared_root,
            'prNumber': args.pr_number,
            'artifactPath': str(artifact_path),
            'promptPath': str(prompt_path),
            'validationPath': str(validation_path) if validation_path else None,
            'issueCount': len(issues),
            'issueIds': issue_ids,
            'changesApplied': False,
            'changedFiles': [],
            'command': command,
            'commandSource': command_spec['source'],
            'note': f'Agent command executable was not found: {command[0]}',
            'metadata': {
                'createdAt': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                'source': 'coderabbit-agent-pass-runner',
            },
        }
        write_json(out_dir / 'agent-pass-summary.json', summary)
        (out_dir / 'agent-pass-summary.txt').write_text(summarize_text(summary), encoding='utf-8')
        print(f'Agent pass executable unavailable: wrote {out_dir / "agent-pass-summary.json"}')
        return 0

    stdout_path.write_text(completed.stdout or '', encoding='utf-8')
    stderr_path.write_text(completed.stderr or '', encoding='utf-8')

    after_status = git_status_lines(Path(args.repo_path))
    after_paths = status_to_paths(after_status)
    changed_files = sorted(dict.fromkeys(after_paths))
    changes_applied = before_status != after_status

    stat_text = diff_stat(Path(args.repo_path))
    if stat_text:
        diff_stat_path.write_text(stat_text + '\n', encoding='utf-8')

    summary = {
        'status': 'ok' if completed.returncode == 0 else 'error',
        'phase': 'agent_pass',
        'repoPath': args.repo_path,
        'sharedRoot': args.shared_root,
        'prNumber': args.pr_number,
        'artifactPath': str(artifact_path),
        'promptPath': str(prompt_path),
        'validationPath': str(validation_path) if validation_path else None,
        'issueCount': len(issues),
        'issueIds': issue_ids,
        'changesApplied': changes_applied,
        'beforeChangedFiles': before_paths,
        'changedFiles': changed_files,
        'command': command,
        'commandSource': command_spec['source'],
        'raw': {
            'stdoutPath': str(stdout_path),
            'stderrPath': str(stderr_path),
            'commandPath': str(command_path),
            'diffStatPath': str(diff_stat_path) if stat_text else None,
            'exitCode': completed.returncode,
        },
        'note': None if completed.returncode == 0 else 'Agent command failed. Inspect raw stdout/stderr artifacts for details.',
        'metadata': {
            'createdAt': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            'source': 'coderabbit-agent-pass-runner',
        },
    }

    write_json(out_dir / 'agent-pass-summary.json', summary)
    (out_dir / 'agent-pass-summary.txt').write_text(summarize_text(summary), encoding='utf-8')

    if completed.returncode == 0:
        print(f'Agent pass complete: wrote {out_dir / "agent-pass-summary.json"}')
        return 0

    print(f'Agent pass failed: wrote {out_dir / "agent-pass-summary.json"}')
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
