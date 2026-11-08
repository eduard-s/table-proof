"""Protect independent gold labels, rich-reference replay, and honest metrics."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from benchmarks import run as benchmark
from benchmarks.common import ROOT, sha256


def fixture(name: str) -> tuple[Path, dict]:
    case = next(case for case in benchmark.load_cases() if case["id"] == name)
    return ROOT / case["source_pdf"], json.loads((ROOT / case["extracted_json"]).read_text())


def test_empty_stratum_has_null_rates() -> None:
    result = benchmark.score([])
    assert result["cases"] == 0
    assert result["precision"] is None
    assert result["recall_all_positive_cases"] is None
    assert result["false_positive_rate_all_negative_cases"] is None
    assert result["abstention_rate"] is None


def test_abstentions_and_failures_do_not_disappear_from_denominators() -> None:
    rows = [
        {"has_error": True, "status": "review"},
        {"has_error": True, "status": "uncertain"},
        {"has_error": True, "status": "execution_error"},
        {"has_error": False, "status": "uncertain"},
        {"has_error": False, "status": "review"},
    ]
    result = benchmark.score(rows)
    assert result["recall_all_positive_cases"] == pytest.approx(1 / 3)
    assert result["false_positive_rate_all_negative_cases"] == 0.5
    assert result["precision"] == 0.5
    assert result["abstentions"] == 2
    assert result["execution_errors"] == 1
    assert result["positive_not_flagged_including_abstentions_and_errors"] == 2
    assert result["review_burden_count"] == 4
    assert result["review_burden_rate"] == 0.8
    assert result["handoff_burden_including_execution_errors"] == 5


def test_source_and_extraction_hashes_match_manifests() -> None:
    cases = benchmark.load_cases()
    assert {case["stratum"] for case in cases} == {
        "real_library_reproducer",
        "real_source_pdf",
        "synthetic_control",
    }
    for case in cases:
        assert sha256(ROOT / case["source_pdf"]) == case["source_sha256"]
        assert sha256(ROOT / case["extracted_json"]) == case["extracted_sha256"]
        assert case["gold"]["has_error"] == bool(case["gold"]["errors"])


def test_real_library_artifact_preserves_misleading_cached_text() -> None:
    _, affected = fixture("docling-5198-affected")
    _, fixed = fixture("docling-5198-fixed")
    bad_cells = affected["tables"][1]["data"]["table_cells"]
    good_cells = fixed["tables"][1]["data"]["table_cells"]
    # Looking only at cached text misses the upstream regression.
    assert [cell["text"] for cell in bad_cells] == [cell["text"] for cell in good_cells]
    assert [benchmark.resolved_text(affected, cell) for cell in bad_cells] == [
        "CCC",
        "20.0 mg",
        "BBB",
        "30.0 mg",
    ]
    assert [benchmark.resolved_text(fixed, cell) for cell in good_cells] == [
        "BBB",
        "20.0 mg",
        "CCC",
        "30.0 mg",
    ]


@pytest.mark.integration
def test_auditor_catches_actual_library_swap_and_accepts_control() -> None:
    bad_source, affected = fixture("docling-5198-affected")
    good_source, fixed = fixture("docling-5198-fixed")
    assert benchmark.tableproof(bad_source, affected)["status"] == "review"
    assert benchmark.tableproof(good_source, fixed)["status"] == "no_findings"
    # Baseline limitation is a property of the input, not an emulated competitor.
    assert benchmark.token_multiset(bad_source, affected)["status"] == "no_findings"
    assert benchmark.structural_validity(bad_source, affected)["status"] == "no_findings"


def test_run_records_method_exceptions_for_every_case(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(source: Path, document: dict) -> dict:
        raise RuntimeError("intentional evaluator failure")

    monkeypatch.setitem(benchmark.METHODS, "broken", fail)
    result = benchmark.run(["broken"])
    assert len(result["results"]) == len(benchmark.load_cases())
    assert all(row["status"] == "execution_error" for row in result["results"])
    assert all(row["exception_type"] == "RuntimeError" for row in result["results"])
    for stratum in ("real_library_reproducer", "synthetic_control"):
        assert result["summary"]["broken"][stratum]["execution_errors"] > 0
        assert result["summary"]["broken"][stratum]["recall_all_positive_cases"] == 0


def test_rich_reference_cycles_raise_instead_of_using_cached_text() -> None:
    document = {"groups": [{"children": [{"$ref": "#/groups/0"}]}]}
    with pytest.raises(ValueError, match="Cyclic"):
        benchmark.resolved_text(document, {"text": "looks correct", "ref": {"$ref": "#/groups/0"}})
