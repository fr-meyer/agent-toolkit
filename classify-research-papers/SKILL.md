---
name: classify-research-papers
description: Use this skill when the user needs to classify one or more research papers within a two-layer taxonomy, either by applying an existing taxonomy or by creating and locking one first when no usable taxonomy exists. Apply it to paper-by-paper classification, misclassification review, taxonomy-gap analysis, adjudication between competing paths, and taxonomy design for a new paper corpus when the end goal is stable two-layer classification. Do not use it for paper discovery alone, whole-paper summarization, or general literature-review synthesis unrelated to taxonomy design or classification.
---

# Classify Research Papers

## Overview

Classify papers against a Level 1 / Level 2 taxonomy in a way that is auditable, stable, and reproducible.

When a usable taxonomy already exists, apply it.
When no usable taxonomy exists, create and lock one first, then classify against that locked version.

Optimize for the paper's **primary intellectual contribution**, not for keyword overlap, venue, or incidental application context.

## Default Modes

### 1. Existing-taxonomy mode

Use this mode when an active taxonomy already exists and is clear enough to govern decisions.

Goal:
- assign exactly one primary Level 1 collection and one primary Level 2 subcollection for each paper
- review misclassifications, borderline cases, and taxonomy-gap candidates against the locked taxonomy version

### 2. Taxonomy-creation-first mode

Use this mode when no usable taxonomy exists, or when the provided taxonomy is so weak, inconsistent, or outdated that it should not govern production classification.

Read:
- `references/taxonomy-creation-from-scratch-playbook.md`
- `references/taxonomy-reference-template.md`

In this mode, do **not** jump directly to batch classification. First create and lock a usable two-layer taxonomy version, then classify papers against it.

### 3. Multi-agent mode

Use this mode only when the environment explicitly supports worker or subagent execution, the taxonomy version is locked, and the task is large or ambiguity-heavy enough that parallel review is worth the merge overhead.

Read:
- `references/multi-agent-operation.md`
- `references/multi-agent-handoff-schema.md`

If the environment does not support worker execution, remain in single-agent mode and work serially.

## Example Prompts

- Classify these papers into my taxonomy.
- Check whether these papers are misclassified.
- Decide whether this paper belongs in subcollection A or B.
- Write a classification decision record for this paper.
- Review this borderline paper and tell me whether it exposes a taxonomy gap.
- Reclassify these papers using taxonomy version 2026-Q1.
- No usable taxonomy exists yet — design a two-layer taxonomy for this corpus, lock version 1, then classify the pilot set.
- Our current taxonomy is inconsistent. Rebuild it into a usable two-layer tree and then classify these papers against the locked version.
- If worker agents are available, split this audit batch across them and route boundary cases to review.

Do not use this skill for requests like:
- find this paper in my library
- summarize this paper in detail
- compare ten papers as a literature review unrelated to taxonomy work
- organize arbitrary non-paper files or folders

## Required Inputs

Gather as many of these as the task supports.

### For existing-taxonomy mode
- active taxonomy reference document
- taxonomy version
- paper title
- abstract
- keywords
- authors / year / venue
- full text or key body sections when needed
- precedent log or prior adjudications, if available
- existing classification, if this is a review or reclassification task

### For taxonomy-creation-first mode
- corpus scope and purpose
- sponsor or retrieval goal
- representative paper sample or corpus slice
- paper metadata and abstracts for the discovery set
- any existing label drafts, however incomplete
- downstream operating constraints, if any

If the taxonomy reference is missing, outdated, or too vague to distinguish neighboring subcollections, do **not** pretend the boundary is clear. Either switch to taxonomy-creation-first mode or explicitly escalate the blocker.

## Authority Order

When an active taxonomy version exists, use this order whenever sources conflict:

1. active taxonomy reference document
2. explicit precedent / prior adjudication
3. the paper's actual content
4. informal habits, spreadsheet comments, or prior guesses

The taxonomy reference is the primary authority. Chat history, old habits, and loose keyword matches do not override it.

If no usable taxonomy exists yet, create and lock one before using this authority order for production classification.

## Read These References As Needed

Start lean. Read only the files needed for the current job.

- `references/paper-classification-tutorial.md`
  - Read for the chronological single-paper classification workflow.
  - Use first for ordinary classification and misclassification review tasks.

- `references/taxonomy-reference-template.md`
  - Read when you need the canonical structure of a good taxonomy reference document.
  - Use to detect missing definitions, weak boundaries, governance gaps, or poor include/exclude rules.

- `references/taxonomy-creation-from-scratch-playbook.md`
  - Read when no usable taxonomy exists yet, or when the current taxonomy is too weak to govern classification safely.
  - Use it to create, pilot, stabilize, and lock a two-layer taxonomy before batch classification.

- `references/workflow-and-communication-playbook.md`
  - Read when the task involves multi-role operations, handoffs, queues, SLA logic, escalation ownership, or adjudication flow.

- `references/operating-artifact-template-library.md`
  - Read when the user wants a formal decision record, review handoff, escalation ticket, precedent entry, QA form, or governance artifact.

- `references/agent-persona-prompts.md`
  - Read when instantiating role-specific agents or simulating analyst / QA / taxonomy-lead perspectives.

- `references/classification-team-blueprint.md`
  - Read when the user asks about staffing, throughput, or team design for classification operations.

- `references/leadership-roles-addendum.md`
  - Read when decision rights, single-point accountability, or team-lead structure matters.

- `references/multi-agent-operation.md`
  - Read when the task involves parallel classification, reviewer routing, coordinator/worker orchestration, or environment-conditioned subagent use.

- `references/multi-agent-handoff-schema.md`
  - Read when assigning papers to workers, packaging handoffs, validating worker outputs, or merging multiple agent results.

- `references/package-index.md`
  - Read only when you need the source package map.

- `references/output-examples.md`
  - Read when you want a concrete normal-case or escalation-case decision record format.

- `references/eval-prompts.json`
  - Read when testing trigger boundaries or refining the frontmatter description.

## Portability Notes

- Use the user's active taxonomy artifact and terminology as the system of record; do not assume Zotero, spreadsheets, or a specific library manager unless the task explicitly provides one.
- If precedent logs or prior adjudications are unavailable, proceed from the taxonomy reference plus paper evidence and explicitly note that precedent was unavailable.
- Default to plain Markdown or YAML outputs unless the user requests a system-specific artifact format.
- Do not assume subagents, worker sessions, or thread binding exist in every host. Treat worker use as conditional on environment availability.

## Core Decision Rules

Apply these rules in order:

1. Classify by the paper's **primary intellectual contribution**.
2. Prefer the **author-stated objective** over incidental details.
3. Assign **one primary Level 1 collection** and **one primary Level 2 subcollection** whenever the active taxonomy supports a clean fit.
4. Use the **deepest valid node**; do not stop at Level 1 if a correct Level 2 exists.
5. Prefer **direct evidence** over keyword matching.
6. Compare the chosen path against the **strongest rejected alternative** when ambiguity exists.
7. Escalate ambiguity instead of forcing fake certainty.
8. If no usable taxonomy exists, create and lock one before large-scale classification begins.

Default evidence order:
1. title
2. abstract
3. introduction / problem statement
4. method section
5. experiments / evaluation
6. conclusion

If title and abstract are not enough, inspect deeper sections before deciding. Do not inflate confidence from weak metadata.

## Classification Workflow

### 1. Lock the operating frame

Identify and state:
- whether a usable taxonomy already exists
- the active taxonomy version, if one exists
- whether this is taxonomy creation, new classification, audit, reclassification, or adjudication
- whether the task should run in single-agent or multi-agent mode
- what evidence is actually available

If no usable taxonomy exists, switch to taxonomy-creation-first mode and lock a taxonomy version before production classification.

### 2. Understand the paper or corpus before mapping it

For paper-level work, extract the minimum needed facts:
- core research problem
- primary object of study
- main method or contribution type
- domain / application context
- any clues that are merely secondary or incidental

Ask:
> What is this paper mainly about?

Not:
> What words appear most often?

For taxonomy-creation-first work, start from:
- corpus scope
- sponsor purpose
- discovery sample
- repeated conceptual clusters
- likely collisions and boundary problems

### 3. If needed, create and lock the taxonomy first

When no usable taxonomy exists:
- define the governing basis of classification
- build a discovery sample
- draft Level 1 and Level 2 labels
- write definition cards and boundary notes
- pilot the taxonomy on a sample set
- revise until stable enough for production use
- lock a taxonomy version before full-batch classification

Use `references/taxonomy-creation-from-scratch-playbook.md` for the full procedure.

### 4. Narrow Level 1, then Level 2

First identify the best Level 1 collection.
Then choose the strongest Level 2 subcollection inside that Level 1.

When two Level 2 nodes look plausible, test them against:
- include rules
- exclude rules
- boundary notes
- precedent
- whether one option better reflects the central contribution

### 5. Evaluate the strongest alternative

Do not stop at the first plausible fit.

For each paper, explicitly consider at least one competing path when ambiguity exists:
- strongest alternate Level 1 / Level 2
- why it initially looks plausible
- why it loses to the selected path

If two candidates remain equally strong after reading the relevant evidence, escalate or mark as taxonomy-gap rather than forcing a tidy answer.

### 6. Assign confidence honestly

Use this rubric:

- **High**: one path clearly fits and the strongest alternative is clearly weaker
- **Medium**: best fit exists, but a neighboring path remains plausible
- **Low**: evidence is incomplete, boundaries are unclear, or multiple paths remain equally strong

Low confidence usually means review or escalation is needed.

### 7. Decide the outcome type

Use one of these outcomes:
- `proposed`
- `accepted`
- `returned_for_rework`
- `escalated`
- `taxonomy_gap`
- `needs_more_evidence`

Choose `taxonomy_gap` when the paper fits poorly across the current taxonomy and the problem is structural, not merely uncertain reading.

### 8. Produce an auditable output

At minimum, return:

```yaml
paper_id:
task_type:
taxonomy_version:
decision_status:
main_collection:
subcollection:
confidence:
primary_evidence:
secondary_evidence:
strongest_rejected_alternative:
rationale:
flags:
escalation_reason:
next_owner:
```

Use one consistent key set across papers. If no meaningful competing path exists, set `strongest_rejected_alternative` to `none` rather than omitting the field.

If the user wants a formal operating artifact, load `references/operating-artifact-template-library.md` and use the appropriate template. For concrete examples of both a straightforward decision and an escalation case, read `references/output-examples.md`.

## Multi-Agent Operation

Use multi-agent mode only when **all** of the following are true:
- the environment explicitly supports worker execution
- the taxonomy version is locked for the active batch
- the task has at least 4 papers, or is ambiguity-heavy enough to justify orchestration overhead
- the parent can collect and normalize worker outputs

Stay in single-agent mode when any of the following are true:
- worker execution is unavailable
- the task has only 1-3 straightforward papers
- the taxonomy version is not locked yet
- the task is a simple one-paper adjudication

Default worker sizing, subject to host limits:
- **4-6 papers** → up to **2 classifier workers**
- **7-12 papers** → up to **3 classifier workers**
- **13+ papers** → up to **4 classifier workers**
- add up to **1 QA / adjudication worker** only when needed
- add up to **1 taxonomy-lead worker** only when needed

Never exceed host-environment limits, never spawn more workers than work units, and do not assign the same paper to multiple classifier workers unless double-review is intentional.

For full routing, merge, and governance details, read `references/multi-agent-operation.md`.

### Multi-Agent Output Contract

When worker mode is used, include these fields in addition to the ordinary decision record:

```yaml
parent_batch_id:
paper_position:
worker_role:
source_evidence_scope:
review_required:
review_reason:
```

Use the detailed schemas in `references/multi-agent-handoff-schema.md` when packaging assignments or validating worker outputs.

### Multi-Agent Conflict Routing

Use these defaults:
- if classifier and QA agree, accept the shared result
- if classifier and QA disagree on Level 2 but agree on Level 1, QA may revise directly only if the issue is not structural; otherwise escalate to taxonomy lead
- if classifier and QA disagree on Level 1, always escalate to taxonomy lead
- if the problem is inadequate evidence, return `needs_more_evidence`
- if the problem is structural mismatch, return `taxonomy_gap`
- never compress disagreement into silent fake consensus

## Multi-Paper Handling

When classifying multiple papers:

- preserve the user's order
- classify each paper independently
- do not let one paper's topic bleed into another decision
- note repeated ambiguity patterns across papers
- call out recurring taxonomy problems separately from paper-level decisions
- return one decision record per paper, then a short cross-paper notes block only when it adds value

If reviewing existing classifications, separate:
- clearly correct placements
- clearly incorrect placements
- borderline cases needing adjudication
- cases that suggest a taxonomy gap or boundary rewrite

## Misclassification Review Guidance

When the task is to verify whether papers are correctly classified:

1. identify the current assigned path
2. test it against the taxonomy definition and boundary rules
3. read enough of the paper to verify the true primary contribution
4. decide whether to keep, move, or escalate
5. explain why the current location fails if you recommend a move

Do not recommend a move based on superficial keyword overlap alone.

## Escalation Triggers

Escalate when any of these are true:

- no valid subcollection fits cleanly
- two or more subcollections are equally strong
- taxonomy reference conflicts with precedent
- metadata or paper access is too incomplete to classify safely
- the paper seems duplicated, corrupted, withdrawn, or out of scope
- the case appears to require a new tag, split, merge, or boundary rewrite
- the taxonomy itself is too weak or inconsistent to govern production classification

When escalating, name the exact issue type instead of saying only that the case is hard.

## If The User Wants Team-Oriented or Multi-Agent Operation

For multi-role or worker-based workflows:

1. read `references/workflow-and-communication-playbook.md`
2. read `references/multi-agent-operation.md`
3. read `references/multi-agent-handoff-schema.md`
4. read `references/agent-persona-prompts.md`
5. read `references/classification-team-blueprint.md` if staffing or throughput matters
6. read `references/leadership-roles-addendum.md` if approval rights or lead structure matters

Use those references to separate analyst work, QA/adjudication, taxonomy governance, and operations.

## Final Quality Checks

Before finishing any taxonomy or classification task, verify all of the following:

- the selected Level 1 / Level 2 path actually exists in the active taxonomy version
- the rationale is anchored in direct paper evidence rather than keyword overlap
- the strongest rejected alternative is the nearest plausible competitor, not a strawman
- the confidence level matches the completeness of the evidence and the clarity of the boundary
- any `escalated` or `taxonomy_gap` outcome names the exact blocker or structural issue
- if taxonomy creation was required, the governing basis, label definitions, and locked version are explicit before large-scale classification starts

## Never Do This

- Never classify from keywords alone when paper content is available.
- Never let venue, author affiliation, or fashionable terminology drive the decision by itself.
- Never assign multiple primary locations unless the governing taxonomy explicitly allows it.
- Never invent paper facts, definitions, precedents, or taxonomy labels during production classification.
- Never silently reinterpret unclear taxonomy boundaries as if they were settled.
- Never hide ambiguity behind inflated confidence.
- Never claim a taxonomy gap without checking whether an existing node already fits.
- Never start large-scale batch classification without a locked taxonomy version.
- Never assume worker execution exists or exceed host limits when using multi-agent mode.
- Never treat chat as the system of record when the task requires a durable artifact.
