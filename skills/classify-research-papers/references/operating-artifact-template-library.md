# Operating Artifact Template Library

## Purpose

This document provides the **copy-paste operational templates** required to run a research-paper classification program in production.

It is designed to support a team structure with these roles:

- Classification Program Director / Program Lead
- Taxonomy Lead / Knowledge Architect
- Classification Operations Manager
- QA & Adjudication Lead
- Classification Team Lead / Senior Lead *(optional layer)*
- Classification Analysts
- Data / Tooling Analyst

Use this document as the working template pack for your documentation system, wiki, shared repository, ticketing platform, or markdown-based operations folder.

---

## How to use this document

1. Copy the relevant template into your documentation system.
2. Preserve the field order unless you have a strong reason to change it.
3. Use immutable identifiers for papers, cases, precedent entries, QA records, and change requests.
4. Use ISO date format: `YYYY-MM-DD`.
5. Use 24-hour time format and explicitly state timezone when needed.
6. Mark all unresolved items as `OPEN`, `PENDING`, or `BLOCKED` rather than leaving blanks.
7. Never overwrite historical decisions without a change log entry.

---

## Global naming conventions

### Artifact ID patterns

- Paper record: `PAPER-YYYY-####`
- Escalation ticket: `ESC-YYYY-####`
- Precedent entry: `PREC-YYYY-####`
- Taxonomy change request: `TCR-YYYY-####`
- QA review: `QA-YYYY-####`
- Adjudication case: `ADJ-YYYY-####`
- Incident review: `INC-YYYY-####`
- Weekly report: `WEEK-YYYY-W##`
- Monthly governance report: `MONTH-YYYY-MM`
- Calibration session: `CAL-YYYY-####`

### Standard confidence scale

| Score | Meaning | Operational interpretation |
|---|---|---|
| 5 | Very high confidence | The assignment is clearly supported by the taxonomy and similar precedents exist. |
| 4 | High confidence | The assignment is well supported; ambiguity is low. |
| 3 | Moderate confidence | Acceptable classification but one plausible alternative exists. |
| 2 | Low confidence | Ambiguous paper; escalation or QA attention is advised. |
| 1 | Very low confidence | The analyst cannot safely finalize without review. |

### Standard issue severity scale

| Severity | Meaning | Example |
|---|---|---|
| S1 | Critical | Large-volume misclassification, broken ingestion, corrupted taxonomy mappings |
| S2 | High | Repeated analyst disagreement, missing taxonomy path for a common paper type |
| S3 | Medium | Local workflow delay, isolated precedent conflict |
| S4 | Low | Minor documentation gap, typo, non-blocking ambiguity |

### Standard status values

- `NEW`
- `IN_PROGRESS`
- `PENDING_REVIEW`
- `PENDING_QA`
- `PENDING_ADJUDICATION`
- `BLOCKED`
- `FINALIZED`
- `REOPENED`
- `CLOSED`

---

## Artifact inventory map

| Artifact | Primary owner | Secondary owner | Trigger | Cadence | Required for all cases? |
|---|---|---|---|---|---|
| Paper classification decision record | Classification Analyst | Team Lead / QA | Any paper with non-trivial ambiguity or sampled review | Per case | No |
| Review request / handoff pack | Classification Analyst | Team Lead / QA | Review needed | Per case | No |
| Escalation ticket | Any role | Operations Manager | Blocker, ambiguity, SLA risk, precedent conflict | Per case | No |
| Precedent log entry | QA Lead / Taxonomy Lead | Analysts | New recurring decision logic | As needed | No |
| Taxonomy change request | Taxonomy Lead / QA Lead / Ops | Program Lead | Taxonomy gap, overlap, structural issue | As needed | No |
| QA sample plan | QA Lead | Operations Manager | Start of QA cycle | Weekly | Yes |
| QA disposition form | QA Reviewer | QA Lead | Review completed | Per reviewed item | Yes for sampled items |
| Adjudication record | QA Lead | Taxonomy Lead | Conflicting views unresolved | Per case | No |
| Weekly operations report | Operations Manager | Program Lead | Reporting cycle | Weekly | Yes |
| Monthly governance report | Program Lead | All leads | Governance cycle | Monthly | Yes |
| Incident / RCA | Operations Manager / Data Analyst | Program Lead | Operational failure | As needed | No |
| Calibration minutes | QA Lead / Team Lead | Taxonomy Lead | Calibration meeting | Weekly / biweekly | Yes |
| Onboarding certification checklist | Team Lead / QA Lead | Operations Manager | New joiner | Per person | Yes for new hires |

---

# 1) Paper Classification Decision Record

## When to use

Use this record whenever any of the following is true:

- the analyst confidence is `3` or lower,
- the paper could plausibly fit more than one main collection,
- the paper could plausibly fit more than one subcollection,
- the paper is likely to become a precedent,
- the paper was corrected after QA,
- the paper is flagged for training value.

## Template

```md
# Paper Classification Decision Record

## Metadata
- Record ID:
- Paper ID:
- Batch ID:
- Analyst:
- Review owner:
- Date created:
- Current status:

## Source paper details
- Title:
- Authors:
- Year:
- Venue / source:
- DOI / URL / internal reference:
- Available fields:
  - [ ] Title
  - [ ] Abstract
  - [ ] Keywords
  - [ ] Full text
  - [ ] Author affiliations
  - [ ] Venue metadata
  - [ ] Citation metadata

## Evidence used for classification
- 1–3 sentence summary of the paper:
- Core research problem:
- Primary object of study:
- Main method or approach:
- Main contribution type:
- Domain / application area:
- Notable exclusions or caveats:

## Candidate classifications considered
### Candidate A
- Main collection:
- Subcollection:
- Why this could fit:

### Candidate B
- Main collection:
- Subcollection:
- Why this could fit:

### Candidate C
- Main collection:
- Subcollection:
- Why this could fit:

## Final classification decision
- Final main collection:
- Final subcollection:
- Confidence score (1–5):
- Final decision rationale:
- Why the selected path is better than alternatives:
- Why non-selected paths were rejected:

## Reference support
- Relevant taxonomy clauses:
- Relevant precedent IDs:
- Similar papers already classified:
- Notes on consistency with prior decisions:

## Review and outcome
- Review required?:
- Review requester:
- Review completed by:
- Review result:
  - [ ] Confirmed
  - [ ] Corrected
  - [ ] Escalated
- Final comments:

## Follow-up actions
- Add to precedent log?:
- Raise taxonomy change request?:
- Add to training set?:
- Notify operations?:
```

---

# 2) Analyst Review Request / Handoff Pack

## When to use

Use when an analyst sends a paper to:

- Team Lead / Senior Lead,
- QA & Adjudication Lead,
- Taxonomy Lead,
- or Operations Manager because of blocking conditions.

## Template

```md
# Review Request / Handoff Pack

## Routing
- Handoff ID:
- From role:
- From person:
- To role:
- To person:
- Date sent:
- Response due by:
- Priority:
- Related paper ID(s):
- Related batch ID:
- Related escalation ID (if any):

## Requested action
- Requested action type:
  - [ ] Confirm classification
  - [ ] Resolve ambiguity
  - [ ] Interpret taxonomy
  - [ ] Approve exception
  - [ ] Correct QA finding
  - [ ] Decide adjudication
  - [ ] Fix tooling / data issue
- Decision needed by:
- Business / operational impact if delayed:

## Case summary
- Proposed main collection:
- Proposed subcollection:
- Confidence score:
- Short summary of the paper:
- Why the case is ambiguous:
- What has already been checked:

## Evidence package
- Taxonomy sections consulted:
- Prior precedent IDs consulted:
- Similar paper IDs:
- Notes from analyst reasoning:
- Attachments / links:

## Specific question to answer
- Question 1:
- Question 2:
- Question 3:

## Handoff quality check
- [ ] Proposed classification included
- [ ] Alternative classifications included
- [ ] Evidence summarized
- [ ] Relevant precedents linked
- [ ] Blocking reason clearly stated
```

---

# 3) Escalation Ticket

## When to open

Open an escalation ticket when:

- a paper cannot be safely finalized,
- the taxonomy lacks a valid path,
- precedent and taxonomy conflict,
- a tool or data issue blocks throughput,
- backlog aging exceeds SLA,
- repeated disagreement indicates a systemic problem.

## Template

```md
# Escalation Ticket

## Ticket header
- Escalation ID:
- Created by:
- Role:
- Date opened:
- Severity:
- Priority:
- Status:
- Owning function:
- Escalation path:
  - [ ] Team Lead
  - [ ] QA Lead
  - [ ] Taxonomy Lead
  - [ ] Operations Manager
  - [ ] Program Lead
  - [ ] Data / Tooling Analyst

## Problem statement
- One-sentence issue summary:
- Detailed issue description:
- Why this is an escalation rather than a normal review:
- Is work currently blocked?:
- Number of impacted papers:
- Batch IDs impacted:
- Earliest due date at risk:

## Classification impact
- Impact type:
  - [ ] Ambiguous classification
  - [ ] Missing taxonomy path
  - [ ] Conflicting precedent
  - [ ] QA disagreement
  - [ ] Tooling defect
  - [ ] Reporting inconsistency
  - [ ] Capacity / SLA issue
- Risk if unresolved:
- Temporary workaround available?:

## Evidence
- Example paper IDs:
- Example classifications attempted:
- Error screenshots / logs / links:
- Related precedent IDs:
- Related taxonomy sections:
- Related QA review IDs:
- Related incident IDs:

## Requested resolution
- What decision or action is needed:
- Suggested owner:
- Suggested deadline:
- Proposed workaround until resolved:

## Resolution log
- Assigned to:
- Date acknowledged:
- Action taken:
- Final decision:
- Date resolved:
- Prevention follow-up:
- Post-resolution communications sent to:
```

---

# 4) Precedent Log Entry

## Purpose

The precedent log stores decisions that should be reused consistently across future papers.

A precedent entry should be created when:

- a recurring ambiguity pattern is resolved,
- multiple analysts have asked the same question,
- QA finds a repeated error pattern,
- taxonomy wording alone is insufficiently operational.

## Template

```md
# Precedent Log Entry

## Entry header
- Precedent ID:
- Title:
- Date created:
- Created by:
- Approved by:
- Status:
  - [ ] Draft
  - [ ] Active
  - [ ] Superseded
  - [ ] Retired

## Precedent scope
- Main collection(s) affected:
- Subcollection(s) affected:
- Paper type / pattern covered:
- Trigger condition:
- Frequency observed:
- Risk of inconsistency if not documented:

## Decision rule
- Decision statement:
- Positive indicators:
- Negative indicators:
- Boundary conditions:
- Tie-break rule:
- Exceptions:

## Examples
### Positive examples
- Paper ID / title:
- Why it fits:

### Negative examples
- Paper ID / title:
- Why it does not fit:

## Source authority
- Taxonomy sections supporting this rule:
- Adjudication case IDs:
- QA review IDs:
- Related change requests:
- Related stakeholder approval:

## Lifecycle
- Effective date:
- Review date:
- Owner:
- Supersedes precedent ID:
- Superseded by precedent ID:
- Communication sent to team on:
```

---

# 5) Taxonomy Change Request (TCR)

## When to raise

Raise a taxonomy change request when:

- the taxonomy has a gap,
- two categories overlap structurally,
- a subcollection has become too broad,
- new paper types appear repeatedly,
- definitions produce systematic inconsistency.

## Template

```md
# Taxonomy Change Request

## Request header
- TCR ID:
- Request title:
- Requester:
- Requester role:
- Date submitted:
- Current status:
- Priority:
- Decision owner:
- Proposed effective date:

## Problem definition
- Current taxonomy path(s) involved:
- Problem type:
  - [ ] Missing category
  - [ ] Overlapping categories
  - [ ] Ambiguous definition
  - [ ] Overly broad category
  - [ ] Underused category
  - [ ] Naming problem
  - [ ] Structural reorganization needed
- Detailed problem statement:
- How the issue appears in actual classification work:
- Number of affected historical papers:
- Estimated future impact:

## Evidence
- Example paper IDs:
- Common analyst confusion pattern:
- QA findings supporting the issue:
- Relevant precedent IDs:
- Metrics demonstrating the problem:
- Stakeholder feedback:
- Tooling or reporting constraints:

## Proposed change
- Proposed new structure:
- Proposed updated definitions:
- Proposed inclusion criteria:
- Proposed exclusion criteria:
- Proposed migration rules:
- Backward compatibility considerations:
- Risks introduced by this change:

## Options analysis
### Option A
- Description:
- Pros:
- Cons:

### Option B
- Description:
- Pros:
- Cons:

### Option C
- Description:
- Pros:
- Cons:

## Decision
- Approved option:
- Decision date:
- Decided by:
- Implementation owner:
- Documentation owner:
- Analyst communication owner:
- Historical backfill required?:
- QA monitoring period after release:
```

---

# 6) QA Sampling Plan

## Purpose

This document defines what QA will review in a given cycle, how samples are chosen, and what risk areas deserve extra attention.

## Template

```md
# QA Sampling Plan

## Plan header
- QA cycle:
- Week / period:
- Prepared by:
- Approved by:
- Date issued:

## QA objectives
- Primary objective:
- Secondary objective:
- Known risk areas for this cycle:
- New taxonomy or precedent changes to monitor:
- Special backlog segments to sample:

## Sample design
- Total papers finalized in prior period:
- Planned sample size:
- Baseline random sample size:
- Risk-based oversample size:
- Reopened case sample size:
- New analyst sample size:
- New / changed taxonomy sample size:

## Sampling logic
- Random sampling method:
- Risk indicators used:
- Confidence thresholds triggering inclusion:
- Analyst-specific coverage rules:
- Collection / subcollection coverage rules:

## Targeted checks
- Main collections requiring extra scrutiny:
- Subcollections requiring extra scrutiny:
- Known error patterns to inspect:
- Specific precedent IDs to verify compliance against:

## Ownership and timing
- Reviewers assigned:
- Review start date:
- Review completion target:
- Calibration checkpoint date:
- Reporting deadline:
```

---

# 7) QA Disposition Form

## Purpose

Use one form per reviewed paper or per reviewed case bundle, depending on your QA granularity model.

## Template

```md
# QA Disposition Form

## Review metadata
- QA review ID:
- Paper ID:
- Batch ID:
- Analyst:
- Reviewer:
- Date reviewed:
- Review type:
  - [ ] Random sample
  - [ ] Risk-based sample
  - [ ] New analyst review
  - [ ] Rework review
  - [ ] Targeted audit

## Original decision
- Original main collection:
- Original subcollection:
- Analyst confidence:
- Analyst used precedent?:
- Analyst used escalation?:

## QA findings
- QA result:
  - [ ] Correct
  - [ ] Minor issue, classification still acceptable
  - [ ] Incorrect main collection
  - [ ] Incorrect subcollection
  - [ ] Insufficient evidence documented
  - [ ] Taxonomy ambiguity exposed
  - [ ] Tooling / UI issue contributed
- Severity of finding:
- Description of finding:
- Root cause category:
  - [ ] Taxonomy misunderstanding
  - [ ] Precedent not applied
  - [ ] Insufficient review
  - [ ] Data quality problem
  - [ ] Tooling issue
  - [ ] Training gap
  - [ ] Taxonomy defect

## Corrective action
- Correct final main collection:
- Correct final subcollection:
- Rework required?:
- Rework owner:
- Due date:
- Add to precedent log?:
- Raise taxonomy change request?:
- Include in training material?:

## Reviewer comments
- What the analyst did well:
- What should change next time:
- Notes for calibration:
```

---

# 8) Adjudication Record

## Purpose

Use when analyst, QA, and/or taxonomy owners disagree and a formal decision is needed.

## Template

```md
# Adjudication Record

## Case header
- Adjudication ID:
- Related paper ID(s):
- Related QA ID(s):
- Related precedent ID(s):
- Related TCR ID(s):
- Case owner:
- Date opened:
- Decision deadline:
- Status:

## Participants
- Analyst(s):
- QA reviewer(s):
- QA lead:
- Taxonomy lead:
- Operations representative:
- Program lead involved?:

## Disputed issue
- Precise question to adjudicate:
- Option 1:
- Option 2:
- Option 3:
- Why this requires adjudication:

## Evidence summary
- Paper summary:
- Taxonomy clauses:
- Existing precedents:
- Historical classification consistency check:
- Metrics / volume implications:
- Operational implications:
- Risks of each option:

## Decision
- Final ruling:
- Decision rationale:
- Tie-break principle used:
- Who approved:
- Effective date:
- Is precedent required?:
- Is taxonomy change required?:
- Historical rework required?:

## Follow-through
- Owner of documentation update:
- Owner of analyst communication:
- Owner of QA monitoring:
- Owner of system / tooling changes:
- Date closed:
```

---

# 9) Weekly Analyst Status Template

## Purpose

Each analyst submits this status update at the end of the workweek or before the weekly operations review.

## Template

```md
# Weekly Analyst Status

## Header
- Analyst:
- Week:
- Team / queue:
- Date submitted:

## Throughput
- Papers assigned:
- Papers completed:
- Papers finalized without review:
- Papers sent for review:
- Papers escalated:
- Papers reopened:
- Average handling time:
- Current backlog:

## Quality and uncertainty
- Average confidence score:
- Number of low-confidence cases (1–2):
- Number of medium-confidence cases (3):
- Number of precedent-dependent cases:
- Most common ambiguity pattern observed:

## Issues and blockers
- Taxonomy blockers:
- Tooling / data blockers:
- Workflow blockers:
- SLA risks:
- Help needed:

## Improvement signals
- Candidate new precedent:
- Candidate taxonomy change:
- Training topics needed:
- Suggested process improvement:

## Next-week focus
- Priority queues:
- Risk areas to watch:
- Personal support request:
```

---

# 10) Weekly Operations Report

## Purpose

Owned by the Operations Manager. Consolidates production, backlog, SLA, staffing, risk, and dependency signals.

## Template

```md
# Weekly Operations Report

## Report metadata
- Report ID:
- Week:
- Prepared by:
- Reviewed by:
- Date published:

## Executive summary
- Overall status:
  - [ ] Green
  - [ ] Yellow
  - [ ] Red
- One-paragraph summary:
- Biggest operational risk:
- Biggest quality risk:
- Biggest dependency risk:

## Volume and throughput
- Opening backlog:
- New intake:
- Total work available:
- Papers finalized:
- Papers in review:
- Papers in adjudication:
- Papers blocked:
- Closing backlog:
- Net backlog change:

## SLA performance
- SLA target:
- SLA achieved:
- Number of at-risk items:
- Number of breached items:
- Oldest open item age:
- Main breach drivers:

## Quality indicators
- QA sample size:
- QA pass rate:
- Major error rate:
- Minor error rate:
- Reopen rate:
- Top recurring error pattern:
- Collections / subcollections with highest correction rate:

## Staffing and capacity
- Planned capacity:
- Actual capacity:
- Analyst availability issues:
- Overtime or surge usage:
- Training time consumed:
- Forecast for next week:

## Escalations and dependencies
- Open escalations by severity:
- New escalations opened:
- Escalations resolved:
- Tooling issues open:
- Taxonomy issues open:
- External stakeholder blockers:

## Actions
- Decisions needed this week:
- Actions assigned:
- Owner per action:
- Due date per action:
```

---

# 11) Monthly Governance Report

## Purpose

Owned by the Program Director / Program Lead. Used to review the health of the whole program and decide structural changes.

## Template

```md
# Monthly Governance Report

## Report metadata
- Report ID:
- Month:
- Prepared by:
- Reviewed with:
- Date issued:

## Executive overview
- Overall program health:
- Major changes since last month:
- Key decisions made:
- Key unresolved issues:
- Executive asks / approvals needed:

## Production summary
- Total papers received:
- Total papers finalized:
- Backlog at start:
- Backlog at end:
- Median handling time:
- 90th percentile handling time:
- Reopen volume:
- High-ambiguity volume:

## Quality summary
- Total QA reviews:
- Pass rate:
- Critical error rate:
- Major error rate:
- Minor error rate:
- Top 3 root causes:
- Collections with highest variance:
- Analysts needing targeted support:

## Taxonomy governance
- Number of active precedents:
- New precedents added:
- Retired precedents:
- Taxonomy change requests opened:
- Taxonomy change requests approved:
- Backfill required due to taxonomy changes:
- Categories with chronic ambiguity:

## Operations and capacity
- Planned FTE:
- Effective FTE:
- Utilization estimate:
- Queue imbalance observations:
- Forecast next month:
- Hiring / staffing recommendations:

## Tooling and data
- Major tool issues:
- Major data integrity issues:
- Automation opportunities:
- Reporting improvements required:

## Decisions and actions
- Decision needed:
- Owner:
- Deadline:
- Expected impact:
```

---

# 12) SLA Breach / Aging Tracker

## Purpose

Use to track all items approaching or breaching target turnaround times.

## Template

```md
# SLA Breach / Aging Tracker

| Paper ID | Batch ID | Current status | Assigned owner | Age in queue (days) | SLA target (days) | Days to breach / days over | Root cause | Escalation ID | Recovery plan | ETA |
|---|---|---:|---|---:|---:|---:|---|---|---|---|
|  |  |  |  |  |  |  |  |  |  |  |
```

### Root cause categories

- Intake surge
- Reviewer shortage
- Taxonomy ambiguity
- Tooling issue
- Missing metadata
- Adjudication backlog
- Manual dependency
- Capacity planning error

---

# 13) Incident Review / Root Cause Analysis (RCA)

## When to use

Use for significant failures such as:

- a large misclassification cluster,
- missed SLA waves,
- broken taxonomy deployment,
- faulty automation causing incorrect assignments,
- missing or inconsistent reporting.

## Template

```md
# Incident Review / RCA

## Incident header
- Incident ID:
- Incident title:
- Date detected:
- Severity:
- Incident commander / owner:
- Current status:

## Incident summary
- What happened:
- When it started:
- When it was detected:
- How it was detected:
- Scope of impact:
- Number of papers affected:
- Collections / subcollections affected:
- Stakeholders affected:

## Containment
- Immediate actions taken:
- Work paused?:
- Temporary controls applied:
- Communication sent to:
- Date service stabilized:

## Root cause analysis
- Primary root cause:
- Contributing cause 1:
- Contributing cause 2:
- Why existing controls failed:
- Why the issue was not detected earlier:

## Corrective actions
- Action 1:
- Owner:
- Due date:
- Prevention effect expected:

- Action 2:
- Owner:
- Due date:
- Prevention effect expected:

- Action 3:
- Owner:
- Due date:
- Prevention effect expected:

## Closure
- Approval to close:
- Date closed:
- Follow-up review date:
```

---

# 14) Calibration Session Minutes

## Purpose

Use for weekly or biweekly consistency sessions between analysts, QA, taxonomy, and operations.

## Template

```md
# Calibration Session Minutes

## Session metadata
- Calibration ID:
- Date:
- Facilitator:
- Participants:
- Scope:
- Recording / notes link:

## Cases reviewed
| Paper ID | Original decision | Alternative considered | Final agreed decision | Why this case matters | Action needed |
|---|---|---|---|---|---|
|  |  |  |  |  |  |

## Decision patterns observed
- Pattern 1:
- Pattern 2:
- Pattern 3:

## Documentation impact
- New precedent required?:
- Precedent update required?:
- Taxonomy clarification required?:
- Training material update required?:

## Actions
- Action:
- Owner:
- Due date:
```

---

# 15) Analyst Onboarding and Certification Checklist

## Purpose

Use to certify that a new analyst can classify independently.

## Template

```md
# Analyst Onboarding and Certification Checklist

## Analyst profile
- Name:
- Start date:
- Manager / lead:
- Domain focus:
- Target certification date:

## Training completion
- [ ] Read taxonomy reference document
- [ ] Read classification tutorial
- [ ] Read workflow and communication playbook
- [ ] Read relevant precedents
- [ ] Completed tool walkthrough
- [ ] Completed escalation workflow training
- [ ] Completed QA feedback training
- [ ] Completed reporting and documentation training

## Practical evaluation
- [ ] Observed 1 live classification session
- [ ] Completed 10 supervised classifications
- [ ] Completed 25 reviewed classifications
- [ ] Demonstrated correct escalation usage
- [ ] Demonstrated precedent search usage
- [ ] Demonstrated evidence-based rationale writing

## Quality gates
- Trial QA pass rate:
- Critical errors observed:
- Major errors observed:
- Common weaknesses:
- Remediation required:

## Certification decision
- Recommendation:
  - [ ] Certified for independent work
  - [ ] Certified with restricted scope
  - [ ] Further supervision required
- Decided by:
- Date:
- Next review date:
```

---

# 16) KPI Glossary and Standard Formula Sheet

## Purpose

Use one standard definition set across all reports so that operations, QA, taxonomy, and leadership interpret metrics the same way.

## Template

```md
# KPI Glossary

## Throughput metrics
- Finalized papers:
  - Definition:
  - Formula:
  - Owner:
- Intake volume:
  - Definition:
  - Formula:
  - Owner:
- Net backlog change:
  - Definition:
  - Formula:
  - Owner:

## Timeliness metrics
- Average handling time:
  - Definition:
  - Formula:
  - Inclusion / exclusion rules:
- Median handling time:
  - Definition:
  - Formula:
- 90th percentile handling time:
  - Definition:
  - Formula:
- SLA attainment:
  - Definition:
  - Formula:

## Quality metrics
- QA pass rate:
  - Definition:
  - Formula:
- Major error rate:
  - Definition:
  - Formula:
- Critical error rate:
  - Definition:
  - Formula:
- Reopen rate:
  - Definition:
  - Formula:

## Taxonomy metrics
- Ambiguity rate:
  - Definition:
  - Formula:
- Precedent dependency rate:
  - Definition:
  - Formula:
- Taxonomy change request rate:
  - Definition:
  - Formula:
```

---

# 17) Program Decision Log

## Purpose

This log centralizes structural decisions affecting taxonomy, workflow, staffing, quality policy, or tools.

## Template

```md
# Program Decision Log

| Decision ID | Date | Decision owner | Topic | Decision summary | Reason | Affected roles | Follow-up required | Status |
|---|---|---|---|---|---|---|---|---|
|  |  |  |  |  |  |  |  |  |
```

### Notes to capture for each decision

- What changed
- Why the change was necessary
- What alternatives were rejected
- Which documents must be updated
- Which historical records need re-interpretation or backfill

---

# 18) Suggested repository structure for markdown operations

Use a folder layout like this in a shared repository or workspace:

```text
classification-program/
├── 00_governance/
│   ├── package_index.md
│   ├── program_decision_log.md
│   ├── monthly_governance_reports/
│   └── taxonomy_change_requests/
├── 01_taxonomy/
│   ├── taxonomy_reference.md
│   ├── precedent_log/
│   └── retired_precedents/
├── 02_operations/
│   ├── weekly_reports/
│   ├── backlog_trackers/
│   ├── escalation_tickets/
│   └── incident_reviews/
├── 03_quality/
│   ├── qa_sampling_plans/
│   ├── qa_dispositions/
│   ├── adjudications/
│   └── calibration_minutes/
├── 04_classification_work/
│   ├── analyst_status/
│   ├── review_requests/
│   └── paper_decision_records/
└── 05_enablement/
    ├── onboarding/
    ├── training_materials/
    └── kpi_glossary.md
```

---

## Minimum viable operating set

If you want the **smallest** artifact set that still runs the program safely, start with these seven:

1. Paper Classification Decision Record
2. Review Request / Handoff Pack
3. Escalation Ticket
4. Precedent Log Entry
5. QA Disposition Form
6. Weekly Operations Report
7. Monthly Governance Report

---

## Recommended ownership summary

| Artifact | Primary author | Approver / validator | Main consumer |
|---|---|---|---|
| Paper Classification Decision Record | Analyst | Team Lead / QA | QA, taxonomy, future analysts |
| Review Request / Handoff Pack | Analyst | Receiving owner validates completeness | Team Lead, QA, taxonomy |
| Escalation Ticket | Any role | Operations Manager or designated owner | Cross-functional leads |
| Precedent Log Entry | QA Lead / Taxonomy Lead | Taxonomy Lead or Program Lead | Analysts and QA |
| Taxonomy Change Request | Taxonomy Lead / QA / Ops | Program Lead | Governance group |
| QA Sampling Plan | QA Lead | Operations Manager | QA reviewers |
| QA Disposition Form | QA reviewer | QA Lead | Analysts, leads, reporting |
| Adjudication Record | QA Lead / Taxonomy Lead | Program Lead if needed | All role owners |
| Weekly Operations Report | Operations Manager | Program Lead | All leads |
| Monthly Governance Report | Program Lead | Governance stakeholders | Leadership and leads |
| Incident Review / RCA | Ops / Data Analyst | Program Lead | Leadership and process owners |
| Calibration Minutes | QA Lead / Team Lead | Taxonomy Lead | Analysts, QA, training |

---

## Final implementation advice

Do not deploy every artifact on day one unless your volume already justifies it.

A strong rollout sequence is:

### Phase 1 — essential controls
- Paper Classification Decision Record
- Review Request / Handoff Pack
- Escalation Ticket
- QA Disposition Form
- Weekly Operations Report

### Phase 2 — consistency controls
- Precedent Log Entry
- Calibration Session Minutes
- KPI Glossary
- Analyst Onboarding Checklist

### Phase 3 — governance controls
- Taxonomy Change Request
- Adjudication Record
- Monthly Governance Report
- Incident Review / RCA
- Program Decision Log

This sequencing keeps the documentation burden proportional while still protecting quality and consistency.

---

## Closing note

This template library is intentionally structured so it can be used:

- as markdown files in Git,
- as wiki pages in Notion / Confluence,
- as ticket templates in Jira,
- or as promptable forms for agent workflows.

Each template is precise enough to support both human-operated teams and multi-agent systems.
