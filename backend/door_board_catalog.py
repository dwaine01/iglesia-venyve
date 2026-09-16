"""Catálogo institucional versionado para Puertas y Junta Directiva."""
from datetime import datetime, timezone

BOARD_ID = "board_directiva_principal"

POSITIONS = [
    ("president", "Presidente/a o Pastor Principal", 10, True),
    ("vice_president", "Vicepresidente/a", 20, True),
    ("secretary", "Secretario/a", 30, True),
    ("treasurer", "Tesorero/a", 40, True),
    ("vocal", "Vocal", 50, True),
    ("member", "Miembro", 60, True),
]

DOOR_DETAILS = {
    "door_1": {"purpose": "Cubrir espiritualmente la iglesia, sus líderes, células y Personas.", "biblical_reference": "Puerta de la Fuente · Nehemías 3:15"},
    "door_2": {"purpose": "Recibir, consolidar e integrar a nuevos creyentes.", "biblical_reference": "Puerta del Pescado · Nehemías 3:3"},
    "door_3": {"purpose": "Responder a cuidado pastoral y consejería inmediata.", "biblical_reference": "Puerta de las Ovejas · Nehemías 3:1‑2"},
    "door_4": {"purpose": "Facilitar retiros, restauración, liberación, bendición y sanidad.", "biblical_reference": "Puerta del Valle · Nehemías 3:13"},
    "door_5": {"purpose": "Formar creyentes mediante discipulado y mentoría.", "biblical_reference": "Puerta Vieja · Nehemías 3:6"},
    "door_6": {"purpose": "Extender cuidado y visitación pastoral fuera del templo.", "biblical_reference": "Puerta del Muladar · Nehemías 3:14"},
    "door_7": {"purpose": "Comunicar y multiplicar el mensaje con tecnología y medios.", "biblical_reference": "Puerta de las Aguas · Nehemías 3:26"},
    "door_8": {"purpose": "Sostener administración, recursos y materiales ministeriales.", "biblical_reference": "Puerta del Caballo · Nehemías 3:28"},
    "door_9": {"purpose": "Coordinar congresos, eventos y entrenamientos especiales.", "biblical_reference": "Puerta Oriental · Nehemías 3:29"},
}

AGENDA_TEMPLATE = ["Apertura", "Lectura de minuta anterior", "Finanzas", "Sistema Celular", "9 Puertas", "Eventos", "Pro‑Templo", "Asuntos nuevos", "Votaciones", "Cierre"]


async def seed_door_board_catalog(db) -> None:
    now = datetime.now(timezone.utc)
    await db.governance_boards.update_one(
        {"board_id": BOARD_ID},
        {"$setOnInsert": {"_id": BOARD_ID, "board_id": BOARD_ID, "name": "Junta Directiva", "status": "active", "quorum_rule": {"type": "percentage", "value": 50, "rounding": "ceil"}, "voting_rule": {"type": "simple_majority", "tie": "presiding_vote"}, "agenda_template": AGENDA_TEMPLATE, "created_at": now}, "$set": {"updated_at": now}},
        upsert=True,
    )
    for key, name, order, voting_default in POSITIONS:
        await db.board_position_catalog.update_one(
            {"position_key": key},
            {"$setOnInsert": {"_id": key, "position_key": key, "name": name, "order": order, "voting_default": voting_default, "active": True, "created_at": now}, "$set": {"updated_at": now}},
            upsert=True,
        )
    for door_key, detail in DOOR_DETAILS.items():
        await db.door_catalog.update_one({"door_key": door_key}, {"$set": {**detail, "version": 2, "updated_at": now}})