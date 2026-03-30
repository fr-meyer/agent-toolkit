---
name: classify-research-papers
description: Use this skill when the user needs to classify one or more research papers into an existing two-layer taxonomy, verify whether papers are correctly classified, adjudicate between competing taxonomy paths, or prepare evidence-based classification records. Apply it to title/abstract/full-text classification work where the taxonomy reference document is the primary authority and each paper must receive exactly one primary main collection and one primary subcollection based on its primary intellectual contribution rather than incidental keywords. Do not use it for paper discovery alone, whole-paper summarization, or designing an entire taxonomy from scratch.
---

# Classify Research Papers

## Overview

Classify papers against an existing Level 1 / Level 2 taxonomy in a way that is auditable, stable, and reproducible.

Optimize for the paper's **primary intellectual contribution**, not for keyword overlap, venue, or incidental application context.

## Example Prompts

- Classify these papers into my taxonomy.
- Check whether these papers are misclassified.
- Decide whether this paper belongs in subcollection A or B.
- Write a classification decision record for this paper.
- Review this borderline paper and tell me whether it exposes a taxonomy gap.
- Reclassify these papers using taxonomy version 2026-Q1.

Do not use this skill for requests like:
- find this paper in my library
- summarize this paper in detail
- build an entire taxonomy from nothing
- compare ten papers as a literature review

## Required Inputs

Before classifying, gather as many of these as the task supports:

- active taxonomy reference document
- taxonomy version
- paper title
- abstract
- keywords
- authors / year / venue
- full text or key body sections when needed
- precedent log or prior adjudications, if available
- existing classification, if this is a review or reclassification task

If the taxonomy reference is missing, outdated, or too vague to distinguish neighboring subcollections, say so explicitly and treat that as a blocker or escalation signal rather than pretending the boundary is clear.

## Authority Order

Use this order whenever sources conflict:

1. active taxonomy reference document
2. explicit precedent / prior adjudication
3. the paper's actual content
4. informal habits, spreadsheet comments, or prior guesses

The taxonomy reference is the primary authority. Chat history, old habits, and loose keyword matches do not override it.

## Read These References As Needed

Start lean. Read only the files needed for the current job.

- `references/paper-classification-tutorial.md`
  - Read for the chronological single-paper classification workflow.
  - Use first for ordinary classification and misclassification review tasks.

- `references/taxonomy-reference-template.md`
  - Read when you need the canonical structure of a good taxonomy reference document.
  - Use to detect missing definitions, weak boundaries, governance gaps, or poor include/exclude rules.

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

- `references/package-index.md`
  - Read only when you need the source package map.

- `references/output-examples.md`
  - Read when you want a concrete normal-case or escalation-case decision record format.

- `references/eval-prompts.json`
  - Read when testing trigger boundaries or refining the frontmatter description.

## Core Decision Rules

Apply these rules in order:

1. Classify by the paper's **primary intellectual contribution**.
2. Prefer the **author-stated objective** over incidental details.
3. Assign **one primary Level 1 collection** and **one primary Level 2 subcollection**.
4. Use the **deepest valid node**; do not stop at Level 1 if a correct Level 2 exists.
5. Prefer **direct evidence** over keyword matching.
6. Compare the chosen path against the **strongest rejected alternative** when ambiguity exists.
7. Escalate ambiguity instead of forcing fake certainty.

Default evidence order:
1. title
2. abstract
3. introduction / problem statement
4. method section
5. experiments / evaluation
6. conclusion

If title and abstract are not enough, inspect deeper sections before deciding. Do not inflate confidence from weak metadata.

## Classification Workflow

### 1. Lock the classification frame

Identify and state:
- active taxonomy version
- whether this is new classification, audit, reclassification, or adjudication
- what evidence is actually available

If the task does not provide the active taxonomy, ask for it or clearly explain the limits of any provisional answer.

### 2. Understand the paper before mapping it

Extract the minimum needed facts:
- core research problem
- primary object of study
- main method or contribution type
- domain / application context
- any clues that are merely secondary or incidental

Ask:
> What is this paper mainly about?

Not:
> What words appear most often?

### 3. Narrow Level 1, then Level 2

First identify the best Level 1 collection.
Then choose the strongest Level 2 subcollection inside that Level 1.

When two Level 2 nodes look plausible, test them against:
- include rules
- exclude rules
- boundary notes
- precedent
- whether one option better reflects the central contribution

### 4. Evaluate the strongest alternative

Do not stop at the first plausible fit.

For each paper, explicitly consider at least one competing path when ambiguity exists:
- strongest alternate Level 1 / Level 2
- why it initially looks plausible
- why it loses to the selected path

If two candidates remain equally strong after reading the relevant evidence, escalate or mark as taxonomy-gap rather than forcing a tidy answer.

### 5. Assign confidence honestly

Use this rubric:

- **High**: one path clearly fits and the strongest alternative is clearly weaker
- **Medium**: best fit exists, but a neighboring path remains plausible
- **Low**: evidence is incomplete, boundaries are unclear, or multiple paths remain equally strong

Low confidence usually means review or escalation is needed.

### 6. Decide the outcome type

Use one of these outcomes:
- `proposed`
- `accepted`
- `returned_for_rework`
- `escalated`
- `taxonomy_gap`
- `needs_more_evidence`

Choose `taxonomy_gap` when the paper fits poorly across the current taxonomy and the problem is structural, not merely uncertain reading.

### 7. Produce an auditable output

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

When escalating, name the exact issue type instead of saying only that the case is hard.

## If The User Wants Team-Oriented Operation

For multi-agent or role-based workflows:

1. read `references/workflow-and-communication-playbook.md`
2. read `references/agent-persona-prompts.md`
3. read `references/classification-team-blueprint.md` if staffing or throughput matters
4. read `references/leadership-roles-addendum.md` if approval rights or lead structure matters

Use those references to separate analyst work, QA/adjudication, taxonomy governance, and operations.

## Never Do This

- Never classify from keywords alone when paper content is available.
- Never let venue, author affiliation, or fashionable terminology drive the decision by itself.
- Never assign multiple primary locations unless the governing taxonomy explicitly allows it.
- Never invent paper facts, definitions, or precedents.
- Never silently reinterpret unclear taxonomy boundaries as if they were settled.
- Never hide ambiguity behind inflated confidence.
- Never claim a taxonomy gap without checking whether an existing node already fits.
- Never treat chat as the system of record when the task requires a durable artifact.
