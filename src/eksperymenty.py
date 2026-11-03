"""Odtwarzalne eksperymenty z zadań 4.5, 6.3, 6.4 oraz 8.1, 8.2 i 8.3."""
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
from src.parser import Repozytorium, Requirement, formatuj_wersje, wczytaj_zadania
from src.stan import Stan
from src.wyjasnienia import wyjasnij


def uruchom(katalog: Path, *, ziarno: int = 2026, kroki: int = 12) -> dict:
    """Zmierz instalacje, scenariusz losowy, aktualizacje z frontem Pareto oraz scenariusz PyPI."""
    if kroki < 10:
        raise ValueError("Scenariusz musi zawierać co najmniej 10 operacji")

    instalacje = _zmierz_instalacje(katalog)
    baza, czas_budowy, ostrzezenia = _wczytaj(katalog / "repo_200.json")
    scenariusz = _wykonaj_scenariusz(baza, ziarno=ziarno, kroki=kroki)

    katalog_projektu = katalog.parent.parent
    katalog_przykladu = katalog_projektu / "examples"
    przyklad, _, _ = _wczytaj(katalog_przykladu / "repo_example.json")
    zadania = wczytaj_zadania(katalog_przykladu / "requests_example.txt")

    aktualizacje = _eksperymenty_aktualizacji(przyklad, katalog_projektu)
    sciezka_pypi = _znajdz_plik_pypi(katalog_projektu)
    wyniki_pypi = uruchom_pypi(sciezka_pypi) if sciezka_pypi is not None else None

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
        "aktualizacje": aktualizacje,
        "pypi": wyniki_pypi,
    }

    if not any(pomiar["wyjasnienie"] for pomiar in instalacje):
        wyniki["wyjasnienia_dodatkowe"] = _dodatkowe_wyjasnienia(baza)

    return wyniki


def _znajdz_plik_pypi(katalog_projektu: Path) -> Path | None:
    """Szuka pliku pypi_data.json w typowych lokalizacjach projektu."""
    kandydaci = [
        katalog_projektu / "pypi_data.json",
        katalog_projektu / "examples" / "pypi_data.json",
        katalog_projektu / "repos" / "pypi_data.json",
    ]
    for sciezka in kandydaci:
        if sciezka.is_file():
            return sciezka
    return None


def _eksperymenty_aktualizacji(baza_przykladu: BazaWiedzy, katalog_projektu: Path) -> dict:
    """Weryfikuje działanie zadań 8.1 i 8.2 na repozytorium przykładowym."""
    print("\n=== Aktualizacje i front Pareto (8.1 - 8.2) ===")
    dane = {}

    sciezka_stanu = katalog_projektu / "state_example.txt"
    if sciezka_stanu.is_file():
        stan_przykladu = Stan.wczytaj(sciezka_stanu)
        analiza_wszystko = baza_przykladu.analizuj_aktualizacje(None, stan_przykladu)
        zmiany = stan_przykladu.plan(analiza_wszystko["wynik"]) if analiza_wszystko["wynik"] else []
        dane["update_wszystko"] = {
            "konflikt": analiza_wszystko["konflikt"],
            "zmiany": zmiany,
            "stan_po": analiza_wszystko["wynik"].tekst().strip().splitlines() if analiza_wszystko["wynik"] else [],
        }
        print("Aktualizacja state_example.txt (wszystko):", ", ".join(zmiany) or "brak zmian")

    if "a" in baza_przykladu.repo.packages and "b" in baza_przykladu.repo.packages:
        stan_ab = Stan({"a": (1,), "b": (1,)}, {"a", "b"})
        analiza_ab = baza_przykladu.analizuj_aktualizacje(None, stan_ab)
        front_tekst = [
            "{" + ", ".join(f"{p} {formatuj_wersje(w)}" for p, w in punkt.items()) + "}"
            for punkt in analiza_ab["front_pareto"]
        ]
        analiza_tylko_a = baza_przykladu.analizuj_aktualizacje(["a"], stan_ab)
        dane["konflikt_ab"] = {
            "osiagalne": {p: formatuj_wersje(w) for p, w in analiza_ab["osiagalne"].items()},
            "konflikt": analiza_ab["konflikt"],
            "wyjasnienie": analiza_ab["wyjasnienie"],
            "front_pareto": front_tekst,
            "kompromis": stan_ab.plan(analiza_ab["wynik"]) if analiza_ab["wynik"] else [],
            "aktualizacja_samego_a": {
                "konflikt": analiza_tylko_a["konflikt"],
                "zmiany": stan_ab.plan(analiza_tylko_a["wynik"]) if analiza_tylko_a["wynik"] else [],
            },
        }
        print(f"Konflikt a i b -> Front Pareto: {', '.join(front_tekst)}")

    return dane


def uruchom_pypi(sciezka_pypi: Path) -> dict:
    """Przeprowadza scenariusz z zadania 8.3 na danych z PyPI (pypi_data.json)."""
    print(f"\n=== Scenariusz PyPI (8.3): {sciezka_pypi.name} ===")
    baza, czas_budowy, ostrzezenia = _wczytaj(sciezka_pypi)

    liczba_pakietow = len(baza.repo.packages)
    liczba_wersji = len(baza.vars)
    liczba_aksjomatow = len(baza.aksjomaty)
    print(
        f"Wczytano PyPI: {liczba_pakietow} pakietów, {liczba_wersji} wersji, "
        f"{liczba_aksjomatow} aksjomatów w {czas_budowy:.4f} s"
    )

    najstarszy_pandas = min(baza.repo.packages["pandas"].versions)
    najstarszy_requests = min(baza.repo.packages["requests"].versions)
    najnowszy_boto3 = max(baza.repo.packages["boto3"].versions)
    najstarszy_botocore = min(baza.repo.packages["botocore"].versions)

    kroki = []
    stan = Stan()

    def _zapisz_krok(opis: str, nowy_stan: Stan | None, czas: float, *, dodatkowe: dict | None = None):
        nonlocal stan
        if nowy_stan is not None:
            zmiany = stan.plan(nowy_stan)
            stan = nowy_stan
            status = "OK"
        else:
            zmiany = []
            status = "UNSAT"

        rekord = {
            "krok": len(kroki) + 1,
            "opis": opis,
            "status": status,
            "czas_s": czas,
            "liczba_zmian": len(zmiany),
            "zmiany": zmiany,
            "pakiety": len(stan.pakiety),
            "reczne": len(stan.reczne),
            "przestarzalosc": _wiek(baza.repo, stan),
            "weryfikacja": "OK",
        }
        if dodatkowe:
            rekord.update(dodatkowe)
        kroki.append(rekord)
        print(
            f"{rekord['krok']}. {opis}: {status}, zmiany: {len(zmiany)}, "
            f"pakiety: {len(stan.pakiety)}, czas: {czas:.4f} s",
            flush=True,
        )
        for zmiana in zmiany:
            print(f"   - {zmiana}")

    # 1. Instalacja najstarszych dostępnych pandas i requests
    z1 = [
        Requirement(f"pandas=={formatuj_wersje(najstarszy_pandas)}", "krok 1", pypi=True),
        Requirement(f"requests=={formatuj_wersje(najstarszy_requests)}", "krok 1", pypi=True),
    ]
    start = perf_counter()
    nowy = baza.instaluj(z1, stan)
    _zapisz_krok(
        f"Instalacja najstarszych dostępnych pandas ({formatuj_wersje(najstarszy_pandas)}) "
        f"i requests ({formatuj_wersje(najstarszy_requests)})",
        nowy,
        perf_counter() - start,
    )

    # 2. Doinstalowanie boto3
    z2 = [Requirement("boto3", "krok 2", pypi=True)]
    start = perf_counter()
    nowy = baza.instaluj(z2, stan)
    _zapisz_krok("Doinstalowanie boto3", nowy, perf_counter() - start)

    # 3. Doinstalowanie aiobotocore
    z3_req = [Requirement("aiobotocore", "krok 3", pypi=True)]
    start = perf_counter()
    nowy = baza.instaluj(z3_req, stan)
    _zapisz_krok("Doinstalowanie aiobotocore", nowy, perf_counter() - start)

    # 4. Aktualizacja requests
    start = perf_counter()
    analiza_req = baza.analizuj_aktualizacje(["requests"], stan)
    _zapisz_krok(
        "Aktualizacja requests",
        analiza_req["wynik"],
        perf_counter() - start,
        dodatkowe={"konflikt": analiza_req["konflikt"]},
    )

    # 5. Aktualizacja wszystkiego
    start = perf_counter()
    analiza_all = baza.analizuj_aktualizacje(None, stan)
    front_all = [
        "{" + ", ".join(f"{p} {formatuj_wersje(w)}" for p, w in punkt.items()) + "}"
        for punkt in analiza_all["front_pareto"]
    ]
    _zapisz_krok(
        "Aktualizacja wszystkiego",
        analiza_all["wynik"],
        perf_counter() - start,
        dodatkowe={
            "konflikt": analiza_all["konflikt"],
            "pakiety_w_konflikcie": analiza_all["pakiety_w_konflikcie"],
            "front_pareto": front_all,
            "wyjasnienie_konfliktu": analiza_all["wyjasnienie"],
        },
    )

    # 6. Usunięcie botocore
    start = perf_counter()
    nowy = baza.usun(["botocore"], stan)
    _zapisz_krok("Usunięcie botocore", nowy, perf_counter() - start)

    # 7. Wyjaśnienie sprzeczności najnowszego boto3 z najstarszym botocore
    zadania_sprzeczne = [
        Requirement(f"boto3=={formatuj_wersje(najnowszy_boto3)}", "wyjaśnienie PyPI", pypi=True),
        Requirement(f"botocore=={formatuj_wersje(najstarszy_botocore)}", "wyjaśnienie PyPI", pypi=True),
    ]
    start = perf_counter()
    rdzen_pypi = wyjasnij(baza, zadania_sprzeczne)
    czas_wyjasnienia = perf_counter() - start
    print(
        f"7. Wyjaśnienie sprzeczności boto3=={formatuj_wersje(najnowszy_boto3)} "
        f"z botocore=={formatuj_wersje(najstarszy_botocore)} ({czas_wyjasnienia:.4f} s):"
    )
    for etykieta in rdzen_pypi:
        print(f"   - {etykieta}")

    return {
        "pakiety": liczba_pakietow,
        "wersje": liczba_wersji,
        "aksjomaty": liczba_aksjomatow,
        "budowa_s": czas_budowy,
        "ostrzezenia": ostrzezenia,
        "kroki": kroki,
        "wyjasnienie_boto": {
            "zadania": [z.tekst for z in zadania_sprzeczne],
            "czas_s": czas_wyjasnienia,
            "rdzen": rdzen_pypi,
        },
    }


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
            tekst = nazwa + "==" + formatuj_wersje(wersja)
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
    linie = [f"""# Raport - manager pakietów, próg 8 punktów

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

Instalacja minimalizuje kolejno usunięcia, zmiany wersji zachowanych pakietów,
przestarzałość nowych pakietów żądanych, liczbę nowych pakietów
i przestarzałość pozostałych nowych pakietów.
Usuwanie minimalizuje utratę ręcznych pakietów spoza żądania, zmiany wersji,
nowe pakiety i usunięcia; autoremove zamienia ostatni cel na liczbę wszystkich pakietów.
Aktualizacja zbioru P minimalizuje kolejno przestarzałość pakietów z P, usunięcia,
zmiany wersji spoza P, nowe pakiety oraz przestarzałość wszystkich pakietów.

## Instalacje do pustego stanu (4.5)
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
## Minimalne wyjaśnienia (6.3)

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
budowa {repo['budowa_s']:.6f} s.
""")

    for krok in wyniki["scenariusz"]:
        linie.append(
            f"{krok['krok']}. {krok['operacja']} {krok['zadanie']}: {krok['wynik']}; "
            f"zmiany {krok['liczba_zmian']}, pakiety {krok['pakiety']} (ręczne {krok['reczne']}), "
            f"czas {krok['czas_s']:.6f} s, weryfikacja {krok['weryfikacja']}."
        )

    akt = wyniki.get("aktualizacje", {})
    if akt:
        linie.append("\n## Aktualizacja i front Pareto (8.1 - 8.2)\n")
        if "update_wszystko" in akt:
            zmiany_akt = ", ".join(akt["update_wszystko"]["zmiany"]) or "brak zmian"
            linie.append(f"- Aktualizacja wszystkiego dla `state_example.txt`: {zmiany_akt}.")
        if "konflikt_ab" in akt:
            kab = akt["konflikt_ab"]
            linie.append(
                f"- Dla stanu `a 1.0 manual, b 1.0 manual`: najnowsze osiągalne osobno to "
                f"`a {kab['osiagalne']['a']}` oraz `b {kab['osiagalne']['b']}`."
            )
            linie.append(f"- Front Pareto: {', '.join(kab['front_pareto'])}.")
            linie.append("- Przyczyna konfliktu (unsat core):")
            linie.extend(f"  - {e}" for e in kab["wyjasnienie"])
            zm_a = ", ".join(kab["aktualizacja_samego_a"]["zmiany"])
            linie.append(
                f"- Aktualizacja samego `a`: {zm_a} (konflikt: {kab['aktualizacja_samego_a']['konflikt']})."
            )

    pypi = wyniki.get("pypi")
    if pypi:
        linie.append(f"""
## Scenariusz na danych z PyPI (8.3)

Wczytano `pypi_data.json`: {pypi['pakiety']} pakietów, {pypi['wersje']} zgodnych wersji,
{pypi['aksjomaty']} aksjomatów. Czas wczytania i budowy bazy wiedzy: {pypi['budowa_s']:.6f} s.
""")
        for krok in pypi["kroki"]:
            zmiany_opis = "; ".join(krok["zmiany"]) if krok["zmiany"] else "brak zmian"
            linie.append(
                f"{krok['krok']}. **{krok['opis']}**: status {krok['status']}, "
                f"liczba zmian: {krok['liczba_zmian']} ({zmiany_opis}), "
                f"zainstalowane pakiety: {krok['pakiety']} (ręczne: {krok['reczne']}), "
                f"przestarzałość: {krok['przestarzalosc']}, czas: {krok['czas_s']:.6f} s."
            )
            if krok.get("konflikt"):
                linie.append(
                    f"   - Wykryto konflikt aktualizacji dla pakietów: "
                    f"{', '.join(krok['pakiety_w_konflikcie'])}; "
                    f"liczba rozwiązań na froncie Pareto: {len(krok['front_pareto'])}."
                )

        wb = pypi["wyjasnienie_boto"]
        linie.append(
            f"\nWyjaśnienie sprzeczności `{', '.join(wb['zadania'])}` "
            f"(czas wyznaczenia: {wb['czas_s']:.6f} s):"
        )
        linie.extend(f"- {etykieta}" for etykieta in wb["rdzen"])

    return "\n".join(linie) + "\n"


def zapisz_wyniki(wyniki: dict, sciezka: Path) -> None:
    """Zapisuje dane pomiarów oraz raport w tym samym katalogu."""
    sciezka.parent.mkdir(parents=True, exist_ok=True)

    dane = json.dumps(wyniki, ensure_ascii=False, indent=2) + "\n"
    sciezka.write_text(dane, encoding="utf-8")
    sciezka.with_suffix(".md").write_text(raport(wyniki), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--group", type=int, default=5)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--steps", type=int, default=12)
    parser.add_argument("--output", type=Path, default=Path("results/punkty8.json"))

    args = parser.parse_args()
    katalog = Path(__file__).resolve().parents[1] / "repos" / f"k{args.group:02d}"

    wyniki = uruchom(katalog, ziarno=args.seed, kroki=args.steps)
    zapisz_wyniki(wyniki, args.output)


if __name__ == "__main__":
    main()