# Team Blueprint for Research Paper Classification

## Purpose

This document defines the **recommended staffing model, roles, missions, capacity assumptions, and governance** for a team that classifies research papers into a **2-layer taxonomy**:

- Level 1 = main collection
- Level 2 = subcollection

It is written to support both:

1. the **initial taxonomy build and pilot**, and
2. the **steady-state production operation**.

---

## 1. The most useful answer first

If I had to staff this work without additional volume data, I would use the following model:

### Recommended default team for a serious medium-scale operation: **10 FTE**

This is the right size for a program that must be **accurate, auditable, and maintainable**, not just fast.

### Team composition

1. **1 Taxonomy Lead / Knowledge Architect**
2. **1 Classification Operations Manager**
3. **1 QA & Adjudication Lead**
4. **6 Classification Analysts**
5. **1 Data / Tooling Analyst**

### Expected capacity of this 10-person team

With a mature workflow and a mixed-complexity corpus, this team can usually finalize about:

- **3,000 to 4,000 papers per month**
- while maintaining formal QA,
- taxonomy maintenance,
- and escalation handling.

For planning, use **3,600 finalized papers/month** as the standard target.

That planning number comes from:

- `6 production analysts × ~600 finalized papers/month each = ~3,600/month`

---

## 2. Capacity assumptions used in this staffing model

These assumptions make the headcount math explicit.

### Per-paper handling time assumptions

- Simple paper: **5–8 minutes**
- Standard paper: **8–12 minutes**
- Ambiguous paper: **12–20 minutes**
- Adjudication case: **15–30 minutes**

### Effective productive time per classifier

Use this planning assumption:

- **6 focused classification hours/day**
- **20 workdays/month**

That gives about **120 productive hours/month**.

### Standard analyst production capacity

If average handling time is about **10–12 minutes per paper**, a trained analyst can reliably deliver about:

- **500–700 finalized papers/month**

For staffing calculations, use this conservative standard:

- **1 classifier = 600 finalized papers/month**

### Senior reviewer capacity

A QA/adjudication lead is not a pure production role. They spend time on:

- reviewing low-confidence cases,
- resolving disagreements,
- calibration,
- audit reporting,
- precedent writing.

So do **not** count them as a full production classifier.

---

## 3. Precise headcount formula

If you know your backlog and inflow, use this formula.

### Variables

- `B` = initial backlog of papers
- `T` = target number of months to clear the backlog
- `I` = expected monthly inflow of new papers
- `C` = classifier capacity per month = **600**

### Required monthly throughput

```text
M = (B / T) + I
```

### Required number of production classifiers

```text
A = ceiling(M / 600)
```

### Required number of QA / adjudication reviewers

Use this rule:

```text
R = max(1, ceiling(A / 5))
```

That means:

- 1 senior reviewer for up to 5 analysts
- 2 senior reviewers for 6–10 analysts
- 3 senior reviewers for 11–15 analysts

### Full team formula

For a stable operation, start with:

```text
Total FTE = A + R + 1 Taxonomy Lead + 1 Operations Manager + 1 Data/Tooling Analyst
```

### Add this adjustment for broad multi-disciplinary corpora

If your corpus spans **multiple unrelated disciplines**, add:

```text
+ 0.5 to 1.0 FTE domain SME coverage per 3 major discipline clusters
```

These can be internal part-time subject advisors rather than full-time hires.

---

## 4. Example staffing calculations

### Scenario A — Medium operation

- Backlog: `24,000` papers
- Target clearance: `12 months`
- Monthly inflow: `1,500`

#### Required monthly throughput

```text
M = (24,000 / 12) + 1,500 = 3,500 papers/month
```

#### Classifiers needed

```text
A = ceiling(3,500 / 600) = 6 analysts
```

#### Senior reviewers needed

```text
R = max(1, ceiling(6 / 5)) = 2 reviewers
```

#### Total recommended team

- 6 Classification Analysts
- 2 Senior Reviewers / Adjudicators
- 1 Taxonomy Lead
- 1 Operations Manager
- 1 Data/Tooling Analyst

**Total = 11 FTE**

If budget is tight, one of the reviewers can be combined with the Taxonomy Lead temporarily, which brings this down to **10 FTE**.

---

### Scenario B — Lean controlled operation

- Backlog: `12,000`
- Target clearance: `12 months`
- Monthly inflow: `1,000`

#### Throughput

```text
M = (12,000 / 12) + 1,000 = 2,000/month
```

#### Classifiers

```text
A = ceiling(2,000 / 600) = 4 analysts
```

#### Reviewers

```text
R = 1
```

#### Total team

- 4 Classification Analysts
- 1 QA / Adjudication Lead
- 1 Taxonomy Lead
- 1 Operations Manager
- 1 Data/Tooling Analyst

**Total = 8 FTE**

This is the smallest team I would recommend for a professional setup with governance and audit.

---

### Scenario C — High-throughput operation

- Backlog: `60,000`
- Target clearance: `12 months`
- Monthly inflow: `3,000`

#### Throughput

```text
M = (60,000 / 12) + 3,000 = 8,000/month
```

#### Classifiers

```text
A = ceiling(8,000 / 600) = 14 analysts
```

#### Reviewers

```text
R = ceiling(14 / 5) = 3 reviewers
```

#### Total team

- 14 Classification Analysts
- 3 Senior Reviewers / Adjudicators
- 1 Taxonomy Lead
- 1 Operations Manager
- 1 Data/Tooling Analyst
- 1 additional Data/Automation Analyst if tooling is complex

**Total = 20 FTE** (or **21 FTE** with heavier automation/reporting needs)

---

## 5. Role-by-role definition

Below is the precise mission for each role.

# 5.1 Taxonomy Lead / Knowledge Architect — **1 FTE**

## Mission
Own the taxonomy as a controlled system. Ensure that every collection and subcollection is well defined, non-overlapping, usable, and versioned.

## Core responsibilities

- Design and maintain Level 1 and Level 2 taxonomy structure
- Write and approve definitions, inclusion/exclusion rules, and boundary rules
- Review taxonomy-gap requests
- Approve changes, merges, splits, and deprecations
- Maintain the taxonomy reference document
- Lead calibration on difficult edge cases
- Decide how historical reclassification should occur when taxonomy changes

## What success looks like

- Low ambiguity between tags
- Low reviewer overturn rate due to taxonomy confusion
- Strong classifier agreement on borderline cases
- Clean change logs and migration rules

## Weekly output

- approved taxonomy updates,
- precedent notes,
- revised examples,
- decision memos for ambiguous cases.

## What this role should **not** own

- day-to-day queue management,
- bulk production classification,
- ingestion pipeline maintenance.

---

# 5.2 Classification Operations Manager — **1 FTE**

## Mission
Run the classification function as an operation: staffing, throughput, backlog, SLA, and process discipline.

## Core responsibilities

- Build production schedules
- Assign batches and priorities
- Monitor throughput and queue health
- Track SLA and backlog burn-down
- Coordinate training and onboarding
- Run weekly operations reviews
- Ensure audit findings turn into actions
- Maintain process documentation and work instructions

## What success looks like

- predictable throughput,
- no uncontrolled backlog growth,
- stable staffing coverage,
- clear visibility into risks and blockers.

## Key metrics owned

- papers completed per week,
- backlog aging,
- % papers awaiting review,
- rework rate,
- escalations older than SLA.

---

# 5.3 QA & Adjudication Lead — **1 FTE for up to 5 analysts**

## Mission
Protect decision quality and consistency by auditing work, adjudicating ambiguous cases, and converting disagreement into written guidance.

## Core responsibilities

- Review all low-confidence cases
- Review sampled medium/high-confidence cases
- Resolve analyst disagreements
- Track error types and root causes
- Write QA reports
- Update precedent examples and ambiguity logs
- Recommend retraining when drift appears

## What success looks like

- low error recurrence,
- declining disagreement rate,
- rapid resolution of edge cases,
- clear feedback loops into taxonomy and training.

## Standard audit scope

- 100% of low-confidence cases
- 20–30% of medium-confidence cases during ramp-up
- 5–10% random sample of high-confidence cases once stable

---

# 5.4 Classification Analysts — **4 to 14+ FTE depending on volume**

## Mission
Perform the actual paper-by-paper classification work using the taxonomy reference and process rules.

## Core responsibilities

- Review title, abstract, and full text when needed
- Assign Level 1 main collection
- Assign Level 2 subcollection
- Record confidence and rationale
- Flag ambiguous, duplicate, or out-of-scope papers
- Escalate taxonomy gaps
- Participate in calibration sessions

## Production expectation per analyst

Use this as the standard target after ramp-up:

- **25–35 papers/day**
- **500–700 papers/month**

Planning target:

- **600 papers/month per analyst**

## What success looks like

- high first-pass accuracy,
- low avoidable escalations,
- concise rationales,
- correct use of taxonomy version and workflow.

## Analyst specialization rule

If the corpus is broad, assign analysts to **collection families** rather than random distribution.

Example:

- Analyst A: methods / theory papers
- Analyst B: application-domain papers
- Analyst C: resource / benchmark / survey papers

This improves speed and consistency.

---

# 5.5 Data / Tooling Analyst — **1 FTE**

## Mission
Make the classification operation scalable and observable by owning intake quality, deduplication support, dashboarding, and workflow tooling.

## Core responsibilities

- Maintain the intake dataset and classification interface
- Implement validation checks
- Support duplicate detection logic
- Build reporting dashboards
- Monitor tag distribution and anomalies
- Prepare exports to downstream systems
- Support machine-assisted preclassification if used
- Run bulk migration scripts when taxonomy versions change

## What success looks like

- minimal metadata defects,
- low duplicate leakage,
- real-time visibility into operations,
- low manual spreadsheet chaos.

## When to add a second tooling analyst

Add another tooling role when:

- volume exceeds ~10,000 finalized papers/month,
- ingestion sources are numerous,
- automated preclassification is being trained and monitored,
- or taxonomy migrations become frequent and complex.

---

# 5.6 Optional Domain SME coverage — **0.2 to 1.0 FTE each, not always full time**

## Mission
Support the team when the corpus spans fields that require expert interpretation beyond general classifier training.

## Use this role when

- the taxonomy spans multiple unrelated scientific domains,
- technical language is hard to interpret correctly,
- reviewers repeatedly disagree because of subject nuance,
- or the taxonomy is being expanded into new domains.

## Typical responsibilities

- advise on edge cases,
- review proposed definitions,
- validate example papers,
- help distinguish conceptually close domains.

## Important note

Do **not** replace process with SME dependency. SMEs should resolve exceptional ambiguity, not become the hidden system.

---

## 6. Recommended team by program phase

# Phase A — Taxonomy design and pilot launch

### Recommended staffing: **6 FTE** for 4–8 weeks

- 1 Taxonomy Lead
- 1 Operations Manager
- 1 QA / Adjudication Lead
- 2 Classification Analysts
- 1 Data / Tooling Analyst

### Mission of this phase

- design taxonomy v1,
- build the reference document,
- classify a pilot set,
- expose gaps and overlaps,
- establish baseline handling-time assumptions.

### Deliverables

- taxonomy v1.0
- classification SOP
- QA plan
- training set
- first 100–500 classified papers with adjudicated answers

---

# Phase B — Controlled production

### Recommended staffing: **8–11 FTE**

This is the right range for most organizations.

#### Lean version — 8 FTE
- 1 Taxonomy Lead
- 1 Operations Manager
- 1 QA Lead
- 4 Analysts
- 1 Data/Tooling Analyst

Capacity: about **2,000–2,400 papers/month**

#### Standard version — 10 FTE
- 1 Taxonomy Lead
- 1 Operations Manager
- 1 QA Lead
- 6 Analysts
- 1 Data/Tooling Analyst

Capacity: about **3,000–4,000 papers/month**

#### Strong-governance version — 11 FTE
- 1 Taxonomy Lead
- 1 Operations Manager
- 2 QA / Senior Reviewers
- 6 Analysts
- 1 Data/Tooling Analyst

Capacity: still about **3,000–4,000 papers/month**, but with stronger review and faster ambiguity resolution.

---

# Phase C — Enterprise-scale production

### Recommended staffing: **20 FTE** for ~8,000 papers/month

- 1 Taxonomy Lead
- 1 Operations Manager
- 3 Senior Reviewers / Adjudicators
- 14 Analysts
- 1 Data/Tooling Analyst

Add:

- +1 extra Data/Automation Analyst if automation is substantial
- +part-time domain SMEs if the subject spread is very broad

---

## 7. RACI-style ownership model

Use this as the operating responsibility map.

```md
| Activity | Taxonomy Lead | Ops Manager | QA Lead | Analysts | Data/Tooling |
|---|---|---|---|---|---|
| Define taxonomy structure | A/R | C | C | I | I |
| Update taxonomy reference | A/R | I | C | I | I |
| Assign paper classifications | I | I | C | R | I |
| Adjudicate difficult cases | C | I | A/R | C | I |
| Run daily queue | I | A/R | I | C | I |
| Audit batches | I | C | A/R | I | I |
| Track throughput metrics | I | A/R | C | I | R |
| Maintain classification tooling | I | C | I | I | A/R |
| Execute reclassification migration | A | C | C | I | R |
```

Legend:
- `R` = Responsible
- `A` = Accountable
- `C` = Consulted
- `I` = Informed

---

## 8. Operating cadence

### Daily

- analysts classify papers,
- QA reviews flagged cases,
- operations manager tracks queue and blockers.

### Weekly

- calibration session on disagreements,
- QA summary review,
- backlog and SLA review,
- taxonomy-gap triage.

### Monthly

- tag distribution review,
- taxonomy change review board,
- productivity and quality review,
- retraining decision if drift appears.

### Quarterly

- structural taxonomy review,
- deprecation and consolidation decisions,
- historical reclassification planning if necessary.

---

## 9. Performance metrics by role

### Team-level metrics

- finalized papers per month
- first-pass agreement rate
- reviewer overturn rate
- low-confidence rate
- taxonomy-gap rate
- rework rate
- average cycle time per paper

### Taxonomy Lead metrics

- number of unresolved ambiguity clusters
- time to approve taxonomy changes
- reduction in boundary confusion over time

### QA Lead metrics

- adjudication turnaround time
- repeat-error rate
- audit defect rate by tag

### Analyst metrics

- monthly output
- accuracy after audit
- escalation appropriateness
- rationale completeness

### Data/Tooling metrics

- duplicate detection effectiveness
- metadata completeness rate
- dashboard freshness
- migration execution accuracy

---

## 10. Hiring profile by role

### Taxonomy Lead

Look for:

- information architecture skill,
- classification system design,
- strong writing,
- comfort with scientific literature,
- ability to define boundaries precisely.

### Operations Manager

Look for:

- workflow management,
- SLA and backlog control,
- cross-functional coordination,
- metrics discipline.

### QA Lead

Look for:

- strong judgment,
- consistency mindset,
- ability to write decision precedent,
- coaching ability.

### Analysts

Look for:

- fast structured reading,
- comfort with abstracts and methods sections,
- reliable documentation habits,
- disciplined use of rules over intuition.

### Data/Tooling Analyst

Look for:

- workflow systems,
- spreadsheet/database competence,
- dashboarding,
- dedupe logic,
- change migration support.

---

## 11. What not to do

Avoid these mistakes.

### Mistake 1 — Understaffing QA

If nobody owns adjudication, disagreement will turn into silent inconsistency.

### Mistake 2 — Making the taxonomy lead the daily traffic controller

The taxonomy owner should protect conceptual quality, not spend all day distributing batches.

### Mistake 3 — Treating analysts as interchangeable without specialization

For broad corpora, specialization by collection family materially improves quality.

### Mistake 4 — Running production from spreadsheets without version control

You will lose auditability, precedent, and migration control.

### Mistake 5 — Expanding the taxonomy informally

Never let new tags appear through ad hoc classifier behavior.

---

## 12. Final recommendation

If you need one practical answer, use this:

### For most organizations, start with **10 FTE**

- 1 Taxonomy Lead
- 1 Operations Manager
- 1 QA & Adjudication Lead
- 6 Classification Analysts
- 1 Data / Tooling Analyst

This is the best default team for a 2-layer research paper classification program that needs real governance and dependable output.

### Scale rule

- Add **1 analyst per additional ~600 papers/month** of required throughput.
- Add **1 extra senior reviewer for every 5 analysts**.
- Add **1 extra tooling/automation specialist** once you cross about **10,000 finalized papers/month** or build automated preclassification.
- Add **part-time domain SMEs** when the taxonomy spans unrelated disciplines.

That model is simple, operationally realistic, and precise enough to plan budget and hiring.
