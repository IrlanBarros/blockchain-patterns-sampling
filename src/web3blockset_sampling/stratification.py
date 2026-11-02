"""The approved mapping is data, not a fallback categorizer."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .errors import ValidationError
from .ingestion import read_json, sha256_file

STRATA = (
    "Blockchain Core", "SDKs e bibliotecas", "Wallets e extensões",
    "Ferramentas de desenvolvimento", "Documentação, educação e especificações",
    "Infraestrutura e dados", "Contratos e aplicações on-chain", "Outros", "Community",
)


@dataclass
class Mapping:
    version: str
    categories: dict[str, str]
    sha256: str

    def assign(self, source: str, category: str) -> str:
        if source == "community":
            return "Community"
        if source != "provider":
            raise ValidationError(f"Origem inválida: {source!r}")
        if category not in self.categories:
            raise ValidationError(f"Categoria provider ausente ou desconhecida: {category!r}")
        return self.categories[category]


def load_mapping(path: Path) -> Mapping:
    data = read_json(path)
    if not isinstance(data.get("version"), str) or not data["version"].strip() or not isinstance(data.get("strata"), dict) or set(data["strata"]) != set(STRATA):
        raise ValidationError("Mapeamento deve versionar exatamente os nove estratos previstos")
    categories: dict[str, str] = {}
    for stratum, entries in data["strata"].items():
        if not isinstance(entries, list) or (stratum == "Community" and entries):
            raise ValidationError("Categorias devem ser listas; Community não possui categorias provider")
        for category in entries:
            if not isinstance(category, str) or not category or category in categories:
                raise ValidationError(f"Categoria inválida ou mapeada mais de uma vez: {category!r}")
            categories[category] = stratum
    # The immutable reference is distributed with the package, independent of user edits.
    with Path(__file__).with_name("expected_categories.json").open(encoding="utf-8") as stream:
        expected = set(json.load(stream))
    if set(categories) != expected or len(categories) != 33 or data["strata"]["Outros"] != ["Other"]:
        raise ValidationError("As 33 categorias originais devem estar contempladas; Outros = Other")
    return Mapping(data["version"], categories, sha256_file(path))


def mapping_approved(mapping: Mapping, approval_path: Path | None) -> bool:
    if approval_path is None:
        return False
    approval = read_json(approval_path)
    if not all(isinstance(approval.get(k), str) and approval[k].strip()
               for k in ("approved_by", "approved_at", "mapping_sha256")):
        return False
    from datetime import datetime
    try:
        approved_at = datetime.fromisoformat(approval["approved_at"])
    except ValueError:
        return False
    return bool(approved_at.tzinfo and approval["mapping_sha256"] == mapping.sha256)
