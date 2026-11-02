"""Intentional technical coverage; never a probabilistic sampling design."""

from __future__ import annotations

import heapq
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from .errors import ValidationError
from .export import occurrence_rows, project_pipeline_row
from .ingestion import digest_json
from .preparation import Prepared, Unit
from .stratification import STRATA

ALGORITHM = "intentional-coverage-v1"
SIZE = 15
LONG_TEXT_MIN = 8000
PREFERRED_TEXT_MAX = 16000
LEXICAL_TARGET = 3
# Superficial integration cues, not pattern labels or a substitute for Stage 1.
LEXICAL_TERMS = (
    "proxy", "oracle", "access control", "state machine", "factory", "circuit breaker",
    "commit reveal", "commit-reveal", "multisig", "multi-signature", "upgradeability",
    "off-chain", "on-chain", "escrow", "time lock", "timelock",
)
LEXICAL_PATTERNS = tuple((term, re.compile(r"(?<!\w)" + re.escape(term) + r"(?!\w)", re.I))
                         for term in LEXICAL_TERMS)
SCENARIOS = (
    "commits_zero", "commits_positive", "commits_empty", "title_present", "body_present",
    "comments_present", "body_empty", "comments_empty", "long_text", "state_open",
    "state_closed", "closed_at_present", "closed_at_empty", "lexical_cue",
)
BITS = {name: 1 << i for i, name in enumerate(SCENARIOS)}


@dataclass(frozen=True, slots=True)
class Candidate:
    unit: Unit
    mask: int
    lengths: tuple[int, int, int]
    lexical_terms: tuple[str, ...]
    tie: str

    @property
    def text_length(self) -> int:
        return sum(self.lengths)

    @property
    def cost(self) -> int:
        return max(0, self.text_length - PREFERRED_TEXT_MAX)

    @property
    def mandatory(self) -> int:
        return (1 << STRATA.index(self.unit.stratum)) | (1 << (9 + (self.unit.artifact_type == "pull_request")))


def features(unit: Unit, pipeline: dict, seed: int) -> Candidate:
    title, body, comments = (pipeline[name] for name in ("issue_title", "issue_body", "concatenated_comments"))
    lengths = (len(title), len(body), len(comments))
    texts = tuple(text.casefold() for text in (title, body, comments))
    lexical = tuple(term for term, pattern in LEXICAL_PATTERNS
                    if any(term in text and pattern.search(text) for text in texts))
    value = pipeline["commits_count"].strip()
    commit_scenario = "commits_empty" if not value else ""
    if value:
        try:
            number = Decimal(value)
            if number.is_finite():
                commit_scenario = "commits_zero" if number == 0 else "commits_positive" if number > 0 else ""
        except InvalidOperation:
            pass  # Invalid/literal values are retained verbatim, never treated as zero.
    names = [commit_scenario, "title_present" if title.strip() else "",
             "body_present" if body.strip() else "body_empty",
             "comments_present" if comments.strip() else "comments_empty",
             "long_text" if sum(lengths) >= LONG_TEXT_MIN else "",
             "state_open" if pipeline["state"].strip().casefold() == "open" else "",
             "state_closed" if pipeline["state"].strip().casefold() == "closed" else "",
             "closed_at_present" if pipeline["closed_at"].strip() else "closed_at_empty",
             "lexical_cue" if lexical else ""]
    return Candidate(unit, sum(BITS[n] for n in names if n), lengths, lexical,
                     digest_json([ALGORITHM, seed, unit.unit_id]))


def profile_candidates(prepared: Prepared, seed: int) -> tuple[list[Candidate], dict]:
    """One streaming pass; keep <=15 interchangeable candidates per signature.

    Equal signatures cover exactly the same constraints. Keeping the best 15
    (cost, seeded tie) is sufficient for every step of a 15-unit greedy selection.
    All repeated-identity occurrences are retained so pair reservation is exact.
    """
    eligible = prepared.eligible
    logical = Counter(u.logical_id for u in eligible)
    ids = {u.unit_id for u in eligible}
    pools: dict[tuple, list] = defaultdict(list)
    duplicates = {}
    available = Counter({name: 0 for name in SCENARIOS})
    seen = set()
    for unit, raw in occurrence_rows(prepared, ids):
        projected = project_pipeline_row({**raw, "sampling_unit_id": unit.unit_id,
                                  "sampling_repository": unit.repository}, prepared)
        candidate = features(unit, projected, seed)
        seen.add(unit.unit_id)
        for name, bit in BITS.items():
            available[name] += bool(candidate.mask & bit)
        signature = (unit.stratum, unit.artifact_type, candidate.mask)
        # A max-heap encoded with negative ranks keeps the least preferred on top.
        entry = (-candidate.cost, -int(candidate.tie, 16), unit.unit_id, candidate)
        pool = pools[signature]
        heapq.heappush(pool, entry)
        if len(pool) > SIZE:
            heapq.heappop(pool)
        if logical[unit.logical_id] > 1:
            duplicates[unit.unit_id] = candidate
    if seen != ids:
        raise ValidationError("Perfil não recuperou exatamente a população elegível")
    kept = {entry[3].unit.unit_id: entry[3] for pool in pools.values() for entry in pool}
    kept.update(duplicates)
    return sorted(kept.values(), key=lambda c: c.unit.unit_id), dict(available)


def real_pairs(candidates: list[Candidate]) -> list[tuple[Candidate, Candidate]]:
    groups = defaultdict(list)
    for candidate in candidates:
        groups[candidate.unit.logical_id].append(candidate)
    pairs = []
    for _, group in sorted(groups.items()):
        providers = sorted((c for c in group if c.unit.source == "provider"), key=lambda c: c.unit.unit_id)
        community = sorted((c for c in group if c.unit.source == "community"), key=lambda c: c.unit.unit_id)
        pairs.extend((a, b) for a in providers for b in community if a.unit.unit_id != b.unit.unit_id)
    return pairs


def select(candidates: list[Candidate], size: int = SIZE) -> list[Candidate]:
    if size != SIZE:
        raise ValidationError("Esta modalidade suporta exatamente --size 15; outros tamanhos exigem contrato de cobertura próprio")
    indexed = {c.unit.unit_id: c for c in candidates}
    if len(indexed) != len(candidates) or any(not uid.strip() for uid in indexed):
        raise ValidationError("Candidatos com sampling_unit_id vazio ou duplicado")
    if len(candidates) < size:
        raise ValidationError(f"Seleção impossível: somente {len(candidates)} ocorrências elegíveis para {size} posições")
    absent = set(STRATA) - {c.unit.stratum for c in candidates}
    if absent:
        raise ValidationError(f"Cobertura obrigatória impossível; estratos ausentes: {sorted(absent)}")
    if {c.unit.artifact_type for c in candidates} != {"issue", "pull_request"}:
        raise ValidationError("Cobertura obrigatória impossível: exige Issues e PRs nos valores reais de artifact_type")
    pairs = real_pairs(candidates)
    if not pairs:
        raise ValidationError("Par real obrigatório indisponível: nenhuma identidade lógica elegível com ocorrências provider e community")
    pair = min(pairs, key=lambda p: (-((p[0].mandatory | p[1].mandatory).bit_count()),
                                   -((p[0].mask | p[1].mask).bit_count()),
                                   p[0].cost + p[1].cost, p[0].tie, p[1].tie))
    chosen = list(pair)
    used = {c.unit.unit_id for c in chosen}
    hard = pair[0].mandatory | pair[1].mandatory
    covered = pair[0].mask | pair[1].mask
    lexical_count = sum(bool(c.lexical_terms) for c in chosen)
    for _ in range(size - len(chosen)):
        best = min((c for c in candidates if c.unit.unit_id not in used),
                   key=lambda c: (-(c.mandatory & ~hard).bit_count(), -(c.mask & ~covered).bit_count(),
                                  -int(bool(c.lexical_terms) and lexical_count < LEXICAL_TARGET), c.cost, c.tie))
        chosen.append(best)
        used.add(best.unit.unit_id)
        hard |= best.mandatory
        covered |= best.mask
        lexical_count += bool(best.lexical_terms)
    # 11 hard bits (9 strata + 2 types) plus a pair require at most 13 slots.
    if hard != (1 << 11) - 1:
        raise ValidationError("Conflito de cobertura obrigatória dentro das 15 posições")
    return sorted(chosen, key=lambda c: c.unit.unit_id)


def selection_details(chosen: list[Candidate], available: dict) -> dict:
    coverage = {}
    for name, bit in BITS.items():
        count = sum(bool(c.mask & bit) for c in chosen)
        coverage[name] = {"selected": count, "available": available[name], "covered": bool(count),
                          "limitation": "" if count else "indisponível na população elegível" if not available[name]
                          else "não contemplado pela heurística de cobertura nas 15 posições"}
    pairs = real_pairs(chosen)
    pair_ids = {c.unit.unit_id for pair in pairs for c in pair}
    return {"selected_ids": [c.unit.unit_id for c in chosen],
            "strata": dict(Counter(c.unit.stratum for c in chosen)),
            "artifact_types": dict(Counter(c.unit.artifact_type for c in chosen)),
            "sources": dict(Counter(c.unit.source for c in chosen)), "coverage": coverage,
            "repeated_identity_pairs": [{"sampling_logical_id": a.unit.logical_id,
                                         "sampling_unit_ids": [a.unit.unit_id, b.unit.unit_id]}
                                        for a, b in pairs],
            "records": [{"sampling_unit_id": c.unit.unit_id, "stratum": c.unit.stratum,
                         "artifact_type": c.unit.artifact_type, "source": c.unit.source,
                         "criteria": ["stratum:" + c.unit.stratum, "type:" + c.unit.artifact_type]
                                     + [n for n, bit in BITS.items() if c.mask & bit]
                                     + (["repeated_logical_identity"] if c.unit.unit_id in pair_ids else []),
                         "text_lengths": dict(zip(("title", "body", "comments"), c.lengths)),
                         "lexical_terms": list(c.lexical_terms)} for c in chosen]}
