"""Read-only explicit-request admission adapter for the gated hosted diagnostic.

No CLI/provider, publication, merge, settings or credential mutation is possible.
A diagnostic journal is not proof of a live distributed/durable claim.
"""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import time

import pullfrog_cloud_coordinator as cloud
import pullfrog_standalone_contract as contract
import pullfrog_standalone_controller as controller
import pullfrog_standalone_worker as worker


def _epoch(value):
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        controller.require(parsed.tzinfo is not None, 'invalid_creation_time')
        return int(parsed.timestamp())
    except (TypeError, ValueError, AttributeError):
        raise contract.ContractError('invalid_creation_time')


def build_bundle(event, kind, policy, client, *, run_id, now):
    controller.require(policy.get('enabled') is True, 'policy_not_enabled')
    slug = policy.get('repository_slug')
    controller.require(type(slug) is str and event.get('repository', {}).get('full_name', '').casefold() == slug, 'repository_mismatch')
    actor = event.get('sender', {})
    identity = {'account_id': actor.get('id'), 'login': actor.get('login'), 'type': actor.get('type')}
    controller.require(any(contract.digest(identity) == contract.digest(a) for a in policy.get('initiators', [])), 'unauthorized_initiator')
    if kind == 'issue_comment':
        issue, comment = event.get('issue', {}), event.get('comment', {})
        controller.require(event.get('action') == 'created' and type(issue.get('pull_request')) is dict
            and comment.get('body') == '/pr-automation run', 'explicit_request_required')
        controller.require(type(comment.get('id')) is int and comment['id'] > 0, 'invalid_comment_id')
        number, issued, rid = issue.get('number'), _epoch(comment.get('created_at')), 'comment:' + str(comment['id'])
        task = None
    elif kind == 'workflow_dispatch':
        inputs = event.get('inputs', {})
        raw_number = inputs.get('pr_number', '')
        controller.require(type(raw_number) is str and raw_number.isascii() and raw_number.isdigit(), 'invalid_pr_number')
        number = int(raw_number)
        controller.require(type(run_id) is int and run_id > 0, 'invalid_run_id')
        run = client.get(f'/repos/{slug}/actions/runs/{run_id}')
        controller.require(type(run) is dict and type(run.get('id')) is int and run['id'] == run_id, 'run_identity_mismatch')
        controller.require(run.get('path', '').split('@')[0] == '.github/workflows/pullfrog-standalone-admission.yml'
            and run.get('event') == 'workflow_dispatch', 'untrusted_run_identity')
        issued, rid = _epoch(run.get('created_at')), 'dispatch:' + str(run_id)
        task = inputs.get('task')
    else:
        raise contract.ContractError('unsupported_initial_event')
    controller.require(type(number) is int and number > 0, 'invalid_pr_number')
    prefix = f'/repos/{slug}'
    repository = client.get(prefix)
    pr = client.get(f'{prefix}/pulls/{number}')
    controller.require(type(repository) is dict and repository.get('full_name', '').casefold() == slug, 'repository_mismatch')
    controller.require(type(pr) is dict and type(pr.get('number')) is int and pr['number'] == number and pr.get('state') == 'open', 'invalid_open_pr')
    head, base = pr.get('head', {}), pr.get('base', {})
    controller.require(head.get('repo', {}).get('full_name', '').casefold() == slug
        and base.get('repo', {}).get('full_name', '').casefold() == slug, 'fork_or_repository_mismatch')
    if task is None:
        task = pr.get('body') or pr.get('title')
    controller.require(type(task) is str, 'missing_task')
    task = task.strip()
    request = {'schema': contract.SCHEMA, 'repository_slug': slug, 'pr_number': number, 'request_id': rid,
        'initiator': identity, 'base_ref': base.get('ref'), 'base_sha': base.get('sha'),
        'head_ref': head.get('ref'), 'head_sha': head.get('sha'), 'task': task,
        'allowed_paths': policy.get('allowed_paths'), 'issued_at': issued,
        'expires_at': issued + policy['budget']['max_seconds'], 'policy_mode': 'standalone', 'budget': policy['budget']}
    contract.validate_request(request, now=now)
    protected = policy.get('protected_refs', [])
    controller.require(type(protected) is list and base.get('ref') in protected
        and repository.get('default_branch') in protected, 'incomplete_protected_refs')
    destination = {'slug': slug, 'head_repository_slug': slug, 'pr_number': number,
        'base_ref': base.get('ref'), 'base_sha': base.get('sha'), 'head_ref': head.get('ref'), 'head_sha': head.get('sha'),
        'default_branch': repository.get('default_branch'), 'protected_refs': protected}
    controller.require(worker.guard.evaluate_destination(destination)['status'] == 'destination_allowed', 'destination_blocked')
    event_input = {'kind': kind, 'delivery_id': rid, 'actor': identity, 'head_sha': head.get('sha')}
    event_input.update({'command': '/pr-automation run'} if kind == 'issue_comment' else {'task': task})
    return {'request': request, 'event': event_input, 'policy': {'initiators': policy['initiators'],
        'repositories': [slug], 'policy_modes': ['standalone']}, 'destination': destination}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--policy', required=True)
    parser.add_argument('--out-dir', required=True)
    args = parser.parse_args()
    try:
        event = controller._read(Path(os.environ['GITHUB_EVENT_PATH']))
        policy = controller._read(Path(args.policy))
        controller.require(os.environ.get('GITHUB_REPOSITORY', '').casefold() == policy.get('repository_slug'), 'repository_mismatch')
        client = cloud.GitHubReadClient(os.environ.get('GITHUB_API_URL', 'https://api.github.com'),
            os.environ.get('GITHUB_TOKEN', ''), policy['repository_slug'])
        now = int(time.time())
        bundle = build_bundle(event, os.environ.get('GITHUB_EVENT_NAME'), policy, client,
            run_id=int(os.environ.get('GITHUB_RUN_ID', '0')), now=now)
        out = Path(args.out_dir); out.mkdir(parents=True, exist_ok=True)
        result = controller.advance(controller.Journal(out/'diagnostic-journal.json'), bundle['request'], bundle['event'], bundle['policy'], expected_digest=None, now=now)
        summary = {'schema': 'pullfrog-standalone-hosted-diagnostic.v1', 'status': result['output']['status'],
            'binding': result['output']['binding'], 'journal_digest': result['journal_digest'],
            'live_execution_allowed': False, 'merge_allowed': False,
            'remaining_gates': ['hosted_durable_claim_store', 'decision_transport_qualification',
                'coding_cli_isolation_and_billing_hard_stop', 'separate_publisher_qualification']}
        (out/'summary.json').write_text(json.dumps(summary, sort_keys=True))
        print(json.dumps(summary, sort_keys=True))
        return 0
    except (contract.ContractError, cloud.CoordinatorError) as exc:
        print(json.dumps({'status': 'stopped', 'reason': exc.code, 'live_execution_allowed': False, 'merge_allowed': False}))
        return 2
    except (KeyError, TypeError, ValueError, OSError):
        print(json.dumps({'status': 'stopped', 'reason': 'invalid_or_unavailable_trusted_input', 'live_execution_allowed': False, 'merge_allowed': False}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
