from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from table_proof.cli import main
from table_proof.models import AuditReport


def test_cli_report_hardlink_does_not_replace_source(
    pdf_case: tuple[Path, dict[str, Any]],
    tmp_path: Path,
) -> None:
    source, document = pdf_case
    original = source.read_bytes()
    extraction = tmp_path / "extraction.json"
    extraction.write_text(json.dumps(document))
    report_path = tmp_path / "report.json"
    os.link(source, report_path)

    result = main([str(source), str(extraction), "--json", str(report_path)])

    assert result == 2
    assert source.read_bytes() == original


def test_html_escapes_all_report_metadata(tmp_path: Path) -> None:
    payload = '<script>alert("metadata")</script>'
    report = AuditReport(
        source_name="source.pdf",
        source_sha256=payload,
        engine_version=payload,
        schema_version=payload,
        tables=[],
    )
    destination = tmp_path / "report.html"
    report.export_html(str(destination))
    content = destination.read_text()

    assert payload not in content
    assert "&lt;script&gt;" in content
