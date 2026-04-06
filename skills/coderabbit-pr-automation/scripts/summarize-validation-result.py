#!/usr/bin/env python3
"""
Summarize a strict validation-result JSON artifact into a compact decision.

Expected schema:
- validationVersion
- tool
- pr
- cycle
- findings
- optional summary
- optional rateLimit
- optional metadata

Exit codes:
- 0: summary produced
- 2: usage/runtime/schema error
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, List, Tuple

ALLOWED_SEVERITIES = {"critical", "high", "medium", "low", "unknown"}
ALLOWED_FINDING_STATUSES = {"open", "resolved", "ignored"}


def load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def is_nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_validation_result(data: Any) -> Tuple[List[str], List[str]]:
    errors: List[str] = []
    warnings: List[str] = []

    if not isinstance(data, dict):
        return ["Validation result root must be a JSON object."], warnings

    if "validationVersion" not in data or not is_nonempty_string(data["validationVersion"]):
        errors.append("Missing or invalid top-level 'validationVersion'.")

    tool = data.get("tool")
    if not isinstance(tool, dict):
        errors.append("Missing or invalid top-level 'tool' object.")
    else:
        if "name" not in tool or not is_nonempty_string(tool["name"]):
            errors.append("tool.name must be a non-empty string.")
        for field in ("mode", "version"):
            if field in tool and not is_nonempty_string(tool[field]):
                errors.append(f"tool.{field} must be a non-empty string if present.")

    pr = data.get("pr")
    if not isinstance(pr, dict):
        errors.append("Missing or invalid top-level 'pr' object.")
    else:
        if "number" not in pr or not isinstance(pr["number"], int) or pr["number"] < 1:
            errors.append("pr.number must be a positive integer.")
        for field in ("title", "branch", "repository"):
            if field not in pr or not is_nonempty_string(pr[field]):
                errors.append(f"pr.{field} must be a non-empty string.")

    if "cycle" not in data or not isinstance(data["cycle"], int) or data["cycle"] < 1:
        errors.append("Missing or invalid top-level 'cycle' (must be integer >= 1).")

    findings = data.get("findings")
    if not isinstance(findings, list):
        errors.append("Missing or invalid top-level 'findings' array.")
    else:
        for i, finding in enumerate(findings):
            prefix = f"findings[{i}]"
            if not isinstance(finding, dict):
                errors.append(f"{prefix} must be an object.")
                continue

            for field in ("id", "severity", "kind", "status", "title", "description"):
                if field not in finding or not is_nonempty_string(finding[field]):
                    errors.append(f"{prefix}.{field} must be a non-empty string.")

            if "severity" in finding and is_nonempty_string(finding["severity"]):
                if finding["severity"] not in ALLOWED_SEVERITIES:
                    errors.append(
                        f"{prefix}.severity must be one of {sorted(ALLOWED_SEVERITIES)}."
                    )

            if "status" in finding and is_nonempty_string(finding["status"]):
                if finding["status"] not in ALLOWED_FINDING_STATUSES:
                    errors.append(
                        f"{prefix}.status must be one of {sorted(ALLOWED_FINDING_STATUSES)}."
                    )

            if "file" in finding and finding["file"] is not None and not is_nonempty_string(finding["file"]):
                errors.append(f"{prefix}.file must be a non-empty string if present.")

            if "line" in finding and finding["line"] is not None:
                if not isinstance(finding["line"], int) or finding["line"] < 1:
                    errors.append(f"{prefix}.line must be an integer >= 1 if present.")

    summary = data.get("summary")
    if summary is not None:
        if not isinstance(summary, dict):
            errors.append("summary must be an object if present.")
        else:
            for field in (
                "critical",
                "high",
                "medium",
                "low",
                "unknown",
                "totalFindings",
                "blockingCount",
            ):
                if field in summary and (not isinstance(summary[field], int) or summary[field] < 0):
                    errors.append(f"summary.{field} must be an integer >= 0 if present.")

    rate_limit = data.get("rateLimit")
    if rate_limit is not None:
        if not isinstance(rate_limit, dict):
            errors.append("rateLimit must be an object if present.")
        else:
            if "hit" in rate_limit and not isinstance(rate_limit["hit"], bool):
                errors.append("rateLimit.hit must be a boolean if present.")
            if "scope" in rate_limit and rate_limit["scope"] is not None and not is_nonempty_string(rate_limit["scope"]):
                errors.append("rateLimit.scope must be a non-empty string if present.")
            if "retryAfterSeconds" in rate_limit and rate_limit["retryAfterSeconds"] is not None:
                if not isinstance(rate_limit["retryAfterSeconds"], int) or rate_limit["retryAfterSeconds"] < 0:
                    errors.append("rateLimit.retryAfterSeconds must be an integer >= 0 if present.")

    metadata = data.get("metadata")
    if metadata is not None:
        if not isinstance(metadata, dict):
            errors.append("metadata must be an object if present.")
        else:
            for field in ("createdAt", "source"):
                if field in metadata and not is_nonempty_string(metadata[field]):
                    errors.append(f"metadata.{field} must be a non-empty string if present.")

    return errors, warnings


def derive_counts_from_findings(findings: List[Dict[str, Any]]) -> Dict[str, int]:
    counts = {k: 0 for k in ALLOWED_SEVERITIES}

    for finding in findings:
        if finding["status"] != "open":
            continue
        counts[finding["severity"]] += 1

    return counts


def build_summary(derived_counts: Dict[str, int]) -> Dict[str, int]:
    total = sum(derived_counts.values())
    blocking = (
        derived_counts["critical"]
        + derived_counts["high"]
        + derived_counts["medium"]
    )

    return {
        "critical": derived_counts["critical"],
        "high": derived_counts["high"],
        "medium": derived_counts["medium"],
        "low": derived_counts["low"],
        "unknown": derived_counts["unknown"],
        "totalFindings": total,
        "blockingCount": blocking,
    }


def compare_with_provided_summary(
    provided: Dict[str, Any] | None,
    derived: Dict[str, int],
) -> List[str]:
    warnings: List[str] = []
    if not provided:
        return warnings

    for field, derived_value in derived.items():
        if field in provided and provided[field] != derived_value:
            warnings.append(
                f"summary.{field}={provided[field]} does not match derived value {derived_value}."
            )

    return warnings


def build_recommendation(summary: Dict[str, int], cycle: int, max_cycles: int) -> Dict[str, Any]:
    if summary["totalFindings"] == 0:
        return {
            "action": "stop-clean",
            "reason": "No open validation findings remain.",
        }

    if summary["blockingCount"] > 0:
        if cycle < max_cycles:
            return {
                "action": "another-pass-recommended",
                "reason": (
                    f"{summary['blockingCount']} blocking finding(s) remain and "
                    f"another bounded pass is still allowed."
                ),
            }
        return {
            "action": "stop-cycle-limit",
            "reason": (
                f"{summary['blockingCount']} blocking finding(s) remain, "
                f"but the workflow is already at cycle limit {max_cycles}."
            ),
        }

    if summary["low"] > 0 and summary["unknown"] == 0:
        return {
            "action": "stop-nits-only",
            "reason": "Only low-priority findings remain.",
        }

    return {
        "action": "manual-review-needed",
        "reason": "Only non-blocking or unknown findings remain; manual adjudication is safer.",
    }


def apply_rate_limit_override(
    recommendation: Dict[str, Any],
    rate_limit: Dict[str, Any] | None,
) -> Dict[str, Any]:
    if not rate_limit or not rate_limit.get("hit"):
        return recommendation

    scope = rate_limit.get("scope") or "validation"
    retry_after = rate_limit.get("retryAfterSeconds")

    reason = f"Validation is rate-limited for the current run ({scope})."
    if retry_after is not None:
        reason += f" Retry after approximately {retry_after} seconds."

    return {
        "action": "stop-validation-rate-limit",
        "reason": reason,
    }


def sample_findings(findings: List[Dict[str, Any]], limit: int = 10) -> List[Dict[str, Any]]:
    result = []
    for finding in findings:
        if finding["status"] != "open":
            continue
        result.append(
            {
                "id": finding["id"],
                "severity": finding["severity"],
                "kind": finding["kind"],
                "title": finding["title"],
                "file": finding.get("file"),
                "line": finding.get("line"),
                "sourceIssueId": finding.get("sourceIssueId"),
            }
        )
        if len(result) >= limit:
            break
    return result


def print_human(result: Dict[str, Any]) -> None:
    s = result["summary"]
    r = result["recommendation"]

    print(f"Validation summary for: {result['path']}")
    print(f"Cycle: {result['cycle']} / {result['maxCycles']}")
    print("")
    print(f"Critical: {s['critical']}")
    print(f"High:     {s['high']}")
    print(f"Medium:   {s['medium']}")
    print(f"Low:      {s['low']}")
    print(f"Unknown:  {s['unknown']}")
    print(f"Total:    {s['totalFindings']}")
    print(f"Blocking: {s['blockingCount']}")
    print("")
    print(f"Recommended action: {r['action']}")
    print(f"Reason: {r['reason']}")

    if result["warnings"]:
        print("\nWarnings:")
        for w in result["warnings"]:
            print(f"- {w}")

    if result["sampleFindings"]:
        print("\nSample open findings:")
        for f in result["sampleFindings"]:
            loc = ""
            if f.get("file"):
                loc = f" [{f['file']}"
                if f.get("line") is not None:
                    loc += f":{f['line']}"
                loc += "]"
            print(f"- ({f['severity']}) {f['title']}{loc}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Summarize a strict validation-result JSON artifact."
    )
    parser.add_argument("validation_result", help="Path to validation-result JSON.")
    parser.add_argument(
        "--max-cycles",
        type=int,
        default=3,
        help="Maximum allowed remediation cycles (default: 3).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON output.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.max_cycles < 1:
        print("--max-cycles must be >= 1", file=sys.stderr)
        return 2

    try:
        data = load_json(args.validation_result)
    except FileNotFoundError:
        print(f"Validation file not found: {args.validation_result}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as exc:
        print(f"Invalid JSON: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"Failed to read validation result: {exc}", file=sys.stderr)
        return 2

    errors, warnings = validate_validation_result(data)
    if errors:
        payload = {
            "valid": False,
            "errors": errors,
            "warnings": warnings,
        }
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print("Validation-result schema errors:", file=sys.stderr)
            for e in errors:
                print(f"- {e}", file=sys.stderr)
        return 2

    findings = data["findings"]
    derived_counts = derive_counts_from_findings(findings)
    derived_summary = build_summary(derived_counts)
    warnings.extend(compare_with_provided_summary(data.get("summary"), derived_summary))

    cycle = data["cycle"]
    recommendation = build_recommendation(derived_summary, cycle, args.max_cycles)
    recommendation = apply_rate_limit_override(recommendation, data.get("rateLimit"))

    result = {
        "path": args.validation_result,
        "validationVersion": data["validationVersion"],
        "tool": data["tool"],
        "pr": data["pr"],
        "cycle": cycle,
        "maxCycles": args.max_cycles,
        "summary": derived_summary,
        "recommendation": recommendation,
        "sampleFindings": sample_findings(findings),
        "rateLimit": data.get("rateLimit"),
        "warnings": warnings,
    }

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print_human(result)

    return 0


if __name__ == "__main__":
    sys.exit(main())
