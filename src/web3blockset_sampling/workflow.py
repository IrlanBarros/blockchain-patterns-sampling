"""Run directories are append-only; a completed manifest is the commit marker."""

from __future__ import annotations

import platform
import tempfile
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from . import __version__
from .config import Config, load_config
from .contracts import export_contract
from .errors import ValidationError
from .export import export_samples, pipeline_export_audit
from .ingestion import digest_json, read_json, rows, sha256_file, write_json
from .preparation import prepare, verify_inputs
from .reports import write_reports
from .sampling import ALGORITHM, draw
from .statistics import allocate
from .stratification import STRATA
from .validation import check_design, check_exports, check_preparation


def snapshot(config: Config) -> dict:
    return {k: str(v.resolve()) if isinstance(v, Path) else v for k, v in asdict(config).items()}


def implementation_hash() -> str:
    """Fingerprint installed code and its immutable category reference."""
    package = Path(__file__).parent
    return digest_json({p.name: sha256_file(p) for p in sorted(package.iterdir()) if p.suffix in {".py", ".json"}})


def run(config: Config, definitive: bool = False) -> tuple[Path, dict]:
    code_hash = implementation_hash()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:12]
    directory = config.output / run_id
    directory.mkdir(parents=True, exist_ok=False)
    write_json(directory / "config_snapshot.json", snapshot(config))
    try:
        prepared = prepare(config)
        counts = Counter(u.stratum for u in prepared.eligible)
        allocation = allocate({s: counts[s] for s in STRATA}, config.z, config.p, config.error)
        checks = check_preparation(prepared, allocation)
        if not all(checks.values()):
            prepared.blockers.append(f"Verificações técnicas da preparação falharam: {[k for k, v in checks.items() if not v]}")
    except (ValidationError, OSError) as exc:
        diagnostic = {"run_id": run_id, "status": "blocked", "blockers": [str(exc)]}
        if "prepared" in locals():
            diagnostic["audit"] = prepared.audit
        write_json(directory / "validation_report.json", diagnostic)
        write_json(directory / "sampling_manifest.json", diagnostic)
        return directory, diagnostic
    selected = None
    export_audit = None
    if definitive and not prepared.blockers:
        selected = draw(prepared.eligible, allocation, config.seed)
        try:
            checks = check_design(prepared, allocation, selected)
            export_audit = export_samples(directory, prepared, selected, allocation, run_id)
            checks.update(check_exports(directory, prepared, allocation, selected, run_id))
            verify_inputs(prepared)
        except (ValidationError, OSError) as exc:
            prepared.blockers.append(str(exc))
            selected = None
    checks["implementation_unchanged"] = implementation_hash() == code_hash
    if not checks["implementation_unchanged"]:
        prepared.blockers.append("Implementação modificada durante a execução; repita com o código estável")
        selected = None
    report = write_reports(directory, prepared, allocation, selected, run_id, checks,
                           export_audit if selected is not None else None)
    manifest = {"run_id": run_id, "created_at": datetime.now(timezone.utc).isoformat(),
                "status": "complete" if report["definitive"] else "blocked" if prepared.blockers else "prepared",
                "program_version": __version__, "implementation_sha256": code_hash,
                "python": platform.python_version(), "platform": platform.platform(),
                "corpus_version": config.corpus_version, "inputs": prepared.inputs,
                "config_sha256": sha256_file(directory / "config_snapshot.json"),
                "mapping_version": prepared.mapping.version, "mapping_sha256": prepared.mapping.sha256,
                "export_contract": export_contract(),
                "seed": config.seed, "algorithm": ALGORITHM, "ordering": "lexicographic stable unit IDs",
                "rounding": "ceil; capped at population; empty strata have n=0",
                "duplicate_policy": config.duplicate_policy, "identity_fields": config.identity_fields,
                "pilot_fields": config.pilot_fields, "unit": "row occurrence" if config.duplicate_policy == "preserve_rows" else "logical artifact",
                "statistics": {"confidence": config.confidence, "z": config.z, "p": config.p, "error": config.error},
                "exclusions": {role: prepared.audit.get(role + "_exclusion") for role in ("pilot", "smoke")},
                "eligible_population": len(prepared.eligible), "calculated_sample": sum(a.sample for a in allocation.values()),
                "selected_sample": len(selected) if selected is not None else 0,
                "allocation": {s: a.to_dict() for s, a in allocation.items()}, "blockers": prepared.blockers,
                "artifacts": {p.name: sha256_file(p) for p in sorted(directory.iterdir()) if p.is_file()}}
    if selected is not None:
        manifest["export_audit"] = export_audit
    write_json(directory / "sampling_manifest.json", manifest)
    return directory, manifest


def validate_run(directory: Path) -> dict:
    if (directory / "smoke_15_manifest.json").is_file():
        from .smoke import validate_smoke
        return validate_smoke(directory)
    manifest = read_json(directory / "sampling_manifest.json")
    required = {"status", "program_version", "algorithm", "implementation_sha256", "python", "artifacts",
                "config_sha256", "seed", "corpus_version", "duplicate_policy", "identity_fields", "pilot_fields",
                "statistics", "inputs", "mapping_version", "mapping_sha256", "exclusions", "allocation",
                "eligible_population", "selected_sample", "calculated_sample", "run_id"}
    required.update({"export_contract", "export_audit"})
    if manifest.get("status") != "complete":
        raise ValidationError("Somente uma execução definitiva completa pode ser validada")
    if not required <= set(manifest):
        raise ValidationError(f"Manifesto sem campos obrigatórios: {sorted(required - set(manifest))}")
    if manifest["program_version"] != __version__ or manifest["algorithm"] != ALGORITHM:
        raise ValidationError("Versão do programa/algoritmo difere da execução original")
    if manifest["implementation_sha256"] != implementation_hash():
        raise ValidationError("Código instalado difere da implementação registrada")
    if manifest["export_contract"] != export_contract():
        raise ValidationError("Contrato de exportação do manifesto divergente")
    if manifest["python"].split(".")[:2] != platform.python_version().split(".")[:2]:
        raise ValidationError("Reprodução requer a mesma versão major.minor do Python")
    expected_files = {"config_snapshot.json", "strata_summary.csv", "repository_distribution.csv",
                      "duplicate_groups.csv", "exclusions_audit.csv",
                      "validation_report.json", "sampling_report.md", "final_sample_full.csv", "final_sample_pipeline.csv",
                      "final_sample_metadata.csv"}
    if set(manifest["artifacts"]) != expected_files:
        raise ValidationError("Lista de artefatos do manifesto incompleta ou inesperada")
    for name, expected in manifest["artifacts"].items():
        if sha256_file(directory / name) != expected:
            raise ValidationError(f"Checksum de saída divergente: {name}")
    if sha256_file(directory / "config_snapshot.json") != manifest["config_sha256"]:
        raise ValidationError("Checksum da configuração divergente")
    config = load_config(directory / "config_snapshot.json")
    config_metadata = {"seed": config.seed, "corpus_version": config.corpus_version,
                       "duplicate_policy": config.duplicate_policy, "identity_fields": config.identity_fields,
                       "pilot_fields": config.pilot_fields,
                       "statistics": {"confidence": config.confidence, "z": config.z, "p": config.p, "error": config.error}}
    if any(manifest.get(k) != v for k, v in config_metadata.items()):
        raise ValidationError("Parâmetros do manifesto divergem da configuração registrada")
    prepared = prepare(config)
    if prepared.inputs != manifest["inputs"]:
        raise ValidationError("Entradas atuais divergem das registradas no manifesto")
    if prepared.blockers:
        raise ValidationError(f"Preparação revalidada com bloqueios: {prepared.blockers}")
    if manifest["mapping_version"] != prepared.mapping.version or manifest["mapping_sha256"] != prepared.mapping.sha256:
        raise ValidationError("Mapeamento do manifesto inconsistente")
    if manifest["exclusions"] != {role: prepared.audit.get(role + "_exclusion") for role in ("pilot", "smoke")}:
        raise ValidationError("Exclusões do manifesto inconsistentes")
    counts = Counter(u.stratum for u in prepared.eligible)
    allocation = allocate({s: counts[s] for s in STRATA}, config.z, config.p, config.error)
    if {s: a.to_dict() for s, a in allocation.items()} != manifest["allocation"]:
        raise ValidationError("Alocações do manifesto inconsistentes com as populações e fórmulas")
    if (len(prepared.eligible) != manifest["eligible_population"] or
        sum(a.sample for a in allocation.values()) != manifest["selected_sample"] or
        manifest["calculated_sample"] != manifest["selected_sample"]):
        raise ValidationError("Totais do manifesto inconsistentes")
    selected = draw(prepared.eligible, allocation, config.seed)
    checks = check_design(prepared, allocation, selected)
    checks.update(check_exports(directory, prepared, allocation, selected, manifest["run_id"]))
    export_audit = pipeline_export_audit(rows(directory / "final_sample_full.csv"), prepared)
    if manifest["export_audit"] != export_audit:
        raise ValidationError("Auditoria de normalização da exportação inconsistente")
    checks["implementation_unchanged"] = implementation_hash() == manifest["implementation_sha256"]
    if not checks["implementation_unchanged"]:
        raise ValidationError("Implementação modificada durante a validação")
    with tempfile.TemporaryDirectory(prefix="web3blockset-validate-") as temp:
        temp_dir = Path(temp)
        write_reports(temp_dir, prepared, allocation, selected, manifest["run_id"], checks, export_audit)
        for name in ("strata_summary.csv", "repository_distribution.csv", "duplicate_groups.csv", "exclusions_audit.csv",
                     "validation_report.json", "sampling_report.md"):
            if sha256_file(temp_dir / name) != sha256_file(directory / name):
                raise ValidationError(f"Relatório inconsistente com os dados recalculados: {name}")
    checks["reports_recalculated"] = True
    return {"valid": True, "run_id": manifest["run_id"], "checks": checks}
