#!/usr/bin/env python3
import argparse
import json
import os
import shlex
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


EXCLUDED_PREFIXES = (
    '.coderabbit/out',
    '.agents/skills',
    '.cursor/rules',
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Post-remediation commit pass runner using installed Git skills.'
    )
    parser.add_argument('--repo-path', required=True)
    parser.add_argument('--shared-root', required=True)
    parser.add_argument('--pr-number', required=True, type=int)
    parser.add_argument('--out-dir', required=True)
    parser.add_argument('--commit-strategy', required=True)
    parser.add_argument('--commit-count-mode', required=True)
    parser.add_argument('--fixed-commit-count', required=True, type=int)
    parser.add_argument('--stop-on-ambiguous-remainder', required=True)
    return parser.parse_args()


def parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {'1', 'true', 'yes', 'on'}:
        return True
    if normalized in {'0', 'false', 'no', 'off'}:
        return False
    raise ValueError(f'Unsupported boolean value: {value}')


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


def is_excluded_path(path: str) -> bool:
    normalized = path.replace('\\', '/').lstrip('./')
    return any(
        normalized == prefix or normalized.startswith(prefix + '/')
        for prefix in EXCLUDED_PREFIXES
    )


def filter_meaningful_paths(paths: Iterable[str]) -> List[str]:
    return [path for path in paths if not is_excluded_path(path)]


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


def build_prompt(
    *,
    repo_path: Path,
    pr_number: int,
    changed_files: List[str],
    strategy: str,
    count_mode: str,
    fixed_count: int,
    stop_on_ambiguous_remainder: bool,
    diff_stat_text: Optional[str],
) -> str:
    git_repo_sync_path = repo_path / '.agents' / 'skills' / 'git-repo-sync' / 'SKILL.md'
    partitioner_path = repo_path / '.agents' / 'skills' / 'changeset-commit-partitioner' / 'SKILL.md'

    lines = [
        'Delegate post-remediation local Git save behavior to the installed Git skills for the meaningful repository changes below.',
        f'Repository path: {repo_path}',
        f'PR number: {pr_number}',
        '',
        'Use the installed Git skills for this task:',
        f'- git-repo-sync: {git_repo_sync_path}',
    ]

    if strategy == 'split-by-scope':
        lines.append(f'- changeset-commit-partitioner: {partitioner_path}')

    lines.extend([
        '',
        'Execution policy:',
        '- mode: execute-approved',
        '- allow_commit: true',
        '- allow_push: false',
        '- allow_fetch: false',
        '- allow_pull: false',
        '- allow_rebase: false',
        f'- commit_strategy: {strategy}',
        f'- commit_count_mode: {count_mode}',
        f'- fixed_commit_count: {fixed_count}',
        f'- stop_on_ambiguous_remainder: {str(stop_on_ambiguous_remainder).lower()}',
        '',
        'Important exclusions:',
        '- Do not include .coderabbit/out/** in any commit.',
        '- Do not include .agents/skills/** in any commit.',
        '- Do not include .cursor/rules/** in any commit.',
        '- Do not push, fetch, pull, rebase, switch branches, or widen scope beyond the meaningful repo changes below.',
        '',
        'Changed files in scope for this commit pass:',
    ])

    lines.extend(f'- {path}' for path in changed_files)

    if diff_stat_text:
        lines.extend([
            '',
            'Current diff stat (may include staged and unstaged changes):',
            diff_stat_text,
        ])

    lines.extend([
        '',
        'Instructions:',
        '- Use git-repo-sync as the governing skill for local Git save behavior.',
        '- If commit_strategy is split-by-scope, use changeset-commit-partitioner to determine a truthful multi-commit plan.',
    ])

    if strategy == 'single-commit':
        lines.append('- In single-commit mode, let git-repo-sync decide whether one honest local commit is justified for the visible change set.')
    elif count_mode == 'auto':
        lines.append('- In auto mode, let the installed skills determine how many coherent commit groups are actually needed.')
    else:
        lines.append(f'- In fixed mode, cap execution at the first {fixed_count} coherent commit groups determined by the installed skills and leave any remainder uncommitted.')

    lines.extend([
        '- If the remainder is ambiguous and stop_on_ambiguous_remainder is true, stop and report the remainder instead of forcing it into a commit.',
        '- Let the installed skills draft any commit title/body. Do not apply extra workflow-specific commit-message formatting rules beyond the policy above.',
        '',
        'Return a concise summary including:',
        '- whether any commit was created',
        '- the commit title(s) used, if any',
        '- any remaining uncommitted meaningful files',
        '- whether the run stopped due to ambiguous remainder or policy',
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
        f"auto commit: {summary.get('autoCommit')}",
        f"commit strategy: {summary.get('commitStrategy')}",
        f"commit count mode: {summary.get('commitCountMode')}",
        f"fixed commit count: {summary.get('fixedCommitCount')}",
        f"stop on ambiguous remainder: {summary.get('stopOnAmbiguousRemainder')}",
        f"prompt path: {summary.get('promptPath')}",
        f"meaningful changes detected: {summary.get('meaningfulChangesDetected')}",
        f"candidate files: {', '.join(summary.get('candidateFiles') or []) or 'none'}",
        f"remaining changed files: {', '.join(summary.get('remainingChangedFiles') or []) or 'none'}",
    ]
    if summary.get('command'):
        lines.append('command: ' + ' '.join(summary['command']))
    if summary.get('note'):
        lines.extend(['', f"note: {summary['note']}"])
    return '\n'.join(lines).strip() + '\n'


def validate_args(args: argparse.Namespace) -> Optional[str]:
    if args.commit_strategy not in {'single-commit', 'split-by-scope'}:
        return 'commit_strategy must be one of: single-commit, split-by-scope'
    if args.commit_count_mode not in {'auto', 'fixed'}:
        return 'commit_count_mode must be one of: auto, fixed'
    if args.commit_count_mode == 'fixed' and args.fixed_commit_count < 1:
        return 'fixed_commit_count must be >= 1 when commit_count_mode=fixed'
    return None


def main() -> int:
    args = parse_args()
    validation_error = validate_args(args)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if validation_error is not None:
        summary = {
            'status': 'misconfigured',
            'phase': 'commit_pass',
            'repoPath': args.repo_path,
            'sharedRoot': args.shared_root,
            'prNumber': args.pr_number,
            'autoCommit': True,
            'commitStrategy': args.commit_strategy,
            'commitCountMode': args.commit_count_mode,
            'fixedCommitCount': args.fixed_commit_count,
            'stopOnAmbiguousRemainder': args.stop_on_ambiguous_remainder,
            'meaningfulChangesDetected': False,
            'candidateFiles': [],
            'remainingChangedFiles': [],
            'promptPath': None,
            'command': None,
            'commandSource': None,
            'note': validation_error,
            'metadata': {
                'createdAt': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                'source': 'coderabbit-commit-pass-runner',
            },
        }
        write_json(out_dir / 'commit-pass-summary.json', summary)
        (out_dir / 'commit-pass-summary.txt').write_text(summarize_text(summary), encoding='utf-8')
        print(f'Commit pass misconfigured: wrote {out_dir / "commit-pass-summary.json"}')
        return 1

    repo_path = Path(args.repo_path).resolve()
    stop_on_ambiguous = parse_bool(args.stop_on_ambiguous_remainder)

    before_status = git_status_lines(repo_path)
    before_paths = status_to_paths(before_status)
    candidate_files = filter_meaningful_paths(before_paths)

    prompt_path = out_dir / 'commit-pass-prompt.txt'
    stdout_path = out_dir / 'commit-pass-raw.stdout.txt'
    stderr_path = out_dir / 'commit-pass-raw.stderr.txt'
    command_path = out_dir / 'commit-pass-command.json'
    diff_stat_path = out_dir / 'commit-pass-diff.stat.txt'

    if not candidate_files:
        summary = {
            'status': 'no_meaningful_changes',
            'phase': 'commit_pass',
            'repoPath': str(repo_path),
            'sharedRoot': args.shared_root,
            'prNumber': args.pr_number,
            'autoCommit': True,
            'commitStrategy': args.commit_strategy,
            'commitCountMode': args.commit_count_mode,
            'fixedCommitCount': args.fixed_commit_count,
            'stopOnAmbiguousRemainder': stop_on_ambiguous,
            'meaningfulChangesDetected': False,
            'candidateFiles': [],
            'remainingChangedFiles': [],
            'promptPath': None,
            'command': None,
            'commandSource': None,
            'note': 'No meaningful post-remediation repository changes were detected after excluding runtime artifacts and installed agent context files.',
            'metadata': {
                'createdAt': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                'source': 'coderabbit-commit-pass-runner',
            },
        }
        write_json(out_dir / 'commit-pass-summary.json', summary)
        (out_dir / 'commit-pass-summary.txt').write_text(summarize_text(summary), encoding='utf-8')
        print(f'Commit pass skipped: wrote {out_dir / "commit-pass-summary.json"}')
        return 0

    diff_stat_text = diff_stat(repo_path)
    if diff_stat_text:
        diff_stat_path.write_text(diff_stat_text + '\n', encoding='utf-8')

    prompt_path.write_text(
        build_prompt(
            repo_path=repo_path,
            pr_number=args.pr_number,
            changed_files=candidate_files,
            strategy=args.commit_strategy,
            count_mode=args.commit_count_mode,
            fixed_count=args.fixed_commit_count,
            stop_on_ambiguous_remainder=stop_on_ambiguous,
            diff_stat_text=diff_stat_text,
        ),
        encoding='utf-8',
    )

    try:
        command_spec = parse_command_spec()
    except ValueError as exc:
        summary = {
            'status': 'misconfigured',
            'phase': 'commit_pass',
            'repoPath': str(repo_path),
            'sharedRoot': args.shared_root,
            'prNumber': args.pr_number,
            'autoCommit': True,
            'commitStrategy': args.commit_strategy,
            'commitCountMode': args.commit_count_mode,
            'fixedCommitCount': args.fixed_commit_count,
            'stopOnAmbiguousRemainder': stop_on_ambiguous,
            'meaningfulChangesDetected': True,
            'candidateFiles': candidate_files,
            'remainingChangedFiles': candidate_files,
            'promptPath': str(prompt_path),
            'command': None,
            'commandSource': None,
            'note': str(exc),
            'metadata': {
                'createdAt': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                'source': 'coderabbit-commit-pass-runner',
            },
        }
        write_json(out_dir / 'commit-pass-summary.json', summary)
        (out_dir / 'commit-pass-summary.txt').write_text(summarize_text(summary), encoding='utf-8')
        print(f'Commit pass misconfigured: wrote {out_dir / "commit-pass-summary.json"}')
        return 1

    if not command_spec['command']:
        summary = {
            'status': 'not_configured',
            'phase': 'commit_pass',
            'repoPath': str(repo_path),
            'sharedRoot': args.shared_root,
            'prNumber': args.pr_number,
            'autoCommit': True,
            'commitStrategy': args.commit_strategy,
            'commitCountMode': args.commit_count_mode,
            'fixedCommitCount': args.fixed_commit_count,
            'stopOnAmbiguousRemainder': stop_on_ambiguous,
            'meaningfulChangesDetected': True,
            'candidateFiles': candidate_files,
            'remainingChangedFiles': candidate_files,
            'promptPath': str(prompt_path),
            'command': None,
            'commandSource': None,
            'note': 'No agent command configured. Set CODERABBIT_AGENT_COMMAND_JSON (preferred) or CODERABBIT_AGENT_COMMAND.',
            'metadata': {
                'createdAt': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                'source': 'coderabbit-commit-pass-runner',
            },
        }
        write_json(out_dir / 'commit-pass-summary.json', summary)
        (out_dir / 'commit-pass-summary.txt').write_text(summarize_text(summary), encoding='utf-8')
        print(f'Commit pass not configured: wrote {out_dir / "commit-pass-summary.json"}')
        return 0

    token_map = {
        'repo_path': str(repo_path),
        'shared_root': str(Path(args.shared_root).resolve()),
        'pr_number': str(args.pr_number),
        'artifact_path': '',
        'prompt_path': str(prompt_path.resolve()),
        'validation_path': '',
        'out_dir': str(out_dir.resolve()),
    }
    command = substitute_tokens(command_spec['command'], token_map)
    write_json(command_path, {
        'source': command_spec['source'],
        'command': command,
    })

    try:
        completed = subprocess.run(
            command,
            cwd=str(repo_path),
            text=True,
            capture_output=True,
            check=False,
        )
    except FileNotFoundError:
        summary = {
            'status': 'not_available',
            'phase': 'commit_pass',
            'repoPath': str(repo_path),
            'sharedRoot': args.shared_root,
            'prNumber': args.pr_number,
            'autoCommit': True,
            'commitStrategy': args.commit_strategy,
            'commitCountMode': args.commit_count_mode,
            'fixedCommitCount': args.fixed_commit_count,
            'stopOnAmbiguousRemainder': stop_on_ambiguous,
            'meaningfulChangesDetected': True,
            'candidateFiles': candidate_files,
            'remainingChangedFiles': candidate_files,
            'promptPath': str(prompt_path),
            'command': command,
            'commandSource': command_spec['source'],
            'note': f'Agent command executable was not found: {command[0]}',
            'metadata': {
                'createdAt': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                'source': 'coderabbit-commit-pass-runner',
            },
        }
        write_json(out_dir / 'commit-pass-summary.json', summary)
        (out_dir / 'commit-pass-summary.txt').write_text(summarize_text(summary), encoding='utf-8')
        print(f'Commit pass executable unavailable: wrote {out_dir / "commit-pass-summary.json"}')
        return 0

    stdout_path.write_text(completed.stdout or '', encoding='utf-8')
    stderr_path.write_text(completed.stderr or '', encoding='utf-8')

    after_status = git_status_lines(repo_path)
    after_paths = status_to_paths(after_status)
    remaining_files = filter_meaningful_paths(after_paths)

    summary = {
        'status': 'ok' if completed.returncode == 0 else 'error',
        'phase': 'commit_pass',
        'repoPath': str(repo_path),
        'sharedRoot': args.shared_root,
        'prNumber': args.pr_number,
        'autoCommit': True,
        'commitStrategy': args.commit_strategy,
        'commitCountMode': args.commit_count_mode,
        'fixedCommitCount': args.fixed_commit_count,
        'stopOnAmbiguousRemainder': stop_on_ambiguous,
        'meaningfulChangesDetected': True,
        'candidateFiles': candidate_files,
        'remainingChangedFiles': remaining_files,
        'promptPath': str(prompt_path),
        'command': command,
        'commandSource': command_spec['source'],
        'raw': {
            'stdoutPath': str(stdout_path),
            'stderrPath': str(stderr_path),
            'commandPath': str(command_path),
            'diffStatPath': str(diff_stat_path) if diff_stat_text else None,
            'exitCode': completed.returncode,
        },
        'note': None if completed.returncode == 0 else 'Commit pass agent command failed. Inspect raw stdout/stderr artifacts for details.',
        'metadata': {
            'createdAt': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            'source': 'coderabbit-commit-pass-runner',
        },
    }

    write_json(out_dir / 'commit-pass-summary.json', summary)
    (out_dir / 'commit-pass-summary.txt').write_text(summarize_text(summary), encoding='utf-8')

    if completed.returncode == 0:
        print(f'Commit pass complete: wrote {out_dir / "commit-pass-summary.json"}')
        return 0

    print(f'Commit pass failed: wrote {out_dir / "commit-pass-summary.json"}')
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
