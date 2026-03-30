# Output examples

Read this file when you want a concrete artifact shape before producing classification records.

## Example 1 — straightforward classification

```yaml
paper_id: smith-2024-ppg-quality
paper_title: "Signal Quality Assessment for Wearable PPG Under Motion"
task_type: proposed
taxonomy_version: 2026-Q1
decision_status: accepted
main_collection: Biosignals
subcollection: PPG signal quality assessment
confidence: High
primary_evidence:
  - "Abstract frames the core task as assessing PPG signal quality under motion corruption."
  - "Methods section centers on signal quality scoring rather than downstream diagnosis."
secondary_evidence:
  - "Evaluation compares quality labels and quality-detection baselines."
strongest_rejected_alternative: "Clinical Monitoring · Wearable monitoring"
rationale: "The paper's primary intellectual contribution is quality assessment methodology for PPG, not deployment of a monitoring system."
flags: []
escalation_reason: none
next_owner: none
```

## Example 2 — escalation / taxonomy-gap case

```yaml
paper_id: lee-2025-multimodal-benchmark
paper_title: "A Multimodal Benchmark Repository for ICU PPG, ECG, ABP, and Waveform Tasks"
task_type: audit
taxonomy_version: 2026-Q1
decision_status: taxonomy_gap
main_collection: Biosignals
subcollection: none
confidence: Low
primary_evidence:
  - "The paper's central contribution is a benchmark repository spanning several modalities and tasks."
  - "No existing subcollection cleanly captures multimodal benchmark-repository work."
secondary_evidence:
  - "Downstream tasks are presented as demonstrations rather than the main contribution."
strongest_rejected_alternative: "Biosignals · PPG benchmark datasets"
rationale: "That alternative is close, but it is too narrow because the repository is explicitly multimodal and not primarily a PPG-only benchmark."
flags:
  - new_bucket_candidate
  - boundary_conflict
escalation_reason: "Existing Level 2 nodes do not cleanly separate modality-specific benchmark datasets from broader multimodal repositories."
next_owner: taxonomy_lead
```

## Notes

- Keep one record per paper.
- Use the same keys in the same order when possible.
- If there is no meaningful competing path, set `strongest_rejected_alternative` to `none`.
- For multi-paper jobs, place any cross-paper observations after the per-paper records rather than mixing them into each rationale.
