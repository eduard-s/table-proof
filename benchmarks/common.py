"""Deterministic fixture helpers. Coordinates use a top-left origin."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
WIDTH, HEIGHT = 612, 792
LEFT, TOP, COL_WIDTH, ROW_HEIGHT = 72, 96, 156, 34


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n")


def bbox(row: int, col: int, row_span: int = 1, col_span: int = 1) -> dict[str, Any]:
    return {
        "l": LEFT + col * COL_WIDTH,
        "t": TOP + row * ROW_HEIGHT,
        "r": LEFT + (col + col_span) * COL_WIDTH,
        "b": TOP + (row + row_span) * ROW_HEIGHT,
        "coord_origin": "TOPLEFT",
    }


def table_document(pages: list[list[list[str]]]) -> dict[str, Any]:
    tables = []
    for page, rows in enumerate(pages, 1):
        cells = [
            {
                "text": text,
                "row_span": 1,
                "col_span": 1,
                "start_row_offset_idx": row,
                "end_row_offset_idx": row + 1,
                "start_col_offset_idx": col,
                "end_col_offset_idx": col + 1,
                "column_header": row == 0,
                "row_header": col == 0,
                "bbox": bbox(row, col),
            }
            for row, values in enumerate(rows)
            for col, text in enumerate(values)
        ]
        tables.append(
            {
                "self_ref": f"#/tables/{page - 1}",
                "label": "table",
                "prov": [{"page_no": page, "bbox": bbox(0, 0, len(rows), len(rows[0]))}],
                "data": {"num_rows": len(rows), "num_cols": len(rows[0]), "table_cells": cells},
            }
        )
    return {
        "schema_name": "DoclingDocument",
        "version": "1.11.0",
        "name": "fixture",
        "tables": tables,
        "groups": [],
        "texts": [],
        "pages": {
            str(page): {"page_no": page, "size": {"width": WIDTH, "height": HEIGHT}}
            for page in range(1, len(pages) + 1)
        },
    }


def draw_pdf(path: Path, pages: list[list[list[str]]], *, merged_header: bool = False) -> None:
    from reportlab.pdfgen.canvas import Canvas

    path.parent.mkdir(parents=True, exist_ok=True)
    canvas = Canvas(str(path), pagesize=(WIDTH, HEIGHT), invariant=1, pageCompression=0)
    canvas.setTitle("TableProof benchmark fixture")
    canvas.setAuthor("TableProof contributors")
    for rows in pages:
        canvas.setFont("Helvetica", 11)
        for row, values in enumerate(rows):
            for col, value in enumerate(values):
                if merged_header and row == 0 and col == 1:
                    continue
                box = bbox(row, col)
                width = COL_WIDTH
                if merged_header and row == 0 and col == 0:
                    width *= 2
                    value = " ".join(values[:2])
                canvas.rect(box["l"], HEIGHT - box["b"], width, ROW_HEIGHT)
                canvas.drawString(box["l"] + 8, HEIGHT - box["t"] - 22, value)
        canvas.showPage()
    canvas.save()


def manifest_case(
    case_id: str,
    stratum: str,
    source: Path,
    extracted: Path,
    errors: list[dict[str, Any]],
    **extra: Any,
) -> dict[str, Any]:
    return {
        "id": case_id,
        "stratum": stratum,
        "source_pdf": str(source.relative_to(ROOT)),
        "source_sha256": sha256(source),
        "extracted_json": str(extracted.relative_to(ROOT)),
        "extracted_sha256": sha256(extracted),
        "gold": {"has_error": bool(errors), "errors": errors},
        **extra,
    }
