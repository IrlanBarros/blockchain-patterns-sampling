"""Build a compact population, audit the many-to-one join and preserve all rows."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field

from .config import Config
from .errors import ValidationError
from .identity import key, logical_id, normalize
from .ingestion import digest_json, header, rows, sha256_file
from .stratification import Mapping, STRATA, load_mapping, mapping_approved


@dataclass(slots=True)
class Unit:
    unit_id: str
    logical_id: str
    pilot_key: tuple[str, ...]
    repository: str
    source: str
    category: str
    stratum: str
    artifact_type: str
    row_hash: str
    record_id: str
    row_occurrence: int
    original_category: str


@dataclass
class Prepared:
    config: Config
    mapping: Mapping
    units: list[Unit]
    excluded: set[str]
    audit: dict
    inputs: dict[str, dict]
    blockers: list[str] = field(default_factory=list)

    @property
    def eligible(self) -> list[Unit]:
        return [u for u in self.units if u.unit_id not in self.excluded]


def check_schema(config: Config, role: str, path, required: set[str]) -> dict[str, str]:
    schema = config.schemas.get(role, {})
    if not required <= set(schema):
        raise ValidationError(f"Mapeamento de {role} sem campos: {sorted(required - set(schema))}")
    columns = set(header(path, config.encoding, config.delimiter))
    missing = set(schema.values()) - columns
    if missing:
        raise ValidationError(f"Colunas configuradas ausentes em {role}: {sorted(missing)}")
    return schema


def repository_index(config: Config, mapping: Mapping | None = None) -> tuple[dict, dict]:
    mapping = mapping or load_mapping(config.mapping)
    required = {"repository", "source", "category"} | set(config.join_fields)
    if config.repository_scope == "provider":
        required.discard("source")
    schema = check_schema(config, "repositories", config.repositories,
                          required)
    index = {}
    sources: dict[str, set[str]] = defaultdict(set)
    categories = Counter()
    for row in rows(config.repositories, config.encoding, config.delimiter):
        values = normalize(row, schema, config, role="repositories")
        if config.repository_scope == "provider":
            if values.get("source", "provider") != "provider":
                raise ValidationError("Metadados declarados provider contêm outra origem")
            values["source"] = "provider"
        values["original_category"] = row[schema["category"]]
        mapping.assign(values["source"], values["category"])
        join_key = key(values, config.join_fields)
        if join_key in index:
            raise ValidationError(f"Chave ambígua em repositories (mesmo se linhas idênticas): {join_key}")
        index[join_key] = values
        sources[values["source"]].add(values["repository"])
        categories[values.get("category", "")] += 1
    return index, {"metadata_rows": len(index), "unique_join_keys": len(index),
                   "cardinality": "many-to-one", "key_fields": config.join_fields,
                   "metadata_scope": config.repository_scope,
                   "repository_format": config.repository_formats.get("repositories", "name"),
                   "organizations": len({v["repository"].split("/")[0] for v in index.values()}),
                   "repositories_by_source": {s: len(v) for s, v in sources.items()},
                   "metadata_repositories_by_stratum": dict(Counter(
                       mapping.assign(v["source"], v["category"]) for v in index.values())),
                   "categories": dict(categories)}


def resolve(row: dict[str, str], schema: dict[str, str], index: dict, config: Config,
            mapping: Mapping) -> dict[str, str]:
    values = normalize(row, schema, config)
    if config.repository_scope == "provider" and values["source"] == "community":
        # Provider metadata must never reclassify or filter a community occurrence.
        values["original_category"] = row[schema["category"]] if "category" in schema else ""
        values["category"] = ""
        values["stratum"] = mapping.assign("community", "")
        return values
    join_key = key(values, config.join_fields)
    if join_key not in index:
        raise ValidationError(f"Repositório sem correspondência: {join_key}")
    repo = index[join_key]
    if values["repository"] != repo["repository"]:
        raise ValidationError(f"Repository divergente apesar da chave de junção: {join_key}")
    if "source" in values and values["source"] != repo["source"]:
        raise ValidationError(f"Origem do registro conflita com repositories: {join_key}")
    values["source"] = repo["source"]
    category = repo.get("category", "")
    if values["source"] == "provider" and values.get("category") and values["category"] != category:
        raise ValidationError(f"Categoria do registro conflita com repositories: {join_key}")
    values["category"] = category
    values["original_category"] = repo["original_category"]
    values["stratum"] = mapping.assign(values["source"], category)
    return values


def prepare(config: Config) -> Prepared:
    config.validate()
    mapping = load_mapping(config.mapping)
    paths = {"issues": config.issues, "repositories": config.repositories, "pilot": config.pilot,
             "mapping": config.mapping}
    if config.smoke:
        paths["smoke"] = config.smoke
    if config.approval:
        paths["approval"] = config.approval
    if config.methodology:
        paths["methodology"] = config.methodology
    inputs = {role: {"path": str(path.resolve()), "sha256": sha256_file(path)} for role, path in paths.items()}
    schema = check_schema(config, "issues", config.issues,
                          {"repository", "number", "artifact_type"} | set(config.join_fields))
    index, join_audit = repository_index(config, mapping)
    units = []
    problems: Counter = Counter()
    problem_examples = []
    logical_counts: Counter = Counter()
    row_counts: Counter = Counter()
    record_ids: dict[str, set[str]] = defaultdict(set)
    type_sets: dict[tuple, set] = defaultdict(set)
    sources: Counter = Counter()
    categories: Counter = Counter()
    before: Counter = Counter({s: 0 for s in STRATA})
    seen_repositories: dict[str, set[str]] = defaultdict(set)
    total = 0
    for total, row in enumerate(rows(config.issues, config.encoding, config.delimiter), start=1):
        try:
            values = resolve(row, schema, index, config, mapping)
            lid = logical_id(values, config.identity_fields)
            pilot_key = key(values, config.pilot_fields)
        except ValidationError as exc:
            problems[str(exc).split(":", 1)[0]] += 1
            if len(problem_examples) < 30:
                problem_examples.append({"record": total, "error": str(exc)})
            continue
        row_hash = digest_json(row)
        row_counts[row_hash] += 1
        logical_counts[lid] += 1
        uid = (f"row:{row_hash}:{row_counts[row_hash]}" if config.duplicate_policy == "preserve_rows"
               else f"{lid}:{logical_counts[lid]}")
        units.append(Unit(uid, lid, pilot_key, values["repository"], values["source"],
                          values["category"], values["stratum"], values["artifact_type"], row_hash,
                          values.get("record_id", ""), row_counts[row_hash], values["original_category"]))
        if values.get("record_id"):
            record_ids[values["record_id"]].add(lid)
        type_sets[(values["repository"], values["number"])].add(values["artifact_type"])
        sources[values["source"]] += 1
        categories[values["category"]] += 1
        before[values["stratum"]] += 1
        seen_repositories[values["source"]].add(values["repository"])
    duplicate_logical = sum(v - 1 for v in logical_counts.values())
    audit = {"input_rows": total, "resolved_rows": len(units), "invalid_rows": total - len(units),
             "invalid_reasons": dict(problems), "invalid_examples": problem_examples,
             "join": {**join_audit,
                      "matched_rows": sources["provider"] if config.repository_scope == "provider" else len(units),
                      "resolved_rows": len(units), "unresolved_rows": total - len(units),
                      "community_rows_without_provider_join": sources["community"] if config.repository_scope == "provider" else 0,
                      "matched_provider_rows": sources["provider"],
                      "missing_repository_rows": problems["Repositório sem correspondência"],
                      "source_conflicts": problems["Origem do registro conflita com repositories"],
                      "metadata_repositories_without_records": sorted(
                          v["repository"] for v in index.values()
                          if v["repository"] not in seen_repositories[v["source"]]),
                      "row_multiplication": 0},
             "invalid_identifiers": sum(n for reason, n in problems.items() if any(
                 term in reason for term in ("Chave incompleta", "identificador inteiro", "Owner conflitante", "Repository deve", "Repository curto"))),
             "unstratified_records": problems["Categoria provider ausente ou desconhecida"],
             "duplicates": {"exact_extra_rows": sum(v - 1 for v in row_counts.values()),
                            "scope": "resolved valid rows; invalid rows are separately reported and block final sampling",
                            "logical_extra_rows": duplicate_logical,
                            "logical_groups": sum(v > 1 for v in logical_counts.values()),
                            "record_id_extra_rows": sum(bool(u.record_id) for u in units) - len(record_ids),
                            "record_id_conflicting_logical_groups": sum(len(v) > 1 for v in record_ids.values()),
                            "repository_number_multiple_types": sum(len(v) > 1 for v in type_sets.values()),
                            "policy": config.duplicate_policy},
             "sources_before_exclusions": dict(sources), "categories_before_exclusions": dict(categories),
             "strata_before_exclusions": dict(before),
             "repositories_before_exclusions": {s: len(v) for s, v in seen_repositories.items()}}
    blockers = []
    if problems:
        blockers.append(f"{total - len(units)} registros inválidos: consulte invalid_examples")
    if duplicate_logical and config.duplicate_policy == "error":
        blockers.append(f"{duplicate_logical} linhas com identidade lógica repetida; defina a unidade amostral explicitamente")
    observed = {"total": total, "provider": sources["provider"], "community": sources["community"]}
    if observed != config.expected_counts:
        blockers.append(f"Contagens do corpus divergentes: observado={observed}, esperado={config.expected_counts}")
    if not mapping_approved(mapping, config.approval):
        blockers.append("Agrupamento não aprovado ou aprovação não corresponde ao SHA-256 do mapeamento")
    prepared = Prepared(config, mapping, units, set(), audit, inputs, blockers)
    from .exclusions import apply_exclusions
    apply_exclusions(prepared)
    audit["duplicates"]["eligible_logical_extra_rows"] = len(prepared.eligible) - len({u.logical_id for u in prepared.eligible})
    if not prepared.eligible:
        blockers.append("População elegível vazia")
    # Input stability covers metadata and exclusions as well as the large corpus.
    verify_inputs(prepared)
    return prepared


def verify_inputs(prepared: Prepared) -> None:
    from pathlib import Path
    for role, metadata in prepared.inputs.items():
        if sha256_file(Path(metadata["path"])) != metadata["sha256"]:
            raise ValidationError(f"Arquivo de entrada modificado durante a execução: {role}")
