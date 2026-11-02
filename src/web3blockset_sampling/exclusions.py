"""Exclude pilot logical identities before allocation, with explicit diagnostics."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import TYPE_CHECKING

from .errors import ValidationError
from .identity import key, normalize
from .ingestion import rows

if TYPE_CHECKING:
    from .preparation import Prepared


def apply_exclusions(prepared: Prepared) -> None:
    from .preparation import check_schema
    config = prepared.config
    matches: dict[tuple, list] = defaultdict(list)
    for unit in prepared.units:
        matches[unit.pilot_key].append(unit)
    for role, path in (("pilot", config.pilot), ("smoke", config.smoke)):
        if path is None:
            continue
        schema = check_schema(config, role if role in config.schemas else "pilot", path, set(config.pilot_fields))
        seen = set()
        key_counts = Counter()
        missing, ambiguous, duplicated = [], [], []
        matched_logical, removed, found_keys = set(), set(), set()
        input_count = 0
        for input_count, row in enumerate(rows(path, config.encoding, config.delimiter), start=1):
            try:
                schema_role = role if role in config.schemas else "pilot"
                pilot_key = key(normalize(row, schema, config, role=schema_role), config.pilot_fields)
            except ValidationError as exc:
                raise ValidationError(f"Identidade inválida em {role}, registro {input_count}: {exc}") from exc
            if pilot_key in seen:
                duplicated.append(pilot_key)
            seen.add(pilot_key)
            key_counts[pilot_key] += 1
            candidates = matches.get(pilot_key, [])
            lids = {u.logical_id for u in candidates}
            if not candidates:
                missing.append(pilot_key)
            elif len(lids) > 1:
                ambiguous.append(pilot_key)
            else:
                found_keys.add(pilot_key)
                matched_logical.update(lids)
                removed.update(u.unit_id for u in candidates)
        previous = set(prepared.excluded)
        prepared.excluded.update(removed)
        report = {"input_rows": input_count, "unique_keys": len(seen), "found_keys": len(found_keys),
                  "logical_identifiers_excluded": len(matched_logical), "rows_matched": len(removed),
                  "rows_removed": len(removed - previous), "overlap_previous_exclusions": len(removed & previous),
                  "missing_count": len(missing), "missing_examples": missing[:30],
                  "ambiguous_count": len(ambiguous), "ambiguous_examples": ambiguous[:30],
                  "duplicate_keys": len(duplicated), "duplicate_examples": duplicated[:30]}
        prepared.audit[role + "_exclusion"] = report
        if missing or ambiguous or duplicated:
            prepared.blockers.append(f"{role}: chaves ausentes, ambíguas ou repetidas; consulte o diagnóstico de exclusão")
        if role == "pilot" and (len(matched_logical) != config.expected_pilot or input_count != config.expected_pilot
                                or len(removed) != config.expected_pilot):
            report["expected"] = config.expected_pilot
            report["divergence_decision"] = config.exclusion_decision
            if not config.exclusion_decision.strip():
                prepared.blockers.append("Exclusão do piloto diverge dos 200 casos/linhas esperados; exige exclusion_decision")
        # Keep keys for an independent overlap test during validation.
        report["keys"] = [list(k) for k in sorted(seen)]
        report["key_results"] = []
        for pilot_key in sorted(seen):
            candidates = matches.get(pilot_key, [])
            lids = {u.logical_id for u in candidates}
            status = ("duplicate_input_key" if key_counts[pilot_key] > 1 else "missing" if not candidates
                      else "ambiguous" if len(lids) > 1 else "matched")
            report["key_results"].append({
                "key": list(pilot_key), "input_occurrences": key_counts[pilot_key], "status": status,
                "matched_rows": len(candidates), "logical_identifiers": len(lids),
                "rows_removed": sum(u.unit_id in removed - previous for u in candidates),
                "sources": dict(Counter(u.source for u in candidates)),
                "strata": dict(Counter(u.stratum for u in candidates)),
            })
