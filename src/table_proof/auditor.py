"""Compare table cells with independent PDF text and geometry."""

from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from .models import BBox, Cell, Finding, SourcePage, SourceWord, Status, Table, TableResult


@dataclass(frozen=True)
class AuditConfig:
    """Set geometric tolerances in PDF points."""

    geometry_tolerance: float = 1.0
    min_word_overlap: float = 0.8

    def __post_init__(self) -> None:
        if not math.isfinite(self.geometry_tolerance) or self.geometry_tolerance < 0:
            raise ValueError("geometry_tolerance must be finite and nonnegative.")
        if not math.isfinite(self.min_word_overlap) or not 0 < self.min_word_overlap <= 1:
            raise ValueError("min_word_overlap must be in (0, 1].")


@dataclass
class _CellState:
    cell: Cell
    words: list[SourceWord] = field(default_factory=list)
    usable: bool = True
    uncertain: bool = False


def _tokens(text: str) -> tuple[str, ...]:
    # Preserve case, punctuation, signs, decimal points, and superscripts.
    return tuple(unicodedata.normalize("NFC", text).split())


def _bracket_tokens(text: str) -> Counter[str]:
    # Font changes can separate brackets and move their source reading order.
    # Keep every bracket, decimal point, sign, and other punctuation character.
    return Counter(re.findall(r"[()\[\]{}]|[^\s()\[\]{}]+", unicodedata.normalize("NFC", text)))


def _area(box: BBox) -> float:
    return (box.x1 - box.x0) * (box.bottom - box.top)


def _overlap(inner: BBox, outer: BBox, tolerance: float = 0) -> float:
    width = max(0.0, min(inner.x1, outer.x1 + tolerance) - max(inner.x0, outer.x0 - tolerance))
    height = max(
        0.0, min(inner.bottom, outer.bottom + tolerance) - max(inner.top, outer.top - tolerance)
    )
    return width * height


def _center_inside(inner: BBox, outer: BBox, tolerance: float) -> bool:
    x = (inner.x0 + inner.x1) / 2
    y = (inner.top + inner.bottom) / 2
    return (
        outer.x0 - tolerance <= x <= outer.x1 + tolerance
        and outer.top - tolerance <= y <= outer.bottom + tolerance
    )


def _inside_page(box: BBox, page: SourcePage, tolerance: float) -> bool:
    return (
        box.x0 >= -tolerance
        and box.top >= -tolerance
        and box.x1 <= page.width + tolerance
        and box.bottom <= page.height + tolerance
    )


def _contains(outer: BBox, inner: BBox, tolerance: float) -> bool:
    return (
        inner.x0 >= outer.x0 - tolerance
        and inner.top >= outer.top - tolerance
        and inner.x1 <= outer.x1 + tolerance
        and inner.bottom <= outer.bottom + tolerance
    )


def _intersects(start_a: int, span_a: int, start_b: int, span_b: int) -> bool:
    return max(start_a, start_b) < min(start_a + span_a, start_b + span_b)


def _finding(
    table: Table,
    code: str,
    message: str,
    *,
    cell: Cell | None = None,
    uncertain: bool = False,
    expected: str | None = None,
    observed: str | None = None,
    evidence: str = "pdf_text_geometry",
) -> Finding:
    return Finding(
        code=code,
        severity="uncertain" if uncertain else "error",
        table_id=table.id,
        page=table.page,
        cell_id=cell.id if cell is not None else None,
        message=message,
        expected_text=expected,
        observed_text=observed,
        bbox=cell.bbox if cell is not None else table.bbox,
        evidence=evidence,
    )


def _sort_cell(cell: Cell) -> tuple[int, int, int, int, str, str, tuple[float, ...]]:
    box = cell.bbox
    return (
        cell.row,
        cell.col,
        cell.row_span,
        cell.col_span,
        cell.id,
        cell.text,
        (box.x0, box.top, box.x1, box.bottom) if box is not None else (),
    )


def _geometry_supported(box: BBox, table: Table, page: SourcePage | None, tolerance: float) -> bool:
    if page is None or page.page != table.page or table.unsupported_reason:
        return False
    if not _inside_page(box, page, tolerance):
        return False
    return table.bbox is None or (
        _inside_page(table.bbox, page, tolerance) and _contains(table.bbox, box, tolerance)
    )


def _structure(
    table: Table, states: list[_CellState], config: AuditConfig, page: SourcePage | None
) -> list[Finding]:
    findings: list[Finding] = []
    ids = Counter(state.cell.id for state in states)
    for state in states:
        cell = state.cell
        if ids[cell.id] > 1:
            findings.append(
                _finding(
                    table,
                    "duplicate_cell_id",
                    "Cell IDs must be unique.",
                    cell=cell,
                    evidence="table_structure",
                )
            )
        if cell.row + cell.row_span > table.num_rows or cell.col + cell.col_span > table.num_cols:
            findings.append(
                _finding(
                    table,
                    "invalid_cell_span",
                    "The cell span exceeds the table grid.",
                    cell=cell,
                    evidence="table_structure",
                )
            )
        if cell.bbox is None:
            state.usable = False
            state.uncertain = True
            findings.append(
                _finding(
                    table,
                    "cell_bbox_missing",
                    "The cell has no source box.",
                    cell=cell,
                    uncertain=True,
                    evidence="table_structure",
                )
            )

    for index, first in enumerate(states):
        a = first.cell
        for second in states[index + 1 :]:
            b = second.cell
            rows_overlap = _intersects(a.row, a.row_span, b.row, b.row_span)
            cols_overlap = _intersects(a.col, a.col_span, b.col, b.col_span)
            if rows_overlap and cols_overlap:
                findings.append(
                    _finding(
                        table,
                        "grid_cell_overlap",
                        f"The grid span overlaps cell {b.id}.",
                        cell=a,
                        evidence="table_structure",
                    )
                )
            if a.bbox is None or b.bbox is None:
                continue
            tolerance = config.geometry_tolerance
            if not all(
                _geometry_supported(box, table, page, tolerance) for box in (a.bbox, b.bbox)
            ):
                continue
            width = min(a.bbox.x1, b.bbox.x1) - max(a.bbox.x0, b.bbox.x0)
            height = min(a.bbox.bottom, b.bbox.bottom) - max(a.bbox.top, b.bbox.top)
            if width > tolerance and height > tolerance:
                first.uncertain = second.uncertain = True
                findings.append(
                    _finding(
                        table,
                        "cell_geometry_overlap",
                        f"The source box overlaps cell {b.id}.",
                        cell=a,
                        uncertain=True,
                        evidence="cell_geometry",
                    )
                )
            if rows_overlap and not cols_overlap:
                left, right = (a, b) if a.col < b.col else (b, a)
                assert left.bbox is not None and right.bbox is not None
                if left.bbox.x0 >= right.bbox.x1 - tolerance:
                    findings.append(
                        _finding(
                            table,
                            "column_order_inversion",
                            f"The cell is physically right of later column cell {right.id}.",
                            cell=left,
                            evidence="cell_geometry",
                        )
                    )
            if cols_overlap and not rows_overlap:
                upper, lower = (a, b) if a.row < b.row else (b, a)
                assert upper.bbox is not None and lower.bbox is not None
                if upper.bbox.top >= lower.bbox.bottom - tolerance:
                    findings.append(
                        _finding(
                            table,
                            "row_order_inversion",
                            f"The cell is physically below later row cell {lower.id}.",
                            cell=upper,
                            evidence="cell_geometry",
                        )
                    )
    return findings


def _word_text(words: Sequence[SourceWord]) -> str:
    ordered = sorted(words, key=lambda word: (word.bbox.top, word.bbox.x0, word.text))
    return " ".join(word.text for word in ordered)


def _bad_text(text: str) -> bool:
    return any(
        char == "\ufffd"
        or unicodedata.category(char) in {"Co", "Cs"}
        or (unicodedata.category(char) == "Cc" and not char.isspace())
        for char in text
    )


def _assign_words(
    table: Table, page: SourcePage, states: list[_CellState], config: AuditConfig
) -> list[Finding]:
    findings: list[Finding] = []
    tolerance = config.geometry_tolerance
    ambiguous: set[int] = set()
    unassigned: list[SourceWord] = []
    seen_boxes: dict[tuple[float, float, float, float], list[int]] = {}
    for word in sorted(page.words, key=lambda item: (item.bbox.top, item.bbox.x0, item.text)):
        if not _tokens(word.text):
            continue
        if table.bbox is not None and not _overlap(word.bbox, table.bbox, tolerance):
            continue
        candidates: list[int] = []
        touches: list[int] = []
        for index, state in enumerate(states):
            box = state.cell.bbox
            if not state.usable or box is None:
                continue
            if _overlap(word.bbox, box) > 0:
                touches.append(index)
            if _center_inside(word.bbox, box, tolerance):
                candidates.append(index)
        if len(candidates) != 1:
            ambiguous.update(candidates or touches)
            if not candidates and not touches and table.bbox is not None:
                if _center_inside(word.bbox, table.bbox, 0):
                    unassigned.append(word)
            continue
        index = candidates[0]
        box = states[index].cell.bbox
        assert box is not None
        reliable = (
            _overlap(word.bbox, box, tolerance) / _area(word.bbox) >= config.min_word_overlap
            and _inside_page(word.bbox, page, tolerance)
            and not _bad_text(word.text)
        )
        if not reliable:
            ambiguous.add(index)
        states[index].words.append(word)
        key = (word.bbox.x0, word.bbox.top, word.bbox.x1, word.bbox.bottom)
        if key in seen_boxes:
            ambiguous.update(seen_boxes[key])
            ambiguous.add(index)
        seen_boxes.setdefault(key, []).append(index)
    for index in sorted(ambiguous):
        states[index].uncertain = True
        findings.append(
            _finding(
                table,
                "source_assignment_ambiguous",
                "Source words cross a boundary, overlap, or have unreadable text.",
                cell=states[index].cell,
                uncertain=True,
            )
        )
    if unassigned:
        findings.append(
            _finding(
                table,
                "unassigned_source_text",
                "Source text in the table box has no cell assignment. Review the table extent.",
                uncertain=True,
                expected=_word_text(unassigned),
            )
        )
    return findings


def _compare(table: Table, state: _CellState) -> Finding | None:
    cell = state.cell
    source = _word_text(state.words)
    expected = _tokens(source)
    observed = _tokens(cell.text)
    if Counter(expected) == Counter(observed):
        return None
    if not expected:
        return _finding(
            table,
            "cell_source_text_missing",
            "No readable source words support the cell text.",
            cell=cell,
            uncertain=True,
            observed=cell.text,
        )
    if not observed:
        return _finding(
            table,
            "missing_cell_text",
            "Source words are absent from the empty cell.",
            cell=cell,
            expected=source,
            observed=cell.text,
        )

    # Token boundaries, ligatures, and line-end hyphens need a human decision.
    def relaxed(text: str) -> str:
        text = unicodedata.normalize("NFKC", text)
        text = re.sub(r"(?<=[^\W\d_])-\s*(?=[^\W\d_])", "", text)
        return "".join(text.split())

    if (
        relaxed(source) == relaxed(cell.text)
        or _bracket_tokens(source) == _bracket_tokens(cell.text)
        or _bad_text(cell.text)
    ):
        return _finding(
            table,
            "text_normalization_uncertain",
            "Text differs in token boundaries, bracket order, glyphs, or hyphens.",
            cell=cell,
            uncertain=True,
            expected=source,
            observed=cell.text,
        )
    return _finding(
        table,
        "cell_text_mismatch",
        "Cell tokens differ from the source words.",
        cell=cell,
        expected=source,
        observed=cell.text,
    )


def _result(table: Table, findings: list[Finding], checked: int) -> TableResult:
    findings.sort(key=lambda finding: (finding.cell_id or "", finding.code, finding.message))
    status: Status = "no_findings"
    if any(finding.severity == "error" for finding in findings):
        status = "review"
    elif findings:
        status = "uncertain"
    return TableResult(
        table_id=table.id,
        page=table.page,
        status=status,
        checked_cells=checked,
        total_cells=len(table.cells),
        findings=findings,
    )


def _audit_table(table: Table, pages: Mapping[int, SourcePage], config: AuditConfig) -> TableResult:
    states = [_CellState(cell) for cell in sorted(table.cells, key=_sort_cell)]
    page = pages.get(table.page)
    findings = _structure(table, states, config, page)
    if table.unsupported_reason:
        findings.append(
            _finding(
                table,
                "unsupported_table",
                table.unsupported_reason,
                uncertain=True,
                evidence="table_structure",
            )
        )
        return _result(table, findings, 0)
    if page is None or page.page != table.page:
        findings.append(
            _finding(
                table, "source_page_missing", "The source page is unavailable.", uncertain=True
            )
        )
        return _result(table, findings, 0)
    if not any(_tokens(word.text) for word in page.words):
        findings.append(
            _finding(
                table,
                "source_text_unavailable",
                "The page has no readable source words. OCR is outside this audit.",
                uncertain=True,
            )
        )
        return _result(table, findings, 0)
    if not states:
        findings.append(
            _finding(
                table,
                "no_cells",
                "The extraction contains no cells.",
                uncertain=True,
                evidence="table_structure",
            )
        )
    tolerance = config.geometry_tolerance
    if table.bbox is None:
        findings.append(
            _finding(
                table,
                "table_bbox_missing",
                "The table has no source box.",
                uncertain=True,
                evidence="table_structure",
            )
        )
    elif not _inside_page(table.bbox, page, tolerance):
        findings.append(
            _finding(
                table,
                "table_outside_page",
                "The table box exceeds the source page.",
                uncertain=True,
                evidence="cell_geometry",
            )
        )
        return _result(table, findings, 0)
    for state in states:
        box = state.cell.bbox
        if box is None:
            continue
        if not _inside_page(box, page, tolerance):
            code, message = "cell_outside_page", "The cell box exceeds the source page."
        elif table.bbox is not None and not _contains(table.bbox, box, tolerance):
            code, message = "cell_outside_table", "The cell box exceeds the table box."
        else:
            continue
        state.usable = False
        findings.append(
            _finding(
                table, code, message, cell=state.cell, uncertain=True, evidence="cell_geometry"
            )
        )
    scope = [table.bbox] if table.bbox is not None else [state.cell.bbox for state in states]
    if not any(
        _tokens(word.text)
        and any(box is not None and _overlap(word.bbox, box, tolerance) > 0 for box in scope)
        for word in page.words
    ):
        findings.append(
            _finding(
                table,
                "table_source_text_unavailable",
                "The table region has no source words. Its content is unknown.",
                uncertain=True,
            )
        )
        return _result(table, findings, 0)
    findings.extend(_assign_words(table, page, states, config))
    checked = 0
    for state in states:
        if not state.usable or state.uncertain:
            continue
        finding = _compare(table, state)
        if finding is not None:
            findings.append(finding)
        if finding is None or finding.severity == "error":
            checked += 1
    return _result(table, findings, checked)


def audit_document(
    tables: Sequence[Table],
    pages: Mapping[int, SourcePage],
    config: AuditConfig | None = None,
) -> list[TableResult]:
    """Audit supplied tables without changing the inputs.

    A result with no findings covers only the implemented checks. It does not
    prove semantic correctness, reading order, or complete table extraction.
    """
    options = config if config is not None else AuditConfig()
    return [_audit_table(table, pages, options) for table in tables]
