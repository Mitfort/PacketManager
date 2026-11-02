"""Interfejs poleceń: python -m src.manager --help."""
import argparse
from pathlib import Path
from src.bazawiedzy import BazaWiedzy
from src.parser import Repozytorium, formatuj_wersje, wczytaj_zadania
from src.stan import Stan
from src.wyjasnienia import wyjasnij


def formatuj_punkt_pareto(punkt: dict) -> str:
    elementy = [f"{pakiet} {formatuj_wersje(wersja)}" for pakiet, wersja in punkt.items()]
    return "{" + ", ".join(elementy) + "}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Manager pakietów (zadania na 8 punktów)")
    parser.add_argument("operacja", choices=["install", "remove", "update", "explain"])
    parser.add_argument(
        "zadania",
        nargs="?",
        help="plik żądań lub nazw pakietów (opcjonalny dla update - brak oznacza wszystkie)",
    )
    parser.add_argument("--repo", required=True, help="repozytorium JSON")
    parser.add_argument("--state", help="plik istniejącego stanu; po sukcesie zostaje zapisany")
    parser.add_argument("--output", help="zapis stanu do osobnego pliku")
    parser.add_argument("--autoremove", action="store_true")

    args = parser.parse_args(argv)

    if args.operacja != "update" and args.zadania is None:
        parser.error(f"Operacja {args.operacja} wymaga podania pliku żądań")

    if args.autoremove and args.operacja != "remove":
        parser.error("--autoremove dotyczy tylko remove")

    try:
        repo = Repozytorium(Path(args.repo).read_text(encoding="utf-8-sig"))
        baza = BazaWiedzy(repo)

        zadania = []
        if args.zadania is not None:
            tylko_nazwy = args.operacja in ("remove", "update")
            zadania = wczytaj_zadania(args.zadania, tylko_nazwy=tylko_nazwy, pypi=repo.czy_pypi)

        if args.operacja == "explain":
            rdzen = wyjasnij(baza, zadania)
            print("Minimalny sprzeczny podzbiór:" if rdzen else "Żądania można zainstalować.")

            for etykieta in rdzen:
                print(f"- {etykieta}")

            return 1 if rdzen else 0

        stan = Stan.wczytaj(args.state, pypi=repo.czy_pypi) if args.state else Stan()

        if args.operacja == "install":
            wynik = baza.instaluj(zadania, stan)
        elif args.operacja == "remove":
            nazwy = [zadanie.alternatives[0]["package"] for zadanie in zadania]
            wynik = baza.usun(nazwy, stan, autoremove=args.autoremove)
        else:
            nazwy = [zadanie.alternatives[0]["package"] for zadanie in zadania] if zadania else None
            analiza = baza.analizuj_aktualizacje(nazwy, stan)
            wynik = analiza["wynik"]

            if analiza["konflikt"]:
                osiagalne_str = ", ".join(
                    f"{p} {formatuj_wersje(w)}" for p, w in analiza["osiagalne"].items()
                )
                print(f"Wykryto konflikt aktualizacji! Najnowsze wersje osiągalne osobno: {osiagalne_str}")
                print("Przyczyna konfliktu (unsat core):")
                for etykieta in analiza["wyjasnienie"]:
                    print(f"- {etykieta}")
                front_str = ", ".join(formatuj_punkt_pareto(p) for p in analiza["front_pareto"])
                print(f"Front Pareto: {front_str}")

        if wynik is None:
            print("Brak rozwiązania. Stan nie został zapisany.")

            if zadania:
                for etykieta in wyjasnij(baza, zadania):
                    print(f"- {etykieta}")

            return 1

        plan = stan.plan(wynik)
        print("Plan zmian:")

        for zmiana in plan:
            print(f"- {zmiana}")

        if not plan:
            print("Brak zmian wersji pakietów.")

        print(f"Pakiety: {len(wynik.pakiety)}, ręczne: {len(wynik.reczne)}")
        sciezka = args.output or args.state

        if sciezka:
            wynik.zapisz(sciezka)
        else:
            print(wynik.tekst(), end="")

        return 0

    except (OSError, ValueError, RuntimeError) as blad:
        print(f"Błąd: {blad}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())