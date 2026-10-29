import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / "pullfrog_review_fallback.py"
SPEC = importlib.util.spec_from_file_location("pullfrog_review_fallback", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)

BASE_SHA = "1" * 40
HEAD_SHA = "2" * 40
REPOSITORY = "fr-meyer/agent-toolkit"
REFUSAL = next(item for item in MODULE.CYBER_REFUSAL_MESSAGES if "you’re" in item)


def pr(head_sha=HEAD_SHA, base_sha=BASE_SHA, head_repo=REPOSITORY, state="open"):
    return {
        "number": 95,
        "state": state,
        "base": {
            "ref": "dev",
            "sha": base_sha,
            "repo": {"full_name": REPOSITORY},
        },
        "head": {
            "ref": "feat/pullfrog-write-capable-loop",
            "sha": head_sha,
            "repo": {"full_name": head_repo},
        },
    }


def check_run(conclusion="failure"):
    return {
        "id": 122715968993,
        "name": "pullfrog",
        "status": "completed",
        "conclusion": conclusion,
        "head_sha": HEAD_SHA,
        "details_url": "https://github.com/fr-meyer/agent-toolkit/actions/runs/40658694176",
        "app": {"slug": "pullfrog"},
        "check_suite": {"id": 500},
        "pull_requests": [
            {
                "number": 95,
                "base": {"ref": "dev", "sha": BASE_SHA},
                "head": {"ref": "feat/pullfrog-write-capable-loop", "sha": HEAD_SHA},
            }
        ],
    }


def evidence_check(name, conclusion="success", check_id=800):
    return {
        "id": check_id,
        "name": name,
        "status": "completed",
        "conclusion": conclusion,
        "head_sha": HEAD_SHA,
        "app": {"slug": "pullfrog"},
        "check_suite": {"id": 500},
    }


def job():
    return {
        "id": 122715989277,
        "name": "pullfrog",
        "status": "completed",
        "conclusion": "failure",
        "steps": [
            {
                "name": "Run review-only agent",
                "status": "completed",
                "conclusion": "failure",
            }
        ],
    }


def review(review_id=601, body="", commit_id=HEAD_SHA):
    return {
        "id": review_id,
        "commit_id": commit_id,
        "submitted_at": "2026-10-28T08:49:22Z",
        "state": "COMMENTED",
        "body": body,
        "user": {"login": "pullfrog[bot]"},
    }


def complete_body(model=MODULE.PRIMARY_RESOLVED_MODEL, clean=True):
    verdict = "> ✅ No new issues found.\n" if clean else "> One actionable finding.\n"
    return (
        verdict
        + "<!-- PULLFROG_DIVIDER_DO_NOT_REMOVE_PLZ -->\n"
        + f"<sup>Using `{model}`</sup>"
    )


def snapshot(conclusion="failure"):
    live = pr()
    return {
        "schema": MODULE.SNAPSHOT_SCHEMA,
        "repository_slug": REPOSITORY,
        "repository": {"full_name": REPOSITORY, "default_branch": "main"},
        "expected_identity": MODULE._identity(REPOSITORY, live),
        "observed_pull_request": live,
        "primary_check": check_run(conclusion),
        "primary_workflow_run": {
            "id": 40658694176,
            "path": ".github/workflows/pullfrog.yml",
            "event": "workflow_dispatch",
            "actor": {"login": "pullfrog[bot]"},
        },
        "primary_jobs": [job()],
        "primary_annotations": [
            {
                "job_id": 122715989277,
                "annotation_level": "failure",
                "message": REFUSAL,
            }
        ],
        "reviews": [review()],
        "review_comments": [
            {
                "id": 4398558244,
                "pull_request_review_id": 601,
                "commit_id": HEAD_SHA,
                "path": "scripts/example.py",
                "line": 12,
                "body": "partial finding",
                "user": {"login": "pullfrog[bot]"},
            }
        ],
        "review_threads": [],
        "check_runs": [
            evidence_check("pullfrog", conclusion, 800),
            evidence_check("pullfrog-approval", "success", 801),
        ],
    }


class PullfrogReviewFallbackDecisionTests(unittest.TestCase):
    def test_exact_policy_refusal_with_only_partial_review_authorizes_once(self):
        for message in MODULE.CYBER_REFUSAL_MESSAGES:
            with self.subTest(message=message):
                fixture = snapshot()
                fixture["primary_annotations"][0]["message"] = message
                receipt = MODULE.evaluate_snapshot(fixture)
                self.assertEqual(receipt["status"], "fallback_ready")
                self.assertTrue(receipt["authorized_fallback"])
                self.assertEqual(receipt["blockers"], [])
                self.assertEqual(receipt["primary"]["partial_review_count"], 1)
                self.assertEqual(receipt["primary"]["exact_head_comment_count"], 1)
                self.assertEqual(receipt["fallback"]["model"], "openai/gpt-astra")
                self.assertEqual(receipt["fallback"]["effort"], "xhigh")
                rendered = json.dumps(receipt)
                self.assertNotIn("cybersecurity risk", rendered)
                self.assertNotIn("partial finding", rendered)

    def test_success_requires_a_complete_exact_head_pullfrog_verdict(self):
        fixture = snapshot(conclusion="success")
        fixture["primary_jobs"] = []
        fixture["primary_annotations"] = []
        fixture["reviews"] = [review(body=complete_body())]
        fixture["review_comments"] = []
        receipt = MODULE.evaluate_snapshot(fixture)
        self.assertEqual(receipt["status"], "primary_valid")
        self.assertFalse(receipt["authorized_fallback"])
        self.assertEqual(receipt["gate"]["initial_conclusion"], "success")

    def test_success_without_complete_review_fails_closed(self):
        fixture = snapshot(conclusion="success")
        fixture["primary_jobs"] = []
        fixture["primary_annotations"] = []
        receipt = MODULE.evaluate_snapshot(fixture)
        self.assertEqual(receipt["status"], "stopped")
        self.assertIn("missing_complete_primary_verdict", receipt["blockers"])

    def test_ordinary_provider_failure_does_not_fallback(self):
        fixture = snapshot()
        fixture["primary_annotations"][0]["message"] = "action failed: rate limit"
        receipt = MODULE.evaluate_snapshot(fixture)
        self.assertEqual(receipt["status"], "stopped")
        self.assertIn("cyber_refusal_signature_mismatch", receipt["blockers"])

    def test_whitespace_variant_of_refusal_does_not_fallback(self):
        fixture = snapshot()
        fixture["primary_annotations"][0]["message"] = REFUSAL.replace(
            "This content", "This  content"
        )
        receipt = MODULE.evaluate_snapshot(fixture)
        self.assertEqual(receipt["status"], "stopped")
        self.assertIn("cyber_refusal_signature_mismatch", receipt["blockers"])

    def test_extra_failure_annotation_does_not_fallback(self):
        fixture = snapshot()
        fixture["primary_annotations"].append(
            {
                "job_id": 122715989277,
                "annotation_level": "failure",
                "message": "another failure",
            }
        )
        receipt = MODULE.evaluate_snapshot(fixture)
        self.assertEqual(receipt["status"], "stopped")
        self.assertIn("additional_primary_failure_annotation", receipt["blockers"])

    def test_additional_failed_step_does_not_fallback(self):
        fixture = snapshot()
        fixture["primary_jobs"][0]["steps"].append(
            {
                "name": "Upload diagnostics",
                "status": "completed",
                "conclusion": "failure",
            }
        )
        receipt = MODULE.evaluate_snapshot(fixture)
        self.assertEqual(receipt["status"], "stopped")
        self.assertIn("additional_primary_failed_step", receipt["blockers"])

    def test_complete_primary_verdict_blocks_fallback_even_after_refusal(self):
        fixture = snapshot()
        fixture["reviews"] = [review(body=complete_body())]
        receipt = MODULE.evaluate_snapshot(fixture)
        self.assertEqual(receipt["status"], "stopped")
        self.assertIn("complete_primary_verdict_already_exists", receipt["blockers"])

    def test_prior_exact_head_gate_blocks_duplicate_fallback(self):
        fixture = snapshot()
        external_id = MODULE._gate_external_id(REPOSITORY, 95, HEAD_SHA, BASE_SHA)
        fixture["check_runs"] = [
            {
                "id": 800,
                "name": "pullfrog-review-gate",
                "head_sha": HEAD_SHA,
                "external_id": external_id,
                "app": {"slug": "github-actions"},
            }
        ]
        receipt = MODULE.evaluate_snapshot(fixture)
        self.assertEqual(receipt["status"], "stopped")
        self.assertIn("fallback_already_attempted_for_head", receipt["blockers"])

    def test_head_base_fork_and_source_workflow_drift_fail_closed(self):
        variants = {
            "head": (lambda item: item["primary_check"].update(head_sha="3" * 40), "primary_check_head_mismatch"),
            "fork": (lambda item: item["observed_pull_request"]["head"]["repo"].update(full_name="someone/fork"), "pull_request_identity_drift"),
            "workflow": (lambda item: item["primary_workflow_run"].update(path=".github/workflows/other.yml"), "wrong_primary_workflow_path"),
        }
        for name, (mutate, blocker) in variants.items():
            with self.subTest(name=name):
                fixture = snapshot()
                mutate(fixture)
                receipt = MODULE.evaluate_snapshot(fixture)
                self.assertEqual(receipt["status"], "stopped")
                self.assertIn(blocker, receipt["blockers"])

    def test_fallback_workflow_check_is_ignored_without_recursive_gate_update(self):
        fixture = snapshot()
        fixture["primary_workflow_run"].update(
            path=MODULE.FALLBACK_WORKFLOW_PATH,
            event="check_run",
            actor={"login": "github-actions[bot]"},
        )
        receipt = MODULE.evaluate_snapshot(fixture)
        self.assertEqual(receipt["status"], "ignored_fallback_run")
        self.assertFalse(receipt["authorized_fallback"])
        self.assertEqual(receipt["blockers"], [])


class FakeClient:
    repository_slug = REPOSITORY

    def __init__(self, *, body=None, comments=None, checks=None, threads=None, pull=None):
        self.body = (
            complete_body(MODULE.FALLBACK_RESOLVED_MODEL) if body is None else body
        )
        self.comments = [] if comments is None else comments
        self.checks = [
            evidence_check("pullfrog", "success", 810),
            evidence_check("pullfrog-approval", "success", 811),
        ] if checks is None else checks
        self.threads = [] if threads is None else threads
        self.pull = pr() if pull is None else pull
        self.posts = []
        self.patches = []

    def get(self, path):
        if path == f"/repos/{REPOSITORY}/pulls/95":
            return copy.deepcopy(self.pull)
        if path == f"/repos/{REPOSITORY}/pulls/95/reviews/700":
            return review(700, self.body)
        if path == f"/repos/{REPOSITORY}/commits/{HEAD_SHA}/check-runs?per_page=100":
            return {"total_count": len(self.checks), "check_runs": copy.deepcopy(self.checks)}
        raise AssertionError(path)

    def paginated(self, path):
        if path == f"/repos/{REPOSITORY}/pulls/95/reviews":
            return [review(700, self.body)]
        if path == f"/repos/{REPOSITORY}/pulls/95/comments":
            return copy.deepcopy(self.comments)
        raise AssertionError(path)

    def graphql(self, query, variables):
        if "resolveReviewThread" in query:
            for item in self.threads:
                if item.get("id") == variables.get("threadId"):
                    item["isResolved"] = True
                    return {
                        "data": {
                            "resolveReviewThread": {
                                "thread": {
                                    "id": item["id"],
                                    "isResolved": True,
                                }
                            }
                        }
                    }
            raise AssertionError(variables)
        return {
            "data": {
                "repository": {
                    "pullRequest": {
                        "reviewThreads": {
                            "nodes": copy.deepcopy(self.threads),
                            "pageInfo": {"hasNextPage": False, "endCursor": None},
                        }
                    }
                }
            }
        }

    def post(self, path, payload):
        self.posts.append((path, payload))
        return {"id": 900}

    def patch(self, path, payload):
        self.patches.append((path, payload))
        return {"id": 901}


class PullfrogReviewFallbackResultTests(unittest.TestCase):
    def coordinator(self):
        return MODULE.evaluate_snapshot(snapshot())

    def result(self, verdict="clean", count=0):
        return {
            "schema": MODULE.RESULT_SCHEMA,
            "status": "review_submitted",
            "repository": REPOSITORY,
            "pr_number": 95,
            "base_sha": BASE_SHA,
            "head_sha": HEAD_SHA,
            "model": MODULE.FALLBACK_MODEL,
            "effort": MODULE.EFFORT,
            "review_id": 700,
            "verdict": verdict,
            "finding_count": count,
        }

    def token_lease(self):
        return {
            "schema": MODULE.TOKEN_LEASE_SCHEMA,
            "status": "active",
            "repository": REPOSITORY,
            "permissions": MODULE.REVIEW_TOKEN_PERMISSIONS,
            "expires_at": "2026-10-29T06:00:00Z",
            "actor": "pullfrog[bot]",
            "raw_token_included": False,
        }

    def token_revocation(self):
        return {
            "schema": MODULE.TOKEN_REVOCATION_SCHEMA,
            "status": "revoked",
            "repository": REPOSITORY,
            "raw_token_included": False,
        }

    def verify(self, client, outcome, result, *, lease=None, revocation=None, revocation_outcome="success"):
        return MODULE.verify_fallback_result(
            client,
            self.coordinator(),
            outcome,
            result,
            lease or self.token_lease(),
            revocation or self.token_revocation(),
            revocation_outcome,
        )

    def test_valid_structured_astra_clean_verdict_is_accepted(self):
        receipt = self.verify(FakeClient(), "success", self.result())
        self.assertEqual(receipt["status"], "valid")
        self.assertEqual(receipt["blockers"], [])
        self.assertEqual(receipt["model"], "openai/gpt-astra")

    def test_wrong_model_or_failed_action_is_rejected(self):
        result = self.result()
        result["model"] = "openai/gpt-sol"
        receipt = self.verify(FakeClient(), "failure", result)
        self.assertEqual(receipt["status"], "invalid")
        self.assertIn("fallback_action_failed", receipt["blockers"])
        self.assertIn("fallback_result_model_mismatch", receipt["blockers"])

    def test_findings_require_matching_exact_review_comment_count(self):
        comments = [
            {
                "id": 1,
                "pull_request_review_id": 700,
                "commit_id": HEAD_SHA,
                "user": {"login": "pullfrog[bot]"},
            }
        ]
        receipt = self.verify(
            FakeClient(body=complete_body(MODULE.FALLBACK_RESOLVED_MODEL, clean=False), comments=comments),
            "success",
            self.result("findings", 2),
        )
        self.assertEqual(receipt["status"], "invalid")
        self.assertIn("fallback_finding_count_mismatch", receipt["blockers"])

    def test_clean_verdict_rejects_comments(self):
        comments = [
            {
                "id": 1,
                "pull_request_review_id": 700,
                "commit_id": HEAD_SHA,
                "user": {"login": "pullfrog[bot]"},
            }
        ]
        receipt = self.verify(FakeClient(comments=comments), "success", self.result())
        self.assertEqual(receipt["status"], "invalid")
        self.assertIn("fallback_finding_count_mismatch", receipt["blockers"])

    def test_finding_comments_must_match_exact_head_and_actor(self):
        comments = [
            {
                "id": 1,
                "pull_request_review_id": 700,
                "commit_id": "3" * 40,
                "user": {"login": "someone-else"},
            }
        ]
        receipt = self.verify(
            FakeClient(body=complete_body(MODULE.FALLBACK_RESOLVED_MODEL, clean=False), comments=comments),
            "success",
            self.result("findings", 1),
        )
        self.assertEqual(receipt["status"], "invalid")
        self.assertIn("invalid_exact_head_fallback_comment", receipt["blockers"])

    def test_token_scope_and_revocation_are_required_for_a_valid_verdict(self):
        lease = self.token_lease()
        lease["permissions"] = {
            "contents": "write",
            "pull_requests": "write",
            "checks": "write",
        }
        receipt = self.verify(
            FakeClient(),
            "success",
            self.result(),
            lease=lease,
            revocation_outcome="failure",
        )
        self.assertEqual(receipt["status"], "invalid")
        self.assertIn("invalid_review_token_lease_permissions", receipt["blockers"])
        self.assertIn("review_token_revocation_failed", receipt["blockers"])

    def test_gate_is_created_then_updated_by_stable_external_id(self):
        coordinator = self.coordinator()
        client = FakeClient()
        created = MODULE.publish_gate(client, coordinator, "https://example.test/run", True, None)
        self.assertEqual(created["operation"], "created")
        self.assertEqual(client.posts[0][1]["status"], "in_progress")
        external_id = coordinator["gate"]["external_id"]

        client = FakeClient(
            checks=[
                {
                    "id": 900,
                    "name": MODULE.GATE_CHECK_NAME,
                    "head_sha": HEAD_SHA,
                    "external_id": external_id,
                    "app": {"slug": MODULE.GATE_APP},
                }
            ]
        )
        result_receipt = MODULE.verify_fallback_result(
            FakeClient(),
            coordinator,
            "success",
            self.result(),
            self.token_lease(),
            self.token_revocation(),
            "success",
        )
        updated = MODULE.publish_gate(
            client, coordinator, "https://example.test/run", True, result_receipt
        )
        self.assertEqual(updated["operation"], "updated")
        self.assertEqual(updated["conclusion"], "success")
        self.assertEqual(client.patches[0][0], f"/repos/{REPOSITORY}/check-runs/900")


class PullfrogExactHeadRereviewTests(unittest.TestCase):
    def result(self):
        return {
            "schema": MODULE.REREVIEW_RESULT_SCHEMA,
            "status": "review_submitted",
            "repository": REPOSITORY,
            "pr_number": 95,
            "base_sha": BASE_SHA,
            "head_sha": HEAD_SHA,
            "model": MODULE.PRIMARY_MODEL,
            "effort": MODULE.EFFORT,
            "review_id": 700,
            "verdict": "clean",
            "finding_count": 0,
        }

    def token_lease(self):
        return {
            "schema": MODULE.TOKEN_LEASE_SCHEMA,
            "status": "active",
            "repository": REPOSITORY,
            "permissions": MODULE.REVIEW_TOKEN_PERMISSIONS,
            "expires_at": "2026-10-29T06:00:00Z",
            "actor": "pullfrog[bot]",
            "raw_token_included": False,
        }

    def token_revocation(self):
        return {
            "schema": MODULE.TOKEN_REVOCATION_SCHEMA,
            "status": "revoked",
            "repository": REPOSITORY,
            "raw_token_included": False,
        }

    def verify(self, client):
        return MODULE.verify_exact_head_rereview_result(
            client,
            95,
            HEAD_SHA,
            BASE_SHA,
            "success",
            self.result(),
            self.token_lease(),
            self.token_revocation(),
            "success",
        )

    def test_clean_sol_rereview_and_exact_head_contract_are_valid(self):
        client = FakeClient(body=complete_body(MODULE.PRIMARY_RESOLVED_MODEL))
        receipt = self.verify(client)
        self.assertEqual(receipt["status"], "valid")
        self.assertEqual(receipt["review_contract_status"], "clean")
        self.assertEqual(receipt["blockers"], [])

        publication = MODULE.publish_rereview_gate(
            client,
            MODULE.reconcile_rereview_threads(client, receipt),
            "https://example.test/run",
        )
        self.assertEqual(publication["conclusion"], "success")
        self.assertEqual(
            publication["external_id"],
            MODULE.review_contract.gate_external_id(
                {
                    "repository_slug": REPOSITORY,
                    "pr_number": 95,
                    "base_sha": BASE_SHA,
                    "head_sha": HEAD_SHA,
                }
            ),
        )

    def test_empty_or_markerless_rereview_fails_closed(self):
        for body in ("", "> ✅ No new issues found.\n<sup>Using `gpt-6.1-sol`</sup>"):
            with self.subTest(body=body):
                receipt = self.verify(FakeClient(body=body))
                self.assertEqual(receipt["status"], "invalid")
                self.assertIn("invalid_exact_head_rereview", receipt["blockers"])

    def test_missing_checks_and_identity_drift_fail_closed(self):
        variants = (
            FakeClient(
                body=complete_body(MODULE.PRIMARY_RESOLVED_MODEL), checks=[]
            ),
            FakeClient(
                body=complete_body(MODULE.PRIMARY_RESOLVED_MODEL),
                pull=pr(head_sha="3" * 40),
            ),
        )
        for client in variants:
            with self.subTest(client=client):
                receipt = self.verify(client)
                self.assertEqual(receipt["status"], "invalid")

    def test_old_pullfrog_threads_are_reconciled_by_isolated_clean_step(self):
        unresolved = {
            "id": "PRRT_old_pullfrog_thread",
            "isResolved": False,
            "path": "scripts/example.py",
            "line": 12,
            "comments": {
                "nodes": [
                    {
                        "author": {"login": "pullfrog[bot]"},
                        "pullRequestReview": {"databaseId": 601},
                    }
                ]
            },
        }
        client = FakeClient(
            body=complete_body(MODULE.PRIMARY_RESOLVED_MODEL),
            threads=[unresolved],
        )
        receipt = self.verify(client)
        self.assertEqual(receipt["status"], "valid")
        self.assertEqual(receipt["review_contract_status"], "reconciliation_required")

        reconciliation = MODULE.reconcile_rereview_threads(client, receipt)
        self.assertEqual(reconciliation["status"], "clean")
        self.assertEqual(reconciliation["resolved_thread_count"], 1)
        self.assertEqual(reconciliation["after_contract_status"], "clean")
        self.assertTrue(client.threads[0]["isResolved"])

    def test_gate_never_succeeds_from_incomplete_reconciliation_evidence(self):
        client = FakeClient(body=complete_body(MODULE.PRIMARY_RESOLVED_MODEL))
        receipt = self.verify(client)
        reconciliation = MODULE.reconcile_rereview_threads(client, receipt)
        for field, value in (
            ("after_contract_status", "reconciliation_required"),
            ("after_contract_digest", ""),
            ("raw_text_included", True),
        ):
            with self.subTest(field=field):
                changed = copy.deepcopy(reconciliation)
                changed[field] = value
                if field == "raw_text_included":
                    with self.assertRaises(MODULE.FallbackError):
                        MODULE.publish_rereview_gate(
                            client, changed, "https://example.test/run"
                        )
                else:
                    publication = MODULE.publish_rereview_gate(
                        client, changed, "https://example.test/run"
                    )
                    self.assertEqual(publication["conclusion"], "failure")

    def test_reconciliation_rejects_current_review_or_non_pullfrog_thread(self):
        current = {
            "id": "PRRT_current_rereview_thread",
            "isResolved": False,
            "path": "scripts/example.py",
            "line": 12,
            "comments": {
                "nodes": [
                    {
                        "author": {"login": "pullfrog[bot]"},
                        "pullRequestReview": {"databaseId": 700},
                    }
                ]
            },
        }
        client = FakeClient(
            body=complete_body(MODULE.PRIMARY_RESOLVED_MODEL),
            threads=[current],
        )
        receipt = self.verify(client)
        self.assertEqual(receipt["status"], "valid")
        reconciliation = MODULE.reconcile_rereview_threads(client, receipt)
        self.assertEqual(reconciliation["status"], "invalid")
        self.assertIn(
            "current_rereview_thread_not_reconcilable",
            reconciliation["blockers"],
        )
        self.assertFalse(client.threads[0]["isResolved"])

        human = copy.deepcopy(current)
        human["id"] = "PRRT_human_thread"
        human["comments"]["nodes"][0]["author"]["login"] = "human-reviewer"
        client = FakeClient(
            body=complete_body(MODULE.PRIMARY_RESOLVED_MODEL),
            threads=[human],
        )
        receipt = self.verify(client)
        reconciliation = MODULE.reconcile_rereview_threads(client, receipt)
        self.assertEqual(reconciliation["status"], "clean")
        self.assertEqual(reconciliation["resolved_thread_count"], 0)
        self.assertFalse(client.threads[0]["isResolved"])


class FakeHttpResponse:
    def __init__(self, value=None, *, status=200):
        self.value = value
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self, limit=-1):
        if self.value is None:
            return b""
        return json.dumps(self.value).encode("utf-8")


class PullfrogReviewFallbackCredentialTests(unittest.TestCase):
    def test_mint_uses_exact_review_only_pullfrog_app_scope(self):
        installation_token = "ghs_" + "a" * 40
        responses = [
            FakeHttpResponse({"value": "oidc-token-value"}),
            FakeHttpResponse(
                {
                    "token": installation_token,
                    "expires_at": "2026-10-29T06:00:00Z",
                }
            ),
        ]
        with mock.patch.object(MODULE.urllib.request, "urlopen", side_effect=responses) as opened:
            token, receipt = MODULE.mint_review_token(
                "https://oidc.actions.githubusercontent.com/token?api-version=2.0",
                "runner",
                REPOSITORY,
            )

        self.assertEqual(token, installation_token)
        self.assertEqual(receipt["permissions"], {"contents": "read", "pull_requests": "write"})
        self.assertEqual(receipt["actor"], "pullfrog[bot]")
        self.assertFalse(receipt["raw_token_included"])
        self.assertNotIn(installation_token, json.dumps(receipt))

        oidc_request = opened.call_args_list[0].args[0]
        self.assertIn("audience=pullfrog-api", oidc_request.full_url)
        self.assertEqual(oidc_request.get_header("Authorization"), "Bearer runner")

        token_request = opened.call_args_list[1].args[0]
        self.assertEqual(token_request.get_method(), "POST")
        self.assertEqual(
            token_request.full_url,
            "https://pullfrog.com/api/github/installation-token?repos=agent-toolkit",
        )
        self.assertEqual(
            json.loads(token_request.data.decode("utf-8")),
            {"permissions": {"contents": "read", "pull_requests": "write"}},
        )
        serialized = token_request.data.decode("utf-8")
        self.assertNotIn("checks", serialized)
        self.assertNotIn("actions", serialized)
        self.assertNotIn('"contents":"write"', serialized)

    def test_revoke_uses_the_installation_token_it_disposes(self):
        installation_token = "ghs_" + "b" * 40
        with mock.patch.object(
            MODULE.urllib.request,
            "urlopen",
            return_value=FakeHttpResponse(status=204),
        ) as opened:
            receipt = MODULE.revoke_review_token(
                "https://api.github.com",
                installation_token,
                REPOSITORY,
            )
        request = opened.call_args.args[0]
        self.assertEqual(request.get_method(), "DELETE")
        self.assertEqual(request.full_url, "https://api.github.com/installation/token")
        self.assertEqual(request.get_header("Authorization"), f"Bearer {installation_token}")
        self.assertEqual(receipt["status"], "revoked")
        self.assertNotIn(installation_token, json.dumps(receipt))

    def test_provider_preflight_rejects_every_rerun_attempt(self):
        with self.assertRaises(MODULE.FallbackError) as error:
            MODULE.verify_live_identity(FakeClient(), 95, HEAD_SHA, BASE_SHA, 2)
        self.assertEqual(error.exception.code, "fallback_run_attempt_consumed")


class PullfrogReviewFallbackInputTests(unittest.TestCase):
    def test_json_and_outcome_inputs_are_size_bounded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            json_path = root / "result.json"
            outcome_path = root / "outcome.txt"
            json_path.write_text('{"padding":"xxxxxxxx"}', encoding="utf-8")
            outcome_path.write_text("x" * 32, encoding="utf-8")
            old_json_limit = MODULE.MAX_RESPONSE_BYTES
            old_outcome_limit = MODULE.MAX_OUTCOME_BYTES
            try:
                MODULE.MAX_RESPONSE_BYTES = 8
                MODULE.MAX_OUTCOME_BYTES = 8
                with self.assertRaises(MODULE.FallbackError) as json_error:
                    MODULE._load_object(json_path)
                self.assertEqual(json_error.exception.code, "invalid_json_file")
                with self.assertRaises(MODULE.FallbackError) as outcome_error:
                    MODULE._load_outcome(outcome_path)
                self.assertEqual(outcome_error.exception.code, "invalid_outcome_file")
            finally:
                MODULE.MAX_RESPONSE_BYTES = old_json_limit
                MODULE.MAX_OUTCOME_BYTES = old_outcome_limit


if __name__ == "__main__":
    unittest.main()
