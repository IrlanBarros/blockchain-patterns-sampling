import json

from conftest import save
from scripts.audit_corpus_details import audit
from web3blockset_sampling.ingestion import sha256_file
from web3blockset_sampling.workflow import run


def test_annex_distinguishes_timestamp_representation_and_chronology_without_deleting(corpus):
    config, records, repositories, _ = corpus
    for row in records:
        row.update(created_at="2025-01-02T00:00:00+00:00", updated_at="2025-01-03T00:00:00+00:00",
                   closed_at="2025-01-03T00:00:00+00:00", year="2025.0", state="closed", raw_text="Same text")
    records[5]["closed_at"] = "2024-01-01T00:00:00Z"
    copied = dict(records[6])
    copied["data_source"] = "community"
    for field in ("created_at", "updated_at", "closed_at"):
        copied[field] = copied[field].replace("+00:00", "Z")
    records.append(copied)
    repositories.append({**repositories[0], "source": "community"})
    config.expected_counts = {"total": 361, "provider": 320, "community": 41}
    save(config.issues, records)
    save(config.repositories, repositories)
    before = sha256_file(config.issues)
    run_dir, manifest = run(config)
    details, temporal = audit(run_dir, config.output / "annex")
    assert details["provenance"]["input_rows"] == 361
    assert details["duplicate_groups"] == 1 and details["duplicate_text_fields_identical"]
    assert temporal["checks_by_source"]["provider"]["closed_before_created"] == 1
    assert not any(temporal["duplicate_groups_with_different_instants"].values())
    assert before == sha256_file(config.issues)
    assert json.loads((config.output / "annex/corpus_additional_audit.json").read_text()) == details
    assert manifest["selected_sample"] == 0
