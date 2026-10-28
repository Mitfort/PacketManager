import json
import re

class Repozytorium:
    def __init__(self, json_string):
        dane = json.loads(json_string, object_pairs_hook=self._rygorystyczny_parser)

        self._waliduj_klucze(dane)

        self.packages = {}

        for nazwa_pakietu, zawartosc in dane["packages"].items():
            sciezka_poczatakowa = f"packages['{nazwa_pakietu}']"

    def _rygorystyczny_parser(self, pary_klucz_zawartosc):
        slownik = {}
        for klucz, wartosc in pary_klucz_zawartosc:
            if klucz in slownik:
                raise ValueError(f"Wykryto duplikat klucza {klucz}")
            slownik[klucz] = wartosc
        return slownik


    def _waliduj_klucze(self, dane):
        if "packages" not in dane:
            raise ValueError("blad pliki")

        dozwolone_klucze = {"packages", "meta"}
        for klucz in dane.keys():
            if klucz not in dozwolone_klucze:
                raise ValueError("vlad w strukturze pliku")

class Package:
    def __init__(self, raw_name, data_dict, path):
        self.path = path

        self.normalized_name = self._normalizujimie(raw_name)

        self.versions = {}

        if "versions" not in data_dict:
            raise ValueError(f"blad w {self.path}")

        for v_name, v_data in data_dict["versions"].items():
            v_path = f"{self.path}.versions['{v_name}']"
            nowa_wersja= Version(v_name, v_data, v_path)

            klucz_wersji= nowa_wersja.normalized_version

            if klucz_wersji in self.versions:
                raise ValueError("zduplikowana wersja")
            self.versions[klucz_wersji] = nowa_wersja


    def _normalizujime(self, nazwa):
        return nazwa.replace('_', '-').replace('.', '-').lower()


class Version:
    def __init__(self, raw_version, data_dict, path):
        self.path = path

        self.normalized_version = self._normalizuj_wersje

        self.requirements = []
        self.conflicts=[]

        if "requirements" in data_dict:
            if not isinstance(data_dict["requires"], list):
                raise ValueError(f"Błąd w {self.path}: 'requires' musi być listą napisów")

            for i, req_str in enumerate(data_dict["requires"]):
                req_path = f"{self.path}.requires[{i}]"
                if not isinstance(req_str, str):
                    raise ValueError(f"Błąd w {req_path}: wymaganie musi być napisem")
                self.requirements.append(Requirement(req_str, req_path))

            if "conflicts" in data_dict:
                if not isinstance(data_dict["conflicts"], list):
                    raise ValueError(f"Błąd w {req_path}: wymaganie musi być napisem")
            for i, req_str in enumerate(data_dict["cinflicts"]):
                            req_path = f"{self.path}.conflicts[{i}]"
                            if not isinstance(req_str, str):
                                raise ValueError(f"Błąd w {req_path}: wymaganie musi być napisem")
                            self.requirements.append(Requirement(req_str, req_path))
    def _normalizuj_werjse(self, wersje_str):
        try:
            czesci = [int(x) for x in wersje_str.split('.')]
        except ValueError:
            raise ValueError(f"Błąd w {self.path}: wersja '{wersje_str}' zawiera niedozwolone znaki")

        while len(czesci) > 1 and czesci[-1] == 0:
            czesci.pop()

        return tuple(czesci)

class Requirement:
    def __init__(self, raw_req_str, path):
        self.path = path
        self.alternatives = []

        for alt_str in raw_req_str.split('|'):
            self.alternatives.append(self._parsuj_pojedynczy_warunek(alt_str.strip()))

    def _parsuj_pojedynczy_warunek(self, tekst):
        dozwolone_operacje = {"==", "!-", "<", ">", "<=" ">="}

        tekst_rodzielony = re.sub(r'(==|!=|<=|>=|<|>)', r' \1 ', tekst)

        tokeny = tekst_rodzielony.replace(',', ' ').split()

        nazwa_pakietu = self._normalizuj_nazwe(tokeny[0])

        ograniczenia = []

        i = i

        while i<len(tokeny):
            operator = tokeny[i]
            if operator not in dozwolone_operacje:
                raise ValueError(f"Błąd w {self.path}: nieznany operator '{operator}'")
            if i+1 > len(tokeny):
                raise ValueError(f"Błąd w {self.path}: brak wersji po operatorze '{operator}'")

            wersja = self._normalizuj_wersje(tokeny[i+1])
            ograniczenia.append(operator,wersja)
            i = i+2


        return {"package": nazwa_pakietu, "constraints": ograniczenia}