"""Fixed GitHub/Actions ports, using existing authenticated get/post clients.

Policy is trusted runtime configuration, never PR/event/model data. No client,
credential or runner is created implicitly. External calls require host authority.
"""
import copy
import pullfrog_standalone_contract as k
import pullfrog_standalone_collector as collector

PULLFROG_ACTION = 'pullfrog/pullfrog@25a837a2b078177c3acdce790506d1fd1acedd82'


def require(value, reason):
    if not value:
        raise k.ContractError(reason)


class Actions:
    def __init__(self, client, policy, *, review_runner=None):
        self.client, self.policy, self.review_runner = client, copy.deepcopy(policy), review_runner
        if review_runner is None and self.policy.get('review_workflow_id'):
            self.review_runner = PullfrogWorkflowRunner(client, trusted_ref=self.policy['review_trusted_ref'], trusted_sha=self.policy['review_trusted_sha'],
                repository_slug='fr-meyer/agent-toolkit', workflow_id=self.policy['review_workflow_id'])

    def current(self, request, head):
        pr = self.client.get(f"/repos/{request['repository_slug']}/pulls/{request['pr_number']}")
        require(pr.get('state') == 'open' and pr.get('number') == request['pr_number']
                and pr.get('head', {}).get('sha') == head
                and pr.get('base', {}).get('sha') == request['base_sha']
                and all(pr.get(side, {}).get('repo', {}).get('full_name') == request['repository_slug']
                        for side in ('head', 'base')), 'live_destination_drift')
        return pr

    def ci(self, request, head, run_id):
        require(type(run_id) is int and run_id > 0, 'invalid_ci_run')
        self.current(request, head)
        prefix = f"/repos/{request['repository_slug']}"
        run = self.client.get(f'{prefix}/actions/runs/{run_id}')
        workflow = self.policy['ci_workflow_id']
        require(type(workflow) is int and run.get('workflow_id') == workflow
                and run.get('id') == run_id and run.get('head_sha') == head
                and run.get('repository', {}).get('full_name') == request['repository_slug']
                and run.get('head_repository', {}).get('full_name') == request['repository_slug']
                and run.get('event') in ('pull_request', 'push')
                and type(run.get('run_attempt')) is int and run['run_attempt'] > 0,
                'ci_identity_mismatch')
        jobs = []
        for page in range(1, 11):
            response = self.client.get(f"{prefix}/actions/runs/{run_id}/attempts/{run['run_attempt']}/jobs?per_page=100&page={page}")
            require(type(response) is dict and type(response.get('jobs')) is list
                    and type(response.get('total_count')) is int and response['total_count'] <= 1000, 'incomplete_ci_jobs')
            jobs.extend(response['jobs'])
            if len(jobs) == response['total_count']:
                break
        require(len(jobs) == response['total_count'] and len({j.get('id') for j in jobs}) == len(jobs), 'incomplete_ci_jobs')
        # GitHub job conclusions, not PR prose, classify infrastructure-only failure.
        transient = (run.get('conclusion') in ('failure', 'timed_out') and bool(jobs)
                     and all(j.get('conclusion') in ('success', 'skipped', 'timed_out', 'startup_failure') for j in jobs)
                     and any(j.get('conclusion') in ('timed_out', 'startup_failure') for j in jobs))
        self.current(request, head)
        value = dict(schema='pullfrog-ci-observation.v1', binding=k.binding(request, head_sha=head),
                     run_id=run_id, workflow_id=workflow, run_attempt=run['run_attempt'],
                     status=run.get('status'), conclusion=run.get('conclusion'), transient=transient)
        value['digest'] = k.digest(value)
        return value

    def review(self, request, head):
        return collector.collect(request, self.client, current_head_sha=head,
                                 trusted_pullfrog_identity=self.policy['pullfrog_identity'])

    def eligible(self, request, head, ci, published):
        actions = ['no_action', 'ask_human']
        if ci and ci['status'] != 'completed':
            return ['wait']
        if ci and ci['transient'] and ci['run_attempt'] <= self.policy.get('max_ci_retries', 0):
            actions.append('retry_ci')
        if ci and ci['conclusion'] == 'success' and published and self.review_runner is not None:
            actions.append('request_review')
        if not ci or ci['conclusion'] not in ('success', None):
            actions.append('implement_fix')
        return actions

    def execute(self, request, intent):
        """Intent must already be durable. Response is never effect proof."""
        self.current(request, intent['binding']['head_sha'])
        if intent['action'] == 'retry_ci':
            ci = self.ci(request, intent['binding']['head_sha'], intent['ci']['run_id'])
            require(ci == intent['ci'] and ci['transient']
                    and ci['run_attempt'] <= self.policy.get('max_ci_retries', 0), 'retry_not_eligible')
            self.client.post(f"/repos/{request['repository_slug']}/actions/runs/{ci['run_id']}/rerun-failed-jobs", {})
        elif intent['action'] == 'request_review':
            require(self.review_runner is not None, 'review_runner_unavailable')
            ci = self.ci(request, intent['binding']['head_sha'], intent['ci']['run_id'])
            require(ci == intent['ci'] and ci['status'] == 'completed' and ci['conclusion'] == 'success', 'review_ci_changed')
            # Host port invokes the existing pinned review-only action, not a
            # caller-selected workflow or model command. Credential lease/revoke
            # remains owned by its existing trusted host runner.
            self.review_runner(action=PULLFROG_ACTION, request=copy.deepcopy(request),
                               head_sha=intent['binding']['head_sha'], effect_id=intent['effect_id'],
                               push='disabled', shell='restricted', progress_comments='disabled')
        else:
            raise k.ContractError('unknown_fixed_action')

    def readback(self, request, intent):
        head = intent['binding']['head_sha']
        if intent['action'] == 'retry_ci':
            observed = self.ci(request, head, intent['ci']['run_id'])
            return observed if observed['run_attempt'] == intent['ci']['run_attempt'] + 1 else None
        observed = self.review(request, head)
        # App/account/exact-head evidence is independently collected; an action
        # runner's success response is never accepted as a review receipt.
        return observed if (observed.get('status') in ('clean', 'findings')
                            and observed.get('review_identity', {}).get('review_id', 0) > intent.get('prior_review_id', 0)
                            and observed.get('evidence_digest') != intent.get('prior_review_digest')) else None


class PullfrogWorkflowRunner:
    """Concrete adapter for the existing pullfrog.yml workflow_dispatch inputs.

    Serving ref must be an immutable, independently qualified trusted source SHA.
    This does not enable a workflow, provision auth or assert cost qualification.
    """
    def __init__(self, client, *, trusted_ref, trusted_sha, repository_slug, workflow_id):
        require(type(trusted_ref) is str and trusted_ref.startswith('tags/')
                and all(c.isalnum() or c in '/._-' for c in trusted_ref) and '..' not in trusted_ref
                and k._sha(trusted_sha), 'immutable_review_ref_required')
        require(repository_slug == 'fr-meyer/agent-toolkit' and type(workflow_id) is int
                and workflow_id > 0, 'review_workflow_identity_required')
        self.client, self.ref, self.sha, self.slug, self.workflow_id = client, trusted_ref, trusted_sha, repository_slug, workflow_id

    def __call__(self, *, action, request, head_sha, effect_id, push, shell, progress_comments):
        require(action == PULLFROG_ACTION and push == 'disabled' and shell == 'restricted'
                and progress_comments == 'disabled' and request['repository_slug'] == self.slug,
                'review_operation_forbidden')
        tag = self.client.get(f'/repos/{self.slug}/git/ref/{self.ref}')
        require(tag.get('object', {}).get('type') == 'commit' and tag['object'].get('sha') == self.sha, 'review_source_drift')
        workflow = self.client.get(f'/repos/{self.slug}/actions/workflows/{self.workflow_id}')
        require(workflow.get('id') == self.workflow_id and workflow.get('path') == '.github/workflows/pullfrog.yml'
                and workflow.get('state') == 'active', 'review_workflow_unavailable')
        # The fixed text comes solely from validated immutable bindings, not task
        # prose/model output. Existing workflow already pins non-pushing action.
        require(k._sha(head_sha) and k._sha(request['base_sha']) and type(request['pr_number']) is int,
                'invalid_review_binding')
        prompt = (f"Review pull request #{request['pr_number']} in {self.slug} at exact head {head_sha} "
                  f"against exact base {request['base_sha']}. Re-read live identity and stop on drift. "
                  "Review the complete diff and submit one complete Pullfrog review containing the required divider marker. "
                  "Do not modify, commit, push, approve, merge, dispatch, release, deploy, change settings, "
                  "resolve threads or delete branches.")
        return self.client.post(f'/repos/{self.slug}/actions/workflows/{self.workflow_id}/dispatches',
                                {'ref': self.ref.removeprefix('tags/'), 'inputs': {'prompt': prompt, 'name': 'standalone-review-' + effect_id}})
