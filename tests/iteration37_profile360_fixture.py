#!/usr/bin/env python3
"""Fixture efímero Iteración 37 para validar Perfil 360 (setup/cleanup)."""

import json
import os
import sys
import uuid
from datetime import datetime, timezone

from bson import ObjectId
from dotenv import dotenv_values
from pymongo import MongoClient


STATE_FILE = "/tmp/iteration37_profile360_fixture.json"


def env_value(key: str, fallback_file: str) -> str:
    value = os.environ.get(key)
    if value:
        return value.strip('"')
    return str(dotenv_values(fallback_file).get(key, "")).strip('"')


def db_client():
    mongo_url = env_value("MONGO_URL", "/app/backend/.env")
    db_name = env_value("DB_NAME", "/app/backend/.env")
    return MongoClient(mongo_url)[db_name]


def delete_person_related_data(database, person_ids: list[str]) -> None:
    person_ids = [item for item in person_ids if item]
    if not person_ids:
        return

    enrollment_ids = [
        item.get("enrollment_id")
        for item in database.process_enrollments.find(
            {"person_id": {"$in": person_ids}},
            {"_id": 0, "enrollment_id": 1},
        )
    ]
    enrollment_ids = [item for item in enrollment_ids if item]

    cycle_ids = [
        item.get("cycle_id")
        for item in database.process_enrollments.find(
            {"person_id": {"$in": person_ids}},
            {"_id": 0, "cycle_id": 1},
        )
    ]
    cycle_ids = [item for item in cycle_ids if item]

    database.person_baptisms.delete_many({"person_id": {"$in": person_ids}})
    database.person_memberships.delete_many({"person_id": {"$in": person_ids}})
    database.membership_events.delete_many({"person_id": {"$in": person_ids}})
    database.person_activity.delete_many({"person_id": {"$in": person_ids}})
    database.process_stage_progress.delete_many({"enrollment_id": {"$in": enrollment_ids}})
    database.process_timeline.delete_many({"enrollment_id": {"$in": enrollment_ids}})
    database.process_evidence.delete_many({"enrollment_id": {"$in": enrollment_ids}})
    database.process_alerts.delete_many({"enrollment_id": {"$in": enrollment_ids}})
    database.process_enrollments.delete_many({"person_id": {"$in": person_ids}})
    database.process_cycles.delete_many({"cycle_id": {"$in": cycle_ids}})
    database.person_contacts.delete_many({"person_id": {"$in": person_ids}})
    database.person_addresses.delete_many({"person_id": {"$in": person_ids}})
    database.person_arrivals.delete_many({"person_id": {"$in": person_ids}})
    database.person_notes.delete_many({"person_id": {"$in": person_ids}})
    database.person_attendance.delete_many({"person_id": {"$in": person_ids}})
    database.front_group_assignments.delete_many({"person_id": {"$in": person_ids}})
    database.persons.delete_many({"_id": {"$in": [ObjectId(pid) for pid in person_ids if ObjectId.is_valid(pid)]}})


def setup_fixture() -> None:
    database = db_client()
    now = datetime.now(timezone.utc)
    person_id = str(ObjectId())

    database.persons.insert_one(
        {
            "_id": ObjectId(person_id),
            "person_number": f"VV-I37{person_id[-6:].upper()}",
            "nombre": "Iter37",
            "apellido": "PerfilUI",
            "search_key": "iter37 perfil ui",
            "idempotency_key": f"qa:iter37:ui:{uuid.uuid4()}",
            "version": 1,
            "created_at": now,
            "updated_at": now,
        }
    )

    database.person_memberships.insert_one(
        {
            "membership_id": str(uuid.uuid4()),
            "person_id": person_id,
            "member_number": f"I37-{uuid.uuid4().hex[:8].upper()}",
            "status": "active",
            "legacy_membership": False,
            "acceptance_signed_at": now,
            "created_at": now,
            "updated_at": now,
        }
    )

    database.person_baptisms.insert_one(
        {
            "baptism_id": str(uuid.uuid4()),
            "person_id": person_id,
            "status": "pending",
            "baptism_date": None,
            "location": None,
            "officiant_name": None,
            "testimony": None,
            "notes": "qa:iter37:ui",
            "created_at": now,
            "updated_at": now,
        }
    )

    consolidation_id = str(uuid.uuid4())
    ley7_id = str(uuid.uuid4())
    discipleship_id = str(uuid.uuid4())
    database.process_enrollments.insert_many(
        [
            {
                "enrollment_id": consolidation_id,
                "process_key": "consolidation",
                "definition_version": 2,
                "person_id": person_id,
                "status": "active",
                "current_stage_key": "welcome_party",
                "progress_pct": 48,
                "next_action": "Completar bienvenida",
                "created_at": now,
                "updated_at": now,
            },
            {
                "enrollment_id": ley7_id,
                "process_key": "seven_weeks",
                "definition_version": 1,
                "person_id": person_id,
                "status": "active",
                "current_stage_key": "week_2",
                "progress_pct": 28,
                "next_action": "Registrar asistencia",
                "cycle_id": str(uuid.uuid4()),
                "created_at": now,
                "updated_at": now,
            },
            {
                "enrollment_id": discipleship_id,
                "process_key": "discipleship",
                "definition_version": 1,
                "person_id": person_id,
                "status": "active",
                "current_stage_key": "active",
                "progress_pct": 12,
                "next_action": "Inicio del expediente",
                "created_at": now,
                "updated_at": now,
            },
        ]
    )
    database.process_stage_progress.insert_one(
        {
            "enrollment_id": consolidation_id,
            "stage_key": "welcome_party",
            "stage_name": "Fiesta de Bienvenida",
            "stage_order": 3,
            "status": "completed",
            "completed_at": now,
            "created_at": now,
            "updated_at": now,
        }
    )

    with open(STATE_FILE, "w", encoding="utf-8") as handle:
        json.dump({"person_id": person_id}, handle)
    print(json.dumps({"person_id": person_id}))


def cleanup_fixture() -> None:
    database = db_client()
    person_ids = []
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
            person_ids.append(payload.get("person_id"))
        os.remove(STATE_FILE)

    # Limpieza explícita del fixture visual temporal indicado por el alcance.
    person_ids.append("6ab16b215f22d5ff11b70378")
    delete_person_related_data(database, person_ids)
    print(json.dumps({"cleanup": True, "person_ids": [item for item in person_ids if item]}))


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "cleanup"
    if command == "setup":
        setup_fixture()
    elif command == "cleanup":
        cleanup_fixture()
    else:
        raise SystemExit("Use setup|cleanup")
