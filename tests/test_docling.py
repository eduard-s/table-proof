from __future__ import annotations

import copy
from types import SimpleNamespace

import pytest

from table_proof import BBox, DocumentFormatError, SourcePage, Table, normalize_document


@pytest.fixture
def pages():
    return {1: SourcePage(page=1, width=360, height=240, words=[])}


def test_normalize_preserves_input(pdf_case, pages):
    _, doc = pdf_case
    before = copy.deepcopy(doc)
    tables = normalize_document(doc, pages)
    assert tables[0].cells[4].text == "80"
    assert tables[0].cells[0].column_header
    assert tables[0].bbox == BBox(x0=20, top=40, x1=335, bottom=145)
    assert doc == before


def test_bottom_left_and_page_scale(pdf_case, pages):
    _, doc = pdf_case
    cell = doc["tables"][0]["data"]["table_cells"][0]
    doc["pages"]["1"]["size"] = {"width": 720, "height": 480}
    cell["bbox"] = {"l": 40, "t": 400, "r": 250, "b": 330, "coord_origin": "BOTTOMLEFT"}
    assert normalize_document(doc, pages)[0].cells[0].bbox == BBox(x0=20, top=40, x1=125, bottom=75)


def test_rich_reference_uses_rendered_text(pdf_case, pages):
    _, doc = pdf_case
    cell = doc["tables"][0]["data"]["table_cells"][4]
    cell["ref"] = {"$ref": "#/groups/0"}
    doc["groups"] = [{"children": [{"$ref": "#/texts/0"}]}]
    doc["texts"] = [{"text": "12"}]
    assert cell["text"] == "80"
    assert normalize_document(doc, pages)[0].cells[4].text == "12"


@pytest.mark.parametrize("reference", ["file:///etc/passwd", "#/texts/20", "#/texts/-1"])
def test_invalid_reference_abstains(pdf_case, pages, reference):
    _, doc = pdf_case
    doc["tables"][0]["data"]["table_cells"][0]["ref"] = {"$ref": reference}
    doc["texts"] = []
    assert normalize_document(doc, pages)[0].unsupported_reason


def test_cyclic_reference_abstains(pdf_case, pages):
    _, doc = pdf_case
    doc["tables"][0]["data"]["table_cells"][0]["ref"] = {"$ref": "#/groups/0"}
    doc["groups"] = [{"children": [{"$ref": "#/groups/0"}]}]
    assert "cyclic" in normalize_document(doc, pages)[0].unsupported_reason


def test_multi_page_abstains(pdf_case, pages):
    _, doc = pdf_case
    doc["tables"][0]["prov"].append({"page_no": 2})
    assert "Multi-page" in normalize_document(doc, pages)[0].unsupported_reason


@pytest.mark.parametrize("document", [{}, {"tables": {}}, "bad", [1]])
def test_malformed_document_rejected(document, pages):
    with pytest.raises(DocumentFormatError):
        normalize_document(document, pages)


def test_object_and_result_wrapper(pdf_case, pages):
    _, doc = pdf_case
    obj = SimpleNamespace(model_dump=lambda **kwargs: doc)
    assert normalize_document(SimpleNamespace(document=obj), pages) == normalize_document(
        doc, pages
    )
    assert normalize_document({"document": doc}, pages) == normalize_document(doc, pages)


def test_table_sequence(pages):
    table = Table(id="x", page=1, num_rows=0, num_cols=0, cells=[])
    assert normalize_document([table], pages) == [table]


@pytest.mark.parametrize(
    "field,value",
    [
        ("start_row_offset_idx", True),
        ("end_col_offset_idx", "1"),
        ("row_span", 2),
    ],
)
def test_invalid_offsets(pdf_case, pages, field, value):
    _, doc = pdf_case
    doc["tables"][0]["data"]["table_cells"][0][field] = value
    with pytest.raises(DocumentFormatError):
        normalize_document(doc, pages)


def test_duplicate_table_identity(pdf_case, pages):
    _, doc = pdf_case
    doc["tables"].append(copy.deepcopy(doc["tables"][0]))
    with pytest.raises(DocumentFormatError, match="Duplicate"):
        normalize_document(doc, pages)


def test_unknown_origin(pdf_case, pages):
    _, doc = pdf_case
    doc["tables"][0]["data"]["table_cells"][0]["bbox"]["coord_origin"] = "CENTER"
    with pytest.raises(DocumentFormatError, match="origin"):
        normalize_document(doc, pages)
