# Multi-Agent Handoff Schema and Prompt Contracts

## Purpose

This document defines the exact handoff packages, normalized output schema, and prompt contracts for coordinator, classifier, QA, and taxonomy-lead roles in multi-agent paper classification.

Use this alongside:
- the team blueprint
- the workflow and communication playbook
- the multi-agent orchestration and decision governance document

---

## Design Goals

The handoff format must be:

- concise enough for operational use
- strict enough for normalization
- explicit enough to preserve evidence and accountability
- stable enough to support merging and auditability

---

## Coordinator Input Package

The parent / coordinator should prepare the following input package for every worker assignment.

```yaml
parent_batch_id:
taxonomy_version:
assignment_id:
worker_role:
paper_position:
paper_id:
paper_title:
paper_authors:
paper_year:
paper_source:
paper_payload:
classification_objective:
allowed_labels_level_1:
allowed_labels_level_2:
escalation_states:
required_output_schema:
evidence_scope_allowed:
priority_level:
review_policy:
notes_from_parent:
```

### Field notes
- `paper_payload` may contain title, abstract, keywords, metadata, excerpted full text, or full text
- `classification_objective` should remind the worker to assign exactly one Level 1 and one Level 2 label when possible
- `allowed_labels_level_1` and `allowed_labels_level_2` should come from the locked taxonomy version
- `review_policy` should state whether the paper is standard review, mandatory double-review, or audit-only

---

## Classifier Worker Task Prompt Template

```md
You are a Classification Analyst agent working inside a research-paper classification program.

Your task:
- classify the assigned paper into exactly one Level 1 main collection and one Level 2 subcollection using the provided taxonomy version
- classify by the paper's primary intellectual contribution unless the assignment explicitly states a different basis
- do not invent labels outside the provided taxonomy
- if the paper does not fit cleanly, return an allowed escalation state instead of forcing a weak placement

You must:
- use only the supplied evidence
- identify the strongest rejected alternative
- mark confidence as high, medium, or low
- set review_required to true if evidence is weak, a close competing label exists, or a taxonomy issue is suspected

Return output only in the required schema.
```

---

## Classifier Worker Output Schema

```yaml
parent_batch_id:
assignment_id:
paper_position:
paper_id:
worker_role: classifier
worker_id:
taxonomy_version:
source_evidence_scope:
decision_status:
level_1_label:
level_2_label:
confidence:
review_required:
review_reason:
strongest_rejected_alternative:
rationale:
evidence_used:
open_questions:
```

### Allowed `source_evidence_scope` values
- `title_only`
- `title_abstract`
- `title_abstract_keywords`
- `title_abstract_intro`
- `full_text`
- `mixed_excerpted_full_text`

### Allowed `review_reason` values
- `close_alternative`
- `thin_evidence`
- `low_confidence`
- `level_1_uncertainty`
- `taxonomy_gap_suspected`
- `precedent_conflict`
- `mandatory_double_review`
- `high_value_item`
- `other`

---

## QA / Adjudication Input Package

QA should receive:

```yaml
parent_batch_id:
review_assignment_id:
paper_position:
paper_id:
taxonomy_version:
original_classifier_record:
paper_payload:
current_precedents:
review_trigger:
specific_questions_for_review:
allowed_actions:
```

### Allowed QA actions
- confirm
- revise
- escalate_to_taxonomy_lead
- return_needs_more_evidence
- return_out_of_scope

---

## QA Prompt Template

```md
You are the QA / Adjudication agent for a research-paper classification program.

Review the classifier's decision record and the supplied paper evidence.

Your goals:
- determine whether the assigned labels are correct under the locked taxonomy version
- identify whether the rationale is strong enough
- decide whether the issue can be resolved at QA level or must be escalated

You may:
- confirm the decision
- revise the decision with justification
- escalate to taxonomy lead if the disagreement is structural or Level 1 cannot be resolved
- return needs_more_evidence if the supplied evidence is inadequate

Do not create new taxonomy labels.
Do not silently erase disagreement.
Return output only in the required schema.
```

---

## QA Output Schema

```yaml
parent_batch_id:
review_assignment_id:
paper_position:
paper_id:
worker_role: qa
worker_id:
taxonomy_version:
review_outcome:
final_recommended_status:
level_1_label:
level_2_label:
confidence:
escalate_to_taxonomy_lead:
escalation_reason:
agreement_with_classifier:
revised_strongest_rejected_alternative:
rationale:
evidence_used:
open_questions:
```

### Allowed `review_outcome` values
- `confirmed`
- `revised`
- `escalated`
- `needs_more_evidence`
- `out_of_scope`

### Allowed `agreement_with_classifier` values
- `full`
- `partial`
- `none`

---

## Taxonomy Lead Adjudication Input Package

```yaml
parent_batch_id:
adjudication_assignment_id:
paper_position:
paper_id:
taxonomy_version:
classifier_record:
qa_record:
paper_payload:
relevant_label_definition_cards:
relevant_precedents:
specific_adjudication_question:
allowed_actions:
```

### Allowed Taxonomy Lead actions
- finalize_existing_label
- finalize_needs_more_evidence
- finalize_taxonomy_gap
- open_taxonomy_change_request
- return_for_additional_evidence

---

## Taxonomy Lead Prompt Template

```md
You are the Taxonomy Lead / Knowledge Architect.

You are reviewing a paper that could not be resolved cleanly by classifier and QA review.

Your job:
- resolve Level 1 or structural Level 2 conflicts
- determine whether the paper can be placed in the existing taxonomy
- decide whether the issue reveals a taxonomy gap or merely a difficult paper

You must:
- preserve the locked taxonomy version
- avoid forcing weak label assignments
- document why the winning label is better than the strongest alternative
- explicitly state whether a taxonomy change request is required

Return output only in the required schema.
```

---

## Taxonomy Lead Output Schema

```yaml
parent_batch_id:
adjudication_assignment_id:
paper_position:
paper_id:
worker_role: taxonomy_lead
worker_id:
taxonomy_version:
final_decision_status:
level_1_label:
level_2_label:
confidence:
taxonomy_change_required:
taxonomy_change_reason:
winning_rationale:
rejected_alternatives:
evidence_used:
precedent_notes:
follow_up_actions:
```

---

## Parent / Coordinator Merge Rules

The coordinator should apply these rules in order:

1. verify taxonomy version match
2. verify schema completeness
3. reject malformed worker outputs for correction
4. accept straightforward classifier results that require no review
5. route flagged classifier results to QA
6. route unresolved structural cases to taxonomy lead
7. produce one final normalized record per paper
8. preserve dissent notes and escalation history
9. produce batch-level summary sections

---

## Final Normalized Record Schema

```yaml
parent_batch_id:
paper_position:
paper_id:
taxonomy_version:
final_decision_owner_role:
final_decision_owner_id:
final_decision_status:
level_1_label:
level_2_label:
confidence:
source_evidence_scope:
strongest_rejected_alternative:
final_rationale:
evidence_used:
review_history:
open_follow_up:
```

---

## Review History Mini-Schema

```yaml
review_history:
  - step:
    worker_role:
    worker_id:
    outcome:
    notes:
```

This allows traceability without bloating the final top-level schema.

---

## Allowed Escalation Conditions

Escalate from classifier to QA when:
- confidence is not high
- rationale is weak
- competing sibling exists
- paper is in mandatory review sample

Escalate to taxonomy lead when:
- Level 1 is disputed
- repeated precedent conflict exists
- taxonomy gap is suspected
- QA cannot resolve without changing policy

Escalate to program lead only when:
- delivery scope is impacted
- taxonomy change affects sponsor commitments
- staffing or SLA trade-offs must be decided

---

## Error Handling Rules

If a worker output is incomplete:
- return it for correction
- do not merge partial records silently

If a worker used the wrong taxonomy version:
- invalidate the output
- re-run under the locked version

If two outputs disagree but neither provides strong evidence:
- do not average them
- escalate or request more evidence

If the evidence package is too thin:
- use `needs_more_evidence`
- do not pretend the disagreement was resolved

---

## Prompt Contract for Parent / Coordinator

```md
You are the Parent Coordinator for a research-paper classification workflow.

Your responsibilities:
- lock the taxonomy version before assignment
- choose single-agent or multi-agent mode based on batch size, ambiguity risk, and environment support
- package work units using the normalized schema
- collect worker outputs
- route review-required items to QA
- route structural conflicts to taxonomy lead
- reject malformed or cross-version outputs
- merge final records in the original paper order
- produce a final batch summary with resolved items, unresolved escalations, taxonomy gaps, and recurring ambiguity patterns

Never merge records created under different taxonomy versions.
Never collapse disagreement into false consensus.
```

---

## Optional Double-Review Protocol

Use this for:
- flagship papers
- benchmark sets
- training / certification
- audit samples
- high-stakes deliverables

### Process
1. assign the same paper independently to two classifier workers
2. hide each worker's draft from the other
3. compare results
4. if they agree, accept or QA-sample
5. if they disagree, route to QA or taxonomy lead based on the disagreement level

This gives better quality than majority voting with three weak reviewers.

---

## Minimal Required Fields by Role

## Classifier
- taxonomy version
- label choice or escalation state
- confidence
- strongest rejected alternative
- rationale
- review flag

## QA
- confirm / revise / escalate
- explanation
- agreement level
- escalation reason when needed

## Taxonomy Lead
- final structural decision
- taxonomy change flag
- precedent note
- follow-up action

## Coordinator
- merged final record
- review history
- unresolved issues section

---

## Recommended File-Level Conventions

- preserve input order with `paper_position`
- use stable label IDs where possible, not only free-text names
- keep taxonomy version in every record
- use controlled vocabulary for statuses and review reasons
- separate final batch output from intermediate worker outputs

---

## Final Recommendation

A multi-agent system becomes reliable only when:
- assignments are packaged consistently
- outputs are normalized
- review triggers are explicit
- conflict routing is deterministic
- final accountability is assigned

Use this handoff schema as the operational contract between parent, classifier, QA, and taxonomy-lead roles.
