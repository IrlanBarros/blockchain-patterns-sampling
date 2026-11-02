"""Independent invariants, including deterministic replay and original field checks."""

from __future__ import annotations

import math
from collections import Counter
from pathlib import Path

from .contracts import METADATA_COLUMNS, PIPELINE_COLUMNS
from .errors import ValidationError
from .export import metadata, metadata_row, pipeline_row
from .ingestion import digest_json, header, rows
from .preparation import Prepared, verify_inputs
from .sampling import draw
from .statistics import Allocation, sample_size
from .stratification import STRATA


def check_preparation(prepared: Prepared, allocation: dict[str, Allocation]) -> dict:
    """Validate counts and weights without drawing any unit, even in dry runs."""
    eligible = prepared.eligible
    all_ids = {u.unit_id for u in prepared.units}
    populations = Counter(u.stratum for u in eligible)
    pilot_keys = {tuple(k) for role in ("pilot", "smoke")
                  for k in prepared.audit.get(role + "_exclusion", {}).get("keys", [])}
    join = prepared.audit["join"]
    provider_total = sum(a.population for s, a in allocation.items() if s != "Community")
    checks = {
        "input_rows_accounted": prepared.audit["input_rows"] == len(prepared.units) + prepared.audit["invalid_rows"],
        "no_invalid_rows": prepared.audit["invalid_rows"] == 0,
        "join_balance_preserved": (join["matched_rows"] + join["community_rows_without_provider_join"]
                                   + join["unresolved_rows"] == prepared.audit["input_rows"]),
        "no_join_multiplication": join["row_multiplication"] == 0,
        "metadata_keys_unique": join["metadata_rows"] == join["unique_join_keys"],
        "unique_unit_ids": len(all_ids) == len(prepared.units),
        "exclusions_accounted": prepared.excluded <= all_ids and len(eligible) + len(prepared.excluded) == len(prepared.units),
        "eligible_population_has_no_pilot_or_smoke": not any(u.pilot_key in pilot_keys for u in eligible),
        "nine_expected_strata": set(allocation) == set(STRATA),
        "population_sum": sum(a.population for a in allocation.values()) == len(eligible),
        "population_per_stratum": all(populations[s] == a.population for s, a in allocation.items()),
        "weights_sum_to_one": math.isclose(sum(a.population_weight for a in allocation.values()), 1, abs_tol=1e-12),
        "provider_weights_sum_to_one": (not provider_total or
                                        math.isclose(sum(a.provider_weight or 0 for a in allocation.values()), 1, abs_tol=1e-12)),
        "provider_weight_consistency": all(
            a.provider_weight is None if s == "Community" or not provider_total
            else math.isclose(a.provider_weight, a.population / provider_total, abs_tol=1e-12)
            for s, a in allocation.items()),
        "community_stratum": all((u.source == "community") == (u.stratum == "Community") for u in eligible),
        "provider_mapping": all(prepared.mapping.assign(u.source, u.category) == u.stratum for u in eligible),
        "formula_consistency": all(a.sample == sample_size(a.population, prepared.config.z, prepared.config.p,
                                                          prepared.config.error) for a in allocation.values()),
        "weight_consistency": all(math.isclose(a.population_weight, a.population / len(eligible), abs_tol=1e-12)
                                  and (not a.sample or math.isclose(a.design_weight, a.population / a.sample))
                                  and (not a.population or math.isclose(a.sampling_fraction, a.sample / a.population))
                                  for a in allocation.values()),
        "expansion_weights_recover_population": math.isclose(
            sum(a.sample * (a.design_weight or 0) for a in allocation.values()), len(eligible), abs_tol=1e-7),
    }
    verify_inputs(prepared)
    checks["inputs_unchanged"] = True
    return checks


def check_design(prepared: Prepared, allocation: dict[str, Allocation], selected: set[str]) -> dict:
    eligible = prepared.eligible
    eligible_ids = {u.unit_id for u in eligible}
    chosen = [u for u in eligible if u.unit_id in selected]
    counts = Counter(u.stratum for u in chosen)
    pilot_keys = {tuple(k) for role in ("pilot", "smoke")
                  for k in prepared.audit.get(role + "_exclusion", {}).get("keys", [])}
    checks = {**check_preparation(prepared, allocation),
        "selected_eligible": selected <= eligible_ids,
        "without_replacement": len(chosen) == len(selected),
        "no_pilot_or_smoke_overlap": not any(u.pilot_key in pilot_keys for u in chosen),
        "exact_allocation": all(counts[s] == a.sample for s, a in allocation.items()),
        "reproducible_selection": selected == draw(eligible, allocation, prepared.config.seed),
    }
    if not all(checks.values()):
        raise ValidationError(f"Verificações de desenho falharam: {[k for k, v in checks.items() if not v]}")
    return checks


def _read_export(path: Path, fields: list[str]) -> dict[str, dict]:
    if header(path) != fields:
        raise ValidationError(f"Cabeçalho da exportação divergente: {path.name}")
    indexed = {}
    for row in rows(path):
        uid = row["sampling_unit_id"]
        if not uid or not uid.strip():
            raise ValidationError(f"sampling_unit_id vazio em {path.name}")
        if uid in indexed:
            raise ValidationError(f"sampling_unit_id duplicado em {path.name}: {uid}")
        indexed[uid] = row
    return indexed


def check_exports(directory: Path, prepared: Prepared, allocation: dict[str, Allocation],
                  selected: set[str], run_id: str) -> dict:
    original_fields = header(prepared.config.issues, prepared.config.encoding, prepared.config.delimiter)
    fields = original_fields + METADATA_COLUMNS
    full_rows = _read_export(directory / "final_sample_full.csv", fields)
    pipeline_rows = _read_export(directory / "final_sample_pipeline.csv", PIPELINE_COLUMNS)
    metadata_rows = _read_export(directory / "final_sample_metadata.csv", METADATA_COLUMNS)
    if not (len(full_rows) == len(pipeline_rows) == len(metadata_rows) == len(selected)):
        raise ValidationError("Quantidades de registros dos três arquivos divergem da seleção")
    if any(set(records) != selected for records in (full_rows, pipeline_rows, metadata_rows)):
        raise ValidationError("Chaves dos três arquivos divergem dos registros sorteados")
    units = {u.unit_id: u for u in prepared.eligible if u.unit_id in selected}
    if set(units) != selected:
        raise ValidationError("Seleção contém unidades não elegíveis")
    for uid, row in full_rows.items():
        unit = units[uid]
        if digest_json({k: row[k] for k in original_fields}) != unit.row_hash:
            raise ValidationError(f"Conteúdo original alterado na exportação: {uid}")
        expected = metadata(unit, allocation[unit.stratum], run_id)
        if any(row[k] != v for k, v in expected.items()):
            raise ValidationError(f"Metadados ou pesos inconsistentes: {uid}")
        if pipeline_rows[uid] != pipeline_row(row, prepared):
            raise ValidationError("Conteúdo da exportação para o pipeline divergente")
        if metadata_rows[uid] != metadata_row(row):
            raise ValidationError("Metadados separados divergem do arquivo completo")
    return {"export_ids_match_draw": True, "original_fields_and_text_preserved": True,
            "export_weights_consistent": True, "pipeline_aliases_verified": True,
            "three_exports_same_rows_and_ids": True, "unique_nonempty_sampling_unit_ids": True,
            "pipeline_exact_13_columns": True, "commits_count_normalized": True,
            "metadata_exact_14_columns": True, "metadata_matches_full": True}
