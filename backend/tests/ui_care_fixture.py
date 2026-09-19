"""Fixture efímero para inspección visual local de Cuidado Pastoral."""
import asyncio
import sys
import uuid
from pathlib import Path
from datetime import datetime, timedelta, timezone

import bcrypt
from bson import ObjectId

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import server
from access_control import access_defaults_for_role
from care_alerts import evaluate_care_alerts
from care_service import assign_case, create_case_record, create_note, create_op72, create_visit, ensure_care_indexes


EMAIL = "care.ui.pastor@example.com"
LEADER_EMAIL = "care.ui.leader@example.com"
PERSONA_EMAIL = "care.ui.persona@example.com"
PASSWORD = "CareVisual2026!"


async def cleanup():
    users = await server.db.users.find({"email": {"$in": [EMAIL, LEADER_EMAIL, PERSONA_EMAIL]}}, {"_id": 1, "person_id": 1}).to_list(10)
    person_ids = [item["person_id"] for item in users]
    extras = await server.db.persons.find({"idempotency_key": {"$regex": "^care:ui:"}}, {"_id": 1}).to_list(20)
    person_ids += [str(item["_id"]) for item in extras]
    cases = await server.db.pastoral_cases.find({"person_id": {"$in": person_ids}}, {"_id": 0, "case_id": 1}).to_list(100)
    case_ids = [item["case_id"] for item in cases]
    visits = await server.db.pastoral_visitation_participants.distinct("visit_id", {"person_id": {"$in": person_ids}})
    for collection in ["pastoral_case_assignments", "pastoral_contact_attempts", "pastoral_case_notes", "care_alerts"]:
        await server.db[collection].delete_many({"case_id": {"$in": case_ids}})
    await server.db.op72_records.delete_many({"person_id": {"$in": person_ids}}); await server.db.pastoral_cases.delete_many({"case_id": {"$in": case_ids}})
    await server.db.care_audit_events.delete_many({"$or": [{"entity_id": {"$in": case_ids + visits}}, {"actor_user_id": {"$in": [str(item["_id"]) for item in users]}}]})
    await server.db.pastoral_visitation_summaries.delete_many({"visit_id": {"$in": visits}}); await server.db.pastoral_visitation_participants.delete_many({"visit_id": {"$in": visits}}); await server.db.pastoral_visitations.delete_many({"visit_id": {"$in": visits}})
    household_ids = await server.db.household_memberships.distinct("household_id", {"person_id": {"$in": person_ids}})
    await server.db.household_memberships.delete_many({"person_id": {"$in": person_ids}}); await server.db.households.delete_many({"_id": {"$in": household_ids}})
    enrollment_ids = await server.db.process_enrollments.distinct("enrollment_id", {"person_id": {"$in": person_ids}, "source": "care_op72"})
    for collection in ["process_stage_progress", "process_timeline", "process_evidence", "process_alerts"]: await server.db[collection].delete_many({"enrollment_id": {"$in": enrollment_ids}})
    await server.db.process_enrollments.delete_many({"enrollment_id": {"$in": enrollment_ids}})
    await server.db.persons.delete_many({"_id": {"$in": [ObjectId(item) for item in set(person_ids)]}}); await server.db.users.delete_many({"_id": {"$in": [item["_id"] for item in users]}})


async def person(name, email=None, role=None):
    person_id = ObjectId(); user_id = ObjectId() if email else None; now = datetime.now(timezone.utc)
    person_doc = {"_id": person_id, "person_number": f"VV-UI{str(person_id)[-6:].upper()}", "nombre": name, "apellido": "Cuidado", "search_key": f"{name} cuidado".lower(), "idempotency_key": f"care:ui:{person_id}", "version": 1, "created_at": now, "updated_at": now}
    if user_id: person_doc["auth_user_id"] = str(user_id)
    await server.db.persons.insert_one(person_doc)
    if email:
        await server.db.users.insert_one({"_id": user_id, "nombre": name, "email": email, "password": bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt()).decode(), "rol": role, "person_id": str(person_id), "is_active": True, "token_version": 1, **access_defaults_for_role(role)})
    return {"person_id": str(person_id), "user_id": str(user_id) if user_id else None}


async def seed():
    await cleanup(); await ensure_care_indexes(server.db)
    pastor = await person("Pastora Abigail", EMAIL, "pastor"); leader = await person("Líder Mateo", LEADER_EMAIL, "lider"); cared = await person("María Fernanda de los Ángeles", PERSONA_EMAIL, "persona"); relative = await person("José Alejandro")
    actor = {"user_id": pastor["user_id"], "person_id": pastor["person_id"], "rol": "pastor", **access_defaults_for_role("pastor")}
    op72, _ = await create_op72(server.db, {"person_id": cared["person_id"], "decision_at": datetime.now(timezone.utc) - timedelta(days=4), "source_type": "manual", "source_id": "care-ui-op72"}, actor)
    case = await server.db.pastoral_cases.find_one({"case_id": op72["case_id"]}, {"_id": 0})
    await assign_case(server.db, case, {"assignee_person_id": leader["person_id"], "assignment_role": "primary", "reason": "Seguimiento inmediato"}, actor)
    await create_note(server.db, case, "Contexto pastoral cifrado de prueba visual. Esta nota nunca debe aparecer fuera de la bóveda.", "pastoral_core", actor)
    urgent = await create_case_record(server.db, {"person_id": relative["person_id"], "case_type": "restoration", "priority": "urgent", "source_type": "manual", "source_id": "care-ui-urgent", "household_id": None, "operational_summary": "Seguimiento urgente con descripción operacional deliberadamente extensa para validar saltos de línea, densidad y comportamiento responsive sin revelar contenido confidencial.", "next_step": "Coordinar intervención con autoridad pastoral y equipo asignado", "next_step_at": datetime.now(timezone.utc) - timedelta(hours=3)}, actor)
    await assign_case(server.db, urgent, {"assignee_person_id": leader["person_id"], "assignment_role": "primary", "reason": "Cobertura"}, actor)
    household_id = str(uuid.uuid4()); now = datetime.now(timezone.utc)
    await server.db.households.insert_one({"_id": household_id, "nombre_hogar": "Hogar Familia Cuidado", "created_by": pastor["user_id"], "created_at": now, "updated_at": now})
    await server.db.household_memberships.insert_many([{"_id": str(uuid.uuid4()), "household_id": household_id, "person_id": cared["person_id"], "created_at": now}, {"_id": str(uuid.uuid4()), "household_id": household_id, "person_id": relative["person_id"], "created_at": now}])
    await create_visit(server.db, {"household_id": household_id, "participants": [{"person_id": cared["person_id"], "case_id": case["case_id"]}, {"person_id": relative["person_id"], "case_id": urgent["case_id"]}], "scheduled_at": now + timedelta(days=1), "lead_visitor_person_id": pastor["person_id"], "visitor_person_ids": [leader["person_id"]], "purpose": "Visita familiar de acompañamiento y definición de próximos pasos individuales"}, actor)
    await evaluate_care_alerts(server.db)
    print(f"EMAIL={EMAIL}\nPASSWORD={PASSWORD}\nCASE_ID={case['case_id']}")


asyncio.run(cleanup() if len(sys.argv) > 1 and sys.argv[1] == "cleanup" else seed())