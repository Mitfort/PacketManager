import json
import shutil
from pathlib import Path

import pytest

from src.bazawiedzy import weryfikujStan
from src.main import main
from src.parser import Repozytorium, Requirement
from src.stan import Stan


@pytest.fixture
def projekt_przykladowy(tmp_path):
    katalog_projektu = Path(__file__).resolve().parents[1]
    katalog_repozytoriow = tmp_path / "repos" / "k05"
    katalog_repozytoriow.mkdir(parents=True)

    shutil.copytree(katalog_projektu / "examples", tmp_path / "examples")
    shutil.copyfile(katalog_projektu / "state_example.txt", tmp_path / "state_example.txt")

    for rozmiar in (10, 30, 100, 200, 300, 1000):
        shutil.copyfile(
            katalog_projektu / "examples" / "repo_example.json",
            katalog_repozytoriow / f"repo_{rozmiar}.json",
        )

        if rozmiar != 200:
            zadania = "app==2.0\ntool\n" if rozmiar == 30 else "app\n"
            (katalog_repozytoriow / f"requests_{rozmiar}.txt").write_text(
                zadania,
                encoding="utf-8",
            )

    return tmp_path


def test_main_wykonuje_pelny_przebieg_i_zapisuje_raport(projekt_przykladowy, capsys):
    # Arrange
    tmp_path = projekt_przykladowy

    # Act
    main(tmp_path)
    plik_danych = tmp_path / "results" / "punkty6.json"
    wyniki = json.loads(plik_danych.read_text(encoding="utf-8"))

    # Assert
    assert [pomiar["N"] for pomiar in wyniki["instalacje"]] == [10, 30, 100, 300, 1000]
    assert wyniki["instalacje"][1]["wyjasnienie"]
    assert wyniki["wyjasnienie_przykladu"]
    assert len(wyniki["scenariusz"]) == 12
    assert all(krok["weryfikacja"] == "OK" for krok in wyniki["scenariusz"])
    assert (tmp_path / "results" / "punkty6.md").is_file()

    instalacja = Stan.wczytaj(tmp_path / "results" / "example_install.txt")
    usuniecie = Stan.wczytaj(tmp_path / "results" / "example_remove_tool.txt")
    autoremove = Stan.wczytaj(tmp_path / "results" / "example_autoremove.txt")

    assert instalacja.pakiety["app"] == (2,)
    assert instalacja.reczne == {"app"}
    assert "json-slow" in usuniecie.pakiety
    assert "json-slow" not in autoremove.pakiety

    komunikaty = capsys.readouterr().out
    assert "Plan zmian:" in komunikaty
    assert "Wyjaśnienie sprzeczności przykładowych żądań" in komunikaty
    assert "Żądanie: app==2.0" in komunikaty

    repo = Repozytorium((tmp_path / "repos" / "k05" / "repo_200.json").read_text(encoding="utf-8"))

    for krok in wyniki["scenariusz"]:
        pakiety = {nazwa: tuple(opis["wersja"]) for nazwa, opis in krok["stan"].items()}
        zadania = []

        if krok["operacja"] == "install" and krok["wynik"] == "OK":
            zadania = [Requirement(krok["zadanie"], "scenariusz")]
        elif krok["operacja"] != "install":
            assert krok["zadanie"] not in pakiety

        assert weryfikujStan(repo, pakiety, zadania)


def test_main_korzysta_z_przykladow_wskazanego_projektu(projekt_przykladowy):
    # Arrange
    plik_zadan = projekt_przykladowy / "examples" / "requests_example.txt"
    plik_zadan.write_text("pakiet-tylko-w-tescie\n", encoding="utf-8")

    # Act
    main(projekt_przykladowy)
    plik_danych = projekt_przykladowy / "results" / "punkty6.json"
    wyniki = json.loads(plik_danych.read_text(encoding="utf-8"))

    # Assert
    assert wyniki["wyjasnienie_przykladu"] == ["Żądanie: pakiet-tylko-w-tescie"]


def test_powtorzenie_main_odtwarza_scenariusz_i_zachowuje_wejscia(projekt_przykladowy):
    # Arrange
    pliki_wejsciowe = [
        plik for plik in projekt_przykladowy.rglob("*") if plik.is_file()
    ]
    przed = {plik: plik.read_bytes() for plik in pliki_wejsciowe}
    plik_danych = projekt_przykladowy / "results" / "punkty6.json"

    # Act
    main(projekt_przykladowy)
    pierwszy = json.loads(plik_danych.read_text(encoding="utf-8"))

    main(projekt_przykladowy)
    drugi = json.loads(plik_danych.read_text(encoding="utf-8"))

    # Assert
    for krok_pierwszy, krok_drugi in zip(pierwszy["scenariusz"], drugi["scenariusz"]):
        assert krok_pierwszy["operacja"] == krok_drugi["operacja"]
        assert krok_pierwszy["zadanie"] == krok_drugi["zadanie"]
        assert krok_pierwszy["stan"] == krok_drugi["stan"]

    assert all(plik.read_bytes() == zawartosc for plik, zawartosc in przed.items())
