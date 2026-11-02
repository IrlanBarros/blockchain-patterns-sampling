from __future__ import annotations

import json
import random
from collections import Counter
from pathlib import Path

import pytest

from conftest import read, save
from web3blockset_sampling.cli import main
from web3blockset_sampling.config import load_config
from web3blockset_sampling.errors import ValidationError
from web3blockset_sampling.ingestion import header, inspect_csv, rows, sha256_file
from web3blockset_sampling.preparation import prepare, verify_inputs
from web3blockset_sampling.sampling import draw
from web3blockset_sampling.statistics import allocate
from web3blockset_sampling.stratification import STRATA
from web3blockset_sampling.validation import check_design, check_exports
from web3blockset_sampling.workflow import run, snapshot, validate_run


def plan(config):
    p = prepare(config)
    counts = Counter(u.stratum for u in p.eligible)
    return p, allocate({s: counts[s] for s in STRATA}, config.z, config.p, config.error)


def test_reproducible_exact_no_replacement(corpus):
    config, *_ = corpus
    p, allocation = plan(config)
    selected = draw(p.eligible, allocation, config.seed)
    assert selected == draw(p.eligible, allocation, config.seed)
    assert selected != draw(p.eligible, allocation, 44)
    assert len(selected) == sum(a.sample for a in allocation.values())
    assert all(a.sampling_fraction == a.sample / a.population for a in allocation.values())
    assert all(check_design(p, allocation, selected).values())


@pytest.mark.parametrize("policy", ["error", "preserve_rows"])
def test_independent_of_input_row_order(corpus, policy):
    config, records, repos, _ = corpus
    if policy == "preserve_rows":
        records.append(dict(records[6]))
        config.expected_counts = {"total": 361, "provider": 321, "community": 40}
        config.duplicate_policy = policy
        config.duplicate_decision = "Synthetic row occurrence units"
        save(config.issues, records)
    p, a = plan(config)
    first = draw(p.eligible, a, config.seed)
    random.Random(99).shuffle(records)
    random.Random(77).shuffle(repos)
    save(config.issues, records)
    save(config.repositories, repos)
    second_p, second_a = plan(config)
    assert first == draw(second_p.eligible, second_a, config.seed)


def test_rng_is_independent_between_strata(corpus):
    config, *_ = corpus
    p, a = plan(config)
    first_stratum = STRATA[0]
    only = [u for u in p.eligible if u.stratum == first_stratum]
    local = draw(only, {first_stratum: a[first_stratum]}, config.seed)
    all_selected = draw(p.eligible, a, config.seed)
    assert local == all_selected & {u.unit_id for u in only}


def test_pilot_overlap_rejected_by_design_validation(corpus):
    config, *_ = corpus
    p, a = plan(config)
    selected = draw(p.eligible, a, config.seed)
    selected.add(next(iter(p.excluded)))
    with pytest.raises(ValidationError):
        check_design(p, a, selected)


def test_end_to_end(corpus):
    config, records, *_ = corpus
    input_hashes = [sha256_file(path) for path in (config.issues, config.repositories, config.pilot)]
    directory, manifest = run(config, definitive=True)
    assert manifest["status"] == "complete"
    assert manifest["eligible_population"] == 358
    assert manifest["selected_sample"] != 3410
    result = validate_run(directory)
    assert result["valid"] and all(result["checks"].values())
    full, pipeline = read(directory / "final_sample_full.csv"), read(directory / "final_sample_pipeline.csv")
    metadata = read(directory / "final_sample_metadata.csv")
    assert len(full) == len(pipeline) == len(metadata) == manifest["selected_sample"]
    source = {row["issue_id"]: row for row in records}
    for exported, alias in zip(full, pipeline):
        original = source[exported["issue_id"]]
        assert {k: exported[k] for k in original} == original
        assert alias["repository"] == exported["sampling_repository"]
        assert alias["issue_body"] == original["issue_body"]
        assert alias["concatenated_comments"] == original["concatenated_comments"]
        assert alias["artifact_type"] == original["type"]
        assert alias["issue_number"] == original["issue_number"]
        assert exported["unknown_metadata"] == "00001"
    summary = read(directory / "strata_summary.csv")
    assert len(summary) == 9
    assert sum(int(s["population"]) for s in summary) == 358
    assert sum(int(s["excluded"]) for s in summary) == 2
    assert sum(float(s["population_weight"]) for s in summary) == pytest.approx(1)
    assert input_hashes == [sha256_file(path) for path in (config.issues, config.repositories, config.pilot)]
    report = json.loads((directory / "validation_report.json").read_text())
    assert report["sample"]["sources"]["community"] > 0
    assert report["checks"]["original_fields_and_text_preserved"]
    assert (directory / "repository_distribution.csv").is_file()
    assert "±5%" in (directory / "sampling_report.md").read_text()


def test_repeated_runs_keep_history_and_selection(corpus):
    config, *_ = corpus
    a_dir, a = run(config, True)
    b_dir, b = run(config, True)
    assert a_dir != b_dir
    assert a["run_id"] != b["run_id"]
    a_ids = {r["sampling_unit_id"] for r in read(a_dir / "final_sample_full.csv")}
    b_ids = {r["sampling_unit_id"] for r in read(b_dir / "final_sample_full.csv")}
    assert a_ids == b_ids


def test_dry_run_does_not_export_sample(corpus):
    config, *_ = corpus
    directory, manifest = run(config)
    assert manifest["status"] == "prepared"
    assert not (directory / "final_sample_full.csv").exists()
    assert manifest["selected_sample"] == 0
    with pytest.raises(ValidationError):
        validate_run(directory)


def test_unapproved_mapping_blocks_final_export(corpus):
    config, *_ = corpus
    config.approval = None
    directory, manifest = run(config, True)
    assert manifest["status"] == "blocked"
    assert not (directory / "final_sample_full.csv").exists()
    assert (directory / "strata_summary.csv").is_file()


def test_critical_join_failure_has_persisted_diagnostic(corpus):
    config, _, repos, _ = corpus
    save(config.repositories, repos + [repos[0]])
    directory, manifest = run(config, True)
    assert manifest["status"] == "blocked"
    assert "ambígua" in manifest["blockers"][0]
    assert (directory / "validation_report.json").is_file()


@pytest.mark.parametrize("field", ["issue_body", "sampling_population_weight", "sampling_unit_id"])
def test_tampered_export_rejected_even_with_updated_checksum(corpus, field):
    config, *_ = corpus
    directory, manifest = run(config, True)
    target = directory / "final_sample_full.csv"
    full = read(target)
    full[0][field] = "alterado"
    save(target, full)
    manifest["artifacts"][target.name] = sha256_file(target)
    (directory / "sampling_manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValidationError):
        validate_run(directory)


@pytest.mark.parametrize("field", ["seed", "eligible_population", "mapping_version"])
def test_tampered_manifest_rejected(corpus, field):
    config, *_ = corpus
    directory, manifest = run(config, True)
    manifest[field] = "alterado"
    (directory / "sampling_manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValidationError):
        validate_run(directory)


def test_tampered_reports_are_recomputed(corpus):
    config, *_ = corpus
    directory, manifest = run(config, True)
    target = directory / "strata_summary.csv"
    summary = read(target)
    summary[0]["population"] = "999999"
    save(target, summary)
    manifest["artifacts"][target.name] = sha256_file(target)
    (directory / "sampling_manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValidationError, match="Relatório inconsistente"):
        validate_run(directory)


def test_input_mutation_rejected(corpus):
    config, *_ = corpus
    directory, manifest = run(config, True)
    config.issues.write_text(config.issues.read_text() + "\n")
    with pytest.raises(ValidationError, match="Entradas"):
        validate_run(directory)


def test_input_mutation_during_run_rejected(corpus):
    config, *_ = corpus
    p, _ = plan(config)
    config.pilot.write_text(config.pilot.read_text() + "\n")
    with pytest.raises(ValidationError, match="modificado"):
        verify_inputs(p)


def test_pipeline_field_missing_blocks_sample(corpus):
    config, *_ = corpus
    config.pipeline_columns["issue_title"] = "missing_title"
    directory, manifest = run(config, True)
    assert manifest["status"] == "blocked"
    assert not (directory / "final_sample_pipeline.csv").exists()


def test_pipeline_identity_contract_is_explicit(corpus):
    config, records, *_ = corpus
    config.error = 0.01  # Census, including a same-number issue/PR collision outside pilot.
    records[3]["issue_number"] = records[2]["issue_number"]
    save(config.issues, records)
    directory, manifest = run(config, True)
    assert manifest["status"] == "complete"
    assert validate_run(directory)["valid"]
    config.pipeline_key_fields = ["repository", "issue_number"]
    with pytest.raises(ValidationError, match="sampling_unit_id"):
        config.validate()


def test_metadata_column_collision_not_overwritten(corpus):
    config, records, *_ = corpus
    for row in records:
        row["sampling_stratum"] = "original"
    save(config.issues, records)
    directory, manifest = run(config, True)
    assert manifest["status"] == "blocked"
    assert any("namespace" in b for b in manifest["blockers"])


def test_cli_full_lifecycle(corpus, capsys):
    config, *_ = corpus
    config_file = config.pilot.parent / "config.json"
    config_file.write_text(json.dumps(snapshot(config)))
    assert main(["inspect", "--file", str(config.pilot)]) == 0
    assert json.loads(capsys.readouterr().out)[0]["rows"] == 2
    assert main(["prepare", "--config", str(config_file)]) == 0
    capsys.readouterr()
    assert main(["sample", "--config", str(config_file), "--dry-run"]) == 0
    dry = json.loads(capsys.readouterr().out)
    assert dry["status"] == "prepared"
    assert main(["sample", "--config", str(config_file)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "complete"
    assert main(["validate", "--run-dir", result["run_directory"]]) == 0
    assert json.loads(capsys.readouterr().out)["valid"]


def test_cli_approval_command_and_errors(corpus, capsys):
    config, *_ = corpus
    output = config.pilot.parent / "new-approval.json"
    assert main(["approve-mapping", "--mapping", str(config.mapping), "--output", str(output), "--reviewer", "Synthetic Reviewer"]) == 0
    assert json.loads(output.read_text())["mapping_sha256"] == sha256_file(config.mapping)
    capsys.readouterr()
    assert main(["inspect", "--file", str(config.pilot.parent / "not-found.csv")]) == 2
    assert "error" in json.loads(capsys.readouterr().err)


def test_config_paths_are_relative_to_file(corpus):
    config, *_ = corpus
    config_file = config.pilot.parent / "config.json"
    data = snapshot(config)
    data["issues"] = "issues.csv"
    config_file.write_text(json.dumps(data))
    assert load_config(config_file).issues == config.issues.resolve()


@pytest.mark.parametrize("text", ["x,x\n1,2\n", "x,y\n1\n", "x,y\n1,2,3\n", 'x,y\n1,"unclosed\n'])
def test_malformed_csv_fails(tmp_path, text):
    path = tmp_path / "bad.csv"
    path.write_text(text)
    with pytest.raises(ValidationError):
        list(rows(path))


def test_inspect_preserves_missing_and_reports_candidate_keys(corpus):
    config, *_ = corpus
    report = inspect_csv(config.issues)
    assert report["rows"] == 360
    assert report["token_distributions"]["data_source"] == {"provider": 320, "community": 40}
    assert report["candidate_keys_raw_values"][0]["distinct"] == 360
    assert next(c for c in report["columns"] if c["name"] == "issue_body")["empty"] > 0


def test_empty_strata_are_explicit_and_weights_defined(corpus):
    config, records, repos, _ = corpus
    records = [r for r in records if r["data_source"] == "community"]
    repos = [r for r in repos if r["source"] == "community"]
    save(config.issues, records)
    save(config.repositories, repos)
    save(config.pilot, [{"repository_full_name": "Org/" + r["repository"], "issue_number": r["issue_number"], "type": r["type"]}
                       for r in records[:2]])
    config.expected_counts = {"total": 40, "provider": 0, "community": 40}
    directory, manifest = run(config, True)
    assert manifest["status"] == "complete"
    assert manifest["allocation"]["Community"]["population_weight"] == 1
    assert manifest["allocation"][STRATA[0]]["design_weight"] is None
    assert manifest["allocation"][STRATA[0]]["sample"] == 0
    assert validate_run(directory)["valid"]


def test_original_repository_category_is_preserved(corpus):
    config, _, repos, _ = corpus
    for repo in repos:
        repo["category"] += "  "
    save(config.repositories, repos)
    directory, manifest = run(config, True)
    assert manifest["status"] == "complete"
    full = read(directory / "final_sample_full.csv")
    assert all(row["sampling_original_category"].endswith("  ") for row in full)
    assert all(not row["sampling_category"].endswith(" ") for row in full)
    assert validate_run(directory)["valid"]


def test_invalid_population_has_no_invented_allocation(corpus):
    config, records, *_ = corpus
    for row in records:
        row["repository"] = "not-found"
    save(config.issues, records)
    directory, manifest = run(config, True)
    assert manifest["status"] == "blocked"
    assert not (directory / "strata_summary.csv").exists()
    assert manifest["audit"]["invalid_rows"] == 360


def test_duplicate_json_object_keys_rejected(corpus):
    config, *_ = corpus
    config_file = config.pilot.parent / "config.json"
    config_file.write_text('{"seed":42,"seed":123}')
    with pytest.raises(ValidationError, match="repetida"):
        load_config(config_file)
