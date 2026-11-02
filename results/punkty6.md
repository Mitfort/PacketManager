# Raport - manager pakietów, próg 8 punktów

Grupa **k05**, ziarno **2026**.
Python 3.10.4, Z3 5.3.3.
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

- N=10: 52 wersji, 31 aksjomatów; żądania: cffi, attrs, falcon-tools; wynik: 5 pakietów, przestarzałość 2; budowa 0.004793 s, rozwiązanie 0.021049 s; weryfikacja: OK; ostrzeżenia: 4.
- N=30: 171 wersji, 99 aksjomatów; żądania: multidict, anyio, basalt-core; wynik: brak rozwiązania; budowa 0.014287 s, rozwiązanie 0.016739 s; weryfikacja: nie dotyczy (UNSAT); ostrzeżenia: 0.
- N=100: 1285 wersji, 1193 aksjomatów; żądania: multidict, markupsafe-willow, krypton-io; wynik: 6 pakietów, przestarzałość 0; budowa 0.247461 s, rozwiązanie 1.018709 s; weryfikacja: OK; ostrzeżenia: 93.
- N=300: 6705 wersji, 6106 aksjomatów; żądania: httpx, importlib-metadata-indigo, prism-api; wynik: 11 pakietów, przestarzałość 1; budowa 1.691130 s, rozwiązanie 3.821089 s; weryfikacja: OK; ostrzeżenia: 206.
- N=1000: 20896 wersji, 15524 aksjomatów; żądania: packaging, chardet-heron, juniper-core; wynik: 4 pakietów, przestarzałość 34; budowa 4.224141 s, rozwiązanie 11.047943 s; weryfikacja: OK; ostrzeżenia: 552.

## Minimalne wyjaśnienia (6.3)

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
budowa 1.362045 s.

1. install wcwidth-falcon: OK; zmiany 1, pakiety 1 (ręczne 1), czas 2.823876 s, weryfikacja OK.
2. remove wcwidth-falcon: OK; zmiany 1, pakiety 0 (ręczne 0), czas 1.181128 s, weryfikacja OK.
3. install hyperframe: OK; zmiany 1, pakiety 1 (ręczne 1), czas 2.814719 s, weryfikacja OK.
4. autoremove hyperframe: OK; zmiany 1, pakiety 0 (ręczne 0), czas 2.330644 s, weryfikacja OK.
5. install referencing-falcon: OK; zmiany 4, pakiety 4 (ręczne 1), czas 3.193702 s, weryfikacja OK.
6. install attrs-krypton: OK; zmiany 1, pakiety 5 (ręczne 2), czas 2.965383 s, weryfikacja OK.
7. autoremove attrs-falcon: OK; zmiany 4, pakiety 4 (ręczne 2), czas 2.534042 s, weryfikacja OK.
8. autoremove referencing-falcon: OK; zmiany 3, pakiety 1 (ręczne 1), czas 2.374464 s, weryfikacja OK.
9. install cached-property: OK; zmiany 1, pakiety 2 (ręczne 2), czas 3.137733 s, weryfikacja OK.
10. install packaging: OK; zmiany 1, pakiety 3 (ręczne 3), czas 3.102084 s, weryfikacja OK.
11. install aiohttp: OK; zmiany 10, pakiety 13 (ręczne 4), czas 3.014966 s, weryfikacja OK.
12. install toml: OK; zmiany 1, pakiety 14 (ręczne 5), czas 2.994749 s, weryfikacja OK.

## Aktualizacja i front Pareto (8.1 - 8.2)

- Aktualizacja wszystkiego dla `state_example.txt`: Podniesienie wersji: lib 1 -> 1.5, Instalacja: util 2.
- Dla stanu `a 1.0 manual, b 1.0 manual`: najnowsze osiągalne osobno to `a 2` oraz `b 2`.
- Front Pareto: {a 2, b 1}, {a 1.1, b 2}.
- Przyczyna konfliktu (unsat core):
  - (A1) Pakiet 'b' ma max 1 wersję
  - (A2) a==2 wymaga b < 2.0 (packages['a'].versions['2.0'].requires[0])
  - Cel aktualizacji: a==2
  - Cel aktualizacji: b==2
- Aktualizacja samego `a`: Podniesienie wersji: a 1 -> 2 (konflikt: False).
