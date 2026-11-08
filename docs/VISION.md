# Optional source-image inspection

The vision option runs a pretrained Table Transformer on the source PDF image.
It compares detected rows, columns, merged regions, and column headers with the exported cells.
It does not send PDF content to a hosted inference service.

The default audit does not import PyTorch or download model files.
Vision also stays offline unless you explicitly permit a model download.

## Install and use

From the repository root:

```bash
python -m pip install -e '.[vision]'
```

The first model download needs explicit permission:

```python
from pathlib import Path

from table_proof.vision import VisionConfig, inspect_table

# `table` is a normalized table_proof.models.Table.
findings = inspect_table(
    Path("source.pdf"),
    table,
    config=VisionConfig(allow_download=True),
)
```

For later runs, omit `config`. The loader then uses cached files only.
A missing model or dependency produces an `uncertain` finding.
It never becomes a successful inspection.

Use `VisionConfig(cache_dir=Path("model-cache"))` for a separate cache.
The download option permits checkpoint retrieval. Inference still runs on the local CPU.

## Fixed model and preprocessing

The model is
[`microsoft/table-transformer-structure-recognition-v1.1-all`](https://huggingface.co/microsoft/table-transformer-structure-recognition-v1.1-all).
The fixed revision is `7587a7ef111d9dcbf8ac695f1376ab7014340a0c`.
The loader needs safetensors and sets `trust_remote_code=False`.
It disables a separate pretrained-backbone download.

The model card identifies training on PubTables-1M and FinTabNet.c.
See the [original Table Transformer project](https://github.com/microsoft/table-transformer).

The default render uses 144 DPI and eight PDF points of padding.
The processor preserves aspect ratio and sets the longer image side to 1,000 pixels.
Both processor size keys are explicit because the checkpoint stores only `longest_edge`.
Transformers 4.x needs both size keys for this processor.

Output boxes first map to the actual rendered crop dimensions.
The code then maps each axis separately to top-left PDF points.
This preserves crop offsets and accommodates render rounding.
For a nonzero PDF page origin, only the renderer input uses the raw page offset.
Returned boxes keep the normalized top-left origin.

The comparison uses predictions with scores of at least 0.8.
Predictions between 0.35 and 0.8 can make the grid uncertain.
These are model scores, not calibrated probabilities of a correct extraction.

## What the result means

`vision_cell_relation_mismatch` identifies a position or span disagreement.
`vision_column_header_mismatch` identifies a column-header flag disagreement.
These findings request source review. A model prediction does not prove an error.

The inspection returns `uncertain` when row or column counts differ.
It also abstains on overlapping regions, missing boxes, unsupported pages, and ambiguous merged cells.
Without reliable column-header evidence, a declared column header remains uncertain.

Table Transformer's projected row headers are section labels.
They are not equivalent to every ordinary row header.
The current comparison does not assess the exported `row_header` flag.

The model receives source pixels only. It does not receive exported cell text or indices.
It therefore supplies separate structural evidence, but it does not supply independent ground truth.
Models trained on related document collections can share errors.

The scope is a bounded table crop on one unrotated digital PDF page.
Rotated pages and empty exports are unsupported.
The model does not establish correct text, units, signs, arithmetic, or semantic claims.
It cannot find an omitted table outside the supplied crop.
An incorrect exported bounding box can also limit detection.
Scans, cross-page tables, and domain-specific accuracy need separate evaluation.
The code never edits exported data.

## Reproduce the real-model smoke run

From a source checkout, install the vision and development extras.
Then run:

```bash
python scripts/vision_smoke.py --allow-download
python scripts/vision_smoke.py
```

The second command uses the local cache.
The script creates a synthetic PDF and writes a JSON evidence record under
`/tmp/table-proof-vision-smoke/`. Use `--output PATH` for another directory.
The record includes model revision, dependency versions, image dimensions, region scores, and findings.

Recorded run on 8 November 2026:

| Item | Observed value |
| --- | --- |
| Python | 3.13.11 |
| Platform | macOS 26.6.2, ARM64 |
| Device | CPU |
| PyTorch | 2.15.0 |
| Transformers | 4.57.6 |
| timm | 1.0.31 |
| pdfplumber | 0.11.10 |
| Rendered crop | 968 × 392 pixels |
| Crop in PDF points | `(64, 92, 548, 288)` |
| Detected structure | 5 rows, 4 columns, 1 column-header region, 1 table |
| Inference and postprocessing | 0.109 seconds |
| Total with cached model load | 1.787 seconds |
| Clean export | No vision findings |
| Changed column index | One relation mismatch at cell `r1c2` |

The changed export preserves all text and source boxes.
It changes only the cell's column index from 2 to 1.
The model recovers `(row=1, col=2, row_span=1, col_span=1)` from source-image structure.
The model run uses real checkpoint weights. It does not mock predictions.

The [recorded JSON evidence](assets/vision-smoke.json) contains all detected regions and scores.
It contains no local absolute paths or private source images.

This single synthetic example shows execution and one detected mutation.
It does not measure real-document accuracy, false alarm rate, or reviewer time.
The unit tests separately exercise coordinate transforms, header flags, spans, and abstention.
They do not download weights.

For the recorded runtime versions:

```bash
python -m pip install 'torch==2.15.0' 'transformers==4.57.6' 'timm==1.0.31'
```

Hardware, package versions, and thread settings affect runtime.
Future evaluation needs public source tables, natural extraction errors, clean controls, and human labels.

## Real-source case: missing headers

The [real-source evidence record](assets/vision-docling-5136.json) covers the top table on original page 6
of the public paper used for [Docling issue 5136](https://github.com/docling-project/docling/issues/5136).
The printed label is Table 2. The run uses the unchanged Docling output with `docling-parse` 7.24.2.
The record contains relative file paths and source hashes.

This run selects one of the two tables on the page. It uses the default model thresholds.
The model finds eight rows, eight columns, and one column-header region.
These counts match the exported grid, so the vision comparison produces no findings.

The geometry audit reports six missing header texts, one ambiguous word assignment,
and one uncertain text normalization.
The structural model does not detect the missing texts.
Thus, vision adds no detected error for this case.

The stored geometry result uses the revised source-word reader and bracket-token handling.
The original model outputs and measured runtime remain unchanged.

The rendered crop is 1,022 × 269 pixels.
CPU inference and postprocessing take 0.251 seconds.
The total with cached model loading is 2.851 seconds.
The software versions match the synthetic run recorded earlier.

Source-image transcription for this case is AI-assisted.
It is not independent human adjudication.
This result is a separate example, not a broad accuracy estimate or a tuned model comparison.
