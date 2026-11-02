"""Second-pass retrieval and reversible pipeline aliases; original texts stay intact."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from .contracts import METADATA_COLUMNS, PIPELINE_COLUMNS
from .errors import ValidationError
from .ingestion import digest_json, header, rows, write_csv
from .normalization import audit_commits_count, normalize_commits_count
from .preparation import Prepared, Unit
from .statistics import Allocation

def metadata(unit: Unit, allocation: Allocation, run_id: str) -> dict:
    values = [unit.unit_id, unit.logical_id, unit.repository, unit.source, unit.category, unit.original_category, unit.stratum,
              allocation.population, allocation.sample, allocation.population_weight,
              allocation.design_weight, allocation.provider_weight, allocation.sampling_fraction, run_id]
    return dict(zip(METADATA_COLUMNS, ("" if v is None else str(v) for v in values)))


def project_pipeline_row(full: dict, prepared: Prepared) -> dict:
    """Project raw aliases, also used by selection before export normalization."""
    result = {"sampling_unit_id": full["sampling_unit_id"]}
    special = {"@repository": full["sampling_repository"],
               "@number": full[prepared.config.schemas["issues"]["number"]],
               "@artifact_type": full[prepared.config.schemas["issues"]["artifact_type"]]}
    for destination in PIPELINE_COLUMNS[1:]:
        source = prepared.config.pipeline_columns[destination]
        if source.startswith("@"):
            if source not in special:
                raise ValidationError(f"Alias de pipeline desconhecido: {source}")
            result[destination] = special[source]
        else:
            if source not in full:
                raise ValidationError(f"Coluna do pipeline ausente: {source}; configure pipeline_columns")
            result[destination] = full[source]
    return result


def pipeline_row(full: dict, prepared: Prepared) -> dict:
    """Apply the classifier contract without mutating any original cell."""
    result = project_pipeline_row(full, prepared)
    result["commits_count"] = normalize_commits_count(result["commits_count"])
    return result


def pipeline_export_audit(records, prepared: Prepared) -> dict:
    """Audit configured aliases against original cells, independently of CSV output."""
    return {"commits_count": audit_commits_count(
        (row["sampling_unit_id"], project_pipeline_row(row, prepared)["commits_count"]) for row in records)}


def metadata_row(full: dict) -> dict:
    """Copy already recorded weights and provenance; never recompute them."""
    return {column: full[column] for column in METADATA_COLUMNS}


def occurrence_rows(prepared: Prepared, selected: set[str]):
    """Stream raw cells with the existing hash/occurrence identity, without new IDs."""
    lookup = {(u.row_hash, u.row_occurrence): u for u in prepared.units if u.unit_id in selected}
    occurrences: Counter = Counter()
    for row in rows(prepared.config.issues, prepared.config.encoding, prepared.config.delimiter):
        hashed = digest_json(row)
        occurrences[hashed] += 1
        unit = lookup.get((hashed, occurrences[hashed]))
        if unit:
            yield unit, row


def recover_rows(prepared: Prepared, selected: set[str]) -> dict[str, dict]:
    """Recover original occurrences for both definitive and technical exports."""
    fields = header(prepared.config.issues, prepared.config.encoding, prepared.config.delimiter)
    if set(fields) & set(METADATA_COLUMNS):
        raise ValidationError("Colunas originais colidem com o namespace reservado sampling_*")
    recovered = {unit.unit_id: row for unit, row in occurrence_rows(prepared, selected)}
    if set(recovered) != selected:
        raise ValidationError("Segunda passagem não recuperou exatamente os registros sorteados")
    return recovered


def selected_rows(prepared: Prepared, selected: set[str], allocation: dict[str, Allocation], run_id: str) -> list[dict]:
    recovered = recover_rows(prepared, selected)
    units = {u.unit_id: u for u in prepared.units if u.unit_id in selected}
    return [{**recovered[uid], **metadata(units[uid], allocation[units[uid].stratum], run_id)}
            for uid in sorted(recovered)]


def export_samples(directory: Path, prepared: Prepared, selected: set[str],
                   allocation: dict[str, Allocation], run_id: str) -> dict:
    records = selected_rows(prepared, selected, allocation, run_id)
    original_fields = header(prepared.config.issues, prepared.config.encoding, prepared.config.delimiter)
    full_fields = original_fields + METADATA_COLUMNS
    pipeline = [pipeline_row(row, prepared) for row in records]
    keys = [row["sampling_unit_id"] for row in records]
    if any(not key or not key.strip() for key in keys) or len(keys) != len(set(keys)):
        raise ValidationError("sampling_unit_id vazio ou duplicado na exportação")
    write_csv(directory / "final_sample_full.csv", full_fields, records)
    write_csv(directory / "final_sample_pipeline.csv", PIPELINE_COLUMNS, pipeline)
    write_csv(directory / "final_sample_metadata.csv", METADATA_COLUMNS, (metadata_row(row) for row in records))
    return pipeline_export_audit(records, prepared)
