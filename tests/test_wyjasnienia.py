import z3

from src.bazawiedzy import BazaWiedzy
from src.parser import Requirement
from src.wyjasnienia import wyjasnij


def test_rdzen_jest_sprzeczny_i_minimalny(repo_przyklad):
    # Arrange
    baza = BazaWiedzy(repo_przyklad)
    zadania = [Requirement("app==2", "żądanie"), Requirement("tool", "żądanie")]
    formuly = dict(baza.aksjomaty)
    formuly.update({"Żądanie: app==2": baza.vars[("app", (2,))],
                    "Żądanie: tool": baza.vars[("tool", (1, 1))]})

    # Act
    etykiety = wyjasnij(baza, zadania)
    rdzen = [formuly[e] for e in etykiety]

    # Assert
    assert len(etykiety) == len(set(etykiety))
    solver = z3.Solver()
    solver.add(*rdzen)
    assert solver.check() == z3.unsat
    for i in range(len(rdzen)):
        solver = z3.Solver()
        solver.add(*(rdzen[:i] + rdzen[i + 1:]))
        assert solver.check() == z3.sat


def test_spelnialne_zadanie_nie_ma_rdzenia(repo_przyklad):
    # Act
    rdzen = wyjasnij(BazaWiedzy(repo_przyklad), [Requirement("app", "żądanie")])

    # Assert
    assert rdzen == []
