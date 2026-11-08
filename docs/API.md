# API and report contract

## Audit

```python
from table_proof import AuditConfig, audit_tables

report = audit_tables(
    source_pdf="source.pdf",
    extracted_document=docling_document,
    config=AuditConfig(geometry_tolerance=1.0, min_word_overlap=0.8),
)
```

`source_pdf` accepts a string or `Path`. `extracted_document` accepts Docling JSON, a Docling object, or a sequence of normalized `Table` objects.

The API reads the source and returns an `AuditReport`. It does not change either input.

Invalid documents raise an exception. The CLI converts exceptions to an error message and exit code `2`.

## Normalized coordinates

`BBox` uses PDF points with a top-left origin. Its fields are `x0`, `top`, `x1`, and `bottom`.

Page numbers start at one. Row and column offsets start at zero. Spans contain at least one row or column.

Each cell has an identifier, text, offsets, spans, and optional geometry. A missing box prevents a complete source comparison.

## Findings

Each finding contains these fields:

| Field | Meaning |
| --- | --- |
| `code` | Stable machine-readable category |
| `severity` | `error` or `uncertain` |
| `table_id`, `page`, `cell_id` | Evidence location |
| `message` | Short explanation |
| `expected_text` | Source evidence, when available |
| `observed_text` | Extracted value, when available |
| `bbox` | Source region, when available |
| `evidence` | Method that produced the finding |

An error finding requests review. It is not an automatic correction.

## Status precedence

An error finding produces `review`. Missing or ambiguous evidence produces `uncertain` when no error finding exists.

`no_findings` means that the selected checks found no error. It does not mean that the document is correct.

The report returns `uncertain` when no tables exist. An empty extraction cannot establish source coverage.

## Exports

```python
report.export_json("report.json")
report.export_html("report.html", source_pdf="source.pdf")
```

JSON export includes the aggregate status. HTML export can include source images when the supplied PDF hash matches the report.

The [JSON Schema](../spec/report-v1.schema.json) describes the exported report.

The HTML report shows at most ten source pages. The JSON report keeps every finding.

Output parent directories must exist. The CLI refuses report paths that replace its input files.

## Version policy

The report schema starts at `1.0`. The library version starts at `0.1.0`.

During the alpha stage, field or behavior changes need release notes. Preserve old benchmark artifacts when behavior changes.
