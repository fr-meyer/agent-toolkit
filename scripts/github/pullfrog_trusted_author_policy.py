#!/usr/bin/env python3
"""Fail-closed trusted-author policy for Pullfrog mutation authority.

The policy is repository-owned data loaded only from the sibling canonical JSON
artifact. Numeric GitHub account IDs are the primary authority. Login and account
type must also match so renames, account recreation, and bot/user drift stop the
write path. GitHub node IDs are diagnostic only and never authorize a mutation.
"""

from __future__ import annotations

import hashlib
import json
import re
import stat
from pathlib import Path
from typing import Any

POLICY_SCHEMA = "pullfrog-trusted-author-policy.v1"
POLICY_PATH = Path(__file__).with_name("pullfrog_trusted_author_policy.json")
MAX_POLICY_BYTES = 64 * 1024
ALLOWED_ACCOUNT_TYPES = frozenset({"Bot", "User"})
POLICY_KEYS = frozenset({"schema", "repository_slug", "trusted_authors"})
AUTHOR_KEYS = frozenset({"account_id", "login", "type"})
OWNER_RE = re.compile(r"^(?=.{1,39}$)(?!-)(?!.*--)[A-Za-z0-9-]+(?<!-)$")
REPOSITORY_RE = re.compile(r"^[A-Za-z0-9._-]{1,100}$")
LOGIN_RE = re.compile(
    r"^(?=.{1,100}$)(?!-)(?!.*--)[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\[bot\])?$"
)
NODE_ID_RE = re.compile(r"^[A-Za-z0-9_+=/-]{1,256}$")


class TrustedAuthorPolicyError(Exception):
    """Sanitized stable error code."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _text(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _integer(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def canonical_repository_slug(value: str) -> str:
    if value.count("/") != 1:
        return ""
    owner, repository = value.split("/", 1)
    if not OWNER_RE.fullmatch(owner):
        return ""
    if not REPOSITORY_RE.fullmatch(repository) or repository in {".", ".."}:
        return ""
    return f"{owner.casefold()}/{repository.casefold()}"


def canonical_login(value: str) -> str:
    login = value.casefold()
    return login if LOGIN_RE.fullmatch(login) else ""


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    item: dict[str, Any] = {}
    for key, value in pairs:
        if key in item:
            raise TrustedAuthorPolicyError("duplicate_policy_key")
        item[key] = value
    return item


def _normalize_policy_author(value: Any) -> dict[str, Any]:
    item = _mapping(value)
    if set(item) != AUTHOR_KEYS:
        raise TrustedAuthorPolicyError("invalid_policy_author_fields")
    account_id = _integer(item.get("account_id"))
    login_value = _text(item.get("login"))
    login = canonical_login(login_value)
    account_type = _text(item.get("type"))
    if account_id is None or account_id <= 0:
        raise TrustedAuthorPolicyError("invalid_policy_author_id")
    if not login or login != login_value:
        raise TrustedAuthorPolicyError("invalid_policy_author_login")
    if account_type not in ALLOWED_ACCOUNT_TYPES:
        raise TrustedAuthorPolicyError("invalid_policy_author_type")
    if (account_type == "Bot") != login.endswith("[bot]"):
        raise TrustedAuthorPolicyError("policy_author_login_type_mismatch")
    return {
        "account_id": account_id,
        "login": login,
        "type": account_type,
    }


def parse_policy(value: Any, expected_repository_slug: str = "") -> dict[str, Any]:
    item = _mapping(value)
    if set(item) != POLICY_KEYS:
        raise TrustedAuthorPolicyError("invalid_policy_fields")
    if item.get("schema") != POLICY_SCHEMA:
        raise TrustedAuthorPolicyError("invalid_policy_schema")
    repository_value = _text(item.get("repository_slug"))
    repository_slug = canonical_repository_slug(repository_value)
    if not repository_slug or repository_slug != repository_value:
        raise TrustedAuthorPolicyError("invalid_policy_repository")
    expected_slug = canonical_repository_slug(expected_repository_slug)
    if expected_repository_slug and (
        not expected_slug or expected_slug != repository_slug
    ):
        raise TrustedAuthorPolicyError("policy_repository_mismatch")
    raw_authors = item.get("trusted_authors")
    if not isinstance(raw_authors, list) or not raw_authors:
        raise TrustedAuthorPolicyError("invalid_policy_authors")
    authors = [_normalize_policy_author(raw) for raw in raw_authors]
    account_ids = [author["account_id"] for author in authors]
    logins = [author["login"] for author in authors]
    if len(set(account_ids)) != len(account_ids):
        raise TrustedAuthorPolicyError("duplicate_policy_author_id")
    if len(set(logins)) != len(logins):
        raise TrustedAuthorPolicyError("duplicate_policy_author_login")
    authors.sort(key=lambda author: author["account_id"])
    return {
        "schema": POLICY_SCHEMA,
        "repository_slug": repository_slug,
        "trusted_authors": authors,
    }


def parse_policy_json(raw: bytes | str, expected_repository_slug: str = "") -> dict[str, Any]:
    encoded = raw.encode("utf-8") if isinstance(raw, str) else raw
    if not isinstance(encoded, bytes) or not encoded or len(encoded) > MAX_POLICY_BYTES:
        raise TrustedAuthorPolicyError("invalid_policy_bytes")
    try:
        decoded = encoded.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise TrustedAuthorPolicyError("invalid_policy_encoding") from exc
    try:
        value = json.loads(decoded, object_pairs_hook=_strict_object)
    except TrustedAuthorPolicyError:
        raise
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise TrustedAuthorPolicyError("invalid_policy_json") from exc
    return parse_policy(value, expected_repository_slug)


def load_policy(expected_repository_slug: str = "") -> dict[str, Any]:
    """Load only the reviewed sibling policy artifact.

    There is deliberately no path, environment, event, or CLI override.
    """

    try:
        metadata = POLICY_PATH.lstat()
        if POLICY_PATH.is_symlink() or not stat.S_ISREG(metadata.st_mode):
            raise TrustedAuthorPolicyError("invalid_policy_file")
        if metadata.st_size <= 0 or metadata.st_size > MAX_POLICY_BYTES:
            raise TrustedAuthorPolicyError("invalid_policy_bytes")
        raw = POLICY_PATH.read_bytes()
        observed = POLICY_PATH.lstat()
    except TrustedAuthorPolicyError:
        raise
    except OSError as exc:
        raise TrustedAuthorPolicyError("policy_unavailable") from exc
    if (
        len(raw) != metadata.st_size
        or POLICY_PATH.is_symlink()
        or not stat.S_ISREG(observed.st_mode)
        or (metadata.st_dev, metadata.st_ino, metadata.st_size, metadata.st_mtime_ns)
        != (observed.st_dev, observed.st_ino, observed.st_size, observed.st_mtime_ns)
    ):
        raise TrustedAuthorPolicyError("policy_file_changed")
    return parse_policy_json(raw, expected_repository_slug)


def policy_digest(policy: Any) -> str:
    return _digest(parse_policy(policy))


def normalize_live_author(value: Any) -> dict[str, Any]:
    item = _mapping(value)
    account_id = _integer(item.get("id"))
    if account_id is None:
        account_id = _integer(item.get("account_id"))
    login = canonical_login(_text(item.get("login")))
    account_type = _text(item.get("type"))
    node_id = _text(item.get("node_id"))
    if account_id is None or account_id <= 0:
        raise TrustedAuthorPolicyError("invalid_live_author_id")
    if not login:
        raise TrustedAuthorPolicyError("invalid_live_author_login")
    if account_type not in ALLOWED_ACCOUNT_TYPES:
        raise TrustedAuthorPolicyError("invalid_live_author_type")
    if node_id and not NODE_ID_RE.fullmatch(node_id):
        raise TrustedAuthorPolicyError("invalid_live_author_node_id")
    return {
        "account_id": account_id,
        "login": login,
        "type": account_type,
        "node_id": node_id,
    }


def author_from_pull_request(pr: Any) -> dict[str, Any]:
    return normalize_live_author(_mapping(pr).get("user"))


def evaluate_author(policy: Any, live_author: Any) -> dict[str, Any]:
    normalized_policy = parse_policy(policy)
    author = normalize_live_author(live_author)
    digest = policy_digest(normalized_policy)
    by_id = {
        trusted["account_id"]: trusted
        for trusted in normalized_policy["trusted_authors"]
    }
    trusted = by_id.get(author["account_id"])
    reason = "untrusted_account_id"
    authorized = False
    if trusted is not None:
        if trusted["login"] != author["login"]:
            reason = "author_login_drift"
        elif trusted["type"] != author["type"]:
            reason = "author_type_drift"
        else:
            reason = "trusted_author"
            authorized = True
    return {
        "authorized": authorized,
        "reason": reason,
        "author": author,
        "policy": {
            "schema": normalized_policy["schema"],
            "repository_slug": normalized_policy["repository_slug"],
            "digest": digest,
        },
    }
