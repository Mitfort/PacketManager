import pytest

from src.bazawiedzy import BazaWiedzy, weryfikujStan
from src.parser import Requirement
from src.stan import Stan


def test_instalacja_do_stanu_z_pdf(repo_przyklad, stan_przyklad):
    # Arrange
    manager = BazaWiedzy(repo_przyklad)
    zadania = [Requirement("app==2.0", "żądanie")]

    # Act
    wynik = manager.instaluj(zadania, stan_przyklad)

    # Assert
    assert wynik is not None
    assert wynik.pakiety == {"app": (2,), "lib": (2,), "util": (2,), "json-slow": (1,)}
    assert wynik.reczne == {"app"}
    assert stan_przyklad.pakiety["app"] == (1,)
    assert weryfikujStan(repo_przyklad, wynik.pakiety, zadania)


def test_zadanie_juz_zainstalowane_zachowuje_wersje_i_staje_sie_reczne(repo_przyklad):
    # Arrange
    stary = Stan({"lib": (1,)})

    # Act
    wynik = BazaWiedzy(repo_przyklad).instaluj([Requirement("lib", "żądanie")], stary)

    # Assert
    assert wynik is not None
    assert wynik.pakiety == {"lib": (1,)}
    assert wynik.reczne == {"lib"}


def test_kolejne_zapytania_nie_dziedzicza_ograniczen(repo_przyklad):
    # Arrange
    manager = BazaWiedzy(repo_przyklad)

    # Act
    pierwszy = manager.instaluj([Requirement("app==2", "żądanie")])
    sprzeczny = manager.instaluj([Requirement("app==2", "żądanie"), Requirement("tool", "żądanie")])
    ostatni = manager.instaluj([Requirement("tool", "żądanie")])

    # Assert
    assert pierwszy is not None
    assert sprzeczny is None
    assert ostatni is not None
    assert ostatni.pakiety == {"tool": (1, 1), "lib": (1,), "json-slow": (1,)}


@pytest.mark.parametrize("poczatek", [{}, {"a": (1,), "b": (1,)}, {"b": (2,), "c": (1,)}])
@pytest.mark.parametrize("zadanie", ["a==2", "b", "c"])
def test_instalacja_ma_optymalne_kryteria_w_przegladzie_wyczerpujacym(male_repo, male_stany, poczatek, zadanie):
    # Arrange
    nazwa = zadanie[0]
    kandydaci = [s for s in male_stany if nazwa in s and (zadanie != "a==2" or s[nazwa] == (2,))]

    def koszt(stan):
        nowe = stan.keys() - poczatek.keys()
        return (len(poczatek.keys() - stan.keys()),
                sum(stan[n] != poczatek[n] for n in stan.keys() & poczatek.keys()),
                2 - stan[nazwa][0] if nazwa in nowe else 0,
                len(nowe), sum(2 - stan[n][0] for n in nowe if n != nazwa))

    # Act
    wynik = BazaWiedzy(male_repo).instaluj([Requirement(zadanie, "żądanie")], Stan(poczatek, set(poczatek)))

    # Assert
    assert wynik is not None
    assert wynik.pakiety in kandydaci
    assert koszt(wynik.pakiety) == min(map(koszt, kandydaci))
    assert wynik.reczne == (set(poczatek) | {nazwa}) & wynik.pakiety.keys()


def test_weryfikator_sprawdza_tez_zadania(repo_przyklad):
    # Arrange
    zadania = [Requirement("app==2", "żądanie")]

    # Act
    poprawny = weryfikujStan(repo_przyklad, {}, zadania)

    # Assert
    assert not poprawny
