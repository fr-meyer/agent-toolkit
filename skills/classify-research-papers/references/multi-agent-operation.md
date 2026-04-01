# Multi-Agent Orchestration and Decision Governance

## Purpose

This document defines how to run research-paper classification with multiple agents or subagents **without losing consistency, accountability, or taxonomy control**.

It answers five critical questions:

1. when to stay single-agent
2. when to switch to multi-agent
3. how many agents to use
4. how disagreements should be resolved
5. who has final authority

---

## Executive Recommendation

The best operating model is:

# **Bounded Deliberation with Designated Adjudication**

This is a hybrid model that combines:
- independent classifier work
- explicit disagreement surfacing
- limited rebuttal / critique rounds
- role-weighted adjudication
- centralized final accountability

This model is better than:
- pure majority voting
- pure consensus seeking
- pure single-judge assignment for every paper

---

## Why Pure Democracy Is Not Recommended

A democratic vote sounds fair, but it is usually the wrong default for classification.

### Main problems
- two weak judgments can outvote one strong evidence-based judgment
- duplicated reasoning errors look like consensus
- the system optimizes for counting votes rather than weighing evidence
- responsibility becomes diffused
- repeated borderline cases can produce unstable precedent

### When voting can still be useful
Voting may be used as a **signal**, not as the final authority, in these cases:
- pilot taxonomy design
- early ambiguity detection
- calibration exercises
- optional secondary quality checks

Voting should inform review, not replace adjudication.

---

## Why Pure Judge-Centralization Is Also Not Recommended

A single central judge for every decision creates a bottleneck and reduces the value of parallel work.

### Main problems
- throughput collapses as volume grows
- edge cases pile up at one person or one agent
- hidden bias goes unchecked
- worker initiative declines
- the lead spends time on ordinary cases instead of policy and true escalations

A judge should decide only the cases that actually require adjudication.

---

## Best Choice: Hybrid, Role-Weighted, Evidence-Weighted Adjudication

### Decision philosophy
Use **independent proposals first**, then escalate only when needed.

### Operational principle
The final decision should be made by the **lowest level that can responsibly decide it**.

That preserves speed while keeping accountability.

### Practical hierarchy
1. **Classifier** decides ordinary cases.
2. **QA / Adjudication Lead** reviews medium-confidence, thin-evidence, or contested cases.
3. **Taxonomy Lead** decides taxonomy-boundary conflicts, Level 1 conflicts, and `taxonomy_gap` situations.
4. **Program Lead** decides policy, priority, staffing, and cross-program governance issues.

---

## Recommended Decision Model

## Per-paper default path

### Case type A — Straightforward paper
- one classifier evaluates
- if confidence is high and rationale is complete, accept
- QA checks only through sampling

### Case type B — Borderline paper
- one classifier evaluates
- if medium confidence or close alternative exists, route to QA
- QA either confirms, revises, or escalates

### Case type C — High-value or high-risk paper
- use double review from the start
- if reviewers agree, accept
- if they disagree, route to adjudication

### Case type D — Taxonomy boundary case
- classifier or QA flags `taxonomy_gap` or Level 1 uncertainty
- Taxonomy Lead adjudicates
- if structural change is needed, open a taxonomy change process rather than forcing a bad label

---

## Agreement Model

Do **not** require all agents to agree before a paper can be finalized.

### Better rule
Require:
- one normalized decision record
- one accountable owner for the final state
- recorded dissent when disagreement occurred

### Stable classification output means
- the decision used the current locked taxonomy version
- the rationale is evidence-based
- the strongest rejected alternative is documented
- any disagreement was resolved through the approved escalation path
- the final state is signed off by the correct authority level

Stability is more important than unanimity.

---

## Multi-Turn Debate Rule

Yes, multi-turn discussion is useful, but it must be **bounded**.

### Recommended maximum
- **Round 1** — independent classification
- **Round 2** — challenge / rebuttal
- **Round 3** — adjudication

After that, stop debating and route to the responsible adjudicator.

### Why bounded debate is best
- it extracts competing reasoning
- it reduces premature convergence
- it avoids infinite loops
- it preserves throughput

### Do not allow
- open-ended consensus hunting
- repeated rewrites without new evidence
- re-litigation of the same boundary without policy change

---

## Single-Agent vs Multi-Agent Mode

## Stay in single-agent mode when
- the environment does not support subagents or worker sessions
- the task has only **1–3 straightforward papers**
- the taxonomy version is not yet locked
- one senior agent can resolve the workload faster than a multi-agent merge process
- the task is a simple adjudication request on one specific paper

## Switch to multi-agent mode when **all** are true
- the environment explicitly supports worker execution
- the taxonomy version is locked for the active batch
- the batch has at least **4 papers**, or is expected to create many borderline cases, or requires audit/review depth
- the host can support a coordinator plus at least two workers
- the parent can collect and normalize outputs

---

## Environment-Gating Rule

Never assume multi-agent support exists.

Before using multi-agent mode, verify that the current environment supports:
- spawning or assigning worker agents
- collecting worker outputs
- routing items to review roles
- merging normalized results

If this support is unavailable, remain in single-agent mode and work serially.

---

## Agent-Count Policy

Use conservative parallelism by default.

### Recommended classifier counts
- **4–6 papers** → up to **2 classifier agents**
- **7–12 papers** → up to **3 classifier agents**
- **13+ papers** → up to **4 classifier agents**

### Additional review roles
- add up to **1 QA / adjudication agent** only when needed
- add up to **1 Taxonomy Lead / escalation agent** only when needed

### Recommended ceiling
- **4 classifier agents maximum at once**
- **6 total active agents maximum at once**, including coordinator-adjacent review roles

### Additional rules
- never spawn more classifier agents than work units
- never assign the same paper to multiple classifier agents unless double-review is intentional
- never exceed host limits
- if only one worker is available, use one worker and let the parent handle the rest serially

---

## Default Role Topology

## Parent / Coordinator
Responsibilities:
- lock taxonomy version
- decide single-agent or multi-agent mode
- create work units
- assign work
- collect results
- route flagged cases
- normalize outputs
- merge final batch report

## Classifier Worker
Responsibilities:
- read assigned paper(s)
- propose one Level 1 and one Level 2 path or an escalation outcome
- provide evidence-based rationale
- name strongest rejected alternative
- mark confidence
- request review when appropriate

## QA / Adjudication Worker
Responsibilities:
- review medium or low confidence outputs
- review thin rationale or weak evidence outputs
- review close-alternative cases
- confirm, revise, or escalate

## Taxonomy Lead Worker
Responsibilities:
- resolve Level 1 conflicts
- resolve persistent Level 2 conflicts
- handle `taxonomy_gap`
- determine whether a taxonomy change is required

## Program Lead
Responsibilities:
- decide policy, priority, and governance matters
- approve major taxonomy changes
- decide how unresolved escalations affect delivery scope

---

## Work-Unit Sizing Rules

### Default rule
Assign **one paper per classifier worker**.

### Bundle only when
- the papers are closely related
- consistency across the mini-set matters more than maximum parallelism
- the worker must compare sibling papers to classify them correctly

### Avoid
- large mixed-topic bundles
- hidden bundle dependencies
- bundles so large that one worker becomes a bottleneck

### Ordering rule
Preserve the user's original paper order in assignment tracking and final reporting.

---

## Output Contract — Required Fields

Every worker result should include at least:

```yaml
parent_batch_id:
paper_position:
worker_role:
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

### Field purpose
- `parent_batch_id` — ties the record to the coordinator job
- `paper_position` — preserves user ordering
- `worker_role` — classifier, QA, taxonomy_lead, etc.
- `taxonomy_version` — prevents cross-version mixing
- `source_evidence_scope` — title/abstract only, title+abstract+intro, full text, etc.
- `decision_status` — accepted, escalated, taxonomy_gap, needs_more_evidence, out_of_scope
- `review_required` — simple routing flag
- `review_reason` — why the coordinator should route the record

---

## Allowed Decision Status Values

Use only a small controlled set:

- `accepted`
- `accepted_after_review`
- `revised_after_review`
- `escalated`
- `taxonomy_gap`
- `needs_more_evidence`
- `out_of_scope`

Do not invent ad hoc status labels in production.

---

## Confidence Policy

### High confidence
- label fits strongly
- nearest alternative is clearly weaker
- evidence is sufficient
- no review required unless the paper is in a mandatory review sample

### Medium confidence
- plausible fit, but close sibling exists
- route to QA if the case is high-value or if similar boundary issues are recurring

### Low confidence
- evidence is thin or contradictory
- route to QA or taxonomy lead
- do not force a final label without escalation

---

## Conflict Resolution Rules

## Rule 1 — Classifier and QA agree
Accept the shared result.

## Rule 2 — Classifier and QA disagree on Level 2 but agree on Level 1
Route to Taxonomy Lead for adjudication if:
- the difference reflects a real boundary problem
- or the disagreement cannot be resolved by clearer reading of the same evidence

Otherwise QA may revise directly and document why.

## Rule 3 — Classifier and QA disagree on Level 1
Always escalate to Taxonomy Lead.

## Rule 4 — Missing evidence
If the core problem is inadequate evidence, return `needs_more_evidence` rather than pretending adjudication solved it.

## Rule 5 — Structural mismatch
If the paper does not fit the current tree cleanly and repeatedly exposes the same issue, return `taxonomy_gap` and open a taxonomy change request.

## Rule 6 — Do not fake consensus
Never compress disagreement into a silent final label with no trace.

Record:
- who disagreed
- what the alternatives were
- who decided
- why the final decision won

---

## Pairwise Escalation Matrix

### Classifier → QA
Use when:
- medium confidence
- thin rationale
- close competing alternative
- high-value paper
- mandatory second review sample

### Classifier → Taxonomy Lead
Use when:
- Level 1 cannot be resolved
- suspected taxonomy gap
- precedent conflict with current taxonomy
- new paper type appears

### QA → Taxonomy Lead
Use when:
- QA cannot responsibly decide between siblings
- disagreement reveals structural ambiguity
- repeated conflict pattern exists

### Taxonomy Lead → Program Lead
Use when:
- taxonomy change affects delivery commitments
- sponsor priorities conflict with the best scientific structure
- backlog, staffing, or policy decisions are required

---

## Multi-Agent Boundaries

Do **not**:
- spawn subagents for a single obvious paper unless explicitly requested
- use multi-agent mode before locking the taxonomy version
- merge records created under different taxonomy versions
- escalate every medium-confidence case by reflex
- create duplicate review on every paper by default
- assume any one host platform's orchestration features are always available

---

## Batch-Level Merge Logic

The parent coordinator should return:

1. one final normalized decision record per paper
2. a section for papers finalized without review
3. a section for papers finalized after review
4. a section for unresolved escalations
5. a section for `taxonomy_gap` patterns
6. a section for repeated ambiguity / boundary failures

This matters because batch quality is not only the sum of paper-level labels.
It also depends on recurring patterns that reveal taxonomy or workflow weakness.

---

## Recommended Final Decision Rights

## Ordinary case
Final by classifier, subject to QA sampling.

## Medium-confidence or contested Level 2 case
Final by QA unless the issue is structural.

## Level 1 conflict or taxonomy gap
Final by Taxonomy Lead.

## Program-wide governance or SLA trade-off
Final by Program Lead.

This is the cleanest split of authority.

---

## Final Recommendation

Use:
- **distributed independent proposals**
- **bounded critique**
- **role-weighted adjudication**
- **centralized accountability**
- **logged dissent**
- **taxonomy version control**

Do **not** use simple majority voting as the default final decision rule.

Do **not** require full consensus before moving forward.

The best operating model is a **hybrid adjudication system** with clear decision rights and limited debate rounds.
