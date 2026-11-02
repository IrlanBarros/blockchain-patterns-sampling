"""Public CSV schemas and occurrence-level joins required by the classifier."""

import json
from collections import Counter

import pytest

from conftest import read, save
from web3blockset_sampling.contracts import METADATA_COLUMNS, PIPELINE_COLUMNS
from web3blockset_sampling.errors import ValidationError
from web3blockset_sampling.export import export_samples
from web3blockset_sampling.ingestion import header, sha256_file
from web3blockset_sampling.preparation import prepare
from web3blockset_sampling.sampling import draw
from web3blockset_sampling.statistics import allocate
from web3blockset_sampling.stratification import STRATA
from web3blockset_sampling.validation import check_exports
from web3blockset_sampling.workflow import run, validate_run

EXPECTED_PIPELINE = [
    "sampling_unit_id", "repository", "issue_number", "artifact_type", "repository_category", "created_at",
    "closed_at", "state", "comments_count", "commits_count", "issue_title", "issue_body", "concatenated_comments",
]
EXPECTED_METADATA = [
    "sampling_unit_id", "sampling_logical_id", "sampling_repository", "sampling_source", "sampling_category",
    "sampling_original_category", "sampling_stratum", "sampling_population", "sampling_sample_size",
    "sampling_population_weight", "sampling_design_weight", "sampling_provider_weight",
    "sampling_inclusion_probability", "sampling_run_id",
]
FILES = ["final_sample_full.csv", "final_sample_pipeline.csv", "final_sample_metadata.csv"]


def index(records):
    return {r["sampling_unit_id"]: r for r in records}


def test_exact_schemas_are_projections_and_full_preserves_future_columns(corpus):
    config, records, *_ = corpus
    for row in records:
        row.update(raw_text="Do not send raw_text", clean_text="clean", stemmed_text="stemmed", author="author",
                   labels="label", matching_keywords="keyword", future_column="unexpected future metadata")
    save(config.issues, records)
    directory, manifest = run(config, True)
    assert manifest["status"] == "complete"
    assert header(directory / FILES[1]) == EXPECTED_PIPELINE == PIPELINE_COLUMNS
    assert header(directory / FILES[2]) == EXPECTED_METADATA == METADATA_COLUMNS
    assert header(directory / FILES[0]) == list(records[0]) + EXPECTED_METADATA
    assert manifest["export_contract"]["pipeline_columns"] == EXPECTED_PIPELINE
    assert manifest["export_contract"]["metadata_columns"] == EXPECTED_METADATA
    assert manifest["export_contract"]["version"] == "4"
    assert all(name in manifest["artifacts"] for name in FILES)
    full, pipeline, metadata = [index(read(directory / name)) for name in FILES]
    assert full.keys() == pipeline.keys() == metadata.keys()
    original = {r["issue_id"]: r for r in records}
    assert {r["sampling_source"] for r in metadata.values()} == {"provider", "community"}
    for uid, row in full.items():
        assert {k: row[k] for k in original[row["issue_id"]]} == original[row["issue_id"]]
        assert pipeline[uid]["artifact_type"] == row["type"]
        assert pipeline[uid]["repository_category"] == row["repository_category"]
        assert pipeline[uid]["commits_count"] == original[row["issue_id"]]["commits_count"]
        assert metadata[uid] == {k: row[k] for k in EXPECTED_METADATA}
    assert validate_run(directory)["valid"]


@pytest.mark.parametrize("value,expected", [("", ""), ("0", "0"), ("0003.0", "3"), (" 7 ", "7"),
                                           ("0.0", "0"), ("null", ""), ("NaN", ""), ("abc", ""),
                                           ("-1", ""), ("2.5", ""), ("Infinity", ""), ("-Infinity", ""),
                                           ("900719925474099312345678901234567890.0", "900719925474099312345678901234567890")])
def test_commits_count_normalized_only_in_classifier_export(corpus, value, expected):
    config, records, *_ = corpus
    config.error = 0.01  # Synthetic census includes this non-pilot occurrence.
    records[6]["commits_count"] = value
    save(config.issues, records)
    directory, manifest = run(config, True)
    assert manifest["status"] == "complete"
    full, pipeline, metadata = [index(read(directory / name)) for name in FILES]
    target = next(row for row in full.values() if row["issue_id"] == records[6]["issue_id"])
    assert target["commits_count"] == value
    assert pipeline[target["sampling_unit_id"]]["commits_count"] == expected
    assert "commits_count" not in header(directory / FILES[2])
    assert full.keys() == pipeline.keys() == metadata.keys()
    assert validate_run(directory)["valid"]


def test_final_export_audit_uses_original_alias_and_preserves_every_other_cell(corpus):
    config, records, *_ = corpus
    config.error = 0.01
    values = ["0", "0.0", "5", "5.0", "", "  ", "null", "NaN", "abc", "-1", "2.5", "Infinity",
              "900719925474099312345678901234567890.0"]
    expected = ["0", "0", "5", "5", "", "", "", "", "", "", "", "",
                "900719925474099312345678901234567890"]
    for row in records:
        row["raw_commits"] = ""
    for row, value in zip(records[5:], values):
        row["raw_commits"] = value
    config.pipeline_columns["commits_count"] = "raw_commits"
    save(config.issues, records)
    before = sha256_file(config.issues)
    directory, manifest = run(config, True)
    assert manifest["status"] == "complete"
    full, pipeline = [index(read(directory / name)) for name in FILES[:2]]
    targets = {str(row["issue_id"]): output for row, output in zip(records[5:], expected)}
    for uid, row in full.items():
        assert pipeline[uid]["commits_count"] == targets.get(row["issue_id"], "")
        for name in ("comments_count", "issue_title", "issue_body", "concatenated_comments", "created_at", "closed_at"):
            assert pipeline[uid][name] == row[name]
        assert row["raw_commits"] == next(r["raw_commits"] for r in records if r["issue_id"] == row["issue_id"])
    counts = manifest["export_audit"]["commits_count"]
    assert counts["total"] == len(full) == 358
    assert counts["valid"] == 5
    assert counts["integers_preserved"] == 2
    assert counts["decimal_representations_converted"] == 3
    assert counts["zeros_preserved"] == 2
    assert counts["missing"] == 349
    assert counts["invalid"] == 4
    assert {item["sampling_unit_id"] for item in counts["invalid_records"]} == {
        uid for uid, row in full.items() if row["raw_commits"] in {"abc", "-1", "2.5", "Infinity"}}
    report = json.loads((directory / "validation_report.json").read_text())
    assert report["export_audit"] == manifest["export_audit"]
    assert "inválidos: 4" in (directory / "sampling_report.md").read_text()
    assert validate_run(directory)["valid"]
    assert sha256_file(config.issues) == before


@pytest.mark.parametrize("target", ["manifest", "validation_report"])
def test_final_audit_tampering_rejected_even_with_updated_checksum(corpus, target):
    directory, manifest = run(corpus[0], True)
    if target == "manifest":
        manifest["export_audit"]["commits_count"]["invalid"] += 1
    else:
        report_path = directory / "validation_report.json"
        report = json.loads(report_path.read_text())
        report["export_audit"]["commits_count"]["invalid"] += 1
        report_path.write_text(json.dumps(report))
        manifest["artifacts"][report_path.name] = sha256_file(report_path)
    (directory / "sampling_manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValidationError, match="inconsistente"):
        validate_run(directory)


def test_original_number_dates_counts_text_and_empty_values_are_preserved(corpus):
    config, records, *_ = corpus
    config.error = 0.01  # Synthetic census makes every edge case observable.
    record = records[6]
    record.update(issue_number="0007.0", repository_category=record["repository_category"] + "  ",
                  created_at=" 2024-02-01T03:04:05Z ", closed_at=None, state="open", comments_count="0000.0",
                  issue_title="", issue_body=None, concatenated_comments="  NA\nnull\r\nNaN, \"汉字\"  ")
    records[-2].update(repository_category="", issue_body="", comments_count="0")
    save(config.issues, records)
    directory, manifest = run(config, True)
    assert manifest["status"] == "complete"
    full, pipeline, metadata = [index(read(directory / name)) for name in FILES]
    target = next(r for r in full.values() if r["issue_id"] == record["issue_id"])
    exported = pipeline[target["sampling_unit_id"]]
    assert exported["issue_number"] == "0007.0"
    assert exported["repository"] == target["sampling_repository"]
    for field in ["repository_category", "created_at", "state", "comments_count", "issue_title", "concatenated_comments"]:
        assert exported[field] == record[field]
    assert exported["closed_at"] == exported["issue_body"] == ""
    assert any(not row["repository_category"] for row in pipeline.values())
    assert all(r["sampling_provider_weight"] == "" for r in metadata.values() if r["sampling_source"] == "community")
    assert validate_run(directory)["valid"]


@pytest.mark.parametrize("origin", ["provider", "community"])
def test_duplicate_logical_occurrences_survive_and_classifier_results_join_one_to_one(corpus, origin):
    config, records, repositories, _ = corpus
    config.error = 0.01
    copied = dict(records[6])
    copied["data_source"] = origin
    records.append(copied)
    if origin == "community":
        repositories.append({**repositories[0], "source": "community"})
    config.expected_counts = {"total": 361, "provider": 321 if origin == "provider" else 320,
                              "community": 40 if origin == "provider" else 41}
    config.duplicate_policy, config.duplicate_decision = "preserve_rows", "Synthetic occurrence policy"
    save(config.issues, records)
    save(config.repositories, repositories)
    directory, manifest = run(config, True)
    assert manifest["status"] == "complete"
    full, pipeline, metadata = [index(read(directory / name)) for name in FILES]
    assert len(full) == len(pipeline) == len(metadata) == manifest["selected_sample"]
    duplicated = [r for r in full.values() if r["issue_id"] == copied["issue_id"]]
    assert len(duplicated) == 2
    assert len({r["sampling_unit_id"] for r in duplicated}) == 2
    assert len({r["sampling_logical_id"] for r in duplicated}) == 1
    assert len({(pipeline[r["sampling_unit_id"]]["repository"], pipeline[r["sampling_unit_id"]]["issue_number"]) for r in duplicated}) == 1
    # Simulated Stage 1/2/final results carry the occurrence ID without any LLM call.
    results = [{"sampling_unit_id": uid, "synthetic_prediction": i % 2} for i, uid in enumerate(reversed(pipeline))]
    assert {r["sampling_unit_id"] for r in results} == set(metadata)
    joined = [{**r, **metadata[r["sampling_unit_id"]]} for r in results]
    assert len(joined) == len(results) and len(index(joined)) == len(results)
    assert all(r["sampling_stratum"] == full[r["sampling_unit_id"]]["sampling_stratum"] for r in joined)
    assert validate_run(directory)["valid"]


@pytest.mark.parametrize("filename", FILES)
@pytest.mark.parametrize("mutation", ["empty_id", "null_id", "duplicate", "missing", "unknown_id"])
def test_three_file_integrity_rejects_null_duplicate_missing_and_foreign_ids(corpus, filename, mutation):
    config, *_ = corpus
    directory, manifest = run(config, True)
    target = directory / filename
    records = read(target)
    if mutation == "empty_id":
        records[0]["sampling_unit_id"] = "   "
    elif mutation == "null_id":
        records[0]["sampling_unit_id"] = None
    elif mutation == "duplicate":
        records.append(dict(records[0]))
    elif mutation == "missing":
        records.pop()
    else:
        records[0]["sampling_unit_id"] = "unit-not-selected"
    save(target, records)
    manifest["artifacts"][filename] = sha256_file(target)
    (directory / "sampling_manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValidationError):
        validate_run(directory)


@pytest.mark.parametrize("filename,field", [(FILES[1], "issue_body"), (FILES[1], "artifact_type"),
                                           (FILES[1], "created_at"), (FILES[1], "comments_count"),
                                           (FILES[1], "commits_count"),
                                           (FILES[2], "sampling_population_weight"), (FILES[2], "sampling_source"),
                                           (FILES[2], "sampling_logical_id")])
def test_content_mismatch_is_detected_independently_of_checksums(corpus, filename, field):
    config, *_ = corpus
    directory, manifest = run(config, True)
    target = directory / filename
    records = read(target)
    records[0][field] = "changed"
    save(target, records)
    manifest["artifacts"][filename] = sha256_file(target)
    (directory / "sampling_manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValidationError):
        validate_run(directory)


@pytest.mark.parametrize("filename", FILES[1:])
def test_extra_columns_are_rejected(corpus, filename):
    config, *_ = corpus
    directory, manifest = run(config, True)
    target = directory / filename
    records = read(target)
    for row in records:
        row["unapproved_column"] = "must not be here"
    save(target, records)
    manifest["artifacts"][filename] = sha256_file(target)
    (directory / "sampling_manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValidationError, match="Cabeçalho"):
        validate_run(directory)


@pytest.mark.parametrize("filename", FILES[1:])
def test_column_order_is_mandatory_even_with_the_same_names(corpus, filename):
    config, *_ = corpus
    directory, manifest = run(config, True)
    target = directory / filename
    records = read(target)
    save(target, [{key: row[key] for key in reversed(row)} for row in records])
    manifest["artifacts"][filename] = sha256_file(target)
    (directory / "sampling_manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValidationError, match="Cabeçalho"):
        validate_run(directory)


@pytest.mark.parametrize("mutation", ["missing_contract", "changed_contract", "missing_metadata_artifact"])
def test_manifest_requires_the_new_contract_and_metadata_artifact(corpus, mutation):
    config, *_ = corpus
    directory, manifest = run(config, True)
    if mutation == "missing_contract":
        manifest.pop("export_contract")
    elif mutation == "changed_contract":
        manifest["export_contract"]["occurrence_key"] = "sampling_logical_id"
    else:
        manifest["artifacts"].pop("final_sample_metadata.csv")
    (directory / "sampling_manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValidationError):
        validate_run(directory)


def test_explicit_input_aliases_and_reordered_configuration_keep_fixed_output(corpus):
    config, records, *_ = corpus
    for row in records:
        row["original_body"] = row.pop("issue_body")
    save(config.issues, records)
    config.pipeline_columns["issue_body"] = "original_body"
    config.pipeline_columns = dict(reversed(list(config.pipeline_columns.items())))
    directory, manifest = run(config, True)
    assert manifest["status"] == "complete"
    assert header(directory / FILES[1]) == EXPECTED_PIPELINE
    full, pipeline = [index(read(directory / name)) for name in FILES[:2]]
    assert all(row["issue_body"] == full[uid]["original_body"] for uid, row in pipeline.items())
    assert all("original_body" not in row for row in pipeline.values())
    assert validate_run(directory)["valid"]


def test_export_copies_weights_without_calling_statistical_calculations(corpus, monkeypatch):
    config, *_ = corpus
    p = prepare(config)
    counts = Counter(u.stratum for u in p.eligible)
    allocation = allocate({s: counts[s] for s in STRATA}, config.z, config.p, config.error)
    selected = draw(p.eligible, allocation, config.seed)
    def forbidden(*args, **kwargs):
        pytest.fail("Statistical weights must not be recalculated while exporting")
    monkeypatch.setattr("web3blockset_sampling.statistics.allocate", forbidden)
    monkeypatch.setattr("web3blockset_sampling.statistics.sample_size", forbidden)
    monkeypatch.setattr("web3blockset_sampling.statistics.cochran_n0", forbidden)
    directory = config.output / "isolated-export"
    directory.mkdir(parents=True)
    export_samples(directory, p, selected, allocation, "synthetic-export")
    assert all(check_exports(directory, p, allocation, selected, "synthetic-export").values())
    full, metadata = index(read(directory / FILES[0])), index(read(directory / FILES[2]))
    assert all(row == {k: full[uid][k] for k in EXPECTED_METADATA} for uid, row in metadata.items())


def test_configuration_cannot_expand_the_pipeline_or_replace_its_occurrence_key(corpus):
    config, *_ = corpus
    config.pipeline_columns["raw_text"] = "raw_text"
    with pytest.raises(ValidationError, match="12 campos"):
        config.validate()
    config.pipeline_columns.pop("raw_text")
    config.pipeline_columns["sampling_unit_id"] = "issue_id"
    with pytest.raises(ValidationError, match="automaticamente"):
        config.validate()
