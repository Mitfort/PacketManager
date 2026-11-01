import pytest

from src.stan import Stan


def test_odczyt_zapis_zachowuje_stan_i_reczne(tmp_path):
    # Arrange
    wejscie = tmp_path / "stan.txt"
    wejscie.write_text("# komentarz\nFoo__BAR 1.0.0 manual\nlib 2.0 # zależność\n", encoding="utf-8")
    wyjscie = tmp_path / "wynik.txt"

    # Act
    stan = Stan.wczytaj(wejscie)
    stan.zapisz(wyjscie)
    zapisany = Stan.wczytaj(wyjscie)

    # Assert
    assert stan.pakiety == zapisany.pakiety == {"foo-bar": (1,), "lib": (2,)}
    assert stan.reczne == zapisany.reczne == {"foo-bar"}


@pytest.mark.parametrize("tekst", [
    "app", "app 1.0 automatic", "app -1", "app 1.0 manual extra",
    "Foo_Bar 1.0\nfoo.bar 2.0", "app! 1.0",
])
def test_niepoprawny_stan_ma_numer_linii(tmp_path, tekst):
    # Arrange
    plik = tmp_path / "stan.txt"
    plik.write_text(tekst, encoding="utf-8")

    # Act / Assert
    with pytest.raises(ValueError, match=r"[Ll]ini"):
        Stan.wczytaj(plik)


def test_plan_obejmuje_wszystkie_rodzaje_zmian():
    # Arrange
    stary = Stan({"up": (1,), "down": (2,), "remove": (1,), "same": (1,)})
    nowy = Stan({"up": (2,), "down": (1,), "install": (1,), "same": (1,)})

    # Act
    plan = stary.plan(nowy)

    # Assert
    assert len(plan) == 4
    assert all(any(nazwa in wpis for wpis in plan) for nazwa in ("up", "down", "remove", "install"))
    assert not any("same" in wpis for wpis in plan)
