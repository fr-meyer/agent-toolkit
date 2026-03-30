# Taxonomy Creation from Scratch Playbook

## Purpose

Use this playbook when **no usable taxonomy exists** or when the existing taxonomy is so weak, inconsistent, or outdated that it should not be used as the governing frame for paper classification.

This playbook is designed for a **2-layer classification tree**:

- **Level 1 = Main Collection**
- **Level 2 = Subcollection**

Production rule:

- every in-scope paper should end with exactly **one Level 1 assignment** and **one Level 2 assignment**
- exceptions must be explicit and rare: `taxonomy_gap`, `needs_more_evidence`, `out_of_scope`, or `escalated`

---

## Core Design Principle

Do **not** start by inventing labels in the abstract.

Start from the corpus, the sponsor purpose, and the downstream use case, then derive the taxonomy from real evidence.

A good taxonomy is not only intellectually neat. It must also be:

- understandable by humans
- stable enough for repeated classification
- operationally usable by analysts and agents
- narrow enough to reduce ambiguity
- broad enough to cover the corpus without a giant miscellaneous bucket

---

## When to Use This Playbook

Use taxonomy creation from scratch if any of the following are true:

- no taxonomy was provided
- the provided taxonomy has no definitions
- the provided taxonomy mixes methods, domains, tasks, and applications without a governing rule
- analysts cannot apply the taxonomy consistently
- more than 15% of pilot papers land in `miscellaneous`, `other`, or repeated escalation states
- the user wants a new classification system designed for a new corpus or program

Do **not** skip taxonomy design and jump directly to batch classification. That creates inconsistent precedent and expensive rework.

---

## Non-Negotiable Principles

1. **One governing basis of classification**
   - Default basis: classify by the paper's **primary intellectual contribution**.
   - Do not mix basis across branches unless explicitly intended and documented.

2. **Mutual exclusivity at decision time**
   - A paper may touch many topics, but the classifier must still assign the best single Level 1 and Level 2 path.

3. **Exhaustiveness within scope**
   - Most in-scope papers should fit somewhere without forcing arbitrary decisions.

4. **Boundary clarity**
   - Each label must have inclusion rules, exclusion rules, and nearest-neighbor distinctions.

5. **Version control**
   - Once classification begins, the taxonomy version must be locked for the active batch.

6. **Bounded convergence**
   - Seek agreement through structured review, but do not allow endless debate.

---

## Recommended Governance Choice

For taxonomy creation and later production classification, the best choice is **not pure democracy** and **not pure single-judge centralization**.

### Recommended model

Use **bounded distributed proposal with centralized adjudication**:

- multiple agents or analysts independently propose structure
- disagreements are surfaced explicitly
- a designated accountable lead decides after reviewing evidence
- dissent is logged, not erased
- the taxonomy changes only through controlled approval

### Why this is better than pure democracy

Pure voting is weak for taxonomy design because:

- identical mistakes can win by repetition
- majority vote hides whether the winning side had stronger evidence
- experts and novices get equal weight even when the issue is technical
- there is no single accountable owner when downstream problems appear

### Why this is better than pure judge-only design

Pure single-judge design is also weak because:

- the lead becomes a bottleneck
- blind spots are harder to catch
- edge cases are under-explored
- trust falls when contributors feel their evidence never matters

### Final recommendation

Use a **hybrid**:

- **distributed generation**
- **structured critique**
- **centralized final approval**
- **logged dissent and precedent**

That creates both quality and accountability.

---

## Roles in Taxonomy Creation

### Classification Program Director / Program Lead
Owns scope, approval authority, timeline, and business alignment.

### Taxonomy Lead / Knowledge Architect
Primary author of the taxonomy structure, definitions, boundaries, and versioning.

### Classification Operations Manager
Turns the taxonomy design into an executable workflow, staffing plan, and operating cadence.

### QA & Adjudication Lead
Tests whether the taxonomy can be applied consistently and identifies ambiguity patterns.

### Classification Analysts
Provide corpus-grounded evidence, candidate examples, counterexamples, and pilot classifications.

### Data / Tooling Analyst
Builds corpus samples, clustering views, dashboards, and version-control support.

### Optional Domain SMEs
Used when the corpus spans specialized fields that require expert interpretation.

---

## Deliverables

At minimum, taxonomy creation from scratch should produce:

1. taxonomy charter
2. corpus profile
3. Level 1 proposal
4. Level 2 proposal
5. label definition cards
6. inclusion / exclusion rules
7. example papers per label
8. ambiguity log
9. pilot classification results
10. stability assessment
11. approved taxonomy version
12. change-control rules

---

## Phase-by-Phase Workflow

## Phase 0 — Charter the Taxonomy Project

### Objective
Define why the taxonomy exists and what it must optimize for.

### Owner
Program Lead

### Inputs
- sponsor goal
- downstream use case
- corpus access
- scope constraints
- expected volume
- expected users of the output

### Required decisions
- what the taxonomy is for
- what “good classification” means
- what is in scope
- what is out of scope
- what classification basis will govern the tree

### Output
A **taxonomy charter** containing:
- mission
- scope
- target user
- classification basis
- quality targets
- approval authority

### Example charter questions
- Is the goal retrieval, portfolio management, literature mapping, or model training?
- Should the taxonomy emphasize research problem, contribution type, method family, application area, or discipline?
- Will the output be used by experts, generalists, or software systems?

---

## Phase 1 — Build a Corpus Discovery Sample

### Objective
Create an evidence base before naming labels.

### Owners
Taxonomy Lead + Data / Tooling Analyst

### Required sample design
Create a discovery set that is:
- large enough to expose diversity
- balanced enough to avoid early bias
- representative of the main corpus

### Recommended starting sample
For a new taxonomy:
- minimum: **100 papers**
- preferred: **200–300 papers**
- if the corpus is very large and heterogeneous: sample across source, year, venue, and topic segments

### For each sampled paper, extract
- title
- abstract
- keywords
- venue
- year
- claimed contribution
- method family
- problem/task
- domain/application
- notable boundary signals

### Output
A structured discovery spreadsheet or markdown registry.

---

## Phase 2 — Create an Evidence Map

### Objective
Understand the natural structure of the corpus before committing to labels.

### Owners
Taxonomy Lead + Analysts + Data / Tooling Analyst

### Actions
- group papers by apparent primary contribution
- separately note method, task, domain, and application signals
- identify repeated conceptual clusters
- identify obvious overlaps and collisions
- identify rare but important paper types

### Required analytical question
What seems to be the **most stable governing basis** for the whole corpus?

### Common basis options
- research problem
- contribution type
- methodological family
- application domain
- artifact type

### Decision rule
Choose the basis that:
- explains the most papers cleanly
- minimizes overlap
- remains understandable to users
- can support stable Level 2 distinctions

### Output
An evidence map with candidate cluster names and collision notes.

---

## Phase 3 — Draft Level 1 Main Collections

### Objective
Propose the smallest sensible set of top-level buckets.

### Owner
Taxonomy Lead

### Constraints
Level 1 labels should be:
- broad but meaningful
- mutually distinguishable
- not excessively numerous
- stable across future additions

### Recommended target count
- small corpus: **4–8 Level 1 collections**
- broader corpus: **6–12 Level 1 collections**

Too few creates overloaded buckets.
Too many creates artificial fragmentation.

### Level 1 label design test
Each proposed Level 1 collection must answer:
- what belongs here?
- what does not belong here?
- how is it distinct from its nearest sibling?
- can an analyst decide this from title + abstract in most cases?
- will this still make sense after 6–12 months of corpus growth?

### Output
A Level 1 draft with:
- name
- one-sentence definition
- inclusion signals
- exclusion signals
- nearest-neighbor comparison
- example papers

---

## Phase 4 — Draft Level 2 Subcollections

### Objective
Split each Level 1 collection into operationally usable subcollections.

### Owners
Taxonomy Lead + Analysts

### Constraints
Level 2 labels should:
- inherit the Level 1 logic
- not switch to a completely different classification basis without explicit justification
- be specific enough to help retrieval and assignment
- remain usable at scale

### Recommended target count
Per Level 1 branch:
- minimum: **2**
- typical: **3–7**
- avoid creating Level 2 leaves with almost no expected population unless the category is strategically important

### Common Level 2 failure modes
- names too vague
- names overlap
- names reflect synonyms rather than real distinctions
- one branch is method-based while sibling branches are domain-based
- an “Other” branch becomes the real largest category

### Output
A full 2-layer draft tree.

---

## Phase 5 — Write Definition Cards for Every Label

### Objective
Turn labels into executable classification instructions.

### Owner
Taxonomy Lead

### Each label card must contain
- label ID
- label name
- parent label
- definition
- what belongs
- what does not belong
- inclusion cues
- exclusion cues
- closest confusing alternative
- positive examples
- negative examples
- notes for edge cases

### Mandatory rule
No label should go live with only a name.

A label name without a definition is not a taxonomy. It is only a placeholder.

---

## Phase 6 — Run a Pilot Classification

### Objective
Test whether independent people or agents can use the taxonomy consistently.

### Owners
QA Lead + Analysts

### Recommended pilot size
- minimum: **50 papers**
- preferred: **100+ papers**
- stratify to include obvious, ambiguous, and boundary cases

### Pilot method
1. lock the draft taxonomy version
2. assign the same paper set independently to multiple reviewers
3. capture confidence, rejected alternative, and escalation notes
4. compare disagreements
5. cluster disagreement reasons

### What to measure
- label coverage
- disagreement rate
- repeated confusions
- use of `other` / `miscellaneous`
- use of `taxonomy_gap`
- low-confidence frequency
- repeated need for full-text review

### Recommended launch thresholds
These are operating targets, not universal laws.

- at least **90–95%** of in-scope pilot papers fit named labels without forced placement
- `other` / `miscellaneous` should be **below 10%** in pilot and ideally **below 5%** before launch
- repeated boundary conflicts should be concentrated in a small number of known edges
- most ordinary papers should be classifiable from title + abstract or title + abstract + skimmed introduction
- disagreement should decline after one clarification round

If these thresholds are not met, revise the taxonomy before large-scale rollout.

---

## Phase 7 — Convergence and Stability Review

### Objective
Determine whether the taxonomy is stable enough for production use.

### Owners
Taxonomy Lead + QA Lead + Program Lead

### Stability review questions
- Are disagreements mostly about a few boundary pairs, or are they everywhere?
- Does each Level 1 branch have a coherent internal logic?
- Are some Level 2 labels too thin or too broad?
- Are analysts repeatedly confused for the same reason?
- Are the labels still understandable to non-authors of the taxonomy?
- Can new papers be handled without constant redesign?

### Stability decision outcomes
- **approve as-is**
- **approve with minor clarifications**
- **revise branch definitions**
- **merge labels**
- **split overloaded labels**
- **rebuild Level 1 structure**
- **delay launch**

### Rule
Do not call the taxonomy stable merely because debate became tiring.

A stable taxonomy is one that can be **used repeatedly with acceptable consistency**.

---

## Phase 8 — Lock Version 1.0 and Publish

### Objective
Move from design mode into production mode.

### Owners
Program Lead + Taxonomy Lead

### Required publication artifacts
- taxonomy tree
- definition cards
- precedent rules
- escalation rules
- effective date
- version ID
- owner
- change process
- deprecation policy

### Lock rule
Once a batch starts, that batch must use one taxonomy version only.

Do not merge results classified under multiple taxonomy versions without explicit normalization.

---

## Phase 9 — Post-Launch Governance

### Objective
Prevent taxonomy drift while allowing controlled improvement.

### Owners
Program Lead + Taxonomy Lead + QA Lead

### Establish
- change request form
- periodic review cadence
- precedent log
- deprecation procedure
- retroactive reclassification policy
- release notes format

### Trigger a taxonomy review if
- a single escalation reason repeats often
- one label becomes overloaded
- one label becomes nearly empty
- new paper types appear that do not fit current branches
- repeated precedent conflicts emerge
- the downstream sponsor changes the use case

---

## Bounded Multi-Turn Convergence Protocol

Use this when creating or refining the taxonomy with multiple agents or reviewers.

### Round 1 — Independent proposal
Each contributor proposes:
- candidate Level 1 structure
- candidate Level 2 structure
- rationale
- likely collisions
- gaps
- uncertainties

### Round 2 — Structured critique
Each contributor reviews the others and must identify:
- strongest agreement
- strongest disagreement
- merge candidates
- split candidates
- labels that are badly named
- labels that switch basis

### Round 3 — Adjudicated merge
The Taxonomy Lead produces a merged proposal and explicitly states:
- what was accepted
- what was rejected
- why
- what remains provisional

### Optional Round 4 — Executive approval
Program Lead confirms operational fit and approves or requests targeted revision.

### Hard stop rule
Do **not** allow endless debate.

If there is still disagreement after:
- one independent proposal round
- one critique round
- one adjudicated merge round

then the Taxonomy Lead decides, logs dissent, and moves forward.

Consensus is desirable.
Unanimity is not required.

---

## Decision Rules for Split / Merge / Rename / Retire

### Split a label when
- it contains multiple distinct contribution types
- reviewers repeatedly disagree within that label
- the label is too large to be useful
- sub-patterns are stable and meaningful

### Merge labels when
- distinctions are mostly linguistic rather than conceptual
- reviewers cannot apply the distinction reliably
- both labels route to nearly identical evidence patterns

### Rename a label when
- the concept is correct but the wording causes confusion
- the label uses internal jargon not understandable to users
- the label name overstates or understates its scope

### Retire a label when
- it has no stable population
- it duplicates another label
- its boundary cannot be defined cleanly

---

## Taxonomy Acceptance Checklist

A taxonomy is ready for production only if all of the following are true:

- [ ] scope is documented
- [ ] governing classification basis is explicit
- [ ] every Level 1 label has a definition
- [ ] every Level 2 label has a definition
- [ ] inclusion and exclusion rules exist
- [ ] nearest-neighbor confusion notes exist
- [ ] example papers exist
- [ ] escalation states are defined
- [ ] pilot results were reviewed
- [ ] version ID is assigned
- [ ] owner is assigned
- [ ] change-control process exists

---

## Recommended Artifact Templates

## Taxonomy Charter
```md
# Taxonomy Charter
Version:
Owner:
Date:
Mission:
Primary use case:
In-scope corpus:
Out-of-scope corpus:
Governing classification basis:
Success criteria:
Approval authority:
```

## Label Definition Card
```md
# Label Definition Card
Label ID:
Label Name:
Parent Label:
Definition:
What belongs:
What does not belong:
Inclusion cues:
Exclusion cues:
Closest confusing alternative:
Positive examples:
Negative examples:
Notes:
```

## Taxonomy Change Request
```md
# Taxonomy Change Request
Request ID:
Requested by:
Date:
Current version:
Problem observed:
Affected labels:
Evidence:
Proposed action: split / merge / rename / add / retire / redefine
Impact on existing records:
Urgency:
Decision:
Decision owner:
Effective version:
```

---

## Recommended Timeline for a Serious First Version

For a medium-scale program:

- **Week 1** — charter + discovery sample
- **Week 2** — evidence map + Level 1 draft
- **Week 3** — Level 2 draft + definition cards
- **Week 4** — pilot classification + ambiguity analysis
- **Week 5** — revision + approval + v1.0 publication

Shorter timelines are possible, but skipping the pilot is usually a false economy.

---

## Final Recommendation

If no taxonomy exists, do **not** treat taxonomy design as a side note.
Treat it as a formal project phase with:
- named ownership
- explicit evidence gathering
- bounded multi-turn critique
- centralized final approval
- version control
- launch thresholds

That is the most reliable way to create a taxonomy that analysts and agents can actually use.
