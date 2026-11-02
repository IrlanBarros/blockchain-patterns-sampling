"""Versioned SRSWOR: sorted IDs, independent SHA-256-derived RNG per stratum."""

from __future__ import annotations

import random
from collections import defaultdict
from typing import Iterable

from .ingestion import digest_json
from .statistics import Allocation

ALGORITHM = "sorted-ids-python-random-sample-sha256-stratum-v1"


def draw(units: Iterable, allocation: dict[str, Allocation], seed: int) -> set[str]:
    groups: dict[str, list[str]] = defaultdict(list)
    for unit in units:
        groups[unit.stratum].append(unit.unit_id)
    selected = set()
    for stratum in sorted(allocation):
        ids = sorted(groups[stratum])
        rng = random.Random(int(digest_json([ALGORITHM, seed, stratum]), 16))
        selected.update(rng.sample(ids, allocation[stratum].sample))
    return selected
