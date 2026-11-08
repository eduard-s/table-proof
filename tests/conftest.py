from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from reportlab.pdfgen import canvas


@pytest.fixture
def pdf_case(tmp_path: Path) -> tuple[Path, dict[str, Any]]:
    source = tmp_path / "pumps.pdf"
    pdf = canvas.Canvas(str(source), pagesize=(360, 240), invariant=1)
    rows = [
        ["Product", "Temperature C", "Pressure bar"],
        ["Pump A", "80", "12"],
        ["Pump B", "60", "20"],
    ]
    cells = []
    for row, values in enumerate(rows):
        top, bottom = 40 + row * 35, 75 + row * 35
        for col, text in enumerate(values):
            left, right = 20 + col * 105, 125 + col * 105
            pdf.setFont("Helvetica", 10)
            pdf.drawString(left + 6, 240 - top - 22, text)
            pdf.rect(left, 240 - bottom, right - left, bottom - top)
            cells.append(
                {
                    "text": text,
                    "start_row_offset_idx": row,
                    "end_row_offset_idx": row + 1,
                    "start_col_offset_idx": col,
                    "end_col_offset_idx": col + 1,
                    "row_span": 1,
                    "col_span": 1,
                    "column_header": row == 0,
                    "bbox": {
                        "l": left,
                        "t": top,
                        "r": right,
                        "b": bottom,
                        "coord_origin": "TOPLEFT",
                    },
                }
            )
    pdf.showPage()
    pdf.save()
    document = {
        "pages": {"1": {"size": {"width": 360, "height": 240}}},
        "tables": [
            {
                "self_ref": "#/tables/0",
                "prov": [
                    {
                        "page_no": 1,
                        "bbox": {"l": 20, "t": 40, "r": 335, "b": 145, "coord_origin": "TOPLEFT"},
                    }
                ],
                "data": {"num_rows": 3, "num_cols": 3, "table_cells": cells},
            }
        ],
    }
    return source, document
