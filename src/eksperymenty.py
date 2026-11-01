"""Odtwarzalne eksperymenty z zadań 4.5, 6.3 i 6.4."""
import argparse
import contextlib
import io
import json
import platform
import random
from pathlib import Path
from time import perf_counter

import z3

from src.bazawiedzy import BazaWiedzy, weryfikujStan
from src.parser import Repozytorium, Requirement, wczytaj_zadania
from src.stan import Stan
from src.wyjasnienia import wyjasnij

def uruchom(katalog: Path, *, ziarno: int = 2026, kroki: int = 12) -> dict:
    """Zmierz instalacje oraz wykonaj losowe operacje od pustego stanu.

    Raises:
        ValueError: Gdy scenariusz ma mniej niż dziesięć operacji.
        RuntimeError: Gdy niezależna weryfikacja wykryje niespójny wynik.
    """
    if kroki < 10:
        raise ValueError("Scenariusz musi zawierać co najmniej 10 operacji")

    instalacje = _zmierz_instalacje(katalog)
    baza, czas_budowy, ostrzezenia = _wczytaj(katalog / "repo_200.json")
    scenariusz = _wykonaj_scenariusz(baza, ziarno=ziarno, kroki=kroki)

    katalog_przykladu = katalog.parent.parent / "examples"
    przyklad, _, _ = _wczytaj(katalog_przykladu / "repo_example.json")
    zadania = wczytaj_zadania(katalog_przykladu / "requests_example.txt")

    wyniki = {
        "grupa": katalog.name,
        "ziarno": ziarno,
        "python": platform.python_version(),
        "z3": z3.get_version_string(),
        "instalacje": instalacje,
        "scenariusz": scenariusz,
        "repo_200": {
            "wersje": len(baza.vars),
            "aksjomaty": len(baza.aksjomaty),
            "budowa_s": czas_budowy,
            "ostrzezenia": ostrzezenia,
        },
        "wyjasnienie_przykladu": wyjasnij(przyklad, zadania),
    }

    if not any(pomiar["wyjasnienie"] for pomiar in instalacje):
        wyniki["wyjasnienia_dodatkowe"] = _dodatkowe_wyjasnienia(baza)

    return wyniki


def _zmierz_instalacje(katalog: Path) -> list[dict]:
    """Mierzy instalacje do pustego stanu dla pięciu rozmiarów repozytorium."""
    pomiary = []

    print("\n=== Instalacje do pustego środowiska ===")

    for rozmiar in (10, 30, 100, 300, 1000):
        baza, czas_budowy, ostrzezenia = _wczytaj(katalog / f"repo_{rozmiar}.json")
        zadania = wczytaj_zadania(katalog / f"requests_{rozmiar}.txt")

        print(f"\nN={rozmiar}, żądania: {', '.join(zadanie.tekst for zadanie in zadania)}")

        start = perf_counter()
        stan = baza.instaluj(zadania)
        czas = perf_counter() - start

        rdzen = []
        if stan is None:
            rdzen = wyjasnij(baza, zadania)

        # Każdy zwrócony stan jest już sprawdzany przez BazaWiedzy.instaluj.
        rekord = {
            "N": rozmiar,
            "wersje": len(baza.vars),
            "aksjomaty": len(baza.aksjomaty),
            "zadania": [zadanie.tekst for zadanie in zadania],
            "budowa_s": czas_budowy,
            "rozwiazanie_s": czas,
            "ostrzezenia": ostrzezenia,
            "pakiety": len(stan.pakiety) if stan is not None else None,
            "przestarzalosc": _wiek(baza.repo, stan) if stan is not None else None,
            "weryfikacja": "OK" if stan is not None else "nie dotyczy (UNSAT)",
            "wyjasnienie": rdzen,
        }
        pomiary.append(rekord)

        wynik = "UNSAT" if stan is None else f"{len(stan.pakiety)} pakietów"
        print(f"Wynik: {wynik}; czas {czas:.4f} s", flush=True)

        for etykieta in rdzen:
            print(f"- {etykieta}")

    return pomiary


def _wykonaj_scenariusz(baza: BazaWiedzy, *, ziarno: int, kroki: int) -> list[dict]:
    """Wykonuje losowe instalacje i usunięcia, zachowując każdy stan pośredni."""
    rng = random.Random(ziarno)
    rodzaje = (["install", "install", "remove", "autoremove"] * ((kroki + 3) // 4))[:kroki]
    rng.shuffle(rodzaje)

    stan = Stan()
    przebieg = []

    print(f"\n=== Scenariusz losowy: {kroki} operacji, ziarno {ziarno} ===")

    for numer, rodzaj in enumerate(rodzaje, 1):
        if not stan.pakiety:
            rodzaj = "install"

        if rodzaj == "install":
            kandydaci = sorted(baza.repo.packages)
        else:
            kandydaci = sorted(stan.pakiety)

        nazwa = rng.choice(kandydaci)

        print(f"\n{numer}. {rodzaj} {nazwa}")

        start = perf_counter()

        if rodzaj == "install":
            zadania = [Requirement(nazwa, f"operacja {numer}")]
            nowy = baza.instaluj(zadania, stan)
        else:
            nowy = baza.usun([nazwa], stan, autoremove=rodzaj == "autoremove")

        czas = perf_counter() - start

        if nowy is not None:
            zmiany = stan.plan(nowy)
            stan = nowy
            wynik = "OK"
        else:
            zmiany = []
            wynik = "UNSAT (stan zachowany)"

            # Nieudana operacja zachowuje stan, który również podlega weryfikacji.
            if not weryfikujStan(baza.repo, stan.pakiety):
                raise RuntimeError(f"Błąd weryfikacji po operacji {numer}")

        zapis_stanu = {}
        for pakiet, wersja in sorted(stan.pakiety.items()):
            zapis_stanu[pakiet] = {
                "wersja": list(wersja),
                "manual": pakiet in stan.reczne,
            }

        rekord = {
            "krok": numer,
            "operacja": rodzaj,
            "zadanie": nazwa,
            "wynik": wynik,
            "liczba_zmian": len(zmiany),
            "zmiany": zmiany,
            "pakiety": len(stan.pakiety),
            "reczne": len(stan.reczne),
            "czas_s": czas,
            "weryfikacja": "OK",
            "stan": zapis_stanu,
        }
        przebieg.append(rekord)

        print(
            f"Wynik: {wynik}; zmiany {len(zmiany)}; "
            f"pakiety {len(stan.pakiety)} (ręczne {len(stan.reczne)}); czas {czas:.4f} s",
            flush=True,
        )

        for zmiana in zmiany:
            print(f"- {zmiana}")

    return przebieg


def _dodatkowe_wyjasnienia(baza: BazaWiedzy) -> list[dict]:
    """Znajduje dwa nieinstalowalne żądania, jeśli instalacje grupy były spełnialne."""
    wyjasnienia = []

    for nazwa, pakiet in baza.repo.packages.items():
        for wersja in pakiet.versions:
            tekst = nazwa + "==" + ".".join(map(str, wersja))
            rdzen = wyjasnij(baza, [Requirement(tekst, "przykład grupy")])

            if rdzen:
                wyjasnienia.append({"zadanie": tekst, "rdzen": rdzen})
                break

        if len(wyjasnienia) == 2:
            break

    return wyjasnienia


def _wczytaj(sciezka: Path) -> tuple[BazaWiedzy, float, int]:
    """Mierz odczyt, parsowanie i budowę; ogranicz szum ostrzeżeń."""
    start = perf_counter()

    with contextlib.redirect_stdout(io.StringIO()) as komunikaty:
        baza = BazaWiedzy(Repozytorium(sciezka.read_text(encoding="utf-8")))

    return baza, perf_counter() - start, len(komunikaty.getvalue().splitlines())


def _wiek(repo: Repozytorium, stan: Stan) -> int:
    """Zsumuj pozycje zainstalowanych wersji od najnowszej."""
    wiek = 0

    for nazwa, wersja in stan.pakiety.items():
        od_najnowszej = sorted(repo.packages[nazwa].versions, reverse=True)
        wiek += od_najnowszej.index(wersja)

    return wiek


def raport(wyniki: dict) -> str:
    """Przygotuj raport tekstowy na podstawie rzeczywistych pomiarów."""
    linie = [f"""# Raport - manager pakietów, próg 6 punktów

Grupa **{wyniki['grupa']}**, ziarno **{wyniki['ziarno']}**.
Python {wyniki['python']}, Z3 {wyniki['z3']}.
Czasy zmierzono zegarem perf_counter, w sekundach.

## Kodowanie i kryteria

Zmienna x[p,v] oznacza instalację wersji v pakietu p.
A1: AtMost(x[p,v], 1).
A2: x[p,v] ⇒ alternatywa pasujących wersji zależności.
A3: x[p,v] ⇒ ¬x[q,w] dla każdej konfliktującej wersji.

Przykłady: app==2 ⇒ lib==2; lib==2 ⇒ util==2;
tool==1.1 ⇒ (lib==1 ∨ lib==1.5);
tool==1.1 ⇒ (json-fast==1 ∨ json-slow==1); legacy==1 ⇒ ¬util==2.
Wszystkie aksjomaty mają czytelne etykiety.
Plik examples/repo_example.json odtworzono z fragmentu i wyników podanych w PDF;
pełnego oryginalnego pliku przykładowego nie było w projekcie.

Instalacja minimalizuje kolejno usunięcia, zmiany wersji zachowanych pakietów,
przestarzałość nowych pakietów żądanych, liczbę nowych pakietów
i przestarzałość pozostałych nowych pakietów.
W pustym środowisku są to kryteria 4.3.
Usuwanie minimalizuje utratę ręcznych pakietów spoza żądania, zmiany wersji,
nowe pakiety i usunięcia; autoremove zamienia ostatni cel na liczbę wszystkich pakietów.
Każdy wynik przechodzi weryfikację bez solvera, łącznie ze spełnieniem żądań.

## Instalacje do pustego stanu (4.5)

Czas budowy obejmuje odczyt pliku, walidację i utworzenie aksjomatów.
Czas rozwiązania obejmuje optymalizację i automatyczną weryfikację wyniku.
Wyjaśnienia UNSAT mierzone są poza tym czasem.
"""]

    for pomiar in wyniki["instalacje"]:
        if pomiar["pakiety"] is None:
            wynik = "brak rozwiązania"
        else:
            wynik = f"{pomiar['pakiety']} pakietów, przestarzałość {pomiar['przestarzalosc']}"

        linie.append(
            f"- N={pomiar['N']}: {pomiar['wersje']} wersji, {pomiar['aksjomaty']} aksjomatów; "
            f"żądania: {', '.join(pomiar['zadania'])}; wynik: {wynik}; "
            f"budowa {pomiar['budowa_s']:.6f} s, rozwiązanie {pomiar['rozwiazanie_s']:.6f} s; "
            f"weryfikacja: {pomiar['weryfikacja']}; ostrzeżenia: {pomiar['ostrzezenia']}."
        )

    linie.append("""
Liczba wersji i zależności wpływa na czas budowy; samo N nie opisuje pełnego rozmiaru formuły.
Czas rozwiązania zależy także od konfliktów i ograniczeń żądań,
więc nie musi rosnąć monotonicznie z N.
Pomiary są pojedynczymi uruchomieniami lokalnymi, a nie średnią wielu prób.

## Minimalne wyjaśnienia (6.3)

Minimalność oznacza minimalność przez zawieranie:
po usunięciu dowolnego elementu podzbiór jest spełnialny.
Nie oznacza to najmniejszej możliwej liczby elementów.
Rdzeń Z3 jest dodatkowo redukowany przez próby usuwania elementów.

Żądania z pliku examples/requests_example.txt:
""")
    linie.extend(f"- {etykieta}" for etykieta in wyniki["wyjasnienie_przykladu"])

    for pomiar in wyniki["instalacje"]:
        if pomiar["wyjasnienie"]:
            linie.append(f"\nRepozytorium N={pomiar['N']}, żądania {', '.join(pomiar['zadania'])}:\n")
            linie.extend(f"- {etykieta}" for etykieta in pomiar["wyjasnienie"])

    for przyklad in wyniki.get("wyjasnienia_dodatkowe", []):
        linie.append(f"\nSkonstruowane żądanie dla repo_200: {przyklad['zadanie']}:\n")
        linie.extend(f"- {etykieta}" for etykieta in przyklad["rdzen"])

    repo = wyniki["repo_200"]
    linie.append(f"""
## Scenariusz losowy (6.4)

Repozytorium repo_200.json: {repo['wersje']} wersji, {repo['aksjomaty']} aksjomatów;
budowa {repo['budowa_s']:.6f} s. Początkowy stan jest pusty.
Generator random.Random najpierw tasuje listę rodzajów operacji,
potem wybiera pakiet z posortowanych nazw;
usuwanie preferuje aktualnie zainstalowane pakiety.
W pustym stanie rodzaj operacji zmieniany jest na instalację, aby uniknąć pustych usunięć.
Żądania, plany i wszystkie stany pośrednie zapisano także w JSON.
""")

    for krok in wyniki["scenariusz"]:
        linie.append(
            f"{krok['krok']}. {krok['operacja']} {krok['zadanie']}: {krok['wynik']}; "
            f"zmiany {krok['liczba_zmian']}, pakiety {krok['pakiety']} (ręczne {krok['reczne']}), "
            f"czas {krok['czas_s']:.6f} s, weryfikacja {krok['weryfikacja']}."
        )

    linie.append("""
Liczba zmian liczy instalacje, usunięcia i zmiany wersji.
Oznaczenie już zainstalowanego pakietu jako ręcznego nie zmienia jego wersji i nie zwiększa tej liczby.
Nieudana operacja zachowuje poprzedni stan.
W przypadku równorzędnych rozwiązań optymalnych Z3 może wybrać inny stan;
dokładny przebieg tego uruchomienia jest zapisany w JSON.
""")

    return "\n".join(linie)


def zapisz_wyniki(wyniki: dict, sciezka: Path) -> None:
    """Zapisuje dane pomiarów oraz raport w tym samym katalogu.

    Raises:
        OSError: Plików nie można utworzyć lub zapisać.
    """
    sciezka.parent.mkdir(parents=True, exist_ok=True)

    dane = json.dumps(wyniki, ensure_ascii=False, indent=2) + "\n"
    sciezka.write_text(dane, encoding="utf-8")
    sciezka.with_suffix(".md").write_text(raport(wyniki), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--group", type=int, default=5)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--steps", type=int, default=12)
    parser.add_argument("--output", type=Path, default=Path("results/punkty6.json"))

    args = parser.parse_args()
    katalog = Path(__file__).resolve().parents[1] / "repos" / f"k{args.group:02d}"

    wyniki = uruchom(katalog, ziarno=args.seed, kroki=args.steps)
    zapisz_wyniki(wyniki, args.output)


if __name__ == "__main__":
    main()
