"""Strict streaming CSV I/O. Values remain strings, including empty text cells."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator

from .errors import ValidationError

csv.field_size_limit(2**31 - 1)


def read_json(path: Path) -> dict:
    """Reject duplicate JSON object keys instead of silently keeping the last."""
    def unique(pairs):
        result = {}
        for k, value in pairs:
            if k in result:
                raise ValidationError(f"Chave JSON repetida em {path}: {k}")
            result[k] = value
        return result
    with path.open(encoding="utf-8") as stream:
        try:
            value = json.load(stream, object_pairs_hook=unique)
        except json.JSONDecodeError as exc:
            raise ValidationError(f"JSON inválido em {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValidationError(f"Objeto JSON esperado em {path}")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def digest_json(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def header(path: Path, encoding: str = "utf-8-sig", delimiter: str = ",") -> list[str]:
    with path.open(encoding=encoding, newline="") as stream:
        try:
            fields = next(csv.reader(stream, delimiter=delimiter, strict=True))
        except StopIteration as exc:
            raise ValidationError(f"CSV vazio: {path}") from exc
        except csv.Error as exc:
            raise ValidationError(f"Cabeçalho CSV inválido em {path}: {exc}") from exc
    if not fields or any(not x for x in fields) or len(fields) != len(set(fields)):
        raise ValidationError(f"Cabeçalho vazio ou com nomes duplicados: {path}")
    return fields


def rows(path: Path, encoding: str = "utf-8-sig", delimiter: str = ",") -> Iterator[dict[str, str]]:
    fields = header(path, encoding, delimiter)
    try:
        with path.open(encoding=encoding, newline="") as stream:
            reader = csv.DictReader(stream, delimiter=delimiter, strict=True)
            for position, row in enumerate(reader, start=2):
                if None in row or any(value is None for value in row.values()):
                    raise ValidationError(f"Largura de linha inválida em {path}, registro {position}")
                yield {field: row[field] for field in fields}
    except csv.Error as exc:
        raise ValidationError(f"CSV inválido em {path}: {exc}") from exc


def write_csv(path: Path, fields: list[str], records: Iterable[dict]) -> None:
    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="raise")
        writer.writeheader()
        writer.writerows(records)


def write_json(path: Path, value: object) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def inspect_csv(path: Path, encoding: str = "utf-8-sig", delimiter: str = ",") -> dict:
    """Profile the whole file without retaining text or guessing a schema."""
    fields = header(path, encoding, delimiter)
    empty: Counter = Counter()
    numeric: Counter = Counter()
    max_lengths: Counter = Counter()
    examples: dict[str, set[str]] = {field: set() for field in fields}
    token_fields = set(fields) & {"data_source", "source", "type", "repository_category", "category", "state"}
    distributions = {k: Counter() for k in token_fields}
    candidates = [list(parts) for parts in (("issue_id",), ("repository_id",), ("repository_full_name",),
                  ("owner", "repository"), ("owner", "repository", "issue_number", "type"),
                  ("repository_full_name", "issue_number", "type")) if set(parts) <= set(fields)]
    candidate_counts = [Counter() for _ in candidates]
    date_profiles = {k: {"nonempty": 0, "invalid_iso8601": 0, "without_timezone": 0,
                         "minimum_utc": None, "maximum_utc": None, "years": Counter()}
                     for k in fields if k in {"created_at", "updated_at", "closed_at"}}
    count = 0
    for row in rows(path, encoding, delimiter):
        count += 1
        for field_name in token_fields:
            distributions[field_name][row[field_name]] += 1
        for keys, counter in zip(candidates, candidate_counts):
            counter[tuple(row[k] for k in keys)] += 1
        for field_name, profile in date_profiles.items():
            value = row[field_name].strip()
            if value:
                profile["nonempty"] += 1
                try:
                    date = datetime.fromisoformat(value)
                except ValueError:
                    profile["invalid_iso8601"] += 1
                    continue
                profile["years"][str(date.year)] += 1
                if date.tzinfo is None:
                    profile["without_timezone"] += 1
                else:
                    stamp = date.astimezone(timezone.utc).isoformat()
                    profile["minimum_utc"] = min(profile["minimum_utc"] or stamp, stamp)
                    profile["maximum_utc"] = max(profile["maximum_utc"] or stamp, stamp)
        for key, value in row.items():
            empty[key] += not value.strip()
            numeric[key] += bool(value) and value.isdecimal()
            max_lengths[key] = max(max_lengths[key], len(value))
            # Small token examples only; never serialize prose or author identities.
            if len(value) <= 80 and len(examples[key]) < 5 and key in {
                "data_source", "type", "repository_category", "source", "category", "state"
            }:
                examples[key].add(value)
    return {"path": str(path.resolve()), "sha256": sha256_file(path), "rows": count,
            "token_distributions": {k: dict(v) for k, v in distributions.items()},
            "date_profiles": date_profiles,
            "candidate_keys_raw_values": [{"fields": keys, "distinct": len(counter),
                                           "extra_rows": sum(n - 1 for n in counter.values()),
                                           "duplicate_groups": sum(n > 1 for n in counter.values())}
                                          for keys, counter in zip(candidates, candidate_counts)],
            "columns": [{"name": k, "storage_type": "string", "empty": empty[k],
                         "integer_like": numeric[k], "max_characters": max_lengths[k],
                         "token_examples": sorted(examples[k])} for k in fields]}
