"""Audit-only validation must remain useful and must never perform a draw."""

import json
from collections import Counter
from dataclasses import replace

import pytest

from conftest import read, save
from web3blockset_sampling.ingestion import inspect_csv
from web3blockset_sampling.preparation import prepare
from web3blockset_sampling.statistics import allocate
from web3blockset_sampling.stratification import STRATA
from web3blockset_sampling.validation import check_preparation
from web3blockset_sampling.workflow import run


def test_preparation_checks_are_recorded_without_drawing(corpus, monkeypatch):
    config, *_ = corpus
    def forbidden(*args, **kwargs):
        pytest.fail("A preparation/dry-run must not draw any record")
    monkeypatch.setattr("web3blockset_sampling.workflow.draw", forbidden)
    monkeypatch.setattr("web3blockset_sampling.validation.draw", forbidden)
    directory, manifest = run(config)
    assert manifest["status"] == "prepared"
    report = json.loads((directory / "validation_report.json").read_text())
    assert len(report["checks"]) >= 20
    assert all(report["checks"].values())
    assert report["checks"]["expansion_weights_recover_population"]
    assert not list(directory.glob("final_sample*.csv"))


@pytest.mark.parametrize("field,value,check", [
    ("population_weight", 0.9, "weight_consistency"),
    ("design_weight", 99999, "weight_consistency"),
    ("provider_weight", 0.9, "provider_weight_consistency"),
    ("sample", 1, "formula_consistency"),
    ("population", 1000, "population_per_stratum"),
])
def test_preparation_checks_detect_inconsistent_statistics(corpus, field, value, check):
    config, *_ = corpus
    p = prepare(config)
    counts = Counter(u.stratum for u in p.eligible)
    a = allocate({s: counts[s] for s in STRATA}, config.z, config.p, config.error)
    a[STRATA[0]] = replace(a[STRATA[0]], **{field: value})
    assert check_preparation(p, a)[check] is False


def test_duplicate_audit_is_per_logical_identity_and_preserves_rows(corpus):
    config, records, repositories, _ = corpus
    copied = dict(records[6])
    copied["data_source"] = "community"
    records.append(copied)
    repositories.append({**repositories[0], "source": "community"})
    config.expected_counts = {"total": 361, "provider": 320, "community": 41}
    save(config.issues, records)
    save(config.repositories, repositories)
    directory, manifest = run(config)
    assert manifest["status"] == "blocked"
    report = json.loads((directory / "validation_report.json").read_text())
    assert report["audit"]["input_rows"] == 361
    assert report["audit"]["duplicates"]["eligible_logical_extra_rows"] == 1
    duplicates = read(directory / "duplicate_groups.csv")
    assert len(duplicates) == 1
    assert duplicates[0]["occurrences"] == "2"
    assert duplicates[0]["content_variants"] == "2"
    assert json.loads(duplicates[0]["source_counts"]) == {"community": 1, "provider": 1}
    assert duplicates[0]["rows_excluded"] == "0"
    assert len(read(config.issues)) == 361


def test_each_pilot_key_has_a_match_audit(corpus):
    config, *_ = corpus
    directory, _ = run(config)
    results = read(directory / "exclusions_audit.csv")
    assert len(results) == 2
    assert all(r["role"] == "pilot" and r["status"] == "matched" for r in results)
    assert all(r["input_occurrences"] == "1" and r["matched_rows"] == "1" and r["rows_removed"] == "1" for r in results)
    assert all(len(json.loads(r["key"])) == 3 for r in results)


def test_metadata_repositories_without_records_are_not_silently_dropped(corpus):
    config, _, repositories, _ = corpus
    repositories.append({**repositories[0], "repository": "unused-repository"})
    save(config.repositories, repositories)
    directory, manifest = run(config)
    assert manifest["status"] == "prepared"
    report = json.loads((directory / "validation_report.json").read_text())
    assert report["audit"]["join"]["metadata_repositories_without_records"] == ["org/unused-repository"]
    summary = {r["stratum"]: r for r in read(directory / "strata_summary.csv")}
    assert summary[STRATA[0]]["metadata_repositories"] == "3"
    assert summary[STRATA[0]]["population_repositories"] == "2"


def test_date_inspection_reports_actual_period_without_filtering(tmp_path):
    path = tmp_path / "dates.csv"
    save(path, [{"created_at": "2012-01-01T00:00:00Z"}, {"created_at": "2025-11-10T12:00:00+00:00"},
                {"created_at": "invalid-date"}, {"created_at": "2024-01-01T10:00:00"}, {"created_at": ""}])
    profile = inspect_csv(path)
    dates = profile["date_profiles"]["created_at"]
    assert profile["rows"] == 5
    assert dates["nonempty"] == 4 and dates["invalid_iso8601"] == 1 and dates["without_timezone"] == 1
    assert dates["years"] == {"2012": 1, "2025": 1, "2024": 1}
    assert dates["maximum_utc"].startswith("2025-11-10")
    assert len(read(path)) == 5


def test_code_change_during_preparation_blocks_execution(corpus, monkeypatch):
    config, *_ = corpus
    hashes = iter(["a" * 64, "b" * 64])
    monkeypatch.setattr("web3blockset_sampling.workflow.implementation_hash", lambda: next(hashes))
    directory, manifest = run(config)
    assert manifest["status"] == "blocked"
    assert manifest["implementation_sha256"] == "a" * 64
    report = json.loads((directory / "validation_report.json").read_text())
    assert report["checks"]["implementation_unchanged"] is False
    assert not list(directory.glob("final_sample*.csv"))
