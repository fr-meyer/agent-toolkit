# Taxonomy Reference Document Template

## Document purpose

This document is the **authoritative reference** for all classification tags used in the research paper taxonomy.

Its function is to ensure that every classifier interprets each:

- main collection,
- subcollection,
- boundary rule,
- and exception pattern

in exactly the same way.

This is **not** just a label list. It is the operational rulebook for what each collection and subcollection should contain.

---

## 1. How to use this document

Use this reference for four purposes:

1. **Classification guidance** — deciding where a paper belongs
2. **Training** — onboarding new classifiers
3. **Quality control** — checking whether decisions follow policy
4. **Governance** — adding, editing, merging, or deprecating tags

### Rule of authority

When there is disagreement between:

- informal team memory,
- past habits,
- spreadsheet comments,
- tooltips,
- or personal interpretation,

this reference document wins.

---

## 2. Document metadata

Copy this block at the top of every released version.

```md
# Taxonomy Reference Metadata

- Taxonomy name:
- Taxonomy version:
- Effective date:
- Previous version:
- Owner:
- Approved by:
- Status: Draft / Active / Deprecated / Archived
- Applies to corpus:
- Change summary:
```

---

## 3. Recommended document structure

Use the following structure in this exact order.

1. Purpose and scope
2. Governance
3. General classification rules
4. Naming conventions
5. Level 1 collection catalogue
6. Level 2 subcollection catalogue
7. Boundary rules between similar tags
8. Escalation rules
9. Change log
10. Deprecated tags and mappings
11. Ambiguity register
12. Example papers by tag

---

## 4. Governance section template

```md
# Governance

## Ownership
- Taxonomy owner:
- Backup owner:
- QA approver:
- Operations contact:

## Authority
- Who can propose a new tag:
- Who can approve a new tag:
- Who can change a definition:
- Who can deprecate a tag:
- Who can authorize bulk reclassification:

## Review cadence
- Weekly operational review:
- Monthly taxonomy review:
- Quarterly structural review:

## Change control policy
- Changes allowed during production batch: Yes / No
- Emergency change process:
- Standard change window:
- Communication method for updates:
```

---

## 5. General classification policy template

This section contains rules that apply to all tags.

```md
# General Classification Policy

## Core principle
Papers must be assigned based on their primary intellectual contribution, not incidental keywords or minor experimental domains.

## One-primary-location rule
Each paper receives one primary main collection and one primary subcollection.

## Evidence order
1. Title
2. Abstract
3. Introduction
4. Method section
5. Evaluation / experiments
6. Conclusion

## Escalation policy
When no tag is clearly correct or when multiple tags are equally plausible, the paper must be escalated rather than force-classified.

## Taxonomy gap policy
If a paper consistently fits poorly within the current taxonomy, classify to the closest valid tag and record a taxonomy-gap request.
```

---

## 6. Naming conventions template

Naming rules prevent drift and synonym chaos.

```md
# Naming Conventions

## Level 1 naming rules
- Use noun phrases, not sentences.
- Keep names short and stable.
- Avoid jargon unless standard in the field.
- Avoid overlap with sibling collections.

## Level 2 naming rules
- Must be specific enough to guide actual classification.
- Must inherit clearly from the parent Level 1 collection.
- Must not duplicate the wording of another subcollection unless meaningfully distinct.

## Forbidden naming patterns
- Ambiguous generic names like "Other Topics"
- Temporary wording like "New Methods 2026"
- Mixed dimensions in one name such as method + audience + format

## Canonical label format
- Level 1 ID:
- Level 1 Name:
- Level 2 ID:
- Level 2 Name:
- Parent ID:
```

---

## 7. Master catalogue template for Level 1 collections

Use one summary row per main collection.

```md
# Level 1 Collection Catalogue

| ID | Main Collection | Definition | Typical papers | Excludes | Owner | Status |
|---|---|---|---|---|---|---|
| L1-001 | [Collection Name] | [What belongs here] | [Typical paper pattern] | [What should not be placed here] | [Owner] | Active |
| L1-002 | [Collection Name] | [What belongs here] | [Typical paper pattern] | [What should not be placed here] | [Owner] | Active |
```

---

## 8. Canonical Level 1 entry template

Create one section like this for **every** main collection.

```md
# [L1-ID] [Main Collection Name]

## Definition
[Precise definition of what this collection covers.]

## Purpose of the collection
[Why this node exists in the taxonomy and what retrieval need it serves.]

## Include when
- [Condition 1]
- [Condition 2]
- [Condition 3]

## Do not include when
- [Condition 1]
- [Condition 2]
- [Condition 3]

## Typical paper types
- Method papers
- Application studies
- Review papers
- Theory papers
- Benchmarks / datasets

## Boundary rules
- Use this collection instead of [Neighbor Collection] when:
- Do not use this collection if the paper is primarily about:

## Required child subcollections
- [L2-ID] [Subcollection Name]
- [L2-ID] [Subcollection Name]
- [L2-ID] [Subcollection Name]

## Example papers that belong here
- [Example title or short pattern]
- [Example title or short pattern]

## Counterexamples
- [Paper pattern that looks similar but should go elsewhere]
- [Paper pattern that looks similar but should go elsewhere]

## Frequent classifier mistakes
- [Common error]
- [Common error]

## Notes for reviewers
- [Special interpretation rule]
```

---

## 9. Master catalogue template for Level 2 subcollections

Use one row per subcollection.

```md
# Level 2 Subcollection Catalogue

| ID | Parent L1 | Subcollection | Definition | Include | Exclude | Example patterns | Status |
|---|---|---|---|---|---|---|---|
| L2-001 | L1-001 | [Subcollection Name] | [Definition] | [What belongs] | [What does not] | [Typical paper pattern] | Active |
| L2-002 | L1-001 | [Subcollection Name] | [Definition] | [What belongs] | [What does not] | [Typical paper pattern] | Active |
```

---

## 10. Canonical Level 2 entry template

Create one section like this for **every** subcollection.

```md
# [L2-ID] [Subcollection Name]

## Parent collection
- Parent ID:
- Parent name:

## Definition
[Precise statement of what this subcollection covers.]

## Inclusion criteria
- [Must have property 1]
- [Must have property 2]
- [May also have property 3]

## Exclusion criteria
- [Should go elsewhere if property 1]
- [Should go elsewhere if property 2]

## What this subcollection is mostly about
- [Primary topic pattern]
- [Contribution pattern]
- [Scope pattern]

## What this subcollection is not about
- [Neighboring topic that should not be placed here]
- [Neighboring topic that should not be placed here]

## Decision test
Use this subcollection if the paper mainly answers:
> [Question that defines the node]

## Typical keywords and phrases
- [Keyword]
- [Keyword]
- [Keyword]

## Typical paper formats
- [New method]
- [Evaluation study]
- [Survey]
- [Benchmark]
- [Case study]

## Positive examples
- [Example title pattern]
- [Example title pattern]

## Negative examples / counterexamples
- [Looks similar but belongs to X]
- [Looks similar but belongs to Y]

## Boundary with sibling tags
- Versus [Sibling A]: use this tag when...
- Versus [Sibling B]: use this tag when...
- Versus [Sibling C]: use this tag when...

## Review notes
- [Special caution]
- [Special caution]

## Change history
- Created in version:
- Last revised in version:
- Revision summary:
```

---

## 11. Boundary rule template

Boundary rules are critical. Most classifier disagreement happens between neighboring tags, not distant ones.

Use a dedicated section for every high-confusion pair.

```md
# Boundary Rule: [Tag A] vs [Tag B]

## Why confusion happens
[Explain the overlap.]

## Use [Tag A] when
- [Condition]
- [Condition]

## Use [Tag B] when
- [Condition]
- [Condition]

## Deciding question
If the paper is mainly about "[Question A]", use [Tag A].
If it is mainly about "[Question B]", use [Tag B].

## Example distinctions
- [Example scenario 1]
- [Example scenario 2]
```

---

## 12. Taxonomy gap register template

This section tracks recurring cases that do not fit well.

```md
# Taxonomy Gap Register

| Gap ID | Date | Trigger paper | Current closest tag | Why fit is poor | Proposed action | Owner | Status |
|---|---|---|---|---|---|---|---|
| GAP-001 | [Date] | [Paper ID / title] | [Tag] | [Explanation] | Add / revise / merge / no action | [Owner] | Open |
```

---

## 13. Deprecated tag mapping template

Never silently remove a tag. Preserve the migration path.

```md
# Deprecated Tags and Mappings

| Old Tag ID | Old Tag Name | Status | Deprecated in version | Replacement tag | Migration rule | Notes |
|---|---|---|---|---|---|---|
| L2-099 | [Old Name] | Deprecated | v1.3 | L2-014 | Reclassify when paper is mainly about X | [Notes] |
```

---

## 14. Change log template

```md
# Change Log

| Version | Date | Change type | Description | Approved by | Reclassification needed? |
|---|---|---|---|---|---|
| v1.0 | [Date] | Initial release | Initial taxonomy launch | [Name] | No |
| v1.1 | [Date] | Definition update | Clarified boundary between A and B | [Name] | Possibly |
| v1.2 | [Date] | New tag | Added new subcollection for X | [Name] | Yes |
```

---

## 15. Ambiguity register template

The ambiguity register captures repeated confusion even when no structural change is needed.

```md
# Ambiguity Register

| Issue ID | Tags involved | Symptom | Example paper pattern | Current guidance | Follow-up needed |
|---|---|---|---|---|---|
| AMB-001 | [Tag A] / [Tag B] | Classifiers split 50/50 | [Pattern] | Use Tag A when contribution is method-first | Add more examples |
```

---

## 16. Example paper library template

A strong taxonomy reference includes examples, not just definitions.

```md
# Example Paper Library

## [Tag ID] [Tag Name]

### Strong positive examples
- [Paper title / pattern]
- Why it belongs:

### Borderline examples
- [Paper title / pattern]
- Why it still belongs:

### Negative examples
- [Paper title / pattern]
- Why it belongs elsewhere:
```

---

## 17. Maintenance workflow for the taxonomy reference

This is the recommended operating process.

### Step 1 — Capture signals

Collect input from:

- classifier disagreement logs
- QA audits
- low-confidence cases
- taxonomy-gap tickets
- search/retrieval complaints
- product or research stakeholders

### Step 2 — Diagnose the problem type

Determine whether the issue is:

- a definition problem,
- a boundary problem,
- an example problem,
- a missing tag,
- an over-granular tag,
- or a workflow/training problem rather than a taxonomy problem.

### Step 3 — Draft the proposed change

For any proposed change, write:

- what is changing,
- why it is needed,
- which papers are affected,
- whether historical papers must be reclassified,
- risk to consistency.

### Step 4 — Review and approve

Approval should include at least:

- taxonomy owner
- QA lead
- operations lead
- subject matter reviewer if needed

### Step 5 — Publish a versioned update

Every approved change must update:

- taxonomy version number
- change log
- relevant tag entries
- boundary rules
- examples
- migration guidance

### Step 6 — Communicate and retrain

Notify classifiers with:

- summary of change
- effective date
- examples of before vs after
- whether prior decisions remain valid

### Step 7 — Audit post-change behavior

For 1–2 weeks after release, monitor:

- confusion rate
- overturn rate
- tag usage distribution
- repeated escalation patterns

---

## 18. Minimum standards for a good tag definition

A tag definition is acceptable only if it answers all of the following:

- What belongs here?
- What does not belong here?
- How is it different from nearby tags?
- What kinds of papers typically appear here?
- What is the deciding question a classifier should ask?
- Are there positive and negative examples?

If any of those are missing, the tag is not yet production-ready.

---

## 19. Example of a fully written tag entry

Use this only as a format model.

```md
# L2-014 Benchmark Datasets

## Parent collection
- Parent ID: L1-003
- Parent name: Research Resources

## Definition
This subcollection contains papers whose primary contribution is the creation, curation, release, or systematic evaluation of datasets, benchmarks, or annotated corpora used for research.

## Inclusion criteria
- The paper's main novelty is the resource itself.
- The paper describes data construction, annotation, coverage, or benchmark design.
- Evaluation is present mainly to validate the usefulness of the resource.

## Exclusion criteria
- Papers that merely use a dataset to test a method.
- Papers whose main contribution is a new model trained on the dataset.
- Survey papers discussing multiple datasets without releasing a new one.

## Decision test
Use this subcollection if the paper mainly answers:
> "What new research dataset, benchmark, or corpus is being introduced or systematically defined?"

## Typical keywords and phrases
- dataset
- benchmark
- corpus
- annotation scheme
- data release
- resource paper

## Boundary with sibling tags
- Versus Method Evaluation: use this tag when the dataset is the contribution; use Method Evaluation when the method is the contribution.
- Versus Survey Papers: use this tag when a new resource is introduced; use Survey Papers when the paper only reviews existing resources.
```

---

## 20. Final recommendations

A taxonomy reference document is healthy when it behaves like a **controlled standard**, not a loose wiki.

To keep it useful:

- version it,
- assign a real owner,
- define approval rights,
- keep examples current,
- map deprecated tags,
- and capture every repeated confusion as either a boundary rule or a structural change proposal.

The more your classification volume grows, the more this document becomes a core operational asset rather than simple documentation.
