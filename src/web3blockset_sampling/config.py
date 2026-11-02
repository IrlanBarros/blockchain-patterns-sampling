"""Explicit schemas and centralized methodological settings (JSON)."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path

from .contracts import DEFAULT_PIPELINE_SOURCES, PIPELINE_COLUMNS
from .errors import ValidationError
from .ingestion import read_json


@dataclass
class Config:
    issues: Path
    repositories: Path
    pilot: Path
    mapping: Path
    output: Path = Path("outputs")
    approval: Path | None = None
    smoke: Path | None = None
    methodology: Path | None = None
    seed: int = 42
    encoding: str = "utf-8-sig"
    delimiter: str = ","
    corpus_version: str = "original-msr2026"
    corpus_decision: str = ""
    expected_counts: dict[str, int] = field(default_factory=lambda: {
        "total": 391596, "provider": 383387, "community": 8209})
    expected_pilot: int = 200
    exclusion_decision: str = ""
    smoke_decision: str = ""
    duplicate_policy: str = "error"
    duplicate_decision: str = ""
    confidence: float = 0.95
    z: float = 1.96
    p: float = 0.5
    error: float = 0.05
    join_fields: list[str] = field(default_factory=lambda: ["repository", "source"])
    repository_scope: str = "all"
    repository_formats: dict[str, str] = field(default_factory=dict)
    identity_fields: list[str] = field(default_factory=lambda: ["repository", "number", "artifact_type"])
    pilot_fields: list[str] = field(default_factory=lambda: ["repository", "number", "artifact_type"])
    schemas: dict[str, dict[str, str]] = field(default_factory=dict)
    pipeline_columns: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_PIPELINE_SOURCES))
    pipeline_key_fields: list[str] = field(default_factory=lambda: ["sampling_unit_id"])
    pipeline_decision: str = ""
    source_values: dict[str, str] = field(default_factory=lambda: {
        "provider": "provider", "community": "community"})
    artifact_values: dict[str, str] = field(default_factory=lambda: {
        "issue": "issue", "pull request": "pull_request", "pull_request": "pull_request", "pr": "pull_request"})

    def validate(self) -> None:
        for name in ("issues", "repositories", "pilot", "mapping", "output"):
            if not isinstance(getattr(self, name), Path):
                raise ValidationError(f"{name} exige um caminho válido")
        if self.methodology is not None and not isinstance(self.methodology, Path):
            raise ValidationError("methodology exige um caminho válido")
        if self.repository_scope not in {"all", "provider"}:
            raise ValidationError("repository_scope deve ser all ou provider")
        if not isinstance(self.repository_formats, dict) or any(
            role not in {"issues", "repositories", "pilot", "smoke"} or fmt not in {"name", "github_url"}
            for role, fmt in self.repository_formats.items()
        ):
            raise ValidationError("repository_formats exige papel → name ou github_url")
        for name in ("corpus_version", "corpus_decision", "exclusion_decision", "smoke_decision", "duplicate_policy",
                     "duplicate_decision", "pipeline_decision", "encoding", "delimiter"):
            if not isinstance(getattr(self, name), str):
                raise ValidationError(f"{name} deve ser string")
        for name in ("expected_counts", "schemas", "pipeline_columns", "source_values", "artifact_values"):
            if not isinstance(getattr(self, name), dict):
                raise ValidationError(f"{name} deve ser objeto JSON")
        for name in ("join_fields", "identity_fields", "pilot_fields", "pipeline_key_fields"):
            if not isinstance(getattr(self, name), list) or any(not isinstance(x, str) for x in getattr(self, name)):
                raise ValidationError(f"{name} deve ser lista de campos")
        valid_fields = {"repository", "owner", "repository_id", "number", "artifact_type", "record_id", "source", "category"}
        for role, schema in self.schemas.items():
            if role not in {"issues", "repositories", "pilot", "smoke"} or not isinstance(schema, dict):
                raise ValidationError(f"Papel de esquema inválido: {role}")
            if not set(schema) <= valid_fields or any(not isinstance(v, str) or not v for v in schema.values()):
                raise ValidationError(f"Campos ou nomes de coluna inválidos no esquema {role}")
        if self.repository_scope == "provider" and "source" not in self.schemas.get("issues", {}):
            raise ValidationError("Metadados somente provider exigem source explícito nos registros")
        for name in ("pipeline_columns", "source_values", "artifact_values"):
            if any(not isinstance(k, str) or not k or not isinstance(v, str) or not v for k, v in getattr(self, name).items()):
                raise ValidationError(f"{name} exige pares de strings não vazias")
        if self.duplicate_policy not in {"error", "preserve_rows"}:
            raise ValidationError("duplicate_policy deve ser error ou preserve_rows; não há deduplicação implícita")
        if self.duplicate_policy == "preserve_rows" and not self.duplicate_decision.strip():
            raise ValidationError("preserve_rows exige duplicate_decision, com a decisão dos pesquisadores")
        if self.corpus_version != "original-msr2026" and not self.corpus_decision.strip():
            raise ValidationError("Versões alternativas exigem corpus_decision e contagens próprias")
        if self.corpus_version == "original-msr2026" and self.expected_counts != {
            "total": 391596, "provider": 383387, "community": 8209
        }:
            raise ValidationError("Não altere as contagens da versão original; declare outra corpus_version")
        if set(self.expected_counts) != {"total", "provider", "community"} or any(
            not isinstance(v, int) or isinstance(v, bool) or v < 0 for v in self.expected_counts.values()
        ) or self.expected_counts["total"] != sum(self.expected_counts[s] for s in ("provider", "community")):
            raise ValidationError("expected_counts exige total = provider + community, inteiros não negativos")
        if self.smoke and not self.smoke_decision.strip():
            raise ValidationError("A exclusão opcional do smoke test exige smoke_decision")
        if self.pipeline_key_fields != ["sampling_unit_id"]:
            raise ValidationError("pipeline_key_fields deve ser [sampling_unit_id]; a chave da ocorrência é exclusiva")
        expected_pipeline = set(PIPELINE_COLUMNS) - {"sampling_unit_id"}
        if set(self.pipeline_columns) != expected_pipeline:
            raise ValidationError("pipeline_columns deve mapear exatamente os 12 campos autorizados; "
                                  "sampling_unit_id é fornecido automaticamente")
        if not isinstance(self.seed, int) or isinstance(self.seed, bool):
            raise ValidationError("seed deve ser um inteiro")
        if not isinstance(self.expected_pilot, int) or isinstance(self.expected_pilot, bool) or self.expected_pilot < 0:
            raise ValidationError("expected_pilot deve ser inteiro não negativo")
        if self.expected_pilot != 200 and not self.exclusion_decision.strip():
            raise ValidationError("Alterar os 200 casos exige exclusion_decision")
        if len(self.delimiter) != 1:
            raise ValidationError("delimiter deve possuir um caractere")
        if not all(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)
                   for x in (self.confidence, self.z, self.p, self.error)):
            raise ValidationError("Parâmetros estatísticos devem ser finitos")
        if not (0 < self.confidence < 1 and self.z > 0 and 0 < self.p < 1 and 0 < self.error < 1):
            raise ValidationError("Parâmetros estatísticos fora dos limites")
        # The published 1.96 is a rounded critical value; allow that precision only.
        from statistics import NormalDist
        if abs(NormalDist().inv_cdf((1 + self.confidence) / 2) - self.z) > 0.005:
            raise ValidationError("z inconsistente com confidence")
        for name, fields in [("join_fields", self.join_fields), ("identity_fields", self.identity_fields),
                             ("pilot_fields", self.pilot_fields)]:
            if not fields or len(fields) != len(set(fields)):
                raise ValidationError(f"{name} vazio ou duplicado")
        if not set(self.identity_fields) <= {"repository", "number", "artifact_type", "record_id"}:
            raise ValidationError("identity_fields aceita apenas atributos intrínsecos; source não define outra identidade do artefato")
        if not {"repository", "number", "artifact_type"} <= set(self.identity_fields):
            raise ValidationError("Identidade deve incluir repository, number e artifact_type")
        if not set(self.pilot_fields) <= set(self.identity_fields) or not {"repository", "number"} <= set(self.pilot_fields):
            raise ValidationError("pilot_fields exige repository + number e deve ser subconjunto de identity_fields")
        if not set(self.join_fields) <= {"repository", "repository_id", "source"} or not (
            {"repository", "repository_id"} & set(self.join_fields)
        ):
            raise ValidationError("join_fields exige repository ou repository_id")
        if set(self.source_values.values()) != {"provider", "community"}:
            raise ValidationError("source_values deve distinguir provider e community")
        if not set(self.artifact_values.values()) <= {"issue", "pull_request"}:
            raise ValidationError("artifact_values inválido")


def load_config(path: Path, overrides: dict | None = None) -> Config:
    data = read_json(path)
    data.update({k: v for k, v in (overrides or {}).items() if v is not None})
    for key in ("issues", "repositories", "pilot", "mapping", "output", "approval", "smoke", "methodology"):
        if data.get(key) is not None:
            if not isinstance(data[key], (str, Path)):
                raise ValidationError(f"{key} deve ser um caminho")
            p = Path(data[key])
            data[key] = p if p.is_absolute() else (path.resolve().parent / p).resolve()
    try:
        config = Config(**data)
    except TypeError as exc:
        raise ValidationError(f"Configuração inválida: {exc}") from exc
    config.validate()
    return config
