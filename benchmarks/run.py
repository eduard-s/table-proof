"""Run every registered case, keep execution failures, and publish stratified counts."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import platform
import re
from collections import Counter, defaultdict
from collections.abc import Callable
from pathlib import Path
from typing import Any

from benchmarks.common import ROOT, sha256, write_json

PDFMUX_COMMIT = "5662a29c634b24bf02f162e0d18ced9ecf8f0fd4"


def load_cases() -> list[dict[str, Any]]:
    cases = [
        json.loads(path.read_text())
        for path in sorted((ROOT / "fixtures").rglob("*.manifest.json"))
    ]
    if not cases:
        raise ValueError("No benchmark cases found")
    ids = [case["id"] for case in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate benchmark case IDs")
    for case in cases:
        for path_key, hash_key in (
            ("source_pdf", "source_sha256"),
            ("extracted_json", "extracted_sha256"),
        ):
            if sha256(ROOT / case[path_key]) != case[hash_key]:
                raise ValueError(f"Fixture hash differs: {case['id']} {path_key}")
    return cases


def resolve_pointer(document: dict, ref: str) -> dict:
    node: Any = document
    if not ref.startswith("#/"):
        raise ValueError(f"Unsupported fixture ref: {ref}")
    for component in ref[2:].split("/"):
        component = component.replace("~1", "/").replace("~0", "~")
        node = node[int(component)] if isinstance(node, list) else node[component]
    return node


def resolved_text(document: dict, cell: dict) -> str:
    """Independent baseline serialization: rich cell refs govern rendered content."""
    if "ref" not in cell:
        return cell.get("text", "")
    seen: set[str] = set()

    def walk(ref: str) -> list[str]:
        if ref in seen:
            raise ValueError("Cyclic rich-cell reference")
        seen.add(ref)
        node = resolve_pointer(document, ref)
        if "text" in node:
            return [node["text"]]
        return [text for child in node.get("children", []) for text in walk(child["$ref"])]

    return " ".join(walk(cell["ref"]["$ref"]))


def page_markdown(document: dict) -> dict[str, str]:
    pages: dict[str, list[str]] = defaultdict(list)
    for table in document.get("tables", []):
        data = table["data"]
        grid = [[""] * data["num_cols"] for _ in range(data["num_rows"])]
        for cell in data["table_cells"]:
            grid[cell["start_row_offset_idx"]][cell["start_col_offset_idx"]] = resolved_text(
                document, cell
            )
        rows = ["| " + " | ".join(row) + " |" for row in grid]
        if rows:
            rows.insert(1, "| " + " | ".join(["---"] * data["num_cols"]) + " |")
        pages[str(table["prov"][0]["page_no"])].append("\n".join(rows))
    return {page: "\n\n".join(tables) for page, tables in pages.items()}


def token_multiset(source: Path, document: dict) -> dict:
    import pdfplumber

    with pdfplumber.open(source) as pdf:
        source_text = " ".join(page.extract_text() or "" for page in pdf.pages)
    extracted_text = " ".join(
        resolved_text(document, cell)
        for table in document.get("tables", [])
        for cell in table["data"]["table_cells"]
    )
    if not source_text.strip():
        return {"status": "uncertain", "reason": "No digital source text"}

    def tokens(text):
        return Counter(re.findall(r"\w+(?:[.,]\w+)*", text.casefold()))

    source_tokens, extracted_tokens = tokens(source_text), tokens(extracted_text)
    return {
        "status": "no_findings" if source_tokens == extracted_tokens else "review",
        "missing": dict(source_tokens - extracted_tokens),
        "extra": dict(extracted_tokens - source_tokens),
    }


def structural_validity(source: Path, document: dict) -> dict:
    del source
    problems = []
    if not document.get("tables"):
        problems.append("No tables supplied")
    for index, table in enumerate(document.get("tables", [])):
        data = table["data"]
        covered: Counter = Counter()
        rows, cols = data["num_rows"], data["num_cols"]
        for cell in data["table_cells"]:
            for row in range(cell["start_row_offset_idx"], cell["end_row_offset_idx"]):
                for col in range(cell["start_col_offset_idx"], cell["end_col_offset_idx"]):
                    covered[row, col] += 1
        expected = {(row, col) for row in range(rows) for col in range(cols)}
        if set(covered) != expected or any(value != 1 for value in covered.values()):
            problems.append(f"Table {index}: invalid grid coverage")
    return {"status": "review" if problems else "no_findings", "problems": problems}


def tableproof(source: Path, document: dict) -> dict:
    from table_proof import audit_tables

    report = audit_tables(source, document)
    return {"status": report.status, "report": report.model_dump(mode="json")}


def pdfmux(source: Path, document: dict) -> dict:
    from pdfmux.verifier import verify_extraction

    dist = importlib.metadata.distribution("pdfmux")
    direct = dist.read_text("direct_url.json") or ""
    if PDFMUX_COMMIT not in direct:
        raise RuntimeError(f"Install pdfmux from commit {PDFMUX_COMMIT}")
    # Real public API; no thresholds or source-text overrides. Rich references
    # are materialized to page Markdown because pdfmux does not parse Docling refs.
    manifest = verify_extraction(
        source,
        page_markdown(document),
        engine="docling-json-materialized",
        check_numeric_literals=True,
    )
    raw = manifest.to_dict()
    verdicts = {page["verdict"].lower() for page in raw["pages"]}
    if verdicts & {"review", "fail"}:
        status = "review"
    elif "unverifiable" in verdicts or not verdicts:
        status = "uncertain"
    else:
        status = "no_findings"
    # Preserve real output, but omit wall-clock fields from the reproducible report.
    for key in ("timestamp", "created_at", "signature", "source"):
        raw.pop(key, None)
    return {"status": status, "manifest": raw}


METHODS: dict[str, Callable[[Path, dict], dict]] = {
    "tableproof": tableproof,
    "token_multiset_control": token_multiset,
    "structural_validity_control": structural_validity,
    "pdfmux_numeric_literals": pdfmux,
}


def score(rows: list[dict]) -> dict:
    positive = sum(row["has_error"] for row in rows)
    negative = len(rows) - positive
    tp = sum(row["has_error"] and row["status"] == "review" for row in rows)
    fp = sum(not row["has_error"] and row["status"] == "review" for row in rows)
    tn = sum(not row["has_error"] and row["status"] == "no_findings" for row in rows)
    review_burden = sum(row["status"] in {"review", "uncertain"} for row in rows)
    handoff_burden = sum(row["status"] != "no_findings" for row in rows)

    def safe_divide(n, d):
        return n / d if d else None

    return {
        "cases": len(rows),
        "positive_cases": positive,
        "negative_cases": negative,
        "true_positive": tp,
        "false_positive": fp,
        "true_negative_determinate": tn,
        "positive_not_flagged_including_abstentions_and_errors": positive - tp,
        "precision": safe_divide(tp, tp + fp),
        "recall_all_positive_cases": safe_divide(tp, positive),
        "false_positive_rate_all_negative_cases": safe_divide(fp, negative),
        "abstentions": sum(row["status"] == "uncertain" for row in rows),
        "abstention_rate": safe_divide(
            sum(row["status"] == "uncertain" for row in rows), len(rows)
        ),
        "execution_errors": sum(row["status"] == "execution_error" for row in rows),
        "review_burden_count": review_burden,
        "review_burden_rate": safe_divide(review_burden, len(rows)),
        "handoff_burden_including_execution_errors": handoff_burden,
        "handoff_burden_rate": safe_divide(handoff_burden, len(rows)),
    }


def summarize(rows: list[dict]) -> dict:
    result = {}
    for method in sorted({row["method"] for row in rows}):
        result[method] = {
            stratum: score(
                [row for row in rows if row["method"] == method and row["stratum"] == stratum]
            )
            for stratum in ("real_library_reproducer", "real_source_pdf", "synthetic_control")
        }
    return result


def run(methods: list[str] | None = None) -> dict:
    selected = methods or list(METHODS)
    cases = load_cases()
    rows = []
    for case in cases:
        for name in selected:
            row = {
                "case_id": case["id"],
                "stratum": case["stratum"],
                "method": name,
                "has_error": case["gold"]["has_error"],
            }
            try:
                document = json.loads((ROOT / case["extracted_json"]).read_text())
                row.update(METHODS[name](ROOT / case["source_pdf"], document))
                if row["status"] not in {"review", "uncertain", "no_findings"}:
                    raise ValueError(f"Unknown method status: {row['status']}")
            except Exception as exc:
                row.update(
                    status="execution_error", exception_type=type(exc).__name__, error=str(exc)
                )
            rows.append(row)
    versions = {}
    for name in (
        "pdfplumber",
        "pdfminer.six",
        "reportlab",
        "docling-core",
        "pdfmux",
        "PyMuPDF",
        "pymupdf4llm",
    ):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    return {
        "schema_version": "1.0",
        "evaluation_unit": "case/document, not cell",
        "python": platform.python_version(),
        "package_versions": versions,
        "pdfmux_commit": PDFMUX_COMMIT,
        "methods": {
            "tableproof": "Local deterministic geometry auditor; optional vision not enabled.",
            "token_multiset_control": "Our simple control; not an implementation of pdfmux.",
            "structural_validity_control": "Our grid coverage control; no source comparison.",
            "pdfmux_numeric_literals": (
                "Installed pinned upstream verify_extraction API; numeric literal signal enabled. "
                "A page review/fail is a flag; only pass/unverifiable pages with an "
                "unverifiable page map to abstention. The raw manifest remains available."
            ),
        },
        "limitations": [
            "Tiny development set. It does not establish a general accuracy advantage.",
            "Real library cases share one generated PDF. They are not independent real documents.",
            "Synthetic cases share one layout family. No confidence intervals are justified.",
            "Real-source cases share one public table and AI-assisted labels, not human gold.",
            "Abstentions and execution errors stay in recall and false-positive-rate denominators.",
            "Rates count document flags, not whether every erroneous cell was localized.",
            "No VLM inference or model accuracy claim forms part of this run.",
            "Method statuses differ. A flag does not establish a correct error diagnosis.",
            "Review burden includes both review and uncertain, unlike the flag precision measure.",
            "TableProof gets Docling JSON geometry. pdfmux gets its supported page Markdown.",
        ],
        "fixture_manifest_sha256": {
            str(path.relative_to(ROOT)): sha256(path)
            for path in sorted((ROOT / "fixtures").rglob("*.manifest.json"))
        },
        "engine_source_sha256": {
            str(path.relative_to(ROOT.parent)): sha256(path)
            for path in sorted((ROOT.parent / "src" / "table_proof").glob("*.py"))
        },
        "summary": summarize(rows),
        "results": rows,
    }


def markdown(report: dict) -> str:
    def fmt(value: float | None) -> str:
        return "n/a" if value is None else f"{value:.3f}"

    lines = [
        "# Small development benchmark",
        "",
        "These results describe this corpus only. They do not prove broad accuracy or adoption.",
        "",
        "The unit is one case/document. The real-library pair shares one generated PDF.",
        "The real-source pair shares one public table excerpt. Gold labels are AI-assisted.",
        "TableProof vision is disabled. Docling extraction used real layout and table models.",
        "",
        "| Method | Stratum | Cases | TP | FP | Precision | Recall | FPR | Abstain "
        "| Review cases | Errors |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for method, strata in report["summary"].items():
        for stratum, data in strata.items():
            lines.append(
                f"| {method} | {stratum} | {data['cases']} | {data['true_positive']} | "
                f"{data['false_positive']} | {fmt(data['precision'])} | "
                f"{fmt(data['recall_all_positive_cases'])} | "
                f"{fmt(data['false_positive_rate_all_negative_cases'])} | "
                f"{data['abstentions']} | {data['review_burden_count']} | "
                f"{data['execution_errors']} |"
            )
    lines += [
        "",
        "Abstentions and execution errors remain in the rate denominators.",
        "A zero denominator produces `null` in JSON and `n/a` here.",
        "",
        "`token_multiset_control` and `structural_validity_control` are local controls.",
        "`pdfmux_numeric_literals` calls upstream code with the numeric signal enabled.",
        "The JSON result contains exact versions, case outcomes, and error details.",
        "Method statuses differ. A generic review flag does not prove a correct diagnosis.",
        "Review burden counts both review and uncertain. Execution errors have a separate count.",
        "TableProof gets Docling JSON geometry. pdfmux gets its supported page Markdown format.",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--methods", nargs="+", choices=list(METHODS))
    parser.add_argument("--output", type=Path, default=ROOT / "results.json")
    args = parser.parse_args()
    report = run(args.methods)
    write_json(args.output, report)
    args.output.with_suffix(".md").write_text(markdown(report))
    errors = sum(row["status"] == "execution_error" for row in report["results"])
    print(f"Wrote {len(report['results'])} outcomes; execution errors: {errors}.")
    raise SystemExit(1 if errors else 0)
