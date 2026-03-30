# Research Paper Classification Package — v6

This package now contains the full operating set for a research-paper classification program, including:
- taxonomy design from scratch
- paper-by-paper classification SOP
- taxonomy reference documentation
- staffing and leadership structure
- agent persona prompts
- workflow and communication rules
- operating artifact templates
- multi-agent orchestration rules
- multi-agent handoff schema and prompt contracts
- an explicit response to the subagent-support readiness audit

---

## Package Contents

### 01. Paper Classification Tutorial
`01_paper_classification_tutorial.md`

Chronological SOP for assigning each paper to exactly one main collection and one subcollection.

### 02. Taxonomy Reference Document Template
`02_taxonomy_reference_template.md`

Fillable reference template that defines what each collection and subcollection should contain.

### 03. Classification Team Blueprint
`03_classification_team_blueprint.md`

Recommended staffing model, role charters, production assumptions, and scaling logic.

### 04. Agent Persona Prompts
`04_agent_persona_prompts.md`

Ready-to-deploy role prompts for the classification organization.

### 05. Leadership Roles Addendum
`05_leadership_roles_addendum.md`

Defines the overall program owner and the optional analyst team-lead layer.

### 06. Workflow and Communication Playbook
`06_workflow_and_communication_playbook.md`

Detailed role-by-role workflow, handoffs, escalation triggers, SLAs, meeting cadence, and RACI.

### 07. Operating Artifact Template Library
`07_operating_artifact_template_library.md`

Ready-to-use markdown templates for decision records, QA forms, reports, escalation tickets, precedent logs, and governance artifacts.

### 08. Taxonomy Creation from Scratch Playbook
`08_taxonomy_creation_from_scratch_playbook.md`

Defines how to create a usable 2-layer taxonomy when no taxonomy exists, including corpus discovery, label drafting, pilot validation, bounded multi-turn convergence, and version locking.

### 09. Multi-Agent Orchestration and Decision Governance
`09_multi_agent_orchestration_and_decision_governance.md`

Defines when to stay single-agent versus switch to multi-agent mode, agent-count policy, role topology, conflict resolution, and the recommended final decision model.

### 10. Multi-Agent Handoff Schema and Prompt Contracts
`10_multi_agent_handoff_schema_and_prompt_contracts.md`

Defines normalized handoff packages, required output schemas, routing rules, and prompt contracts for coordinator, classifier, QA, and taxonomy-lead roles.

### 11. Subagent-Support Readiness Response
`11_subagent_support_readiness_response.md`

Maps the user-provided audit findings to the new package documents and explains how the orchestration and taxonomy gaps are now covered.

### Appendix A. User Audit Report
`classify-research-papers-subagent-support-audit-2026-03-30.md`

The user-provided audit that identified the missing orchestration layer and multi-agent readiness gaps.

---

## Recommended Reading Order

1. Start with `08_taxonomy_creation_from_scratch_playbook.md` if no taxonomy exists.
2. Then use `02_taxonomy_reference_template.md` to publish the approved taxonomy.
3. Then read `01_paper_classification_tutorial.md` for the operating SOP.
4. Then use `03_classification_team_blueprint.md` and `05_leadership_roles_addendum.md` to define structure and accountability.
5. Then read `06_workflow_and_communication_playbook.md` to operationalize daily work and escalation.
6. Then use `09_multi_agent_orchestration_and_decision_governance.md` and `10_multi_agent_handoff_schema_and_prompt_contracts.md` if agents or subagents will be used.
7. Then read `11_subagent_support_readiness_response.md` as the bridge from the audit to the operating package.
8. Then use `04_agent_persona_prompts.md` to instantiate role agents.
9. Keep `07_operating_artifact_template_library.md` open as the template library for day-to-day execution.
10. Keep the audit report as a reference appendix when validating subagent-support readiness.

---

## Recommended Governance Choices

### Best final decision model
Use **bounded distributed proposal with centralized adjudication**:
- classifiers propose
- QA reviews contested items
- taxonomy lead adjudicates structural conflicts
- program lead owns policy and program-level governance

This is better than simple democracy and better than routing everything to one judge.

### Best agreement rule
Seek convergence, but do **not** require unanimity.
Use bounded multi-turn review and then escalate to the correct decision owner.

### Best taxonomy rule
Do not start batch classification before:
- the taxonomy basis is chosen
- the labels are defined
- the taxonomy version is locked

---

## Recommended Organization Choices

### Lean but well-governed model
- 1 Classification Program Director / Program Lead
- 1 Taxonomy Lead / Knowledge Architect
- 1 Classification Operations Manager
- 1 QA & Adjudication Lead
- 6 Classification Analysts
- 1 Data / Tooling Analyst

**Total = 11 FTE**

### Fully supervised model
- 1 Classification Program Director / Program Lead
- 1 Taxonomy Lead / Knowledge Architect
- 1 Classification Operations Manager
- 1 QA & Adjudication Lead
- 1 Classification Team Lead / Senior Lead
- 6 Classification Analysts
- 1 Data / Tooling Analyst

**Total = 12 FTE**

---

## Recommended Multi-Agent Scaling Rule

If subagent support is available:
- 4–6 papers → up to 2 classifier workers
- 7–12 papers → up to 3 classifier workers
- 13+ papers → up to 4 classifier workers by default
- add QA and taxonomy-lead review roles only when needed

Keep the default ceiling conservative to protect merge quality and taxonomy consistency.
