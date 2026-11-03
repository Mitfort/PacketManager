# Manager pakietów — zadania na 6 punktów

Cały przykładowy przebieg uruchamia funkcja `main`:

```powershell
python -m src.main
```

Polecenie wykonaj z katalogu `PacketManager`, w środowisku z zainstalowanymi
zależnościami. Program kolejno:

1. Wczytuje i pokazuje przykładowy stan środowiska.
2. Instaluje `app==2.0`, pokazuje plan zmian i zapisuje nowy stan.
3. Pokazuje usunięcie `lib` oraz usunięcie `tool` z `autoremove` i bez niego.
   Każdy wariant zaczyna od tego samego stanu początkowego.
4. Wykonuje pomiary na repozytoriach grupy `k05` dla N=10,30,100,300,1000
   oraz 12 losowych operacji na `repo_200.json`, z ziarnem `2026`.
5. Pokazuje minimalne wyjaśnienia sprzecznych żądań i zapisuje raport.

Plany i stany są widoczne w konsoli. W katalogu `results` powstają:

- `example_install.txt` — stan po instalacji;
- `example_remove_lib.txt`, `example_remove_tool.txt`, `example_autoremove.txt`
  — wyniki trzech wariantów usuwania;
- `punkty6.json` — pomiary, plany i wszystkie stany scenariusza losowego;
- `punkty6.md` — raport z wynikami i komentarzem.

Każdy wynik solvera sprawdza procedura weryfikacji bez użycia solvera.
Instalacja i usuwanie korzystają z jednej klasy `BazaWiedzy` oraz kryteriów
leksykograficznych z zadań 6.1 i 6.2.

## Przygotowanie środowiska

Wymagany jest Python 3.11 lub nowszy.

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m src.main
```

Dalsze polecenia zakładają użycie Pythona z tego środowiska. Na Linux/macOS
zamiast `.venv\Scripts\python.exe` użyj `.venv/bin/python`.

## Pojedyncze operacje

Interfejs poleceń pozwala uruchomić wybraną operację osobno:

```powershell
.venv\Scripts\python.exe -m src.manager --help

.venv\Scripts\python.exe -m src.manager install examples/install_app.txt --repo examples/repo_example.json --state state_example.txt --output results/installed.txt

.venv\Scripts\python.exe -m src.manager remove examples/remove_tool.txt --repo examples/repo_example.json --state state_example.txt --output results/removed.txt --autoremove

.venv\Scripts\python.exe -m src.manager explain examples/requests_example.txt --repo examples/repo_example.json
```

Żądania pochodzą wyłącznie z pliku tekstowego, po jednym w linii. Puste linie
i komentarze po `#` są pomijane. Błąd żądania wskazuje numer linii.
Plik dla `remove` zawiera same nazwy pakietów; pominięcie `--autoremove`
zachowuje zbędne zależności zgodnie z kryteriami zadania.

Brak `--state` oznacza pusty stan. `--output` wybiera osobny plik wyniku.
Bez tej opcji udana operacja zapisuje stan do pliku wskazanego przez
`--state`; bez obu opcji wypisuje go w konsoli. Nieudana operacja zachowuje
dotychczasowy plik stanu.

W stanie każda linia ma postać `NAZWA WERSJA` lub `NAZWA WERSJA manual`.
Żądane pakiety stają się ręczne, a zachowane pakiety ręczne pozostają ręczne.
Plan rozróżnia instalację, usunięcie, podniesienie i obniżenie wersji.

Wyjaśnienia są minimalne względem zawierania: usunięcie dowolnego elementu
rdzenia usuwa sprzeczność. Nie oznacza to najmniejszego możliwego rdzenia.

Kody zakończenia CLI: `0` — sukces, `1` — brak rozwiązania lub wykryty
sprzeczny rdzeń, `2` — błąd danych albo wykonania.

## Inna grupa lub scenariusz

Domyślna grupa `k05` odpowiada katalogowi używanemu w pierwotnym programie.
Eksperymenty można uruchomić osobno, zmieniając ich parametry:

```powershell
.venv\Scripts\python.exe -m src.eksperymenty --group 5 --seed 2026 --steps 12 --output results/punkty6.json
```

Do odtworzenia losowania użyj tej samej grupy, ziarna i liczby kroków.
Usuwanie w pustym stanie jest zastępowane instalacją. Równorzędne optima
mogą dawać różne stany w innej wersji Z3; wersja środowiska i dokładny
przebieg uruchomienia są zapisane w JSON.

`examples/repo_example.json` odtworzono na podstawie fragmentu i wyników
podanych w PDF, ponieważ pełny oryginalny plik nie był dołączony do projektu.
`state_example.txt` pochodzi z projektu.

## Testy

```powershell
.venv\Scripts\python.exe -m pytest -q --tb=short
```

Testy sprawdzają formaty danych, odczyt i zapis stanu, operacje, CLI, cały
przebieg z `main`, minimalność wyjaśnień oraz optymalność wyników na małych
repozytoriach przez porównanie z przeszukiwaniem wyczerpującym.
