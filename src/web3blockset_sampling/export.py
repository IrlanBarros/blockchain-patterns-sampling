"""Second-pass retrieval and reversible pipeline aliases; original texts stay intact."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from .errors import ValidationError
from .ingestion import digest_json, header, rows, write_csv
from .preparation import Prepared, Unit
from .statistics import Allocation

META = ["unit_id", "logical_id", "repository", "source", "category", "original_category", "stratum", "population",
        "sample_size", "population_weight", "design_weight", "provider_weight", "inclusion_probability", "run_id"]
METADATA_COLUMNS = ["sampling_" + name for name in META]


def metadata(unit: Unit, allocation: Allocation, run_id: str) -> dict:
    values = [unit.unit_id, unit.logical_id, unit.repository, unit.source, unit.category, unit.original_category, unit.stratum,
              allocation.population, allocation.sample, allocation.population_weight,
              allocation.design_weight, allocation.provider_weight, allocation.sampling_fraction, run_id]
    return dict(zip(METADATA_COLUMNS, ("" if v is None else str(v) for v in values)))


def pipeline_row(full: dict, prepared: Prepared) -> dict:
    result = dict(full)
    special = {"@repository": full["sampling_repository"],
               "@number": str(int(full[prepared.config.schemas["issues"]["number"]].strip().split(".")[0])),
               "@artifact_type": full[prepared.config.schemas["issues"]["artifact_type"]]}
    for destination, source in prepared.config.pipeline_columns.items():
        if source.startswith("@"):
            if source not in special:
                raise ValidationError(f"Alias de pipeline desconhecido: {source}")
            result[destination] = special[source]
        else:
            if source not in full:
                raise ValidationError(f"Coluna do pipeline ausente: {source}; configure pipeline_columns")
            result[destination] = full[source]
    return result


def selected_rows(prepared: Prepared, selected: set[str], allocation: dict[str, Allocation], run_id: str) -> list[dict]:
    fields = header(prepared.config.issues, prepared.config.encoding, prepared.config.delimiter)
    if set(fields) & set(METADATA_COLUMNS):
        raise ValidationError("Colunas originais colidem com o namespace reservado sampling_*")
    lookup = {(u.row_hash, u.row_occurrence): u for u in prepared.units if u.unit_id in selected}
    occurrences: Counter = Counter()
    recovered = {}
    for row in rows(prepared.config.issues, prepared.config.encoding, prepared.config.delimiter):
        hashed = digest_json(row)
        occurrences[hashed] += 1
        unit = lookup.get((hashed, occurrences[hashed]))
        if unit:
            recovered[unit.unit_id] = {**row, **metadata(unit, allocation[unit.stratum], run_id)}
    if set(recovered) != selected:
        raise ValidationError("Segunda passagem não recuperou exatamente os registros sorteados")
    return [recovered[uid] for uid in sorted(recovered)]


def export_samples(directory: Path, prepared: Prepared, selected: set[str],
                   allocation: dict[str, Allocation], run_id: str) -> None:
    records = selected_rows(prepared, selected, allocation, run_id)
    original_fields = header(prepared.config.issues, prepared.config.encoding, prepared.config.delimiter)
    full_fields = original_fields + METADATA_COLUMNS
    pipeline_fields = full_fields + [k for k in prepared.config.pipeline_columns if k not in full_fields]
    pipeline = [pipeline_row(row, prepared) for row in records]
    required = {"repository", "issue_number", "issue_title", "issue_body", "concatenated_comments"}
    if not required <= set(pipeline_fields):
        raise ValidationError(f"Exportação sem campos exigidos pelo pipeline: {sorted(required - set(pipeline_fields))}")
    # The inspected classifier keys records by (repository, issue_number).
    if not set(prepared.config.pipeline_key_fields) <= set(pipeline_fields):
        raise ValidationError("pipeline_key_fields contém campos ausentes na exportação")
    keys = [tuple(r[k].casefold().strip() for k in prepared.config.pipeline_key_fields) for r in pipeline]
    if len(keys) != len(set(keys)):
        raise ValidationError("A amostra contém (repository, issue_number) repetido, incompatível com o pipeline inspecionado. "
                              "É necessária uma adaptação explícita do contrato do classificador; não refaça o sorteio para esconder a colisão")
    write_csv(directory / "final_sample_full.csv", full_fields, records)
    write_csv(directory / "final_sample_pipeline.csv", pipeline_fields, pipeline)
