# Raport - manager pakietów, próg 6 punktów

Grupa **k05**, ziarno **2026**.
Python 3.11.9, Z3 5.3.2.
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

- N=10: 52 wersji, 31 aksjomatów; żądania: cffi, attrs, falcon-tools; wynik: 5 pakietów, przestarzałość 2; budowa 0.004669 s, rozwiązanie 0.012168 s; weryfikacja: OK; ostrzeżenia: 4.
- N=30: 171 wersji, 99 aksjomatów; żądania: multidict, anyio, basalt-core; wynik: brak rozwiązania; budowa 0.011016 s, rozwiązanie 0.017882 s; weryfikacja: nie dotyczy (UNSAT); ostrzeżenia: 0.
- N=100: 1285 wersji, 1193 aksjomatów; żądania: multidict, markupsafe-willow, krypton-io; wynik: 6 pakietów, przestarzałość 0; budowa 0.221290 s, rozwiązanie 0.168365 s; weryfikacja: OK; ostrzeżenia: 93.
- N=300: 6705 wersji, 6106 aksjomatów; żądania: httpx, importlib-metadata-indigo, prism-api; wynik: 11 pakietów, przestarzałość 1; budowa 1.847039 s, rozwiązanie 1.077698 s; weryfikacja: OK; ostrzeżenia: 206.
- N=1000: 20896 wersji, 15524 aksjomatów; żądania: packaging, chardet-heron, juniper-core; wynik: 4 pakietów, przestarzałość 34; budowa 4.308281 s, rozwiązanie 3.542006 s; weryfikacja: OK; ostrzeżenia: 552.

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

- (A1) Pakiet 'lib' ma max 1 wersję
- (A2) app==2 wymaga lib >=2.0 (packages['app'].versions['2.0'].requires[0])
- (A2) tool==1.1 wymaga lib <2.0 (packages['tool'].versions['1.1'].requires[0])
- Żądanie: app==2.0
- Żądanie: tool

Repozytorium N=30, żądania multidict, anyio, basalt-core:

- (A1) Pakiet 'alder-tools' ma max 1 wersję
- (A2) basalt-core==1 wymaga prism-compat (packages['basalt-core'].versions['1.0'].requires[0])
- (A2) basalt-core==2 wymaga nova-io (packages['basalt-core'].versions['2.0'].requires[0])
- (A2) basalt-core==2 wymaga thistle-cli (packages['basalt-core'].versions['2.0'].requires[1])
- (A2) nova-io==1 wymaga alder-tools ==1.0 (packages['nova-io'].versions['1.0'].requires[0])
- (A2) nova-io==1.1 wymaga alder-tools<2 (packages['nova-io'].versions['1.1'].requires[0])
- (A2) thistle-cli==1 wymaga alder-tools >=2.0 (packages['thistle-cli'].versions['1.0'].requires[0])
- (A3) prism-compat==1 wyklucza basalt-core==1 (packages['prism-compat'].versions['1.0'].conflicts[0])
- Żądanie: basalt-core

## Scenariusz losowy (6.4)

Repozytorium repo_200.json: 4816 wersji, 4446 aksjomatów;
budowa 1.257299 s. Początkowy stan jest pusty.
Generator random.Random najpierw tasuje listę rodzajów operacji,
potem wybiera pakiet z posortowanych nazw;
usuwanie preferuje aktualnie zainstalowane pakiety.
W pustym stanie rodzaj operacji zmieniany jest na instalację, aby uniknąć pustych usunięć.
Żądania, plany i wszystkie stany pośrednie zapisano także w JSON.

1. install wcwidth-falcon: OK; zmiany 1, pakiety 1 (ręczne 1), czas 0.739212 s, weryfikacja OK.
2. remove wcwidth-falcon: OK; zmiany 1, pakiety 0 (ręczne 0), czas 0.326578 s, weryfikacja OK.
3. install hyperframe: OK; zmiany 1, pakiety 1 (ręczne 1), czas 0.814065 s, weryfikacja OK.
4. autoremove hyperframe: OK; zmiany 1, pakiety 0 (ręczne 0), czas 0.335271 s, weryfikacja OK.
5. install referencing-falcon: OK; zmiany 4, pakiety 4 (ręczne 1), czas 0.812413 s, weryfikacja OK.
6. install attrs-krypton: OK; zmiany 1, pakiety 5 (ręczne 2), czas 0.749133 s, weryfikacja OK.
7. autoremove attrs-falcon: OK; zmiany 4, pakiety 4 (ręczne 2), czas 0.373981 s, weryfikacja OK.
8. autoremove referencing-falcon: OK; zmiany 3, pakiety 1 (ręczne 1), czas 0.331576 s, weryfikacja OK.
9. install cached-property: OK; zmiany 1, pakiety 2 (ręczne 2), czas 0.792932 s, weryfikacja OK.
10. install packaging: OK; zmiany 1, pakiety 3 (ręczne 3), czas 0.725487 s, weryfikacja OK.
11. install aiohttp: OK; zmiany 10, pakiety 13 (ręczne 4), czas 0.766045 s, weryfikacja OK.
12. install toml: OK; zmiany 1, pakiety 14 (ręczne 5), czas 0.714914 s, weryfikacja OK.

Liczba zmian liczy instalacje, usunięcia i zmiany wersji.
Oznaczenie już zainstalowanego pakietu jako ręcznego nie zmienia jego wersji i nie zwiększa tej liczby.
Nieudana operacja zachowuje poprzedni stan.
W przypadku równorzędnych rozwiązań optymalnych Z3 może wybrać inny stan;
dokładny przebieg tego uruchomienia jest zapisany w JSON.
