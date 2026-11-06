"""Offline trusted-run/artifact/head-check binding tests; no GitHub writes."""
import copy
import datetime
import hashlib
import importlib.util
import io
import json
import subprocess
import unittest
import zipfile
from pathlib import Path
from unittest import mock

SOURCE = Path(__file__).resolve().parents[1] / "pullfrog_speculoos_attestation.py"
spec = importlib.util.spec_from_file_location("speculoos_attestation", SOURCE)
assert spec and spec.loader
A = importlib.util.module_from_spec(spec)
spec.loader.exec_module(A)

HEAD, BASE, SOURCE_SHA = "a" * 40, "b" * 40, "c" * 40
NOW = datetime.datetime(2026, 11, 6, 12, 0, tzinfo=datetime.timezone.utc)


def time_at(seconds):
    return (NOW + datetime.timedelta(seconds=seconds)).isoformat()


def zipped(report_raw, attestation_raw):
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("contract.json", report_raw)
        archive.writestr("attestation.json", attestation_raw)
    return out.getvalue()


class BindingTest(unittest.TestCase):
    def setUp(self):
        self.signed_source = mock.patch.object(A, "verify_signed_source")
        self.signed_source.start()
        self.addCleanup(self.signed_source.stop)
        self.report = {"schema": "agent-toolkit-speculoos-pr-contract/v1", "status": "ok",
                       "repository": A.REPO, "task": "public-canary", "task_source": "per-pr",
                       "head_ref": "test/public-canary", "head_sha": HEAD,
                       "base_ref": "dev", "base_sha": BASE,
                       "checks": [{"name": name, "status": "passed"} for name in sorted(A.REQUIRED_CHECKS)],
                       "blockers": []}
        self.report_raw = A._canonical(self.report) + b"\n"
        self.attestation = A.produce(self.report_raw, repository_id=42, pr_number=106,
                                     head_ref="test/public-canary", head_sha=HEAD,
                                     base_ref="dev", base_sha=BASE, source_sha=SOURCE_SHA,
                                     run_id=111, run_attempt=1)
        self.raw = zipped(self.report_raw, A._canonical(self.attestation) + b"\n")
        self.artifact = {"id": 222, "name": "speculoos-pr-106-" + HEAD + "-111-1",
                         "expired": False, "digest": "sha256:" + hashlib.sha256(self.raw).hexdigest(),
                         "expires_at": time_at(3600),
                         "workflow_run": {"id": 111, "repository_id": 42,
                                          "head_repository_id": 42,
                                          "head_branch": "test/public-canary",
                                          "head_sha": HEAD}}
        self.run = {"id": 111, "run_attempt": 1, "event": "pull_request_target",
                    "path": A.WORKFLOW_PATH, "head_sha": HEAD,
                    "head_branch": "test/public-canary",
                    "status": "completed", "conclusion": "success",
                    "created_at": time_at(-120), "run_started_at": time_at(-120),
                    "updated_at": time_at(-60),
                    "repository": {"id": 42, "full_name": A.REPO}}
        self.pr = {"number": 106, "state": "open",
                   "head": {"ref": "test/public-canary", "sha": HEAD, "repo": {"id": 42}},
                   "base": {"ref": "dev", "sha": BASE, "repo": {"id": 42}}}
        self.check = {"id": 333, "name": A.CHECK_NAME, "head_sha": HEAD,
                      "status": "completed", "conclusion": "success",
                      "external_id": "speculoos:v1:" + self.attestation["binding_digest"],
                      "app": {"id": 444}}

    def verify(self, **changes):
        values = dict(raw=self.raw, artifact=self.artifact, run=self.run, check=self.check,
                      pr=self.pr, repository_id=42, trusted_app_id=444,
                      expected_source_sha=SOURCE_SHA, now=NOW.timestamp())
        values.update(changes)
        return A.verify_archive(**values)

    def test_clean_exact_revision_binding(self):
        result = self.verify()
        self.assertEqual(result["status"], "verified")
        self.assertEqual(result["head_sha"], HEAD)
        self.assertEqual(result["source_sha"], SOURCE_SHA)
        self.assertNotEqual(self.run["head_sha"], result["source_sha"])

    def test_source_sha_remains_independently_pinned(self):
        with self.assertRaisesRegex(A.EvidenceError, "attestation_binding_invalid"):
            self.verify(expected_source_sha=HEAD)

    def test_unverified_signature_blocks_head_check_intent(self):
        self.signed_source.stop()
        with mock.patch.object(A, "verify_signed_source",
                               side_effect=A.EvidenceError("signed_source_unverified")) as verify:
            with self.assertRaisesRegex(A.EvidenceError, "signed_source_unverified"):
                A.prepare_head_check_intent(self.raw, artifact=self.artifact, run=self.run,
                                            pr=self.pr, repository_id=42,
                                            expected_source_sha=SOURCE_SHA, now=NOW.timestamp())
            verify.assert_called_once()
            self.assertEqual(verify.call_args.kwargs["source_sha"], SOURCE_SHA)
            self.assertEqual(verify.call_args.kwargs["run_id"], 111)
        self.signed_source.start()

    def test_workflow_path_accepts_main_suffix_only(self):
        self.assertEqual(self.verify(run=dict(self.run, path=A.WORKFLOW_PATH + "@main"))["status"],
                         "verified")
        with self.assertRaisesRegex(A.EvidenceError, "workflow_run_untrusted"):
            self.verify(run=dict(self.run, path=A.WORKFLOW_PATH + "@dev"))

    def test_publisher_intent_requires_verified_source_bundle(self):
        intent = A.prepare_head_check_intent(self.raw, artifact=self.artifact, run=self.run,
                                             pr=self.pr, repository_id=42,
                                             expected_source_sha=SOURCE_SHA, now=NOW.timestamp())
        self.assertEqual(intent["head_sha"], HEAD)
        self.assertEqual(intent["external_id"], self.check["external_id"])
        with self.assertRaisesRegex(A.EvidenceError, "live_pr_revision_drift"):
            A.prepare_head_check_intent(self.raw, artifact=self.artifact, run=self.run,
                                        pr=dict(self.pr, number=999), repository_id=42,
                                        expected_source_sha=SOURCE_SHA, now=NOW.timestamp())

    def test_contract_must_be_clean_per_pr(self):
        for field, value in (("status", "blocked"), ("task_source", "manifest")):
            report = dict(self.report, **{field: value})
            with self.assertRaises(A.EvidenceError):
                A.produce(A._canonical(report), repository_id=42, pr_number=106,
                          head_ref="test/public-canary", head_sha=HEAD, base_ref="dev",
                          base_sha=BASE, source_sha=SOURCE_SHA, run_id=111, run_attempt=1)
        report = dict(self.report, checks=self.report["checks"][:-1])
        with self.assertRaisesRegex(A.EvidenceError, "speculoos_contract_not_clean"):
            A.produce(A._canonical(report), repository_id=42, pr_number=106,
                      head_ref="test/public-canary", head_sha=HEAD,
                      base_ref="dev", base_sha=BASE, source_sha=SOURCE_SHA,
                      run_id=111, run_attempt=1)

    def test_producer_rejects_revision_mismatch(self):
        with self.assertRaisesRegex(A.EvidenceError, "contract_revision_mismatch"):
            A.produce(self.report_raw, repository_id=42, pr_number=106,
                      head_ref="test/public-canary", head_sha="d" * 40,
                      base_ref="dev", base_sha=BASE, source_sha=SOURCE_SHA,
                      run_id=111, run_attempt=1)

    def test_stale_or_wrong_live_pr_fails(self):
        for section, field, value in (("head", "sha", "d" * 40), ("base", "sha", "d" * 40),
                                      ("head", "ref", "test/other"), ("head", "repo", {"id": 99})):
            pr = copy.deepcopy(self.pr)
            pr[section][field] = value
            with self.assertRaisesRegex(A.EvidenceError, "live_pr_revision_drift"):
                self.verify(pr=pr)

    def test_wrong_run_source_attempt_or_event_fails(self):
        for field, value in (("head_sha", "d" * 40),
                             ("head_branch", "main"), ("run_attempt", 2),
                             ("event", "pull_request"), ("path", "other.yml"),
                             ("conclusion", "failure")):
            run = dict(self.run, **{field: value})
            with self.assertRaisesRegex(A.EvidenceError, "workflow_run_untrusted"):
                self.verify(run=run)

    def test_run_must_be_recent(self):
        run = dict(self.run, updated_at=time_at(-7200))
        with self.assertRaisesRegex(A.EvidenceError, "workflow_run_stale"):
            self.verify(run=run)

    def test_signature_verification_time_cannot_cross_freshness_or_expiry(self):
        with mock.patch.object(A.time, "monotonic", side_effect=[0.0, 3601.0]):
            with self.assertRaisesRegex(A.EvidenceError, "workflow_run_stale"):
                self.verify()
        with mock.patch.object(A.time, "monotonic", side_effect=[0.0, 20.0]):
            with self.assertRaisesRegex(A.EvidenceError, "artifact_expired"):
                self.verify(artifact=dict(self.artifact, expires_at=time_at(10)))

    def test_old_run_recent_second_attempt_uses_attempt_start(self):
        run = dict(self.run, created_at=time_at(-86400), run_started_at=time_at(-120),
                   run_attempt=2)
        report = self.report_raw
        attestation = A.produce(report, repository_id=42, pr_number=106,
                                head_ref="test/public-canary", head_sha=HEAD,
                                base_ref="dev", base_sha=BASE, source_sha=SOURCE_SHA,
                                run_id=111, run_attempt=2)
        raw = zipped(report, A._canonical(attestation) + b"\n")
        artifact = dict(self.artifact,
                        name="speculoos-pr-106-" + HEAD + "-111-2",
                        digest="sha256:" + hashlib.sha256(raw).hexdigest())
        check = dict(self.check, external_id="speculoos:v1:" + attestation["binding_digest"])
        self.assertEqual(self.verify(run=run, raw=raw, artifact=artifact, check=check)["status"],
                         "verified")
        with self.assertRaisesRegex(A.EvidenceError, "workflow_run_stale"):
            self.verify(run=dict(run, run_started_at=time_at(-86500)), raw=raw,
                        artifact=artifact, check=check)

    def test_artifact_digest_or_provenance_fails(self):
        for field, value in (("digest", "sha256:" + "0" * 64), ("expired", True),
                             ("name", "wrong")):
            artifact = dict(self.artifact, **{field: value})
            with self.assertRaisesRegex(A.EvidenceError, "artifact_provenance_invalid"):
                self.verify(artifact=artifact)

    def test_absolute_artifact_expiry_and_attempt_name_fail_closed(self):
        with self.assertRaisesRegex(A.EvidenceError, "artifact_expired"):
            self.verify(artifact=dict(self.artifact, expires_at=time_at(-1)))
        with self.assertRaisesRegex(A.EvidenceError, "artifact_provenance_invalid"):
            self.verify(artifact=dict(self.artifact, name="speculoos-pr-106-" + HEAD + "-111-2"))
        with self.assertRaisesRegex(A.EvidenceError, "artifact_provenance_invalid"):
            self.verify(artifact=dict(self.artifact, expires_at=time_at(3600), name="speculoos-pr-106-" + HEAD))

    def test_check_must_be_head_bound_from_trusted_app(self):
        for field, value in (("head_sha", SOURCE_SHA), ("external_id", "wrong"),
                             ("conclusion", "failure"), ("app", {"id": 555})):
            check = dict(self.check, **{field: value})
            with self.assertRaisesRegex(A.EvidenceError, "trusted_head_check_missing"):
                self.verify(check=check)

    def test_attestation_report_substitution_fails(self):
        report = dict(self.report, task="other")
        raw = zipped(A._canonical(report), A._canonical(self.attestation))
        artifact = dict(self.artifact, digest="sha256:" + hashlib.sha256(raw).hexdigest())
        with self.assertRaisesRegex(A.EvidenceError, "attestation_binding_invalid"):
            self.verify(raw=raw, artifact=artifact)

    def test_duplicate_json_or_extra_member_fails(self):
        raw = zipped(b'{"schema":"x","schema":"y"}', A._canonical(self.attestation))
        artifact = dict(self.artifact, digest="sha256:" + hashlib.sha256(raw).hexdigest())
        with self.assertRaises(A.EvidenceError):
            self.verify(raw=raw, artifact=artifact)
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w") as archive:
            archive.writestr("contract.json", self.report_raw)
            archive.writestr("attestation.json", A._canonical(self.attestation))
            archive.writestr("extra.json", b"{}")
        raw = out.getvalue()
        artifact = dict(self.artifact, digest="sha256:" + hashlib.sha256(raw).hexdigest())
        with self.assertRaisesRegex(A.EvidenceError, "artifact_members_invalid"):
            self.verify(raw=raw, artifact=artifact)

    def test_workflow_contains_only_trusted_producer(self):
        path = SOURCE.parents[2] / "templates/starter-workflows/speculoos-trusted-canary.yml"
        workflow = path.read_text()
        self.assertIn("pull_request_target:", workflow)
        self.assertIn("startsWith(github.event.pull_request.head.ref, 'test/speculoos-shadow-')", workflow)
        self.assertIn("python -I trusted/scripts/github/pullfrog_speculoos_attestation.py", workflow)
        self.assertIn("--source-sha \"$SOURCE_SHA\"", workflow)
        self.assertIn("--run-attempt \"$GITHUB_RUN_ATTEMPT\"", workflow)
        self.assertIn("speculoos-shadow-${{ github.repository_id }}", workflow)
        self.assertIn("-${{ github.run_id }}-${{ github.run_attempt }}", workflow)
        self.assertIn("id-token: write", workflow)
        self.assertIn("attestations: write", workflow)
        self.assertIn("uses: actions/attest@1e69f48acb82d1966a394da916b4c1698aa569d6", workflow)
        self.assertIn("subject-path: artifacts/speculoos/attestation.json", workflow)
        validator, signer = workflow.split("  sign:\n", 1)
        self.assertNotIn("id-token: write", validator)
        self.assertNotIn("attestations: write", validator)
        self.assertIn("needs: speculoos", signer)
        self.assertIn("uses: actions/download-artifact@d3f86a106a0bac45b974a628896c90dbdf5c8093", signer)
        self.assertNotIn("actions/checkout", signer)
        self.assertNotIn("candidate", signer)
        self.assertNotIn("scripts/github/validate_pullfrog_workflow.sh", workflow)

    def test_collector_binds_existing_server_objects_and_rereads_pr(self):
        parent = self
        prefix = "/repos/" + A.REPO
        paths = {f"{prefix}/actions/runs/111": self.run,
                 f"{prefix}/actions/artifacts/222": self.artifact,
                 f"{prefix}/commits/{HEAD}/check-runs?per_page=100":
                     {"total_count": 1, "check_runs": [self.check]}}
        class Client:
            def __init__(self):
                self.pr_reads = 0
            def get(self, path):
                if path == f"{prefix}/pulls/106":
                    self.pr_reads += 1
                    return copy.deepcopy(parent.pr)
                return copy.deepcopy(paths[path])
        client = Client()
        receipt = A.collect_verified(client, lambda artifact_id: self.raw,
                                     pr_number=106, run_id=111, artifact_id=222,
                                     repository_id=42, trusted_app_id=444,
                                     expected_source_sha=SOURCE_SHA, now=NOW.timestamp())
        self.assertEqual(receipt["binding_digest"], self.attestation["binding_digest"])
        self.assertEqual(client.pr_reads, 3)
        paths[f"{prefix}/commits/{HEAD}/check-runs?per_page=100"] = {
            "total_count": 2, "check_runs": [self.check]}
        with self.assertRaisesRegex(A.EvidenceError, "head_check_collection_incomplete"):
            A.collect_verified(client, lambda _: self.raw, pr_number=106, run_id=111,
                               artifact_id=222, repository_id=42, trusted_app_id=444,
                               expected_source_sha=SOURCE_SHA, now=NOW.timestamp())

    def test_collector_detects_changed_check_after_final_pr_read(self):
        parent = self
        prefix = "/repos/" + A.REPO
        class Client:
            def __init__(self):
                self.pr_reads = 0
            def get(self, path):
                if path == f"{prefix}/pulls/106":
                    self.pr_reads += 1
                    return copy.deepcopy(parent.pr)
                if path == f"{prefix}/actions/runs/111":
                    return copy.deepcopy(parent.run)
                if path == f"{prefix}/actions/artifacts/222":
                    return copy.deepcopy(parent.artifact)
                if path == f"{prefix}/commits/{HEAD}/check-runs?per_page=100":
                    checks = [parent.check]
                    if self.pr_reads > 1:
                        checks.append(dict(parent.check, id=334, conclusion="failure"))
                    return {"total_count": len(checks), "check_runs": copy.deepcopy(checks)}
                raise AssertionError(path)
        with self.assertRaisesRegex(A.EvidenceError, "evidence_changed_during_collection"):
            A.collect_verified(Client(), lambda _: self.raw, pr_number=106, run_id=111,
                               artifact_id=222, repository_id=42, trusted_app_id=444,
                               expected_source_sha=SOURCE_SHA, now=NOW.timestamp())

    def test_collector_resamples_freshness_after_slow_reads(self):
        parent = self
        prefix = "/repos/" + A.REPO
        parent.artifact["expires_at"] = time_at(7200)
        class Client:
            def get(self, path):
                if path == f"{prefix}/pulls/106": return copy.deepcopy(parent.pr)
                if path == f"{prefix}/actions/runs/111": return copy.deepcopy(parent.run)
                if path == f"{prefix}/actions/artifacts/222": return copy.deepcopy(parent.artifact)
                if path == f"{prefix}/commits/{HEAD}/check-runs?per_page=100":
                    return {"total_count": 1, "check_runs": [copy.deepcopy(parent.check)]}
                raise AssertionError(path)
        with mock.patch.object(A.time, "monotonic",
                               side_effect=[0.0, 0.0, 0.0, 3601.0, 3601.0]):
            with self.assertRaisesRegex(A.EvidenceError, "workflow_run_stale"):
                A.collect_verified(Client(), lambda _: self.raw, pr_number=106, run_id=111,
                                   artifact_id=222, repository_id=42, trusted_app_id=444,
                                   expected_source_sha=SOURCE_SHA, now=NOW.timestamp())

    def test_collector_rechecks_pr_after_final_check_read(self):
        parent = self
        prefix = "/repos/" + A.REPO
        class Client:
            def __init__(self):
                self.pr_reads = 0
            def get(self, path):
                if path == f"{prefix}/pulls/106":
                    self.pr_reads += 1
                    pr = copy.deepcopy(parent.pr)
                    if self.pr_reads == 3:
                        pr["head"]["sha"] = "d" * 40
                    return pr
                if path == f"{prefix}/actions/runs/111": return copy.deepcopy(parent.run)
                if path == f"{prefix}/actions/artifacts/222": return copy.deepcopy(parent.artifact)
                if path == f"{prefix}/commits/{HEAD}/check-runs?per_page=100":
                    return {"total_count": 1, "check_runs": [copy.deepcopy(parent.check)]}
                raise AssertionError(path)
        with self.assertRaisesRegex(A.EvidenceError, "live_pr_changed_during_evidence_collection"):
            A.collect_verified(Client(), lambda _: self.raw, pr_number=106, run_id=111,
                               artifact_id=222, repository_id=42, trusted_app_id=444,
                               expected_source_sha=SOURCE_SHA, now=NOW.timestamp())

    def test_collector_does_not_reopen_server_race_after_final_read(self):
        parent = self
        prefix = "/repos/" + A.REPO
        class Client:
            def get(self, path):
                if path == f"{prefix}/pulls/106": return copy.deepcopy(parent.pr)
                if path == f"{prefix}/actions/runs/111": return copy.deepcopy(parent.run)
                if path == f"{prefix}/actions/artifacts/222": return copy.deepcopy(parent.artifact)
                if path == f"{prefix}/commits/{HEAD}/check-runs?per_page=100":
                    return {"total_count": 1, "check_runs": [copy.deepcopy(parent.check)]}
                raise AssertionError(path)
        with mock.patch.object(A, "verify_signed_source") as signed:
            receipt = A.collect_verified(Client(), lambda _: self.raw, pr_number=106,
                                         run_id=111, artifact_id=222, repository_id=42,
                                         trusted_app_id=444, expected_source_sha=SOURCE_SHA,
                                         now=NOW.timestamp())
        self.assertEqual(receipt["status"], "verified")
        signed.assert_called_once()


class SignedSourceTest(unittest.TestCase):
    def setUp(self):
        self.binding = b'{"binding":"test"}\n'
        self.cert = {
            "sourceRepositoryDigest": SOURCE_SHA,
            "buildSignerDigest": SOURCE_SHA,
            "sourceRepositoryRef": "refs/heads/main",
            "sourceRepositoryURI": "https://github.com/" + A.REPO,
            "sourceRepositoryIdentifier": "42",
            "buildSignerURI": A.SIGNER_IDENTITY,
            "issuer": "https://token.actions.githubusercontent.com",
            "subjectAlternativeName": {"type": "URI", "value": A.SIGNER_IDENTITY},
            "runInvocationURI": f"https://github.com/{A.REPO}/actions/runs/111/attempts/1",
            "buildTrigger": "pull_request_target",
            "runnerEnvironment": "github-hosted",
        }

    def invoke(self, cert=None, *, status=0, output=None):
        cert = self.cert if cert is None else cert
        result = [{"verificationResult": {"signature": {"certificate": cert},
                                          "verifiedTimestamps": [{"timestamp": "signed"}]}}]
        payload = json.dumps(result).encode() if output is None else output
        def fake_run(command, **kwargs):
            self.assertEqual(command[:3], ["gh", "attestation", "verify"])
            self.assertEqual(Path(command[3]).read_bytes(), self.binding)
            self.assertIn("--deny-self-hosted-runners", command)
            for key, expected in (("--repo", A.REPO),
                                  ("--cert-identity", A.SIGNER_IDENTITY),
                                  ("--source-digest", SOURCE_SHA),
                                  ("--signer-digest", SOURCE_SHA)):
                self.assertEqual(command[command.index(key) + 1], expected)
            self.assertNotIn("--source-ref", command)
            self.assertEqual(command[command.index("--hostname") + 1], "github.com")
            return subprocess.CompletedProcess(command, status, payload, b"")
        with mock.patch.object(A.subprocess, "run", side_effect=fake_run):
            A.verify_signed_source(self.binding, source_sha=SOURCE_SHA,
                                   repository_id=42, run_id=111, run_attempt=1)

    def test_certificate_binds_exact_source_and_run(self):
        self.invoke()
        self.invoke(dict(self.cert, subjectAlternativeName=A.SIGNER_IDENTITY))

    def test_wrong_signed_identity_fails(self):
        for key, wrong in (("sourceRepositoryDigest", HEAD),
                           ("buildSignerDigest", HEAD),
                           ("sourceRepositoryRef", "refs/heads/Main"),
                           ("sourceRepositoryIdentifier", "43"),
                           ("subjectAlternativeName", A.SIGNER_IDENTITY + "-other"),
                           ("runInvocationURI", "https://github.com/" + A.REPO + "/actions/runs/111/attempts/2"),
                           ("buildTrigger", "pull_request"),
                           ("runnerEnvironment", "self-hosted")):
            with self.subTest(key=key):
                cert = dict(self.cert, **{key: wrong})
                with self.assertRaisesRegex(A.EvidenceError, "signed_source_certificate_mismatch"):
                    self.invoke(cert)

    def test_unverified_or_ambiguous_result_fails(self):
        with self.assertRaisesRegex(A.EvidenceError, "signed_source_unverified"):
            self.invoke(status=1)
        for raw in (b'[]', b'{}', b'[{"verificationResult":{}}]', b'not json'):
            with self.subTest(raw=raw):
                with self.assertRaises(A.EvidenceError):
                    self.invoke(output=raw)

    def test_missing_cli_fails_closed(self):
        with mock.patch.object(A.subprocess, "run", side_effect=FileNotFoundError):
            with self.assertRaisesRegex(A.EvidenceError, "signed_source_verification_unavailable"):
                A.verify_signed_source(self.binding, source_sha=SOURCE_SHA,
                                       repository_id=42, run_id=111, run_attempt=1)


if __name__ == "__main__":
    unittest.main()
