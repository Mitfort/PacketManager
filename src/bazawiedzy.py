import z3
from src.parser import Requirement, normalizuj_nazwe
from src.stan import Stan

class BazaWiedzy:
    def __init__(self, repository):
        self.repo = repository
        self.vars = {}
        self.aksjomaty = []

        self._utworz_zmienne()
        self._wypisz_ostrzezenia_o_pustych_wymaganiach()

        self.dodajAksjomatA1()
        self.dodajAksjomatA2()
        self.dodajAksjomatA3()

    def instaluj(self, zadania: list[Requirement], stan: Stan | None = None) -> Stan | None:
        """Instaluje żądania, minimalizując zmiany istniejącego stanu.

        Raises:
            ValueError: Stan zawiera pakiet lub wersję spoza repozytorium.
            RuntimeError: Solver nie rozstrzygnął zapytania lub zwrócił błędny stan.
        """
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

        # Kolejność listy jest kolejnością kryteriów leksykograficznych.
        cele = [usuniete, zmienione, wiek_zadanych, nowe, wiek_reszty]
        warunki = [self.formula_zadania(zadanie) for zadanie in zadania]

        return self._rozwiaz(
            warunki=warunki,
            cele=cele,
            reczne=stan.reczne | zadane,
            zadania=zadania,
        )

    def usun(self, nazwy: list[str], stan: Stan, autoremove: bool = False) -> Stan | None:
        """Usuwa pakiety, opcjonalnie także zbędne zależności.

        Raises:
            ValueError: Nazwa lub pakiet w stanie jest niepoprawny.
            RuntimeError: Solver nie rozstrzygnął zapytania lub zwrócił błędny stan.
        """
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

    def formula_zadania(self, zadanie: Requirement):
        pasujace = []

        for alternatywa in zadanie.alternatives:
            pasujace.extend(self._znajdz_pasujace_zmienne(alternatywa))

        return z3.Or(pasujace)

    def _zmiany(self, stan: Stan):
        """Buduje składniki celów wspólne dla instalacji i usuwania."""
        for nazwa, wersja in stan.pakiety.items():
            if (nazwa, wersja) not in self.vars:
                raise ValueError(f"Stan: nieznany pakiet lub wersja {nazwa} {wersja}")

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
                wersja_tekst = '.'.join(map(str, wersja))
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
                        wersja_tekst = '.'.join(map(str, wersja))
                        print(
                            f"Ostrzeżenie: W {nazwa}=={wersja_tekst} wymóg "
                            f"'{wymaganie.path}' wskazuje na nieistniejący pakiet/wersję."
                        )

    def dodajAksjomatA1(self):
        for nazwa, pakiet in self.repo.packages.items():
            zmienne_wersji = [self.vars[nazwa, wersja] for wersja in pakiet.versions]
            etykieta = f"(A1) Pakiet '{nazwa}' ma max 1 wersję"

            self._dodaj_aksjomat(z3.AtMost(*zmienne_wersji, 1), etykieta)

    def dodajAksjomatA2(self):
        for (nazwa, wersja), zmienna in self.vars.items():
            opis = self.repo.packages[nazwa].versions[wersja]
            wersja_tekst = '.'.join(map(str, wersja))

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
            wersja_tekst = '.'.join(map(str, wersja))

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

        pasujace = []

        for wersja in self.repo.packages[nazwa].versions:
            if _sprawdz_wersje(wersja, ograniczenia):
                pasujace.append(self.vars[nazwa, wersja])

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
            wersja_tekst = '.'.join(map(str, wersja))
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
    """Sprawdza wszystkie ograniczenia numerycznej wersji."""
    for operator, wymagana in ograniczenia:
        dlugosc = max(len(wersja), len(wymagana))
        lewa = wersja + (0,) * (dlugosc - len(wersja))
        prawa = wymagana + (0,) * (dlugosc - len(wymagana))

        if operator == "==" and lewa != prawa:
            return False

        if operator == "!=" and lewa == prawa:
            return False

        if operator == "<" and lewa >= prawa:
            return False

        if operator == "<=" and lewa > prawa:
            return False

        if operator == ">" and lewa <= prawa:
            return False

        if operator == ">=" and lewa < prawa:
            return False

    return True
