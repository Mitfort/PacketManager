import sys
import time
from pathlib import Path
from parser import Repozytorium, Requirement
from bazawiedzy import BazaWiedzy, weryfikujStan

def wczytaj_zadania(sciezka_do_pliku):
    zadania = []
    try:
        with open(sciezka_do_pliku, 'r', encoding='utf-8') as f:
            for linia in f:
                linia = linia.strip()
                if not linia or linia.startswith('#'):
                    continue
                zadania.append(linia)
    except FileNotFoundError:
        return None
    return zadania

def uruchom_test_dla_rozmiaru(katalog_k05, rozmiar):
    sciezka_repo = katalog_k05 / f"repo_{rozmiar}.json"
    
    sciezka_zadan = katalog_k05 / f"requests_{rozmiar}.txt"
    if not sciezka_zadan.exists():
        sciezka_zadan = katalog_k05 / f"requests_{rozmiar}.json"

    if not sciezka_repo.exists() or not sciezka_zadan.exists():
        print(f"| {rozmiar:<10} | Pominięto (brak pliku repo_{rozmiar}.json lub requests_{rozmiar}) |")
        return
    try:
        with open(sciezka_repo, 'r', encoding='utf-8') as f:
            zawartosc_json = f.read()
    except Exception as e:
        print(f"| {rozmiar:<10} | Błąd odczytu repo: {e} |")
        return

    zadania = wczytaj_zadania(sciezka_zadan)
    if zadania is None:
        print(f"| {rozmiar:<10} | Błąd odczytu żądań |")
        return

    t0 = time.time()
    try:
        repo = Repozytorium(zawartosc_json)
        baza_wiedzy = BazaWiedzy(repo)
    except Exception as e:
        print(f"| {rozmiar:<10} | Błąd Bazy Wiedzy: {e} |")
        return
    t1 = time.time()
    czas_budowy = t1 - t0

    t2 = time.time()
    wynik = baza_wiedzy.instaluj(zadania)
    t3 = time.time()
    czas_solvera = t3 - t2

    if isinstance(wynik, list):
        status = f"OK ({len(wynik)} pakietów)"
    else:
        status = str(wynik)

    print(f"| N={rozmiar:<8} | {czas_budowy:12.4f} s | {czas_solvera:13.4f} s | {status:<20} |")

def main():
    sciezka_src = Path(__file__).resolve().parent
    katalog_k05 = sciezka_src.parent / "repos" / "k05"

    rozmiary = [10, 30, 100, 200, 300, 1000]

    print("=== PĘTLA TESTOWA W K05 (N = 10, 30, 100, 200, 300, 1000) ===")
    print(f"Katalog: {katalog_k05}\n")
    print(f"| {'Rozmiar':<10} | {'Czas budowy':<14} | {'Czas Z3':<15} | {'Wynik':<20} |")
    print("-" * 70)

    for r in rozmiary:
        uruchom_test_dla_rozmiaru(katalog_k05, r)

    print("-" * 70)

if __name__ == "__main__":
    main()