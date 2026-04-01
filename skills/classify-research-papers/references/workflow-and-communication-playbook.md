# Workflow and Communication Playbook for the Research Paper Classification Program

## Purpose

This document defines the **precise operating workflow, handoff structure, escalation path, and communication process** for every role in the paper-classification team.

It complements the other package documents by answering four questions in operational detail:

1. **What exactly does each role do, in what order, and at what cadence?**
2. **When and how does one role hand work to another?**
3. **What communication channel, artifact, and response time should be used for each type of exchange?**
4. **Who decides, who reviews, who approves, and who is merely informed?**

The document assumes a controlled research paper classification program with a **2-layer taxonomy**:

- **Level 1** = main collection
- **Level 2** = subcollection inside that main collection

---

## 1. Operating model assumptions

This playbook is written for the staffing model already defined in the package.

### Core roles

1. **Classification Program Director / Program Lead**
2. **Taxonomy Lead / Knowledge Architect**
3. **Classification Operations Manager**
4. **QA & Adjudication Lead**
5. **Classification Team Lead / Senior Lead** *(optional but recommended at 6+ analysts)*
6. **Classification Analysts**
7. **Data / Tooling Analyst**

### Two deployment variants

#### Variant A — 11 FTE model

- 1 Program Director
- 1 Taxonomy Lead
- 1 Operations Manager
- 1 QA & Adjudication Lead
- 6 Classification Analysts
- 1 Data / Tooling Analyst

In this model, **the Operations Manager absorbs Team Lead duties** or designates one analyst as a rotating shift coordinator without changing headcount.

#### Variant B — 12 FTE model

- 1 Program Director
- 1 Taxonomy Lead
- 1 Operations Manager
- 1 QA & Adjudication Lead
- 1 Team Lead / Senior Lead
- 6 Classification Analysts
- 1 Data / Tooling Analyst

In this model, the **Team Lead owns day-to-day analyst supervision**, while the Operations Manager stays focused on throughput, queue design, SLA control, and cross-functional operating issues.

### Default recommendation

Use **Variant B** if:

- analysts are junior,
- the taxonomy is still evolving,
- the corpus is broad and ambiguous,
- rework is frequent,
- or you want tighter day-to-day discipline.

Use **Variant A** only when the team is experienced and the operation is stable.

---

## 2. Governing principles for all workflows

All roles follow these seven rules:

1. **The taxonomy reference document is the primary authority.**
2. **The precedent log is the secondary authority.**
3. **Every finalized classification decision must be durable, reviewable, and auditable.**
4. **Chat is never the system of record.** All binding decisions must be written into a tracked artifact.
5. **Escalations must be typed.** Every escalated case must state the exact problem type.
6. **One paper must have one current owner at all times.**
7. **No role may silently reinterpret taxonomy rules.** Semantic change belongs to taxonomy governance, not informal practice.

---

## 3. Canonical lifecycle of a paper

This is the standard end-to-end lifecycle for one paper record.

## 3.1 Lifecycle statuses

Use these statuses in the case-management system, tracker, or spreadsheet.

| Status | Meaning | Current owner |
|---|---|---|
| `NEW` | Record ingested but not yet checked for usability | Data / Tooling Analyst |
| `READY_FOR_ROUTING` | Record is usable and awaits queue assignment | Operations Manager |
| `ASSIGNED` | Paper is assigned to an analyst | Team Lead or Operations Manager |
| `IN_PRIMARY_REVIEW` | Analyst is actively classifying the paper | Classification Analyst |
| `PENDING_ANALYST_QUERY` | Analyst needs a non-semantic clarification or missing asset fix | Team Lead, Ops, or Data depending on issue |
| `PENDING_QA` | Paper requires review because of low confidence or policy trigger | QA & Adjudication Lead |
| `PENDING_TAXONOMY` | Semantic dispute or taxonomy-gap case awaiting decision | Taxonomy Lead |
| `PENDING_DATA_FIX` | Record cannot proceed due to missing/corrupt metadata, broken link, duplicate, or ingestion issue | Data / Tooling Analyst |
| `RETURNED_FOR_REWORK` | Reviewer has sent the case back to analyst for correction or fuller rationale | Classification Analyst |
| `FINAL_APPROVED` | Classification is accepted as final | No active owner; retained in ledger |
| `DEFERRED` | Paper is intentionally held pending a larger policy decision or source remediation | Operations Manager or Program Director |
| `EXCLUDED` | Paper is not in scope for classification | Operations Manager with QA validation |

## 3.2 Standard lifecycle steps

### Step 0 — Intake and record validation
**Owner:** Data / Tooling Analyst

1. Import paper metadata and source link or file.
2. Validate required fields:
   - paper ID
   - title
   - abstract or equivalent summary
   - authors
   - year
   - source link or document access
3. Detect obvious duplicates using ID, title similarity, DOI, or source metadata.
4. Flag corrupt or missing records.
5. Mark valid records as `READY_FOR_ROUTING`.

**Output artifact:** ingestion validation log

---

### Step 1 — Queue design and routing
**Owner:** Operations Manager  
**Supporting owner:** Team Lead if present

1. Segment papers into work batches based on:
   - source stream,
   - discipline cluster,
   - expected complexity,
   - SLA priority,
   - backlog age.
2. Assign batches to analysts or to the Team Lead for analyst-level distribution.
3. Set due dates and priority codes.
4. Mark records as `ASSIGNED`.

**Output artifact:** assignment roster / queue board

---

### Step 2 — Primary classification
**Owner:** Classification Analyst

1. Review title, abstract, keywords, venue, and where needed methods/contribution language.
2. Determine the most appropriate **main collection**.
3. Determine the most appropriate **subcollection within that main collection**.
4. Write evidence-based reasoning.
5. Assign a confidence score.
6. Either:
   - finalize the recommendation directly if within policy, or
   - escalate if any trigger is met.

**Output artifact:** primary classification record

---

### Step 3 — First-line support and supervision
**Owner:** Team Lead or Operations Manager

1. Resolve workflow blockers that do not require semantic adjudication.
2. Rebalance analyst workload.
3. Check whether the analyst escalation belongs to:
   - QA,
   - Taxonomy,
   - Data / Tooling,
   - or simple analyst coaching.
4. Ensure every escalated item is properly typed and documented.

**Output artifact:** triaged escalation ticket

---

### Step 4 — QA review and adjudication
**Owner:** QA & Adjudication Lead

Cases enter QA through two paths:

- **mandatory QA path**
  - low-confidence cases,
  - ambiguous border cases under current taxonomy,
  - new analyst work,
  - sampled audits,
  - returned/reworked cases

- **exception QA path**
  - stakeholder challenge,
  - policy sensitivity,
  - repeated analyst disagreement

QA then:

1. Reviews the analyst rationale and the paper evidence.
2. Confirms or rejects the classification.
3. Sends back for rework if the issue is execution quality.
4. Escalates to Taxonomy if the issue is semantic or structural.

**Output artifact:** QA disposition record

---

### Step 5 — Taxonomy decision
**Owner:** Taxonomy Lead / Knowledge Architect

This step applies only when the case reveals one of the following:

- unclear boundary between existing tags,
- inconsistent precedent,
- taxonomy gap,
- candidate split/merge/rename issue,
- repeated borderline confusion across analysts.

Taxonomy then:

1. Determines whether the current taxonomy already contains a correct answer.
2. If yes, issues a semantic ruling and precedent.
3. If no, drafts the smallest stable taxonomy change required.
4. Sends recommendation to Program Director if approval is needed.

**Output artifact:** taxonomy ruling / precedent entry / change proposal

---

### Step 6 — Final approval and ledger closure
**Owner:** QA & Adjudication Lead for paper-level closure  
**Owner:** Program Director for major policy exceptions

1. Ensure the case record includes:
   - final main collection
   - final subcollection
   - rationale
   - confidence
   - reviewer identity
   - precedent reference if used
2. Change the record to `FINAL_APPROVED`.
3. If the case drove a new precedent or policy change, notify operations and training channels.

**Output artifact:** finalized classification ledger entry

---

### Step 7 — Reporting, calibration, and feedback loop
**Owners:** QA Lead, Operations Manager, Taxonomy Lead, Data / Tooling Analyst, Program Director

1. QA reports error trends and disagreement patterns.
2. Operations reports throughput, backlog, and SLA compliance.
3. Taxonomy reports semantic hotspots and proposed definition changes.
4. Data / Tooling reports data issues, automation opportunities, and dashboard trends.
5. Program Director approves corrective action.

**Output artifacts:**
- weekly quality report
- weekly operations report
- taxonomy issue log
- monthly steering report

---

## 4. Mandatory escalation triggers

These are non-optional triggers. If one occurs, the case must not be silently finalized.

### 4.1 Analyst to Team Lead / Operations / QA triggers

Escalate when any of the following is true:

- confidence is below the program threshold, for example **< 0.80**
- two candidate subcollections remain plausible after normal review
- main collection choice is still uncertain after reading abstract plus one deeper evidence source
- the paper appears to fit **none** of the available tags
- the analyst suspects a duplicate or near-duplicate
- the record is missing critical evidence
- the analyst needs more than the allowed handling-time threshold without reaching a clear decision
- the paper may trigger a known exception policy
- the analyst sees a conflict between the taxonomy document and the precedent log

### 4.2 QA to Taxonomy triggers

Escalate to Taxonomy when any of the following is true:

- the issue is not analyst error but **tag-boundary ambiguity**
- the same confusion appears across multiple analysts or batches
- existing tag definitions produce contradictory outcomes
- a new research theme seems to be emerging outside the current tree
- adjudication cannot be completed without clarifying the meaning of a tag

### 4.3 Any functional lead to Program Director triggers

Escalate to Program Director when any of the following is true:

- a taxonomy change affects reporting, customers, or historical comparability
- a large reclassification campaign may be required
- quality and throughput targets are in structural conflict
- one function is blocked by another for more than the agreed threshold
- there is disagreement among Ops, QA, and Taxonomy that cannot be resolved at lead level
- a stakeholder demands an exception that conflicts with policy

---

## 5. Detailed workflow for each role

Each role description below uses the same structure:

- mission
- ownership
- daily workflow
- weekly workflow
- monthly / triggered workflow
- inputs
- outputs
- decision rights
- escalation responsibilities
- communication obligations

---

## 5.1 Classification Program Director / Program Lead

### Mission

Be the **single accountable owner** of the entire classification program so that taxonomy, operations, quality, and tooling remain aligned.

### Core ownership

The Program Director owns:

- program charter
- service levels
- quality thresholds
- headcount and staffing plan
- conflict resolution across functions
- approval of major taxonomy changes
- approval of reclassification campaigns
- stakeholder communication
- risk ownership

### Daily workflow

1. Review the executive dashboard by the start of the operating day:
   - backlog size
   - age of oldest items
   - papers finalized yesterday
   - escalation queue size
   - QA fail rate
   - blocked cases by owner
2. Check for any red-flag issues:
   - SLA breach risk
   - quality spike
   - unresolved cross-functional conflict
   - tooling outage
   - taxonomy bottleneck
3. Contact the relevant lead immediately if:
   - a blocker is cross-functional,
   - a queue is aging beyond threshold,
   - or a governance decision is needed.
4. Confirm that all critical escalations have a named owner and decision deadline.
5. Update the risk log if any issue threatens delivery or quality.

### Weekly workflow

1. Chair the **weekly cross-functional operating review**.
2. Review:
   - throughput vs plan
   - backlog by queue
   - QA pass/fail and rework rates
   - top taxonomy ambiguities
   - tooling incidents and automation opportunities
   - staffing risks and training gaps
3. Decide corrective actions:
   - staffing changes
   - temporary queue reprioritization
   - calibration emphasis
   - taxonomy clarification requests
   - tooling fixes or automation trials
4. Approve or reject proposed exceptions that exceed lead-level authority.
5. Publish a short weekly decision memo.

### Monthly / triggered workflow

1. Review month-end performance against:
   - throughput target
   - backlog target
   - quality threshold
   - turnaround-time target
   - cost / effort assumptions
2. Approve or reject:
   - taxonomy release packages
   - large-scale reclassification plans
   - revised staffing plans
   - tooling investment priorities
3. Meet stakeholders and explain:
   - progress
   - risks
   - expected changes
   - policy decisions
4. Trigger a formal root-cause review if:
   - audit accuracy drops below threshold,
   - backlog trend worsens for two consecutive periods,
   - or taxonomy change demand becomes excessive.

### Inputs

- executive dashboard
- weekly operations report
- weekly QA report
- taxonomy issue register
- taxonomy change proposals
- incident log
- staffing and utilization report

### Outputs

- operating decisions
- priority decisions
- policy exception decisions
- approval or rejection of major changes
- weekly decision memo
- monthly steering report

### Decision rights

The Program Director decides:

- final program priorities
- escalation policy
- acceptance of major taxonomy changes
- resourcing changes
- reclassification campaign approval
- final arbitration across leads

### Escalation responsibilities

The Program Director must resolve, not merely forward, any issue that crosses functional boundaries and remains unresolved after lead-level discussion.

### Communication obligations

The Program Director must maintain direct operating contact with:

- Taxonomy Lead
- Operations Manager
- QA Lead
- Data / Tooling Analyst

and indirect but visible contact with:

- Team Lead
- Analysts during calibration or all-hands sessions

---

## 5.2 Taxonomy Lead / Knowledge Architect

### Mission

Own the **meaning, boundary logic, stability, and controlled evolution** of the taxonomy.

### Core ownership

The Taxonomy Lead owns:

- tag definitions
- inclusion and exclusion rules
- border-case precedent
- merge / split / rename recommendations
- taxonomy version control
- controlled semantic change

### Daily workflow

1. Review new taxonomy escalations.
2. Triage each case into one of five issue types:
   - simple boundary clarification
   - repeated boundary conflict
   - taxonomy gap
   - inconsistent precedent
   - structural change candidate
3. For each case:
   1. read the paper evidence,
   2. read the current tag definitions,
   3. read the strongest competing tag definitions,
   4. inspect precedent,
   5. issue one of three outcomes:
      - current taxonomy already resolves the case,
      - current taxonomy needs clarification only,
      - structural change is warranted.
4. Record a written ruling.
5. If the ruling creates a reusable decision pattern, add it to the precedent log the same day or next business day.

### Weekly workflow

1. Review all taxonomy escalations from the week and cluster them.
2. Identify:
   - tags with chronic confusion,
   - subcollections with weak boundaries,
   - overloaded or underused tags,
   - possible new research themes.
3. Run a **taxonomy working session** with QA and Operations:
   - review top ambiguous cases,
   - identify whether the issue is taxonomy, training, or execution.
4. Update definitions or decision notes as needed.
5. Issue release notes for any approved semantic clarification.

### Monthly / triggered workflow

1. Prepare a monthly taxonomy health review:
   - number of semantic escalations
   - repeated confusion areas
   - candidate tag changes
   - projected reclassification impact
2. Draft change proposals for:
   - merge
   - split
   - rename
   - deprecate
   - create new subcollection
3. Estimate impact:
   - number of historical papers affected
   - retraining cost
   - reporting impact
4. Submit major changes to Program Director for approval.
5. After approval, publish:
   - new definitions,
   - migration guidance,
   - effective date,
   - change summary.

### Inputs

- taxonomy escalation tickets
- taxonomy reference document
- precedent log
- weekly QA disagreement report
- operations confusion summary
- historical examples from affected tags

### Outputs

- taxonomy rulings
- precedent entries
- clarified definitions
- taxonomy change proposals
- taxonomy release notes

### Decision rights

The Taxonomy Lead decides:

- semantic interpretation of existing tags
- official border-case rulings
- definition updates that do not change top-level policy
- recommended structural taxonomy changes

### Escalation responsibilities

The Taxonomy Lead escalates to Program Director when the semantic decision has material downstream impact on delivery, reporting, or reclassification volume.

### Communication obligations

The Taxonomy Lead must maintain regular communication with:

- QA Lead for escalated ambiguities
- Operations Manager for training and rollout implications
- Data / Tooling Analyst for taxonomy implementation changes
- Program Director for approval of major changes

The Taxonomy Lead should **not** become the default first-line support for analysts. Routine analyst confusion should first pass through Team Lead or QA, unless the question is plainly semantic.

---

## 5.3 Classification Operations Manager

### Mission

Run the classification operation so that work is routed, balanced, completed on time, and escalated correctly.

### Core ownership

The Operations Manager owns:

- queue design
- batch planning
- assignment logic
- productivity management
- backlog management
- turnaround performance
- workflow compliance
- operating rhythm

### Daily workflow

1. Start the day by reviewing queue health:
   - new inflow
   - open backlog
   - aging distribution
   - analyst capacity
   - blocked items
2. Confirm batch priorities for the day.
3. Assign or confirm batch allocation.
4. Check whether any analysts are overloaded or underloaded.
5. Re-route items when:
   - skill fit is poor,
   - backlog is aging,
   - or priority has changed.
6. Monitor escalations and ensure every escalated item has reached the correct destination.
7. Resolve operational blockers such as:
   - unclear assignment,
   - missing priority,
   - overdue queue,
   - absent analyst coverage,
   - conflicting due dates.
8. End the day by checking actual completions vs plan.

### Weekly workflow

1. Produce the weekly operations report:
   - finalized papers
   - backlog by queue
   - average handling time
   - aging
   - productivity by batch
   - rework volume
   - blocked-case counts
2. Meet Team Lead, QA, and Data / Tooling to review operational friction.
3. Update routing rules if certain queues are repeatedly misallocated.
4. Confirm next week's capacity plan.
5. Raise risks to Program Director when throughput goals are threatened.

### Monthly / triggered workflow

1. Reforecast backlog clearance and steady-state capacity.
2. Revisit staffing assumptions.
3. Review whether:
   - some queues need specialization,
   - some analysts need retraining,
   - some work should be temporarily quarantined due to taxonomy instability.
4. Propose process changes to Program Director.
5. Approve updated workflow instructions after QA and Taxonomy alignment.

### Inputs

- intake queue
- analyst availability
- current priorities
- dashboard metrics
- QA rework trends
- taxonomy clarification notices
- tooling incident reports

### Outputs

- daily assignment plan
- queue board
- weekly operations report
- risk notices
- routing rule changes
- capacity forecast

### Decision rights

The Operations Manager decides:

- who works on what,
- queue priority order,
- batch composition,
- turnaround mitigation actions,
- and operational exception handling within policy.

### Escalation responsibilities

The Operations Manager escalates when:

- throughput is threatened by taxonomy or QA bottlenecks,
- blocked cases accumulate beyond threshold,
- staffing is insufficient,
- or cross-functional cooperation is failing.

### Communication obligations

The Operations Manager must maintain structured daily contact with:

- Team Lead
- QA Lead
- Data / Tooling Analyst

and regular policy contact with:

- Taxonomy Lead
- Program Director

---

## 5.4 QA & Adjudication Lead

### Mission

Protect classification accuracy, consistency, and auditability through review, adjudication, calibration, and quality reporting.

### Core ownership

The QA Lead owns:

- review criteria
- audit sampling
- ambiguous-case adjudication under current policy
- return-for-rework decisions
- calibration sessions
- quality metrics
- root-cause analysis of errors

### Daily workflow

1. Review all cases arriving in `PENDING_QA`.
2. Separate them into:
   - simple low-confidence review,
   - clear analyst error,
   - true ambiguity,
   - possible taxonomy issue,
   - training issue.
3. For each case:
   1. read the analyst rationale,
   2. review the paper evidence,
   3. compare with taxonomy and precedent,
   4. issue a disposition:
      - approve,
      - correct and finalize,
      - return for rework,
      - escalate to taxonomy.
4. Track error reasons in a coded quality log.
5. Sample a percentage of otherwise finalized work for audit.
6. Notify Team Lead or Ops immediately if a systemic analyst error pattern is detected.

### Weekly workflow

1. Produce the weekly QA report:
   - number reviewed
   - approval rate
   - correction rate
   - return-for-rework rate
   - top error categories
   - disagreement hotspots
2. Run the weekly calibration meeting with analysts and Team Lead.
3. Prepare a concise list of cases needing taxonomy attention.
4. Recommend corrective actions:
   - analyst coaching
   - instruction change
   - precedent update
   - taxonomy clarification
5. Validate whether previous error trends are improving.

### Monthly / triggered workflow

1. Run a deeper quality audit.
2. Measure:
   - inter-review consistency
   - analyst-specific error concentration
   - error rate by queue or domain
   - drift vs earlier periods
3. Recommend threshold changes if confidence scoring is not predictive enough.
4. Escalate systemic semantic problems to Taxonomy.
5. Escalate serious quality risk to Program Director.

### Inputs

- analyst classification records
- taxonomy reference
- precedent log
- sampled papers
- historical QA metrics
- rework history

### Outputs

- QA dispositions
- adjudication records
- weekly QA report
- calibration agenda
- error coding log
- taxonomy escalation bundle

### Decision rights

The QA Lead decides:

- whether a paper passes review,
- whether it requires rework,
- whether it can be adjudicated within current policy,
- and when an issue must be escalated to Taxonomy.

### Escalation responsibilities

The QA Lead must escalate semantic, structural, and repeated ambiguity issues to Taxonomy, and escalate material quality risk to Program Director.

### Communication obligations

The QA Lead must maintain frequent structured contact with:

- Team Lead / Operations for coaching and rework
- Taxonomy Lead for ambiguity and precedent
- Program Director for quality-risk reporting
- Data / Tooling Analyst for data-quality-driven misclassification patterns

---

## 5.5 Classification Team Lead / Senior Lead

### Mission

Be the day-to-day production leader closest to the analysts.

### Core ownership

The Team Lead owns:

- analyst task allocation within the shift or day
- first-line coaching
- first-line review of low-confidence work when configured
- analyst discipline and compliance
- immediate escalation routing
- shift-level performance visibility

### Daily workflow

1. Start the day with a short analyst standup:
   - priorities
   - blockers
   - special instructions
   - known taxonomy clarifications
2. Distribute work across analysts according to:
   - queue priority,
   - analyst skill fit,
   - analyst capacity,
   - training needs.
3. Monitor work-in-progress during the day.
4. Answer routine procedural questions.
5. Review analyst escalations and route them correctly:
   - to QA for decision review,
   - to Taxonomy via QA for semantic boundary issues,
   - to Data / Tooling for broken records,
   - to Ops for reprioritization.
6. Perform spot checks on analyst rationale quality.
7. Coach analysts immediately when repeatable execution issues appear.
8. Close the day with:
   - completion count,
   - open blockers,
   - cases requiring next-day attention.

### Weekly workflow

1. Review analyst-level metrics:
   - volume
   - rework rate
   - average handling time
   - escalation rate
   - common error types
2. Prepare a coaching plan for each analyst who needs support.
3. Bring repeatable confusion themes to QA and Taxonomy.
4. Confirm coverage with Operations for the following week.

### Monthly / triggered workflow

1. Support analyst performance reviews.
2. Confirm which analysts are ready for greater autonomy.
3. Identify where specialization is needed.
4. Help Ops redesign queue distribution if certain analysts are consistently mismatched to queues.

### Inputs

- assignment plan
- analyst workload
- current queue priorities
- QA feedback
- taxonomy notices
- dashboard snippets

### Outputs

- analyst allocations
- triaged escalation tickets
- coaching notes
- shift summary
- analyst performance signals

### Decision rights

The Team Lead decides:

- day-to-day analyst distribution within the assigned queue,
- first-line coaching actions,
- whether an analyst case needs immediate escalation,
- and whether an analyst should keep or relinquish a difficult batch.

### Escalation responsibilities

The Team Lead escalates:

- quality patterns to QA,
- semantic patterns to Taxonomy through the correct path,
- capacity and backlog concerns to Operations,
- severe personnel or discipline concerns to Program Director through Ops.

### Communication obligations

The Team Lead is the most communication-intensive role in the operating day. This role must maintain near-continuous contact with analysts and structured contact with Ops and QA.

### If this role does not exist

In the 11 FTE model, the **Operations Manager temporarily absorbs these duties**. The workflow remains the same, but the owner field changes from Team Lead to Operations Manager.

---

## 5.6 Classification Analyst

### Mission

Read each paper record and produce the best-supported classification into one main collection and one subcollection, with explicit rationale and confidence.

### Core ownership

The Analyst owns:

- paper-level review
- evidence extraction
- tag selection
- rationale writing
- confidence assignment
- timely escalation when policy requires it

### Daily workflow

For each paper:

1. Open the paper record and confirm the record is usable.
2. Review available evidence in this order:
   1. title
   2. abstract
   3. keywords
   4. venue or source category
   5. methods / contribution sentence if needed
3. Identify the **paper’s primary contribution or topical center of gravity**.
4. Compare candidate main collections.
5. Select the best main collection.
6. Compare subcollections only **within that chosen main collection**.
7. Select the best subcollection.
8. Record a concise rationale:
   - why the chosen main collection fits,
   - why the chosen subcollection fits,
   - why the closest competing option was not chosen.
9. Assign a confidence score.
10. Decide one of three outcomes:
   - finalize under normal policy,
   - request support,
   - escalate to QA / Data / Ops based on trigger.
11. Move immediately to the next item unless a blocker requires active follow-up.

### Evidence standard

The analyst rationale should cite the paper’s actual content, not intuition. The preferred evidence order is:

1. explicit problem statement
2. explicit method statement
3. explicit domain statement
4. venue / source clues
5. keyword clues

### Weekly workflow

1. Attend calibration.
2. Review returned cases and understand correction reasons.
3. Update personal error checklist.
4. Raise recurring confusion to Team Lead.

### Monthly / triggered workflow

1. Review personal metrics and coaching notes.
2. Complete refresher training on taxonomy changes.
3. Demonstrate understanding of newly issued precedents.

### Inputs

- assigned paper records
- taxonomy reference document
- precedent log
- analyst work instructions
- recent taxonomy clarifications

### Outputs

- completed classification records
- analyst rationale
- confidence score
- escalation ticket when needed

### Decision rights

The Analyst decides the paper-level recommendation within the current taxonomy and policy. The Analyst does **not** change definitions, invent new tags, or silently create exceptions.

### Escalation responsibilities

The Analyst must escalate rather than guess whenever a mandatory trigger applies.

### Communication obligations

The Analyst primarily communicates with:

- Team Lead
- QA Lead
- Operations when assignment or deadline is unclear
- Data / Tooling when record quality blocks review

The Analyst should rarely contact Program Director directly.

---

## 5.7 Data / Tooling Analyst

### Mission

Provide clean records, reliable instrumentation, usable workflow tooling, and decision-support analytics.

### Core ownership

The Data / Tooling Analyst owns:

- ingestion integrity
- data quality checks
- duplicate detection
- dashboard production
- operational instrumentation
- workflow-system improvements
- automation analysis

### Daily workflow

1. Review ingestion jobs and error logs.
2. Validate new records.
3. Resolve or triage:
   - missing metadata
   - broken links
   - duplicate records
   - malformed IDs
   - status-sync errors
4. Maintain the operational dashboard.
5. Respond to analyst or Ops data-fix tickets.
6. Track system defects and manual workarounds.
7. Flag any tooling issue that distorts productivity or quality reporting.

### Weekly workflow

1. Publish data-quality and tooling health summary:
   - ingested records
   - rejected records
   - duplicates resolved
   - open data-fix tickets
   - tooling incidents
   - dashboard anomalies
2. Review repeated data issues by source and recommend upstream fixes.
3. Partner with Ops and QA to see whether tooling can reduce rework or misrouting.
4. Prototype or specify workflow improvements.

### Monthly / triggered workflow

1. Review instrumentation against operating needs.
2. Propose automation candidates, for example:
   - pre-clustering papers by likely domain,
   - duplicate pre-screening,
   - confidence-risk surfacing,
   - queue aging alerts.
3. Estimate gain, cost, and operational risk.
4. Implement approved dashboard or workflow changes with change notes.

### Inputs

- source feeds
- ingestion logs
- data-fix tickets
- dashboard requirements
- QA error codes
- operations pain points
- taxonomy structure changes

### Outputs

- validated records
- dashboard updates
- incident tickets
- data-fix resolutions
- automation proposals
- implementation notes

### Decision rights

The Data / Tooling Analyst decides:

- how data validation is executed,
- how dashboards and metrics are computed within approved definitions,
- how to implement approved tooling changes.

### Escalation responsibilities

The Data / Tooling Analyst escalates when:

- source data quality materially harms classification,
- system issues block workflow,
- measurement definitions are disputed,
- or tooling changes require governance approval.

### Communication obligations

This role maintains direct working contact with:

- Operations for queue and dashboard needs
- QA for error-trend instrumentation
- Taxonomy for implementation of taxonomy changes
- Program Director for investment priorities

---

## 6. Detailed communication and exchange process

The communication model must separate **fast coordination** from **authoritative record keeping**.

## 6.1 Approved communication layers

### Layer A — Fast coordination
Used for short operational clarifications, for example:

- “Queue B is reassigned.”
- “Case 1287 needs data repair.”
- “Calibration moved to 3 PM.”

**Channel examples:** chat, team messaging, standup meeting

**Rule:** not authoritative; all binding decisions must be copied into a tracked artifact.

### Layer B — Tracked operational artifacts
Used for work that changes queue status, ownership, or required action.

**Channel examples:**
- case-management ticket
- issue tracker
- spreadsheet row with locked audit fields
- workflow board comment

**Rule:** authoritative for operational ownership

### Layer C — Controlled policy artifacts
Used for semantic, QA, or governance decisions.

**Channel examples:**
- precedent log
- taxonomy change proposal
- weekly QA report
- leadership decision memo

**Rule:** authoritative for policy and precedent

---

## 6.2 Standard exchange packet for any escalation

Every escalated case should contain these fields.

```text
case_id:
paper_id:
title:
current_status:
current_owner:
requested_recipient:
issue_type:
priority:
due_by:
proposed_main_collection:
proposed_subcollection:
closest_competing_option:
confidence_score:
evidence_summary:
specific_question_to_resolve:
attachments_or_links:
impact_if_delayed:
requester_name:
request_time:
```

### Allowed `issue_type` values

Use one of the following controlled values:

- `LOW_CONFIDENCE_CLASSIFICATION`
- `BORDERLINE_BETWEEN_SUBCOLLECTIONS`
- `BORDERLINE_BETWEEN_MAIN_COLLECTIONS`
- `TAXONOMY_GAP_SUSPECTED`
- `PRECEDENT_CONFLICT`
- `MISSING_OR_CORRUPT_METADATA`
- `DUPLICATE_SUSPECTED`
- `ASSIGNMENT_OR_PRIORITY_QUESTION`
- `RETURNED_FOR_REWORK`
- `QUALITY_PATTERN_ALERT`
- `TOOLING_INCIDENT`
- `REPORTING_DISCREPANCY`
- `MAJOR_POLICY_EXCEPTION`

---

## 6.3 Response-time standards

Use these default service levels.

| Exchange type | First response SLA | Resolution target | Owner |
|---|---:|---:|---|
| Analyst procedural question to Team Lead | 30 minutes | same working day | Team Lead |
| Analyst assignment issue to Operations | 1 hour | same working day | Operations Manager |
| Analyst data-fix ticket to Data / Tooling | 2 hours | 1 working day | Data / Tooling Analyst |
| Analyst low-confidence escalation to QA | 2 hours | 1 working day | QA Lead |
| QA semantic escalation to Taxonomy | same day | 1–2 working days | Taxonomy Lead |
| Lead-level cross-functional blocker to Program Director | 2 hours | 1 working day | Program Director |
| Tooling incident affecting multiple users | 30 minutes | severity-based | Data / Tooling + Program Director if severe |
| Major taxonomy change proposal | acknowledgment in 1 day | decision in scheduled governance cycle unless urgent | Program Director |

These are planning standards. If you need stricter SLAs, define them explicitly by queue or stakeholder class.

---

## 7. Pairwise communication matrix

This matrix answers: **Who communicates with whom, about what, by which channel, how often, and with what authority?**

| Role pair | Primary purpose | Usual direction | Primary channel | Authoritative artifact | Frequency |
|---|---|---|---|---|---|
| Program Director ↔ Taxonomy Lead | approve semantic policy, review change impact | bidirectional | weekly leadership review + ad hoc | taxonomy proposal / decision memo | weekly + triggered |
| Program Director ↔ Operations Manager | priorities, backlog, SLA, staffing | bidirectional | daily dashboard + weekly review | operations report / decision memo | daily light + weekly formal |
| Program Director ↔ QA Lead | quality threshold, risk, audit findings | bidirectional | weekly review + urgent escalation | QA report / risk log | weekly + triggered |
| Program Director ↔ Data / Tooling Analyst | tooling priorities, metric definitions, incidents | bidirectional | weekly review + incident channel | tooling summary / incident log | weekly + triggered |
| Program Director ↔ Team Lead | floor conditions, analyst readiness, severe people issues | mostly Team Lead upward | ops sync | shift summary / decision note if needed | weekly + triggered |
| Program Director ↔ Analysts | culture, calibration visibility, major announcements | mostly Program downward | all-hands / calibration | memo or release note | monthly + triggered |
| Taxonomy Lead ↔ Operations Manager | rollout of taxonomy clarifications, impact on workflow | bidirectional | working session | change note / runbook update | weekly + triggered |
| Taxonomy Lead ↔ QA Lead | semantic ambiguity, precedent, border cases | bidirectional | taxonomy-qa working session | precedent log / taxonomy ruling | frequent |
| Taxonomy Lead ↔ Team Lead | repeated analyst confusion themes | mostly Team Lead upward | routed through QA or working session | clarification note | weekly + triggered |
| Taxonomy Lead ↔ Analysts | training on meanings, examples, office hours | mostly Taxonomy downward | calibration / office hours | precedent note | occasional |
| Taxonomy Lead ↔ Data / Tooling Analyst | implement taxonomy structures in systems, metrics, forms | bidirectional | change ticket | implementation note | triggered |
| Operations Manager ↔ QA Lead | rework trends, queue risk, audit coverage | bidirectional | daily or weekly ops-quality sync | ops report / QA report | frequent |
| Operations Manager ↔ Team Lead | assignments, capacity, blockers, productivity | bidirectional | daily standup + chat | queue board / shift summary | multiple times daily |
| Operations Manager ↔ Analysts | assignment clarity, deadlines, queue changes | mostly Ops downward | queue board / chat | assignment record | daily |
| Operations Manager ↔ Data / Tooling Analyst | dashboard needs, data issues, queue automation | bidirectional | ticket + sync | dashboard request / incident ticket | frequent |
| QA Lead ↔ Team Lead | coaching needs, returned cases, analyst quality | bidirectional | QA coaching sync | rework log / coaching note | frequent |
| QA Lead ↔ Analysts | clarifications on returned work, calibration | bidirectional | returned-case comments / calibration | QA disposition | frequent |
| QA Lead ↔ Data / Tooling Analyst | data patterns causing errors, audit extracts | bidirectional | ticket + sync | quality-data issue log | weekly + triggered |
| Team Lead ↔ Analysts | task allocation, blockers, coaching | bidirectional | standup + chat + tracker | assignment record / coaching note | continuous |
| Team Lead ↔ Data / Tooling Analyst | broken records affecting assigned analysts | mostly Team Lead upward | ticket | data-fix ticket | daily as needed |
| Analysts ↔ Data / Tooling Analyst | direct data issues on specific papers | mostly Analysts upward | ticket | data-fix ticket | as needed |

### Important control rule

Where both a fast channel and a tracked artifact are used, the tracked artifact always wins.  
For example, if chat says one thing but the ticket says another, the ticket is authoritative until explicitly corrected.

---

## 8. Detailed handoff map by sender and receiver

This section makes the exchanges operationally precise.

## 8.1 Data / Tooling Analyst → Operations Manager

### Trigger
New records have passed intake validation.

### Required payload
- batch ID
- record count
- source
- known limitations
- duplicate exclusions
- unresolved data defects

### Expected receiver action
- place the batch in routing queue
- assign priority
- schedule distribution

### Response standard
Same working day

---

## 8.2 Operations Manager → Team Lead

### Trigger
Daily queue plan is finalized.

### Required payload
- batch IDs
- target counts
- priority order
- due dates
- analyst constraints
- special instructions

### Expected receiver action
- distribute work across analysts
- surface expected blockers
- monitor progress

### Response standard
Before shift start or within the first work hour

---

## 8.3 Operations Manager → Analyst *(when no Team Lead exists, or for direct assignment)*

### Trigger
Direct assignment or reprioritization is needed.

### Required payload
- paper or batch IDs
- due date
- queue priority
- any known handling notes

### Expected receiver action
- acknowledge assignment
- start work
- escalate blockers promptly

---

## 8.4 Analyst → Team Lead

### Trigger
Procedural blocker, workload issue, or preliminary uncertainty requiring routing help.

### Required payload
- case ID
- issue type
- brief blocker description
- time already spent
- current best guess
- urgency

### Expected receiver action
One of:
- answer directly,
- reroute to QA,
- reroute to Data / Tooling,
- escalate to Ops,
- hold for calibration if non-blocking.

### Response standard
30 minutes for active shift work

---

## 8.5 Analyst → QA Lead

### Trigger
Low confidence or ambiguity that cannot be responsibly finalized.

### Required payload
- case ID
- proposed main and subcollection
- closest competing tag
- confidence score
- evidence summary
- exact question

### Expected receiver action
- approve,
- correct and finalize,
- return for rework,
- or escalate to Taxonomy

### Response standard
Same working day if this blocks completion target

---

## 8.6 Analyst → Data / Tooling Analyst

### Trigger
Record quality prevents review.

### Required payload
- case ID
- defect type
- screenshots or source note if needed
- whether a substitute record is available

### Expected receiver action
- repair record,
- mark duplicate,
- replace source,
- or exclude record

### Response standard
Within 1 working day unless critical queue impact

---

## 8.7 Team Lead → QA Lead

### Trigger
Pattern of low-confidence work or repeated analyst confusion.

### Required payload
- affected analysts or queue
- representative cases
- pattern summary
- suspected cause
- urgency

### Expected receiver action
- review representative cases
- confirm whether issue is training, execution, or taxonomy
- return guidance

---

## 8.8 QA Lead → Analyst

### Trigger
Case has been reviewed.

### Required payload
- disposition
- correction if any
- rationale for correction
- precedent reference if applicable
- whether resubmission is required

### Expected receiver action
- apply correction,
- internalize lesson,
- or resubmit reworked case

---

## 8.9 QA Lead → Taxonomy Lead

### Trigger
A case cannot be settled under current policy.

### Required payload
- full case record
- analyst proposal
- QA assessment
- competing tags
- precedent conflict, if any
- scope of likely repeatability

### Expected receiver action
- issue semantic ruling,
- create precedent,
- or draft taxonomy change recommendation

### Response standard
1–2 working days

---

## 8.10 Taxonomy Lead → QA Lead and Operations Manager

### Trigger
A semantic clarification or change has been decided.

### Required payload
- decision summary
- effective date
- exact affected tags
- precedent entry
- whether existing papers need review
- training note

### Expected receiver action
- QA updates review logic
- Ops updates instructions and queue handling
- Team Lead / analysts are briefed

---

## 8.11 Taxonomy Lead → Program Director

### Trigger
A change has material operational or reporting impact.

### Required payload
- problem summary
- recommended action
- impact assessment
- reclassification volume estimate
- training and tooling impact
- alternatives considered

### Expected receiver action
- approve,
- request revision,
- defer,
- or reject

---

## 8.12 QA Lead → Program Director

### Trigger
Material quality risk or policy conflict exists.

### Required payload
- quality issue summary
- trend data
- affected volume
- root-cause hypothesis
- proposed mitigation
- urgency

### Expected receiver action
- prioritize corrective action
- authorize temporary controls
- resolve cross-functional conflict if present

---

## 8.13 Data / Tooling Analyst → Program Director and Operations Manager

### Trigger
A tooling defect or reporting discrepancy affects delivery or measurement.

### Required payload
- issue description
- affected systems or queues
- estimated impact
- workaround
- estimated fix path
- decision needed, if any

### Expected receiver action
- approve workaround,
- reset expectations,
- or prioritize fix investment

---

## 9. Meeting and cadence architecture

Use a fixed operating rhythm. Do not rely solely on ad hoc messages.

## 9.1 Daily cadence

### Daily analyst standup
**Owner:** Team Lead  
**Participants:** Analysts, optional Ops

Purpose:
- confirm priorities
- surface blockers
- restate recent clarifications

Length:
- 10–15 minutes

### Daily operations check
**Owner:** Operations Manager  
**Participants:** Team Lead, QA Lead, Data / Tooling as needed

Purpose:
- queue health
- aging risk
- blocked cases
- staffing changes

Length:
- 15 minutes

### Daily lead exception touchpoint
**Owner:** Program Director when needed  
**Participants:** only affected leads

Purpose:
- resolve urgent cross-functional blockers

Length:
- 10–20 minutes

---

## 9.2 Weekly cadence

### Weekly calibration session
**Owner:** QA Lead  
**Participants:** Analysts, Team Lead, Taxonomy Lead optional or mandatory when semantic issues exist

Purpose:
- review disagreements
- explain corrections
- align interpretation
- update examples

Length:
- 45–60 minutes

### Weekly taxonomy-ops-quality working session
**Owner:** Taxonomy Lead  
**Participants:** Taxonomy, QA, Ops, Team Lead, Data / Tooling optional

Purpose:
- review semantic hotspots
- determine whether issue is taxonomy, training, or workflow
- plan controlled updates

Length:
- 45 minutes

### Weekly cross-functional operating review
**Owner:** Program Director  
**Participants:** Taxonomy, Ops, QA, Data / Tooling, Team Lead if present

Purpose:
- review KPIs
- decide actions
- resolve lead-level conflicts
- approve short-term priorities

Length:
- 60 minutes

---

## 9.3 Monthly cadence

### Monthly taxonomy governance board
**Owner:** Program Director + Taxonomy Lead

Purpose:
- approve or defer major taxonomy changes
- assess reclassification impact
- confirm release timing

### Monthly performance and staffing review
**Owner:** Program Director + Operations Manager

Purpose:
- review volume, productivity, and headcount assumptions
- adjust capacity plan

### Monthly quality deep dive
**Owner:** QA Lead

Purpose:
- review audit accuracy
- identify drift
- set corrective-action plan

---

## 10. RACI by major process step

**R = Responsible**  
**A = Accountable**  
**C = Consulted**  
**I = Informed**

| Process step | Program Director | Taxonomy Lead | Operations Manager | QA Lead | Team Lead | Analysts | Data / Tooling |
|---|---|---|---|---|---|---|---|
| Define classification policy | A | R | C | C | I | I | I |
| Maintain taxonomy definitions | C | A/R | I | C | I | I | C |
| Ingest and validate records | I | I | C | I | I | I | A/R |
| Build and prioritize queues | I | I | A/R | C | C | I | C |
| Distribute work to analysts | I | I | A | I | R | I | I |
| Perform primary classification | I | I | I | I | C | A/R | I |
| First-line procedural support | I | I | C | I | A/R | C | C |
| Review low-confidence cases | I | C | I | A/R | C | C | I |
| Adjudicate within existing policy | I | C | I | A/R | I | C | I |
| Resolve semantic border cases | C | A/R | I | C | I | I | I |
| Approve major taxonomy changes | A/R | R | C | C | I | I | C |
| Finalize approved case | I | I | I | A/R | I | C | I |
| Publish quality report | I | C | C | A/R | C | I | C |
| Publish operations report | C | I | A/R | C | C | I | C |
| Publish dashboard metrics | I | I | C | C | I | I | A/R |
| Approve reclassification campaign | A/R | R | C | C | I | I | C |

### Note on the Team Lead column

If no Team Lead exists, shift **Team Lead R/C responsibilities to Operations Manager**.

---

## 11. Decision and escalation ladder

Use this ladder to prevent confusion about who owns which decision.

### Level 1 — Analyst
Use for:
- standard paper classification within current rules

### Level 2 — Team Lead / Operations
Use for:
- task routing
- workload balancing
- procedural clarification
- non-semantic blockers

### Level 3 — QA Lead
Use for:
- low-confidence review
- ambiguous paper-level adjudication
- correction vs rework decisions
- quality-pattern identification

### Level 4 — Taxonomy Lead
Use for:
- semantic boundary decisions
- precedent conflicts
- taxonomy gaps
- structural taxonomy change proposals

### Level 5 — Program Director
Use for:
- cross-functional conflict
- major policy exceptions
- major taxonomy approval
- budget or staffing implications
- high-impact reclassification decisions

---

## 12. Workflow for common scenarios

These scenarios make the roles concrete.

## 12.1 Scenario A — straightforward paper

1. Data validates record.
2. Ops assigns batch.
3. Analyst classifies with high confidence.
4. Case is finalized directly or sampled later by QA.
5. Dashboard updates nightly.

### Communication load
Minimal:
- assignment notice
- final record saved

---

## 12.2 Scenario B — analyst unsure between two subcollections

1. Analyst records best current guess, competing option, and confidence.
2. Analyst escalates to Team Lead or directly to QA depending on workflow.
3. QA reviews and chooses:
   - approve analyst choice,
   - correct choice,
   - escalate to Taxonomy if the boundary is semantically unclear.
4. If Taxonomy rules, precedent is written.
5. Team Lead shares the precedent with analysts.

### Communication load
Moderate:
- one escalation packet
- one QA disposition
- possible taxonomy note

---

## 12.3 Scenario C — suspected taxonomy gap

1. Analyst cannot find a credible existing subcollection.
2. Analyst escalates to QA with evidence.
3. QA confirms that the issue is not simple analyst error.
4. QA escalates to Taxonomy with representative cases.
5. Taxonomy reviews affected tags and historical examples.
6. If a new subcollection is justified, Taxonomy drafts proposal.
7. Program Director approves or defers based on impact.
8. Data / Tooling implements updated taxonomy fields.
9. Ops plans any reclassification campaign.
10. QA and Team Lead retrain analysts.

### Communication load
High:
- QA escalation bundle
- taxonomy proposal
- program decision memo
- implementation notice
- training note

---

## 12.4 Scenario D — corrupted source data blocks multiple analysts

1. Analysts submit data-fix tickets.
2. Team Lead or Ops notices pattern.
3. Data / Tooling confirms source defect.
4. Ops quarantines affected queue.
5. Program Director is informed if SLA impact exists.
6. Data / Tooling issues workaround or fix.
7. Ops reactivates queue and reassigns work.

### Communication load
High and time-sensitive:
- incident notice
- workaround note
- queue status change
- restart notice

---

## 13. Minimum required documents and their owners

| Document / artifact | Primary owner | Backup owner | Update trigger |
|---|---|---|---|
| Taxonomy reference document | Taxonomy Lead | Program Director | any approved semantic change |
| Precedent log | Taxonomy Lead | QA Lead | every reusable ruling |
| Operations runbook | Operations Manager | Team Lead | workflow change |
| QA review guide | QA Lead | Program Director | review-policy change |
| Queue board / assignment log | Operations Manager | Team Lead | daily |
| Data validation rules | Data / Tooling Analyst | Operations Manager | source-change or defect pattern |
| Dashboard metric definitions | Data / Tooling Analyst | Program Director | reporting change |
| Weekly decision memo | Program Director | none | weekly |
| Risk log | Program Director | Operations Manager | new program-level risk |

---

## 14. Minimum communication rules that should be enforced

1. **Every case has one owner.**
2. **Every escalation has one recipient and one due-by time.**
3. **Every nontrivial decision leaves a durable written trace.**
4. **Analysts do not invent taxonomy.**
5. **QA does not silently rewrite taxonomy definitions.**
6. **Operations does not suppress quality findings for throughput reasons.**
7. **Taxonomy does not release structural changes without impact analysis.**
8. **Program Director resolves cross-functional deadlock within one working day unless a longer governance process is explicitly declared.**
9. **No role may keep a blocker unreported past end of day.**
10. **Recurring confusion must be converted into training, precedent, or taxonomy change.**

---

## 15. Practical implementation recommendation

If you are setting this up from scratch, implement the workflow in this order:

1. Create the status model.
2. Create the escalation template.
3. Create the queue board and assignment log.
4. Create the QA disposition form.
5. Create the taxonomy precedent log.
6. Define response-time SLAs.
7. Launch the meeting cadence.
8. Measure handoff lag between roles.
9. Only then add automation.

This order matters because weak handoffs create more failure than weak tooling.

---

## 16. Final recommendation

For the strongest governance model, use this chain:

```text
Program Director
├── Taxonomy Lead
├── Operations Manager
│   └── Team Lead
│       └── Analysts
├── QA & Adjudication Lead
└── Data / Tooling Analyst
```

Then enforce this operating rule:

> **Operations owns flow, QA owns correctness, Taxonomy owns meaning, Data/Tooling owns infrastructure, and the Program Director owns alignment.**

That division prevents the most common failure mode in classification programs: one function informally taking over responsibilities that belong to another.

---
