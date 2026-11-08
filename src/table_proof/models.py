"""Typed source evidence and audit results."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Status = Literal["no_findings", "review", "uncertain"]


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class BBox(Record):
    """A box in PDF points, with a top-left origin."""

    x0: float
    top: float
    x1: float
    bottom: float

    @model_validator(mode="after")
    def positive_area(self) -> BBox:
        if self.x1 <= self.x0 or self.bottom <= self.top:
            raise ValueError("A box must have positive width and height.")
        return self


class SourceWord(Record):
    text: str
    bbox: BBox


class SourcePage(Record):
    page: int = Field(ge=1)
    width: float = Field(gt=0)
    height: float = Field(gt=0)
    words: list[SourceWord]


class Cell(Record):
    id: str
    row: int = Field(ge=0)
    col: int = Field(ge=0)
    text: str
    bbox: BBox | None = None
    row_span: int = Field(default=1, ge=1)
    col_span: int = Field(default=1, ge=1)
    column_header: bool = False
    row_header: bool = False


class Table(Record):
    id: str
    page: int = Field(ge=1)
    bbox: BBox | None = None
    num_rows: int = Field(ge=0)
    num_cols: int = Field(ge=0)
    cells: list[Cell]
    unsupported_reason: str | None = None


class Finding(Record):
    code: str
    severity: Literal["error", "uncertain"]
    table_id: str
    page: int
    cell_id: str | None = None
    message: str
    expected_text: str | None = None
    observed_text: str | None = None
    bbox: BBox | None = None
    evidence: str = "pdf_text_geometry"


class TableResult(Record):
    table_id: str
    page: int
    status: Status
    checked_cells: int = Field(ge=0)
    total_cells: int = Field(ge=0)
    findings: list[Finding]


class AuditReport(Record):
    schema_version: str = "1.0"
    engine_version: str = "0.1.0"
    source_name: str
    source_sha256: str
    tables: list[TableResult]
    limitations: list[str] = Field(default_factory=list)

    @property
    def status(self) -> Status:
        if any(table.status == "review" for table in self.tables):
            return "review"
        if not self.tables or any(table.status == "uncertain" for table in self.tables):
            return "uncertain"
        return "no_findings"

    def export_json(self, path: str) -> None:
        from .report import export_json

        export_json(self, path)

    def export_html(self, path: str, *, source_pdf: str | None = None) -> None:
        from .report import export_html

        export_html(self, path, source_pdf=source_pdf)
