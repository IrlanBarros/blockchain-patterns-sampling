"""Reproduce the descriptive annexes of the real-corpus audit, without sampling.

Uses an existing preparation snapshot and duplicate report. All original rows
remain in the counts, including blank text and inconsistent timestamps.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from web3blockset_sampling.config import load_config
from web3blockset_sampling.errors import ValidationError
from web3blockset_sampling.ingestion import header, read_json, rows, sha256_file, write_json


def audit(run_dir: Path, output_dir: Path) -> tuple[dict, dict]:
    manifest = read_json(run_dir / "sampling_manifest.json")
    config_path = run_dir / "config_snapshot.json"
    if sha256_file(config_path) != manifest["config_sha256"]:
        raise ValidationError("Configuração da preparação foi alterada")
    config = load_config(config_path)
    baseline = manifest["inputs"]["issues"]["sha256"]
    if sha256_file(config.issues) != baseline:
        raise ValidationError("Corpus difere da preparação original")
    duplicate_path = run_dir / "duplicate_groups.csv"
    if sha256_file(duplicate_path) != manifest["artifacts"][duplicate_path.name]:
        raise ValidationError("Relatório de duplicidades foi alterado")
    import json
    duplicate_ids = {rid for r in rows(duplicate_path) for rid in json.loads(r["record_ids"])}
    schema = config.schemas["issues"]
    required = {schema[k] for k in ("source", "category", "artifact_type", "record_id")}
    required |= {"issue_title", "issue_body", "concatenated_comments", "raw_text", "created_at", "updated_at", "closed_at", "year", "state"}
    if not required <= set(header(config.issues, config.encoding, config.delimiter)):
        raise ValidationError("Este anexo exige as colunas documentadas do corpus real")
    categories, types, years, missing, chronological = (defaultdict(Counter) for _ in range(5))
    duplicates = defaultdict(list)
    examples = defaultdict(list)
    count = 0
    for count, row in enumerate(rows(config.issues, config.encoding, config.delimiter), 1):
        source = config.source_values[row[schema["source"]].strip().casefold()]
        categories[source][row[schema["category"]]] += 1
        types[source][row[schema["artifact_type"]]] += 1
        dates = {k: datetime.fromisoformat(row[k]) if row[k] else None
                 for k in ("created_at", "updated_at", "closed_at")}
        # A failed parse is a visible error; the annex never drops a row to continue.
        if not dates["created_at"] or not dates["updated_at"] or any(d is not None and d.tzinfo is None for d in dates.values()):
            raise ValidationError("Datas obrigatórias ausentes ou sem timezone; confira o perfil de inspect")
        years[source][str(dates["created_at"].year)] += 1
        for field in ("issue_title", "issue_body", "concatenated_comments", schema["category"]):
            missing[source][field] += not row[field].strip()
        flags = {
            "closed_before_created": bool(dates["closed_at"] and dates["closed_at"] < dates["created_at"]),
            "updated_before_created": dates["updated_at"] < dates["created_at"],
            "closed_after_updated": bool(dates["closed_at"] and dates["closed_at"] > dates["updated_at"]),
            "state_closed_without_date": row["state"] == "closed" and not row["closed_at"],
            "state_open_with_close_date": row["state"] == "open" and bool(row["closed_at"]),
            "year_differs_from_created_year": int(float(row["year"])) != dates["created_at"].year,
        }
        for flag, failed in flags.items():
            chronological[source][flag] += failed
            if failed and len(examples[flag]) < 20:
                examples[flag].append(row[schema["record_id"]])
        if row[schema["record_id"]] in duplicate_ids:
            duplicates[row[schema["record_id"]]].append(row)
    differing_fields = Counter()
    different_instants = Counter({k: 0 for k in ("created_at", "updated_at", "closed_at")})
    for group in duplicates.values():
        for field in group[0]:
            differing_fields[field] += len({r[field] for r in group}) > 1
        for field in different_instants:
            instants = {datetime.fromisoformat(r[field]) if r[field] else None for r in group}
            different_instants[field] += len(instants) > 1
    if count != manifest["eligible_population"] + sum(
        value["rows_removed"] for value in manifest["exclusions"].values() if value is not None
    ):
        raise ValidationError("Contagem de linhas do anexo diverge da preparação")
    if sha256_file(config.issues) != baseline:
        raise ValidationError("Corpus alterado durante o anexo")
    provenance = {"run_id": manifest["run_id"], "input_rows": count, "issues_sha256": baseline,
                  "script_sha256": sha256_file(Path(__file__))}
    details = {"provenance": provenance, "source_categories": dict(categories), "source_types": dict(types),
               "creation_years_by_source": dict(years), "missing_by_source": dict(missing),
               "duplicate_groups": len(duplicates),
               "fields_differing_between_duplicate_occurrences": {k: n for k, n in differing_fields.items() if n},
               "duplicate_text_fields_identical": not any(differing_fields[k] for k in
                                                          ("issue_title", "issue_body", "concatenated_comments", "raw_text"))}
    temporal = {"provenance": provenance, "checks_by_source": dict(chronological), "examples_issue_ids": dict(examples),
                "duplicate_groups_with_different_instants": dict(different_instants)}
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "corpus_additional_audit.json", details)
    write_json(output_dir / "corpus_temporal_consistency_audit.json", temporal)
    return details, temporal


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    audit(args.run_dir, args.output_dir)
    print(f"Anexos gravados em {args.output_dir}; nenhum registro foi sorteado ou alterado")
