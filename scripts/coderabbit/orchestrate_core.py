#!/usr/bin/env python3
import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

SEVERITY_ORDER = ['critical', 'high', 'medium', 'low', 'unknown']


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Bounded orchestration for CodeRabbit PR automation.'
    )
    parser.add_argument('--repo-path', required=True)
    parser.add_argument('--shared-root', required=True)
    parser.add_argument('--pr-number', required=True, type=int)
    parser.add_argument('--run-validation', default='true')
    parser.add_argument('--out-dir', required=True)
    return parser.parse_args()


def parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {'1', 'true', 'yes', 'on'}:
        return True
    if normalized in {'0', 'false', 'no', 'off'}:
        return False
    raise ValueError(f'Unsupported boolean value: {value}')


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))


def summarize_issue_severities(issues: List[Dict[str, Any]]) -> Dict[str, int]:
    counts = {severity: 0 for severity in SEVERITY_ORDER}
    for issue in issues:
        severity = issue.get('severity') or 'unknown'
        if severity not in counts:
            severity = 'unknown'
        counts[severity] += 1
    counts['total'] = len(issues)
    counts['blocking'] = counts['critical'] + counts['high'] + counts['medium']
    return counts


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + '\n', encoding='utf-8')


def ensure_artifact(cycle_dir: Path, root_artifact_path: Path) -> Path:
    target_artifact = cycle_dir / 'actionable-issues.json'
    shutil.copy2(root_artifact_path, target_artifact)
    return target_artifact


def build_summary(
    *,
    args: argparse.Namespace,
    artifact: Dict[str, Any],
    issue_summary: Dict[str, int],
    max_cycles: int,
    run_validation: bool,
    status: str,
    stop_reason: str,
    cycles: List[Dict[str, Any]],
    validation_available: bool,
    rate_limited: bool,
) -> Dict[str, Any]:
    pr = artifact.get('pr') or {}
    return {
        'status': status,
        'repoPath': args.repo_path,
        'sharedRoot': args.shared_root,
        'prNumber': args.pr_number,
        'runValidation': run_validation,
        'maxCycles': max_cycles,
        'stopReason': stop_reason,
        'validationAvailable': validation_available,
        'rateLimited': rate_limited,
        'pr': {
            'number': pr.get('number'),
            'title': pr.get('title'),
            'branch': pr.get('branch'),
            'repository': pr.get('repository'),
            'headSha': pr.get('headSha'),
        },
        'issueSummary': issue_summary,
        'cyclesCompleted': len(cycles),
        'cycles': cycles,
        'metadata': {
            'createdAt': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            'source': 'coderabbit-orchestrator',
        },
    }


def run_python(script_path: Path, *script_args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script_path), *script_args],
        text=True,
        capture_output=True,
        check=False,
    )


def interpret_validation(validation: Dict[str, Any]) -> Dict[str, Any]:
    status = validation.get('status')
    rate_limit = validation.get('rateLimit') or {}
    summary = validation.get('summary') or {}

    rate_limited = bool(rate_limit.get('hit'))
    if rate_limited:
        return {
            'decision': 'stop',
            'reason': 'validation_rate_limited',
            'blockingCount': summary.get('blockingCount'),
            'rateLimited': True,
        }

    if status == 'not_implemented':
        return {
            'decision': 'stop',
            'reason': 'validation_not_implemented',
            'blockingCount': None,
            'rateLimited': False,
        }
    if status == 'not_available':
        return {
            'decision': 'stop',
            'reason': 'validation_not_available',
            'blockingCount': None,
            'rateLimited': False,
        }
    if status == 'auth_required':
        return {
            'decision': 'stop',
            'reason': 'validation_auth_required',
            'blockingCount': None,
            'rateLimited': False,
        }
    if status == 'error':
        return {
            'decision': 'stop',
            'reason': 'validation_error',
            'blockingCount': None,
            'rateLimited': False,
        }

    blocking_count = summary.get('blockingCount')
    total_findings = summary.get('totalFindings')

    if isinstance(blocking_count, int):
        if blocking_count <= 0:
            if isinstance(total_findings, int) and total_findings > 0:
                return {
                    'decision': 'stop',
                    'reason': 'only_nits_remain',
                    'blockingCount': blocking_count,
                    'rateLimited': False,
                }
            return {
                'decision': 'stop',
                'reason': 'validation_clean',
                'blockingCount': blocking_count,
                'rateLimited': False,
            }
        return {
            'decision': 'continue',
            'reason': 'blocking_findings_remain',
            'blockingCount': blocking_count,
            'rateLimited': False,
        }

    return {
        'decision': 'stop',
        'reason': 'validation_unusable',
        'blockingCount': None,
        'rateLimited': False,
    }


def main() -> int:
    args = parse_args()
    run_validation = parse_bool(args.run_validation)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    shared_root = Path(args.shared_root)
    scripts_dir = shared_root / 'scripts' / 'coderabbit'

    root_artifact_path = out_dir / 'actionable-issues.json'
    if not root_artifact_path.exists():
        raise SystemExit(f'Missing normalized issue artifact: {root_artifact_path}')

    artifact = load_json(root_artifact_path)
    issues = artifact.get('issues')
    if not isinstance(issues, list):
        raise SystemExit('actionable-issues.json must contain an issues array')

    issue_summary = summarize_issue_severities([issue for issue in issues if isinstance(issue, dict)])
    constraints = artifact.get('constraints') or {}
    max_cycles = int(constraints.get('maxCycles') or 3)
    if max_cycles < 1:
        max_cycles = 1

    cycles: List[Dict[str, Any]] = []
    validation_available = False
    rate_limited = False

    if len(issues) == 0:
        summary = build_summary(
            args=args,
            artifact=artifact,
            issue_summary=issue_summary,
            max_cycles=max_cycles,
            run_validation=run_validation,
            status='no_actionable_work',
            stop_reason='no_actionable_issues',
            cycles=cycles,
            validation_available=False,
            rate_limited=False,
        )
        write_json(out_dir / 'orchestration-summary.json', summary)
        print(f'Orchestration stopped early: wrote {out_dir / "orchestration-summary.json"}')
        return 0

    agent_pass_core = scripts_dir / 'run_agent_pass_core.py'
    validation_core = scripts_dir / 'run_validation_core.py'

    stop_reason = 'cycle_limit_reached'
    status = 'completed'

    for cycle in range(1, max_cycles + 1):
        cycle_dir = out_dir / 'cycles' / f'cycle-{cycle:03d}'
        cycle_dir.mkdir(parents=True, exist_ok=True)
        cycle_artifact_path = ensure_artifact(cycle_dir, root_artifact_path)

        cycle_record: Dict[str, Any] = {
            'cycle': cycle,
            'artifactPath': str(cycle_artifact_path),
            'agentPass': None,
            'validation': None,
            'decision': None,
        }

        agent_result = run_python(
            agent_pass_core,
            '--repo-path', args.repo_path,
            '--shared-root', args.shared_root,
            '--pr-number', str(args.pr_number),
            '--out-dir', str(cycle_dir),
        )
        cycle_record['agentPass'] = {
            'exitCode': agent_result.returncode,
            'stdout': agent_result.stdout.strip(),
            'stderr': agent_result.stderr.strip(),
            'summaryPath': str(cycle_dir / 'agent-pass-summary.json'),
        }
        if agent_result.returncode != 0:
            status = 'failed'
            stop_reason = 'agent_pass_failed'
            cycle_record['decision'] = {
                'action': 'stop',
                'reason': stop_reason,
            }
            cycles.append(cycle_record)
            break

        shutil.copy2(cycle_dir / 'agent-pass-summary.json', out_dir / 'agent-pass-summary.json')
        shutil.copy2(cycle_dir / 'agent-pass-summary.txt', out_dir / 'agent-pass-summary.txt')
        agent_summary = load_json(cycle_dir / 'agent-pass-summary.json')
        agent_status = agent_summary.get('status')
        agent_not_implemented = agent_status == 'not_implemented'

        if agent_status == 'not_configured':
            stop_reason = 'agent_pass_not_configured'
            cycle_record['decision'] = {
                'action': 'stop',
                'reason': stop_reason,
            }
            cycles.append(cycle_record)
            break
        if agent_status == 'not_available':
            stop_reason = 'agent_pass_not_available'
            cycle_record['decision'] = {
                'action': 'stop',
                'reason': stop_reason,
            }
            cycles.append(cycle_record)
            break

        if not run_validation:
            stop_reason = 'validation_disabled'
            cycle_record['decision'] = {
                'action': 'stop',
                'reason': stop_reason,
            }
            cycles.append(cycle_record)
            break

        validation_result = run_python(
            validation_core,
            '--repo-path', args.repo_path,
            '--pr-number', str(args.pr_number),
            '--out-dir', str(cycle_dir),
        )
        cycle_record['validation'] = {
            'exitCode': validation_result.returncode,
            'stdout': validation_result.stdout.strip(),
            'stderr': validation_result.stderr.strip(),
            'summaryPath': str(cycle_dir / 'validation-result.json'),
        }
        if validation_result.returncode != 0:
            status = 'failed'
            stop_reason = 'validation_command_failed'
            cycle_record['decision'] = {
                'action': 'stop',
                'reason': stop_reason,
            }
            cycles.append(cycle_record)
            break

        validation_available = True
        shutil.copy2(cycle_dir / 'validation-result.json', out_dir / 'validation-result.json')
        validation_payload = load_json(cycle_dir / 'validation-result.json')
        validation_decision = interpret_validation(validation_payload)
        rate_limited = rate_limited or bool(validation_decision.get('rateLimited'))

        cycle_record['decision'] = {
            'action': validation_decision['decision'],
            'reason': validation_decision['reason'],
            'blockingCount': validation_decision.get('blockingCount'),
        }
        cycles.append(cycle_record)

        if validation_decision['decision'] == 'continue':
            if agent_not_implemented:
                stop_reason = 'agent_pass_not_implemented'
                cycle_record['decision'] = {
                    'action': 'stop',
                    'reason': stop_reason,
                    'blockingCount': validation_decision.get('blockingCount'),
                }
                break
            if cycle >= max_cycles:
                stop_reason = 'cycle_limit_reached'
                break
            continue

        stop_reason = validation_decision['reason']
        break

    if cycles and cycles[-1].get('decision', {}).get('reason') == 'agent_pass_failed':
        status = 'failed'
    elif cycles and cycles[-1].get('decision', {}).get('reason') == 'validation_command_failed':
        status = 'failed'
    elif stop_reason in {
        'cycle_limit_reached',
        'blocking_findings_remain',
        'agent_pass_not_implemented',
        'agent_pass_not_configured',
        'agent_pass_not_available',
    }:
        status = 'stopped'
    else:
        status = 'completed'

    summary = build_summary(
        args=args,
        artifact=artifact,
        issue_summary=issue_summary,
        max_cycles=max_cycles,
        run_validation=run_validation,
        status=status,
        stop_reason=stop_reason,
        cycles=cycles,
        validation_available=validation_available,
        rate_limited=rate_limited,
    )
    write_json(out_dir / 'orchestration-summary.json', summary)
    print(f'Orchestration complete: wrote {out_dir / "orchestration-summary.json"}')
    return 0 if status != 'failed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
