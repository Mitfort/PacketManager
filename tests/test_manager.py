import json

import pytest

from src.manager import main
from src.stan import Stan


@pytest.fixture
def pliki_cli(tmp_path):
    repo = tmp_path / "repo.json"
    repo.write_text(json.dumps({"packages": {
        "app": {"versions": {"1": {"requires": ["lib==1"]}, "2": {"requires": ["lib==2"]}}},
        "lib": {"versions": {"1": {}, "2": {}}},
    }}), encoding="utf-8")
    zadania = tmp_path / "zadania.txt"
    stan = tmp_path / "stan.txt"
    return repo, zadania, stan


def test_install_zapisuje_stan_reczny_i_plan(pliki_cli, capsys):
    # Arrange
    repo, zadania, stan = pliki_cli
    zadania.write_text("app\n", encoding="utf-8")

    # Act
    status = main(["install", str(zadania), "--repo", str(repo), "--output", str(stan)])
    wynik = Stan.wczytaj(stan)

    # Assert
    assert status == 0
    assert wynik.pakiety == {"app": (2,), "lib": (2,)}
    assert wynik.reczne == {"app"}
    assert "Instalacja: app 2" in capsys.readouterr().out


def test_sprzeczne_zadania_nie_nadpisuja_stanu(pliki_cli, capsys):
    # Arrange
    repo, zadania, stan = pliki_cli
    zadania.write_text("app==2\nlib==1\n", encoding="utf-8")
    oryginal = b"# zachowaj komentarz\r\napp 1 manual\r\nlib 1\r\n"
    stan.write_bytes(oryginal)

    # Act
    status = main(["install", str(zadania), "--repo", str(repo), "--state", str(stan)])

    # Assert
    assert status == 1
    assert stan.read_bytes() == oryginal
    assert "Brak rozwiązania" in capsys.readouterr().out


def test_bledne_zadanie_wskazuje_numer_linii(pliki_cli, capsys):
    # Arrange
    repo, zadania, stan = pliki_cli
    zadania.write_text("# komentarz\napp =>2\n", encoding="utf-8")

    # Act
    status = main(["install", str(zadania), "--repo", str(repo), "--output", str(stan)])

    # Assert
    assert status == 2
    assert "linia 2" in capsys.readouterr().out
    assert not stan.exists()


def test_remove_autoremove_zapisuje_stan(pliki_cli, capsys):
    # Arrange
    repo, zadania, stan = pliki_cli
    zadania.write_text("app\n", encoding="utf-8")
    stan.write_text("app 1 manual\nlib 1\n", encoding="utf-8")

    # Act
    status = main(["remove", str(zadania), "--repo", str(repo), "--state", str(stan), "--autoremove"])
    wynik = Stan.wczytaj(stan)

    # Assert
    assert status == 0
    assert wynik.pakiety == {}
    assert wynik.reczne == set()
    assert "Usunięcie: lib 1" in capsys.readouterr().out
