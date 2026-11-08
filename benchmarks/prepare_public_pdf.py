"""Get the CC BY 2.0 paper and make a declared text/vector excerpt of Table 2."""

from __future__ import annotations

from benchmarks.common import ROOT, sha256, write_json

URL = "https://link.springer.com/content/pdf/10.1007/s10886-012-0088-8.pdf"
DOI = "https://doi.org/10.1007/s10886-012-0088-8"
SOURCE_SHA256 = "7ae6c3e944cd2116902fcfb278730d0373618e5c7312a7da3372c0b86899fb20"
OUT = ROOT / "fixtures" / "docling_5136"


def prepare() -> None:
    import pymupdf
    import requests

    OUT.mkdir(parents=True, exist_ok=True)
    source = OUT / "source.pdf"
    if not source.exists():
        response = requests.get(URL, timeout=60)
        response.raise_for_status()
        if not response.content.startswith(b"%PDF"):
            raise ValueError("Publisher response is not a PDF")
        source.write_bytes(response.content)
    if sha256(source) != SOURCE_SHA256:
        raise ValueError("Publisher PDF differs from the recorded benchmark source")
    with pymupdf.open(source) as document:
        document.select([5])
        document.save(OUT / "page6.pdf", no_new_id=True)
        page = document[0]
        left, top, right, bottom = 45, 95, 550, 225
        outside = [
            (0, 0, page.rect.width, top),
            (0, bottom, page.rect.width, page.rect.height),
            (0, top, left, bottom),
            (right, top, page.rect.width, bottom),
        ]
        for box in outside:
            page.add_redact_annot(box, fill=(1, 1, 1))
        page.apply_redactions(images=0, graphics=2)
        document.save(OUT / "table2.pdf", no_new_id=True)
    write_json(
        OUT / "source.json",
        {
            "title": (
                "A Novel Synthetic Odorant Blend for Trapping of Malaria "
                "and Other African Mosquito Species"
            ),
            "authors": [
                "Wolfgang R. Mukabana",
                "Collins K. Mweresa",
                "Bruno Otieno",
                "Philemon Omusula",
                "Renate C. Smallegange",
                "Joop J. A. van Loon",
                "Willem Takken",
            ],
            "citation": "Journal of Chemical Ecology 38, 235–244 (2012)",
            "copyright": "The Author(s) 2012",
            "doi": DOI,
            "download_url": URL,
            "license": "CC-BY-2.0",
            "license_url": "https://creativecommons.org/licenses/by/2.0/",
            "license_evidence_url": "https://link.springer.com/article/10.1007/s10886-012-0088-8#rightslink",
            "source_sha256": sha256(source),
            "page6_sha256": sha256(OUT / "page6.pdf"),
            "table_excerpt_sha256": sha256(OUT / "table2.pdf"),
            "transformation": (
                "Copy original page 6. Remove text and vector graphics outside PDF-point "
                "rectangle [45, 95, 550, 225]. Keep table glyphs, values, fonts, positions "
                "and page size. The excerpt is derived source material, not generated content."
            ),
            "original_printed_table": "Table 2",
            "original_pdf_page": 6,
            "issue_note": "Issue 5136 calls this Table 1. The publisher PDF prints Table 2.",
            "preparation_package": {"PyMuPDF": pymupdf.__version__},
        },
    )
    print("Prepared original PDF, unchanged page copy, and declared Table 2 excerpt.")


if __name__ == "__main__":
    prepare()
