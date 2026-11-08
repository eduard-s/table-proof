"""TableProof audits PDF table cell associations."""

from .api import audit_tables
from .auditor import AuditConfig, audit_document
from .docling import DocumentFormatError, normalize_document
from .models import AuditReport, BBox, Cell, Finding, SourcePage, SourceWord, Table, TableResult

__version__ = "0.1.0"

__all__ = [
    "AuditConfig",
    "AuditReport",
    "BBox",
    "Cell",
    "DocumentFormatError",
    "Finding",
    "SourcePage",
    "SourceWord",
    "Table",
    "TableResult",
    "audit_document",
    "audit_tables",
    "normalize_document",
]
