"""Regression cases for the provider-only metadata supplied with the real corpus."""

import pytest

from conftest import read, save
from web3blockset_sampling.errors import ValidationError
from web3blockset_sampling.identity import normalize
from web3blockset_sampling.ingestion import sha256_file
from web3blockset_sampling.preparation import prepare, verify_inputs
from web3blockset_sampling.workflow import run, validate_run


def provider_only(corpus):
    config, records, repositories, pilot = corpus
    repositories = [{"#": str(i), "organization": r["owner"],
                     "html_url": f"https://github.com/{r['owner']}/{r['repository']}",
                     "repository_category": r["category"]}
                    for i, r in enumerate(repositories, 1) if r["source"] == "provider"]
    save(config.repositories, repositories)
    config.repository_scope = "provider"
    config.repository_formats = {"repositories": "github_url"}
    config.schemas["repositories"] = {"repository": "html_url", "owner": "organization", "category": "repository_category"}
    return config, records, repositories, pilot


def test_provider_only_metadata_with_community_records(corpus):
    config, *_ = provider_only(corpus)
    before = sha256_file(config.repositories)
    p = prepare(config)
    assert not p.blockers
    assert len(p.units) == 360 and len(p.eligible) == 358
    assert p.audit["join"]["metadata_rows"] == 16
    assert p.audit["join"]["matched_provider_rows"] == 320
    assert p.audit["join"]["matched_rows"] == 320
    assert p.audit["join"]["community_rows_without_provider_join"] == 40
    assert p.audit["join"]["missing_repository_rows"] == 0
    assert p.audit["join"]["organizations"] == 1
    assert before == sha256_file(config.repositories)
    directory, manifest = run(config, True)
    assert manifest["status"] == "complete"
    assert validate_run(directory)["valid"]


def test_community_category_does_not_require_provider_join(corpus):
    config, records, *_ = provider_only(corpus)
    for row in records:
        if row["data_source"] == "community":
            row["repository_category"] = "Other"
    save(config.issues, records)
    p = prepare(config)
    assert not p.blockers
    community = [u for u in p.units if u.source == "community"]
    assert len(community) == 40
    assert all(u.stratum == "Community" and u.category == "" and u.original_category == "Other" for u in community)


def test_provider_must_still_match_official_metadata(corpus):
    config, _, repositories, _ = provider_only(corpus)
    save(config.repositories, repositories[1:])
    p = prepare(config)
    assert p.blockers
    assert p.audit["join"]["missing_repository_rows"] == 20
    assert p.audit["join"]["community_rows_without_provider_join"] == 40


def test_explicit_issue_source_required_for_provider_scope(corpus):
    config, *_ = provider_only(corpus)
    config.schemas["issues"].pop("source")
    with pytest.raises(ValidationError, match="source explícito"):
        prepare(config)


def test_provider_scope_rejects_community_metadata(corpus):
    config, _, repositories, _ = provider_only(corpus)
    for row in repositories:
        row["origin"] = "community"
    save(config.repositories, repositories)
    config.schemas["repositories"]["source"] = "origin"
    with pytest.raises(ValidationError, match="outra origem"):
        prepare(config)


@pytest.mark.parametrize("url", ["https://example.org/Org/Repo", "http://github.com/Org/Repo",
                               "https://github.com/Org/Repo?x=1", "https://github.com/Org/Repo#readme",
                               "https://github.com/Org/Repo/tree/main", "https://user@github.com/Org/Repo",
                               "https://github.com/Org%2fOther/Repo", "https://[invalid/Org/Repo", "https://github.com/"])
def test_invalid_repository_urls_fail(corpus, url):
    config, *_ = provider_only(corpus)
    with pytest.raises(ValidationError):
        normalize({"url": url}, {"repository": "url"}, config, role="repositories")


def test_clone_url_is_an_explicit_supported_representation(corpus):
    config, *_ = provider_only(corpus)
    result = normalize({"url": "https://github.com/Org/Repo.git"}, {"repository": "url"}, config, role="repositories")
    assert result["repository"] == "org/repo"


def test_methodological_document_is_fingerprinted(corpus):
    config, *_ = provider_only(corpus)
    config.methodology = config.pilot.parent / "methodology-reference.txt"
    config.methodology.write_text("Synthetic methodological reference")
    p = prepare(config)
    assert p.inputs["methodology"]["sha256"] == sha256_file(config.methodology)
    config.methodology.write_text("Changed reference")
    with pytest.raises(ValidationError, match="methodology"):
        verify_inputs(p)


def test_url_configuration_does_not_leak_between_roles(corpus):
    config, *_ = provider_only(corpus)
    pilot = read(config.pilot)
    config.repository_formats["pilot"] = "github_url"
    for row in pilot:
        row["repository_full_name"] = "https://github.com/" + row["repository_full_name"]
    save(config.pilot, pilot)
    assert not prepare(config).blockers
