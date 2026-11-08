"""Exercise the installed distribution against the pinned regression pair."""

import json
from pathlib import Path

from table_proof import audit_tables

root = Path(__file__).resolve().parents[1]
fixture = root / "benchmarks/fixtures/docling_5198"
affected = audit_tables(fixture / "source.pdf", json.loads((fixture / "affected.json").read_text()))
fixed = audit_tables(fixture / "source.pdf", json.loads((fixture / "fixed.json").read_text()))
assert affected.status == "review", affected
assert fixed.status == "no_findings", fixed
print("The installed wheel detects the affected case and accepts the fixed control.")
