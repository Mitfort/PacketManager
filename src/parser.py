import json
import re
from pathlib import Path

from packaging.markers import Marker
from packaging.requirements import InvalidRequirement, Requirement as PackagingRequirement
from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version as PackagingVersion


class WersjaPyPI:
    """Reprezentacja wersji PEP 440 kompatybilna z krotkami wersji numerycznych."""

    def __init__(self, tekst: str, path: str = "wersja"):
        if not isinstance(tekst, str) or not tekst.strip():
            raise ValueError(f"Błąd w {path}: niepoprawna wersja {tekst!r}")
        try:
            self.pep440 = PackagingVersion(tekst)
        except InvalidVersion as e:
            raise ValueError(f"Błąd w {path}: niepoprawna wersja PEP 440 {tekst!r}") from e

        self.tekst = str(self.pep440)

        if (
            self.pep440.epoch == 0
            and self.pep440.pre is None
            and self.pep440.post is None
            and self.pep440.dev is None
            and self.pep440.local is None
        ):
            czesci = list(self.pep440.release)
            while len(czesci) > 1 and czesci[-1] == 0:
                czesci.pop()
            self._krotka: tuple[int, ...] | None = tuple(czesci)
        else:
            self._krotka = None

    @staticmethod
    def na_pep440(wartosc) -> PackagingVersion:
        if isinstance(wartosc, WersjaPyPI):
            return wartosc.pep440
        if isinstance(wartosc, PackagingVersion):
            return wartosc
        if isinstance(wartosc, tuple):
            return PackagingVersion(".".join(map(str, wartosc)))
        raise TypeError(f"Nieobsługiwany typ wersji: {type(wartosc)}")

    def __hash__(self) -> int:
        if self._krotka is not None:
            return hash(self._krotka)
        return hash(self.pep440)

    def __eq__(self, other) -> bool:
        if isinstance(other, WersjaPyPI):
            return self.pep440 == other.pep440
        if isinstance(other, PackagingVersion):
            return self.pep440 == other
        if isinstance(other, tuple):
            return self._krotka is not None and self._krotka == other
        return NotImplemented

    def __lt__(self, other) -> bool:
        return self.pep440 < self.na_pep440(other)

    def __le__(self, other) -> bool:
        return self.pep440 <= self.na_pep440(other)

    def __gt__(self, other) -> bool:
        return self.pep440 > self.na_pep440(other)

    def __ge__(self, other) -> bool:
        return self.pep440 >= self.na_pep440(other)

    def __iter__(self):
        yield self.tekst

    def __len__(self) -> int:
        return 1

    def __str__(self) -> str:
        return self.tekst

    def __repr__(self) -> str:
        return f"WersjaPyPI({self.tekst!r})"


def formatuj_wersje(wersja) -> str:
    """Zamienia krotkę wersji lub obiekt WersjaPyPI na napis."""
    if isinstance(wersja, WersjaPyPI):
        return wersja.tekst
    if isinstance(wersja, PackagingVersion):
        return str(wersja)
    return ".".join(map(str, wersja))


def porownaj_wersje(lewa, prawa) -> int:
    """Zwraca -1 gdy lewa < prawa, 0 gdy równe, 1 gdy lewa > prawa."""
    if isinstance(lewa, (WersjaPyPI, PackagingVersion)) or isinstance(prawa, (WersjaPyPI, PackagingVersion)):
        v1 = WersjaPyPI.na_pep440(lewa)
        v2 = WersjaPyPI.na_pep440(prawa)
        return -1 if v1 < v2 else (1 if v1 > v2 else 0)

    dlugosc = max(len(lewa), len(prawa))
    k1 = lewa + (0,) * (dlugosc - len(lewa))
    k2 = prawa + (0,) * (dlugosc - len(prawa))
    return -1 if k1 < k2 else (1 if k1 > k2 else 0)


def normalizuj_nazwe(nazwa: str, path: str = "nazwa") -> str:
    """
    Raises:
        ValueError: Nazwa zawiera niedozwolone znaki lub jest pusta.
    """
    if not isinstance(nazwa, str) or not re.fullmatch(r"[A-Za-z0-9._-]+", nazwa):
        raise ValueError(f"Błąd w {path}: niepoprawna nazwa pakietu {nazwa!r}")
    return re.sub(r"[-_.]+", "-", nazwa).lower()


def normalizuj_wersje(wersja: str, path: str = "wersja", *, pypi: bool = False) -> tuple[int, ...] | WersjaPyPI:
    """
    Raises:
        ValueError: Wersja nie jest poprawna w zadanym formacie.
    """
    if pypi:
        return WersjaPyPI(wersja, path)

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
        self.czy_pypi = isinstance(dane.get("meta"), dict) and "environment" in dane["meta"]
        self.environment = dict(dane["meta"]["environment"]) if self.czy_pypi else None

        marker_env = None
        python_ver = None
        if self.czy_pypi:
            marker_env = {**self.environment, "extra": ""}
            if "python_full_version" not in marker_env and "python_version" in marker_env:
                marker_env["python_full_version"] = f"{marker_env['python_version']}.0"
            py_str = marker_env.get("python_full_version") or marker_env.get("python_version") or "3.11"
            python_ver = PackagingVersion(py_str)

        for nazwa_pakietu, zawartosc in dane["packages"].items():
            sciezka_poczatkowa = f"packages['{nazwa_pakietu}']"
            pakiet = Package(
                nazwa_pakietu,
                zawartosc,
                sciezka_poczatkowa,
                czy_pypi=self.czy_pypi,
                marker_env=marker_env,
                python_ver=python_ver,
            )
            if pakiet.normalized_name in self.packages:
                raise ValueError(f"Błąd w {sciezka_poczatkowa}: powtórzony pakiet po normalizacji")
            self.packages[pakiet.normalized_name] = pakiet

    def _rygorystyczny_parser(self, pary_klucz_zawartosc):
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
    def __init__(
        self,
        raw_name,
        data_dict,
        path,
        *,
        czy_pypi: bool = False,
        marker_env: dict | None = None,
        python_ver: PackagingVersion | None = None,
    ):
        self.path = path
        self.normalized_name = self._normalizuj_nazwe(raw_name)
        self.versions = {}

        _waliduj_obiekt(data_dict, {"versions"}, {"versions"}, self.path)
        if not isinstance(data_dict["versions"], dict) or not data_dict["versions"]:
            raise ValueError(f"Błąd w {self.path}.versions: oczekiwano niepustego obiektu JSON")

        for v_name, v_data in data_dict["versions"].items():
            v_path = f"{self.path}.versions['{v_name}']"

            if czy_pypi:
                if not isinstance(v_data, dict):
                    raise ValueError(f"Błąd w {v_path}: oczekiwano obiektu JSON")
                req_python = v_data.get("requires_python")
                if req_python:
                    try:
                        spec_py = SpecifierSet(req_python)
                    except InvalidSpecifier as e:
                        raise ValueError(f"Błąd w {v_path}.requires_python: {e}") from e
                    if python_ver is not None and not spec_py.contains(python_ver, prereleases=True):
                        continue

                nowa_wersja = Version(
                    v_name,
                    v_data,
                    v_path,
                    czy_pypi=True,
                    marker_env=marker_env,
                    nazwa_pakietu=self.normalized_name,
                )
                self.versions[nowa_wersja.normalized_version] = nowa_wersja
            else:
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
    def __init__(
        self,
        raw_version,
        data_dict,
        path,
        *,
        czy_pypi: bool = False,
        marker_env: dict | None = None,
        nazwa_pakietu: str | None = None,
    ):
        self.path = path
        self.requirements = []
        self.conflicts = []

        if czy_pypi:
            self.normalized_version = WersjaPyPI(raw_version, self.path)
            _waliduj_obiekt(data_dict, {"requires_dist", "requires_python"}, set(), self.path)
            requires_dist = data_dict.get("requires_dist")
            if requires_dist is not None:
                if not isinstance(requires_dist, list):
                    raise ValueError(f"Błąd w {self.path}: 'requires_dist' musi być listą")
                for i, req_str in enumerate(requires_dist):
                    req_path = f"{self.path}.requires_dist[{i}]"
                    if not isinstance(req_str, str):
                        raise ValueError(f"Błąd w {req_path}: wymaganie musi być napisem")
                    wymaganie = Requirement.z_pep508(
                        req_str,
                        req_path,
                        marker_env=marker_env,
                        nazwa_pakietu=nazwa_pakietu,
                    )
                    if wymaganie is not None:
                        self.requirements.append(wymaganie)
            return

        self.normalized_version = self._normalizuj_wersje(raw_version)
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
    def __init__(self, raw_req_str, path, *, pypi: bool = False):
        self.path = path
        self.alternatives = []
        if not isinstance(raw_req_str, str):
            raise ValueError(f"Błąd w {path}: wymaganie musi być napisem")
        self.tekst = raw_req_str.strip()

        if pypi:
            for alt_str in raw_req_str.split('|'):
                alt_tekst = alt_str.strip()
                try:
                    pkg_req = PackagingRequirement(alt_tekst)
                except InvalidRequirement as e:
                    raise ValueError(f"Błąd w {path}: niepoprawne wymaganie PEP 508 {alt_tekst!r}") from e
                nazwa = normalizuj_nazwe(pkg_req.name, path)
                self.alternatives.append({"package": nazwa, "constraints": pkg_req.specifier})
            return

        for alt_str in raw_req_str.split('|'):
            self.alternatives.append(self._parsuj_pojedynczy_warunek(alt_str.strip()))

    @classmethod
    def z_pep508(
        cls,
        raw_req_str: str,
        path: str,
        *,
        marker_env: dict | None = None,
        nazwa_pakietu: str | None = None,
    ) -> "Requirement | None":
        """Tworzy wymaganie z napisu PEP 508 z uwzględnieniem markerów środowiska."""
        try:
            pkg_req = PackagingRequirement(raw_req_str)
        except InvalidRequirement as e:
            raise ValueError(f"Błąd w {path}: niepoprawne wymaganie PEP 508 {raw_req_str!r}") from e

        if pkg_req.marker is not None and marker_env is not None:
            if not pkg_req.marker.evaluate(marker_env):
                return None

        znormalizowana = normalizuj_nazwe(pkg_req.name, path)
        if nazwa_pakietu is not None and znormalizowana == nazwa_pakietu:
            return None

        obiekt = cls.__new__(cls)
        obiekt.path = path
        obiekt.tekst = f"{znormalizowana}{pkg_req.specifier}" if str(pkg_req.specifier) else znormalizowana
        obiekt.alternatives = [{"package": znormalizowana, "constraints": pkg_req.specifier}]
        return obiekt

    def _parsuj_pojedynczy_warunek(self, tekst):
        dopasowanie = re.fullmatch(r"([A-Za-z0-9._-]+)\s*(.*)", tekst)
        if not dopasowanie:
            raise ValueError(f"Błąd w {self.path}: niepoprawne wymaganie {tekst!r}")

        nazwa, reszta = dopasowanie.groups()
        warunek = r"(?:==|!=|<=|>=|<|>)\s*[0-9]+(?:\.[0-9]+)*"

        if reszta and not re.fullmatch(rf"{warunek}(?:(?:\s*,\s*|\s+){warunek})*", reszta):
            raise ValueError(f"Błąd w {self.path}: niepoprawne ograniczenia {reszta!r}")

        ograniczenia = [
            (op, self._normalizuj_wersje(wer))
            for op, wer in re.findall(r"(==|!=|<=|>=|<|>)\s*([0-9.]+)", reszta)
        ]

        return {"package": self._normalizuj_nazwe(nazwa), "constraints": ograniczenia}

    def _normalizuj_nazwe(self, nazwa):
        return normalizuj_nazwe(nazwa, self.path)

    def _normalizuj_wersje(self, wersja_str):
        return normalizuj_wersje(wersja_str, self.path)


def wczytaj_zadania(sciezka: str | Path, tylko_nazwy: bool = False, *, pypi: bool = False) -> list[Requirement]:
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
        wymaganie = Requirement(tekst, path, pypi=pypi)

        if len(wymaganie.alternatives) != 1:
            raise ValueError(f"Błąd w {path}: żądanie nie może zawierać alternatywy")

        if tylko_nazwy and wymaganie.alternatives[0]["constraints"]:
            raise ValueError(f"Błąd w {path}: oczekiwano samej nazwy pakietu")

        zadania.append(wymaganie)
    return zadania