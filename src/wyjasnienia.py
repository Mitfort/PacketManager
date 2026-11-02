"""Wyznaczanie sprzecznego rdzenia minimalnego względem zawierania."""
import z3
from src.parser import Requirement


def wyjasnij(
    baza,
    zadania: list[Requirement],
    dodatkowe_warunki: list[tuple[str, z3.ExprRef]] | None = None,
) -> list[str]:
    aksjomaty = list(baza.aksjomaty)

    for zadanie in zadania:
        aksjomaty.append((f"Żądanie: {zadanie.tekst}", baza.formula_zadania(zadanie)))

    if dodatkowe_warunki:
        aksjomaty.extend(dodatkowe_warunki)

    solver = z3.Solver()
    znaczniki = [z3.FreshBool("rdzen") for _ in aksjomaty]

    for znacznik, (_, formula) in zip(znaczniki, aksjomaty):
        solver.add(z3.Implies(znacznik, formula))

    status = solver.check(*znaczniki)

    if status == z3.sat:
        return []

    if status != z3.unsat:
        raise RuntimeError(f"Solver nie rozstrzygnął wyjaśnienia: {solver.reason_unknown()}")

    # Z3 zwraca sprzeczny rdzeń; sprawdzamy minimalność przez usuwanie elementów.
    rdzen = list(solver.unsat_core())

    for znacznik in list(rdzen):
        bez_elementu = [element for element in rdzen if not element.eq(znacznik)]
        status = solver.check(*bez_elementu)

        if status == z3.unsat:
            rdzen = bez_elementu
        elif status != z3.sat:
            raise RuntimeError(f"Solver nie rozstrzygnął minimalności: {solver.reason_unknown()}")

    wybrane = {znacznik.get_id() for znacznik in rdzen}
    etykiety = []

    for znacznik, (etykieta, _) in zip(znaczniki, aksjomaty):
        if znacznik.get_id() in wybrane:
            etykiety.append(etykieta)

    return etykiety