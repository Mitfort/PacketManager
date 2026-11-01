import json
from pathlib import Path

import pytest

from src.parser import Repozytorium, Requirement, wczytaj_zadania


def test_normalizacja_repozytorium_i_wymagan():
    # Arrange
    dane = {"packages": {
        "Foo__..Bar": {"versions": {"1.0.0": {}}},
        "app": {"versions": {"2.0": {"requires": ["foo-bar >=1.0, < 2.0"]}}},
    }}

    # Act
    repo = Repozytorium(json.dumps(dane))

    # Assert
    assert set(repo.packages) == {"foo-bar", "app"}
    assert set(repo.packages["foo-bar"].versions) == {(1,)}
    wymaganie = repo.packages["app"].versions[(2,)].requirements[0]
    assert wymaganie.tekst == "foo-bar >=1.0, < 2.0"
    assert wymaganie.alternatives == [{"package": "foo-bar", "constraints": [(">=", (1,)), ("<", (2,))]}]


@pytest.mark.parametrize("tekst,sciezka", [
    ('[]', "repozytorium"),
    ('{}', "repozytorium"),
    ('{"packages": []}', "packages"),
    ('{"packages": {}, "other": 1}', "other"),
    ('{"packages": {"bad/name": {"versions": {"1": {}}}}}', "bad/name"),
    ('{"packages": {"app": []}}', "packages['app']"),
    ('{"packages": {"app": {}}}', "packages['app']"),
    ('{"packages": {"app": {"versions": []}}}', "versions"),
    ('{"packages": {"app": {"versions": {}}}}', "versions"),
    ('{"packages": {"app": {"versions": {"1": {}}, "other": 0}}}', "other"),
    ('{"packages": {"app": {"versions": {"-1": {}}}}}', "-1"),
    ('{"packages": {"app": {"versions": {"1.a": {}}}}}', "1.a"),
    ('{"packages": {"app": {"versions": {"1": []}}}}', "versions['1']"),
    ('{"packages": {"app": {"versions": {"1": {"other": 0}}}}}', "other"),
    ('{"packages": {"app": {"versions": {"1": {"requires": "lib"}}}}}', "versions['1']"),
    ('{"packages": {"app": {"versions": {"1": {"requires": [2]}}}}}', "requires[0]"),
    ('{"packages": {"app": {"versions": {"1": {"requires": ["app"]}}}}}', "requires[0]"),
    ('{"packages": {"app": {"versions": {"1": {"conflicts": ["APP"]}}}}}', "conflicts[0]"),
    ('{"packages": {"app": {"versions": {"1": {"conflicts": ["x | y"]}}}}}', "conflicts[0]"),
    ('{"packages": {"Foo_Bar": {"versions": {"1": {}}}, "foo.bar": {"versions": {"1": {}}}}}', "foo.bar"),
    ('{"packages": {"app": {"versions": {"1.0": {}, "1.0.0": {}}}}}', "1.0.0"),
    ('{"packages": {"app": {"versions": {"1": {}, "1": {}}}}}', "packages['app']['versions']['1']"),
    ('{"packages": {}, "packages": {}}', "packages"),
])
def test_odrzucanie_repozytoriow_z_miejscem_bledu(tekst, sciezka):
    # Act
    with pytest.raises(ValueError) as blad:
        Repozytorium(tekst)

    # Assert
    assert sciezka in str(blad.value)


def test_blad_skladni_json_ma_numer_linii():
    # Act / Assert
    with pytest.raises(ValueError, match="linii 2"):
        Repozytorium('{"packages": {\ninvalid}')


@pytest.mark.parametrize("tekst", ["", "x |", "|x", "x || y", "x=1", "x ~=1", "x >=-1", "x >=", "x >=1,", "x >=1,,<2", "x >=1<2", "x/other", "x ==1.a"])
def test_odrzucanie_niepoprawnych_wymagan(tekst):
    # Act / Assert
    with pytest.raises(ValueError, match="test-path"):
        Requirement(tekst, "test-path")


@pytest.mark.parametrize("tekst", ["lib==2.0", "lib == 2.0", "lib>=1.0 <2.0", "lib >=1.0,< 2.0", "json-fast | json-slow >=1.0"])
def test_dozwolona_skladnia_wymagan(tekst):
    # Act
    wymaganie = Requirement(tekst, "test")

    # Assert
    assert wymaganie.tekst == tekst
    assert wymaganie.alternatives


def test_wczytywanie_zadan_z_komentarzami(tmp_path):
    # Arrange
    plik = tmp_path / "zadania.txt"
    plik.write_text("\ufeff# komentarz\n\nFoo_Bar >= 1.0 # uwaga\nlib\n", encoding="utf-8")

    # Act
    zadania = wczytaj_zadania(plik)

    # Assert
    assert [x.tekst for x in zadania] == ["Foo_Bar >= 1.0", "lib"]
    assert zadania[0].alternatives[0]["package"] == "foo-bar"
    assert "linia 3" in zadania[0].path


@pytest.mark.parametrize("tekst,tylko_nazwy", [("bad >=", False), ("app | tool", False), ("app >=1", True)])
def test_bledne_zadanie_ma_numer_linii(tmp_path, tekst, tylko_nazwy):
    # Arrange
    plik = tmp_path / "zadania.txt"
    plik.write_text(f"# komentarz\n\n{tekst}\n", encoding="utf-8")

    # Act / Assert
    with pytest.raises(ValueError, match="linia 3"):
        wczytaj_zadania(plik, tylko_nazwy)


@pytest.mark.parametrize("rozmiar", [10, 30, 100, 200, 300, 1000])
def test_repozytoria_grupy_sa_obslugiwane(rozmiar):
    # Arrange
    plik = Path(__file__).resolve().parents[1] / "repos" / "k05" / f"repo_{rozmiar}.json"

    # Act
    repo = Repozytorium(plik.read_text(encoding="utf-8"))

    # Assert
    assert len(repo.packages) == rozmiar
