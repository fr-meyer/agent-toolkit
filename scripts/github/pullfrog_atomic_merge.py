#!/usr/bin/env python3
"""Atomic reviewed-dev transport with mandatory trusted admission and custody.

This library is intentionally not an enabled CLI or a replacement review policy.
It reuses the existing real Git object pack producer, with a literal no-op source
guard in one atomic transaction. Fresh complete review/policy/check/veto admission
and exclusive durable custody must be supplied by trusted code. Ref confirmation
never certifies GitHub PR projection or performs downstream actions.
"""
from __future__ import annotations

import base64
import fcntl
import hashlib
import json
import os
import re
import stat
import subprocess
import tempfile
import time
import types
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable

SHA_RE=re.compile(r"^[0-9a-f]{40}$")
DIGEST_RE=re.compile(r"^[0-9a-f]{64}$")
REVIEW_BASE_REFS=frozenset({"dev"})
ALLOWED_HEAD_PREFIXES=("feat/","fix/","docs/","test/","chore/")
MAX_RESPONSE_BYTES=2*1024*1024
MAX_GIT_PROTOCOL_BYTES=8*1024*1024
MAX_PUSH_PACK_BYTES=64*1024*1024
GIT_PUSH_AGENT="agent-toolkit-pullfrog-auto-merge/1"



class AutoMergeError(Exception):
    """Sanitized fail-closed error with a stable code."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


POLICY_HELPER_SHA256='d8b5b453e3afeae48bf971158699528a39b57dea2b76811642b58202ac00d748'

def _load_fixed_policy_helper():
    """Compile exact sibling bytes; never reuse or replace canonical modules."""
    path=Path(__file__).resolve().with_name("pullfrog_trusted_author_policy.py")
    try:
        fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC|os.O_NONBLOCK)
        with os.fdopen(fd,"rb") as source:
            info=os.fstat(source.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size>65536:
                raise AutoMergeError("untrusted_policy_helper")
            raw=source.read(65537)
    except OSError:
        raise AutoMergeError("policy_helper_unavailable") from None
    if hashlib.sha256(raw).hexdigest()!=POLICY_HELPER_SHA256:
        raise AutoMergeError("untrusted_policy_helper")
    module=types.ModuleType("_pullfrog_atomic_merge_fixed_policy")
    module.__file__=str(path)
    exec(compile(raw,str(path),"exec"),module.__dict__)
    return module

trusted_author_policy=_load_fixed_policy_helper()
canonical_slug=trusted_author_policy.canonical_repository_slug
valid_branch=trusted_author_policy.valid_branch


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _text(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _integer(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def normalize_identity(value: Any) -> dict[str, Any]:
    item = _mapping(value)
    slug = canonical_slug(_text(item.get("repository_slug") or item.get("slug")))
    head_repository_slug = canonical_slug(_text(item.get("head_repository_slug")))
    base_repository_slug = canonical_slug(
        _text(item.get("base_repository_slug"))
    )
    author_login = trusted_author_policy.canonical_login(
        _text(item.get("author_login"))
    )
    return {
        "repository_slug": slug,
        "pr_number": _integer(item.get("pr_number")),
        "base_ref": _text(item.get("base_ref")),
        "base_sha": _text(item.get("base_sha")),
        "head_ref": _text(item.get("head_ref")),
        "head_sha": _text(item.get("head_sha")),
        "head_repository_slug": head_repository_slug,
        "base_repository_slug": base_repository_slug,
        "author_login": author_login,
        "author_account_id": _integer(item.get("author_account_id")),
        "author_type": _text(item.get("author_type")),
        "trusted_author_policy_schema": _text(
            item.get("trusted_author_policy_schema")
        ),
        "trusted_author_policy_digest": _text(
            item.get("trusted_author_policy_digest")
        ),
    }


def identity_from_pull_request(
    repository_slug: str,
    pr: dict[str, Any],
    policy: Any | None = None,
) -> dict[str, Any]:
    normalized_policy = trusted_author_policy.parse_policy(
        trusted_author_policy.load_policy(repository_slug)
        if policy is None
        else policy,
        repository_slug,
    )
    pull_request_identity = trusted_author_policy.normalize_pull_request_identity(
        repository_slug,
        pr,
    )
    author = _mapping(pull_request_identity.get("author"))
    return normalize_identity(
        {
            **pull_request_identity,
            "author_login": author["login"],
            "author_account_id": author["account_id"],
            "author_type": author["type"],
            "trusted_author_policy_schema": normalized_policy["schema"],
            "trusted_author_policy_digest": trusted_author_policy.policy_digest(
                normalized_policy
            ),
        }
    )


def _valid_review_identity(identity: dict[str, Any]) -> bool:
    return bool(
        identity["repository_slug"]
        and identity["head_repository_slug"]
        and identity["base_repository_slug"] == identity["repository_slug"]
        and bool(identity["author_login"])
        and (_integer(identity.get("author_account_id")) or 0) > 0
        and identity["author_type"] in trusted_author_policy.ALLOWED_ACCOUNT_TYPES
        and (identity["author_type"] == "Bot")
        == identity["author_login"].endswith("[bot]")
        and identity["trusted_author_policy_schema"]
        == trusted_author_policy.POLICY_SCHEMA
        and bool(DIGEST_RE.fullmatch(identity["trusted_author_policy_digest"]))
        and identity["base_ref"] in REVIEW_BASE_REFS
        and (_integer(identity.get("pr_number")) or 0) > 0
        and valid_branch(_text(identity.get("base_ref")))
        and valid_branch(_text(identity.get("head_ref")))
        and SHA_RE.fullmatch(_text(identity.get("base_sha")))
        and SHA_RE.fullmatch(_text(identity.get("head_sha")))
    )


def _valid_gate_identity(identity: dict[str, Any]) -> bool:
    return bool(
        _valid_review_identity(identity)
        and identity["head_repository_slug"] == identity["repository_slug"]
    )


def identity_digest(identity: Any) -> str:
    item = normalize_identity(identity)
    if not _valid_review_identity(item):
        raise AutoMergeError("invalid_review_identity")
    return _digest(item)


class _DualRefNoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class AtomicReceivePackRejected(AutoMergeError):
    """A complete negotiated atomic status report explicitly rejected a ref."""


def merge_operation_id(identity: dict[str, Any]) -> str:
    # Policy/review/actor changes must not mint a new mutation slot for an
    # unresolved attempt against the same reviewed refs.
    refs = {key:identity.get(key) for key in ("repository_slug","pr_number","base_ref","base_sha","head_ref","head_sha")}
    return _digest({"schema": "pullfrog-dualref-operation.v1", "reviewed_refs": refs})


def merge_operation_path(directory: Path, identity: dict[str, Any]) -> Path:
    return directory / (merge_operation_id(identity) + ".json")


def _validate_dualref_identity(identity: dict[str, Any]) -> tuple[str, str]:
    if not isinstance(identity, dict):
        raise AutoMergeError("invalid_dualref_identity")
    if normalize_identity(identity) != identity or not _valid_gate_identity(identity):
        raise AutoMergeError("invalid_full_merge_identity")
    base, head = identity.get("base_ref"), identity.get("head_ref")
    if (base != "dev" or not isinstance(head, str)
            or not head.startswith(ALLOWED_HEAD_PREFIXES)
            or not valid_branch(base) or not valid_branch(head)
            or base == head or identity.get("head_repository_slug") != identity.get("repository_slug")
            or identity.get("base_repository_slug") != identity.get("repository_slug")):
        raise AutoMergeError("invalid_dualref_destination")
    for name in ("base_sha", "head_sha"):
        value = identity.get(name)
        if not isinstance(value, str) or not SHA_RE.fullmatch(value) or value == "0" * 40:
            raise AutoMergeError("invalid_dualref_oid")
    return "refs/heads/" + base, "refs/heads/" + head


def _validate_final_admission(value: Any, identity: dict[str, Any]) -> dict[str, Any]:
    now = time.time()
    observed = value.get("observed_at") if isinstance(value, dict) else None
    if (not isinstance(value, dict) or value.get("schema") != "pullfrog-final-merge-admission.v1"
            or value.get("allowed") is not True or value.get("identity") != identity
            or type(observed) not in (int, float) or not now - 30 <= observed <= now + 5
            or not isinstance(value.get("snapshot_digest"), str)
            or not re.fullmatch(r"[0-9a-f]{64}", value["snapshot_digest"])):
        raise AutoMergeError("final_admission_missing_stale_or_mismatched")
    return {"schema": value["schema"], "allowed": True, "identity": identity,
            "observed_at": observed, "snapshot_digest": value["snapshot_digest"]}


def _strict_status_packets(data: bytes) -> list[bytes]:
    if not isinstance(data, bytes) or len(data) > MAX_GIT_PROTOCOL_BYTES:
        raise AutoMergeError("invalid_git_protocol_response")
    result, offset = [], 0
    while offset < len(data):
        if offset + 4 > len(data) or not re.fullmatch(rb"[0-9a-fA-F]{4}", data[offset:offset+4]):
            raise AutoMergeError("invalid_git_protocol_response")
        length = int(data[offset:offset+4], 16); offset += 4
        if length == 0:
            if offset != len(data):
                raise AutoMergeError("unexpected_git_protocol_after_flush")
            return result
        if length < 5 or offset + length - 4 > len(data):
            raise AutoMergeError("invalid_git_protocol_response")
        result.append(data[offset:offset+length-4]); offset += length-4
    raise AutoMergeError("missing_git_protocol_flush")


class MergeOperationJournal:
    """Owner-only local ledger, coupled to a REQUIRED external custody barrier.

    A runner-local fsync alone is not cross-run durability. The trusted caller
    must implement the custody callback by storing/verifying the immutable plan
    under the stable operation ID before this adapter may submit a POST. The
    legacy CLI has no such callback and therefore cannot mutate.
    """
    def __init__(self, path: Path, identity: dict[str, Any]):
        self.path, self.identity = Path(path), identity
        self.operation_id = merge_operation_id(identity)
        if self.path.name != self.operation_id + ".json":
            raise AutoMergeError("operation_path_not_identity_bound")
        self.lock = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        directory = self.path.parent.stat()
        if directory.st_uid != os.geteuid() or directory.st_mode & 0o077:
            raise AutoMergeError("unsafe_operation_directory")
        descriptor = os.open(str(self.path) + ".lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK, 0o600)
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077:
            os.close(descriptor)
            raise AutoMergeError("unsafe_operation_lock")
        self.lock = os.fdopen(descriptor, "r+")
        try:
            fcntl.flock(self.lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self.lock.close(); self.lock = None
            raise AutoMergeError("merge_operation_in_progress") from None
        return self

    def __exit__(self, *_):
        if self.lock is not None:
            fcntl.flock(self.lock.fileno(), fcntl.LOCK_UN); self.lock.close()

    def read(self) -> dict[str, Any] | None:
        try:
            descriptor = os.open(self.path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
        except FileNotFoundError:
            return None
        try:
            info = os.fstat(descriptor)
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077 or not 0 < info.st_size <= 131072:
                raise AutoMergeError("unsafe_operation_record")
            with os.fdopen(descriptor, "rb") as source:
                descriptor = -1; raw = source.read(131073)
            value = json.loads(raw)
            plan = value.get("plan") if isinstance(value, dict) else None
            if (len(raw) > 131072 or not isinstance(value, dict) or value.get("schema") != "pullfrog-dualref-journal.v1"
                    or not isinstance(plan, dict) or plan.get("identity") != self.identity
                    or plan.get("schema") != "pullfrog-dualref-operation.v1"
                    or plan.get("operation_id") != self.operation_id
                    or value.get("state") not in {"reserved", "submitting", "ambiguous", "rejected", "confirmed", "blocked"}):
                raise AutoMergeError("invalid_operation_record")
            _validate_dualref_identity(plan["identity"])
            for name in ("merge_sha", "tree_sha"):
                if not isinstance(plan.get(name), str) or not SHA_RE.fullmatch(plan[name]) or plan[name] == "0"*40:
                    raise AutoMergeError("invalid_operation_record")
            base, head = _validate_dualref_identity(self.identity)
            if (plan.get("expected_refs") != {base:self.identity["base_sha"],head:self.identity["head_sha"]}
                    or plan.get("updated_refs") != {base:plan["merge_sha"],head:self.identity["head_sha"]}
                    or plan.get("parents") != [self.identity["base_sha"],self.identity["head_sha"]]
                    or not isinstance(plan.get("pack_digest"), str)
                    or not re.fullmatch(r"[0-9a-f]{64}", plan["pack_digest"])):
                raise AutoMergeError("invalid_operation_record")
            return value
        except AutoMergeError:
            raise
        except Exception:
            raise AutoMergeError("invalid_operation_record") from None
        finally:
            if descriptor >= 0: os.close(descriptor)

    def write(self, value: dict[str, Any]) -> None:
        data = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
        descriptor, temporary = tempfile.mkstemp(prefix=".dualref-", dir=self.path.parent)
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "wb") as target:
                descriptor = -1; target.write(data); target.flush(); os.fsync(target.fileno())
            os.replace(temporary, self.path)
            parent = os.open(self.path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
            try: os.fsync(parent)
            finally: os.close(parent)
        finally:
            if descriptor >= 0: os.close(descriptor)
            if os.path.exists(temporary): os.unlink(temporary)


def _validate_operation_custody(value: Any, plan: dict[str, Any]) -> dict[str, Any]:
    if (not isinstance(value, dict) or value.get("schema") != "pullfrog-merge-operation-custody.v1"
            or value.get("durable") is not True or value.get("operation_id") != plan["operation_id"]
            or value.get("exclusive_reservation") is not True or value.get("existing_operation") is not False
            or value.get("record_digest") != _digest(plan)
            or type(value.get("artifact_id")) is not int or value["artifact_id"] < 1):
        raise AutoMergeError("durable_operation_custody_unverified")
    return {key:value[key] for key in ("schema","durable","exclusive_reservation","existing_operation","operation_id","record_digest","artifact_id")}


class GitHubMergeClient:
    def __init__(self,api_url: str,token: str,repository_slug: str,*,
                 trusted_policy_loader: Callable[[str],dict[str,Any]] | None=None,
                 read_client: Any=None):
        slug=canonical_slug(repository_slug)
        if api_url!="https://api.github.com" or not slug:
            raise AutoMergeError("untrusted_api_or_repository")
        self.api_url,self.token,self.repository_slug=api_url,token,slug
        self.allowed_prefix="/repos/"+slug
        self._trusted_policy_loader=trusted_policy_loader or trusted_author_policy.load_policy
        self._trusted_read_client=read_client

    def get(self,path: str):
        if path!=f"{self.allowed_prefix}/pulls/"+path.rsplit("/",1)[-1] or not path.rsplit("/",1)[-1].isdigit():
            raise AutoMergeError("unapproved_read_path")
        if self._trusted_read_client is None:
            raise AutoMergeError("trusted_read_client_required")
        return self._trusted_read_client.get(path)

    def _assert_current_identity(self,pr: dict[str,Any],identity: dict[str,Any]):
        try:
            policy=trusted_author_policy.parse_policy(self._trusted_policy_loader(self.repository_slug),self.repository_slug)
            observed=identity_from_pull_request(self.repository_slug,pr,policy)
            author={"login":observed["author_login"],"account_id":observed["author_account_id"],"type":observed["author_type"]}
            authorized=trusted_author_policy.evaluate_author(policy,author).get("authorized") is True
        except (trusted_author_policy.TrustedAuthorPolicyError,KeyError,TypeError,ValueError):
            raise AutoMergeError("live_pull_request_identity_invalid") from None
        if pr.get("state")!="open" or pr.get("draft") is not False or observed!=identity or not authorized:
            raise AutoMergeError("live_pull_request_identity_or_authority_drift")

    def _final_admission(self,callback,identity):
        self._assert_current_identity(_mapping(self.get(f"{self.allowed_prefix}/pulls/{identity['pr_number']}")),identity)
        result=callback(json.loads(json.dumps(identity)))
        self._assert_current_identity(_mapping(self.get(f"{self.allowed_prefix}/pulls/{identity['pr_number']}")),identity)
        return _validate_final_admission(result,identity)

    @staticmethod
    def _git(
        workspace: Path,
        *args: str,
        env: dict[str, str] | None = None,
        code: str = "git_merge_failed",
    ) -> subprocess.CompletedProcess[str]:
        try:
            result = subprocess.run(
                ["git", *args],
                cwd=workspace,
                env=env,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=120,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise AutoMergeError(code) from exc
        if result.returncode != 0:
            raise AutoMergeError(code)
        return result

    @staticmethod
    def _pkt_line(payload: bytes) -> bytes:
        length = len(payload) + 4
        if length > 0xFFFF:
            raise AutoMergeError("git_protocol_packet_too_large")
        return f"{length:04x}".encode("ascii") + payload

    @staticmethod
    def _pkt_payloads(data: bytes) -> list[bytes | None]:
        packets: list[bytes | None] = []
        offset = 0
        while offset < len(data):
            if offset + 4 > len(data):
                raise AutoMergeError("invalid_git_protocol_response")
            prefix = data[offset : offset + 4]
            try:
                length = int(prefix, 16)
            except ValueError as exc:
                raise AutoMergeError("invalid_git_protocol_response") from exc
            offset += 4
            if length in {0, 1, 2}:
                packets.append(None)
                continue
            if length < 4 or offset + length - 4 > len(data):
                raise AutoMergeError("invalid_git_protocol_response")
            packets.append(data[offset : offset + length - 4])
            offset += length - 4
        return packets

    @staticmethod
    def _basic_git_authorization(token: str) -> str:
        if not token:
            raise AutoMergeError("missing_github_token")
        encoded = base64.b64encode(f"x-access-token:{token}".encode("utf-8")).decode(
            "ascii"
        )
        return f"Basic {encoded}"

    @staticmethod
    def _bounded_protocol_output(data: bytes) -> bytes:
        if len(data) > MAX_GIT_PROTOCOL_BYTES:
            raise AutoMergeError("git_protocol_response_too_large")
        return data

    @staticmethod
    def _pack_objects(workspace: Path, new_oid: str, old_oid: str) -> bytes:
        try:
            result = subprocess.run(
                [
                    "git",
                    "pack-objects",
                    "--stdout",
                    "--revs",
                    "--thin",
                    "--delta-base-offset",
                ],
                cwd=workspace,
                input=f"{new_oid}\n^{old_oid}\n".encode("ascii"),
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=120,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise AutoMergeError("git_pack_creation_failed") from exc
        if (
            result.returncode != 0
            or not result.stdout.startswith(b"PACK")
            or len(result.stdout) > MAX_PUSH_PACK_BYTES
        ):
            raise AutoMergeError("git_pack_creation_failed")
        return result.stdout

    def _repository_remote(self) -> str:
        return f"https://github.com/{self.repository_slug}.git"

    def _http_receive_pack(self, remote: str, token: str, *, body: bytes | None = None) -> bytes:
        if remote != f"https://github.com/{self.repository_slug}.git":
            raise AutoMergeError("untrusted_git_rpc_origin")
        url = remote + ("/info/refs?service=git-receive-pack" if body is None else "/git-receive-pack")
        request = urllib.request.Request(url, data=body, method="GET" if body is None else "POST", headers={
            "Accept":"application/x-git-receive-pack-advertisement" if body is None else "application/x-git-receive-pack-result",
            "Authorization":self._basic_git_authorization(token),"User-Agent":GIT_PUSH_AGENT,
            **({} if body is None else {"Content-Type":"application/x-git-receive-pack-request"})})
        try:
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),_DualRefNoRedirect())
            with opener.open(request, timeout=30 if body is None else 120) as response:
                if response.status != 200 or response.geturl() != url:
                    raise AutoMergeError("unexpected_git_rpc_response")
                data = response.read(MAX_GIT_PROTOCOL_BYTES+1)
            return self._bounded_protocol_output(data)
        except Exception:
            raise AutoMergeError("git_advertisement_unavailable" if body is None else "git_submission_response_uncertain") from None

    def _receive_pack_advertisement(self, remote: str, token: str) -> bytes:
        if urllib.parse.urlparse(remote).scheme in {"http","https"}:
            return self._http_receive_pack(remote,token)
        if not Path(remote).is_absolute() or not Path(remote).is_dir():
            raise AutoMergeError("invalid_local_git_fixture")
        try:
            result=subprocess.run(["git","receive-pack","--stateless-rpc","--advertise-refs",remote],check=False,
                stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=120)
        except (OSError,subprocess.TimeoutExpired):raise AutoMergeError("git_advertisement_unavailable") from None
        if result.returncode:raise AutoMergeError("git_advertisement_unavailable")
        return self._bounded_protocol_output(result.stdout)

    def _submit_receive_pack(self, remote: str, token: str, body: bytes) -> bytes:
        if urllib.parse.urlparse(remote).scheme in {"http","https"}:
            return self._http_receive_pack(remote,token,body=body)
        if not Path(remote).is_absolute() or not Path(remote).is_dir():
            raise AutoMergeError("invalid_local_git_fixture")
        try:
            result=subprocess.run(["git","receive-pack","--stateless-rpc",remote],input=body,check=False,
                stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=120)
        except (OSError,subprocess.TimeoutExpired):raise AutoMergeError("git_submission_response_uncertain") from None
        if result.returncode:raise AutoMergeError("git_submission_response_uncertain")
        return self._bounded_protocol_output(result.stdout)

    @classmethod
    def _advertised_ref(cls, data: bytes, ref: str) -> tuple[str, set[str]]:
        advertised, capabilities = {}, set()
        if not data.endswith(b"0000"):
            raise AutoMergeError("invalid_git_protocol_advertisement")
        for payload in cls._pkt_payloads(data):
            if payload is None or payload.startswith(b"# service="):
                continue
            line = payload.rstrip(b"\n")
            if line.startswith(b"version "):
                raise AutoMergeError("unsupported_git_protocol_advertisement")
            if b"\0" in line:
                if capabilities:
                    raise AutoMergeError("duplicate_git_capabilities")
                line, raw = line.split(b"\0", 1)
                try: capabilities = set(raw.decode("ascii").split())
                except UnicodeDecodeError: raise AutoMergeError("invalid_git_protocol_advertisement") from None
            fields = line.split(b" ", 1)
            if len(fields) != 2 or fields[1] in advertised:
                raise AutoMergeError("invalid_git_protocol_advertisement")
            try: oid = fields[0].decode("ascii")
            except UnicodeDecodeError: raise AutoMergeError("invalid_git_protocol_advertisement") from None
            if not SHA_RE.fullmatch(oid) or oid == "0"*40:
                raise AutoMergeError("invalid_git_protocol_advertisement")
            advertised[fields[1]] = oid
        if ref.encode("utf-8") not in advertised:
            raise AutoMergeError("reviewed_ref_not_advertised")
        # Deliberately negotiate v1. A v2-only server fails closed rather than
        # accepting status-v2 option semantics through a permissive parser.
        if not {"atomic", "report-status", "ofs-delta"} <= capabilities:
            raise AutoMergeError("atomic_receive_pack_capability_missing")
        if any(value.startswith("object-format=") and value != "object-format=sha1" for value in capabilities):
            raise AutoMergeError("unsupported_git_object_format")
        return advertised[ref.encode("utf-8")], capabilities

    @classmethod
    def _receive_pack_body(cls, *, old_oid: str, new_oid: str, ref: str,
                           head_oid: str, head_ref: str, capabilities: set[str], pack: bytes) -> bytes:
        if (ref == head_ref or not ref.startswith("refs/heads/") or not head_ref.startswith("refs/heads/")
                or ref != "refs/heads/dev" or not head_ref[len("refs/heads/"):].startswith(ALLOWED_HEAD_PREFIXES)
                or not valid_branch(head_ref[len("refs/heads/"):])):
            raise AutoMergeError("invalid_dualref_destination")
        for oid in (old_oid, new_oid, head_oid):
            if not isinstance(oid, str) or not SHA_RE.fullmatch(oid) or oid == "0"*40:
                raise AutoMergeError("invalid_dualref_oid")
        if not {"atomic", "report-status", "ofs-delta"} <= capabilities:
            raise AutoMergeError("atomic_receive_pack_capability_missing")
        if not isinstance(pack, bytes) or not pack.startswith(b"PACK") or len(pack) > MAX_PUSH_PACK_BYTES:
            raise AutoMergeError("invalid_merge_pack")
        requested = ["report-status", "atomic"]
        for capability in ("side-band-64k", "ofs-delta", "object-format=sha1"):
            if capability in capabilities: requested.append(capability)
        requested.append(f"agent={GIT_PUSH_AGENT}")
        base = f"{old_oid} {new_oid} {ref}\0{' '.join(requested)}\n".encode("utf-8")
        guard = f"{head_oid} {head_oid} {head_ref}\n".encode("utf-8")
        return cls._pkt_line(base) + cls._pkt_line(guard) + b"0000" + pack

    @classmethod
    def _assert_receive_pack_success(cls, data: bytes, refs: set[str]) -> None:
        packets = _strict_status_packets(data)
        if not packets or len(refs) != 2:
            raise AutoMergeError("invalid_git_protocol_response")
        if packets[0][:1] in (b"\x01", b"\x02", b"\x03"):
            stream = bytearray()
            for packet in packets:
                if packet[:1] == b"\x03": raise AutoMergeError("git_receive_pack_fatal_response")
                if packet[:1] == b"\x01": stream.extend(packet[1:])
                elif packet[:1] != b"\x02": raise AutoMergeError("mixed_git_protocol_response")
            packets = _strict_status_packets(bytes(stream))
        if any(not packet.endswith(b"\n") or b"\n" in packet[:-1] or b"\r" in packet or b"\0" in packet for packet in packets):
            raise AutoMergeError("invalid_git_status_line")
        try: lines = [packet.decode("utf-8", "strict")[:-1] for packet in packets]
        except UnicodeDecodeError: raise AutoMergeError("invalid_git_protocol_response") from None
        if len(lines) != 3 or not lines[0].startswith("unpack "):
            raise AutoMergeError("invalid_git_protocol_response")
        statuses = {}
        for line in lines[1:]:
            if line.startswith("ok "):
                ref, accepted = line[3:], True
            elif line.startswith("ng "):
                fields = line[3:].split(" ", 1)
                if len(fields) != 2 or not fields[1]: raise AutoMergeError("invalid_git_protocol_response")
                ref, accepted = fields[0], False
            else: raise AutoMergeError("invalid_git_protocol_response")
            if ref not in refs or ref in statuses:
                raise AutoMergeError("unexpected_or_duplicate_ref_status")
            statuses[ref] = accepted
        if set(statuses) != refs: raise AutoMergeError("missing_ref_status")
        if lines[0] != "unpack ok":
            raise AutoMergeError("invalid_git_unpack_status")
        if not all(statuses.values()):
            if any(statuses.values()):
                raise AutoMergeError("contradictory_atomic_ref_status")
            raise AtomicReceivePackRejected("atomic_ref_transaction_rejected")

    def _observe_merge_ref_pair(self, identity: dict[str, Any]) -> dict[str, str]:
        base, head = _validate_dualref_identity(identity)
        data = self._receive_pack_advertisement(self._repository_remote(), self.token)
        return {ref:self._advertised_ref(data, ref)[0] for ref in (base, head)}

    def _reconcile_merge_operation(self, record: dict[str, Any], journal: MergeOperationJournal) -> dict[str, Any]:
        plan = record["plan"]
        if record["state"] == "rejected":
            raise AutoMergeError("operation_previously_rejected_no_replay")
        _validate_operation_custody(record.get("custody"), plan)
        try: current = self._observe_merge_ref_pair(plan["identity"])
        except Exception:
            current = None
        if current == plan["updated_refs"]:
            record.update(state="confirmed", confirmation="desired_ref_pair_observed")
            journal.write(record)
            return {"ref_outcome":"confirmed", "sha":plan["merge_sha"],
                    "base_ref":plan["identity"]["base_ref"], "base_sha":plan["identity"]["base_sha"],
                    "head_sha":plan["identity"]["head_sha"], "operation_id":plan["operation_id"],
                    "transport":"atomic-dual-ref-normal-fast-forward-push", "recovered":True,
                    "confirmation":record["confirmation"], "atomic_status_verified":record.get("protocol_status_verified") is True,
                    "post_attempted":False, "pr_projection_verified":False, "downstream_actions_performed":False}
        # In particular, OLD refs after a timeout are NOT proof of rejection:
        # a server may still finish the first submission after this observation.
        record.update(state="ambiguous", confirmation="unresolved_ref_outcome")
        journal.write(record)
        raise AutoMergeError("merge_operation_ambiguous_no_replay")

    def push_exact_merge(self, identity: dict[str, Any], title: str, *,
                         operation_path: Path | None = None,
                         final_admission: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
                         custody_barrier: Callable[[dict[str, Any]], dict[str, Any]] | None = None) -> dict[str, Any]:
        """One raw atomic base/head transaction with explicit execution custody.

        The legacy CLI supplies none of these trusted integration controls and
        fails closed. Custody must be implemented/verified by a durable hosted
        artifact/claim adapter before CI rollout; fsync on a runner is not it.
        """
        base_ref, head_ref = _validate_dualref_identity(identity)
        identity = json.loads(json.dumps(identity))
        if operation_path is None or not callable(final_admission) or not callable(custody_barrier):
            raise AutoMergeError("dualref_execution_controls_required")
        if not self.token:
            raise AutoMergeError("missing_github_token")
        with MergeOperationJournal(operation_path, identity) as journal:
            previous = journal.read()
            if previous is not None:
                return self._reconcile_merge_operation(previous, journal)
            self._assert_current_identity(_mapping(self.get(f"{self.allowed_prefix}/pulls/{identity['pr_number']}")), identity)
            remote = self._repository_remote()
            if urllib.parse.urlparse(remote).scheme in {"http","https"}:
                if remote != f"https://github.com/{self.repository_slug}.git":
                    raise AutoMergeError("untrusted_git_rpc_origin")
            elif not Path(remote).is_absolute() or not Path(remote).is_dir():
                raise AutoMergeError("invalid_local_git_fixture")
            with tempfile.TemporaryDirectory(prefix="pullfrog-auto-merge-") as temporary:
                workspace = Path(temporary)
                askpass = workspace / "git-askpass.sh"
                askpass.write_text('#!/bin/sh\ncase "$1" in\n  *Username*) printf "%s\\n" x-access-token ;;\n  *) printf "%s\\n" "$GITHUB_TOKEN" ;;\nesac\n',encoding="utf-8")
                askpass.chmod(0o700)
                env = os.environ.copy()
                env.update({"GITHUB_TOKEN":self.token,"GIT_ASKPASS":str(askpass),"GIT_TERMINAL_PROMPT":"0",
                    "GIT_CONFIG_NOSYSTEM":"1","GIT_CONFIG_GLOBAL":"/dev/null",
                    "GIT_AUTHOR_NAME":"github-actions[bot]","GIT_AUTHOR_EMAIL":"41898282+github-actions[bot]@users.noreply.github.com",
                    "GIT_COMMITTER_NAME":"github-actions[bot]","GIT_COMMITTER_EMAIL":"41898282+github-actions[bot]@users.noreply.github.com"})
                self._git(workspace,"init","--quiet",env=env)
                self._git(workspace,"remote","add","origin",remote,env=env)
                self._git(workspace,"-c","http.followRedirects=false","-c","http.proxy=","fetch","--quiet","--no-tags","origin",
                    base_ref+":refs/remotes/origin/base",head_ref+":refs/remotes/origin/pull-head",env=env,code="git_fetch_failed")
                base=self._git(workspace,"rev-parse","refs/remotes/origin/base",env=env).stdout.strip()
                head=self._git(workspace,"rev-parse","refs/remotes/origin/pull-head",env=env).stdout.strip()
                if base != identity["base_sha"] or head != identity["head_sha"]:
                    raise AutoMergeError("git_fetch_identity_drift")
                tree=self._git(workspace,"merge-tree","--write-tree",base,head,env=env,code="merge_conflict_or_tree_failure").stdout.strip()
                if not SHA_RE.fullmatch(tree) or tree == "0"*40: raise AutoMergeError("invalid_merge_tree")
                merge_sha=self._git(workspace,"commit-tree",tree,"-p",base,"-p",head,"-m",f"{title} (#{identity['pr_number']})",env=env,code="merge_commit_creation_failed").stdout.strip()
                if not SHA_RE.fullmatch(merge_sha) or merge_sha == "0"*40: raise AutoMergeError("invalid_merge_commit")
                parents=self._git(workspace,"rev-list","--parents","-n","1",merge_sha,env=env).stdout.split()
                if parents != [merge_sha,base,head]: raise AutoMergeError("merge_commit_parent_mismatch")
                self._git(workspace,"merge-base","--is-ancestor",base,merge_sha,env=env,code="merge_not_fast_forward")
                pack=self._pack_objects(workspace,merge_sha,base)
                advertisement=self._receive_pack_advertisement(remote,self.token)
                advertised_base,capabilities=self._advertised_ref(advertisement,base_ref)
                advertised_head,head_capabilities=self._advertised_ref(advertisement,head_ref)
                if advertised_base != base or advertised_head != head or capabilities != head_capabilities:
                    raise AutoMergeError("advertised_ref_identity_drift")
                body=self._receive_pack_body(old_oid=base,new_oid=merge_sha,ref=base_ref,head_oid=head,head_ref=head_ref,capabilities=capabilities,pack=pack)
                plan={"schema":"pullfrog-dualref-operation.v1","operation_id":journal.operation_id,"identity":identity,
                    "merge_sha":merge_sha,"tree_sha":tree,"parents":[base,head],"pack_digest":hashlib.sha256(pack).hexdigest(),
                    "expected_refs":{base_ref:base,head_ref:head},"updated_refs":{base_ref:merge_sha,head_ref:head}}
                record={"schema":"pullfrog-dualref-journal.v1","plan":plan,"state":"reserved","attempts":0}
                journal.write(record)
                try:
                    record["custody"]=_validate_operation_custody(custody_barrier(json.loads(json.dumps(plan))),plan)
                    journal.write(record)
                    admission=self._final_admission(final_admission,identity)
                    record.update(admission=admission,state="submitting",attempts=1)
                    journal.write(record)
                    _validate_final_admission(admission,identity)
                except Exception:
                    record["state"]="blocked";journal.write(record)
                    raise AutoMergeError("merge_pre_submission_controls_failed") from None
                try:
                    response=self._submit_receive_pack(remote,self.token,body)
                    self._assert_receive_pack_success(response,{base_ref,head_ref})
                    record["protocol_status_verified"]=True
                except AtomicReceivePackRejected:
                    record.update(state="rejected",confirmation="complete_atomic_rejection")
                    journal.write(record)
                    raise
                except Exception:
                    record.update(state="ambiguous",confirmation="uncertain_submission_response")
                    journal.write(record)
                    result=self._reconcile_merge_operation(record,journal)
                    result["post_attempted"]=True
                    return result
                record.update(state="ambiguous",confirmation="response_requires_ref_readback")
                journal.write(record)
                result=self._reconcile_merge_operation(record,journal)
                result.update(recovered=False,post_attempted=True)
                return result



AtomicMergeClient=GitHubMergeClient
