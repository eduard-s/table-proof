"""Geometry and abstention tests; normal test runs never fetch model weights."""

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from table_proof import vision
from table_proof.models import BBox, Cell, Table
from table_proof.vision import VisionConfig, VisionRegion, VisionResult


def box(x0: float, top: float, x1: float, bottom: float) -> BBox:
    return BBox(x0=x0, top=top, x1=x1, bottom=bottom)


def table() -> Table:
    return Table(
        id="t1",
        page=1,
        bbox=box(100, 200, 300, 300),
        num_rows=2,
        num_cols=2,
        cells=[
            Cell(
                id=f"r{r}c{c}",
                row=r,
                col=c,
                text=str(r * 2 + c),
                bbox=box(110 + c * 100, 210 + r * 50, 190 + c * 100, 240 + r * 50),
                column_header=r == 0,
            )
            for r in range(2)
            for c in range(2)
        ],
    )


def result() -> VisionResult:
    return VisionResult(
        crop_bbox=box(100, 200, 300, 300),
        image_width=400,
        image_height=200,
        inference_seconds=0.01,
        regions=(
            VisionRegion("table", 0.99, box(100, 200, 300, 300)),
            VisionRegion("table row", 0.99, box(100, 200, 300, 250)),
            VisionRegion("table row", 0.99, box(100, 250, 300, 300)),
            VisionRegion("table column", 0.99, box(100, 200, 200, 300)),
            VisionRegion("table column", 0.99, box(200, 200, 300, 300)),
            VisionRegion("table column header", 0.99, box(100, 200, 300, 250)),
        ),
    )


def test_crop_pixel_coordinates_include_offset_and_independent_scale() -> None:
    mapped = vision.pixel_box_to_pdf([20, 30, 180, 270], box(70, 90, 170, 190), 200, 300)
    assert mapped == box(80, 100, 160, 180)


def test_pixel_coordinates_clip_small_model_overshoot() -> None:
    assert vision.pixel_box_to_pdf([-1, -1, 201, 301], box(70, 90, 170, 190), 200, 300) == (
        box(70, 90, 170, 190)
    )


@pytest.mark.parametrize("coords", [[1, 2, 0, 3], [float("nan"), 0, 1, 2], [0, 1, 2]])
def test_invalid_prediction_boxes_fail(coords: list[float]) -> None:
    with pytest.raises(ValueError):
        vision.pixel_box_to_pdf(coords, box(0, 0, 100, 100), 100, 100)


def test_matching_grid_has_no_findings() -> None:
    assert vision.compare_structure(table(), result()) == []


def test_source_grid_catches_exported_position_change_with_unchanged_text() -> None:
    clean = table()
    cells = list(clean.cells)
    cells[3] = cells[3].model_copy(update={"col": 0})
    findings = vision.compare_structure(clean.model_copy(update={"cells": cells}), result())
    assert [f.code for f in findings] == ["vision_cell_relation_mismatch"]
    assert findings[0].expected_text == "(1, 1, 1, 1)"
    assert findings[0].observed_text == "(1, 0, 1, 1)"
    assert findings[0].severity == "error"
    assert vision.MODEL_REVISION in findings[0].evidence


def test_header_flag_uses_image_header_region() -> None:
    clean = table()
    cells = [c.model_copy(update={"column_header": False}) for c in clean.cells]
    findings = vision.compare_structure(clean.model_copy(update={"cells": cells}), result())
    assert {f.cell_id for f in findings} == {"r0c0", "r0c1"}
    assert all(f.code == "vision_column_header_mismatch" for f in findings)


def test_count_disagreement_is_uncertain_not_false_error() -> None:
    findings = vision.compare_structure(table().model_copy(update={"num_rows": 3}), result())
    assert len(findings) == 1
    assert findings[0].code == "vision_grid_uncertain"
    assert findings[0].severity == "uncertain"


def test_weak_axis_region_prevents_confident_grid_comparison() -> None:
    base = result()
    extra = VisionRegion("table row", 0.6, box(100, 210, 300, 240))
    changed = VisionResult(base.regions + (extra,), base.crop_bbox, 400, 200, 0.01)
    assert vision.compare_structure(table(), changed)[0].code == "vision_grid_uncertain"


def test_overlapping_row_regions_are_ambiguous_even_when_count_matches() -> None:
    base = result()
    regions = list(base.regions)
    regions[2] = VisionRegion("table row", 0.99, box(100, 220, 300, 300))
    changed = VisionResult(tuple(regions), base.crop_bbox, 400, 200, 0.01)
    assert vision.compare_structure(table(), changed)[0].code == "vision_grid_uncertain"


def test_model_spanning_cell_checks_export_span() -> None:
    base = result()
    extra = VisionRegion("table spanning cell", 0.99, box(100, 250, 300, 300))
    merged = Cell(id="merged", row=1, col=0, text="Both", bbox=box(140, 260, 260, 290), col_span=2)
    current = table().model_copy(update={"cells": [merged]})
    changed = VisionResult(base.regions + (extra,), base.crop_bbox, 400, 200, 0.01)
    assert vision.compare_structure(current, changed) == []
    broken = current.model_copy(update={"cells": [merged.model_copy(update={"col_span": 1})]})
    assert vision.compare_structure(broken, changed)[0].code == "vision_cell_relation_mismatch"


def test_merged_cell_without_model_span_abstains() -> None:
    cell = table().cells[3].model_copy(update={"col_span": 2})
    findings = vision.compare_structure(table().model_copy(update={"cells": [cell]}), result())
    assert [f.code for f in findings] == ["vision_cell_uncertain"]


def test_projected_header_does_not_overwrite_ordinary_row_header_semantics() -> None:
    clean = table()
    cells = [c.model_copy(update={"row_header": True}) for c in clean.cells]
    assert vision.compare_structure(clean.model_copy(update={"cells": cells}), result()) == []


def test_missing_model_becomes_uncertain(monkeypatch: pytest.MonkeyPatch) -> None:
    def unavailable(*args: Any, **kwargs: Any) -> VisionResult:
        raise OSError("The pinned model is not in the local cache.")

    monkeypatch.setattr(vision, "detect_structure", unavailable)
    findings = vision.inspect_table(Path("unused.pdf"), table())
    assert findings[0].code == "vision_unavailable"
    assert findings[0].severity == "uncertain"


def test_loader_pins_weights_and_never_downloads_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []

    def load(name: str, **kwargs: Any) -> Any:
        calls.append({"name": name, **kwargs})
        return SimpleNamespace(to=lambda device: None, eval=lambda: None)

    fake = SimpleNamespace(
        AutoImageProcessor=SimpleNamespace(from_pretrained=load),
        TableTransformerForObjectDetection=SimpleNamespace(from_pretrained=load),
    )
    monkeypatch.setattr(vision.importlib, "import_module", lambda name: fake)
    vision._load_model.cache_clear()
    try:
        vision._load_model(False, None)
    finally:
        vision._load_model.cache_clear()
    assert len(calls) == 2
    assert all(call["local_files_only"] is True for call in calls)
    assert all(call["revision"] == vision.MODEL_REVISION for call in calls)
    assert all(call["trust_remote_code"] is False for call in calls)
    assert calls[1]["use_safetensors"] is True
    assert calls[1]["use_pretrained_backbone"] is False


def test_real_render_preserves_pdf_crop_coordinates(tmp_path: Path) -> None:
    from reportlab.pdfgen.canvas import Canvas

    path = tmp_path / "source.pdf"
    canvas = Canvas(str(path), pagesize=(400, 500))
    canvas.drawString(110, 275, "Header")
    canvas.save()
    image, crop = vision._render_crop(path, table(), VisionConfig(dpi=144, padding=0))
    assert crop == box(100, 200, 300, 300)
    assert image.size == (400, 200)


def test_image_only_table_crop_is_outside_scope(tmp_path: Path) -> None:
    from reportlab.pdfgen.canvas import Canvas

    path = tmp_path / "no-text.pdf"
    canvas = Canvas(str(path), pagesize=(400, 500))
    canvas.rect(100, 200, 200, 100)
    canvas.save()
    with pytest.raises(ValueError, match="no digital text"):
        vision._render_crop(path, table(), VisionConfig())


def test_render_translates_nonzero_mediabox_and_returns_normalized_crop(tmp_path: Path) -> None:
    from reportlab.pdfgen.canvas import Canvas

    path = tmp_path / "offset-page.pdf"
    canvas = Canvas(str(path), pagesize=(360, 240))
    canvas.drawString(40, 180, "42")
    canvas.save()
    old = b"/MediaBox [ 0 0 360 240 ]"
    new = b"/MediaBox [20 30 380 270]"
    original = path.read_bytes()
    assert old in original
    assert len(old) == len(new)  # Preserve xref offsets in this test PDF.
    path.write_bytes(original.replace(old, new))
    normalized = table().model_copy(update={"bbox": box(10, 70, 50, 105)})
    image, crop = vision._render_crop(path, normalized, VisionConfig(dpi=144, padding=0))
    assert crop == box(10, 70, 50, 105)
    assert image.size == (80, 70)
    assert image.getextrema()[0][0] < 100  # The source text is inside the rendered crop.
    assert vision.pixel_box_to_pdf([0, 0, 80, 70], crop, 80, 70) == normalized.bbox


def test_unsupported_table_does_not_load_model(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> VisionResult:
        raise AssertionError("An unsupported table must not run inference.")

    monkeypatch.setattr(vision, "detect_structure", forbidden)
    unsupported = table().model_copy(update={"unsupported_reason": "Cross-page table."})
    findings = vision.inspect_table(Path("unused.pdf"), unsupported)
    assert findings[0].code == "vision_unsupported"
    assert findings[0].severity == "uncertain"


@pytest.mark.parametrize(
    "kwargs", [{"dpi": 30}, {"padding": -1}, {"max_pixels": 0}, {"score_threshold": 0.2}]
)
def test_configuration_rejects_invalid_limits(kwargs: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        VisionConfig(**kwargs)
