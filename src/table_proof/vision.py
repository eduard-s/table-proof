"""Optional, local Table Transformer evidence for PDF table structure."""

from __future__ import annotations

import importlib
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from time import perf_counter
from typing import Any, Literal

from .models import BBox, Cell, Finding, Table

MODEL_ID = "microsoft/table-transformer-structure-recognition-v1.1-all"
MODEL_REVISION = "7587a7ef111d9dcbf8ac695f1376ab7014340a0c"
EVIDENCE = f"table_transformer:{MODEL_ID}@{MODEL_REVISION}"


@dataclass(frozen=True)
class VisionConfig:
    """Model files stay local unless the caller explicitly permits download."""

    allow_download: bool = False
    cache_dir: Path | None = None
    dpi: int = 144
    padding: float = 8.0
    score_threshold: float = 0.8
    uncertainty_threshold: float = 0.35
    max_pixels: int = 12_000_000

    def __post_init__(self) -> None:
        if not 72 <= self.dpi <= 300:
            raise ValueError("dpi must be between 72 and 300.")
        if not math.isfinite(self.padding) or self.padding < 0:
            raise ValueError("padding must be finite and nonnegative.")
        if not 0 < self.uncertainty_threshold < self.score_threshold < 1:
            raise ValueError("Require 0 < uncertainty_threshold < score_threshold < 1.")
        if self.max_pixels < 1:
            raise ValueError("max_pixels must be positive.")


@dataclass(frozen=True)
class VisionRegion:
    label: str
    score: float
    bbox: BBox


@dataclass(frozen=True)
class VisionResult:
    regions: tuple[VisionRegion, ...]
    crop_bbox: BBox
    image_width: int
    image_height: int
    inference_seconds: float
    model_id: str = MODEL_ID
    model_revision: str = MODEL_REVISION


def pixel_box_to_pdf(box: list[float], crop: BBox, image_width: int, image_height: int) -> BBox:
    """Map crop pixels to top-left PDF points using actual rendered dimensions."""
    if len(box) != 4 or not all(math.isfinite(value) for value in box):
        raise ValueError("A pixel box needs four finite values.")
    if image_width <= 0 or image_height <= 0:
        raise ValueError("Image dimensions must be positive.")
    x0, y0, x1, y1 = box
    sx = (crop.x1 - crop.x0) / image_width
    sy = (crop.bottom - crop.top) / image_height
    return BBox(
        x0=crop.x0 + max(0.0, min(float(image_width), x0)) * sx,
        top=crop.top + max(0.0, min(float(image_height), y0)) * sy,
        x1=crop.x0 + max(0.0, min(float(image_width), x1)) * sx,
        bottom=crop.top + max(0.0, min(float(image_height), y1)) * sy,
    )


@lru_cache(maxsize=2)
def _load_model(allow_download: bool, cache_dir: str | None) -> tuple[Any, Any, Any]:
    # Lazy imports keep the normal audit and its installation free of torch.
    torch = importlib.import_module("torch")
    transformers = importlib.import_module("transformers")
    kwargs = {
        "revision": MODEL_REVISION,
        "cache_dir": cache_dir,
        "local_files_only": not allow_download,
        "trust_remote_code": False,
    }
    # The checkpoint stores only longest_edge. DetrImageProcessor 4.x requires
    # both keys; equal limits preserve aspect ratio with a 1000-pixel long side.
    processor = transformers.AutoImageProcessor.from_pretrained(
        MODEL_ID,
        use_fast=False,
        size={"shortest_edge": 1000, "longest_edge": 1000},
        **kwargs,
    )
    model = transformers.TableTransformerForObjectDetection.from_pretrained(
        MODEL_ID,
        use_safetensors=True,
        use_pretrained_backbone=False,
        **kwargs,
    )
    model.to("cpu")
    model.eval()
    return torch, processor, model


def _render_crop(source_pdf: Path, table: Table, config: VisionConfig) -> tuple[Any, BBox]:
    import pdfplumber

    if table.bbox is None:
        raise ValueError("A source table bounding box is required.")
    with pdfplumber.open(source_pdf) as pdf:
        if table.page > len(pdf.pages):
            raise ValueError("The source page does not exist.")
        page = pdf.pages[table.page - 1]
        if page.rotation:
            raise ValueError("Rotated pages are outside the vision scope.")
        px0, py0, _, _ = page.bbox
        box = table.bbox
        if box.x0 < 0 or box.top < 0 or box.x1 > page.width or box.bottom > page.height:
            raise ValueError("The table box is outside the source page.")
        # Normalized Table boxes start at (0, 0), even if MediaBox does not.
        # Keep returned coordinates normalized; translate only the renderer input.
        crop = BBox(
            x0=max(0.0, box.x0 - config.padding),
            top=max(0.0, box.top - config.padding),
            x1=min(page.width, box.x1 + config.padding),
            bottom=min(page.height, box.bottom + config.padding),
        )
        # pdfplumber renders the page before cropping it.
        page_pixels = page.width * page.height * (config.dpi / 72) ** 2
        if page_pixels > config.max_pixels:
            raise ValueError("The page exceeds the configured render pixel limit.")
        cropped_page = page.crop((crop.x0 + px0, crop.top + py0, crop.x1 + px0, crop.bottom + py0))
        if not cropped_page.chars:
            raise ValueError("The table crop has no digital text; scanned tables are unsupported.")
        image = cropped_page.to_image(resolution=config.dpi, antialias=True).original.convert("RGB")
    return image, crop


def detect_structure(
    source_pdf: Path, table: Table, *, config: VisionConfig | None = None
) -> VisionResult:
    """Run the pretrained model on source pixels, without extracted cell text."""
    selected = config or VisionConfig()
    image, crop = _render_crop(source_pdf, table, selected)
    torch, processor, model = _load_model(
        selected.allow_download, str(selected.cache_dir) if selected.cache_dir else None
    )
    start = perf_counter()
    inputs = processor(images=image, return_tensors="pt")
    with torch.inference_mode():
        outputs = model(**inputs)
    result = processor.post_process_object_detection(
        outputs,
        threshold=selected.uncertainty_threshold,
        target_sizes=torch.tensor([[image.height, image.width]]),
    )[0]
    regions = []
    for score, label, raw_box in zip(
        result["scores"].tolist(),
        result["labels"].tolist(),
        result["boxes"].tolist(),
        strict=True,
    ):
        try:
            bbox = pixel_box_to_pdf(raw_box, crop, image.width, image.height)
        except ValueError:
            continue  # Degenerate or entirely off-crop predictions carry no evidence.
        regions.append(VisionRegion(str(model.config.id2label[label]), float(score), bbox))
    return VisionResult(
        regions=tuple(regions),
        crop_bbox=crop,
        image_width=image.width,
        image_height=image.height,
        inference_seconds=perf_counter() - start,
    )


def _finding(
    table: Table,
    code: str,
    message: str,
    *,
    cell: Cell | None = None,
    severity: Literal["error", "uncertain"] = "uncertain",
    expected: str | None = None,
    observed: str | None = None,
) -> Finding:
    return Finding(
        code=code,
        severity=severity,
        table_id=table.id,
        page=table.page,
        cell_id=cell.id if cell else None,
        bbox=cell.bbox if cell else table.bbox,
        message=message,
        expected_text=expected,
        observed_text=observed,
        evidence=EVIDENCE,
    )


def _interval(region: VisionRegion, axis: Literal["row", "col"]) -> tuple[float, float]:
    box = region.bbox
    return (box.top, box.bottom) if axis == "row" else (box.x0, box.x1)


def _ambiguous_axis(regions: list[VisionRegion], axis: Literal["row", "col"]) -> bool:
    for left, right in zip(regions, regions[1:], strict=False):
        a, b = _interval(left, axis)
        c, d = _interval(right, axis)
        if max(0.0, min(b, d) - max(a, c)) > 0.2 * min(b - a, d - c):
            return True
    return False


def _contains(box: BBox, x: float, y: float) -> bool:
    return box.x0 <= x <= box.x1 and box.top <= y <= box.bottom


def _locate(point: float, regions: list[VisionRegion], axis: Literal["row", "col"]) -> list[int]:
    return [
        i
        for i, region in enumerate(regions)
        if _interval(region, axis)[0] < point < _interval(region, axis)[1]
    ]


def compare_structure(
    table: Table, result: VisionResult, *, config: VisionConfig | None = None
) -> list[Finding]:
    """Compare model regions with exported cell indices; abstain on ambiguous grids."""
    selected = config or VisionConfig()
    strong = [r for r in result.regions if r.score >= selected.score_threshold]
    weak = [
        r
        for r in result.regions
        if selected.uncertainty_threshold <= r.score < selected.score_threshold
    ]
    rows = sorted((r for r in strong if r.label == "table row"), key=lambda r: r.bbox.top)
    cols = sorted((r for r in strong if r.label == "table column"), key=lambda r: r.bbox.x0)
    if (
        not rows
        or not cols
        or len(rows) != table.num_rows
        or len(cols) != table.num_cols
        or any(r.label in {"table row", "table column"} for r in weak)
        or _ambiguous_axis(rows, "row")
        or _ambiguous_axis(cols, "col")
        or len([r for r in strong if r.label == "table"]) != 1
    ):
        return [
            _finding(
                table,
                "vision_grid_uncertain",
                "The model grid is ambiguous or differs in size. Review the source table.",
                expected=f"model rows={len(rows)}, columns={len(cols)}",
                observed=f"export rows={table.num_rows}, columns={table.num_cols}",
            )
        ]
    headers = [r for r in strong if r.label == "table column header"]
    spans = [r for r in strong if r.label == "table spanning cell"]
    findings: list[Finding] = []
    for cell in table.cells:
        if cell.bbox is None:
            findings.append(
                _finding(
                    table,
                    "vision_cell_uncertain",
                    "The cell has no source bounding box.",
                    cell=cell,
                )
            )
            continue
        x = (cell.bbox.x0 + cell.bbox.x1) / 2
        y = (cell.bbox.top + cell.bbox.bottom) / 2
        matching_spans = [r for r in spans if _contains(r.bbox, x, y)]
        if len(matching_spans) > 1 or any(
            r.label == "table spanning cell" and _contains(r.bbox, x, y) for r in weak
        ):
            findings.append(
                _finding(
                    table,
                    "vision_cell_uncertain",
                    "Spanning-cell evidence is ambiguous.",
                    cell=cell,
                )
            )
            continue
        if matching_spans:
            span = matching_spans[0].bbox
            ri = [
                i
                for i, r in enumerate(rows)
                if span.top < (r.bbox.top + r.bbox.bottom) / 2 < span.bottom
            ]
            ci = [i for i, r in enumerate(cols) if span.x0 < (r.bbox.x0 + r.bbox.x1) / 2 < span.x1]
        else:
            ri, ci = _locate(y, rows, "row"), _locate(x, cols, "col")
            if cell.row_span > 1 or cell.col_span > 1:
                findings.append(
                    _finding(
                        table,
                        "vision_cell_uncertain",
                        "The model does not establish this merged cell.",
                        cell=cell,
                    )
                )
                continue
        if not ri or not ci or (not matching_spans and (len(ri) != 1 or len(ci) != 1)):
            findings.append(
                _finding(
                    table,
                    "vision_cell_uncertain",
                    "The cell does not map to a unique model region.",
                    cell=cell,
                )
            )
            continue
        source = (ri[0], ci[0], len(ri), len(ci))
        exported = (cell.row, cell.col, cell.row_span, cell.col_span)
        if source != exported:
            findings.append(
                _finding(
                    table,
                    "vision_cell_relation_mismatch",
                    "Source-image regions disagree with the exported cell position or span.",
                    cell=cell,
                    severity="error",
                    expected=str(source),
                    observed=str(exported),
                )
            )
        # Projected row headers are not ordinary row headers. Do not equate them.
        if headers and not any(r.label == "table column header" for r in weak):
            is_header = any(_contains(r.bbox, x, y) for r in headers)
            if is_header != cell.column_header:
                findings.append(
                    _finding(
                        table,
                        "vision_column_header_mismatch",
                        "Source-image header regions disagree with the exported header flag.",
                        cell=cell,
                        severity="error",
                        expected=str(is_header),
                        observed=str(cell.column_header),
                    )
                )
        elif cell.column_header:
            findings.append(
                _finding(
                    table,
                    "vision_header_uncertain",
                    "The model does not establish the column header.",
                    cell=cell,
                )
            )
    return findings


def inspect_table(
    source_pdf: Path, table: Table, *, config: VisionConfig | None = None
) -> list[Finding]:
    """Return review findings. Missing models and unsupported inputs are uncertain."""
    if table.unsupported_reason:
        return [_finding(table, "vision_unsupported", table.unsupported_reason)]
    if not table.cells or table.num_rows == 0 or table.num_cols == 0:
        return [_finding(table, "vision_unsupported", "The exported table is empty.")]
    try:
        result = detect_structure(source_pdf, table, config=config)
    except (ImportError, OSError, RuntimeError, ValueError) as exc:
        return [
            _finding(
                table,
                "vision_unavailable",
                f"Vision inspection did not complete: {type(exc).__name__}: {str(exc)[:240]}",
            )
        ]
    return compare_structure(table, result, config=config)
