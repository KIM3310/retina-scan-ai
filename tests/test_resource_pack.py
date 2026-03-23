"""Tests for the built-in synthetic clinical review pack."""

from __future__ import annotations

from app.monitoring.resource_pack import (
    data_files,
    load_clinical_cases,
    load_quality_scenarios,
    load_release_checks,
    load_validation_cases,
    raw_resource_bytes,
    resource_pack_summary,
)


def test_resource_pack_summary_matches_expected_shape() -> None:
    summary = resource_pack_summary()
    assert summary["clinical_case_count"] >= 5
    assert summary["quality_scenario_count"] >= 4
    assert summary["validation_case_count"] >= 5


def test_resource_pack_files_exist_and_load() -> None:
    for path in data_files().values():
        assert path.exists()

    assert len(load_clinical_cases()) >= 5
    assert len(load_quality_scenarios()) >= 4
    assert len(load_validation_cases()) >= 5
    assert len(load_release_checks()) >= 4
    assert "clinical_case_pack.json" in raw_resource_bytes()
