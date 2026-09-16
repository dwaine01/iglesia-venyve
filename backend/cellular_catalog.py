"""Catálogos configurables y reglas iniciales del Sistema Celular."""
from datetime import datetime, timezone


INITIAL_NETWORKS = [
    ("damas", "Damas"),
    ("caballeros", "Caballeros"),
    ("jovenes", "Jóvenes"),
    ("parejas_familias", "Parejas / Familias"),
]

NEED_DOOR_MAP = {
    "illness": "door_6",
    "urgent_prayer": "door_1",
    "crisis": "door_3",
    "new_believer": "door_5",
    "special_event": "door_9",
    "first_visit": "door_2",
}


async def seed_cellular_catalog(db) -> None:
    now = datetime.now(timezone.utc)
    for key, name in INITIAL_NETWORKS:
        await db.cell_networks.update_one(
            {"network_key": key, "source": "institutional_catalog"},
            {"$setOnInsert": {
                "_id": key,
                "network_id": key,
                "network_key": key,
                "name": name,
                "description": None,
                "campus_id": None,
                "status": "active",
                "source": "institutional_catalog",
                "created_at": now,
                "updated_at": now,
            }},
            upsert=True,
        )
    await db.cell_multiplication_rules.update_one(
        {"rule_key": "default"},
        {"$setOnInsert": {
            "_id": "default",
            "rule_key": "default",
            "name": "Criterio inicial de multiplicación",
            "min_active_members": 10,
            "target_members": 15,
            "min_stable_meetings": 8,
            "min_average_attendance": 10,
            "requires_leader_in_training": True,
            "requires_new_host": True,
            "enabled": True,
            "created_at": now,
            "updated_at": now,
        }},
        upsert=True,
    )