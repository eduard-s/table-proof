from __future__ import annotations

import math

import pytest

from table_proof.auditor import AuditConfig, audit_document
from table_proof.models import BBox, Cell, SourcePage, SourceWord, Table, TableResult


def box(x0: float = 10, top: float = 10, x1: float = 110, bottom: float = 40) -> BBox:
    return BBox(x0=x0, top=top, x1=x1, bottom=bottom)


def fixture(text: str = "42", source: str = "42") -> tuple[Table, SourcePage]:
    table = Table(
        id="t1",
        page=1,
        bbox=box(),
        num_rows=1,
        num_cols=1,
        cells=[Cell(id="c1", row=0, col=0, text=text, bbox=box())],
    )
    page = SourcePage(
        page=1,
        width=600,
        height=800,
        words=[SourceWord(text=source, bbox=box(20, 15, 80, 25))],
    )
    return table, page


def run(table: Table, page: SourcePage) -> TableResult:
    return audit_document([table], {1: page})[0]


def codes(result: TableResult) -> set[str]:
    return {finding.code for finding in result.findings}


def replace_cells(table: Table, cells: list[Cell]) -> Table:
    return table.model_copy(update={"cells": cells})


def two_cells(*, repeated: bool = False) -> tuple[Table, SourcePage]:
    cells = [
        Cell(id="left", row=0, col=0, text="42", bbox=box()),
        Cell(id="right", row=0, col=1, text="42" if repeated else "84", bbox=box(110, 10, 210, 40)),
    ]
    table = Table(id="t1", page=1, bbox=box(10, 10, 210, 40), num_rows=1, num_cols=2, cells=cells)
    page = SourcePage(
        page=1,
        width=600,
        height=800,
        words=[
            SourceWord(text="42", bbox=box(20, 15, 80, 25)),
            SourceWord(text="42" if repeated else "84", bbox=box(120, 15, 180, 25)),
        ],
    )
    return table, page


def test_matching_cell_records_limited_success() -> None:
    table, page = fixture()
    result = run(table, page)
    assert result.status == "no_findings"
    assert result.checked_cells == result.total_cells == 1
    assert result.findings == []


@pytest.mark.parametrize(
    ("source", "text"),
    [
        ("1.20", "120"),
        ("-10", "10"),
        ("1,200", "1200"),
        ("mM", "mm"),
        ("10%", "10"),
        ("12", "21"),
        ("1e-3", "1e3"),
        ("10.0", "10,0"),
    ],
)
def test_significant_token_changes_remain_visible(source: str, text: str) -> None:
    table, page = fixture(text, source)
    result = run(table, page)
    assert result.status == "review"
    finding = result.findings[0]
    assert finding.code == "cell_text_mismatch"
    assert finding.expected_text == source
    assert finding.observed_text == text
    assert finding.bbox == table.cells[0].bbox
    assert result.checked_cells == 1


def test_missing_text_is_an_error_with_source_evidence() -> None:
    table, page = fixture("", "Revenue")
    result = run(table, page)
    assert result.status == "review"
    assert result.findings[0].code == "missing_cell_text"
    assert result.findings[0].expected_text == "Revenue"


def test_cell_without_source_words_is_uncertain() -> None:
    table, page = fixture("42")
    page = page.model_copy(
        update={"words": [SourceWord(text="Outside", bbox=box(300, 20, 400, 30))]}
    )
    result = run(table, page)
    assert result.status == "uncertain"
    assert codes(result) == {"table_source_text_unavailable"}
    assert result.checked_cells == 0


def test_blank_cell_is_valid_when_source_text_exists_elsewhere() -> None:
    table, page = two_cells()
    table = replace_cells(table, [table.cells[0], table.cells[1].model_copy(update={"text": ""})])
    page = page.model_copy(update={"words": [page.words[0]]})
    result = run(table, page)
    assert result.status == "no_findings"
    assert result.checked_cells == 2


def test_populated_cell_without_words_has_no_proof_from_a_neighbor() -> None:
    table, page = two_cells()
    page = page.model_copy(update={"words": [page.words[0]]})
    result = run(table, page)
    assert result.status == "uncertain"
    assert codes(result) == {"cell_source_text_missing"}
    assert result.checked_cells == 1


def test_blank_table_region_is_uncertain_despite_text_elsewhere_on_page() -> None:
    table, page = fixture("", "")
    page = page.model_copy(
        update={
            "words": [SourceWord(text="Page header", bbox=box(300, 20, 400, 30))],
        }
    )
    result = run(table, page)
    assert result.status == "uncertain"
    assert codes(result) == {"table_source_text_unavailable"}
    assert result.checked_cells == 0


@pytest.mark.parametrize(
    ("source", "text"),
    [
        ("cost- effective", "cost-effective"),
        ("office", "ofﬁce"),
        ("10 000", "10000"),
        ("m²", "m2"),
        ("a b", "ab"),
    ],
)
def test_normalization_differences_require_review(source: str, text: str) -> None:
    table, page = fixture(text, source)
    result = run(table, page)
    assert result.status == "uncertain"
    assert codes(result) == {"text_normalization_uncertain"}
    assert result.checked_cells == 0


def test_whitespace_and_canonical_unicode_do_not_raise_findings() -> None:
    table, page = fixture("  café\n42\t", "cafe\u0301\u00a042")
    assert run(table, page).status == "no_findings"


@pytest.mark.parametrize(
    ("source", "text"),
    [
        ("Total mosquito catches ( ) n", "Total mosquito catches (n)"),
        ("Rate [ ] n", "Rate [n]"),
        ("Set { } n", "Set {n}"),
        ("Estimate ( ) -0.65", "Estimate (-0.65)"),
    ],
)
def test_bracket_and_font_segmentation_is_uncertain(source: str, text: str) -> None:
    table, page = fixture(text, source)
    result = run(table, page)
    assert result.status == "uncertain"
    assert codes(result) == {"text_normalization_uncertain"}
    assert result.checked_cells == 0
    assert result.findings[0].expected_text == source
    assert result.findings[0].observed_text == text


@pytest.mark.parametrize(
    ("source", "text"),
    [
        ("Estimate ( ) 0.65", "Estimate (0.56)"),
        ("Estimate ( ) 1.20", "Estimate (120)"),
        ("Estimate ( ) -10", "Estimate (10)"),
        ("Estimate ( ) 10", "Estimate 10"),
        ("Estimate [ ] n", "Estimate (n)"),
        ("Estimate ( ) n", "Estimate (m)"),
    ],
)
def test_bracket_segmentation_preserves_numeric_and_content_errors(source: str, text: str) -> None:
    table, page = fixture(text, source)
    result = run(table, page)
    assert result.status == "review"
    assert codes(result) == {"cell_text_mismatch"}


def test_token_counts_preserve_repeated_values() -> None:
    table, page = fixture("42", "42 42")
    assert run(table, page).status == "review"


def test_same_value_in_different_cells_is_not_ambiguous() -> None:
    table, page = two_cells(repeated=True)
    result = run(table, page)
    assert result.status == "no_findings"
    assert result.checked_cells == 2


def test_text_swapped_between_cells_is_detected() -> None:
    table, page = two_cells()
    cells = [
        table.cells[0].model_copy(update={"text": "84"}),
        table.cells[1].model_copy(update={"text": "42"}),
    ]
    result = run(replace_cells(table, cells), page)
    assert result.status == "review"
    assert [finding.code for finding in result.findings] == ["cell_text_mismatch"] * 2


def test_column_inversion_with_repeated_values_is_detected() -> None:
    table, page = two_cells(repeated=True)
    cells = [
        table.cells[0].model_copy(update={"col": 1}),
        table.cells[1].model_copy(update={"col": 0}),
    ]
    result = run(replace_cells(table, cells), page)
    assert result.status == "review"
    assert codes(result) == {"column_order_inversion"}
    assert result.findings[0].evidence == "cell_geometry"


def test_row_inversion_is_detected() -> None:
    table, page = fixture()
    table = table.model_copy(
        update={
            "bbox": box(10, 10, 110, 70),
            "num_rows": 2,
            "cells": [
                table.cells[0].model_copy(update={"row": 1}),
                Cell(id="lower", row=0, col=0, text="84", bbox=box(10, 40, 110, 70)),
            ],
        }
    )
    page = page.model_copy(
        update={
            "words": page.words
            + [
                SourceWord(text="84", bbox=box(20, 45, 80, 55)),
            ]
        }
    )
    assert codes(run(table, page)) == {"row_order_inversion"}


def test_merged_header_does_not_overlap_logical_data_cells() -> None:
    table, page = two_cells()
    table = table.model_copy(
        update={
            "num_rows": 2,
            "bbox": box(10, 10, 210, 70),
            "cells": [
                Cell(
                    id="header",
                    row=0,
                    col=0,
                    col_span=2,
                    text="Results",
                    column_header=True,
                    bbox=box(10, 10, 210, 40),
                ),
                table.cells[0].model_copy(update={"row": 1, "bbox": box(10, 40, 110, 70)}),
                table.cells[1].model_copy(update={"row": 1, "bbox": box(110, 40, 210, 70)}),
            ],
        }
    )
    page = page.model_copy(
        update={
            "words": [
                SourceWord(text="Results", bbox=box(20, 15, 80, 25)),
                SourceWord(text="42", bbox=box(20, 45, 80, 55)),
                SourceWord(text="84", bbox=box(120, 45, 180, 55)),
            ]
        }
    )
    assert run(table, page).status == "no_findings"


def test_grid_overlap_detects_intersecting_merged_spans() -> None:
    table, page = two_cells()
    table = replace_cells(
        table, [table.cells[0].model_copy(update={"col_span": 2}), table.cells[1]]
    )
    assert "grid_cell_overlap" in codes(run(table, page))


def test_invalid_span_and_duplicate_ids_are_errors() -> None:
    table, page = two_cells()
    cells = [
        table.cells[0].model_copy(update={"col_span": 4}),
        table.cells[1].model_copy(update={"id": "left"}),
    ]
    result = run(replace_cells(table, cells), page)
    assert result.status == "review"
    assert {"invalid_cell_span", "duplicate_cell_id"} <= codes(result)


def test_overlapping_geometry_does_not_produce_false_text_errors() -> None:
    table, page = two_cells()
    table = replace_cells(
        table, [table.cells[0].model_copy(update={"bbox": box(10, 10, 180, 40)}), table.cells[1]]
    )
    result = run(table, page)
    assert result.status == "uncertain"
    assert "cell_geometry_overlap" in codes(result)
    assert "cell_text_mismatch" not in codes(result)
    assert result.checked_cells == 0


def test_boundary_word_is_uncertain() -> None:
    table, page = two_cells()
    page = page.model_copy(update={"words": [SourceWord(text="42", bbox=box(95, 15, 125, 25))]})
    result = run(table, page)
    assert result.status == "uncertain"
    assert "source_assignment_ambiguous" in codes(result)
    assert "missing_cell_text" not in codes(result)


def test_partial_word_coverage_is_uncertain() -> None:
    table, page = fixture()
    page = page.model_copy(update={"words": [SourceWord(text="42", bbox=box(0, 15, 30, 25))]})
    result = run(table, page)
    assert result.status == "uncertain"
    assert codes(result) == {"source_assignment_ambiguous"}


def test_small_coordinate_drift_uses_the_tolerance() -> None:
    table, page = fixture()
    page = page.model_copy(update={"words": [SourceWord(text="42", bbox=box(9.5, 15, 40, 25))]})
    assert run(table, page).status == "no_findings"


def test_duplicate_source_boxes_require_review() -> None:
    table, page = fixture()
    page = page.model_copy(update={"words": [page.words[0], page.words[0]]})
    result = run(table, page)
    assert result.status == "uncertain"
    assert result.checked_cells == 0


@pytest.mark.parametrize("source", ["\ufffd", "\ue001", "a\x00b"])
def test_unreadable_source_text_is_uncertain(source: str) -> None:
    table, page = fixture(source, source)
    assert run(table, page).status == "uncertain"


def test_source_words_outside_all_cells_are_reported_without_claiming_loss() -> None:
    table, page = fixture()
    table = table.model_copy(update={"bbox": box(10, 10, 210, 40)})
    page = page.model_copy(
        update={
            "words": page.words
            + [
                SourceWord(text="Note", bbox=box(120, 15, 180, 25)),
            ]
        }
    )
    result = run(table, page)
    assert result.status == "uncertain"
    assert codes(result) == {"unassigned_source_text"}
    assert result.findings[0].expected_text == "Note"


def test_source_words_outside_the_table_are_ignored() -> None:
    table, page = fixture()
    page = page.model_copy(
        update={
            "words": page.words
            + [
                SourceWord(text="Caption", bbox=box(10, 80, 100, 90)),
            ]
        }
    )
    assert run(table, page).status == "no_findings"


def test_missing_cell_bbox_does_not_fall_back_to_global_token_presence() -> None:
    table, page = fixture()
    table = replace_cells(table, [table.cells[0].model_copy(update={"bbox": None})])
    result = run(table, page)
    assert result.status == "uncertain"
    assert "cell_bbox_missing" in codes(result)
    assert result.checked_cells == 0


def test_missing_table_bbox_keeps_valid_cell_checks_but_marks_scope_uncertain() -> None:
    table, page = fixture()
    result = run(table.model_copy(update={"bbox": None}), page)
    assert result.status == "uncertain"
    assert codes(result) == {"table_bbox_missing"}
    assert result.checked_cells == 1


@pytest.mark.parametrize("target", ["table", "cell"])
def test_boxes_outside_page_are_uncertain(target: str) -> None:
    table, page = fixture()
    outside = box(10, 10, 700, 40)
    if target == "table":
        table = table.model_copy(update={"bbox": outside})
    else:
        table = replace_cells(table, [table.cells[0].model_copy(update={"bbox": outside})])
    result = run(table, page)
    assert result.status == "uncertain"
    assert f"{target}_outside_page" in codes(result)
    assert result.checked_cells == 0


def test_cell_outside_table_is_uncertain() -> None:
    table, page = fixture()
    table = replace_cells(table, [table.cells[0].model_copy(update={"bbox": box(10, 10, 210, 40)})])
    assert "cell_outside_table" in codes(run(table, page))


def test_out_of_bounds_geometry_does_not_create_an_inversion_error() -> None:
    table, page = two_cells()
    table = replace_cells(
        table,
        [
            table.cells[0].model_copy(update={"bbox": box(300, 10, 700, 40)}),
            table.cells[1],
        ],
    )
    result = run(table, page)
    assert result.status == "uncertain"
    assert "column_order_inversion" not in codes(result)


def test_missing_source_page_is_uncertain() -> None:
    table, _ = fixture()
    result = audit_document([table], {})[0]
    assert result.status == "uncertain"
    assert result.checked_cells == 0


def test_wrong_source_page_identity_is_uncertain() -> None:
    table, page = fixture()
    page = page.model_copy(update={"page": 2})
    assert codes(run(table, page)) == {"source_page_missing"}


def test_scanned_page_is_not_treated_as_an_empty_correct_table() -> None:
    table, page = fixture("", "")
    result = run(table, page)
    assert result.status == "uncertain"
    assert codes(result) == {"source_text_unavailable"}


def test_empty_extraction_is_uncertain() -> None:
    table, page = fixture()
    result = run(replace_cells(table, []), page)
    assert result.status == "uncertain"
    assert "no_cells" in codes(result)


def test_unsupported_table_is_not_audited() -> None:
    table, page = fixture("Wrong", "Right")
    result = run(
        table.model_copy(update={"unsupported_reason": "The table spans two pages."}), page
    )
    assert result.status == "uncertain"
    assert codes(result) == {"unsupported_table"}
    assert result.checked_cells == 0


def test_structural_errors_take_priority_over_source_uncertainty() -> None:
    table, _ = fixture()
    table = replace_cells(table, [table.cells[0].model_copy(update={"row_span": 3})])
    result = audit_document([table], {})[0]
    assert result.status == "review"
    assert {finding.severity for finding in result.findings} == {"error", "uncertain"}


@pytest.mark.parametrize("tolerance", [-1, math.inf, math.nan])
def test_invalid_geometric_tolerance_is_rejected(tolerance: float) -> None:
    with pytest.raises(ValueError):
        AuditConfig(geometry_tolerance=tolerance)


@pytest.mark.parametrize("overlap", [-1, 0, 1.1, math.inf, math.nan])
def test_invalid_word_overlap_is_rejected(overlap: float) -> None:
    with pytest.raises(ValueError):
        AuditConfig(min_word_overlap=overlap)


def test_empty_document_returns_no_table_results() -> None:
    assert audit_document([], {}) == []
