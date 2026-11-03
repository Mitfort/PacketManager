"""Stan środowiska, plik stanu i plan zmian."""
from pathlib import Path
from src.parser import WersjaPyPI, formatuj_wersje, normalizuj_nazwe, normalizuj_wersje, porownaj_wersje


class Stan:
    def __init__(
        self,
        pakiety: dict[str, tuple[int, ...] | WersjaPyPI] | None = None,
        reczne: set[str] | None = None,
    ):
        self.pakiety = dict(pakiety or {})
        self.reczne = set(reczne or ())

        if not self.reczne <= self.pakiety.keys():
            raise ValueError("Pakiety ręczne muszą należeć do stanu")

    @classmethod
    def wczytaj(cls, sciezka: str | Path, *, pypi: bool = False) -> "Stan":
        pakiety = {}
        reczne = set()
        linie = Path(sciezka).read_text(encoding="utf-8-sig").splitlines()

        for numer, linia in enumerate(linie, 1):
            pola = linia.split("#", 1)[0].split()

            if not pola:
                continue

            miejsce = f"{sciezka}, linia {numer}"

            if len(pola) not in (2, 3) or (len(pola) == 3 and pola[2] != "manual"):
                raise ValueError(f"{miejsce}: oczekiwano NAZWA WERSJA [manual]")

            nazwa = normalizuj_nazwe(pola[0], miejsce)
            wersja = normalizuj_wersje(pola[1], miejsce, pypi=pypi)

            if nazwa in pakiety:
                raise ValueError(f"{miejsce}: powtórzony pakiet {nazwa}")

            pakiety[nazwa] = wersja

            if len(pola) == 3:
                reczne.add(nazwa)

        return cls(pakiety, reczne)

    def zapisz(self, sciezka: str | Path) -> None:
        Path(sciezka).write_text(self.tekst(), encoding="utf-8")

    def tekst(self) -> str:
        linie = []

        for nazwa, wersja in sorted(self.pakiety.items()):
            numer_wersji = formatuj_wersje(wersja)
            oznaczenie = " manual" if nazwa in self.reczne else ""
            linie.append(f"{nazwa} {numer_wersji}{oznaczenie}\n")

        return "".join(linie)

    def plan(self, nowy: "Stan") -> list[str]:
        zmiany = []

        for nazwa in sorted(self.pakiety.keys() | nowy.pakiety.keys()):
            przed = self.pakiety.get(nazwa)
            po = nowy.pakiety.get(nazwa)

            if przed == po:
                continue

            stara = formatuj_wersje(przed) if przed is not None else ""
            nowa = formatuj_wersje(po) if po is not None else ""

            if przed is None:
                zmiany.append(f"Instalacja: {nazwa} {nowa}")
            elif po is None:
                zmiany.append(f"Usunięcie: {nazwa} {stara}")
            else:
                rodzaj = "Podniesienie" if porownaj_wersje(po, przed) > 0 else "Obniżenie"
                zmiany.append(f"{rodzaj} wersji: {nazwa} {stara} -> {nowa}")

        return zmiany