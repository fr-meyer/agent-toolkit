# Research Paper Classification Tutorial (2-Layer Taxonomy)

## Document purpose

This document is a **chronological, step-by-step operating procedure** for classifying research papers into:

1. a **main collection** (Level 1), and
2. a **subcollection** within that main collection (Level 2).

It is written as a reusable template. Replace bracketed placeholders such as `[Project Name]`, `[Collection Name]`, and `[Subcollection Name]` with your real taxonomy.

---

## 1. Scope

Use this workflow when you need to assign **one primary Level 1 collection** and **one primary Level 2 subcollection** to each paper.

### Assumptions

- The taxonomy has exactly **2 navigational layers**:
  - **Level 1** = Main collection
  - **Level 2** = Subcollection
- Each paper receives:
  - one primary main collection,
  - one primary subcollection,
  - a confidence score,
  - optional notes for ambiguity or escalation.
- The objective is **consistent retrieval and browsing**, not perfect philosophical representation of every nuance in a paper.
- When a paper is multidisciplinary, the classifier must still choose **one primary location** using the decision rules below.

### Non-goals

This procedure does **not** define the taxonomy itself. That belongs in the separate taxonomy reference document.

---

## 2. Required inputs before classification begins

Before production classification starts, make sure all of the following exist.

### Required assets

- A published taxonomy with:
  - Level 1 collections
  - Level 2 subcollections
  - definitions
  - inclusion criteria
  - exclusion criteria
  - examples
- A paper intake sheet or database
- A classification form or UI
- A QA and escalation process
- A versioned taxonomy reference document
- A list of mandatory metadata fields

### Minimum metadata per paper

Each paper record should contain at least:

- Paper ID
- Title
- Authors
- Year
- Venue / source
- Abstract
- DOI / URL / arXiv ID / publisher link
- Full text link or PDF if available
- Language
- Existing keywords, if available

### Recommended output fields

For every classification decision, store:

- `paper_id`
- `main_collection`
- `subcollection`
- `confidence` (`high`, `medium`, `low`)
- `decision_basis` (title / abstract / full text / reviewer note)
- `needs_review` (`yes` / `no`)
- `review_reason`
- `classifier_name`
- `classification_date`
- `taxonomy_version`
- `notes`

---

## 3. Core decision principles

These rules matter more than intuition. All classifiers should follow the same order of precedence.

### Rule 1: Classify by the paper's **primary intellectual contribution**

Choose the category that best answers:

> "What is the main thing this paper contributes or studies?"

Use the paper's **central contribution**, not just a passing mention, dataset, or application example.

### Rule 2: Prefer the **author-stated objective** over incidental details

If the title, abstract, introduction, and conclusion consistently describe the same main purpose, classify on that basis.

### Rule 3: Use the **deepest valid node**

Do not stop at the main collection if a clearly correct subcollection exists. Always assign both levels if possible.

### Rule 4: One paper, one primary location

Even if the paper touches many themes, assign one primary main collection and one primary subcollection.

### Rule 5: Use evidence hierarchy

Resolve decisions using this evidence order:

1. Title
2. Abstract
3. Introduction / problem statement
4. Method section
5. Experiments / evaluation
6. Conclusion

### Rule 6: Escalate ambiguity instead of forcing certainty

If confidence is low after reviewing the abstract and key body sections, mark the paper for adjudication.

---

## 4. Roles in the workflow

These roles can be played by different people or combined in a small team.

### Classifier

- Reviews the paper
- Assigns main collection and subcollection
- Adds confidence and notes
- Flags ambiguity

### Senior reviewer / adjudicator

- Resolves low-confidence cases
- Reviews borderline decisions
- Updates examples and edge-case rules

### Taxonomy owner

- Maintains definitions
- Approves taxonomy changes
- Resolves structural conflicts between categories

### Operations lead

- Tracks throughput, backlog, SLA, and audit results
- Ensures training, calibration, and process compliance

---

## 5. End-to-end chronological workflow

This is the recommended order of operations.

# Phase 0 — Prepare the system before the first paper is classified

### Step 0.1 — Freeze the taxonomy version for the current batch

Before production starts, define the active taxonomy version, for example:

- `v1.0`
- `v1.1`
- `2026-Q1`

Do **not** let classifiers work against changing definitions mid-batch.

### Step 0.2 — Train the classification team

Training should include:

- taxonomy overview
- decision rules
- review of edge cases
- practice set with answer key
- calibration exercise

### Step 0.3 — Build the classification form

At minimum, the form should ask for:

- paper ID
- title
- abstract
- main collection
- subcollection
- confidence
- notes
- escalation flag

### Step 0.4 — Define the audit policy

Recommended audit policy:

- 100% review of low-confidence cases
- 20–30% review of medium-confidence cases during early ramp-up
- 5–10% random review of high-confidence cases after stabilization

---

# Phase 1 — Intake and metadata normalization

### Step 1.1 — Import the paper record

Create or retrieve the paper record from the source system.

### Step 1.2 — Validate metadata completeness

Check whether the paper has enough information to classify.

#### If metadata is sufficient
Continue to Step 1.3.

#### If metadata is missing
Apply this recovery order:

1. Use title + abstract if available.
2. If abstract is missing, retrieve abstract from the source.
3. If title is vague and abstract unavailable, open the full text.
4. If still insufficient, mark as `insufficient_information` and route for metadata enrichment.

### Step 1.3 — Normalize record fields

Normalize:

- title casing only if your system requires it
- duplicated whitespace
- author separators
- venue names
- identifiers
- language flag

### Step 1.4 — Check for duplicate records

Before classifying, verify whether the same paper already exists as:

- preprint and journal version
- duplicate ingestion from multiple sources
- translated duplicate
- partial metadata duplicate

If duplicates exist, apply your duplicate-handling rule before classification.

---

# Phase 2 — Relevance and eligibility triage

### Step 2.1 — Confirm the item is actually a research paper

Exclude or separately label items such as:

- editorial notes
- corrigenda
- conference schedules
- cover pages
- announcements
- table of contents entries
- non-paper artifacts

### Step 2.2 — Confirm the paper belongs in the overall corpus

If your corpus has scope boundaries, verify them now.

Examples of corpus boundaries:

- only peer-reviewed literature
- only English papers
- only papers after a certain year
- only papers relevant to `[Domain Name]`

If the paper is out of corpus scope, mark it accordingly and stop.

---

# Phase 3 — Rapid content scan

The goal here is to form an initial hypothesis quickly.

### Step 3.1 — Read the title once

Ask:

- What topic is explicitly named?
- Is the paper about a method, application, dataset, review, theory, or evaluation?
- Does the title indicate a domain or technique?

### Step 3.2 — Read the abstract carefully

Extract the following from the abstract:

- **problem** — what issue is being addressed?
- **object** — what subject, system, or phenomenon is studied?
- **method** — what approach is used?
- **output** — what is contributed (model, framework, survey, dataset, benchmark, theory)?
- **evaluation context** — where or how is it tested?

### Step 3.3 — Write a one-sentence paraphrase

Before selecting a category, force the classifier to paraphrase:

> "This paper mainly does X for Y using Z."

This is one of the strongest consistency controls in the workflow.

#### Example

> "This paper proposes a graph-based method for detecting misinformation in online social networks."

That single sentence usually makes the correct Level 1 and Level 2 choice much clearer.

---

# Phase 4 — Candidate selection

### Step 4.1 — Generate 2–3 likely main collections

Do not jump to a final answer immediately. First create a short candidate list.

Example:

- Candidate 1: `[Main Collection A]`
- Candidate 2: `[Main Collection B]`
- Candidate 3: `[Main Collection C]`

### Step 4.2 — Compare the paper against the Level 1 definitions

For each candidate, answer:

- Does the paper match the definition?
- Does it satisfy the inclusion rule?
- Does it violate any exclusion rule?
- Is the match about the main contribution or only a secondary detail?

### Step 4.3 — Select the best Level 1 main collection

Choose the main collection with the strongest evidence from the paper's **core contribution**.

### Step 4.4 — Generate candidate subcollections only within the selected main collection

After Level 1 is fixed, shortlist the subcollections under that main collection.

### Step 4.5 — Compare against subcollection definitions

For each candidate subcollection, test:

- scope fit
- boundary rules
- typical paper types
- examples and counterexamples

### Step 4.6 — Select the final subcollection

Assign the deepest valid node within the chosen main collection.

---

# Phase 5 — Verification using the full paper when needed

Use this phase only if the title and abstract are insufficient or conflicting.

### Step 5.1 — Open the introduction

Read the first 1–3 paragraphs and identify:

- the stated research problem
- the claimed contribution
- the intended audience or domain

### Step 5.2 — Inspect section headings

Look at headings such as:

- Methods
- Proposed approach
- Experiments
- Benchmark
- Survey methodology
- Case study

These often reveal whether the paper is primarily theoretical, methodological, applied, evaluative, or review-oriented.

### Step 5.3 — Read the contribution statement or conclusion

If the introduction says one thing and the experiments emphasize another, the contribution statement and conclusion usually settle the question.

### Step 5.4 — Re-test the chosen Level 1 and Level 2 assignment

Ask:

- Does my chosen classification still fit after reading the body?
- Is there a more specific subcollection that better represents the paper?
- Was I confusing the application domain with the actual contribution type?

---

# Phase 6 — Apply formal decision rules for difficult cases

Use these rules exactly as written.

## Case A — Method vs application domain

If a paper proposes a new method and merely tests it in a domain, classify by the **method** unless your taxonomy explicitly prioritizes application domains.

### Example

A paper introduces a new optimization algorithm and evaluates it on medical image datasets.

- Primary classification: optimization / algorithmic method
- Not: healthcare application

## Case B — Application paper using standard methods

If the paper's novelty is in applying known methods to solve a domain-specific problem, classify by the **application problem/domain**.

### Example

A paper applies standard transformers to legal judgment prediction and frames its contribution as a legal AI task study.

- Primary classification: legal AI application area
- Not: general transformer methods

## Case C — Survey / review / benchmark papers

If the paper synthesizes literature rather than proposing a new method, classify it under the review / survey / benchmark subcollection if one exists.

## Case D — Dataset papers

If the core contribution is a dataset, corpus, benchmark, or annotation scheme, classify under the data resource or benchmark subcollection.

## Case E — Theory papers

If the paper contributes formal proof, analysis, or conceptual theory rather than empirical application, classify under the theory-oriented node.

## Case F — Multidisciplinary papers

Choose the category that best represents:

1. the stated contribution,
2. the majority of the paper's substance,
3. the target retrieval need.

If still ambiguous, escalate.

## Case G — Emerging topic not covered well by the taxonomy

Do **not** invent a new production tag during classification.

Instead:

- assign the closest valid current category,
- mark `taxonomy_gap = yes`,
- note the proposed new or revised tag,
- route to the taxonomy owner.

---

# Phase 7 — Record confidence and rationale

### Step 7.1 — Assign confidence

Use the following rubric.

#### High confidence

- Title and abstract clearly match one category
- Definitions are unambiguous
- No meaningful overlap with neighbors

#### Medium confidence

- One category is best, but one or two neighbors are plausible
- Full text or deeper reading was required
- Boundary is manageable but not obvious

#### Low confidence

- Multiple categories remain plausible
- Taxonomy language is unclear
- Paper is unusually interdisciplinary or underspecified

### Step 7.2 — Write a short rationale

Recommended format:

> Assigned to `[Main Collection] > [Subcollection]` because the paper's primary contribution is `[summary]`; evidence found in `[title/abstract/introduction/method]`.

### Step 7.3 — Mark review requirement

Set `needs_review = yes` if:

- confidence is low,
- the paper triggered a taxonomy gap,
- the classifier had to override an automated suggestion,
- the case exposes a boundary ambiguity.

---

# Phase 8 — Quality assurance and adjudication

### Step 8.1 — Run first-line QA checks

Before finalizing, verify:

- a main collection is selected,
- a subcollection under that main collection is selected,
- the subcollection belongs to the chosen parent,
- confidence is present,
- rationale is present for medium/low confidence,
- taxonomy version is recorded.

### Step 8.2 — Route flagged papers to adjudication

The senior reviewer should evaluate:

- low-confidence cases
- disagreement cases
- taxonomy-gap cases
- new edge-case patterns

### Step 8.3 — Record final disposition

Store whether the adjudicator:

- confirmed the original decision,
- modified the main collection,
- modified the subcollection,
- updated the taxonomy guidance,
- sent the paper to metadata repair.

### Step 8.4 — Capture precedent

Every difficult resolved case should be converted into a reusable example in the taxonomy reference or calibration guide.

---

# Phase 9 — Finalization and publishing

### Step 9.1 — Lock the classification record

Once QA is complete, freeze the final classification unless a later taxonomy migration occurs.

### Step 9.2 — Export to downstream systems

Push the final classification to:

- search index
- collection browser
- analytics dashboard
- internal repository
- labeling dataset for ML support, if applicable

### Step 9.3 — Log unresolved taxonomy issues

Keep a structured issue register for:

- recurring confusion between categories
- proposed tag additions
- problematic definitions
- papers that fit poorly anywhere

---

# Phase 10 — Ongoing calibration and continuous improvement

### Step 10.1 — Hold weekly calibration sessions during ramp-up

Review:

- disagreements
- low-confidence cases
- new paper types
- drift in interpretation across classifiers

### Step 10.2 — Measure quality trends

Track at minimum:

- agreement rate
- adjudication overturn rate
- low-confidence rate
- taxonomy-gap rate
- papers processed per classifier per day
- rework rate

### Step 10.3 — Update the taxonomy reference, not the classifier's memory

If a boundary rule changes, update the reference document and announce the new version. Never rely on informal oral memory for production consistency.

---

## 6. Recommended per-paper working sequence for classifiers

Use this checklist exactly in order.

### Classifier checklist

1. Open the paper record.
2. Validate title, abstract, and identifier.
3. Confirm the item is in corpus scope.
4. Read the title.
5. Read the abstract.
6. Write the one-sentence paraphrase.
7. Identify the paper's primary contribution type.
8. Shortlist 2–3 candidate main collections.
9. Compare against Level 1 definitions.
10. Choose the main collection.
11. Shortlist subcollections under that main collection.
12. Compare against Level 2 definitions.
13. Choose the subcollection.
14. Open the full text only if needed.
15. Assign confidence.
16. Write rationale.
17. Flag ambiguity or taxonomy gap if present.
18. Submit for QA or finalize.

---

## 7. Recommended classification time standard

These are practical operating targets, not hard laws.

### Expected handling time per paper

- **Simple paper** (clear title + abstract): 5–8 minutes
- **Standard paper**: 8–12 minutes
- **Ambiguous / interdisciplinary paper**: 12–20 minutes
- **Hard adjudication case**: 15–30 minutes

For staffing and SLA planning, assume an average of **10–12 minutes per paper** in a mature operation.

---

## 8. Escalation triggers

Escalate a paper when any of the following occur:

- the best Level 1 fit is uncertain,
- the correct subcollection is unclear,
- two subcollections appear equally valid,
- the paper exposes a taxonomy gap,
- the paper is poorly described and metadata is insufficient,
- the paper appears mis-ingested or duplicated,
- the classifier believes current rules are internally inconsistent.

---

## 9. Example paper classification record template

Copy and fill this per paper.

```md
# Paper Classification Record

- Paper ID:
- Title:
- Authors:
- Year:
- Source / Venue:
- DOI / URL:
- Abstract available: Yes / No
- Full text reviewed: Yes / No

## Scope check
- In corpus scope: Yes / No
- If no, reason:

## Content summary
- One-sentence paraphrase:
- Primary contribution type:
- Problem addressed:
- Method / approach:
- Application domain (if any):

## Classification decision
- Main collection:
- Subcollection:
- Confidence: High / Medium / Low
- Decision basis: Title / Abstract / Intro / Method / Full text

## Rationale
- Why this main collection:
- Why this subcollection:
- Neighboring categories considered:
- Why those were rejected:

## Flags
- Needs review: Yes / No
- Review reason:
- Taxonomy gap: Yes / No
- Duplicate suspected: Yes / No

## Audit trail
- Classifier:
- Date:
- Taxonomy version:
- Adjudicator (if any):
- Final disposition:
```

---

## 10. Example batch QA template

```md
# Batch QA Log

- Batch ID:
- Taxonomy version:
- QA reviewer:
- Review date:

## Sample reviewed
- Total papers in batch:
- Papers sampled for QA:
- Sampling method: Random / Risk-based / 100% flagged cases

## Error summary
- Wrong main collection:
- Wrong subcollection:
- Missing rationale:
- Confidence mismatch:
- Metadata issue:
- Duplicate issue:

## Root causes
- Definition unclear:
- Training gap:
- Metadata incomplete:
- Paper inherently ambiguous:
- UI / workflow issue:

## Actions
- Taxonomy update needed:
- New edge-case example needed:
- Classifier retraining needed:
- Tooling fix needed:
```

---

## 11. Acceptance criteria for a finished classification system

A production-ready classification process should satisfy all of the following:

- Every paper can be assigned to one valid Level 1 and one valid Level 2 node.
- Definitions are specific enough to reduce overlap.
- Borderline cases have written decision rules.
- Every classifier uses the same evidence order.
- QA is formal, not ad hoc.
- Edge cases produce documented precedent.
- Taxonomy changes are versioned.
- Audit data can reveal where the taxonomy or process is failing.

---

## 12. Recommended operating policy summary

If you need a compact policy statement, use this.

```md
Each paper must be assigned to one primary main collection and one primary subcollection based on its primary intellectual contribution. Classifiers must use the taxonomy reference document, apply the evidence hierarchy of title → abstract → introduction → methods → experiments → conclusion, record confidence and rationale, and escalate ambiguity rather than forcing certainty. Low-confidence and taxonomy-gap cases must be adjudicated and converted into reusable precedent.
```

---

## 13. Suggested implementation sequence for a new program

If you are starting from zero, use this rollout order.

### Week 1
- Draft the two-layer taxonomy
- Write definitions and boundary rules
- Create the reference document

### Week 2
- Build the intake sheet and classification form
- Assemble pilot team
- Create training set of 100–300 papers

### Week 3
- Run calibration exercise
- Refine ambiguous categories
- Freeze taxonomy version 1

### Week 4
- Start pilot production
- Audit first 10–20% of output
- Capture edge cases and precedents

### Week 5+
- Move to steady-state production
- Review metrics weekly
- Update taxonomy only through versioned governance

---

## 14. Final note

A classification workflow succeeds when it optimizes **consistency, explainability, and maintainability**. A two-layer taxonomy is simple enough to operate efficiently, but only if the team has explicit rules for boundary cases and a strong taxonomy reference document.
