"""Isolated integration smoke workflow using the existing population and exports."""

from __future__ import annotations

import platform
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from . import __version__
from .config import Config, load_config
from .contracts import METADATA_COLUMNS, PIPELINE_COLUMNS, export_contract
from .errors import ValidationError
from .export import metadata_row, pipeline_export_audit, pipeline_row, recover_rows
from .ingestion import digest_json, header, read_json, sha256_file, write_csv, write_json
from .preparation import Prepared, prepare, verify_inputs
from .reports import render_export_audit
from .smoke_selection import (
    ALGORITHM, LEXICAL_TARGET, LEXICAL_TERMS, LONG_TEXT_MIN, PREFERRED_TEXT_MAX, SIZE,
    profile_candidates, select, selection_details,
)
from .statistics import allocate
from .stratification import STRATA, mapping_approved
from .validation import _read_export, check_preparation
from .workflow import implementation_hash, snapshot

MANIFEST = "smoke_15_manifest.json"
REPORT = "smoke_15_selection_report.md"
VALIDATION = "smoke_15_validation.json"
FULL, PIPELINE, METADATA = (f"smoke_15_{part}.csv" for part in ("full", "pipeline", "metadata"))
ARTIFACTS = {FULL, PIPELINE, METADATA, REPORT, VALIDATION, "config_snapshot.json"}
NOT_APPLICABLE = ["sampling_sample_size", "sampling_design_weight", "sampling_provider_weight",
                  "sampling_inclusion_probability"]
WARNING = ("Este conjunto de 15 registros foi selecionado para validação técnica de integração e cobertura de cenários. "
           "Não constitui uma amostra probabilística representativa do corpus e não deve ser utilizado para inferências populacionais.")
AUTHORIZATION = {"explicit": True, "scope": "integration_smoke_only", "human_approval_recorded": False,
                 "definitive_sampling_authorized": False}


def pending_methodology(prepared: Prepared) -> list[str]:
    """Allow only the two known methodological blockers, retaining them verbatim."""
    allowed = set()
    extra = prepared.audit["duplicates"]["logical_extra_rows"]
    if extra and prepared.config.duplicate_policy == "error":
        allowed.add(f"{extra} linhas com identidade lógica repetida; defina a unidade amostral explicitamente")
    if not mapping_approved(prepared.mapping, prepared.config.approval):
        allowed.add("Agrupamento não aprovado ou aprovação não corresponde ao SHA-256 do mapeamento")
    technical = [b for b in prepared.blockers if b not in allowed]
    if technical:
        raise ValidationError(f"Bloqueios técnicos não autorizados no smoke test: {technical}")
    return list(prepared.blockers)


def evaluate(config: Config, seed: int, size: int) -> tuple[Prepared, list, dict]:
    if size != SIZE:
        raise ValidationError("Esta modalidade suporta exatamente --size 15")
    if not isinstance(seed, int) or isinstance(seed, bool):
        raise ValidationError("seed deve ser um inteiro")
    if config.smoke is not None:
        raise ValidationError("Smoke técnico exige somente exclusão do piloto; config.smoke contém uma exclusão adicional")
    prepared = prepare(config)
    pending = pending_methodology(prepared)
    counts = Counter(u.stratum for u in prepared.eligible)
    allocation = allocate({s: counts[s] for s in STRATA}, config.z, config.p, config.error)
    checks = check_preparation(prepared, allocation)
    if not all(checks.values()):
        raise ValidationError(f"Preparação técnica inválida: {[k for k, v in checks.items() if not v]}")
    candidates, available = profile_candidates(prepared, seed)
    chosen = select(candidates, size)
    # A second independent call also verifies that container iteration order is irrelevant.
    replay = select(list(reversed(candidates)), size)
    if [c.unit.unit_id for c in replay] != [c.unit.unit_id for c in chosen]:
        raise ValidationError("Seleção de cobertura não reproduzível")
    ids = [c.unit.unit_id for c in chosen]
    eligible = {u.unit_id for u in prepared.eligible}
    pilot_keys = {tuple(k) for k in prepared.audit["pilot_exclusion"]["keys"]}
    selection_checks = {
        "exactly_15": len(ids) == SIZE, "unique_nonempty_ids": len(set(ids)) == SIZE and all(ids),
        "all_eligible": set(ids) <= eligible, "none_excluded": not set(ids) & prepared.excluded,
        "no_pilot_keys": all(c.unit.pilot_key not in pilot_keys for c in chosen),
        "nine_strata": {c.unit.stratum for c in chosen} == set(STRATA),
        "issues_and_prs": {c.unit.artifact_type for c in chosen} == {"issue", "pull_request"},
        "deterministic_order": ids == sorted(ids), "selection_replayed": ids == [c.unit.unit_id for c in replay],
    }
    details = selection_details(chosen, available)
    selection_checks["real_provider_community_pair"] = bool(details["repeated_identity_pairs"])
    checks.update(selection_checks)
    if not all(checks.values()):
        raise ValidationError(f"Seleção inválida: {[k for k, v in checks.items() if not v]}")
    return prepared, chosen, {
        "run_type": "integration_smoke", "requested_size": size, "selected_size": len(chosen), "seed": seed,
        "algorithm": ALGORITHM, "selection_nature": "intentional_technical_coverage",
        "population_inference_allowed": False, "methodological_warning": WARNING,
        "authorization": dict(AUTHORIZATION), "pending_methodological_decisions": pending,
        "effective_config": snapshot(config), "inputs": prepared.inputs,
        "mapping_sha256": prepared.mapping.sha256, "mapping_version": prepared.mapping.version,
        "export_contract": export_contract(), "eligible_population": len(eligible),
        "preparation_audit": prepared.audit,
        "definitive_plan": {"calculated_size": sum(a.sample for a in allocation.values()),
                            "allocation": {s: a.to_dict() for s, a in allocation.items()},
                            "draw_executed": False, "methodological_approval_granted": False},
        "selection_parameters": {"long_text_min_characters": LONG_TEXT_MIN,
                                 "preferred_text_max_characters": PREFERRED_TEXT_MAX,
                                 "lexical_target": LEXICAL_TARGET, "lexical_terms": list(LEXICAL_TERMS),
                                 "tie_break": "sha256([algorithm, seed, sampling_unit_id])",
                                 "order": "lexicographic sampling_unit_id",
                                 "priority": "real pair; mandatory coverage gain; optional coverage gain; lexical target; text cost; seeded tie"},
        "statistical_fields_not_applicable": NOT_APPLICABLE,
        "statistical_absence_representation": "empty CSV cell",
        "population_fields_meaning": "eligible stratum population and its descriptive proportion of the eligible corpus",
        "selection": details, "checks": checks,
    }


def smoke_metadata(unit, populations: Counter, total: int, run_id: str) -> dict:
    result = dict.fromkeys(METADATA_COLUMNS, "")
    result.update(sampling_unit_id=unit.unit_id, sampling_logical_id=unit.logical_id,
                  sampling_repository=unit.repository, sampling_source=unit.source, sampling_category=unit.category,
                  sampling_original_category=unit.original_category, sampling_stratum=unit.stratum,
                  sampling_population=str(populations[unit.stratum]),
                  sampling_population_weight=str(populations[unit.stratum] / total), sampling_run_id=run_id)
    return result


def records_for(prepared: Prepared, chosen: list, run_id: str) -> list[dict]:
    recovered = recover_rows(prepared, {c.unit.unit_id for c in chosen})
    counts = Counter(u.stratum for u in prepared.eligible)
    total = sum(counts.values())
    return [{**recovered[c.unit.unit_id], **smoke_metadata(c.unit, counts, total, run_id)} for c in chosen]


def export_smoke(directory: Path, prepared: Prepared, records: list[dict]) -> dict:
    fields = header(prepared.config.issues, prepared.config.encoding, prepared.config.delimiter)
    write_csv(directory / FULL, fields + METADATA_COLUMNS, records)
    write_csv(directory / PIPELINE, PIPELINE_COLUMNS, (pipeline_row(row, prepared) for row in records))
    write_csv(directory / METADATA, METADATA_COLUMNS, (metadata_row(row) for row in records))
    return pipeline_export_audit(records, prepared)


def check_smoke_exports(directory: Path, prepared: Prepared, chosen: list, expected: list[dict]) -> dict:
    fields = header(prepared.config.issues, prepared.config.encoding, prepared.config.delimiter)
    full = _read_export(directory / FULL, fields + METADATA_COLUMNS)
    pipeline = _read_export(directory / PIPELINE, PIPELINE_COLUMNS)
    metadata = _read_export(directory / METADATA, METADATA_COLUMNS)
    ids = [c.unit.unit_id for c in chosen]
    if any(list(data) != ids or len(data) != SIZE for data in (full, pipeline, metadata)):
        raise ValidationError("Três CSVs devem preservar exatamente as 15 ocorrências na ordem da seleção")
    for candidate, record in zip(chosen, expected):
        uid = candidate.unit.unit_id
        if digest_json({k: full[uid][k] for k in fields}) != candidate.unit.row_hash:
            raise ValidationError(f"Células originais alteradas: {uid}")
        if full[uid] != record or metadata[uid] != metadata_row(record):
            raise ValidationError(f"Conteúdo ou metadados inconsistentes: {uid}")
        if pipeline[uid] != pipeline_row(record, prepared):
            raise ValidationError(f"Pipeline alterado (textos, commits_count, datas ou vazios): {uid}")
        if any(full[uid][k] for k in NOT_APPLICABLE):
            raise ValidationError("Pesos/probabilidades/tamanho amostral inaplicáveis devem permanecer vazios")
    return {"three_exports_same_order_and_ids": True, "pipeline_exact_13_columns": True,
            "metadata_exact_14_columns": True, "all_original_cells_preserved": True,
            "full_commits_count_preserved": True, "commits_count_normalized": True,
            "texts_dates_and_empty_cells_preserved": True,
            "occurrence_metadata_verified": True, "inapplicable_statistics_empty": True}


def render_report(run_id: str, evidence: dict) -> str:
    details = evidence["selection"]
    lines = ["# Smoke test técnico de integração", "", WARNING, "", f"Execução: `{run_id}`. Tipo: `integration_smoke`.",
             f"Seleção intencional: 15 ocorrências. Semente: {evidence['seed']}. Algoritmo: `{ALGORITHM}`.", "",
             "## Estratégia", "",
             "Reserva um par real provider/community identificado pela preparação; prioriza ganho de cobertura obrigatória, "
             "ganho de cenários opcionais e até três registros com indícios lexicais. Desempata pelo custo textual acima de "
             f"{PREFERRED_TEXT_MAX} caracteres e pelo hash da semente/ID. Texto extenso: pelo menos {LONG_TEXT_MIN} caracteres. "
             "A ordem de exportação é lexicográfica por sampling_unit_id. Nenhum texto é truncado.", "",
             "## Distribuições", ""]
    for title, name in (("Estrato", "strata"), ("Tipo normalizado da coluna de origem", "artifact_types"), ("Origem", "sources")):
        lines += [f"| {title} | Quantidade |", "|---|---:|"]
        lines += [f"| {key} | {value} |" for key, value in sorted(details[name].items())]
        lines += [""]
    lines += ["## Por que cada ocorrência foi selecionada", "",
              "| sampling_unit_id | Estrato | Tipo | Origem | Critérios atendidos |",
              "|---|---|---|---|---|"]
    for record in details["records"]:
        criteria = ", ".join(record["criteria"])
        if record["lexical_terms"]:
            criteria += "; indícios: " + ", ".join(record["lexical_terms"])
        criteria += "; caracteres título/corpo/comentários: " + "/".join(str(v) for v in record["text_lengths"].values())
        lines.append(f"| {record['sampling_unit_id']} | {record['stratum']} | {record['artifact_type']} | {record['source']} | {criteria} |")
    lines += ["", "## Matriz de cobertura", "", "| Cenário | Selecionados | Disponíveis | Situação |", "|---|---:|---:|---|"]
    for name, values in details["coverage"].items():
        lines.append(f"| {name} | {values['selected']} | {values['available']} | {'atendido' if values['covered'] else values['limitation']} |")
    lines += ["| Nove estratos | 9 | 9 | atendido |", "| Issues e PRs | 2 tipos | 2 tipos | atendido |",
              f"| Pares reais de identidade lógica repetida | {len(details['repeated_identity_pairs'])} | ver auditoria de duplicidades | atendido |",
              "", "## Par de identidade lógica repetida", ""]
    for pair in details["repeated_identity_pairs"]:
        lines += [f"- `{pair['sampling_logical_id']}`: " + ", ".join(f"`{uid}`" for uid in pair["sampling_unit_ids"])]
    lines += ["", "## Limitações e pendências", "",
              "Indícios lexicais apenas priorizam entradas. Nenhum registro foi classificado como relevante neste projeto. "
              "Somente o classificador independente poderá validar Stage 1, encaminhamento e avaliação no Stage 2, checkpoints, "
              "retomadas e resultados. O fluxo possui somente Stage 1 e Stage 2.", "",
              "A heurística maximiza cobertura de forma gulosa; não afirma ótimo global dos critérios opcionais. "
              "A seleção e as duas chamadas de desempate são determinísticas; validate reconstrói a preparação e compara cada célula.", ""]
    limitations = [f"- {name}: {values['limitation']}." for name, values in details["coverage"].items() if not values["covered"]]
    lines += limitations or ["Todos os cenários opcionais listados foram contemplados."]
    lines += ["", "Pendências metodológicas mantidas (a autorização técnica não concede aprovação):"]
    lines += ["- " + p for p in evidence["pending_methodological_decisions"]] or ["- Nenhuma pendência de preparação identificada."]
    lines += ["", "## Estatística e isolamento", "",
              "Células vazias representam ausência/inaplicabilidade de: " + ", ".join(f"`{k}`" for k in NOT_APPLICABLE) + ". "
              "Não existem probabilidades de inclusão ou pesos de expansão para esta seleção intencional. "
              "sampling_population e sampling_population_weight são informações descritivas da população elegível, sem inferência.", "",
              f"Planejamento definitivo preservado: {evidence['definitive_plan']['calculated_size']} registros calculados. "
              "Nenhum sorteio definitivo foi executado; as ocorrências continuam elegíveis para uma seleção futura. "
              "Entradas, configuração definitiva e aprovações não são alteradas.", "", "## Integridade e uso", "",
              f"Enviar somente `{PIPELINE}` ao classificador. Os três CSVs possuem as mesmas 15 chaves. O completo preserva "
              "todas as células originais; o pipeline normaliza somente commits_count. "
              "O manifesto registra hashes SHA-256 de todas as entradas e saídas (exceto o próprio manifesto), configuração, "
              "hash da implementação, cobertura e validações. Validar com:", "", "```bash",
              f"python -m web3blockset_sampling validate --run-dir outputs/smoke_tests/{run_id}", "```", ""]
    lines += render_export_audit(evidence["export_audit"])
    return "\n".join(lines) + "\n"


def run_smoke(config: Config, *, seed: int = 20261102, size: int = SIZE,
              run_id: str | None = None, authorized: bool = False) -> tuple[Path, dict]:
    if not authorized:
        raise ValidationError("Informe --authorize-technical-smoke: autorização explícita limitada à extração técnica, sem aprovação metodológica")
    if run_id is None:
        run_id = datetime.now(timezone.utc).strftime("smoke_15_%Y%m%dT%H%M%SZ_") + uuid4().hex[:12]
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}", run_id):
        raise ValidationError("run-id deve ter 1–96 caracteres alfanuméricos, ponto, hífen ou sublinhado, sem caminhos")
    directory = config.output / "smoke_tests" / run_id
    directory.mkdir(parents=True, exist_ok=False)
    code_hash = implementation_hash()
    base = {"run_id": run_id, "created_at": datetime.now(timezone.utc).isoformat(),
            "program_version": __version__, "implementation_sha256": code_hash,
            "python": platform.python_version(), "run_type": "integration_smoke"}
    try:
        write_json(directory / "config_snapshot.json", snapshot(config))
        prepared, chosen, evidence = evaluate(config, seed, size)
        records = records_for(prepared, chosen, run_id)
        evidence["export_audit"] = export_smoke(directory, prepared, records)
        evidence["checks"].update(check_smoke_exports(directory, prepared, chosen, records))
        verify_inputs(prepared)
        if implementation_hash() != code_hash:
            raise ValidationError("Implementação modificada durante a execução; repita com o código estável")
        evidence["checks"]["implementation_unchanged"] = True
        write_json(directory / VALIDATION, {"valid": True, "checks": evidence["checks"],
                                            "export_audit": evidence["export_audit"]})
        with (directory / REPORT).open("x", encoding="utf-8") as stream:
            stream.write(render_report(run_id, evidence))
        manifest = {**base, **evidence, "status": "complete", "blockers": [],
                    "artifacts": {name: sha256_file(directory / name) for name in sorted(ARTIFACTS)}}
    except (ValidationError, OSError) as exc:
        manifest = {**base, "status": "blocked", "blockers": [str(exc)], "requested_size": size,
                    "seed": seed, "authorization": dict(AUTHORIZATION), "selected_size": 0}
    write_json(directory / MANIFEST, manifest)
    return directory, manifest


def validate_smoke(directory: Path) -> dict:
    manifest = read_json(directory / MANIFEST)
    if manifest.get("status") != "complete" or manifest.get("run_type") != "integration_smoke":
        raise ValidationError("Somente um integration_smoke completo pode ser validado")
    if manifest.get("program_version") != __version__ or manifest.get("implementation_sha256") != implementation_hash():
        raise ValidationError("Implementação difere da registrada no smoke test")
    if manifest.get("python", "").split(".")[:2] != platform.python_version().split(".")[:2]:
        raise ValidationError("Reprodução requer a mesma versão major.minor do Python")
    if set(manifest.get("artifacts", {})) != ARTIFACTS:
        raise ValidationError("Lista de artefatos do smoke test incompleta ou inesperada")
    for name in sorted(ARTIFACTS):
        if sha256_file(directory / name) != manifest["artifacts"][name]:
            raise ValidationError(f"Checksum de saída divergente: {name}")
    config = load_config(directory / "config_snapshot.json")
    if snapshot(config) != manifest.get("effective_config"):
        raise ValidationError("Configuração efetiva diverge do snapshot")
    for role, item in manifest.get("inputs", {}).items():
        if sha256_file(Path(item["path"])) != item["sha256"]:
            raise ValidationError(f"Entrada atual difere da registrada: {role}")
    prepared, chosen, expected = evaluate(config, manifest.get("seed"), manifest.get("requested_size"))
    records = records_for(prepared, chosen, manifest["run_id"])
    expected["export_audit"] = pipeline_export_audit(records, prepared)
    expected["checks"].update(check_smoke_exports(directory, prepared, chosen, records))
    verify_inputs(prepared)
    if implementation_hash() != manifest["implementation_sha256"]:
        raise ValidationError("Implementação modificada durante a validação")
    expected["checks"]["implementation_unchanged"] = True
    for key, value in expected.items():
        if manifest.get(key) != value:
            raise ValidationError(f"Manifesto inconsistente com reprodução: {key}")
    if manifest.get("blockers") != []:
        raise ValidationError("Manifesto completo não pode conter bloqueios")
    if read_json(directory / VALIDATION) != {"valid": True, "checks": expected["checks"],
                                            "export_audit": expected["export_audit"]}:
        raise ValidationError("Relatório de validação inconsistente")
    if (directory / REPORT).read_text(encoding="utf-8") != render_report(manifest["run_id"], expected):
        raise ValidationError("Relatório de seleção inconsistente com reprodução")
    return {"valid": True, "run_id": manifest["run_id"], "run_type": "integration_smoke",
            "checks": {**expected["checks"], "manifest_and_reports_recalculated": True, "artifact_hashes_verified": True}}
