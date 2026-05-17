#!/usr/bin/env python3
"""Check byte/character budgets for context-loaded files.

The hard gate is byte-based by default because bootstrap/context warnings are
commonly emitted from serialized byte sizes. Character counts are reported as a
secondary diagnostic.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional


def measure(path: Path) -> Dict[str, Any]:
    data = path.read_bytes()
    text = data.decode("utf-8", errors="replace")
    return {
        "path": str(path),
        "bytes": len(data),
        "characters": len(text),
        "lines": text.count("\n") + (0 if not text else 1 if not text.endswith("\n") else 0),
    }


def status(size: int, limit: int, target: Optional[int]) -> str:
    if size > limit:
        return "over-limit"
    if target is not None and size > target:
        return "over-target"
    return "ok"


def selected_size(result: Dict[str, Any], unit: str) -> int:
    if unit == "bytes":
        return int(result["bytes"])
    if unit == "characters":
        return int(result["characters"])
    raise ValueError(f"unsupported unit: {unit}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check context/bootstrap file sizes against a hard byte or character limit."
    )
    parser.add_argument("paths", nargs="+", help="Files to check")
    parser.add_argument(
        "--limit",
        type=int,
        default=12000,
        help="Hard limit in the selected unit. Exit non-zero when any file exceeds it. Default: 12000",
    )
    parser.add_argument(
        "--target",
        type=int,
        default=10000,
        help="Preferred target in the selected unit. Files above target but below limit are warnings. Default: 10000",
    )
    parser.add_argument(
        "--unit",
        choices=("bytes", "characters"),
        default="bytes",
        help="Unit to enforce for limit and target. Default: bytes",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON instead of human-readable lines.",
    )
    args = parser.parse_args()

    if args.limit <= 0:
        parser.error("--limit must be positive")
    if args.target is not None and args.target <= 0:
        parser.error("--target must be positive")
    if args.target is not None and args.target > args.limit:
        parser.error("--target must be less than or equal to --limit")

    results: List[Dict[str, Any]] = []
    exit_code = 0

    for raw_path in args.paths:
        path = Path(raw_path)
        if not path.exists():
            result = {"path": raw_path, "status": "missing", "error": "file does not exist"}
            exit_code = 2
        elif not path.is_file():
            result = {"path": raw_path, "status": "not-file", "error": "path is not a file"}
            exit_code = 2
        else:
            result = measure(path)
            result["limit"] = args.limit
            result["target"] = args.target
            size = selected_size(result, args.unit)
            result["unit"] = args.unit
            result["measured"] = size
            result["status"] = status(size, args.limit, args.target)
            if result["status"] == "over-limit":
                exit_code = 1
        results.append(result)

    if args.json:
        print(json.dumps({"results": results, "ok": exit_code == 0}, indent=2, ensure_ascii=False))
    else:
        for result in results:
            path = result["path"]
            state = result["status"]
            if "bytes" in result:
                print(
                    f"{state}: {path} — {result['bytes']} bytes, "
                    f"{result['characters']} chars, {result['lines']} lines; "
                    f"checked {result.get('measured', '?')} {result.get('unit', args.unit)} "
                    f"(target {args.target}, limit {args.limit})"
                )
            else:
                print(f"{state}: {path} — {result.get('error', 'unknown error')}")

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
