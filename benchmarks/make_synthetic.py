"""Make explicit positive, negative, and unsupported controls, separate from real bugs."""

from __future__ import annotations

import copy
from typing import Any

from benchmarks.common import ROOT, draw_pdf, manifest_case, table_document, write_json

ROWS = [
    ["Sample", "Dose (mg)", "Volume (ml)"],
    ["Alpha", "12.5", "3.0"],
    ["Beta", "20.0", "4.0"],
    ["Gamma", "30.0", "5.0"],
]


def generate() -> list[dict[str, Any]]:
    out = ROOT / "fixtures" / "synthetic"
    cases = []

    def add(
        name: str,
        rows: list[list[str]],
        mutations: dict[tuple[int, int], str],
        *,
        missing_geometry: bool = False,
        no_tables: bool = False,
        merged: bool = False,
        scanned: bool = False,
    ) -> None:
        source = out / f"{name}.pdf"
        draw_pdf(source, [rows], merged_header=merged)
        if scanned:
            import pypdfium2 as pdfium
            from reportlab.lib.utils import ImageReader
            from reportlab.pdfgen.canvas import Canvas

            pdf = pdfium.PdfDocument(source)
            page = pdf[0]
            bitmap = page.render(scale=2)
            image = bitmap.to_pil().copy()
            bitmap.close()
            page.close()
            pdf.close()
            canvas = Canvas(str(source), pagesize=(612, 792), invariant=1, pageCompression=0)
            canvas.drawImage(ImageReader(image), 0, 0, 612, 792)
            canvas.save()
        document = table_document([rows])
        errors = []
        for cell in document["tables"][0]["data"]["table_cells"]:
            key = (cell["start_row_offset_idx"], cell["start_col_offset_idx"])
            if key in mutations:
                cell["text"] = mutations[key]
                errors.append(
                    {
                        "table_index": 0,
                        "row": key[0],
                        "col": key[1],
                        "type": name,
                        "expected": rows[key[0]][key[1]],
                        "observed": mutations[key],
                    }
                )
            if missing_geometry:
                cell.pop("bbox")
        if missing_geometry:
            document["tables"][0]["prov"][0].pop("bbox")
        if no_tables:
            document["tables"] = []
            errors.append({"table_index": 0, "type": "entire_table_missing"})
        if merged:
            cells = document["tables"][0]["data"]["table_cells"]
            cells[0]["col_span"] = 2
            cells[0]["end_col_offset_idx"] = 2
            cells[0]["text"] = "Sample Dose (mg)"
            cells[0]["bbox"]["r"] = cells[1]["bbox"]["r"]
            del cells[1]
            # Semantic text is intact; the extraction represents a spanning header.
            # This deliberately exercises an unsupported layout, not an error detector.
        extracted = out / f"{name}.json"
        write_json(extracted, document)
        case = manifest_case(
            f"synthetic-{name}",
            "synthetic_control",
            source,
            extracted,
            errors,
            metadata={
                "fixture_license": "MIT",
                "generator": "benchmarks/make_synthetic.py",
                "expected_support": "uncertain"
                if any((missing_geometry, no_tables, merged, scanned))
                else "supported",
                "gold_source": "Declared fixture text and explicit mutations, not model output.",
                "independence_note": "One generated layout family; cases are correlated.",
            },
        )
        write_json(out / f"{name}.manifest.json", case)
        cases.append(case)

    add("clean", ROWS, {})
    add("row-label-swap", ROWS, {(1, 0): "Beta", (2, 0): "Alpha"})
    add("row-value-swap", ROWS, {(1, 1): "20.0", (2, 1): "12.5"})
    add("column-value-swap", ROWS, {(1, 1): "3.0", (1, 2): "12.5"})
    add("header-swap", ROWS, {(0, 1): "Volume (ml)", (0, 2): "Dose (mg)"})
    add("empty-cell", ROWS, {(2, 1): ""})
    add("decimal-loss", ROWS, {(1, 1): "125"})
    add("unit-change", ROWS, {(0, 1): "Dose (g)"})
    blank_rows = copy.deepcopy(ROWS)
    blank_rows[2][1] = ""
    add("clean-empty-cell", blank_rows, {})
    repeated = copy.deepcopy(ROWS)
    repeated[2][1] = "12.5"
    add("clean-repeated-value", repeated, {})
    add("missing-geometry", ROWS, {}, missing_geometry=True)
    add("missing-table", ROWS, {}, no_tables=True)
    add("spanning-header", ROWS, {}, merged=True)
    add("scan-only", ROWS, {}, scanned=True)
    return cases


if __name__ == "__main__":
    print(f"Wrote {len(generate())} synthetic controls.")
