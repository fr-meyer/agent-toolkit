# Taxonomy-creation output examples

Read this file when taxonomy-creation-first mode needs a concrete deliverable shape before production classification begins.

## Example 1 — taxonomy charter

```md
# Taxonomy Charter
Version: draft-v0.1
Owner: Taxonomy Lead
Date: 2026-03-30
Mission: Create a stable two-layer taxonomy for cardiovascular ML papers so the corpus can be classified consistently for retrieval and QA.
Primary use case: paper classification and browsing
In-scope corpus: research papers on cardiovascular machine learning and related biosignal analysis
Out-of-scope corpus: patents, product brochures, and non-paper clinical documents
Governing classification basis: primary intellectual contribution
Success criteria:
- most in-scope pilot papers fit the tree without forced placement
- major boundary conflicts are reduced to a small known set
Approval authority: Program Lead
```

## Example 2 — label definition card

```md
# Label Definition Card
Label ID: biosignals.ppg-quality
Label Name: PPG signal quality assessment
Parent Label: Biosignals
Definition: Papers whose central contribution is assessing, scoring, or modeling the quality of PPG signals.
What belongs:
- signal quality indices for PPG
- quality detection or corruption detection for PPG streams
What does not belong:
- downstream diagnosis papers that merely mention quality filtering
- generic wearable monitoring papers whose main contribution is deployment or operations
Inclusion cues:
- explicit focus on signal quality, artifacts, or corruption detection
Exclusion cues:
- diagnosis or monitoring is the main stated objective
Closest confusing alternative: Clinical Monitoring · Wearable monitoring
Positive examples:
- motion-artifact quality scoring for wrist PPG
Negative examples:
- wearable arrhythmia detection pipeline with minor PPG cleaning step
Notes:
- if the contribution is a multimodal repository rather than PPG-only quality assessment, test benchmark/dataset nodes before assigning here
```

## Example 3 — locked-version handoff summary

```md
# Locked Taxonomy Handoff Summary
Taxonomy version: v1.0
Effective date: 2026-03-30
Governing basis: primary intellectual contribution
Level 1 count: 8
Level 2 count: 34
Pilot size: 100 papers
Readiness decision: approved with minor clarification notes
Known boundary pairs to watch:
- Biosignals · PPG signal quality assessment vs Clinical Monitoring · Wearable monitoring
- Methods · Benchmark datasets vs Biosignals · Multimodal physiological repositories
Open issues:
- one candidate taxonomy gap remains under review for multimodal benchmark repositories
Batch rule:
- all production classification in the current batch must use taxonomy version v1.0 only
```

## Notes

- Use these shapes only when the task is taxonomy-creation-first in service of later paper classification.
- Keep taxonomy deliverables tied to a research-paper corpus and a locked classification version.
- Do not use these examples as a template for arbitrary ontology design outside this skill's scope.
