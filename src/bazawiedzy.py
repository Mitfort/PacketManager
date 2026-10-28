import z3
from parser import Requirement

class BazaWiedzy:
    def __init__(self, repository):
        self.repo = repository
        self.opt = z3.Optimize()
        self.opt.set(priority="lex")
        self.vars = {}

        self._utworz_zmienne()
        self.dodajAksjomatA1()
        self.dodajAksjomatA2()
        self.dodajAksjomatA3()

    def _utworz_zmienne(self):
        for nazwa_pakietu, pakiet in self.repo.packages.items():
            for wer_krotka, wersja_obj in pakiet.versions.items():
                wer_str = '.'.join(map(str, wer_krotka))
                nazwa_zmiennej = f"{nazwa_pakietu}=={wer_str}"
                self.vars[(nazwa_pakietu, wer_krotka)] = z3.Bool(nazwa_zmiennej)

    def dodajAksjomatA1(self):
        for nazwa_pakietu, pakiet in self.repo.packages.items():
            zmienne_wersje = [self.vars[(nazwa_pakietu, wer_krotka)] for wer_krotka in pakiet.versions.keys()]
            self.opt.add(z3.AtMost(*zmienne_wersje, 1))

    def dodajAksjomatA2(self):
        for (nazwa_pakietu, wer_krotka), zmienna_z3 in self.vars.items():
            wersja_obj = self.repo.packages[nazwa_pakietu].versions[wer_krotka]

            for wymaganie in wersja_obj.requirements:
                opcje_z3 = []

                for alternatywa in wymaganie.alternatives:
                    pasujace_zmienne = self._znajdz_pasujace_zmienne(alternatywa)
                    opcje_z3.extend(pasujace_zmienne)

                if opcje_z3:
                    self.opt.add(z3.Implies(zmienna_z3, z3.Or(opcje_z3)))
                else:
                    self.opt.add(z3.Implies(zmienna_z3, z3.BoolVal(False)))

    def dodajAksjomatA3(self):
        for (nazwa_pakietu, wer_krotka), zmienna_z3 in self.vars.items():
            wersja_obj = self.repo.packages[nazwa_pakietu].versions[wer_krotka]

            for konflikt in wersja_obj.conflicts:
                for alternatywa in konflikt.alternatives:
                    pasujace_zmienne = self._znajdz_pasujace_zmienne(alternatywa)
                    for konfliktujaca_zmienna in pasujace_zmienne:
                        self.opt.add(z3.Implies(zmienna_z3, z3.Not(konfliktujaca_zmienna)))

    def _znajdz_pasujace_zmienne(self, alternatywa):
        nazwa_pakietu = alternatywa["package"]
        ograniczenia = alternatywa["constraints"]
        pasujace_zmienne = []

        if nazwa_pakietu not in self.repo.packages:
            return []

        pakiet_obj = self.repo.packages[nazwa_pakietu]

        for wer_krotka in pakiet_obj.versions.keys():
            czy_pasuje = True
            for operator, wer_wymagana in ograniczenia:
                length = max(len(wer_krotka), len(wer_wymagana))
                v1 = wer_krotka + (0,) * (length - len(wer_krotka))
                v2 = wer_wymagana + (0,) * (length - len(wer_wymagana))

                if operator == "==" and not (v1 == v2): czy_pasuje = False
                elif operator == "!=" and not (v1 != v2): czy_pasuje = False
                elif operator == "<" and not (v1 < v2): czy_pasuje = False
                elif operator == "<=" and not (v1 <= v2): czy_pasuje = False
                elif operator == ">" and not (v1 > v2): czy_pasuje = False
                elif operator == ">=" and not (v1 >= v2): czy_pasuje = False
                
                if not czy_pasuje:
                    break

            if czy_pasuje:
                pasujace_zmienne.append(self.vars[(nazwa_pakietu, wer_krotka)])

        return pasujace_zmienne

    def _oblicz_przestarzalosc(self):
        kary = {}
        for nazwa_pakietu, pakiet in self.repo.packages.items():
            posortowane_wersje = sorted(pakiet.versions.keys(), reverse=True)
            for indeks, wer_krotka in enumerate(posortowane_wersje):
                kary[(nazwa_pakietu, wer_krotka)] = indeks
        return kary

    def instaluj(self, surowe_zadania):
        zadania_obj = []
        pakiet_zadany_nazwy = set()

        for tekst_zadania in surowe_zadania:
            req = Requirement(tekst_zadania, f"żądanie: {tekst_zadania}")
            zadania_obj.append(req)
            for alt in req.alternatives:
                pakiet_zadany_nazwy.add(alt["package"])

        for req in zadania_obj:
            opcje_z3 = []
            for alt in req.alternatives:
                opcje_z3.extend(self._znajdz_pasujace_zmienne(alt))

            if opcje_z3:
                self.opt.add(z3.Or(opcje_z3))
            else:
                return "brak rozwiazania"

        kary_wiek = self._oblicz_przestarzalosc()
        cel_1_wiek_zadanych = []
        cel_2_liczba_wszystkich = []
        cel_3_wiek_reszty = []

        for (nazwa, krotka), zmienna in self.vars.items():
            kara = kary_wiek[(nazwa, krotka)]
            if nazwa in pakiet_zadany_nazwy:
                cel_1_wiek_zadanych.append(z3.If(zmienna, kara, 0))
            else:
                cel_3_wiek_reszty.append(z3.If(zmienna, kara, 0))
            cel_2_liczba_wszystkich.append(z3.If(zmienna, 1, 0))

        self.opt.minimize(z3.Sum(cel_1_wiek_zadanych) if cel_1_wiek_zadanych else z3.IntVal(0))
        self.opt.minimize(z3.Sum(cel_2_liczba_wszystkich) if cel_2_liczba_wszystkich else z3.IntVal(0))
        self.opt.minimize(z3.Sum(cel_3_wiek_reszty) if cel_3_wiek_reszty else z3.IntVal(0))
        
        if self.opt.check() == z3.sat:
            model = self.opt.model()
            zainstalowane = []

            for (nazwa, krotka), zmienna in self.vars.items():
                if z3.is_true(model.eval(zmienna)):
                    wer_str = '.'.join(map(str, krotka))
                    zainstalowane.append(f"{nazwa} {wer_str}")
            return zainstalowane
        else:
            return "brak rozwiazania"


def weryfikujStan(repo, zainstalowane_pakiety):
    bledy = []

    for nazwa, wer_krotka in zainstalowane_pakiety.items():
        if nazwa not in repo.packages:
            bledy.append(f"Zainstalowany pakiet '{nazwa}' nie istnieje w repozytorium")
            continue
            
        pakiet_obj = repo.packages[nazwa]
        if wer_krotka not in pakiet_obj.versions:
            wer_str = '.'.join(map(str, wer_krotka))
            bledy.append(f"Zainstalowana wersja '{wer_str}' pakietu '{nazwa}' nie istnieje w repozytorium!")
            continue

        wersja_obj = pakiet_obj.versions[wer_krotka]

        for wymaganie in wersja_obj.requirements:
            wymaganie_spelnione = False

            for alternatywa in wymaganie.alternatives:
                nazwa_wymagana = alternatywa["package"]
                ograniczenia = alternatywa["constraints"]

                if nazwa_wymagana in zainstalowane_pakiety:
                    zainstalowana_wersja_wymaganego = zainstalowane_pakiety[nazwa_wymagana]
                    if _sprawdz_wersje(zainstalowana_wersja_wymaganego, ograniczenia):
                        wymaganie_spelnione = True
                        break
                        
            if not wymaganie_spelnione:
                bledy.append(f"Błąd zależności w {wersja_obj.path}: nie spełniono wymogu '{wymaganie.path}'")

        for konflikt in wersja_obj.conflicts:
            for alternatywa in konflikt.alternatives:
                nazwa_konfliktu = alternatywa["package"]
                ograniczenia = alternatywa["constraints"]

                if nazwa_konfliktu in zainstalowane_pakiety:
                    zainstalowana_wersja_konfliktu = zainstalowane_pakiety[nazwa_konfliktu]
                    if _sprawdz_wersje(zainstalowana_wersja_konfliktu, ograniczenia):
                        bledy.append(f"Wykryto konflikt w {wersja_obj.path}: gryzie się z zainstalowanym '{nazwa_konfliktu}'")
                        
    if not bledy:
        print("Weryfikacja zakończona sukcesem. Stan jest całkowicie spójny.")
        return True
    else:
        print("STAN JEST NIESPÓJNY! Znaleziono naruszenia:")
        for błąd in bledy:
            print(f"- {błąd}")
        return False

def _sprawdz_wersje(krotka_do_sprawdzenia, ograniczenia):
    for operator, wer_wymagana in ograniczenia:
        length = max(len(krotka_do_sprawdzenia), len(wer_wymagana))
        v1 = krotka_do_sprawdzenia + (0,) * (length - len(krotka_do_sprawdzenia))
        v2 = wer_wymagana + (0,) * (length - len(wer_wymagana))

        if operator == "==" and not (v1 == v2): return False
        if operator == "!=" and not (v1 != v2): return False
        if operator == "<" and not (v1 < v2): return False
        if operator == "<=" and not (v1 <= v2): return False
        if operator == ">" and not (v1 > v2): return False
        if operator == ">=" and not (v1 >= v2): return False
    return True