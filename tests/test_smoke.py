"""Technical extraction tests; all fixtures are synthetic, never LLM calls."""

from __future__ import annotations

import copy
import json
from collections import Counter
from dataclasses import replace

import pytest

from conftest import read, save
from web3blockset_sampling.cli import main
from web3blockset_sampling.contracts import METADATA_COLUMNS, PIPELINE_COLUMNS
from web3blockset_sampling.errors import ValidationError
from web3blockset_sampling.ingestion import header, sha256_file
from web3blockset_sampling.normalization import normalize_commits_count
from web3blockset_sampling.preparation import prepare
from web3blockset_sampling.smoke import (
    FULL, MANIFEST, METADATA, NOT_APPLICABLE, PIPELINE, REPORT, VALIDATION,
    check_smoke_exports, evaluate, records_for, run_smoke, validate_smoke,
)
from web3blockset_sampling.smoke_selection import BITS, LONG_TEXT_MIN, features, profile_candidates, select
from web3blockset_sampling.stratification import STRATA
from web3blockset_sampling.workflow import run, snapshot, validate_run


@pytest.fixture
def smoke_corpus(corpus):
    config, records, repos, pilots = corpus
    config.approval = None
    config.repository_scope = "provider"
    save(config.repositories, [r for r in repos if r["source"] == "provider"])
    records[6]["issue_body"] = "oracle access control proxy\n" + "x" * LONG_TEXT_MIN
    for i, row in enumerate(records):
        if i % 7 == 0:
            row["commits_count"] = "0"
        if i % 11 == 0:
            row["concatenated_comments"] = ""
    pair = dict(records[5], data_source="community")
    records.append(pair)
    config.expected_counts = {"total": 361, "provider": 320, "community": 41}
    save(config.issues, records)
    return config, records, repos, pilots


def complete(corpus, **kwargs):
    config, *_ = corpus
    directory, manifest = run_smoke(config, authorized=True, **kwargs)
    assert manifest["status"] == "complete", manifest
    return directory, manifest


def rewrite_manifest(directory, manifest):
    (directory / MANIFEST).write_text(json.dumps(manifest), encoding="utf-8")


def test_selection_all_mandatory_and_optional_coverage(smoke_corpus):
    config, *_ = smoke_corpus
    prepared, chosen, evidence = evaluate(config, 20261102, 15)
    ids = [c.unit.unit_id for c in chosen]
    assert len(ids) == len(set(ids)) == 15
    assert ids == sorted(ids)
    assert {c.unit.stratum for c in chosen} == set(STRATA)
    assert {c.unit.artifact_type for c in chosen} == {"issue", "pull_request"}
    assert set(ids) <= {u.unit_id for u in prepared.eligible}
    assert not set(ids) & prepared.excluded
    assert evidence["selection"]["repeated_identity_pairs"]
    assert all(v["covered"] for v in evidence["selection"]["coverage"].values())
    assert len(evidence["pending_methodological_decisions"]) == 2
    assert all(evidence["checks"].values())


def test_seed_and_iteration_order_are_deterministic(smoke_corpus):
    config, *_ = smoke_corpus
    p = prepare(config)
    candidates, _ = profile_candidates(p, 123)
    first = select(candidates)
    assert first == select(list(reversed(candidates)))
    assert first == select(profile_candidates(prepare(config), 123)[0])
    second = select(profile_candidates(p, 124)[0])
    assert [c.unit.unit_id for c in first] != [c.unit.unit_id for c in second]


def test_repeated_pair_uses_existing_ids_and_eligible_occurrences(smoke_corpus):
    config, *_ = smoke_corpus
    p, chosen, evidence = evaluate(config, 1, 15)
    pair = evidence["selection"]["repeated_identity_pairs"][0]
    units = {u.unit_id: u for u in p.units}
    a, b = [units[uid] for uid in pair["sampling_unit_ids"]]
    assert a.logical_id == b.logical_id == pair["sampling_logical_id"]
    assert a.unit_id != b.unit_id
    assert {a.source, b.source} == {"provider", "community"}
    assert a.pilot_key == b.pilot_key
    assert all(c.unit.unit_id.startswith("logical:") for c in chosen)
    assert config.duplicate_policy == "error"  # No preserve_rows override or ID rewriting.


def test_missing_real_pair_fails_and_persists_diagnostic(corpus):
    config, *_ = corpus
    directory, manifest = run_smoke(config, authorized=True)
    assert manifest["status"] == "blocked"
    assert "Par real obrigatório" in manifest["blockers"][0]
    assert not (directory / PIPELINE).exists()
    with pytest.raises(ValidationError, match="completo"):
        validate_smoke(directory)


@pytest.mark.parametrize("case", ["stratum", "artifact", "pair", "too_few", "duplicate_id", "blank_id"])
def test_impossible_mandatory_constraints_are_diagnostic(smoke_corpus, case):
    config, *_ = smoke_corpus
    p = prepare(config)
    candidates, _ = profile_candidates(p, 1)
    if case == "stratum":
        candidates = [c for c in candidates if c.unit.stratum != STRATA[0]]
        expected = "estratos ausentes"
    elif case == "artifact":
        candidates = [c for c in candidates if c.unit.artifact_type == "issue"]
        expected = "Issues e PRs"
    elif case == "pair":
        logical = Counter(c.unit.logical_id for c in candidates)
        candidates = [c for c in candidates if logical[c.unit.logical_id] == 1]
        expected = "Par real obrigatório"
    elif case == "too_few":
        candidates = candidates[:14]
        expected = "somente 14"
    elif case == "duplicate_id":
        candidates.append(candidates[0])
        expected = "duplicado"
    else:
        candidates[0] = replace(candidates[0], unit=replace(candidates[0].unit, unit_id=" "))
        expected = "vazio"
    with pytest.raises(ValidationError, match=expected):
        select(candidates)


@pytest.mark.parametrize("size", [0, 9, 14, 16, 100])
def test_unsupported_sizes_cannot_relax_coverage(smoke_corpus, size):
    config, *_ = smoke_corpus
    directory, manifest = run_smoke(config, authorized=True, size=size)
    assert manifest["status"] == "blocked"
    assert "--size 15" in manifest["blockers"][0]
    assert not (directory / PIPELINE).exists()


@pytest.mark.parametrize("value,scenario", [("", "commits_empty"), ("  ", "commits_empty"), ("0", "commits_zero"),
                                           ("000.0", "commits_zero"), ("3", "commits_positive"),
                                           (" 003.00 ", "commits_positive"), ("null", None), ("NaN", None),
                                           ("-1", None), ("Infinity", None)])
def test_commits_semantics_do_not_change_raw_values(smoke_corpus, value, scenario):
    config, *_ = smoke_corpus
    unit = prepare(config).eligible[0]
    pipeline = dict.fromkeys(PIPELINE_COLUMNS, "")
    pipeline["commits_count"] = value
    candidate = features(unit, pipeline, 1)
    bits = sum(BITS[k] for k in ("commits_empty", "commits_zero", "commits_positive"))
    assert candidate.mask & bits == (BITS[scenario] if scenario else 0)
    assert pipeline["commits_count"] == value


def test_unavailable_scenario_is_reported_not_invented(smoke_corpus):
    config, records, *_ = smoke_corpus
    for row in records:
        row["commits_count"] = ""
    save(config.issues, records)
    _, manifest = complete(smoke_corpus)
    scenario = manifest["selection"]["coverage"]["commits_zero"]
    assert scenario == {"selected": 0, "available": 0, "covered": False,
                        "limitation": "indisponível na população elegível"}


def test_original_values_contracts_and_nonprobabilistic_metadata(smoke_corpus):
    config, records, *_ = smoke_corpus
    directory, manifest = complete(smoke_corpus)
    assert header(directory / PIPELINE) == PIPELINE_COLUMNS
    assert header(directory / METADATA) == METADATA_COLUMNS
    assert header(directory / FULL) == list(records[0]) + METADATA_COLUMNS
    full, pipeline, metadata = (read(directory / name) for name in (FULL, PIPELINE, METADATA))
    assert len(full) == len(pipeline) == len(metadata) == 15
    for raw, projected, meta in zip(full, pipeline, metadata):
        assert raw["sampling_unit_id"] == projected["sampling_unit_id"] == meta["sampling_unit_id"]
        assert {k: raw[k] for k in records[0]} in records
        assert projected["commits_count"] == normalize_commits_count(raw["commits_count"])
        for field in ("issue_body", "issue_title", "concatenated_comments", "closed_at", "created_at"):
            assert projected[field] == raw[field]
        assert projected["artifact_type"] == raw["type"]
        assert all(meta[k] == raw[k] == "" for k in NOT_APPLICABLE)
        assert int(meta["sampling_population"]) > 0
        assert float(meta["sampling_population_weight"]) > 0
    assert {r["commits_count"] for r in pipeline} >= {"0", ""}
    assert any(float(r["commits_count"] or 0) > 0 for r in pipeline)
    for pair in manifest["selection"]["repeated_identity_pairs"]:
        for data in (full, pipeline, metadata):
            assert set(pair["sampling_unit_ids"]) <= {r["sampling_unit_id"] for r in data}
    assert validate_run(directory)["valid"]


@pytest.mark.parametrize("value,expected,kind", [
    ("0.0", "0", "decimal_representations_converted"), ("5.0", "5", "decimal_representations_converted"),
    ("5", "5", "integers_preserved"), ("0", "0", "integers_preserved"),
    ("900719925474099312345678901234567890.0", "900719925474099312345678901234567890", "decimal_representations_converted"),
    ("", "", "missing"), ("   ", "", "missing"), ("null", "", "missing"), ("NaN", "", "missing"),
    ("abc", "", "invalid"), ("-1", "", "invalid"), ("2.5", "", "invalid"),
    ("Infinity", "", "invalid"), ("-Infinity", "", "invalid"),
])
def test_smoke_export_normalization_audit_and_full_integrity(smoke_corpus, value, expected, kind):
    config, records, *_ = smoke_corpus
    for row in records:
        row["commits_count"] = value
    save(config.issues, records)
    before = sha256_file(config.issues)
    directory, manifest = complete(smoke_corpus)
    full, pipeline, metadata = (read(directory / name) for name in (FULL, PIPELINE, METADATA))
    assert len(full) == len(pipeline) == len(metadata) == 15
    assert header(directory / PIPELINE) == PIPELINE_COLUMNS
    assert {row["commits_count"] for row in full} == {value}
    assert {row["commits_count"] for row in pipeline} == {expected}
    ids = [row["sampling_unit_id"] for row in full]
    assert ids == [row["sampling_unit_id"] for row in pipeline] == [row["sampling_unit_id"] for row in metadata]
    assert ids == manifest["selection"]["selected_ids"]
    assert len({row["sampling_stratum"] for row in metadata}) == 9
    assert manifest["selection"]["repeated_identity_pairs"]
    for raw, projected in zip(full, pipeline):
        for name in ("comments_count", "issue_title", "issue_body", "concatenated_comments", "created_at", "closed_at"):
            assert raw[name] == projected[name]
    counts = manifest["export_audit"]["commits_count"]
    assert counts["total"] == counts[kind] == 15
    assert counts["valid"] == (15 if expected else 0)
    assert counts["zeros_preserved"] == (15 if expected == "0" else 0)
    assert len(counts["invalid_records"]) == (15 if kind == "invalid" else 0)
    if kind == "invalid":
        assert [item["sampling_unit_id"] for item in counts["invalid_records"]] == ids
    assert json.loads((directory / VALIDATION).read_text())["export_audit"] == manifest["export_audit"]
    assert "Normalização de commits_count" in (directory / REPORT).read_text()
    assert validate_smoke(directory)["valid"]
    assert sha256_file(config.issues) == before


def test_selection_uses_raw_projection_without_running_export_normalization(smoke_corpus, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Export normalization must not affect smoke selection or its coverage criteria")
    monkeypatch.setattr("web3blockset_sampling.export.normalize_commits_count", forbidden)
    _, chosen, evidence = evaluate(smoke_corpus[0], 20261102, 15)
    assert len(chosen) == 15
    assert all(evidence["checks"].values())


def test_reproduction_across_independent_runs_ignores_only_run_specific_fields(smoke_corpus):
    first_dir, first = complete(smoke_corpus, run_id="first")
    second_dir, second = complete(smoke_corpus, run_id="second")
    assert first["selection"] == second["selection"]
    assert first["inputs"] == second["inputs"]
    assert sha256_file(first_dir / PIPELINE) == sha256_file(second_dir / PIPELINE)
    for filename in (FULL, METADATA):
        a, b = read(first_dir / filename), read(second_dir / filename)
        for row in a + b:
            row.pop("sampling_run_id")
        assert a == b


def test_explicit_authorization_is_required_and_isolated(smoke_corpus):
    config, *_ = smoke_corpus
    before = copy.deepcopy(snapshot(config))
    with pytest.raises(ValidationError, match="--authorize-technical-smoke"):
        run_smoke(config)
    assert not config.output.exists()
    _, manifest = complete(smoke_corpus)
    assert snapshot(config) == before
    assert manifest["authorization"]["human_approval_recorded"] is False
    assert manifest["authorization"]["definitive_sampling_authorized"] is False
    directory, definitive = run(config, definitive=True)
    assert definitive["status"] == "blocked"
    assert not (directory / "final_sample_pipeline.csv").exists()


def test_smoke_never_draws_or_approves_and_preserves_originals(smoke_corpus, monkeypatch):
    config, *_ = smoke_corpus
    paths = [config.issues, config.repositories, config.pilot, config.mapping]
    hashes = {p: sha256_file(p) for p in paths}
    before = snapshot(config)
    def forbidden(*args, **kwargs):
        raise AssertionError("No definitive draw or approval write allowed")
    monkeypatch.setattr("web3blockset_sampling.workflow.draw", forbidden)
    monkeypatch.setattr("web3blockset_sampling.sampling.draw", forbidden)
    directory, manifest = complete(smoke_corpus)
    assert validate_smoke(directory)["valid"]
    assert {p: sha256_file(p) for p in paths} == hashes
    assert snapshot(config) == before
    assert config.approval is None
    assert not list(directory.glob("final_*"))
    assert manifest["definitive_plan"]["draw_executed"] is False


@pytest.mark.parametrize("case", ["count", "pilot", "extra_exclusion", "schema"])
def test_technical_blockers_are_never_bypassed(smoke_corpus, case):
    config, *_ = smoke_corpus
    if case == "count":
        config.expected_counts = {"total": 362, "provider": 321, "community": 41}
    elif case == "pilot":
        save(config.pilot, [{"repository_full_name": "missing/repo", "issue_number": "1", "type": "Issue"}])
    elif case == "extra_exclusion":
        config.smoke = config.pilot
        config.smoke_decision = "Synthetic prior exclusion"
    else:
        config.pipeline_columns["commits_count"] = "missing"
    directory, manifest = run_smoke(config, authorized=True)
    assert manifest["status"] == "blocked"
    assert not (directory / PIPELINE).exists()


def test_existing_run_is_never_overwritten(smoke_corpus):
    directory, _ = complete(smoke_corpus, run_id="unique")
    before = {p.name: sha256_file(p) for p in directory.iterdir()}
    with pytest.raises(FileExistsError):
        run_smoke(smoke_corpus[0], authorized=True, run_id="unique")
    assert before == {p.name: sha256_file(p) for p in directory.iterdir()}


@pytest.mark.parametrize("run_id", ["../escape", "/tmp/escape", ".", "..", "a/b", "", "a" * 97])
def test_bad_run_id_rejected(smoke_corpus, run_id):
    with pytest.raises(ValidationError, match="run-id"):
        run_smoke(smoke_corpus[0], authorized=True, run_id=run_id)


@pytest.mark.parametrize("filename,field", [(PIPELINE, "commits_count"), (PIPELINE, "issue_body"),
                                           (PIPELINE, "closed_at"), (FULL, "unknown_metadata"),
                                           (METADATA, "sampling_design_weight"), (METADATA, "sampling_source")])
def test_cell_tampering_rejected_even_with_new_checksum(smoke_corpus, filename, field):
    directory, manifest = complete(smoke_corpus)
    data = read(directory / filename)
    data[0][field] = "tampered"
    save(directory / filename, data)
    manifest["artifacts"][filename] = sha256_file(directory / filename)
    rewrite_manifest(directory, manifest)
    with pytest.raises(ValidationError):
        validate_smoke(directory)


@pytest.mark.parametrize("mutation", ["reorder", "drop", "duplicate", "blank_id", "header", "pair_metadata"])
def test_csv_structure_and_pair_tampering_rejected(smoke_corpus, mutation):
    directory, manifest = complete(smoke_corpus)
    target = directory / PIPELINE
    data = read(target)
    if mutation == "reorder":
        data.reverse()
    elif mutation == "drop":
        data.pop()
    elif mutation == "duplicate":
        data[-1] = dict(data[0])
    elif mutation == "blank_id":
        data[0]["sampling_unit_id"] = ""
    elif mutation == "header":
        data = [{k: v for k, v in row.items() if k != "commits_count"} for row in data]
    else:
        target = directory / METADATA
        data = read(target)
        pair = manifest["selection"]["repeated_identity_pairs"][0]
        uid = pair["sampling_unit_ids"][0]
        next(r for r in data if r["sampling_unit_id"] == uid)["sampling_logical_id"] = "fake"
    save(target, data)
    manifest["artifacts"][target.name] = sha256_file(target)
    rewrite_manifest(directory, manifest)
    with pytest.raises(ValidationError):
        validate_smoke(directory)


@pytest.mark.parametrize("field,value", [("seed", 88), ("run_type", "final"), ("selected_size", 14),
                                       ("pending_methodological_decisions", []), ("authorization", {}),
                                       ("population_inference_allowed", True), ("inputs", {}),
                                       ("implementation_sha256", "bad"), ("blockers", ["bad"]),
                                       ("export_audit", {})])
def test_manifest_claims_are_recomputed(smoke_corpus, field, value):
    directory, manifest = complete(smoke_corpus)
    manifest[field] = value
    rewrite_manifest(directory, manifest)
    with pytest.raises(ValidationError):
        validate_smoke(directory)


@pytest.mark.parametrize("filename", [REPORT, VALIDATION])
def test_reports_are_recomputed_even_with_new_checksums(smoke_corpus, filename):
    directory, manifest = complete(smoke_corpus)
    target = directory / filename
    target.write_text('{}' if filename.endswith('.json') else "alterado", encoding="utf-8")
    manifest["artifacts"][filename] = sha256_file(target)
    rewrite_manifest(directory, manifest)
    with pytest.raises(ValidationError, match="inconsistente"):
        validate_smoke(directory)


def test_hashes_input_changes_and_no_sensitive_environment(smoke_corpus, monkeypatch):
    monkeypatch.setenv("API_KEY", "never-export-this-value")
    directory, manifest = complete(smoke_corpus)
    assert "never-export-this-value" not in (directory / MANIFEST).read_text()
    assert "API_KEY" not in (directory / MANIFEST).read_text()
    for name, hashed in manifest["artifacts"].items():
        assert sha256_file(directory / name) == hashed
    config = smoke_corpus[0]
    config.pilot.write_text(config.pilot.read_text() + "\n")
    with pytest.raises(ValidationError, match="Entrada"):
        validate_smoke(directory)


def test_cli_smoke_and_generic_validate(smoke_corpus, capsys):
    config = smoke_corpus[0]
    config_file = config.pilot.parent / "smoke_config.json"
    config_file.write_text(json.dumps(snapshot(config)))
    assert main(["smoke", "--config", str(config_file)]) == 2
    assert "authorize-technical-smoke" in capsys.readouterr().err
    output = config.pilot.parent / "custom"
    assert main(["smoke", "--config", str(config_file), "--authorize-technical-smoke", "--size", "15",
                 "--seed", "99", "--run-id", "cli-smoke", "--output", str(output)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["run_directory"] == str(output / "smoke_tests/cli-smoke")
    assert result["selected_size"] == 15
    assert main(["validate", "--run-dir", result["run_directory"]]) == 0
    assert json.loads(capsys.readouterr().out)["valid"]


def test_same_source_duplicate_does_not_satisfy_required_pair(smoke_corpus):
    config = smoke_corpus[0]
    candidates, _ = profile_candidates(prepare(config), 1)
    candidates = [replace(c, unit=replace(c.unit, source="provider")) for c in candidates]
    with pytest.raises(ValidationError, match="Par real obrigatório"):
        select(candidates)


def test_pilot_removes_both_occurrences_before_pair_selection(smoke_corpus):
    config, records, _, pilots = smoke_corpus
    paired = records[-1]
    pilots[0] = {"repository_full_name": "Org/" + paired["repository"], "issue_number": paired["issue_number"],
                 "type": paired["type"]}
    save(config.pilot, pilots)
    prepared = prepare(config)
    assert not any(u.record_id == paired["issue_id"] for u in prepared.eligible)
    directory, manifest = run_smoke(config, authorized=True)
    assert manifest["status"] == "blocked"
    assert "Par real obrigatório" in manifest["blockers"][0]
    assert not (directory / PIPELINE).exists()


def test_existing_preserve_rows_policy_remains_supported_without_rewriting(smoke_corpus):
    config = smoke_corpus[0]
    config.duplicate_policy = "preserve_rows"
    config.duplicate_decision = "Synthetic fixture occurrence policy"
    _, manifest = complete(smoke_corpus)
    assert all(uid.startswith("row:") for uid in manifest["selection"]["selected_ids"])
    assert len(manifest["pending_methodological_decisions"]) == 1


def test_lexical_cues_are_word_bounded_and_not_labels(smoke_corpus):
    unit = prepare(smoke_corpus[0]).eligible[0]
    pipeline = dict.fromkeys(PIPELINE_COLUMNS, "")
    pipeline["issue_title"] = "ProXy and ORACLE; proximal factories oracles"
    candidate = features(unit, pipeline, 4)
    assert candidate.lexical_terms == ("proxy", "oracle")
    pipeline["issue_title"] = "proxymap oracles factorywork"
    assert not features(unit, pipeline, 4).lexical_terms


def test_code_mutation_during_run_cannot_complete(smoke_corpus, monkeypatch):
    from web3blockset_sampling import smoke
    real_hash = smoke.implementation_hash
    calls = 0
    def changed_hash():
        nonlocal calls
        calls += 1
        return real_hash() if calls == 1 else "changed"
    monkeypatch.setattr(smoke, "implementation_hash", changed_hash)
    _, manifest = run_smoke(smoke_corpus[0], authorized=True)
    assert manifest["status"] == "blocked"
    assert "Implementação modificada" in manifest["blockers"][0]


def test_input_mutation_during_retrieval_cannot_complete(smoke_corpus, monkeypatch):
    from web3blockset_sampling import smoke
    original = smoke.records_for
    def mutating(prepared, chosen, run_id):
        result = original(prepared, chosen, run_id)
        prepared.config.pilot.write_text(prepared.config.pilot.read_text() + "\n")
        return result
    monkeypatch.setattr(smoke, "records_for", mutating)
    _, manifest = run_smoke(smoke_corpus[0], authorized=True)
    assert manifest["status"] == "blocked"
    assert "entrada modificado" in manifest["blockers"][0]


def test_missing_artifact_and_wrong_hash_are_rejected(smoke_corpus):
    directory, manifest = complete(smoke_corpus)
    manifest["artifacts"].pop(PIPELINE)
    rewrite_manifest(directory, manifest)
    with pytest.raises(ValidationError, match="Lista de artefatos"):
        validate_smoke(directory)
    manifest["artifacts"][PIPELINE] = "bad"
    rewrite_manifest(directory, manifest)
    with pytest.raises(ValidationError, match="Checksum"):
        validate_smoke(directory)


def test_selected_pipeline_retains_raw_null_literals_and_text_cells(smoke_corpus):
    config, records, *_ = smoke_corpus
    for i, row in enumerate(records):
        row["unknown_metadata"] = "null" if i % 2 else "NA"
        row["issue_title"] = '  título, "aspas" 🧪\r\n汉字  '
        row["issue_body"] = "NaN" if i % 3 else ""
    save(config.issues, records)
    directory, _ = complete(smoke_corpus)
    exported = read(directory / FULL)
    assert {r["unknown_metadata"] for r in exported} <= {"null", "NA"}
    assert all(r["issue_title"] == records[0]["issue_title"] for r in exported)
    assert {r["issue_body"] for r in exported} == {"NaN", ""}
    assert validate_smoke(directory)["valid"]
