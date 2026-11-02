import json

import pytest

from conftest import ROOT, read, save
from web3blockset_sampling.errors import ValidationError
from web3blockset_sampling.identity import normalize
from web3blockset_sampling.ingestion import sha256_file
from web3blockset_sampling.preparation import prepare
from web3blockset_sampling.stratification import STRATA, load_mapping

REFERENCE = load_mapping(ROOT / "configs/strata.json")


@pytest.mark.parametrize("category,stratum", list(REFERENCE.categories.items()))
def test_all_33_categories(category, stratum):
    assert REFERENCE.assign("provider", category) == stratum


@pytest.mark.parametrize("category", ["", "Unknown", "other", "Unclassified"])
def test_unknown_or_missing_provider_category(category):
    with pytest.raises(ValidationError):
        REFERENCE.assign("provider", category)


def test_other_and_community():
    assert REFERENCE.assign("provider", "Other") == "Outros"
    assert REFERENCE.assign("community", "") == "Community"
    assert REFERENCE.assign("community", "Other") == "Community"


@pytest.mark.parametrize("mutation", ["duplicate", "missing", "extra", "wrong_strata", "community_category"])
def test_bad_mapping(corpus, mutation):
    config, *_ = corpus
    data = json.loads(config.mapping.read_text())
    if mutation == "duplicate":
        data["strata"]["Outros"].append("SDK / Library")
    elif mutation == "missing":
        data["strata"]["Blockchain Core"].pop()
    elif mutation == "extra":
        data["strata"]["Outros"].append("Unknown")
    elif mutation == "wrong_strata":
        data["strata"]["X"] = []
    else:
        data["strata"]["Community"] = ["Other"]
    config.mapping.write_text(json.dumps(data))
    with pytest.raises(ValidationError):
        load_mapping(config.mapping)


def test_complete_join_identity_and_exclusion(corpus):
    config, *_ = corpus
    p = prepare(config)
    assert not p.blockers
    assert len(p.units) == 360
    assert len(p.eligible) == 358
    assert len({u.logical_id for u in p.units}) == 360
    assert p.audit["join"]["row_multiplication"] == 0
    assert p.audit["pilot_exclusion"]["rows_removed"] == 2
    assert all((u.source == "community") == (u.stratum == "Community") for u in p.units)


@pytest.mark.parametrize("mutation", ["unknown_repo", "unknown_source", "unknown_type", "missing_number", "short_repo", "category_conflict"])
def test_invalid_records_are_reported_and_blocked(corpus, mutation):
    config, records, repositories, _ = corpus
    if mutation == "unknown_repo":
        records[0]["repository"] = "missing"
    elif mutation == "unknown_source":
        records[0]["data_source"] = "both"
    elif mutation == "unknown_type":
        records[0]["type"] = "Discussion"
    elif mutation == "missing_number":
        records[0]["issue_number"] = ""
    elif mutation == "short_repo":
        records[0]["owner"] = ""
    elif mutation == "category_conflict":
        records[0]["repository_category"] = "Other"
    save(config.issues, records)
    p = prepare(config)
    assert p.blockers
    assert p.audit["invalid_rows"] >= 1
    assert p.audit["input_rows"] == p.audit["resolved_rows"] + p.audit["invalid_rows"]


@pytest.mark.parametrize("has_records", [True, False])
def test_unknown_metadata_category_is_rejected_even_without_records(corpus, has_records):
    config, records, repositories, _ = corpus
    target = repositories[0] if has_records else {**repositories[0], "repository": "unused-repository"}
    target["category"] = "Unknown"
    if not has_records:
        repositories.append(target)
    save(config.repositories, repositories)
    with pytest.raises(ValidationError, match="Categoria provider ausente ou desconhecida"):
        prepare(config)


def test_ambiguous_repository_key_rejected(corpus):
    config, _, repos, _ = corpus
    save(config.repositories, repos + [repos[0]])
    with pytest.raises(ValidationError, match="ambígua"):
        prepare(config)


def test_source_conflict_join_by_repository(corpus):
    config, records, repos, _ = corpus
    config.join_fields = ["repository"]
    repos[0]["source"] = "community"
    save(config.repositories, repos)
    p = prepare(config)
    assert p.audit["invalid_rows"] == 20
    assert any("Origem" in e["error"] for e in p.audit["invalid_examples"])


def test_numeric_repository_join_checks_names(corpus):
    config, records, repos, _ = corpus
    for row in records:
        row["repo_id"] = next(r["repo_id"] for r in repos if r["repository"] == row["repository"])
    config.join_fields = ["repository_id"]
    config.schemas["issues"]["repository_id"] = "repo_id"
    config.schemas["repositories"]["repository_id"] = "repo_id"
    records[0]["repository"] = "wrong-name"
    save(config.issues, records)
    p = prepare(config)
    assert p.audit["invalid_rows"] == 1


def test_identical_rows_audited_not_automatically_deduplicated(corpus):
    config, records, *_ = corpus
    records.append(dict(records[5]))
    config.expected_counts = {"total": 361, "provider": 321, "community": 40}
    save(config.issues, records)
    p = prepare(config)
    assert p.audit["duplicates"]["exact_extra_rows"] == 1
    assert p.audit["duplicates"]["logical_extra_rows"] == 1
    assert len(p.units) == 361
    assert p.blockers
    config.duplicate_policy = "preserve_rows"
    with pytest.raises(ValidationError, match="duplicate_decision"):
        prepare(config)
    config.duplicate_decision = "Approved synthetic occurrence units"
    p = prepare(config)
    assert not p.blockers
    assert len({u.unit_id for u in p.units}) == 361


def test_issue_pr_same_number_is_distinct(corpus):
    config, records, *_ = corpus
    records[1]["issue_number"] = records[0]["issue_number"]
    save(config.issues, records)
    p = prepare(config)
    assert not p.blockers
    assert p.audit["duplicates"]["repository_number_multiple_types"] == 1
    assert p.units[0].logical_id != p.units[1].logical_id


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "wrong_type"])
def test_bad_pilot_blocks(corpus, mutation):
    config, _, _, pilot = corpus
    if mutation == "missing":
        pilot[0]["issue_number"] = "999999"
    elif mutation == "duplicate":
        pilot[1] = dict(pilot[0])
    else:
        pilot[0]["type"] = "Pull Request"
    save(config.pilot, pilot)
    p = prepare(config)
    assert p.blockers
    assert p.audit["pilot_exclusion"]["missing_count"] or p.audit["pilot_exclusion"]["duplicate_keys"]


def test_partial_pilot_key_requires_unique_logical_match(corpus):
    config, records, *_ = corpus
    config.pilot_fields = ["repository", "number"]
    config.schemas["pilot"].pop("artifact_type")
    assert not prepare(config).blockers
    records[1]["issue_number"] = records[0]["issue_number"]
    save(config.issues, records)
    p = prepare(config)
    assert p.audit["pilot_exclusion"]["ambiguous_count"] == 1
    assert p.blockers


def test_pilot_logical_identifiers_vs_rows(corpus):
    config, records, *_ = corpus
    records.append(dict(records[0]))
    config.expected_counts = {"total": 361, "provider": 321, "community": 40}
    config.duplicate_policy, config.duplicate_decision = "preserve_rows", "Synthetic approval"
    save(config.issues, records)
    p = prepare(config)
    assert p.audit["pilot_exclusion"]["logical_identifiers_excluded"] == 2
    assert p.audit["pilot_exclusion"]["rows_removed"] == 3
    assert len(p.eligible) == 358


def test_smoke_exclusion_is_opt_in(corpus):
    config, records, _, pilot = corpus
    config.smoke = config.pilot.parent / "smoke.csv"
    save(config.smoke, [pilot[0]])
    with pytest.raises(ValidationError, match="smoke_decision"):
        prepare(config)
    config.smoke_decision = "Synthetic opt-in"
    p = prepare(config)
    assert not p.blockers
    assert p.audit["smoke_exclusion"]["overlap_previous_exclusions"] == 1
    assert p.audit["smoke_exclusion"]["rows_removed"] == 0


def test_approval_bound_to_exact_mapping_hash(corpus):
    config, *_ = corpus
    config.approval = None
    assert any("aprovado" in b for b in prepare(config).blockers)
    config.approval = config.pilot.parent / "approval.json"
    config.mapping.write_text(config.mapping.read_text() + "\n")
    assert any("aprovado" in b for b in prepare(config).blockers)


def test_missing_columns_rejected(corpus):
    config, *_ = corpus
    config.schemas["issues"]["number"] = "absent"
    with pytest.raises(ValidationError, match="Colunas"):
        prepare(config)


def test_universe_not_silently_switched(corpus):
    config, *_ = corpus
    config.corpus_version = "original-msr2026"
    with pytest.raises(ValidationError, match="contagens"):
        config.validate()
    config.corpus_version, config.corpus_decision = "canonicalized", ""
    with pytest.raises(ValidationError, match="corpus_decision"):
        config.validate()


def test_identity_normalization_is_explicit_and_text_preserved(corpus):
    config, *_ = corpus
    row = {"repo": "Owner/Repo", "num": "001.0", "type": "PR"}
    result = normalize(row, {"repository": "repo", "number": "num", "artifact_type": "type"}, config)
    assert result == {"repository": "owner/repo", "number": "1", "artifact_type": "pull_request"}
    assert row["num"] == "001.0"


def test_origin_can_be_derived_from_unique_metadata(corpus):
    config, *_ = corpus
    config.join_fields = ["repository"]
    config.schemas["issues"].pop("source")
    p = prepare(config)
    assert not p.blockers
    assert p.audit["sources_before_exclusions"] == {"provider": 320, "community": 40}


def test_same_artifact_across_origins_excluded_in_both(corpus):
    config, records, repos, _ = corpus
    copied = dict(records[0])
    copied["data_source"] = "community"
    records.append(copied)
    repos.append({**repos[0], "source": "community", "category": ""})
    config.expected_counts = {"total": 361, "provider": 320, "community": 41}
    config.duplicate_policy, config.duplicate_decision = "preserve_rows", "Synthetic occurrence approval"
    save(config.issues, records)
    save(config.repositories, repos)
    p = prepare(config)
    assert not p.blockers
    assert p.audit["pilot_exclusion"]["logical_identifiers_excluded"] == 2
    assert p.audit["pilot_exclusion"]["rows_removed"] == 3
    assert not any(u.repository == "org/repo-0-0" and u.pilot_key[1] == "1" for u in p.eligible)


def test_source_cannot_hide_same_artifact_from_pilot(corpus):
    config, *_ = corpus
    config.identity_fields.append("source")
    with pytest.raises(ValidationError, match="intrínsecos"):
        config.validate()


def test_distinguish_logical_and_exact_duplicates(corpus):
    config, records, *_ = corpus
    changed = dict(records[6])
    changed["issue_body"] = "different text"
    records.append(changed)
    config.expected_counts = {"total": 361, "provider": 321, "community": 40}
    save(config.issues, records)
    p = prepare(config)
    assert p.audit["duplicates"]["exact_extra_rows"] == 0
    assert p.audit["duplicates"]["logical_extra_rows"] == 1
    assert p.blockers


@pytest.mark.parametrize("field,value", [("z", "bad"), ("seed", True), ("expected_pilot", "200"),
                                          ("schemas", []), ("duplicate_decision", None), ("join_fields", "repository")])
def test_invalid_config_types_are_actionable(corpus, field, value):
    config, *_ = corpus
    setattr(config, field, value)
    with pytest.raises(ValidationError):
        config.validate()
