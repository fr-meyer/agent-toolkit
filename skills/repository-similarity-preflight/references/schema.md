# Repository similarity preflight schema

Schema identifier: `repository-similarity-preflight/v1`

The bundled helper accepts a JSON object. The collector may add fields, but the
helper emits only the bounded/sanitized fields described here.

## Input

```json
{
  "schema_version": "repository-similarity-preflight/v1",
  "repository": {
    "host": "github.com",
    "owner": "example",
    "name": "project",
    "visibility": "public",
    "revision": "<base-or-current-revision>",
    "branch": "planned/technical-change"
  },
  "intent": {
    "title": "Technical change title",
    "summary": "Public, sanitized description of the intended change.",
    "target": "code|docs|config|issue|pull_request|other",
    "terms": ["exact phrase", "synonym"],
    "behavior_names": ["public API or behavior name"]
  },
  "search": {
    "auth": {"status": "anonymous"},
    "queries": ["technical public query"],
    "required_source_kinds": [
      "issues", "discussions", "pull_requests", "releases", "docs", "code", "tests"
    ],
    "sources": [
      {
        "kind": "issues",
        "status": "complete",
        "items": [
          {
            "number": 42,
            "url": "https://github.com/example/project/issues/42",
            "state": "open",
            "title": "Existing work",
            "relationship": "duplicate",
            "reason": "Same requested behavior and target API."
          }
        ]
      },
      {
        "kind": "discussions",
        "status": "not_applicable",
        "reason": "Repository has Discussions disabled."
      }
    ]
  },
  "external_write": {
    "approval": {
      "authorized": true,
      "scope": "create pull request for this technical change"
    }
  }
}
```

### Required repository fields

`host`, `owner`, `name`, `visibility`, `revision` (or `base_revision`), and
`branch` are required. Visibility must be exactly `public` or `private`.
Unknown visibility is a blocker.

### Search authentication

- Public repositories accept `available`, `anonymous`, or `not_required`.
- Private repositories accept only `approved_authenticated`.
- Other values, including `unavailable` and `failed`, block the gate.

### Search sources

Each applicable source must have `status: complete` and an `items` list. A
source may use `status: not_applicable` only with a reason. Missing required
source kinds block the gate. Source kinds can be narrowed by the caller when a
repository genuinely lacks a surface, but the omission must be explicit and
justified.

Candidate `relationship` values:

- `duplicate`
- `directly_related`
- `superseded`
- `unrelated`

Duplicate and related/superseded candidates require a stable `url`,
`canonical_url`, or `number`; otherwise the gate is blocked. If relationship is
omitted, the helper performs only conservative token-overlap inference and
records the inferred match type.

## Output

The helper emits:

```json
{
  "schema_version": "repository-similarity-preflight/v1",
  "status": "pass|related|duplicate|blocked|not-applicable",
  "reason": "decision explanation",
  "repository": {},
  "intent": {},
  "search": {
    "auth": {"status": "..."},
    "queries": [],
    "sources": [{"kind": "issues", "status": "complete", "item_count": 1}]
  },
  "matches": [],
  "checks": [],
  "blockers": [],
  "warnings": [],
  "redaction": {"findings": []},
  "external_write": {"requested": false, "allowed": false}
}
```

Status precedence is safety-first: `blocked` overrides `duplicate` or
`related` when evidence or approval is incomplete; otherwise `duplicate`
precedes `related`, which precedes `pass`.

`external_write.allowed` is true only when `--external-write` is requested, the
similarity status is `pass`, and an explicit authorized approval with a
non-empty scope is present. A normal pass without `--external-write` remains
discovery-only.

## Privacy contract

Search queries, public intent text, and candidate explanations are treated as
public evidence. The helper redacts obvious email addresses, phone numbers,
local POSIX/Windows paths, bearer tokens, credential assignments, and secret
query parameters. Any such finding blocks the gate. Raw candidate bodies are
not copied into the output; only bounded metadata and sanitized reasons are
retained.
