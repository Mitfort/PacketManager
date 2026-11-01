import json
import re
from pathlib import Path

def normalizuj_nazwe(nazwa: str, path: str = "nazwa") -> str:
    """
    Raises:
        ValueError: Nazwa zawiera niedozwolone znaki lub jest pusta.
    """
    if not isinstance(nazwa, str) or not re.fullmatch(r"[A-Za-z0-9._-]+", nazwa):
        raise ValueError(f"Błąd w {path}: niepoprawna nazwa pakietu {nazwa!r}")
    return re.sub(r"[-_.]+", "-", nazwa).lower()


def normalizuj_wersje(wersja: str, path: str = "wersja") -> tuple[int, ...]:
    """
    Raises:
        ValueError: Wersja nie jest ciągiem nieujemnych liczb oddzielonych kropkami.
    """
    if not isinstance(wersja, str) or not re.fullmatch(r"[0-9]+(?:\.[0-9]+)*", wersja):
        raise ValueError(f"Błąd w {path}: niepoprawna wersja {wersja!r}")

    czesci = [int(x) for x in wersja.split('.')]

    while len(czesci) > 1 and czesci[-1] == 0:
        czesci.pop()

    return tuple(czesci)


def _waliduj_obiekt(dane, dozwolone: set[str], wymagane: set[str], path: str):
    """Sprawdza typ i klucze obiektu JSON."""
    if not isinstance(dane, dict):
        raise ValueError(f"Błąd w {path}: oczekiwano obiektu JSON")

    for klucz in wymagane - dane.keys():
        raise ValueError(f"Błąd w {path}: brak klucza {klucz!r}")

    for klucz in dane.keys() - dozwolone:
        raise ValueError(f"Błąd w {path}[{klucz!r}]: niedozwolony klucz")

class Repozytorium:
    def __init__(self, json_string):
        try:
            dane = json.loads(json_string, object_pairs_hook=self._rygorystyczny_parser)
        except json.JSONDecodeError as e:
            raise ValueError(f"Błąd składni JSON w linii {e.lineno}, kolumnie {e.colno}: {e.msg}")

        dane = self._odtworz_json(dane)
        self._waliduj_klucze(dane)
        self.packages = {}

        for nazwa_pakietu, zawartosc in dane["packages"].items():
            sciezka_poczatkowa = f"packages['{nazwa_pakietu}']"
            pakiet = Package(nazwa_pakietu, zawartosc, sciezka_poczatkowa)
            if pakiet.normalized_name in self.packages:
                raise ValueError(f"Błąd w {sciezka_poczatkowa}: powtórzony pakiet po normalizacji")
            self.packages[pakiet.normalized_name] = pakiet

    def _rygorystyczny_parser(self, pary_klucz_zawartosc):
        # Krotka odróżnia obiekty od tablic JSON i zachowuje powtórzone klucze.
        return tuple(pary_klucz_zawartosc)

    def _odtworz_json(self, dane, path=""):
        if isinstance(dane, tuple):
            slownik = {}
            for klucz, wartosc in dane:
                sciezka = f"{path}[{klucz!r}]" if path else klucz
                if klucz in slownik:
                    raise ValueError(f"Błąd w {sciezka}: powtórzony klucz")
                slownik[klucz] = self._odtworz_json(wartosc, sciezka)
            return slownik
        if isinstance(dane, list):
            return [self._odtworz_json(wartosc, f"{path}[{i}]") for i, wartosc in enumerate(dane)]
        return dane

    def _waliduj_klucze(self, dane):
        _waliduj_obiekt(dane, {"packages", "meta"}, {"packages"}, "repozytorium")
        if not isinstance(dane["packages"], dict):
            raise ValueError("Błąd w packages: oczekiwano obiektu JSON")

class Package:
    def __init__(self, raw_name, data_dict, path):
        self.path = path
        self.normalized_name = self._normalizuj_nazwe(raw_name)
        self.versions = {}

        _waliduj_obiekt(data_dict, {"versions"}, {"versions"}, self.path)
        if not isinstance(data_dict["versions"], dict) or not data_dict["versions"]:
            raise ValueError(f"Błąd w {self.path}.versions: oczekiwano niepustego obiektu JSON")

        for v_name, v_data in data_dict["versions"].items():
            v_path = f"{self.path}.versions['{v_name}']"
            nowa_wersja = Version(v_name, v_data, v_path)
            klucz_wersji = nowa_wersja.normalized_version

            if klucz_wersji in self.versions:
                raise ValueError(f"Błąd w {v_path}: powtórzona wersja po normalizacji")
            for wymaganie in nowa_wersja.requirements + nowa_wersja.conflicts:
                if any(alt["package"] == self.normalized_name for alt in wymaganie.alternatives):
                    raise ValueError(f"Błąd w {wymaganie.path}: pakiet odwołuje się do samego siebie")
            self.versions[klucz_wersji] = nowa_wersja

    def _normalizuj_nazwe(self, nazwa):
        return normalizuj_nazwe(nazwa, self.path)

class Version:
    def __init__(self, raw_version, data_dict, path):
        self.path = path
        self.normalized_version = self._normalizuj_wersje(raw_version)
        self.requirements = []
        self.conflicts = []
        _waliduj_obiekt(data_dict, {"requires", "conflicts"}, set(), self.path)

        if "requires" in data_dict:
            if not isinstance(data_dict["requires"], list):
                raise ValueError(f"Błąd w {self.path}: 'requires' musi być listą")

            for i, req_str in enumerate(data_dict["requires"]):
                req_path = f"{self.path}.requires[{i}]"
                if not isinstance(req_str, str):
                    raise ValueError(f"Błąd w {req_path}: wymaganie musi być napisem")
                self.requirements.append(Requirement(req_str, req_path))

        if "conflicts" in data_dict:
            if not isinstance(data_dict["conflicts"], list):
                raise ValueError(f"Błąd w {self.path}: 'conflicts' musi być listą")

            for i, req_str in enumerate(data_dict["conflicts"]):
                req_path = f"{self.path}.conflicts[{i}]"
                if not isinstance(req_str, str):
                    raise ValueError(f"Błąd w {req_path}: wymaganie musi być napisem")
                konflikt = Requirement(req_str, req_path)
                if len(konflikt.alternatives) != 1:
                    raise ValueError(f"Błąd w {req_path}: konflikt musi zawierać jedno wymaganie")
                self.conflicts.append(konflikt)

    def _normalizuj_wersje(self, wersja_str):
        return normalizuj_wersje(wersja_str, self.path)

class Requirement:
    def __init__(self, raw_req_str, path):
        self.path = path
        self.alternatives = []
        if not isinstance(raw_req_str, str):
            raise ValueError(f"Błąd w {path}: wymaganie musi być napisem")
        self.tekst = raw_req_str.strip()

        for alt_str in raw_req_str.split('|'):
            self.alternatives.append(self._parsuj_pojedynczy_warunek(alt_str.strip()))

    def _parsuj_pojedynczy_warunek(self, tekst):
        dopasowanie = re.fullmatch(r"([A-Za-z0-9._-]+)\s*(.*)", tekst)
        if not dopasowanie:
            raise ValueError(f"Błąd w {self.path}: niepoprawne wymaganie {tekst!r}")

        nazwa, reszta = dopasowanie.groups()
        warunek = r"(?:==|!=|<=|>=|<|>)\s*[0-9]+(?:\.[0-9]+)*"

        if reszta and not re.fullmatch(rf"{warunek}(?:(?:\s*,\s*|\s+){warunek})*", reszta):
            raise ValueError(f"Błąd w {self.path}: niepoprawne ograniczenia {reszta!r}")

        ograniczenia = [(op, self._normalizuj_wersje(wer)) for op, wer in re.findall(r"(==|!=|<=|>=|<|>)\s*([0-9.]+)", reszta)]

        return {"package": self._normalizuj_nazwe(nazwa), "constraints": ograniczenia}

    def _normalizuj_nazwe(self, nazwa):
        return normalizuj_nazwe(nazwa, self.path)

    def _normalizuj_wersje(self, wersja_str):
        return normalizuj_wersje(wersja_str, self.path)


def wczytaj_zadania(sciezka: str | Path, tylko_nazwy: bool = False) -> list[Requirement]:
    """Wczytuje żądania z pliku, zachowując numery linii w diagnostyce.

    Raises:
        OSError: Plik jest niedostępny.
        ValueError: Linia zawiera niepoprawne żądanie.
    """
    zadania = []
    for numer, linia in enumerate(Path(sciezka).read_text(encoding="utf-8-sig").splitlines(), 1):
        tekst = linia.split('#', 1)[0].strip()

        if not tekst:
            continue

        path = f"{sciezka}, linia {numer}"
        wymaganie = Requirement(tekst, path)

        if len(wymaganie.alternatives) != 1:
            raise ValueError(f"Błąd w {path}: żądanie nie może zawierać alternatywy")

        if tylko_nazwy and wymaganie.alternatives[0]["constraints"]:
            raise ValueError(f"Błąd w {path}: oczekiwano samej nazwy pakietu")

        zadania.append(wymaganie)
    return zadania
