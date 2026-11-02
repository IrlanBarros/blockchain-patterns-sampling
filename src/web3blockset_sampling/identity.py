"""Technical normalization for keys; raw fields are never overwritten."""

from __future__ import annotations

import re
from urllib.parse import urlsplit

from .config import Config
from .errors import ValidationError
from .ingestion import digest_json


def normalize(row: dict[str, str], schema: dict[str, str], config: Config, role: str = "issues") -> dict[str, str]:
    values = {key: row[column].strip() for key, column in schema.items()}
    repo = values.get("repository", "")
    owner = values.get("owner", "")
    if config.repository_formats.get(role, "name") == "github_url":
        try:
            url = urlsplit(repo)
        except ValueError as exc:
            raise ValidationError(f"URL GitHub de repositório inválida: {repo!r}") from exc
        if (url.scheme != "https" or url.netloc.casefold() != "github.com" or url.query or url.fragment
                or "%" in url.path):
            raise ValidationError(f"URL GitHub de repositório inválida: {repo!r}")
        repo = url.path.strip("/").removesuffix(".git")
        if not repo:
            raise ValidationError("URL GitHub sem nome de repositório")
    if repo:
        if "/" not in repo:
            if not owner:
                raise ValidationError("Repository curto exige owner explícito; nomes isolados não são chaves")
            repo = f"{owner}/{repo}"
        if len(repo.split("/")) != 2 or any(not part or part in {".", ".."} or re.search(r"\s", part) for part in repo.split("/")):
            raise ValidationError(f"Repository deve ser owner/name: {repo!r}")
        if owner and repo.split("/")[0].casefold() != owner.casefold():
            raise ValidationError(f"Owner conflitante: {repo!r} / {owner!r}")
        values["repository"] = repo.casefold()
    for key in ("number", "record_id", "repository_id"):
        if key in values:
            text = values[key]
            if not re.fullmatch(r"[0-9]+(?:\.0+)?", text) or int(text.split(".")[0]) < 1:
                raise ValidationError(f"{key} deve ser identificador inteiro positivo: {text!r}")
            values[key] = str(int(text.split(".")[0]))
    for key, mapping in (("source", config.source_values), ("artifact_type", config.artifact_values)):
        if key in values:
            original = values[key]
            try:
                values[key] = mapping[original.casefold()]
            except KeyError as exc:
                raise ValidationError(f"Valor desconhecido de {key}: {original!r}") from exc
    return values


def key(values: dict[str, str], fields: list[str]) -> tuple[str, ...]:
    if any(not values.get(field) for field in fields):
        raise ValidationError(f"Chave incompleta; campos exigidos: {fields}")
    return tuple(values[field] for field in fields)


def logical_id(values: dict[str, str], fields: list[str]) -> str:
    return "logical:" + digest_json(list(zip(fields, key(values, fields))))
