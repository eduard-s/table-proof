from __future__ import annotations

from copy import deepcopy

from hypothesis import given
from hypothesis import strategies as st

from table_proof.auditor import audit_document
from table_proof.models import BBox, Cell, SourcePage, SourceWord, Table


def make_grid(values: list[str]) -> tuple[Table, SourcePage]:
    cells: list[Cell] = []
    words: list[SourceWord] = []
    for index, value in enumerate(values):
        row, col = divmod(index, 2)
        x, y = 10 + col * 100, 10 + row * 30
        cells.append(
            Cell(
                id=f"c{index}",
                row=row,
                col=col,
                text=value,
                bbox=BBox(x0=x, top=y, x1=x + 100, bottom=y + 30),
            )
        )
        words.append(
            SourceWord(
                text=value,
                bbox=BBox(x0=x + 10, top=y + 5, x1=x + 70, bottom=y + 15),
            )
        )
    table = Table(
        id="t",
        page=1,
        num_rows=2,
        num_cols=2,
        cells=cells,
        bbox=BBox(x0=10, top=10, x1=210, bottom=70),
    )
    return table, SourcePage(page=1, width=600, height=800, words=words)


@given(
    st.lists(st.integers(min_value=-100000, max_value=100000).map(str), min_size=4, max_size=4),
    st.permutations([0, 1, 2, 3]),
    st.permutations([0, 1, 2, 3]),
)
def test_equivalent_input_orders_have_identical_results(
    values: list[str],
    cell_order: list[int],
    word_order: list[int],
) -> None:
    table, page = make_grid(values)
    expected = audit_document([table], {1: page})
    reordered_table = table.model_copy(update={"cells": [table.cells[i] for i in cell_order]})
    reordered_page = page.model_copy(update={"words": [page.words[i] for i in word_order]})
    actual = audit_document([reordered_table], {1: reordered_page})
    assert actual == expected
    assert actual[0].status == "no_findings"


@given(st.permutations([0, 1, 2, 3]), st.permutations([0, 1, 2, 3]))
def test_error_reports_are_invariant_to_input_order(
    cell_order: list[int],
    word_order: list[int],
) -> None:
    table, page = make_grid(["10", "20", "30", "40"])
    changed = [cell.model_copy(update={"text": "wrong"}) for cell in table.cells]
    table = table.model_copy(update={"cells": changed})
    expected = audit_document([table], {1: page})
    table = table.model_copy(update={"cells": [table.cells[i] for i in cell_order]})
    page = page.model_copy(update={"words": [page.words[i] for i in word_order]})
    assert audit_document([table], {1: page}) == expected


@given(st.lists(st.text(min_size=0, max_size=30), min_size=4, max_size=4))
def test_audit_does_not_change_input_models(values: list[str]) -> None:
    table, page = make_grid(values)
    tables, pages = [table], {1: page}
    original_tables, original_pages = deepcopy(tables), deepcopy(pages)
    audit_document(tables, pages)
    assert tables == original_tables
    assert pages == original_pages


@given(st.integers(min_value=1, max_value=9999), st.integers(min_value=1, max_value=99))
def test_decimal_point_loss_is_never_a_success(whole: int, fraction: int) -> None:
    value = f"{whole}.{fraction:02d}"
    table, page = make_grid([value] * 4)
    cells = [cell.model_copy(update={"text": value.replace(".", "")}) for cell in table.cells]
    result = audit_document([table.model_copy(update={"cells": cells})], {1: page})[0]
    assert result.status == "review"
    assert len(result.findings) == 4
    assert all(finding.code == "cell_text_mismatch" for finding in result.findings)
