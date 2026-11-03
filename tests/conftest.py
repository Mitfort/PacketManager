import json
from itertools import product

import pytest

from src.parser import Repozytorium
from src.stan import Stan


@pytest.fixture
def repo_przyklad():
    return Repozytorium(json.dumps({"packages": {
        "app": {"versions": {"1.0": {"requires": ["lib >=1.0"]},
                              "2.0": {"requires": ["lib >=2.0", "util"]}}},
        "lib": {"versions": {"1.0": {}, "1.5": {"requires": ["util >=2.0"]},
                              "2.0": {"requires": ["util >=2.0"]}}},
        "util": {"versions": {"1.0": {}, "2.0": {}}},
        "tool": {"versions": {"1.1": {"requires": ["lib <2.0", "json-fast | json-slow >=1.0"]}}},
        "json-fast": {"versions": {"1.0": {"requires": ["missing"]}}},
        "json-slow": {"versions": {"1.0": {}}},
        "legacy": {"versions": {"1.0": {"conflicts": ["util >=2.0"]}}},
    }}))


@pytest.fixture
def stan_przyklad():
    return Stan({"app": (1,), "tool": (1, 1), "lib": (1,), "json-slow": (1,)},
                {"app", "tool"})


@pytest.fixture
def male_repo():
    return Repozytorium(json.dumps({"packages": {
        "a": {"versions": {"1": {"requires": ["b==1"]}, "2": {"requires": ["b==2"]}}},
        "b": {"versions": {"1": {}, "2": {}}},
        "c": {"versions": {"1": {"conflicts": ["a>=2"]}, "2": {"conflicts": ["b==2"]}}},
    }}))


@pytest.fixture
def male_stany():
    stany = []
    for wersje in product((None, (1,), (2,)), repeat=3):
        stan = dict((n, w) for n, w in zip("abc", wersje) if w is not None)
        if "a" in stan and stan.get("b") != stan["a"]:
            continue
        if stan.get("c") == (1,) and stan.get("a") == (2,):
            continue
        if stan.get("c") == (2,) and stan.get("b") == (2,):
            continue
        stany.append(stan)
    return stany
