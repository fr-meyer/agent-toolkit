---
name: repository-similarity-preflight
description: Use this skill before starting planned work on a repository, creating a branch, opening an issue or pull request, or making another repository change when duplicate or related work may already exist. Apply it to repository discovery, issue/PR similarity checks, continuation work, and canonical-thread routing. Do not use it as a substitute for code review, CI debugging, or authorization to publish or mutate external repositories.
---

# Repository Similarity Preflight

## Goal

Prevent duplicate repository work by running a read-only, fail-closed similarity screen before repo work becomes ready/running, before branch or checkout mutation, and again immediately before an external GitHub write.

This skill is **generic-shared**. It must work across repositories and hosts without embedding private incidents, personal context, local paths, credentials, or repository-specific issue numbers in production logic.

## Scope receipt

- **Reusable invariant:** search the repository's existing public or approved-private work, classify overlap, and route duplicate/related work to the canonical item.
- **Collector boundary:** the agent or an approved GitHub/search adapter gathers results; the bundled helper validates and classifies sanitized evidence deterministically.
- **Local adapter:** repository-specific authentication, GitHub broker selection, Workboard integration, and source queries remain in the calling workflow.
- **External writes:** never implied by a passing discovery report; issue, Discussion, PR, comment, push, and merge remain separately authorized.

## When to run

Run the preflight at all of these gates:

1. Before specifying a repository task as ready or running.
2. Before creating or checking out a branch, worktree, or other repository-mutating state.
3. Immediately before creating or editing an issue, Discussion, PR, comment, push, or merge.
4. Re-run when the intended change, target repository, base revision, or search evidence changes.

## Required inputs

Prepare a JSON input using the schema in `references/schema.md`:

- repository host, owner/name, explicit `public` or `private` visibility, revision/base revision, and planned branch;
- sanitized public intent title, summary, target, terms, and behavior/API names;
- search authentication status and complete/not-applicable source evidence for applicable Issues, Discussions, PRs, releases/changelogs, docs, code, and tests;
- each candidate's stable URL or number, state, title, relationship, and short matching reason.

For public repositories, use synthetic/public wording in queries. For private repositories, use only the approved authenticated lane and record sanitized evidence. If access fails, record the failure; do not report “no match.”

## Collection procedure

1. Establish the repository identity and visibility from a trusted source.
2. Establish the current revision/base revision and planned branch without mutating the checkout.
3. Search current and recent Issues, Discussions, pull requests, release notes/changelogs, documentation, relevant source, and tests. Use exact terms, synonyms, proposed behavior names, and API names.
4. Preserve only bounded, sanitized candidate metadata. Do not put raw prompts, transcripts, host paths, Workboard-private data, personal identifiers, credentials, or secrets into public search queries or evidence.
5. Classify every meaningful candidate as one of:
   - `duplicate` — same requested work or same defect/feature;
   - `directly_related` — materially overlapping implementation or continuation;
   - `superseded` — older/closed item whose canonical replacement still governs the work;
   - `unrelated` — search hit without material overlap.
6. Give every duplicate or related candidate a stable canonical URL or issue/PR number. If it has no route, the gate is blocked.
7. Run the bundled helper and retain both its JSON report and Markdown evidence.

## Deterministic helper

From this skill directory, run:

```bash
python3 scripts/repository_similarity_preflight.py \
  --input <sanitized-input.json> \
  --output <preflight-report.json> \
  --markdown-output <preflight-evidence.md> \
  --pretty
```

Use `--external-write` only at the final external-write gate, and provide an explicit scoped approval in the input. A discovery pass alone never authorizes a write.

Exit codes are fail-closed:

- `0` — `pass` or justified `not-applicable`;
- `2` — `related` and canonical routing is required;
- `3` — `duplicate` and new issue/PR creation is prohibited;
- `4` — `blocked` because evidence, privacy, authentication, canonical routing, or approval is incomplete;
- `5` — invalid input or helper failure.

## Gate decisions

- **`pass`:** no duplicate or strong related match was found across complete evidence. Continue only within the separately authorized local task.
- **`related`:** stop new issue/PR creation; inspect the canonical item and ask whether an update/comment or continuation is wanted.
- **`duplicate`:** do not create another issue/PR. Route to the existing canonical item.
- **`blocked`:** stop. Fix evidence, authentication, visibility, redaction, source coverage, or approval before continuing.
- **`not-applicable`:** use only when the task genuinely has no repository-work surface, with a reason.

A closed or superseded item is not automatically irrelevant. If it remains the canonical history or replacement route, classify it as `superseded` and return `related`.

## GitHub and bot verification

Optional GitHub/ClawSweeper/CI hints may enrich discovery but are never the sole gate. A normal issue comment is not proof that a bot review ran. If a bot review is explicitly triggered, record the trigger URL and later verify durable review evidence such as the bot comment, reviewed revision/timestamp, labels, or run record. Never create a duplicate issue merely to provoke a bot review.

Use `github-pr-preflight` as an additional gate for public PR branch hygiene, public prose, diffs, patches, and live PR metadata. This skill answers a different question: whether the intended repository work already exists or is materially related.

## Safety and privacy

- Treat unknown repository visibility as blocked until confirmed.
- Do not echo unsafe raw values in reports; the helper redacts obvious emails, phone numbers, local paths, bearer tokens, credentials, and secret query parameters and blocks the gate when they appear in evidence fields.
- Do not bypass a duplicate/related/blocked status with an automatic override.
- Any human override must be explicit, scoped, recorded, and separately authorized; it does not erase the similarity evidence.

## Validation

Before calling the work complete:

1. Validate the skill with `skills-ref validate skills/repository-similarity-preflight` (or `agentskills validate ...`).
2. Run the bundled tests.
3. Run the helper against the public continuation fixture and verify it returns `duplicate` with the canonical issue route.
4. Verify the report and Markdown evidence contain no raw sensitive values.
5. Record the schema version, status, evidence paths, source-access result, and any canonical route in the task/Workboard proof.

## Resources

Read only when needed:

- `references/schema.md` — exact input/output contract and status semantics.
- `references/eval-prompts.json` — trigger and near-miss examples for skill evaluation.

Run only when needed:

- `scripts/repository_similarity_preflight.py` — deterministic validation, redaction, classification, and evidence generation.
