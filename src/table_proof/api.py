"""Public audit entry point."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from .auditor import AuditConfig, audit_document
from .docling import normalize_document
from .models import AuditReport, TableResult
from .pdf import read_pdf_pages


def audit_tables(
    source_pdf: str | Path,
    extracted_document: Any,
    *,
    config: AuditConfig | None = None,
    vision: bool = False,
    allow_model_download: bool = False,
) -> AuditReport:
    """Audit table associations without changes to the source or extraction."""
    path = Path(source_pdf)
    with path.open("rb") as source:
        digest = hashlib.file_digest(source, "sha256").hexdigest()
    pages = read_pdf_pages(path)
    tables = normalize_document(extracted_document, pages)
    results = audit_document(tables, pages, config=config)
    limitations = [
        "No findings means that the selected checks found no error. It does not prove accuracy.",
        "The geometry path depends on digital PDF text and cell coordinates.",
        "Scans, multi-page tables, and ambiguous evidence need human review.",
        "The tool does not certify meaning, units, or the factual accuracy of a source document.",
    ]
    if vision:
        from .vision import VisionConfig, inspect_table

        updated = []
        for table, result in zip(tables, results, strict=True):
            findings = result.findings + inspect_table(
                path, table, config=VisionConfig(allow_download=allow_model_download)
            )
            status = result.status
            if any(finding.severity == "error" for finding in findings):
                status = "review"
            elif findings:
                status = "uncertain"
            updated.append(
                TableResult(
                    table_id=result.table_id,
                    page=result.page,
                    status=status,
                    checked_cells=result.checked_cells,
                    total_cells=result.total_cells,
                    findings=findings,
                )
            )
        results = updated
        limitations.append("Vision detector scores are not calibrated error probabilities.")
    if not tables:
        limitations.append("The extraction contains no tables. Coverage is unknown.")
    return AuditReport(
        source_name=path.name, source_sha256=digest, tables=results, limitations=limitations
    )
