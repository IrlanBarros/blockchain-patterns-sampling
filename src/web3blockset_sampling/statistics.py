"""Pure functions for the stated stratified finite-population design."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass

from .errors import ValidationError


def cochran_n0(z: float = 1.96, p: float = 0.5, error: float = 0.05) -> float:
    if not all(math.isfinite(v) for v in (z, p, error)) or not (z > 0 and 0 < p < 1 and 0 < error < 1):
        raise ValidationError("Parâmetros de Cochran inválidos")
    return z * z * p * (1 - p) / (error * error)


def sample_size(population: int, z: float = 1.96, p: float = 0.5, error: float = 0.05) -> int:
    if not isinstance(population, int) or isinstance(population, bool) or population < 0:
        raise ValidationError("População deve ser inteiro não negativo")
    n0 = cochran_n0(z, p, error)
    if population == 0:
        return 0
    return min(population, math.ceil(n0 / (1 + (n0 - 1) / population)))


@dataclass(frozen=True)
class Allocation:
    stratum: str
    population: int
    sample: int
    population_weight: float
    design_weight: float | None
    sampling_fraction: float
    provider_weight: float | None

    def to_dict(self) -> dict:
        return asdict(self)


def allocate(counts: dict[str, int], z: float = 1.96, p: float = 0.5, error: float = 0.05) -> dict[str, Allocation]:
    total = sum(counts.values())
    if total <= 0:
        raise ValidationError("População elegível vazia")
    provider_total = sum(v for k, v in counts.items() if k != "Community")
    result = {}
    for stratum, population in counts.items():
        n = sample_size(population, z, p, error)
        result[stratum] = Allocation(stratum, population, n, population / total,
                                    population / n if n else None, n / population if population else 0,
                                    population / provider_total if provider_total and stratum != "Community" else None)
    return result

