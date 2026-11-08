"""Read digital PDF words without a model or network request."""

from __future__ import annotations

from pathlib import Path

import pdfplumber

from .models import BBox, SourcePage, SourceWord


def read_pdf_pages(source_pdf: str | Path) -> dict[int, SourcePage]:
    pages: dict[int, SourcePage] = {}
    with pdfplumber.open(source_pdf) as document:
        for index, page in enumerate(document.pages, 1):
            left, top, _, _ = page.bbox
            words = []
            for word in page.dedupe_chars().extract_words(
                x_tolerance=2, y_tolerance=2, keep_blank_chars=False, extra_attrs=["size"]
            ):
                x0, x1 = float(word["x0"]) - left, float(word["x1"]) - left
                y0, y1 = float(word["top"]) - top, float(word["bottom"]) - top
                if x1 > x0 and y1 > y0:
                    words.append(
                        SourceWord(text=word["text"], bbox=BBox(x0=x0, top=y0, x1=x1, bottom=y1))
                    )
            pages[index] = SourcePage(page=index, width=page.width, height=page.height, words=words)
    return pages
