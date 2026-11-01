import pytest

from src.bazawiedzy import BazaWiedzy
from src.stan import Stan


def test_usuniecie_lib_usuwa_zalezne_z_pdf(repo_przyklad, stan_przyklad):
    # Act
    wynik = BazaWiedzy(repo_przyklad).usun(["lib"], stan_przyklad)

    # Assert
    assert wynik is not None
    assert wynik.pakiety == {"json-slow": (1,)}
    assert wynik.reczne == set()


@pytest.mark.parametrize("autoremove", [False, True])
def test_autoremove_usuwa_zbedna_zaleznosc(repo_przyklad, stan_przyklad, autoremove):
    # Act
    wynik = BazaWiedzy(repo_przyklad).usun(["tool"], stan_przyklad, autoremove=autoremove)

    # Assert
    assert wynik is not None
    oczekiwany = {"app": (1,), "lib": (1,)}
    if not autoremove:
        oczekiwany["json-slow"] = (1,)
    assert wynik.pakiety == oczekiwany
    assert wynik.reczne == {"app"}


@pytest.mark.parametrize("poczatek,reczne", [
    ({"a": (1,), "b": (1,), "c": (1,)}, {"a", "c"}),
    ({"a": (2,), "b": (2,)}, {"a"}),
    ({"b": (1,), "c": (2,)}, {"c"}),
])
@pytest.mark.parametrize("usun", ["a", "b", "c"])
@pytest.mark.parametrize("autoremove", [False, True])
def test_usuwanie_ma_optymalne_kryteria_w_przegladzie_wyczerpujacym(male_repo, male_stany, poczatek, reczne, usun, autoremove):
    # Arrange
    kandydaci = [s for s in male_stany if usun not in s]

    def koszt(stan):
        usuniete = poczatek.keys() - stan.keys()
        return (len((reczne - {usun}) & usuniete),
                sum(stan[n] != poczatek[n] for n in stan.keys() & poczatek.keys()),
                len(stan.keys() - poczatek.keys()),
                len(stan) if autoremove else len(usuniete))

    # Act
    wynik = BazaWiedzy(male_repo).usun([usun], Stan(poczatek, reczne), autoremove=autoremove)

    # Assert
    assert wynik is not None
    assert wynik.pakiety in kandydaci
    assert koszt(wynik.pakiety) == min(map(koszt, kandydaci))
    assert wynik.reczne == reczne & wynik.pakiety.keys()
