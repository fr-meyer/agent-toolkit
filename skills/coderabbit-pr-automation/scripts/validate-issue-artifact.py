#!/usr/bin/env python3
"""
Validate a normalized CodeRabbit issue artifact against a stricter schema.

Exit codes:
- 0: valid
- 1: invalid artifact
- 2: usage/runtime error
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Tuple

ALLOWED_SEVERITIES = {"critical", "high", "medium", "low", "unknown"}
ALLOWED_STATUSES = {"open"}

REQUIRED_PR_FIELDS = ("number", "title", "branch", "repository")
REQUIRED_METADATA_FIELDS = ("artifactVersion", "createdAt", "source")
REQUIRED_ISSUE_FIELDS = (
    "id",
    "threadId",
    "status",
    "file",
    "severity",
    "type",
    "title",
    "description",
    "agentPrompt",
)


def load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def is_nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def is_relative_repo_path(value: Any) -> bool:
    if not is_nonempty_string(value):
        return False
    if os.path.isabs(value):
        return False
    if len(value) >= 2 and value[1] == ":":
        return False
    return True


def is_iso8601ish(value: str) -> bool:
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


def validate_pr(pr: Any, errors: List[str]) -> None:
    if not isinstance(pr, dict):
        errors.append("Top-level 'pr' must be an object.")
        return

    for field in REQUIRED_PR_FIELDS:
        if field not in pr:
            errors.append(f"Missing required pr field: '{field}'.")
        elif field == "number":
            if not isinstance(pr[field], int) or pr[field] < 1:
                errors.append("pr.number must be a positive integer.")
        else:
            if not is_nonempty_string(pr[field]):
                errors.append(f"pr.{field} must be a non-empty string.")

    optional_string_fields = ("url", "headSha", "baseBranch")
    for field in optional_string_fields:
        if field in pr and not is_nonempty_string(pr[field]):
            errors.append(f"pr.{field} must be a non-empty string if present.")


def validate_metadata(metadata: Any, errors: List[str]) -> None:
    if not isinstance(metadata, dict):
        errors.append("Top-level 'metadata' must be an object.")
        return

    for field in REQUIRED_METADATA_FIELDS:
        if field not in metadata:
            errors.append(f"Missing required metadata field: '{field}'.")
        elif not is_nonempty_string(metadata[field]):
            errors.append(f"metadata.{field} must be a non-empty string.")

    if "createdAt" in metadata and is_nonempty_string(metadata["createdAt"]):
        if not is_iso8601ish(metadata["createdAt"]):
            errors.append("metadata.createdAt must be a valid ISO-8601 timestamp.")


def validate_constraints(constraints: Any, errors: List[str]) -> None:
    if constraints is None:
        return

    if not isinstance(constraints, dict):
        errors.append("Top-level 'constraints' must be an object if present.")
        return

    bool_fields = (
        "allowCommit",
        "allowPush",
        "allowPrComment",
        "allowThreadResolution",
        "allowScopeExpansion",
    )

    for field in bool_fields:
        if field in constraints and not isinstance(constraints[field], bool):
            errors.append(f"constraints.{field} must be a boolean if present.")

    if "maxCycles" in constraints:
        if not isinstance(constraints["maxCycles"], int) or constraints["maxCycles"] < 1:
            errors.append("constraints.maxCycles must be an integer >= 1.")


def validate_context(context: Any, errors: List[str]) -> None:
    if context is None:
        return

    if not isinstance(context, dict):
        errors.append("Top-level 'context' must be an object if present.")
        return

    string_fields = ("repoPath", "expectedRepository", "expectedBranch", "expectedHeadSha")
    for field in string_fields:
        if field in context and context[field] is not None and not is_nonempty_string(context[field]):
            errors.append(f"context.{field} must be a non-empty string if present.")

    if "workingTreeMustBeClean" in context and not isinstance(context["workingTreeMustBeClean"], bool):
        errors.append("context.workingTreeMustBeClean must be a boolean if present.")


def validate_validation_context(validation: Any, errors: List[str]) -> None:
    if validation is None:
        return

    if not isinstance(validation, dict):
        errors.append("Top-level 'validation' must be an object if present.")
        return

    if "rateLimited" in validation and not isinstance(validation["rateLimited"], bool):
        errors.append("validation.rateLimited must be a boolean if present.")

    if "rateLimitScope" in validation and validation["rateLimitScope"] is not None and not is_nonempty_string(validation["rateLimitScope"]):
        errors.append("validation.rateLimitScope must be a non-empty string if present.")

    if "retryAfterSeconds" in validation and validation["retryAfterSeconds"] is not None:
        if not isinstance(validation["retryAfterSeconds"], int) or validation["retryAfterSeconds"] < 0:
            errors.append("validation.retryAfterSeconds must be an integer >= 0 if present.")


def validate_issue(issue: Any, index: int, errors: List[str], warnings: List[str]) -> None:
    prefix = f"issues[{index}]"

    if not isinstance(issue, dict):
        errors.append(f"{prefix} must be an object.")
        return

    for field in REQUIRED_ISSUE_FIELDS:
        if field not in issue:
            errors.append(f"{prefix} is missing required field '{field}'.")
            continue

        if field == "severity":
            if not is_nonempty_string(issue[field]):
                errors.append(f"{prefix}.severity must be a non-empty string.")
            elif issue[field] not in ALLOWED_SEVERITIES:
                errors.append(
                    f"{prefix}.severity must be one of {sorted(ALLOWED_SEVERITIES)}."
                )
        elif field == "status":
            if not is_nonempty_string(issue[field]):
                errors.append(f"{prefix}.status must be a non-empty string.")
            elif issue[field] not in ALLOWED_STATUSES:
                errors.append(
                    f"{prefix}.status must be one of {sorted(ALLOWED_STATUSES)}."
                )
        elif field == "file":
            if not is_relative_repo_path(issue[field]):
                errors.append(f"{prefix}.file must be a repo-relative path.")
        else:
            if not is_nonempty_string(issue[field]):
                errors.append(f"{prefix}.{field} must be a non-empty string.")

    for field in ("commentId", "author", "rawBody"):
        if field in issue and issue[field] is not None and not is_nonempty_string(issue[field]):
            errors.append(f"{prefix}.{field} must be a non-empty string if present.")

    has_line = False
    for field in ("line", "startLine", "endLine"):
        if field in issue and issue[field] is not None:
            if not isinstance(issue[field], int) or issue[field] < 1:
                errors.append(f"{prefix}.{field} must be an integer >= 1 if present.")
            else:
                has_line = True

    if not has_line:
        warnings.append(f"{prefix} has no line/startLine/endLine.")

    if "startLine" in issue and "endLine" in issue:
        s = issue.get("startLine")
        e = issue.get("endLine")
        if isinstance(s, int) and isinstance(e, int) and e < s:
            errors.append(f"{prefix}.endLine must be >= startLine.")

    if "agentPrompt" in issue and is_nonempty_string(issue["agentPrompt"]):
        if len(issue["agentPrompt"].strip()) < 15:
            warnings.append(f"{prefix}.agentPrompt looks unusually short.")


def validate_artifact(data: Any) -> Tuple[List[str], List[str]]:
    errors: List[str] = []
    warnings: List[str] = []

    if not isinstance(data, dict):
        return ["Artifact root must be a JSON object."], warnings

    if "pr" not in data:
        errors.append("Missing top-level 'pr'.")
    else:
        validate_pr(data["pr"], errors)

    if "issues" not in data:
        errors.append("Missing top-level 'issues'.")
    elif not isinstance(data["issues"], list):
        errors.append("Top-level 'issues' must be an array.")
    else:
        for i, issue in enumerate(data["issues"]):
            validate_issue(issue, i, errors, warnings)

    if "metadata" not in data:
        errors.append("Missing top-level 'metadata'.")
    else:
        validate_metadata(data["metadata"], errors)

    validate_constraints(data.get("constraints"), errors)
    validate_context(data.get("context"), errors)
    validate_validation_context(data.get("validation"), errors)

    return errors, warnings


def build_result(path: str, errors: List[str], warnings: List[str]) -> Dict[str, Any]:
    return {
        "path": path,
        "valid": len(errors) == 0,
        "errorCount": len(errors),
        "warningCount": len(warnings),
        "errors": errors,
        "warnings": warnings,
    }


def print_human(result: Dict[str, Any]) -> None:
    status = "VALID" if result["valid"] else "INVALID"
    print(f"[{status}] {result['path']}")
    print(f"Errors: {result['errorCount']}")
    print(f"Warnings: {result['warningCount']}")

    if result["errors"]:
        print("\nErrors:")
        for msg in result["errors"]:
            print(f"- {msg}")

    if result["warnings"]:
        print("\nWarnings:")
        for msg in result["warnings"]:
            print(f"- {msg}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate a normalized CodeRabbit issue artifact."
    )
    parser.add_argument("artifact", help="Path to actionable-issues JSON.")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON output.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        data = load_json(args.artifact)
    except FileNotFoundError:
        msg = f"Artifact file not found: {args.artifact}"
        if args.json:
            print(json.dumps({"valid": False, "errors": [msg], "warnings": []}, indent=2))
        else:
            print(msg, file=sys.stderr)
        return 2
    except json.JSONDecodeError as exc:
        msg = f"Invalid JSON: {exc}"
        if args.json:
            print(json.dumps({"valid": False, "errors": [msg], "warnings": []}, indent=2))
        else:
            print(msg, file=sys.stderr)
        return 2
    except Exception as exc:
        msg = f"Failed to read artifact: {exc}"
        if args.json:
            print(json.dumps({"valid": False, "errors": [msg], "warnings": []}, indent=2))
        else:
            print(msg, file=sys.stderr)
        return 2

    errors, warnings = validate_artifact(data)
    result = build_result(args.artifact, errors, warnings)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print_human(result)

    return 0 if result["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
