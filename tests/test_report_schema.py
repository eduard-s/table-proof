import json
from pathlib import Path

import jsonschema

from table_proof import audit_tables


def test_export_matches_public_schema(pdf_case, tmp_path):
    source, document = pdf_case
    report = audit_tables(source, document)
    output = tmp_path / "report.json"
    report.export_json(str(output))
    schema = json.loads(
        (Path(__file__).resolve().parents[1] / "spec/report-v1.schema.json").read_text()
    )
    jsonschema.validate(json.loads(output.read_text()), schema)
