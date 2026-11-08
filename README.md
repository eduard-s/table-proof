# TableProof

[![CI](https://github.com/eduard-s/table-proof/actions/workflows/ci.yml/badge.svg)](https://github.com/eduard-s/table-proof/actions/workflows/ci.yml)

TableProof finds suspected errors in extracted PDF tables. It compares cell text and row or column positions with source evidence.

Every number can survive extraction while its row label changes. TableProof reports the disputed cell and its original PDF region.

This is an alpha Python library. It needs Python 3.11 or later.

## Installation

```sh
python -m pip install table-proof
table-proof source.pdf docling-export.json --html report.html --json report.json
```

`docling-export.json` is a Docling document export with table cells and source coordinates.

For the optional local vision model, install the extra dependencies:

```sh
python -m pip install 'table-proof[vision]'
```

## Try the real regression case

The recorded regression pair contains this error:

| Source row | Affected extracted row | Result |
| --- | --- | --- |
| `BBB → 20.0 mg` | `CCC → 20.0 mg` | Row label differs from the source region. |
| `CCC → 30.0 mg` | `BBB → 30.0 mg` | Row label differs from the source region. |

The regression fixtures are in the source repository. Run these commands:

```sh
git clone https://github.com/eduard-s/table-proof.git
cd table-proof
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/table-proof \
  benchmarks/fixtures/docling_5198/source.pdf \
  benchmarks/fixtures/docling_5198/affected.json \
  --html report.html --json report.json
```

The command exits with code `1`. It reports two swapped row labels in the affected fixture.

Replace `affected.json` with `fixed.json` to examine the paired control. That command exits with code `0`.

The fixture reproduces a real Docling defect on a generated PDF. It does not represent an independent production document.

Read the [benchmark results](https://github.com/eduard-s/table-proof/blob/main/benchmarks/results.md) and [fixture provenance](https://github.com/eduard-s/table-proof/blob/main/benchmarks/README.md).

## Python API

```python
import json
from pathlib import Path

from table_proof import audit_tables

fixture = Path("benchmarks/fixtures/docling_5198")
document = json.loads((fixture / "affected.json").read_text())
report = audit_tables(fixture / "source.pdf", document)

print(report.status)
report.export_json("report.json")
report.export_html("report.html", source_pdf=str(fixture / "source.pdf"))
```

The adapter accepts Docling JSON, a `DoclingDocument`, or a conversion result with a `document` field. Docling is optional at runtime.

Rich cells can contain text references. The adapter resolves the references that control the rendered table. It does not trust stale cell text.

## What the MVP does

- Compares cell tokens with PDF words in the cell region.
- Detects reversed row or column positions and invalid cell spans.
- Reports missing source text, incomplete geometry, and ambiguous word assignments.
- Produces JSON findings and local HTML evidence.
- Preserves the source PDF and extraction.
- Supports an optional, pinned Table Transformer model for independent structure evidence.

The default path uses PDF text and geometry. It makes no network requests.

The optional model runs locally. It needs an explicit download option before its first use. Read the [vision guide](https://github.com/eduard-s/table-proof/blob/main/docs/VISION.md).

## Results and limits

| Status | Meaning | CLI exit code |
| --- | --- | --- |
| `no_findings` | The selected checks found no error in the supplied evidence. | `0` |
| `review` | At least one check found a suspected error. | `1` |
| `uncertain` | Evidence is missing, ambiguous, or unsupported. | `3` |
| `error` | The command did not process the input. | `2` |

`no_findings` does not prove semantic accuracy. An empty table list returns `uncertain`.

Start with digital PDFs and tables that occupy one page. Scans and multi-page tables need other methods.

The tool does not certify units or source facts. It does not repair data automatically. Detector scores are not calibrated error probabilities.

The [small development benchmark](https://github.com/eduard-s/table-proof/blob/main/benchmarks/results.md) compares TableProof with local controls and pinned upstream pdfmux code.
Its cases establish a reproducible regression result. They do not establish broad superiority on real documents.

On the included public paper, TableProof flags six missing headers. It returns uncertainty for a clipped superscript in another parser output.

The optional vision model recovers the table grid but adds no error detection on that public example.
Read the [recorded model results](https://github.com/eduard-s/table-proof/blob/main/docs/VISION.md) before a model accuracy claim.

## Development

```sh
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy src/table_proof
.venv/bin/pytest --cov=table_proof --cov-report=term-missing
.venv/bin/python -m build
.venv/bin/python -m twine check dist/*
```

Use Python 3.12 for the type analysis. CI runs tests on Python 3.11 through 3.14.

## Documents

- [MVP plan and acceptance criteria](https://github.com/eduard-s/table-proof/blob/main/docs/MVP_PLAN.md)
- [Architecture and Python stack](https://github.com/eduard-s/table-proof/blob/main/docs/ARCHITECTURE.md)
- [API and report contract](https://github.com/eduard-s/table-proof/blob/main/docs/API.md)
- [Datasets and evaluation plan](https://github.com/eduard-s/table-proof/blob/main/docs/DATASETS.md)
- [Benchmark reproduction](https://github.com/eduard-s/table-proof/blob/main/benchmarks/README.md)
- [Optional vision model](https://github.com/eduard-s/table-proof/blob/main/docs/VISION.md)
- [Development and contribution](https://github.com/eduard-s/table-proof/blob/main/CONTRIBUTING.md)
- [Release instructions](https://github.com/eduard-s/table-proof/blob/main/PUBLISHING.md)

## License

MIT. See [LICENSE](https://github.com/eduard-s/table-proof/blob/main/LICENSE) and [third-party notices](https://github.com/eduard-s/table-proof/blob/main/THIRD_PARTY.md).
