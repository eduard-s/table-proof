"""Read Docling JSON and objects without a Docling runtime dependency."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .models import BBox, Cell, SourcePage, Table


class DocumentFormatError(ValueError):
    """The input does not match a supported document format."""


def _mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise DocumentFormatError(f"{name} must be an object.")
    return value


def _integer(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise DocumentFormatError(f"{name} must be an integer.")
    return int(value)


def _box(value: Any, page_height: float, scale_x: float, scale_y: float) -> BBox | None:
    if value is None:
        return None
    raw = _mapping(value, "bbox")
    origin = raw.get("coord_origin", "TOPLEFT")
    if origin not in {"TOPLEFT", "BOTTOMLEFT"}:
        raise DocumentFormatError(f"Unsupported coordinate origin: {origin}")
    try:
        left, right = float(raw["l"]) * scale_x, float(raw["r"]) * scale_x
        top, bottom = float(raw["t"]) * scale_y, float(raw["b"]) * scale_y
    except (KeyError, TypeError, ValueError) as error:
        raise DocumentFormatError("A Docling box needs numeric l, t, r, and b values.") from error
    if origin == "BOTTOMLEFT":
        top, bottom = page_height - top, page_height - bottom
    return BBox(x0=left, top=top, x1=right, bottom=bottom)


def _reference_text(document: Mapping[str, Any], reference: Any, visited: set[str]) -> str:
    raw = _mapping(reference, "ref")
    pointer = raw.get("$ref")
    if not isinstance(pointer, str) or not pointer.startswith("#/"):
        raise DocumentFormatError("A rich cell needs a local JSON reference.")
    if pointer in visited or len(visited) >= 32:
        raise DocumentFormatError("A rich cell has a cyclic or excessive reference chain.")
    node: Any = document
    try:
        for token in pointer[2:].split("/"):
            token = token.replace("~1", "/").replace("~0", "~")
            if isinstance(node, list):
                if not token.isdecimal():
                    raise KeyError(token)
                node = node[int(token)]
            else:
                node = node[token]
    except (KeyError, IndexError, TypeError) as error:
        raise DocumentFormatError(f"Unresolved rich cell reference: {pointer}") from error
    item = _mapping(node, "Referenced item")
    if "text" in item:
        if not isinstance(item["text"], str):
            raise DocumentFormatError("Referenced text must be a string.")
        return str(item["text"])
    children = item.get("children", [])
    if not isinstance(children, list):
        raise DocumentFormatError("Referenced children must be a list.")
    return " ".join(_reference_text(document, child, visited | {pointer}) for child in children)


def normalize_document(document: Any, pages: Mapping[int, SourcePage]) -> list[Table]:
    """Resolve rendered rich-cell text and normalize source coordinates."""
    if isinstance(document, Sequence) and not isinstance(document, (str, bytes)):
        if all(isinstance(table, Table) for table in document):
            return list(document)
        raise DocumentFormatError("A table sequence must contain Table objects.")
    if hasattr(document, "document"):
        document = document.document
    if hasattr(document, "model_dump"):
        document = document.model_dump(mode="json")
    root = _mapping(document, "Document")
    if "document" in root and "tables" not in root:
        root = _mapping(root["document"], "document")
    raw_tables = root.get("tables")
    if not isinstance(raw_tables, list):
        raise DocumentFormatError("A Docling document must contain a tables list.")
    declared_pages = _mapping(root.get("pages", {}), "pages")
    tables: list[Table] = []
    seen: set[str] = set()
    for table_index, raw_table in enumerate(raw_tables):
        raw = _mapping(raw_table, "Table")
        table_id = str(raw.get("self_ref", f"#/tables/{table_index}"))
        if table_id in seen:
            raise DocumentFormatError(f"Duplicate table reference: {table_id}")
        seen.add(table_id)
        data = _mapping(raw.get("data"), "Table data")
        rows = _integer(data.get("num_rows"), "num_rows")
        cols = _integer(data.get("num_cols"), "num_cols")
        provenance = raw.get("prov", [])
        if not isinstance(provenance, list):
            raise DocumentFormatError("Table provenance must be a list.")
        reason: str | None = None
        if len(provenance) != 1:
            reason = "The table needs exactly one source page. Multi-page tables are unsupported."
        prov = _mapping(provenance[0], "Provenance") if provenance else {}
        page_no = _integer(prov.get("page_no", 1), "page_no")
        source_page = pages.get(page_no)
        size = _mapping(
            _mapping(declared_pages.get(str(page_no), {}), "Page").get("size", {}), "Page size"
        )
        height = source_page.height if source_page else float(size.get("height", 1))
        width = source_page.width if source_page else float(size.get("width", 1))
        declared_width = float(size.get("width", width))
        declared_height = float(size.get("height", height))
        if declared_width <= 0 or declared_height <= 0:
            raise DocumentFormatError("Declared page dimensions must be positive.")
        sx, sy = width / declared_width, height / declared_height
        cells: list[Cell] = []
        raw_cells = data.get("table_cells")
        if not isinstance(raw_cells, list):
            raise DocumentFormatError("Table data must contain a table_cells list.")
        for index, raw_cell in enumerate(raw_cells):
            cell = _mapping(raw_cell, "Cell")
            text = cell.get("text", "")
            if not isinstance(text, str):
                raise DocumentFormatError("Cell text must be a string.")
            if cell.get("ref") is not None:
                try:
                    text = _reference_text(root, cell["ref"], set())
                except DocumentFormatError as error:
                    reason = str(error)
            row = _integer(cell.get("start_row_offset_idx"), "start_row_offset_idx")
            col = _integer(cell.get("start_col_offset_idx"), "start_col_offset_idx")
            row_end = _integer(cell.get("end_row_offset_idx"), "end_row_offset_idx")
            col_end = _integer(cell.get("end_col_offset_idx"), "end_col_offset_idx")
            row_span, col_span = row_end - row, col_end - col
            if row_span != cell.get("row_span", row_span) or col_span != cell.get(
                "col_span", col_span
            ):
                raise DocumentFormatError("Cell spans disagree with their start and end offsets.")
            cells.append(
                Cell(
                    id=f"{table_id}/cells/{index}",
                    row=row,
                    col=col,
                    text=text,
                    bbox=_box(cell.get("bbox"), height, sx, sy),
                    row_span=row_span,
                    col_span=col_span,
                    column_header=bool(cell.get("column_header", False)),
                    row_header=bool(cell.get("row_header", False)),
                )
            )
        tables.append(
            Table(
                id=table_id,
                page=page_no,
                bbox=_box(prov.get("bbox"), height, sx, sy),
                num_rows=rows,
                num_cols=cols,
                cells=cells,
                unsupported_reason=reason,
            )
        )
    return tables
