"""Run real Docling models with a pinned parser and compare Table 2 with visual gold."""

from __future__ import annotations

import argparse
import importlib.metadata
import platform
import re
from pathlib import Path

from benchmarks.common import ROOT, manifest_case, sha256, write_json

OUT = ROOT / "fixtures" / "docling_5136"
MODEL_REVISIONS = {
    "docling-project/docling-layout-heron": "8f39ad3c0b4c58e9c2d2c84a38465abf757272d8",
    "docling-project/docling-models": "fc0f2d45e2218ea24bce5045f58a389aed16dc23",
}
GOLD_ROWS = [
    [
        "Treatment (delivery)",
        "N",
        "An. gambiae s.l.",
        "An. funestus",
        "Culex spp.",
        "Mansonia spp.",
        "Aedes spp.",
        "Other spp.",
    ],
    ["Empty (control)", "40", "0.65 a", "0.55 a", "2.28 a", "0.25 a", "0.10 a", "0.43 a"],
    ["IB1 (LDPE)", "40", "1.30 b", "0.53 a", "1.85 a", "0.53 b", "0.15 ab", "0.43 a"],
    ["IB1 (nylon strips)", "40", "1.43 b", "1.15 b", "2.98 b", "0.55 b", "0.13 a", "0.58 b"],
    ["SB (LDPE)", "40", "1.05 b", "0.58 a", "2.48 a", "0.33 ab", "0.25 a", "0.38 a"],
    ["SB (nylon strips)", "40", "1.03 b", "1.73 c", "1.88 a", "0.60 b", "0.38 b", "0.40 a"],
    ["MB (LDPE)", "40", "1.03 b", "0.58 a", "2.15 a", "0.55 b", "0.08 a", "0.83 c"],
    ["Total mosquito catches (n)", "", "259", "207", "544", "112", "43", "121"],
]


def reproduce(parser_version: str, full_page: bool = False) -> dict:
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import (
        AcceleratorOptions,
        PdfPipelineOptions,
        TableStructureOptions,
    )
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from huggingface_hub import snapshot_download

    if importlib.metadata.version("docling-parse") != parser_version:
        raise RuntimeError(f"Install docling-parse=={parser_version} first")
    if importlib.metadata.version("docling") != "2.145.0":
        raise RuntimeError("This reproducer needs docling==2.145.0")
    artifacts = ROOT / "downloads" / "docling-models"
    artifacts.mkdir(parents=True, exist_ok=True)
    weights = {}
    for repo, revision in MODEL_REVISIONS.items():
        snapshot = Path(snapshot_download(repo_id=repo, revision=revision))
        link = artifacts / repo.replace("/", "--")
        if link.exists() and link.resolve() != snapshot.resolve():
            raise RuntimeError(f"Different cached model at {link}")
        if not link.exists():
            link.symlink_to(snapshot, target_is_directory=True)
        weights[repo] = {
            "revision": revision,
            "files": {
                str(path.relative_to(snapshot)): sha256(path)
                for path in sorted(snapshot.rglob("*"))
                if path.is_file() and path.suffix in {".safetensors", ".json"}
            },
        }
    options = PdfPipelineOptions(do_ocr=False, artifacts_path=artifacts)
    options.table_structure_options = TableStructureOptions(do_cell_matching=False)
    options.accelerator_options = AcceleratorOptions(device="cpu", num_threads=4)
    converter = DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)}
    )
    source = OUT / ("page6.pdf" if full_page else "table2.pdf")
    prefix = "page6" if full_page else "table2"
    result = converter.convert(source)
    extracted = OUT / f"{prefix}-{parser_version}.json"
    write_json(extracted, result.document.export_to_dict())
    (OUT / f"{prefix}-{parser_version}.md").write_text(result.document.export_to_markdown() + "\n")
    packages = {
        name: importlib.metadata.version(name)
        for name in (
            "docling",
            "docling-core",
            "docling-parse",
            "docling-ibm-models",
            "torch",
            "transformers",
        )
    }
    metadata = {
        "source_issue": "https://github.com/docling-project/docling/issues/5136",
        "source_record": "fixtures/docling_5136/source.json",
        "package_versions": packages,
        "source_pdf": str(source.relative_to(ROOT)),
        "source_sha256": sha256(source),
        "extracted_json": str(extracted.relative_to(ROOT)),
        "extracted_sha256": sha256(extracted),
        "models": weights,
        "python": platform.python_version(),
        "pipeline": {
            "do_ocr": False,
            "do_cell_matching": False,
            "device": "cpu",
            "num_threads": 4,
            "status": result.status.value,
            "table_mode": options.table_structure_options.mode.value,
        },
        "gold_annotation": (
            "AI-assisted visual transcription of Table 2, not independent human gold. "
            "A second AI visual pass confirms the header and first data row. "
            "Superscript significance letters remain part of cell text."
        ),
        "normalization": "Ignore whitespace only when comparing extracted text with visual gold.",
        "source_license": "CC-BY-2.0",
        "output_note": "Actual Docling model output. No cell text or geometry repaired.",
        "independence_note": "Both parser versions share one source table and model weights.",
    }
    write_json(OUT / f"{prefix}-{parser_version}.runtime.json", metadata)
    if full_page:
        print(f"Saved complete page output with {len(result.document.tables)} tables.")
        return metadata
    write_json(
        OUT / "gold.json",
        {
            "rows": GOLD_ROWS,
            "annotation": metadata["gold_annotation"],
            "normalization": metadata["normalization"],
        },
    )
    errors = []
    if len(result.document.tables) != 1:
        errors.append(
            {"type": "table_count_mismatch", "expected": 1, "observed": len(result.document.tables)}
        )
    for table_index, table in enumerate(result.document.tables[:1]):
        actual = [[cell.text for cell in row] for row in table.data.grid]
        if (table.data.num_rows, table.data.num_cols) != (8, 8):
            errors.append(
                {
                    "type": "table_shape_mismatch",
                    "expected": [8, 8],
                    "observed": [table.data.num_rows, table.data.num_cols],
                }
            )
        for row, values in enumerate(GOLD_ROWS):
            for col, expected in enumerate(values):
                observed = (
                    actual[row][col] if row < len(actual) and col < len(actual[row]) else None
                )
                if observed is None or re.sub(r"\s", "", expected) != re.sub(r"\s", "", observed):
                    errors.append(
                        {
                            "table_index": table_index,
                            "row": row,
                            "col": col,
                            "type": "missing_cell_text" if not observed else "cell_text_mismatch",
                            "expected": expected,
                            "observed": observed,
                        }
                    )
    case = manifest_case(
        f"docling-5136-parse-{parser_version}",
        "real_source_pdf",
        source,
        extracted,
        errors,
        metadata=metadata,
    )
    write_json(OUT / f"{prefix}-{parser_version}.manifest.json", case)
    print(
        f"Saved actual output: {len(result.document.tables)} tables, {len(errors)} gold mismatches."
    )
    return case


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parser-version", choices=["7.24.2", "7.20.0"], required=True)
    parser.add_argument("--full-page", action="store_true")
    args = parser.parse_args()
    reproduce(args.parser_version, args.full_page)
