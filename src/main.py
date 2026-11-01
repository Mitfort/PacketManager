"""Jeden pełny przebieg projektu: python -m src.main."""
from pathlib import Path
from src.bazawiedzy import BazaWiedzy
from src.eksperymenty import uruchom, zapisz_wyniki
from src.parser import Repozytorium, wczytaj_zadania
from src.stan import Stan

def main(katalog_projektu: Path | None = None) -> None:
    if katalog_projektu is None:
        katalog_projektu = Path(__file__).resolve().parents[1]

    katalog_repozytoriow = katalog_projektu / "repos" / "k05"
    katalog_wynikow = katalog_projektu / "results"
    katalog_przykladow = katalog_projektu / "examples"
    katalog_wynikow.mkdir(parents=True, exist_ok=True)

    print("\n=== Pełny przebieg projektu — grupa k05 ===\n")

    repo = Repozytorium((katalog_przykladow / "repo_example.json").read_text(encoding="utf-8"))
    baza = BazaWiedzy(repo)
    stan = Stan.wczytaj(katalog_projektu / "state_example.txt")

    print("Stan początkowy:")
    print(stan.tekst())

    print("--- Instalacja app==2.0 do istniejącego stanu ---\n")
    zadania = wczytaj_zadania(katalog_przykladow / "install_app.txt")
    wynik = baza.instaluj(zadania, stan)
    _pokaz_i_zapisz(stan, wynik, katalog_wynikow / "example_install.txt")

    # Każdy wariant usuwania zaczyna od tego samego stanu, aby porównać wyniki.
    przyklady_usuwania = [
        ("Usunięcie lib", "remove_lib.txt", False, "example_remove_lib.txt"),
        ("Usunięcie tool", "remove_tool.txt", False, "example_remove_tool.txt"),
        ("Usunięcie tool z autoremove", "remove_tool.txt", True, "example_autoremove.txt"),
    ]

    for opis, plik_zadan, autoremove, plik_wyniku in przyklady_usuwania:
        print(f"--- {opis} ---\n")
        zadania = wczytaj_zadania(katalog_przykladow / plik_zadan, tylko_nazwy=True)
        nazwy = [zadanie.alternatives[0]["package"] for zadanie in zadania]

        wynik = baza.usun(nazwy, stan, autoremove=autoremove)
        _pokaz_i_zapisz(stan, wynik, katalog_wynikow / plik_wyniku)

    wyniki = uruchom(katalog_repozytoriow, ziarno=2026, kroki=12)

    print("\n--- Wyjaśnienie sprzeczności przykładowych żądań ---\n")

    for etykieta in wyniki["wyjasnienie_przykladu"]:
        print(f"- {etykieta}")

    plik_danych = katalog_wynikow / "punkty6.json"
    zapisz_wyniki(wyniki, plik_danych)

    print(f"\nDane: {plik_danych}")
    print(f"Raport: {plik_danych.with_suffix('.md')}\n")


def _pokaz_i_zapisz(stan: Stan, wynik: Stan | None, sciezka: Path) -> None:
    """Pokazuje plan i zapisuje wynik pojedynczej operacji przykładowej."""
    if wynik is None:
        raise RuntimeError(f"Przykład {sciezka.stem} nie ma rozwiązania")

    print("Plan zmian:")

    for zmiana in stan.plan(wynik):
        print(f"- {zmiana}")

    wynik.zapisz(sciezka)

    print("\nStan po operacji:")
    print(wynik.tekst())


if __name__ == "__main__":
    main()
