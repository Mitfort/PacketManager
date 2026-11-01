"""Interfejs poleceń: python -m src.manager --help."""
import argparse
from pathlib import Path
from src.bazawiedzy import BazaWiedzy
from src.parser import Repozytorium, wczytaj_zadania
from src.stan import Stan
from src.wyjasnienia import wyjasnij

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Manager pakietów (zadania na 6 punktów)")
    parser.add_argument("operacja", choices=["install", "remove", "explain"])
    parser.add_argument("zadania", help="plik żądań lub nazw pakietów do usunięcia")
    parser.add_argument("--repo", required=True, help="repozytorium JSON")
    parser.add_argument("--state", help="plik istniejącego stanu; po sukcesie zostaje zapisany")
    parser.add_argument("--output", help="zapis stanu do osobnego pliku")
    parser.add_argument("--autoremove", action="store_true")

    args = parser.parse_args(argv)

    if args.autoremove and args.operacja != "remove":
        parser.error("--autoremove dotyczy tylko remove")

    try:
        repo = Repozytorium(Path(args.repo).read_text(encoding="utf-8-sig"))
        baza = BazaWiedzy(repo)
        zadania = wczytaj_zadania(args.zadania, tylko_nazwy=args.operacja == "remove")

        if args.operacja == "explain":
            rdzen = wyjasnij(baza, zadania)
            print("Minimalny sprzeczny podzbiór:" if rdzen else "Żądania można zainstalować.")

            for etykieta in rdzen:
                print(f"- {etykieta}")

            return 1 if rdzen else 0

        stan = Stan.wczytaj(args.state) if args.state else Stan()

        if args.operacja == "install":
            wynik = baza.instaluj(zadania, stan)
        else:
            nazwy = [zadanie.alternatives[0]["package"] for zadanie in zadania]
            wynik = baza.usun(nazwy, stan, autoremove=args.autoremove)

        if wynik is None:
            print("Brak rozwiązania. Stan nie został zapisany.")

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
