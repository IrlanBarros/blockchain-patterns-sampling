import math

import pytest

from web3blockset_sampling.errors import ValidationError
from web3blockset_sampling.statistics import allocate, cochran_n0, sample_size


def test_cochran():
    assert cochran_n0() == pytest.approx(384.16)
    assert cochran_n0(p=0.2) < cochran_n0()


@pytest.mark.parametrize("population, expected", [(121100, 383), (53600, 382), (51900, 382), (50000, 382),
                                                   (48100, 382), (23300, 378), (18200, 377), (17200, 376), (8209, 368)])
def test_methodology_approximate_table(population, expected):
    assert sample_size(population) == expected


@pytest.mark.parametrize("population", [0, 1, 2, 3, 10, 100, 1000])
def test_small_populations_and_rounding(population):
    n = sample_size(population)
    assert 0 <= n <= population
    if population:
        continuous = 384.16 / (1 + 383.16 / population)
        assert n == math.ceil(continuous)


@pytest.mark.parametrize("args", [{"z": 0}, {"p": 1}, {"p": 0}, {"error": 0}, {"z": float("nan")}, {"error": float("inf")}])
def test_invalid_parameters(args):
    with pytest.raises(ValidationError):
        cochran_n0(**args)


def test_weights_and_provider_comparison():
    allocation = allocate({"A": 100, "B": 200, "Community": 50})
    assert sum(a.population_weight for a in allocation.values()) == pytest.approx(1)
    assert sum(a.provider_weight or 0 for a in allocation.values()) == pytest.approx(1)
    assert allocation["A"].provider_weight == pytest.approx(1 / 3)
    for a in allocation.values():
        assert a.design_weight == a.population / a.sample
        assert a.sampling_fraction * a.design_weight == pytest.approx(1)


@pytest.mark.parametrize("population", [-1, 1.5, True])
def test_bad_population(population):
    with pytest.raises(ValidationError):
        sample_size(population)


def test_empty_population():
    with pytest.raises(ValidationError):
        allocate({"A": 0})

