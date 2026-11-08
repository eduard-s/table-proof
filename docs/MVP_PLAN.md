# MVP plan

## User and problem

The first user is a Python developer with a PDF extraction pipeline. A successful conversion can contain incorrect cell associations.

The user needs a short evidence report before data enters a database or AI retrieval system.

## Current implementation

| Deliverable | State | Evidence |
| --- | --- | --- |
| Python API and CLI | Implemented | API and command tests |
| Docling adapter | Implemented | Coordinate and rich-reference tests |
| Source geometry audit | Implemented | Unit, property, and PDF tests |
| Local HTML evidence | Implemented | Escaping, hash, and image tests |
| Optional model inference | Implemented | Vision tests and recorded smoke run |
| Real library regression pair | Implemented | Pinned upstream reproduction |
| Existing-tool comparison | Implemented | Pinned pdfmux audit results |
| Broad real-document accuracy | Not established | Independent corpus needed |
| Model calibration | Not established | Labeled development set needed |
| Repeat use by external teams | Not established | Pilot evidence needed |
| PyPI publication | Deferred | Separate release round |

## Stage 1: reproducible alpha

The current repository covers this stage.

1. Reproduce a real upstream defect at an exact commit.
2. Apply the isolated upstream fix to create a paired control.
3. Preserve the source, outputs, labels, versions, and hashes.
4. Compare the audit with simple controls and one real upstream tool.
5. Run the unit, property, integration, and distribution tests.

Acceptance needs a detected affected case and an unflagged fixed control. Missing evidence must produce uncertainty.

This result establishes a specific capability. It does not establish population accuracy.

## Stage 2: independent real-document evaluation

Target 50 independent PDFs across at least five layout families. Include at least 200 tables.

Reserve at least 20 PDFs before threshold selection. Keep every table from one PDF in the same partition.

1. Record each source license and retrieval hash.
2. Capture unchanged parser outputs at pinned versions.
3. Label cell associations against the original page.
4. Ask a second reviewer to examine every disputed association.
5. Freeze the labels before the final comparison.
6. Run all methods on the same cases.
7. Publish failed runs and uncertain results.

These counts are collection targets. The repository does not claim that this corpus already exists.

## Stage 3: comparative acceptance

Use these proposed thresholds before a broad accuracy claim:

- At least 95% precision for flagged cell associations.
- At least 80% recall for incorrect associations in the supported scope.
- At most 5% of clean tables receive an error flag.
- At most 20% of supported tables receive an uncertain result.

Report intervals from document-level resampling. A point estimate alone does not satisfy the comparative claim.

Compare recall at matched precision and abstention. Report paired differences against each baseline.

Run geometry-only, vision-only, and combined ablations. Keep model inference time separate from PDF parsing time.

If the model adds cost without a measured benefit, keep it optional.

## Stage 4: pilot use

Ask three independent teams to run the audit on documents they already process. Keep confidential documents in their environment.

Record false alarms, missed errors, review time, and repeat use. Expand support only after a repeated user need.

## Scope limits

The first scope covers digital PDFs and single-page tables. It excludes automatic repairs and universal semantic certification.

Multi-page tables, scans, unit inference, and broad format adapters are later work. Each needs separate fixtures and acceptance criteria.
