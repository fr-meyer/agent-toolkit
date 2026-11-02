# Repository similarity preflight

`repository-similarity-preflight` is the shared, deterministic gate for deciding
whether planned work is genuinely new repository work. It complements
`github-pr-preflight`: similarity answers **whether the work already exists**;
PR preflight answers **whether a proposed public PR is safe and branch-valid**.

## Gate placement

Run the similarity preflight:

1. before a repository task is specified as `ready` or `running`;
2. before branch creation, checkout, worktree creation, or other repository
   mutation;
3. immediately before an issue, Discussion, PR, comment, push, or merge;
4. again after a material change to the target, base revision, or search terms.

The first three gates may use the same evidence only when repository identity,
visibility, revision, intent, and search results are unchanged. Otherwise collect
fresh evidence.

## Evidence contract

The collector/search adapter creates a sanitized JSON input. It must identify:

- repository host, owner/name, explicit visibility, revision, and planned branch;
- the public technical intent, target surface, exact terms, synonyms, and
  behavior/API names;
- authentication status and complete or explicitly not-applicable source
  coverage for Issues, Discussions, PRs, releases/changelogs, docs, code, and
  tests;
- bounded candidate metadata, stable URL/number, state, relationship, and
  reason for the match.

The bundled helper emits the canonical schema
`repository-similarity-preflight/v1` as JSON and Markdown. It does not perform
network searches. This keeps source access replaceable and makes the safety
classification deterministic and testable.

## Decision and routing policy

| Status | Meaning | Next action |
|---|---|---|
| `pass` | Complete evidence found no duplicate or strong related work. | Continue only within the separately authorized local task. |
| `related` | A directly related or superseded item exists. | Stop new issue/PR creation; inspect and route to the canonical item. |
| `duplicate` | The requested work already exists. | Do not create another issue/PR; use the canonical URL/number. |
| `blocked` | Search/auth/source/visibility/privacy/routing/approval evidence is incomplete. | Stop and repair the gate. |
| `not-applicable` | No repository-work surface exists. | Continue only with the recorded reason. |

Closed or superseded work remains relevant when it is the canonical history or
replacement route. A related or duplicate candidate without a stable route is
`blocked`, not a pass.

## Override and external-write proof

Discovery never authorizes a write. A human or explicitly authorized workflow
must separately approve the exact external-write scope. The helper's
`--external-write` mode returns `allowed: true` only when the similarity status
is a clean `pass` and the input contains an explicit scoped approval. Duplicate,
related, and blocked states cannot be bypassed automatically.

A task/Workboard proof record should include:

- schema version and preflight status;
- repository identity, visibility, revision, and branch;
- search source statuses and authentication mode;
- sanitized JSON/Markdown evidence paths or immutable artifact references;
- canonical URL/number when routed;
- redaction findings and blocker details, if any;
- separate external-write approval identity, scope, and time when a write is
  authorized.

Do not store raw private prompts, transcripts, host paths, Workboard-private
fields, credentials, or secrets in the proof.

## Bot and CI signals

GitHub/ClawSweeper/CI hints can improve discovery but cannot be the sole gate.
A normal comment is not proof that a bot review ran. If a bot is explicitly
triggered, record the trigger URL and verify a durable result (bot comment,
reviewed revision/timestamp, labels, or run record). Never create a duplicate
issue to provoke a bot review.

## Local command

```bash
python3 skills/repository-similarity-preflight/scripts/repository_similarity_preflight.py \
  --input sanitized-input.json \
  --output preflight-report.json \
  --markdown-output preflight-evidence.md \
  --pretty
```

Exit codes are `0` for `pass`/`not-applicable`, `2` for `related`, `3` for
`duplicate`, `4` for `blocked`, and `5` for invalid input/helper failure.
