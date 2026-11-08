"""Command-line audit interface."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .api import audit_tables


def _same_file(first: Path, second: Path) -> bool:
    return first.resolve() == second.resolve() or (
        first.exists() and second.exists() and first.samefile(second)
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit PDF table cell associations.")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("source_pdf", type=Path, help="Original digital PDF.")
    parser.add_argument("extraction", type=Path, help="Docling JSON export.")
    parser.add_argument("--json", dest="json_path", type=Path, help="Write the JSON report.")
    parser.add_argument("--html", dest="html_path", type=Path, help="Write an HTML report.")
    parser.add_argument("--vision", action="store_true", help="Use the optional vision model.")
    parser.add_argument(
        "--allow-model-download", action="store_true", help="Allow the pinned model download."
    )
    args = parser.parse_args(argv)
    if args.allow_model_download and not args.vision:
        parser.error("--allow-model-download needs --vision.")
    try:
        inputs = (args.source_pdf, args.extraction)
        outputs = [path for path in (args.json_path, args.html_path) if path is not None]
        if any(_same_file(output, source) for output in outputs for source in inputs):
            raise ValueError("A report path must not replace an input file.")
        if len(outputs) == 2 and _same_file(outputs[0], outputs[1]):
            raise ValueError("The JSON and HTML reports need different paths.")
        document = json.loads(args.extraction.read_text(encoding="utf-8"))
        report = audit_tables(
            args.source_pdf,
            document,
            vision=args.vision,
            allow_model_download=args.allow_model_download,
        )
        if args.json_path:
            report.export_json(str(args.json_path))
        if args.html_path:
            report.export_html(str(args.html_path), source_pdf=str(args.source_pdf))
        print(
            json.dumps(
                {
                    "status": report.status,
                    "tables": len(report.tables),
                    "findings": sum(len(table.findings) for table in report.tables),
                }
            )
        )
        return {"no_findings": 0, "review": 1, "uncertain": 3}[report.status]
    except Exception as error:
        print(json.dumps({"status": "error", "message": str(error)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
