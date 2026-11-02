"""Jeden pełny przebieg projektu: python -m src.main."""
from pathlib import Path
from src.bazawiedzy import BazaWiedzy
from src.eksperymenty import uruchom, zapisz_wyniki
from src.manager import formatuj_punkt_pareto
from src.parser import Repozytorium, formatuj_wersje, wczytaj_zadania
from src.stan import Stan


def main(katalog_projektu: Path | None = None) -> None:
    if katalog_projektu is None:
        katalog_projektu = Path(__file__).resolve().parents[1]

    katalog_repozytoriow = katalog_projektu / "repos" / "k05"
    katalog_wynikow = katalog_projektu / "results"
    katalog_przykladow = katalog_projektu / "examples"
    katalog_wynikow.mkdir(parents=True, exist_ok=True)

    print("\n=== Pełny przebieg projektu — grupa k05 (próg 8 punktów) ===\n")

    repo = Repozytorium((katalog_przykladow / "repo_example.json").read_text(encoding="utf-8"))
    baza = BazaWiedzy(repo)
    stan = Stan.wczytaj(katalog_projektu / "state_example.txt")

    print("Stan początkowy:")
    print(stan.tekst())

    print("--- Instalacja app==2.0 do istniejącego stanu ---\n")
    zadania = wczytaj_zadania(katalog_przykladow / "install_app.txt")
    wynik = baza.instaluj(zadania, stan)
    _pokaz_i_zapisz(stan, wynik, katalog_wynikow / "example_install.txt")

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

    print("--- Aktualizacja wszystkich pakietów (zadanie 8.1) ---\n")
    wynik_update = baza.aktualizuj(None, stan)
    _pokaz_i_zapisz(stan, wynik_update, katalog_wynikow / "example_update.txt")

    if "a" in repo.packages and "b" in repo.packages:
        print("--- Konflikt aktualizacji i front Pareto dla a i b (zadanie 8.2) ---\n")
        stan_ab = Stan({"a": (1,), "b": (1,)}, {"a", "b"})
        analiza_ab = baza.analizuj_aktualizacje(None, stan_ab)
        print(
            "Najnowsze osiągalne osobno:",
            ", ".join(f"{p} {formatuj_wersje(w)}" for p, w in analiza_ab["osiagalne"].items()),
        )
        print("Przyczyna konfliktu (unsat core):")
        for etykieta in analiza_ab["wyjasnienie"]:
            print(f"- {etykieta}")
        print(
            "Front Pareto:",
            ", ".join(formatuj_punkt_pareto(p) for p in analiza_ab["front_pareto"]),
        )
        analiza_a = baza.analizuj_aktualizacje(["a"], stan_ab)
        print("Aktualizacja samego a:", ", ".join(stan_ab.plan(analiza_a["wynik"])))

    wyniki = uruchom(katalog_repozytoriow, ziarno=2026, kroki=12)

    print("\n--- Wyjaśnienie sprzeczności przykładowych żądań ---\n")

    for etykieta in wyniki["wyjasnienie_przykladu"]:
        print(f"- {etykieta}")

    plik_danych_6 = katalog_wynikow / "punkty6.json"
    zapisz_wyniki(wyniki, plik_danych_6)

    plik_danych_8 = katalog_wynikow / "punkty8.json"
    zapisz_wyniki(wyniki, plik_danych_8)

    print(f"\nDane: {plik_danych_8}")
    print(f"Raport: {plik_danych_8.with_suffix('.md')}\n")


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