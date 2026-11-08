"""Run the installed docling-core rich-reference regression, without model inference.

The independently reported mechanism and minimal reproduction come from:
https://github.com/docling-project/docling-core/pull/986 (MIT).
The PDF, text choices, and explicit source geometry are our generated fixture.
This is a real library reproducer, NOT a harvested real-world PDF.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import platform
from pathlib import Path

from benchmarks.common import HEIGHT, ROOT, WIDTH, bbox, draw_pdf, manifest_case, sha256, write_json

AFFECTED = "3e3be95e9de7472e78da2068ae2b281e4dd34611"
FIXED = "bef3c28565c623537d0723b0d3d04f5af8d56c41"
PAGES = [[["AAA", "12.5 mg"]], [["BBB", "20.0 mg"], ["CCC", "30.0 mg"]]]


def reproduce(variant: str) -> dict:
    from docling_core.types.doc import DoclingDocument
    from docling_core.types.doc.base import BoundingBox, Size
    from docling_core.types.doc.document import ProvenanceItem
    from docling_core.types.doc.items.table.table_data import RichTableCell, TableCell, TableData
    from docling_core.types.doc.labels import DocItemLabel, GroupLabel

    expected_commit = AFFECTED
    dist = importlib.metadata.distribution("docling-core")
    direct_url = json.loads(dist.read_text("direct_url.json") or "{}")
    if expected_commit not in json.dumps(direct_url):
        raise RuntimeError(f"Install docling-core from commit {expected_commit}; got {direct_url}")
    docs = []
    for index, rows in enumerate(PAGES):
        doc = DoclingDocument(name=f"page-{index + 1}")
        doc.add_page(page_no=1, size=Size(width=WIDTH, height=HEIGHT))
        table = doc.add_table(data=TableData(num_rows=len(rows), num_cols=2))
        table.prov = [
            ProvenanceItem(page_no=1, charspan=(0, 0), bbox=BoundingBox(**bbox(0, 0, len(rows), 2)))
        ]
        for row, values in enumerate(rows):
            group = doc.add_group(label=GroupLabel.UNSPECIFIED, parent=table)
            doc.add_text(parent=group, text=values[0], label=DocItemLabel.TEXT)
            for col, text in enumerate(values):
                kwargs = dict(
                    text=text,
                    start_row_offset_idx=row,
                    end_row_offset_idx=row + 1,
                    start_col_offset_idx=col,
                    end_col_offset_idx=col + 1,
                    bbox=BoundingBox(**bbox(row, col)),
                    row_header=col == 0,
                )
                cell = (
                    RichTableCell(ref=group.get_ref(), **kwargs)
                    if col == 0
                    else TableCell(**kwargs)
                )
                doc.add_table_cell(table_item=table, cell=cell)
        docs.append(doc)
    merged = DoclingDocument.concatenate(docs=docs)
    resolved = []
    errors = []
    for table_index, table in enumerate(merged.tables):
        actual = []
        for cell in table.data.table_cells:
            text = cell.text
            if isinstance(cell, RichTableCell):
                text = " ".join(
                    child.resolve(merged).text for child in cell.ref.resolve(merged).children
                )
            actual.append(text)
            expected = PAGES[table_index][cell.start_row_offset_idx][cell.start_col_offset_idx]
            if text != expected:
                errors.append(
                    {
                        "table_index": table_index,
                        "row": cell.start_row_offset_idx,
                        "col": cell.start_col_offset_idx,
                        "type": "wrong_row_association",
                        "expected": expected,
                        "observed": text,
                    }
                )
        resolved.append(actual)
    if (variant == "affected" and len(errors) != 2) or (variant == "fixed" and errors):
        raise RuntimeError(f"Unexpected upstream behavior; variant={variant}, errors={errors}")
    out = ROOT / "fixtures" / "docling_5198"
    source = out / "source.pdf"
    draw_pdf(source, PAGES)
    extracted = out / f"{variant}.json"
    write_json(extracted, merged.export_to_dict())
    (out / f"{variant}.md").write_text(merged.export_to_markdown() + "\n")
    module = Path(__import__("docling_core.types.doc.document", fromlist=["_"]).__file__)
    metadata = {
        "source_issue": "https://github.com/docling-project/docling/issues/5198",
        "source_reproducer": "https://github.com/docling-project/docling-core/pull/986",
        "upstream_license": "MIT",
        "fixture_license": "MIT",
        "upstream_commit": expected_commit,
        "package_version": dist.version,
        "package_direct_url": direct_url,
        "document_module_sha256": sha256(module),
        "python": platform.python_version(),
        "resolved_cells": resolved,
        "provenance_note": "Generated PDF and explicit boxes from known fixture geometry. "
        "Actual installed Docling concatenate output; no model inference. "
        "This is not the private invoice from the original report.",
    }
    if variant == "fixed":
        patch_record = ROOT / "fixtures" / "docling_5198" / "applied_fix.json"
        record = json.loads(patch_record.read_text())
        if record["patched_module_sha256"] != sha256(module):
            raise RuntimeError("The installed module does not match the recorded controlled patch")
        metadata["controlled_patch"] = record
    case = manifest_case(
        f"docling-5198-{variant}",
        "real_library_reproducer",
        source,
        extracted,
        errors,
        metadata=metadata,
    )
    write_json(out / f"{variant}.manifest.json", case)
    return case


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", choices=["affected", "fixed"], required=True)
    print(json.dumps(reproduce(parser.parse_args().variant), indent=2))
