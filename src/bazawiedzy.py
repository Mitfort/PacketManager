import z3
from packaging.specifiers import SpecifierSet
from src.parser import (
    Requirement,
    WersjaPyPI,
    formatuj_wersje,
    normalizuj_nazwe,
    porownaj_wersje,
)
from src.stan import Stan
from src.wyjasnienia import wyjasnij


class BazaWiedzy:
    def __init__(self, repository):
        self.repo = repository
        self.vars = {}
        self.aksjomaty = []
        self._cache_pasujacych = {}

        self._utworz_zmienne()
        self._wypisz_ostrzezenia_o_pustych_wymaganiach()

        self.dodajAksjomatA1()
        self.dodajAksjomatA2()
        self.dodajAksjomatA3()

    def instaluj(self, zadania: list[Requirement], stan: Stan | None = None) -> Stan | None:
        """Instaluje żądania, minimalizując zmiany istniejącego stanu."""
        stan = stan if stan is not None else Stan()
        zadane = {zadanie.alternatives[0]["package"] for zadanie in zadania}

        _, usuniete, zmienione, nowe = self._zmiany(stan)
        kary = self._oblicz_przestarzalosc()
        wiek_zadanych = []
        wiek_reszty = []

        for (nazwa, wersja), zmienna in self.vars.items():
            if nazwa in stan.pakiety:
                continue

            kara = z3.If(zmienna, kary[nazwa, wersja], 0)

            if nazwa in zadane:
                wiek_zadanych.append(kara)
            else:
                wiek_reszty.append(kara)

        cele = [usuniete, zmienione, wiek_zadanych, nowe, wiek_reszty]
        warunki = [self.formula_zadania(zadanie) for zadanie in zadania]

        return self._rozwiaz(
            warunki=warunki,
            cele=cele,
            reczne=stan.reczne | zadane,
            zadania=zadania,
        )

    def usun(self, nazwy: list[str], stan: Stan, autoremove: bool = False) -> Stan | None:
        """Usuwa pakiety, opcjonalnie także zbędne zależności."""
        usuwane = {normalizuj_nazwe(nazwa) for nazwa in nazwy}
        obecne, usuniete, zmienione, nowe = self._zmiany(stan)

        usuniete_reczne = []
        for nazwa in stan.reczne - usuwane:
            usuniete_reczne.append(z3.If(z3.Not(obecne[nazwa]), 1, 0))

        ostatni_cel = usuniete
        if autoremove:
            ostatni_cel = [z3.If(zmienna, 1, 0) for zmienna in obecne.values()]

        warunki = []
        for nazwa in usuwane:
            zainstalowany = obecne.get(nazwa, z3.BoolVal(False))
            warunki.append(z3.Not(zainstalowany))

        cele = [usuniete_reczne, zmienione, nowe, ostatni_cel]
        wynik = self._rozwiaz(warunki=warunki, cele=cele, reczne=stan.reczne)

        if wynik is not None and usuwane & wynik.pakiety.keys():
            raise RuntimeError("Solver pozostawił pakiet przeznaczony do usunięcia")

        return wynik

    def aktualizuj(self, nazwy: list[str] | None, stan: Stan) -> Stan | None:
        """Aktualizuje zbiór zainstalowanych pakietów P (domyślnie wszystkie) wg kryteriów 8.1."""
        zbior_p = self._zwaliduj_zbior_aktualizacji(nazwy, stan)
        obecne, usuniete, _, nowe = self._zmiany(stan)
        kary = self._oblicz_przestarzalosc()

        warunki = [obecne[nazwa] for nazwa in sorted(stan.reczne | zbior_p)]

        wiek_p = []
        wiek_wszystkich = []
        for (nazwa, wersja), zmienna in self.vars.items():
            kara = z3.If(zmienna, kary[nazwa, wersja], 0)
            wiek_wszystkich.append(kara)
            if nazwa in zbior_p:
                wiek_p.append(kara)

        zmienione_spoza_p = []
        for nazwa, wersja in stan.pakiety.items():
            if nazwa not in zbior_p:
                inna_wersja = z3.And(obecne[nazwa], z3.Not(self.vars[nazwa, wersja]))
                zmienione_spoza_p.append(z3.If(inna_wersja, 1, 0))

        # Kryteria leksykograficzne z zadania 8.1:
        # 1. minimalna przestarzałość pakietów z P
        # 2. minimalna liczba usuniętych pakietów
        # 3. minimalna liczba zmian wersji pakietów spoza P
        # 4. minimalna liczba nowych pakietów
        # 5. minimalna przestarzałość wszystkich pakietów
        cele = [wiek_p, usuniete, zmienione_spoza_p, nowe, wiek_wszystkich]
        return self._rozwiaz(warunki=warunki, cele=cele, reczne=stan.reczne)

    def analizuj_aktualizacje(self, nazwy: list[str] | None, stan: Stan) -> dict:
        """Wykonuje aktualizację (8.1) oraz analizę konfliktów i frontu Pareto (8.2)."""
        zbior_p = self._zwaliduj_zbior_aktualizacji(nazwy, stan)
        obecne, _, _, _ = self._zmiany(stan)
        kary = self._oblicz_przestarzalosc()

        osiagalne = {}
        for pakiet in sorted(zbior_p):
            najnowsza = self._najnowsza_osiagalna_wersja(pakiet, stan, obecne, kary)
            if najnowsza is not None:
                osiagalne[pakiet] = najnowsza

        dodatkowe_warunki = [
            (f"Zachowanie pakietu ręcznego: {r}", obecne[r])
            for r in sorted(stan.reczne - set(osiagalne))
        ]
        cele_etykiety = []
        for pakiet, wersja in osiagalne.items():
            etykieta = f"Cel aktualizacji: {pakiet}=={formatuj_wersje(wersja)}"
            cele_etykiety.append((etykieta, self.vars[pakiet, wersja]))

        rdzen = wyjasnij(self, [], dodatkowe_warunki=dodatkowe_warunki + cele_etykiety)
        konflikt = bool(rdzen)

        pakiety_w_konflikcie = []
        front_pareto = []

        if konflikt:
            for pakiet, wersja in osiagalne.items():
                etykieta = f"Cel aktualizacji: {pakiet}=={formatuj_wersje(wersja)}"
                if etykieta in rdzen:
                    pakiety_w_konflikcie.append(pakiet)

            if not pakiety_w_konflikcie:
                pakiety_w_konflikcie = sorted(osiagalne)

            front_pareto = self._wyznacz_front_pareto(
                pakiety_w_konflikcie=pakiety_w_konflikcie,
                wymagane_obecne=stan.reczne | zbior_p,
                obecne=obecne,
                kary=kary,
            )

        wynik = self.aktualizuj(list(zbior_p), stan)

        return {
            "zbior_P": sorted(zbior_p),
            "osiagalne": osiagalne,
            "konflikt": konflikt,
            "wyjasnienie": rdzen,
            "pakiety_w_konflikcie": pakiety_w_konflikcie,
            "front_pareto": front_pareto,
            "wynik": wynik,
        }

    def _zwaliduj_zbior_aktualizacji(self, nazwy: list[str] | None, stan: Stan) -> set[str]:
        for nazwa, wersja in stan.pakiety.items():
            if (nazwa, wersja) not in self.vars:
                raise ValueError(f"Stan: nieznany pakiet lub wersja {nazwa} {formatuj_wersje(wersja)}")

        if not nazwy:
            return set(stan.pakiety.keys())

        zbior_p = {normalizuj_nazwe(nazwa) for nazwa in nazwy}
        niezainstalowane = sorted(zbior_p - stan.pakiety.keys())
        if niezainstalowane:
            raise ValueError(
                f"Aktualizacja dotyczy tylko zainstalowanych pakietów; brak w stanie: {', '.join(niezainstalowane)}"
            )
        return zbior_p

    def _najnowsza_osiagalna_wersja(self, pakiet: str, stan: Stan, obecne: dict, kary: dict):
        """Wyznacza najnowszą wersję pakietu osiągalną osobno przy zachowaniu pakietów ręcznych."""
        opt = z3.Optimize()
        opt.set(priority="lex")
        opt.add([formula for _, formula in self.aksjomaty])
        opt.add(obecne[pakiet])
        for reczny in stan.reczne:
            opt.add(obecne[reczny])

        cel = [
            z3.If(self.vars[pakiet, wersja], kary[pakiet, wersja], 0)
            for wersja in self.repo.packages[pakiet].versions
        ]
        opt.minimize(z3.Sum(cel))

        if opt.check() != z3.sat:
            return None

        model = opt.model()
        for wersja in sorted(self.repo.packages[pakiet].versions, reverse=True):
            if z3.is_true(model.eval(self.vars[pakiet, wersja])):
                return wersja
        return None

    def _wyznacz_front_pareto(
        self,
        *,
        pakiety_w_konflikcie: list[str],
        wymagane_obecne: set[str],
        obecne: dict,
        kary: dict,
    ) -> list[dict]:
        """Wyznacza front Pareto względem przestarzałości pakietów w konflikcie."""
        opt = z3.Optimize()
        opt.set(priority="pareto")
        opt.add([formula for _, formula in self.aksjomaty])

        for nazwa in sorted(wymagane_obecne):
            opt.add(obecne[nazwa])

        for pakiet in pakiety_w_konflikcie:
            wiek_pakietu = [
                z3.If(self.vars[pakiet, wersja], kary[pakiet, wersja], 0)
                for wersja in self.repo.packages[pakiet].versions
            ]
            opt.minimize(z3.Sum(wiek_pakietu))

        front = []
        while opt.check() == z3.sat:
            model = opt.model()
            rozwiazanie = {}
            for pakiet in pakiety_w_konflikcie:
                for wersja in sorted(self.repo.packages[pakiet].versions, reverse=True):
                    if z3.is_true(model.eval(self.vars[pakiet, wersja])):
                        rozwiazanie[pakiet] = wersja
                        break
            if rozwiazanie not in front:
                front.append(rozwiazanie)

        return front

    def formula_zadania(self, zadanie: Requirement):
        pasujace = []

        for alternatywa in zadanie.alternatives:
            pasujace.extend(self._znajdz_pasujace_zmienne(alternatywa))

        return z3.Or(pasujace)

    def _zmiany(self, stan: Stan):
        """Buduje składniki celów wspólne dla instalacji, usuwania i aktualizacji."""
        for nazwa, wersja in stan.pakiety.items():
            if (nazwa, wersja) not in self.vars:
                raise ValueError(f"Stan: nieznany pakiet lub wersja {nazwa} {formatuj_wersje(wersja)}")

        obecne = {}
        for nazwa, pakiet in self.repo.packages.items():
            wersje = [self.vars[nazwa, wersja] for wersja in pakiet.versions]
            obecne[nazwa] = z3.Or(wersje)

        usuniete = []
        zmienione = []
        nowe = []

        for nazwa, wersja in stan.pakiety.items():
            usuniete.append(z3.If(z3.Not(obecne[nazwa]), 1, 0))

            inna_wersja = z3.And(obecne[nazwa], z3.Not(self.vars[nazwa, wersja]))
            zmienione.append(z3.If(inna_wersja, 1, 0))

        for nazwa, zmienna in obecne.items():
            if nazwa not in stan.pakiety:
                nowe.append(z3.If(zmienna, 1, 0))

        return obecne, usuniete, zmienione, nowe

    def _rozwiaz(self, *, warunki, cele, reczne: set[str], zadania=()) -> Stan | None:
        """Rozwiązuje jedno zapytanie i niezależnie weryfikuje jego wynik."""
        solver = z3.Optimize()
        solver.set(priority="lex")
        solver.add([formula for _, formula in self.aksjomaty])
        solver.add(warunki)

        for cel in cele:
            solver.minimize(z3.Sum(cel) if cel else z3.IntVal(0))

        status = solver.check()

        if status == z3.unsat:
            return None

        if status != z3.sat:
            raise RuntimeError(f"Solver nie rozstrzygnął zapytania: {solver.reason_unknown()}")

        model = solver.model()
        pakiety = {}

        for (nazwa, wersja), zmienna in self.vars.items():
            if z3.is_true(model.eval(zmienna)):
                pakiety[nazwa] = wersja

        wynik = Stan(pakiety, reczne & pakiety.keys())

        if not weryfikujStan(self.repo, wynik.pakiety, zadania):
            raise RuntimeError("Solver zwrócił niespójny stan")

        return wynik

    def _utworz_zmienne(self):
        for nazwa, pakiet in self.repo.packages.items():
            for wersja in pakiet.versions:
                wersja_tekst = formatuj_wersje(wersja)
                self.vars[nazwa, wersja] = z3.Bool(f"{nazwa}=={wersja_tekst}")

    def _wypisz_ostrzezenia_o_pustych_wymaganiach(self):
        for nazwa, pakiet in self.repo.packages.items():
            for wersja, opis in pakiet.versions.items():
                for wymaganie in opis.requirements + opis.conflicts:
                    ma_pasujace = any(
                        self._znajdz_pasujace_zmienne(alternatywa)
                        for alternatywa in wymaganie.alternatives
                    )

                    if not ma_pasujace:
                        wersja_tekst = formatuj_wersje(wersja)
                        print(
                            f"Ostrzeżenie: W {nazwa}=={wersja_tekst} wymóg "
                            f"'{wymaganie.path}' wskazuje na nieistniejący pakiet/wersję."
                        )

    def dodajAksjomatA1(self):
        for nazwa, pakiet in self.repo.packages.items():
            zmienne_wersji = [self.vars[nazwa, wersja] for wersja in pakiet.versions]
            if not zmienne_wersji:
                continue
            etykieta = f"(A1) Pakiet '{nazwa}' ma max 1 wersję"
            self._dodaj_aksjomat(z3.AtMost(*zmienne_wersji, 1), etykieta)

    def dodajAksjomatA2(self):
        for (nazwa, wersja), zmienna in self.vars.items():
            opis = self.repo.packages[nazwa].versions[wersja]
            wersja_tekst = formatuj_wersje(wersja)

            for wymaganie in opis.requirements:
                warunek = self.formula_zadania(wymaganie)
                etykieta = (
                    f"(A2) {nazwa}=={wersja_tekst} wymaga "
                    f"{wymaganie.tekst} ({wymaganie.path})"
                )

                self._dodaj_aksjomat(z3.Implies(zmienna, warunek), etykieta)

    def dodajAksjomatA3(self):
        for (nazwa, wersja), zmienna in self.vars.items():
            opis = self.repo.packages[nazwa].versions[wersja]
            wersja_tekst = formatuj_wersje(wersja)

            for konflikt in opis.conflicts:
                for alternatywa in konflikt.alternatives:
                    for wykluczona in self._znajdz_pasujace_zmienne(alternatywa):
                        etykieta = (
                            f"(A3) {nazwa}=={wersja_tekst} wyklucza "
                            f"{wykluczona} ({konflikt.path})"
                        )

                        self._dodaj_aksjomat(z3.Implies(zmienna, z3.Not(wykluczona)), etykieta)

    def _dodaj_aksjomat(self, formula, etykieta: str):
        self.aksjomaty.append((etykieta, formula))

    def _znajdz_pasujace_zmienne(self, alternatywa):
        nazwa = alternatywa["package"]
        ograniczenia = alternatywa["constraints"]

        if nazwa not in self.repo.packages:
            return []

        klucz_cache = (
            nazwa,
            str(ograniczenia) if isinstance(ograniczenia, SpecifierSet) else tuple(ograniczenia),
        )
        if klucz_cache in self._cache_pasujacych:
            return self._cache_pasujacych[klucz_cache]

        pasujace = []

        for wersja in self.repo.packages[nazwa].versions:
            if _sprawdz_wersje(wersja, ograniczenia):
                pasujace.append(self.vars[nazwa, wersja])

        self._cache_pasujacych[klucz_cache] = pasujace
        return pasujace

    def _oblicz_przestarzalosc(self):
        kary = {}

        for nazwa, pakiet in self.repo.packages.items():
            posortowane = sorted(pakiet.versions, reverse=True)

            for indeks, wersja in enumerate(posortowane):
                kary[nazwa, wersja] = indeks

        return kary


def weryfikujStan(repo, zainstalowane_pakiety, zadania=()):
    bledy = []

    for nazwa, wersja in zainstalowane_pakiety.items():
        if nazwa not in repo.packages:
            bledy.append(f"Zainstalowany pakiet '{nazwa}' nie istnieje w repozytorium")
            continue

        pakiet = repo.packages[nazwa]

        if wersja not in pakiet.versions:
            wersja_tekst = formatuj_wersje(wersja)
            bledy.append(f"Zainstalowana wersja '{wersja_tekst}' pakietu '{nazwa}' nie istnieje w repozytorium!")
            continue

        opis = pakiet.versions[wersja]

        for wymaganie in opis.requirements:
            if not _spelnia_wymaganie(zainstalowane_pakiety, wymaganie):
                bledy.append(f"Błąd zależności w {opis.path}: nie spełniono wymogu '{wymaganie.tekst}'")

        for konflikt in opis.conflicts:
            if _spelnia_wymaganie(zainstalowane_pakiety, konflikt):
                bledy.append(f"Wykryto konflikt w {opis.path}: {konflikt.tekst}")

    for zadanie in zadania:
        if not _spelnia_wymaganie(zainstalowane_pakiety, zadanie):
            bledy.append(f"Niespełnione żądanie: {zadanie.tekst}")

    if not bledy:
        print("Weryfikacja zakończona sukcesem. Stan jest całkowicie spójny.")
        return True

    print("STAN JEST NIESPÓJNY! Znaleziono naruszenia:")

    for blad in bledy:
        print(f"- {blad}")

    return False


def _spelnia_wymaganie(pakiety, wymaganie: Requirement) -> bool:
    """Sprawdza wymaganie wyłącznie na danych stanu, bez solvera."""
    for alternatywa in wymaganie.alternatives:
        nazwa = alternatywa["package"]
        ograniczenia = alternatywa["constraints"]

        if nazwa in pakiety and _sprawdz_wersje(pakiety[nazwa], ograniczenia):
            return True

    return False


def _sprawdz_wersje(wersja, ograniczenia) -> bool:
    """Sprawdza wszystkie ograniczenia wersji (zarówno numerycznej, jak i PEP 440)."""
    if isinstance(ograniczenia, SpecifierSet):
        v = WersjaPyPI.na_pep440(wersja)
        return ograniczenia.contains(v, prereleases=True)

    for operator, wymagana in ograniczenia:
        cmp_val = porownaj_wersje(wersja, wymagana)

        if operator == "==" and cmp_val != 0:
            return False

        if operator == "!=" and cmp_val == 0:
            return False

        if operator == "<" and cmp_val >= 0:
            return False

        if operator == "<=" and cmp_val > 0:
            return False

        if operator == ">" and cmp_val <= 0:
            return False

        if operator == ">=" and cmp_val < 0:
            return False

    return True