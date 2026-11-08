from pathlib import Path

from reportlab.pdfgen import canvas

from table_proof import BBox, Cell, Table, audit_tables
from table_proof.pdf import read_pdf_pages


def test_superscript_stays_separate_from_numeric_value(tmp_path: Path):
    source = tmp_path / "superscript.pdf"
    pdf = canvas.Canvas(str(source), pagesize=(240, 160), invariant=1)
    pdf.setFont("Helvetica", 12)
    pdf.drawString(30, 110, "0.65")
    x = 30 + pdf.stringWidth("0.65", "Helvetica", 12)
    pdf.setFont("Helvetica", 8)
    pdf.drawString(x, 114, "a")
    pdf.showPage()
    pdf.save()
    page = read_pdf_pages(source)[1]
    assert sorted(word.text for word in page.words) == ["0.65", "a"]
    table = Table(
        id="t",
        page=1,
        bbox=BBox(x0=20, top=30, x1=100, bottom=70),
        num_rows=1,
        num_cols=1,
        cells=[
            Cell(id="c", row=0, col=0, text="0.65 a", bbox=BBox(x0=20, top=30, x1=100, bottom=70))
        ],
    )
    assert audit_tables(source, [table]).status == "no_findings"
    altered = table.model_copy(
        update={"cells": [table.cells[0].model_copy(update={"text": "0.56 a"})]}
    )
    assert audit_tables(source, [altered]).status == "review"
