"""Quién cuenta como PARTICIPANTE (regla del dueño, un solo lugar).

La autoridad principal —pastor o pastora general (`is_global_pastoral_authority`)—
supervisa y administra, pero no participa como mentora ni como integrante del
equipo operativo. Por eso queda fuera de:
- el roster de mentores/colaboradores que deben confirmar asistencia;
- los conteos de participantes y las métricas de oración, visitas, personas
  alcanzadas y actividad en la calle;
- comparaciones, clasificaciones, rankings y gráficas de desempeño individual.

Sigue pudiendo crear y administrar todo y consultar todos los reportes; su
actividad administrativa queda en la auditoría, nunca como participación.

Caso NO decidido aquí (pendiente del dueño): un coordinador general que además
es mentor activo SÍ se cuenta como participante."""
from typing import Iterable


async def principal_authority_person_ids(db) -> set[str]:
    """Person_id de las cuentas activas con autoridad pastoral principal."""
    from access_control import is_global_pastoral_authority

    users = await db.users.find(
        {"person_id": {"$nin": [None, ""]}, "is_active": {"$ne": False}},
        {"_id": 0, "person_id": 1, "rol": 1, "role": 1, "access_level": 1},
    ).to_list(20000)
    return {user["person_id"] for user in users if is_global_pastoral_authority(user)}


def without(person_ids: Iterable[str], excluded: set[str]) -> list[str]:
    """Quita a las autoridades de una lista conservando el orden."""
    return [person_id for person_id in person_ids if person_id and person_id not in excluded]


async def participants_only(db, person_ids: Iterable[str]) -> list[str]:
    return without(person_ids, await principal_authority_person_ids(db))
