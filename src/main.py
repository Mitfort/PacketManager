import sys
import time
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
        print(f"Błąd: Nie znaleziono pliku żądań '{sciezka_do_pliku}'")
        sys.exit(1)
    return zadania

def main():
    if len(sys.argv) < 3:
        print("Użycie: python main.py <ścieżka_do_repo.json> <ścieżka_do_zadań.txt>")
        sys.exit(1)

    plik_repo = sys.argv[1]
    plik_zadan = sys.argv[2]

    try:
        with open(plik_repo, 'r', encoding='utf-8') as f:
            zawartosc_json = f.read()
    except FileNotFoundError:
        print(f"Błąd: Nie znaleziono pliku repozytorium '{plik_repo}'")
        sys.exit(1)

    zadania = wczytaj_zadania(plik_zadan)

    print(f"=== Uruchamianie menedżera pakietów ===")
    print(f"Repozytorium: {plik_repo}")
    print(f"Plik żądań:  {plik_zadan}\n")

    t0 = time.time()
    try:
        repo = Repozytorium(zawartosc_json)
        baza_wiedzy = BazaWiedzy(repo)
    except Exception as e:
        print(f"Błąd walidacji / tworzenia bazy wiedzy:\n{e}")
        sys.exit(1)
    t1 = time.time()
    czas_budowy = t1 - t0

    t2 = time.time()
    wynik = baza_wiedzy.instaluj(zadania)
    t3 = time.time()
    czas_solvera = t3 - t2
    print(f"Czas budowy bazy wiedzy: {czas_budowy:.4f} s")
    print(f"Czas rozwiązywania (Z3): {czas_solvera:.4f} s\n")

    if isinstance(wynik, list):
        print(" Wynik instalacji:")
        for p in wynik:
            print(f"  - {p}")
        print(f"\nLiczba zainstalowanych pakietów: {len(wynik)}\n")
        stan_do_weryfikacji = {}
        for wpis in wynik:
            nazwa, wersja_str = wpis.split()
            krotka_wersji = tuple(int(x) for x in wersja_str.split('.'))
            stan_do_weryfikacji[nazwa] = krotka_wersji

        print("--- Uruchamianie niezależnego weryfikatora ---")
        weryfikujStan(repo, stan_do_weryfikacji)
    else:
        print(f"Wynik: {wynik}")

if __name__ == "__main__":
    main()