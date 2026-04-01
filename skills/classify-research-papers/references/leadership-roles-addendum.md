# Leadership Roles Addendum: Main Lead and Team Lead for the Research Paper Classification Program

## Direct answer

Yes. The role that should **supervise and centralize the complete task** is:

# **Classification Program Director / Program Lead**

This is the **single accountable owner** of the entire classification program.

This person sits **above**:

- Taxonomy Lead / Knowledge Architect
- Classification Operations Manager
- QA & Adjudication Lead
- Data / Tooling Analyst
- Classification Team Lead / Senior Lead *(if used)*
- Classification Analysts *(indirectly through the Team Lead or Operations Manager)*

If you want one person who can say, "I own the whole thing end to end," this is the role.

---

## Important distinction: there are actually two different "lead" roles

Many teams confuse these two roles.

## 1. Classification Program Director / Program Lead

This is the **overall head of the program**.

They own:

- scope
- governance
- staffing model
- delivery commitments
- quality thresholds
- taxonomy change approval
- escalation routing
- stakeholder communication
- budget and prioritization
- final conflict resolution across taxonomy, operations, QA, and tooling

They are the **main lead of the complete task**.

## 2. Classification Team Lead / Senior Lead

This is the **day-to-day leader of the analysts**.

They own:

- daily analyst supervision
- queue balancing
- analyst coaching
- first-line review of low-confidence work
- attendance / coverage checks
- new-hire support
- execution discipline on the floor

They are **not** the overall program owner.

They are the **people-and-production lead closest to the analysts**.

---

## Recommended reporting structure

Use this structure if you want clear accountability.

```text
Classification Program Director / Program Lead
├── Taxonomy Lead / Knowledge Architect
├── Classification Operations Manager
│   └── Classification Team Lead / Senior Lead (optional but recommended at 6+ analysts)
│       └── Classification Analysts
├── QA & Adjudication Lead
└── Data / Tooling Analyst
```

### Dotted-line governance relationships

- The **QA & Adjudication Lead** should have direct access to the Program Director so quality issues cannot be suppressed by throughput pressure.
- The **Taxonomy Lead** should also report directly to the Program Director so taxonomy policy is not distorted by production convenience.
- The **Team Lead** should work daily with the Operations Manager and maintain a dotted-line relationship with QA for coaching and calibration.

---

## Which role is the real main lead?

The answer is:

# **Classification Program Director / Program Lead**

This role is the final owner of the entire classification mission.

If a conflict appears between:

- speed and quality,
- taxonomy purity and operational practicality,
- QA findings and analyst productivity,
- manual review and automation,
- budget and staffing,
- stakeholder requests and taxonomy rules,

this is the role that makes the final operating decision.

---

## When this role should be a separate person

Make the Program Lead a **separate dedicated role** when one or more of these are true:

1. The program is ongoing, not just a short pilot.
2. More than 5 people are involved.
3. More than one manager or specialist lead exists.
4. External stakeholders need reporting and governance.
5. Auditability or compliance matters.
6. Taxonomy changes have business consequences.
7. Backlog, inflow, and SLA must all be balanced at the same time.
8. Tooling, QA, and taxonomy decisions need coordination.

If all of these are small or temporary, the role can be combined with either:

- the Taxonomy Lead, or
- the Operations Manager.

But that is a **lean compromise**, not the strongest governance model.

---

## Headcount impact

## Previous recommended model

- 1 Taxonomy Lead / Knowledge Architect
- 1 Classification Operations Manager
- 1 QA & Adjudication Lead
- 6 Classification Analysts
- 1 Data / Tooling Analyst

**Total = 10 FTE**

## Revised model with an explicit overall owner

- 1 **Classification Program Director / Program Lead**
- 1 Taxonomy Lead / Knowledge Architect
- 1 Classification Operations Manager
- 1 QA & Adjudication Lead
- 6 Classification Analysts
- 1 Data / Tooling Analyst

**Total = 11 FTE**

## Revised model with both overall owner and analyst people lead

- 1 **Classification Program Director / Program Lead**
- 1 Taxonomy Lead / Knowledge Architect
- 1 Classification Operations Manager
- 1 QA & Adjudication Lead
- 1 **Classification Team Lead / Senior Lead**
- 6 Classification Analysts
- 1 Data / Tooling Analyst

**Total = 12 FTE**

### My precise recommendation

For your setup, I would recommend:

- **11 FTE** if the 6 analysts are experienced and the operation is single-shift and stable.
- **12 FTE** if the analysts are junior, the taxonomy is evolving, there is rework pressure, or you want close daily supervision.

---

## Decision-rights split: who decides what?

## Classification Program Director / Program Lead decides

- final program priorities
- staffing plan
- production targets
- quality thresholds at program level
- escalation policy
- approval or rejection of major taxonomy changes
- reclassification campaigns
- tool investment priority
- stakeholder commitments
- final arbitration across functions

## Taxonomy Lead decides

- tag meanings
- tag boundaries
- precedent for semantic border cases
- merge / split / rename recommendations
- taxonomy release notes

## Operations Manager decides

- daily workflow design
- batch routing
- staffing schedules
- throughput management
- SLA management
- operational exception handling

## QA & Adjudication Lead decides

- review criteria
- adjudication of ambiguous cases within current policy
- calibration outcomes
- acceptance / return-for-rework on reviewed items
- audit sampling plan

## Classification Team Lead decides

- day-to-day analyst supervision
- work allocation within the shift or queue
- first-line coaching
- when a case needs fast escalation to QA or taxonomy
- analyst readiness for independent work

## Data / Tooling Analyst decides

- instrumentation design
- dashboard logic
- data quality checks
- automation suggestions
- workflow analytics methods

---

## Program Director / Program Lead role charter

## Mission

Be the **single accountable owner** of the classification program so that taxonomy, operations, quality, and tooling remain aligned.

## Primary objective

Deliver a classification program that is:

- accurate
- stable
- scalable
- auditable
- on schedule
- governable over time

## Core responsibilities

1. Define the program charter and operating model.
2. Set throughput, quality, backlog, and turnaround targets.
3. Approve governance rules, escalation paths, and change-control rules.
4. Chair weekly cross-functional review with taxonomy, ops, QA, and tooling.
5. Resolve conflicts that cross functional boundaries.
6. Approve major taxonomy releases after Taxonomy Lead recommendation.
7. Approve large-scale reclassification campaigns.
8. Own stakeholder communication, status reporting, and risk communication.
9. Review weekly dashboard and intervene when KPIs drift.
10. Decide when to hire, retrain, split queues, or pause production for recalibration.
11. Ensure audit readiness and decision traceability.
12. Protect quality from being sacrificed for speed and protect delivery from unnecessary academic perfectionism.

## Specific deliverables

- program charter
- governance model
- target operating metrics
- decision-rights matrix
- risk register
- escalation register
- weekly executive summary
- monthly performance review
- major change approvals
- reclassification approval memo when needed

## KPIs this role owns

- finalized papers per month
- backlog age
- SLA attainment
- first-pass acceptance rate
- QA disagreement rate
- rework rate
- taxonomy change volume
- share of low-confidence cases
- audit pass rate
- tooling adoption rate
- cost per finalized paper

## What this role must not do

- manually classify large volumes of papers as routine work
- bypass taxonomy governance because of deadline pressure
- rewrite QA findings to make dashboards look better
- allow informal undocumented exceptions
- let operations redefine taxonomy on the fly
- let taxonomy expand without impact analysis

## Weekly operating cadence

### Daily

- review dashboard exceptions
- resolve urgent cross-functional blockers
- approve priority changes if needed

### Weekly

- run governance review with Taxonomy, Ops, QA, and Tooling
- review KPI trends
- approve corrective actions
- review escalations older than target SLA

### Monthly

- review staffing and capacity model
- review taxonomy drift indicators
- review audit findings
- issue stakeholder report

---

## Classification Team Lead / Senior Lead role charter

## Mission

Provide **first-line operational leadership** for analysts so daily production stays controlled, coached, and consistent.

## Primary objective

Convert the program design into disciplined day-to-day execution.

## Core responsibilities

1. Run analyst standups or shift starts.
2. Assign queues and rebalance workload during the day.
3. Monitor low-confidence rate, rework rate, and queue aging.
4. Coach analysts on evidence-based classification.
5. Spot training gaps and report them.
6. Escalate semantic issues to Taxonomy or QA issues to the QA Lead.
7. Check that analysts follow templates and evidence rules.
8. Support onboarding and shadowing for new analysts.
9. Flag outlier analysts early.
10. Maintain execution discipline without rewriting taxonomy policy.

## Specific deliverables

- daily queue allocation
- shift coverage plan
- analyst coaching log
- readiness sign-off for new analysts
- daily issue log
- analyst error pattern summary
- queue aging report

## KPIs this role owns

- analyst productivity consistency
- queue aging
- low-confidence submission rate
- analyst rework rate
- adherence to workflow steps
- time-to-escalation for blocked cases

## What this role must not do

- create or change taxonomy definitions
- suppress escalations to make throughput look better
- overrule QA on adjudication
- invent shortcuts that break auditability
- become a second unofficial operations manager without clarity

## When this role becomes strongly recommended

Add this role when one or more of these conditions are true:

1. There are **6 or more analysts**.
2. Analysts are junior or newly hired.
3. The queue is split by subject, language, or client.
4. The operation runs in more than one shift or timezone.
5. Rework exceeds **5%** for more than two consecutive weeks.
6. Low-confidence submissions exceed **15%** in sustained volume.
7. The Operations Manager is spending too much time on first-line supervision.

---

## Agent persona prompt: Classification Program Director / Program Lead

Use the following as a system prompt.

```text
You are the Classification Program Director / Program Lead for a controlled research paper classification program.

You are the single accountable owner of the full program across taxonomy governance, operational delivery, quality control, staffing logic, tooling priorities, escalation policy, and stakeholder reporting.

Your primary responsibility is to keep the entire classification system aligned, governable, auditable, and effective over time.

You sit above the Taxonomy Lead, Classification Operations Manager, QA & Adjudication Lead, Data / Tooling Analyst, and Classification Team Lead if one exists.

Your governing principles are:
1. Protect end-to-end program integrity, not just one function.
2. Prefer documented policy over informal exceptions.
3. Never trade away quality silently in order to improve throughput.
4. Never freeze operations unnecessarily in pursuit of perfect taxonomy purity.
5. Require traceability for all major decisions.
6. Resolve cross-functional conflicts explicitly and document the rationale.
7. Distinguish between temporary operational exceptions and permanent policy changes.
8. Require impact analysis before approving taxonomy changes or mass reclassification.
9. Use metrics, audit evidence, and escalation patterns to guide interventions.
10. Maintain a clear owner and next action for every unresolved issue.

You do not perform routine bulk classification work.
You do not redefine taxonomy personally without the Taxonomy Lead's analysis.
You do not suppress QA findings.
You do not allow operations to drift into undocumented policy.

When responding:
- state the decision or recommendation clearly,
- name the owner of each next step,
- state risks,
- state what must be approved,
- distinguish immediate action from structural change,
- and always preserve governance clarity.
```

### Task prompt template

```text
Task type: [program decision / escalation / staffing / risk review / taxonomy-change approval / reclassification approval / KPI review / cross-functional arbitration]

Context:
[insert relevant metrics, backlog data, SLA status, stakeholder requirement, taxonomy issue, QA findings, tooling constraints, and current risks]

Inputs:
- backlog:
- monthly inflow:
- throughput:
- QA disagreement rate:
- rework rate:
- low-confidence rate:
- proposed taxonomy or process change:
- impacted teams:
- stakeholder deadline:
- known risks:

Required output:
1. Decision summary
2. Why this decision is correct
3. Immediate actions
4. Structural follow-up actions
5. Owners
6. Risks and mitigations
7. Approval status
```

### Output template

```yaml
task_type:
decision_summary:
program_goal_affected:
recommended_action:
decision_rationale:
alternatives_considered:
metrics_considered:
risks:
mitigations:
approvals_required:
owners:
next_steps:
review_date:
status: approved | approved_with_conditions | deferred | rejected | escalated
```

---

## Agent persona prompt: Classification Team Lead / Senior Lead

Use the following as a system prompt.

```text
You are the Classification Team Lead / Senior Lead in a controlled research paper classification program.

You are the first-line leader of the analysts. Your responsibility is daily execution discipline, coaching, queue balance, workflow adherence, and early detection of analyst or process issues.

You do not own taxonomy policy. You do not change tag definitions. You do not overrule formal adjudication. You do not hide uncertainty or suppress escalation.

Your governing principles are:
1. Keep analysts working on the right items at the right time.
2. Coach analysts toward evidence-based classification, not guesswork.
3. Escalate ambiguity early instead of allowing hidden rework to accumulate.
4. Keep queue aging visible.
5. Maintain consistency across analysts.
6. Detect analyst confusion patterns and convert them into training or QA review.
7. Protect auditability by enforcing structured outputs and evidence citation.
8. Distinguish a people problem, process problem, taxonomy problem, and tooling problem.
9. Be precise, calm, and operationally disciplined.
10. Make the next action obvious.

When responding:
- identify the operational issue,
- state what the analyst team should do next,
- specify any needed escalation,
- note coaching points,
- and quantify impact where possible.
```

### Task prompt template

```text
Task type: [daily queue allocation / analyst coaching / exception handling / workflow blockage / quality drift / onboarding support / shift summary]

Context:
[insert analyst roster, queue size, aging, low-confidence volume, rework data, blocked items, absent staff, and priority batches]

Inputs:
- analysts available:
- queue by priority:
- items aging over SLA:
- low-confidence count:
- rework count:
- blocked cases:
- new analysts in training:
- urgent stakeholder commitments:

Required output:
1. Daily operational decision
2. Analyst assignments or coaching actions
3. Escalations required
4. Risks to SLA or quality
5. End-of-day checkpoints
```

### Output template

```yaml
task_type:
operational_issue:
queue_state:
recommended_action:
analyst_assignments:
coaching_actions:
escalations_required:
risks:
mitigations:
end_of_day_checks:
owner:
status: open | in_progress | blocked | escalated | resolved
```

---

## Precise recommendation for your package

If your question is: **"Who is the main lead of the whole classification task?"**

The answer is:

# **Classification Program Director / Program Lead**

If your question is: **"Who directly supervises analysts every day?"**

The answer is:

# **Classification Team Lead / Senior Lead** *(optional but recommended once you have 6+ analysts or meaningful daily complexity)*

---

## Minimal recommendation you can adopt immediately

If you want the cleanest structure, use this:

- 1 Classification Program Director / Program Lead
- 1 Taxonomy Lead / Knowledge Architect
- 1 Classification Operations Manager
- 1 QA & Adjudication Lead
- 1 Classification Team Lead / Senior Lead
- 6 Classification Analysts
- 1 Data / Tooling Analyst

**Total = 12 FTE**

If you need to stay lean, remove the Team Lead first, not the Program Director.

That leaves:

- 1 Classification Program Director / Program Lead
- 1 Taxonomy Lead / Knowledge Architect
- 1 Classification Operations Manager
- 1 QA & Adjudication Lead
- 6 Classification Analysts
- 1 Data / Tooling Analyst

**Total = 11 FTE**

That is the strongest lean model with one explicit overall owner.
