#!/usr/bin/env python3
"""Deterministic, fail-closed repository similarity preflight.

The collector/search layer is intentionally outside this script. Callers provide
sanitized search evidence, and this script validates the evidence, classifies
matches, redacts unsafe text, and emits JSON/Markdown proof.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

SCHEMA_VERSION = "repository-similarity-preflight/v1"
STATUSES = {"pass", "related", "duplicate", "blocked", "not-applicable"}
RELATIONSHIPS = {"duplicate", "directly_related", "superseded", "unrelated"}
PUBLIC_AUTH = {"available", "anonymous", "not_required"}
PRIVATE_AUTH = {"approved_authenticated"}
DEFAULT_SOURCE_KINDS = (
    "issues",
    "discussions",
    "pull_requests",
    "releases",
    "docs",
    "code",
    "tests",
)

# These patterns are deliberately conservative. A finding blocks the gate; the
# report contains a redacted value and never echoes the original text.
_REDACTION_PATTERNS: tuple[tuple[str, re.Pattern[str], str], ...] = (
    ("email", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I), "<redacted-email>"),
    ("bearer", re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{12,}", re.I), "Bearer <redacted>"),
    ("github_token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"), "<redacted-token>"),
    ("secret_assignment", re.compile(r"\b(?:api[_-]?key|access[_-]?token|secret|password|private[_-]?key)\s*[:=]\s*[^\s,;]+", re.I), "<redacted-secret>"),
    ("posix_path", re.compile(r"(?<![A-Za-z0-9])/(?:home|Users|root|tmp|var|etc|mnt|opt)/[^\s\"']+"), "<redacted-path>"),
    ("windows_path", re.compile(r"\b[A-Za-z]:\\[^\s\"']+"), "<redacted-path>"),
    ("phone", re.compile(r"(?<!\w)(?:\+?\d[\d .()_-]{7,}\d)(?!\w)"), "<redacted-phone>"),
)
_SECRET_KEY_RE = re.compile(
    r"(?:token|secret|password|passwd|cookie|authorization|private[_ -]?key|api[_ -]?key|client[_ -]?secret)",
    re.I,
)


def _normalise(value: str) -> str:
    value = value.casefold()
    value = re.sub(r"[^\w]+", " ", value, flags=re.UNICODE)
    return re.sub(r"\s+", " ", value).strip()


def _tokens(value: str) -> set[str]:
    return {token for token in _normalise(value).split() if len(token) > 1}


def _safe_finding_field(field: Any) -> str:
    label = str(field)
    for _, pattern, replacement in _REDACTION_PATTERNS:
        label = pattern.sub(replacement, label)
    label = re.sub(r"(\.query\.)[^.]+", r"\1<key>", label)
    label = re.sub(r"(required_source_kinds\.)[^.]+", r"\1<kind>", label)
    return label[:200]


def _redact_text(value: Any, findings: list[dict[str, str]], field: str) -> str:
    if value is None:
        return ""
    text = str(value)
    redacted = text
    for kind, pattern, replacement in _REDACTION_PATTERNS:
        if pattern.search(redacted):
            findings.append({"field": _safe_finding_field(field), "kind": kind})
            redacted = pattern.sub(replacement, redacted)
    return redacted


def _redact_url(value: Any, findings: list[dict[str, str]], field: str) -> str:
    if not value:
        return ""
    raw_url = str(value)
    try:
        parts = urlsplit(raw_url)
    except ValueError:
        return _redact_text(raw_url, findings, field)

    # Never preserve URL userinfo. It is credential material even when the
    # username/password does not use a recognised query-parameter name.
    netloc = parts.hostname or ""
    try:
        if parts.port is not None:
            netloc = f"{netloc}:{parts.port}"
    except ValueError:
        findings.append({"field": field, "kind": "url_userinfo"})
    if parts.username is not None or parts.password is not None:
        findings.append({"field": field, "kind": "url_userinfo"})

    safe_path = _redact_text(parts.path, findings, f"{field}.path")
    safe_query: list[tuple[str, str]] = []
    for key, val in parse_qsl(parts.query, keep_blank_values=True):
        if _SECRET_KEY_RE.search(key):
            findings.append({"field": field, "kind": "secret_query_parameter"})
            safe_query.append((key, "<redacted>"))
        else:
            safe_query.append((key, _redact_text(val, findings, f"{field}.query.{key}")))
    return urlunsplit((parts.scheme, netloc, safe_path, urlencode(safe_query), ""))


def _safe_text(value: Any, findings: list[dict[str, str]], field: str) -> str:
    return _redact_text(value, findings, field)


def _safe_item(item: dict[str, Any], findings: list[dict[str, str]], field: str) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    for key in ("kind", "number", "state", "relationship", "match_type"):
        if key in item:
            value = item[key]
            if key == "number" and isinstance(value, int) and not isinstance(value, bool):
                safe[key] = value
            else:
                safe[key] = _safe_text(value, findings, f"{field}.{key}")
    if "matched_terms" in item:
        terms = item.get("matched_terms")
        if isinstance(terms, list):
            safe["matched_terms"] = [
                _safe_text(term, findings, f"{field}.matched_terms")
                for term in terms
                if str(term).strip()
            ]
        else:
            safe["matched_terms"] = _safe_text(terms, findings, f"{field}.matched_terms")
    for key in ("url", "canonical_url"):
        if key in item:
            safe[key] = _redact_url(item[key], findings, f"{field}.{key}")
    for key in ("title", "reason", "summary"):
        if key in item:
            safe[key] = _safe_text(item[key], findings, f"{field}.{key}")
    return safe


def _issue(code: str, detail: str, *, severity: str = "blocker") -> dict[str, str]:
    return {"code": code, "detail": detail, "severity": severity}


def _require_string(obj: dict[str, Any], key: str, errors: list[dict[str, str]], label: str) -> str:
    value = obj.get(key)
    if not isinstance(value, str) or not value.strip():
        errors.append(_issue(f"missing_{key}", f"{label}.{key} is required"))
        return ""
    return value.strip()


def _usable_route(item: dict[str, Any], source_kind: str, repository: dict[str, Any]) -> bool:
    number = item.get("number")
    if (
        isinstance(number, int)
        and not isinstance(number, bool)
        and number > 0
        and source_kind in {"issues", "pull_requests", "discussions"}
    ):
        return True
    expected_host = repository.get("host")
    expected_owner = repository.get("owner")
    expected_name = repository.get("name")
    if not all(isinstance(value, str) and value.strip() for value in (expected_host, expected_owner, expected_name)):
        return False
    for key in ("url", "canonical_url"):
        value = item.get(key)
        if not isinstance(value, str) or not value.strip():
            continue
        try:
            parts = urlsplit(value)
        except ValueError:
            continue
        path_parts = [part for part in parts.path.split("/") if part]
        if (
            parts.scheme in {"http", "https"}
            and parts.hostname
            and parts.hostname.casefold() == expected_host.casefold()
            and len(path_parts) >= 3
            and path_parts[0] == expected_owner
            and path_parts[1] == expected_name
        ):
            return True
    return False


def _classify_item(
    item: dict[str, Any], intent_terms: set[str], intent_title: str,
    source_kind: str, repository: dict[str, Any], findings: list[dict[str, str]], field: str
) -> tuple[dict[str, Any], str | None]:
    safe = _safe_item(item, findings, field)
    safe["source_kind"] = _safe_text(source_kind, findings, f"{field}.source_kind")
    relationship = item.get("relationship")
    if relationship not in RELATIONSHIPS:
        candidate_text = " ".join(
            str(item.get(key, "")) for key in ("title", "summary", "reason")
        )
        matched = _tokens(candidate_text) & intent_terms
        safe["matched_terms"] = sorted(matched)
        if item.get("exact_match") or (
            _normalise(str(item.get("title", "")))
            and _normalise(str(item.get("title", ""))) == intent_title
        ):
            relationship = "duplicate"
            safe["match_type"] = "exact"
        elif len(matched) >= 2:
            relationship = "directly_related"
            safe["match_type"] = "synonym_or_term_overlap"
        else:
            relationship = "unrelated"
            safe["match_type"] = "none"
    safe["relationship"] = relationship
    if relationship in {"duplicate", "directly_related", "superseded"}:
        if not _usable_route(item, source_kind, repository):
            return safe, "related_match_without_canonical_route"
        return safe, relationship
    return safe, None


def _markdown_text(value: Any) -> str:
    text = str(value if value is not None else "")
    text = re.sub(r"[\r\n\t]+", " ", text)
    text = text.replace("\\", "\\\\")
    for character in ("`", "*", "_", "[", "]", "#", "+", "-", "!", "|", ">"):
        text = text.replace(character, f"\\{character}")
    return text.replace("<", "&lt;")


def _markdown(report: dict[str, Any]) -> str:
    repository = report.get("repository", {})
    lines = [
        "# Repository Similarity Preflight",
        "",
        f"- Schema: `{_markdown_text(report.get('schema_version'))}`",
        f"- Status: **{_markdown_text(report.get('status'))}**",
        f"- Reason: {_markdown_text(report.get('reason'))}",
        f"- Repository: `{_markdown_text(repository.get('host'))}/{_markdown_text(repository.get('owner'))}/{_markdown_text(repository.get('name'))}`",
        f"- Visibility: `{_markdown_text(repository.get('visibility'))}`",
        f"- Revision: `{_markdown_text(repository.get('revision'))}`",
        f"- Branch: `{_markdown_text(repository.get('branch'))}`",
        "",
        "## Checks",
    ]
    for check in report.get("checks", []):
        lines.append(
            f"- `{_markdown_text(check.get('name'))}`: **{_markdown_text(check.get('status'))}** — {_markdown_text(check.get('detail'))}"
        )
    lines.extend(["", "## Matches"])
    matches = report.get("matches", [])
    if not matches:
        lines.append("- None")
    else:
        for match in matches:
            route = match.get("canonical_url") or match.get("url") or match.get("number") or "no route"
            lines.append(
                f"- `{_markdown_text(match.get('relationship', 'unknown'))}` `{_markdown_text(route)}` — {_markdown_text(match.get('title', '<untitled>'))}"
            )
    if report.get("blockers"):
        lines.extend(["", "## Blockers"])
        lines.extend(
            f"- `{_markdown_text(item.get('code'))}`: {_markdown_text(item.get('detail'))}"
            for item in report["blockers"]
        )
    if report.get("redaction", {}).get("findings"):
        lines.extend(["", "## Redaction"])
        lines.append("- Unsafe values were redacted from the evidence; the gate is fail-closed until the public wording is corrected.")
    lines.append("")
    return "\n".join(lines)


def build_report(payload: dict[str, Any], *, external_write: bool = False) -> dict[str, Any]:
    blockers: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    checks: list[dict[str, str]] = []
    findings: list[dict[str, str]] = []

    if payload.get("schema_version") != SCHEMA_VERSION:
        blockers.append(_issue("unsupported_schema", "input schema_version is not supported"))
    repository = payload.get("repository")
    intent = payload.get("intent")
    search = payload.get("search")
    if not isinstance(repository, dict):
        blockers.append(_issue("missing_repository", "repository object is required"))
        repository = {}
    if not isinstance(intent, dict):
        blockers.append(_issue("missing_intent", "intent object is required"))
        intent = {}
    if not isinstance(search, dict):
        blockers.append(_issue("missing_search", "search object is required"))
        search = {}

    visibility = repository.get("visibility")
    safe_repository = {
        "host": _safe_text(repository.get("host"), findings, "repository.host"),
        "owner": _safe_text(repository.get("owner"), findings, "repository.owner"),
        "name": _safe_text(repository.get("name"), findings, "repository.name"),
        "visibility": visibility if isinstance(visibility, str) and visibility in {"public", "private"} else _safe_text(visibility, findings, "repository.visibility"),
        "revision": _safe_text(repository.get("revision") or repository.get("base_revision"), findings, "repository.revision"),
        "branch": _safe_text(repository.get("branch"), findings, "repository.branch"),
    }
    for key in ("host", "owner", "name", "visibility", "revision", "branch"):
        if not safe_repository.get(key):
            blockers.append(_issue(f"missing_repository_{key}", f"repository.{key} is required"))
    if not isinstance(visibility, str) or visibility not in {"public", "private"}:
        blockers.append(_issue("visibility_unknown", "repository visibility must be explicitly public or private"))

    title = _require_string(intent, "title", blockers, "intent")
    summary = _require_string(intent, "summary", blockers, "intent")
    target = _require_string(intent, "target", blockers, "intent")
    terms_raw = intent.get("terms", [])
    behavior_raw = intent.get("behavior_names", [])
    if not isinstance(terms_raw, list) or not all(isinstance(v, str) for v in terms_raw):
        blockers.append(_issue("invalid_intent_terms", "intent.terms must be a list of strings"))
        terms_raw = []
    if not isinstance(behavior_raw, list) or not all(isinstance(v, str) for v in behavior_raw):
        blockers.append(_issue("invalid_behavior_names", "intent.behavior_names must be a list of strings"))
        behavior_raw = []
    safe_intent = {
        "title": _safe_text(title, findings, "intent.title"),
        "summary": _safe_text(summary, findings, "intent.summary"),
        "target": _safe_text(target, findings, "intent.target"),
        "terms": [_safe_text(v, findings, "intent.terms") for v in terms_raw],
        "behavior_names": [_safe_text(v, findings, "intent.behavior_names") for v in behavior_raw],
    }

    not_applicable = intent.get("not_applicable", False)
    if not isinstance(not_applicable, bool):
        blockers.append(_issue("invalid_not_applicable", "intent.not_applicable must be a boolean"))
        not_applicable = False
    if not_applicable:
        reason = _safe_text(intent.get("not_applicable_reason"), findings, "intent.not_applicable_reason")
        if not reason:
            blockers.append(_issue("missing_not_applicable_reason", "not-applicable requires a reason"))
        else:
            checks.append({"name": "applicability", "status": "passed", "detail": reason})
            if findings:
                blockers.append(_issue("unsafe_public_evidence", "private or secret-like values were found in public evidence fields"))
            if external_write:
                blockers.append(_issue("external_write_not_allowed", "external writes require a clean pass and cannot bypass not-applicable status"))
            if not blockers:
                return {
                    "schema_version": SCHEMA_VERSION,
                    "status": "not-applicable",
                    "reason": reason,
                    "repository": safe_repository,
                    "intent": safe_intent,
                    "search": {"sources": [], "auth": {"status": "not_required"}},
                    "matches": [],
                    "checks": checks,
                    "blockers": [],
                    "warnings": [],
                    "redaction": {"findings": findings},
                    "external_write": {"requested": external_write, "allowed": False},
                }

    auth = search.get("auth")
    if not isinstance(auth, dict):
        blockers.append(_issue("missing_search_auth", "search.auth object is required"))
        auth = {}
    auth_status = auth.get("status")
    safe_auth_status = _safe_text(auth_status, findings, "search.auth.status")
    allowed_auth = PRIVATE_AUTH if visibility == "private" else PUBLIC_AUTH
    if not isinstance(auth_status, str) or auth_status not in allowed_auth:
        blockers.append(
            _issue(
                "search_auth_unavailable",
                "search authentication/source access is unavailable or not approved for this repository visibility",
            )
        )
    else:
        checks.append({"name": "search_auth", "status": "passed", "detail": "approved search access recorded"})

    source_list = search.get("sources")
    if not isinstance(source_list, list) or not source_list:
        blockers.append(_issue("missing_search_sources", "at least one search source is required"))
        source_list = []
    required_kinds = search.get("required_source_kinds", list(DEFAULT_SOURCE_KINDS))
    if not isinstance(required_kinds, list) or not all(isinstance(v, str) for v in required_kinds):
        blockers.append(_issue("invalid_required_source_kinds", "required_source_kinds must be a list of strings"))
        required_kinds = list(DEFAULT_SOURCE_KINDS)
    source_by_kind: dict[str, list[dict[str, Any]]] = {}
    configured_kinds = set(required_kinds)
    omitted_default_kinds = set(DEFAULT_SOURCE_KINDS) - configured_kinds
    for index, source in enumerate(source_list):
        if not isinstance(source, dict):
            blockers.append(_issue("invalid_search_source", f"search.sources[{index}] must be an object"))
            continue
        kind = source.get("kind")
        status = source.get("status")
        if not isinstance(kind, str) or not kind.strip():
            blockers.append(_issue("search_source_kind_missing", f"search.sources[{index}].kind is required"))
            continue
        source_by_kind.setdefault(kind, []).append(source)
        safe_kind = _safe_text(kind, findings, f"search.sources[{index}].kind")
        if status == "not_applicable":
            if not _safe_text(source.get("reason"), findings, f"search.sources[{index}].reason"):
                blockers.append(_issue("search_source_reason_missing", f"not-applicable source {safe_kind} needs a reason"))
        elif status != "complete":
            blockers.append(_issue("search_source_incomplete", f"search source {safe_kind} is not complete"))
        elif "items" not in source or not isinstance(source.get("items"), list):
            blockers.append(_issue("search_source_items_invalid", f"search source {safe_kind}.items must be a list"))
    safe_source_metadata = [
        {
            "kind": _safe_text(source.get("kind"), findings, f"search.sources[{index}].kind"),
            "status": _safe_text(source.get("status"), findings, f"search.sources[{index}].status"),
            "item_count": len(source.get("items", []) or []) if isinstance(source.get("items", []), list) else 0,
        }
        for index, source in enumerate(source_list)
        if isinstance(source, dict)
    ]
    for kind in omitted_default_kinds:
        entries = source_by_kind.get(kind, [])
        if not entries or any(
            entry.get("status") != "not_applicable"
            or not _safe_text(entry.get("reason"), findings, f"search.sources.{kind}.reason")
            for entry in entries
        ):
            blockers.append(
                _issue(
                    "required_search_source_omission_not_justified",
                    f"omitted default search source {kind} must be present with an explicit not-applicable reason",
                )
            )
    for kind in required_kinds:
        entries = source_by_kind.get(kind, [])
        if not entries:
            safe_kind = _safe_text(kind, findings, f"search.required_source_kinds.{kind}")
            blockers.append(_issue("required_search_source_missing", f"required search source is missing: {safe_kind}"))
    if not blockers:
        checks.append({"name": "search_coverage", "status": "passed", "detail": "all required search sources have complete or justified not-applicable evidence"})

    # Public query fields are retained only after redaction. Any finding blocks
    # the gate because redaction is evidence that unsafe wording was supplied.
    raw_queries = search.get("queries", [])
    if not isinstance(raw_queries, list):
        blockers.append(_issue("invalid_search_queries", "search.queries must be a list of strings"))
        raw_queries = []
    queries: list[str] = []
    for index, query in enumerate(raw_queries):
        if not isinstance(query, str) or not query.strip():
            blockers.append(_issue("invalid_search_query", f"search.queries[{index}] must be a non-empty string"))
            continue
        queries.append(_safe_text(query, findings, f"search.queries[{index}]"))
    if not queries:
        blockers.append(_issue("missing_search_queries", "at least one public/sanitized search query is required"))

    intent_terms = _tokens(" ".join([title, summary, *terms_raw, *behavior_raw]))
    matches: list[dict[str, Any]] = []
    relationship_hits: list[str] = []
    for source_index, source in enumerate(source_list):
        if not isinstance(source, dict):
            continue
        items = source.get("items", [])
        if not isinstance(items, list):
            continue
        for item_index, item in enumerate(items):
            if not isinstance(item, dict):
                blockers.append(_issue("invalid_search_item", f"search.sources[{source_index}].items[{item_index}] must be an object"))
                continue
            if "relationship" in item and item["relationship"] not in RELATIONSHIPS:
                blockers.append(_issue("invalid_search_item_relationship", f"search.sources[{source_index}].items[{item_index}].relationship must be one of the supported relationship values"))
                continue
            safe_item, hit = _classify_item(
                item, intent_terms, _normalise(title), str(source.get("kind")), repository, findings,
                f"search.sources[{source_index}].items[{item_index}]",
            )
            # Keep all explicit matches and only retain deterministic inferred
            # matches with enough evidence. Unrelated results are proof too.
            if item.get("relationship") in RELATIONSHIPS or hit in {"duplicate", "directly_related", "superseded"}:
                matches.append(safe_item)
            if hit:
                relationship_hits.append(hit)
            if hit == "related_match_without_canonical_route":
                blockers.append(_issue("canonical_route_missing", "a duplicate/related match has no stable URL, number, or canonical URL"))

    if relationship_hits:
        if "duplicate" in relationship_hits:
            status = "duplicate"
            reason = "a duplicate match exists; route work to the canonical item instead of opening a new issue or PR"
        else:
            status = "related"
            reason = "a directly related or superseded item exists; review and route to the canonical thread before new work"
    else:
        status = "pass"
        reason = "no duplicate or strong related match was found in the completed evidence"
    if blockers:
        status = "blocked"
        reason = "preflight evidence or safety validation is incomplete; do not proceed"
    elif not source_list:
        status = "blocked"
        reason = "no search evidence was supplied"

    if status in {"duplicate", "related"}:
        checks.append({"name": "canonical_routing", "status": "blocked", "detail": "new issue/PR creation is prohibited until the canonical item is selected"})
    else:
        checks.append({"name": "canonical_routing", "status": "passed", "detail": "no canonical duplicate/related route is required"})

    external = {"requested": external_write, "allowed": False}
    if external_write:
        approval = payload.get("external_write", {}).get("approval") if isinstance(payload.get("external_write"), dict) else None
        if status != "pass":
            blockers.append(_issue("external_write_not_allowed", "external writes require a clean pass and cannot bypass duplicate/related/blocked status"))
        elif not isinstance(approval, dict) or approval.get("authorized") is not True:
            blockers.append(_issue("external_write_approval_required", "external write approval must be explicit and scoped"))
        else:
            scope = approval.get("scope")
            if not isinstance(scope, str) or not scope.strip():
                blockers.append(_issue("external_write_scope_missing", "external write approval must name its scope"))
            else:
                external["allowed"] = True
                external["scope"] = _safe_text(scope, findings, "external_write.approval.scope")
        if blockers:
            status = "blocked"
            reason = "external write gate is not satisfied; discovery does not authorize publication or mutation"
    elif status == "pass":
        external["allowed"] = False
        external["detail"] = "discovery-only; external writes remain separately approval-gated"

    # Findings can arise from candidate metadata or the approval scope after the
    # earlier query pass. Privacy findings always override a provisional result.
    if findings and not any(item["code"] == "unsafe_public_evidence" for item in blockers):
        blockers.append(_issue("unsafe_public_evidence", "private or secret-like values were found in public evidence fields"))
    if findings:
        status = "blocked"
        reason = "preflight evidence contains unsafe private or secret-like values; correct the public wording and rerun"
        external["allowed"] = False

    report = {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "reason": reason,
        "repository": safe_repository,
        "intent": safe_intent,
        "search": {
            "auth": {"status": safe_auth_status},
            "queries": queries,
            "sources": safe_source_metadata,
        },
        "matches": matches,
        "checks": checks,
        "blockers": blockers,
        "warnings": warnings,
        "redaction": {"findings": findings},
        "external_write": external,
    }
    return report


def _load(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError("input JSON must be an object")
    return value


def _exit_code(status: str) -> int:
    return {"pass": 0, "not-applicable": 0, "related": 2, "duplicate": 3, "blocked": 4}.get(status, 5)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="sanitized preflight input JSON")
    parser.add_argument("--output", type=Path, help="write structured report JSON to this path")
    parser.add_argument("--markdown-output", type=Path, help="write Markdown evidence to this path")
    parser.add_argument("--external-write", action="store_true", help="apply the separate external-write approval gate")
    parser.add_argument("--pretty", action="store_true", help="pretty-print JSON on stdout")
    args = parser.parse_args(argv)
    try:
        report = build_report(_load(args.input), external_write=args.external_write)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"schema_version": SCHEMA_VERSION, "status": "blocked", "reason": str(exc)}), file=sys.stderr)
        return 5
    encoded = json.dumps(report, indent=2 if args.pretty else None, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded + "\n", encoding="utf-8")
    if args.markdown_output:
        args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_output.write_text(_markdown(report), encoding="utf-8")
    print(encoded)
    return _exit_code(report["status"])


if __name__ == "__main__":
    raise SystemExit(main())
