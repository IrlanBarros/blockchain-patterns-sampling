from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path

import pytest

from web3blockset_sampling.config import Config
from web3blockset_sampling.ingestion import sha256_file
from web3blockset_sampling.stratification import STRATA, load_mapping

ROOT = Path(__file__).resolve().parents[1]


def save(path, records):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)


def read(path):
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


@pytest.fixture
def corpus(tmp_path):
    mapping_path = tmp_path / "strata.json"
    shutil.copyfile(ROOT / "configs/strata.json", mapping_path)
    mapping = load_mapping(mapping_path)
    categories = {s: next((c for c, st in mapping.categories.items() if st == s), "") for s in STRATA}
    repositories, records = [], []
    for h, stratum in enumerate(STRATA):
        source = "community" if stratum == "Community" else "provider"
        for repo_index in range(2):
            repo = f"repo-{h}-{repo_index}"
            repositories.append({"owner": "Org", "repository": repo, "source": source, "category": categories[stratum],
                                 "repo_id": str(100 + h * 2 + repo_index)})
            for number in range(1, 21):
                records.append({"owner": "ORG", "repository": repo, "issue_number": str(number),
                                "issue_id": str(len(records) + 1), "type": "Issue" if number % 2 else "Pull Request",
                                "created_at": "2024-01-02T03:04:05+00:00",
                                "closed_at": "2024-01-03T03:04:05+00:00" if number % 5 else "",
                                "state": "closed" if number % 5 else "open", "comments_count": str(number % 4),
                                "commits_count": str(number) if number % 2 == 0 else "",
                                "data_source": source, "repository_category": categories[stratum],
                                "issue_title": f"  Título {number} 🧪  ",
                                "issue_body": "linha 1\r\nlinha 2, \"aspas\"\n汉字" if number % 3 else "",
                                "concatenated_comments": "  comentário\ncom espaços  ", "unknown_metadata": "00001"})
    issues, repos, pilot = (tmp_path / f for f in ("issues.csv", "repos.csv", "pilot.csv"))
    save(issues, records)
    save(repos, repositories)
    pilot_records = []
    for record in (records[0], records[-1]):
        pilot_records.append({"repository_full_name": "Org/" + record["repository"], "issue_number": record["issue_number"], "type": record["type"]})
    save(pilot, pilot_records)
    approval = tmp_path / "approval.json"
    approval.write_text(json.dumps({"mapping_sha256": sha256_file(mapping_path), "approved_by": "Synthetic fixture only",
                                    "approved_at": "2026-10-29T00:00:00Z"}))
    config = Config(issues=issues, repositories=repos, pilot=pilot, mapping=mapping_path, approval=approval,
                    output=tmp_path / "outputs", corpus_version="synthetic-test", corpus_decision="Synthetic fixture, not research data",
                    expected_counts={"total": 360, "provider": 320, "community": 40}, expected_pilot=2,
                    exclusion_decision="Synthetic fixture with two pilot cases", error=0.25,
                    schemas={"issues": {"repository": "repository", "owner": "owner", "number": "issue_number",
                                        "record_id": "issue_id", "source": "data_source", "artifact_type": "type", "category": "repository_category"},
                             "repositories": {"repository": "repository", "owner": "owner", "source": "source", "category": "category"},
                             "pilot": {"repository": "repository_full_name", "number": "issue_number", "artifact_type": "type"}})
    return config, records, repositories, pilot_records
