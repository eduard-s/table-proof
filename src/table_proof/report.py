"""Write local reports with escaped text and optional source images."""

from __future__ import annotations

import base64
import hashlib
import io
import json
from html import escape
from pathlib import Path

import pdfplumber

from .models import AuditReport


def export_json(report: AuditReport, path: str | Path) -> None:
    data = report.model_dump(mode="json")
    data["status"] = report.status
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _source_images(report: AuditReport, source_pdf: str) -> str:
    path = Path(source_pdf)
    with path.open("rb") as file:
        if hashlib.file_digest(file, "sha256").hexdigest() != report.source_sha256:
            raise ValueError("The evidence PDF does not match the audited source hash.")
    pages = sorted({table.page for table in report.tables})
    blocks: list[str] = []
    with pdfplumber.open(path) as pdf:
        for page_no in pages[:10]:
            if page_no < 1 or page_no > len(pdf.pages):
                continue
            page = pdf.pages[page_no - 1]
            resolution = min(100.0, 1600 * 72 / max(page.width, page.height))
            img = page.to_image(resolution=resolution, force_mediabox=True).original
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
            boxes = []
            for table in report.tables:
                if table.page != page_no:
                    continue
                for finding in table.findings:
                    box = finding.bbox
                    if box is None:
                        continue
                    x = max(0.0, box.x0 / page.width * 100)
                    y = max(0.0, box.top / page.height * 100)
                    width = min(100.0 - x, (box.x1 - box.x0) / page.width * 100)
                    height = min(100.0 - y, (box.bottom - box.top) / page.height * 100)
                    if width <= 0 or height <= 0:
                        continue
                    boxes.append(
                        f'<span class="box {finding.severity}" '
                        f'style="left:{x:.4f}%;top:{y:.4f}%;width:{width:.4f}%;'
                        f'height:{height:.4f}%" title="{escape(finding.message, quote=True)}">'
                        '<span class="sr-only">Suspected cell</span></span>'
                    )
            blocks.append(
                f'<figure><figcaption>Source page {page_no}</figcaption><div class="page">'
                f'<img alt="Source PDF page {page_no}" src="data:image/png;base64,{encoded}">'
                f"{''.join(boxes)}</div></figure>"
            )
    if len(pages) > 10:
        blocks.append("<p>The report shows the first 10 source pages.</p>")
    return "".join(blocks)


def export_html(report: AuditReport, path: str | Path, *, source_pdf: str | None = None) -> None:
    destination = Path(path)
    if source_pdf:
        source = Path(source_pdf)
        if destination.resolve() == source.resolve() or (
            destination.exists() and source.exists() and destination.samefile(source)
        ):
            raise ValueError("The HTML report must not replace the source PDF.")
    tables = []
    for table in report.tables:
        findings = []
        for finding in table.findings:
            values = ""
            if finding.expected_text is not None:
                values += f"<dt>Source evidence</dt><dd>{escape(finding.expected_text)}</dd>"
            if finding.observed_text is not None:
                values += f"<dt>Extracted text</dt><dd>{escape(finding.observed_text)}</dd>"
            findings.append(
                f'<li class="finding {finding.severity}"><strong>{escape(finding.code)}</strong>'
                f"<p>{escape(finding.message)}</p><dl><dt>Cell</dt>"
                f"<dd>{escape(finding.cell_id or 'Table')}</dd>{values}"
                f"<dt>Evidence method</dt><dd>{escape(finding.evidence)}</dd></dl></li>"
            )
        tables.append(
            f'<section><div class="table-title"><h2>{escape(table.table_id)}</h2>'
            f'<span class="badge">{table.status}</span></div>'
            f"<p>Page {table.page} · Cells with source evidence: "
            f"{table.checked_cells} / {table.total_cells}</p>"
            f'<ul class="findings">{"".join(findings)}</ul></section>'
        )
    limitations = "".join(f"<li>{escape(text)}</li>" for text in report.limitations)
    images = _source_images(report, source_pdf) if source_pdf else ""
    markup = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy"
content="default-src 'none'; img-src data:; style-src 'unsafe-inline'">
<title>TableProof · {escape(report.source_name)}</title>
<style>
:root {{ color-scheme: light;
font-family: ui-sans-serif, system-ui, sans-serif;
color:#182936;
background:#f2f5f4;
}}
body {{ margin:0;
}} main {{ max-width:1060px;
margin:auto;
padding:36px 22px;
}}
header {{ border-top:5px solid #0a7368;
padding:22px 0;
}}
.eyebrow {{ color:#0a7368;
text-transform:uppercase;
letter-spacing:.14em;
font-size:12px;
font-weight:700;
}}
h1 {{ font-size:34px;
margin:10px 0;
overflow-wrap:anywhere;
}}
h2 {{ font-size:19px;
margin:0;
overflow-wrap:anywhere;
}} p {{ line-height:1.6;
}}
.badge {{ background:#dceae6;
color:#174e43;
border-radius:4px;
padding:6px 10px;
font:600 13px monospace;
}}
.table-title {{ display:flex;
justify-content:space-between;
gap:16px;
flex-wrap:wrap;
}}
section, figure {{ background:white;
border:1px solid #d4dfdc;
padding:22px;
margin:18px 0;
border-radius:7px;
}}
.findings {{ list-style:none;
margin:0;
padding:0;
}} .finding {{ padding:18px;
margin:12px 0;
background:#faf5ef;
border-left:4px solid #ac5a21;
}}
.finding.uncertain {{ background:#f3f1e5;
border-left-color:#877521;
}}
dl {{ display:grid;
grid-template-columns:150px 1fr;
gap:8px 14px;
font-size:14px;
}}
dt {{ color:#57646c;
}} dd {{ margin:0;
white-space:pre-wrap;
overflow-wrap:anywhere;
}}
.page {{ position:relative;
margin:auto;
max-width:800px;
}} img {{ width:100%;
display:block;
}}
.box {{ position:absolute;
box-sizing:border-box;
border:2px solid #b64222;
background:#ff6b3625;
}}
.box.uncertain {{ border-color:#9a7b14;
background:#ffdf3020;
}}
figcaption {{ margin-bottom:16px;
font-weight:600;
}}
.sr-only {{ position:absolute;
width:1px;
height:1px;
overflow:hidden;
clip:rect(0,0,0,0);
}}
footer {{ font-size:12px;
color:#5b6870;
overflow-wrap:anywhere;
}}
@media(max-width:600px) {{ dl {{ grid-template-columns:1fr;
}} section,figure {{ padding:14px;
}} h1 {{ font-size:26px;
}} }}
</style></head><body><main>
<header><div class="eyebrow">TableProof / Evidence report</div>
<h1>{escape(report.source_name)}</h1><span class="badge">{report.status}</span>
<p>Examine each alert against the original source. A report does not certify the table.</p></header>
{"".join(tables) or "<section><p>No tables were supplied. Coverage is unknown.</p></section>"}
{images}<section><h2>Limits</h2><ul>{limitations}</ul></section>
<footer>TableProof {escape(report.engine_version)}
· Report schema {escape(report.schema_version)}<br>
Source SHA-256: {escape(report.source_sha256)}</footer>
</main></body></html>
"""
    Path(path).write_text(markup, encoding="utf-8")
