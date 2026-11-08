from __future__ import annotations

import copy
import json
from pathlib import Path
from unittest.mock import patch

import pytest
from reportlab.pdfgen import canvas

from table_proof import audit_tables
from table_proof.cli import main


def test_real_pdf_correct_and_permutation(pdf_case):
    source, document = pdf_case
    before = copy.deepcopy(document)
    clean = audit_tables(source, document)
    assert clean.status == "no_findings"
    assert clean.tables[0].checked_cells == 9
    cells = document["tables"][0]["data"]["table_cells"]
    cells[4]["text"], cells[5]["text"] = cells[5]["text"], cells[4]["text"]
    changed = audit_tables(source, document)
    assert changed.status == "review"
    assert len(changed.tables[0].findings) >= 2
    assert before["tables"][0]["data"]["table_cells"][4]["text"] == "80"


def test_json_and_html_evidence(pdf_case, tmp_path):
    source, doc = pdf_case
    doc["tables"][0]["data"]["table_cells"][4]["text"] = '<script>alert("x")</script>'
    report = audit_tables(source, doc)
    html = tmp_path / "report.html"
    output = tmp_path / "report.json"
    report.export_html(str(html), source_pdf=str(source))
    report.export_json(str(output))
    markup = html.read_text()
    assert "data:image/png;base64," in markup
    assert "<script>" not in markup
    assert "&lt;script&gt;" in markup
    assert "Content-Security-Policy" in markup
    assert json.loads(output.read_text())["status"] == "review"
    assert report.source_sha256 in markup


def test_html_refuses_different_source(pdf_case, tmp_path):
    source, doc = pdf_case
    report = audit_tables(source, doc)
    altered = tmp_path / "other.pdf"
    altered.write_bytes(source.read_bytes() + b"changed")
    with pytest.raises(ValueError, match="hash"):
        report.export_html(str(tmp_path / "report.html"), source_pdf=str(altered))


def test_html_export_preserves_source(pdf_case):
    source, doc = pdf_case
    report = audit_tables(source, doc)
    before = source.read_bytes()
    with pytest.raises(ValueError, match="replace"):
        report.export_html(str(source), source_pdf=str(source))
    assert source.read_bytes() == before


def test_blank_source_is_uncertain(pdf_case, tmp_path):
    _, doc = pdf_case
    blank = tmp_path / "blank.pdf"
    pdf = canvas.Canvas(str(blank), pagesize=(360, 240))
    pdf.showPage()
    pdf.save()
    assert audit_tables(blank, doc).status == "uncertain"


def test_empty_extraction_is_uncertain(pdf_case):
    source, _ = pdf_case
    assert audit_tables(source, {"tables": []}).status == "uncertain"


def test_cli_exit_statuses(pdf_case, tmp_path, capsys):
    source, doc = pdf_case
    extraction = tmp_path / "extraction.json"
    output = tmp_path / "out.json"
    extraction.write_text(json.dumps(doc))
    assert main([str(source), str(extraction), "--json", str(output)]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "no_findings"
    doc["tables"][0]["data"]["table_cells"][4]["text"] = "123"
    extraction.write_text(json.dumps(doc))
    assert main([str(source), str(extraction)]) == 1
    extraction.write_text('{"tables": []}')
    assert main([str(source), str(extraction)]) == 3
    extraction.write_text("bad-json")
    assert main([str(source), str(extraction)]) == 2
    assert "error" in capsys.readouterr().err


def test_cli_protects_inputs_and_distinct_outputs(pdf_case, tmp_path):
    source, doc = pdf_case
    extraction = tmp_path / "extraction.json"
    extraction.write_text(json.dumps(doc))
    original = source.read_bytes()
    assert main([str(source), str(extraction), "--html", str(source)]) == 2
    assert source.read_bytes() == original
    assert main([str(source), str(extraction), "--json", str(extraction)]) == 2
    out = str(tmp_path / "out")
    assert main([str(source), str(extraction), "--json", out, "--html", out]) == 2


def test_cli_download_flag_needs_vision(pdf_case):
    source, _ = pdf_case
    with pytest.raises(SystemExit) as error:
        main([str(source), "extract.json", "--allow-model-download"])
    assert error.value.code == 2


def test_optional_vision_findings_affect_status(pdf_case):
    from table_proof.models import Finding

    source, doc = pdf_case
    finding = Finding(
        code="vision_unavailable",
        severity="uncertain",
        table_id="#/tables/0",
        page=1,
        message="The optional model is unavailable.",
        evidence="vision",
    )
    with patch("table_proof.vision.inspect_table", return_value=[finding]):
        assert audit_tables(source, doc, vision=True).status == "uncertain"


def test_invalid_pdf_is_error(tmp_path: Path, capsys):
    source = tmp_path / "bad.pdf"
    source.write_text("not a pdf")
    extraction = tmp_path / "doc.json"
    extraction.write_text('{"tables": []}')
    assert main([str(source), str(extraction)]) == 2
    assert json.loads(capsys.readouterr().err)["status"] == "error"
