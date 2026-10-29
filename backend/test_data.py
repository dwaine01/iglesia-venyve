"""Datos de prueba: marca `is_test`, inventario de solo lectura y archivo de invasiones (auditoría 8/10).

Nada se borra. El inventario solo LISTA candidatos (correos y nombres de prueba, restos de la
demostración antigua, invasiones «de prueba»). Marcar `is_test` saca a esa persona o invasión de
todas las cifras (vía `report_period.excluded_person_ids` y los filtros de invasiones) y se puede
quitar con otro toque. Archivar una invasión también se puede deshacer. Cada cambio queda en
`test_data_marks` (quién, cuándo, qué había antes y por qué)."""
import re
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from access_control import is_global_pastoral_authority
from report_period import TEST_HINT, require_manager
from server import db, get_current_user

router = APIRouter(prefix="/api/test-data", tags=["test-data"])

NAME_HINT = re.compile(r"\b(prueba|pruebas|test|qa|demo|e2e|fixture|ficticio|ficticia)\b", re.IGNORECASE)
LIMIT = 500


def _name(doc: dict) -> str:
    return " ".join(filter(None, [doc.get("nombre"), doc.get("apellido")])) or "Persona"


async def inventory() -> dict:
    """Candidatos a datos de prueba. SOLO LECTURA: no escribe nada."""
    reasons: dict[str, set] = {}

    def add(person_id, reason):
        if person_id and ObjectId.is_valid(str(person_id)):
            reasons.setdefault(str(person_id), set()).add(reason)

    async for user in db.users.find({"person_id": {"$nin": [None, ""]}}, {"_id": 0, "person_id": 1, "email": 1, "demo": 1}):
        if TEST_HINT.search(user.get("email") or ""):
            add(user["person_id"], f"Correo de prueba ({user.get('email')})")
        if user.get("demo"):
            add(user["person_id"], "Cuenta de la demostración antigua")
    async for doc in db.people.find({"demo": True, "canonical_person_id": {"$nin": [None, ""]}}, {"_id": 0, "canonical_person_id": 1}):
        add(doc["canonical_person_id"], "Persona de la demostración antigua (Manual)")
    async for doc in db.persons.find({"$or": [{"demo": True}, {"is_test": True}, {"nombre": {"$regex": NAME_HINT.pattern, "$options": "i"}},
                                              {"apellido": {"$regex": NAME_HINT.pattern, "$options": "i"}}]}, {"_id": 1, "demo": 1, "is_test": 1}):
        add(str(doc["_id"]), "Ya marcada como prueba" if doc.get("is_test") else ("Marcada demo" if doc.get("demo") else "Nombre de prueba"))
    await _more_candidates(add, reasons)
    # «Es persona real» (confirmado por el pastor): ya no se sugiere como prueba; se lista aparte para poder quitar la marca.
    confirmed = [{"person_id": str(doc["_id"]), "name": _name(doc), "person_number": doc.get("person_number"),
                  "confirmed_at": doc["confirmed_real"].get("at").isoformat() if isinstance(doc["confirmed_real"].get("at"), datetime) else None,
                  "reason": doc["confirmed_real"].get("reason")}
                 async for doc in db.persons.find({"confirmed_real.active": True}, {"nombre": 1, "apellido": 1, "person_number": 1, "confirmed_real": 1})]
    for row in confirmed:
        reasons.pop(row["person_id"], None)
    oids = [ObjectId(pid) for pid in list(reasons)[:LIMIT * 2]]
    persons = {str(doc["_id"]): doc async for doc in db.persons.find({"_id": {"$in": oids}}, {"nombre": 1, "apellido": 1, "is_test": 1, "is_archived": 1, "person_number": 1})}
    people_rows = sorted(({"person_id": pid, "name": _name(doc), "person_number": doc.get("person_number"), "is_test": bool(doc.get("is_test")),
                           "is_archived": bool(doc.get("is_archived")), "reasons": sorted(reasons[pid])} for pid, doc in persons.items()),
                         key=lambda row: (row["is_test"], row["name"].lower()))[:LIMIT]
    campaigns = [{"campaign_id": doc["campaign_id"], "name": doc.get("name") or "Invasión", "start_date": doc.get("start_date"), "is_test": bool(doc.get("is_test")),
                  "archived": bool(doc.get("archived")), "reasons": ["Ya marcada como prueba"] if doc.get("is_test") else ["Nombre de prueba"]}
                 async for doc in db.outreach_campaigns.find({"$or": [{"is_test": True}, {"name": {"$regex": NAME_HINT.pattern, "$options": "i"}}]},
                                                             {"_id": 0, "campaign_id": 1, "name": 1, "start_date": 1, "is_test": 1, "archived": 1}).limit(LIMIT)]
    # Finanzas F1: contribuciones a nombre de personas candidatas o marcadas (solo total, sin nombres ni montos por persona).
    finance_ids = [row["person_id"] for row in people_rows]
    finance_rows = await db.finance_contributions.aggregate([
        {"$match": {"person_id": {"$in": finance_ids}, "status": {"$ne": "corrected"}}}, {"$group": {"_id": None, "count": {"$sum": 1}, "cents": {"$sum": "$amount_cents"}}}]).to_list(1) if finance_ids else []
    return {
        "finance_contributions": {"count": finance_rows[0]["count"] if finance_rows else 0, "amount_cents": finance_rows[0]["cents"] if finance_rows else 0},
        "people": people_rows, "campaigns": campaigns, "confirmed_real": confirmed,
        "visitor_registrations_marked": await db.visitor_registrations.count_documents({"test_data": True}),
        "counts": {"people": len(people_rows), "people_marked": sum(1 for row in people_rows if row["is_test"]),
                   "campaigns": len(campaigns), "campaigns_marked": sum(1 for row in campaigns if row["is_test"])},
        "note": "Solo lectura. Marcar como prueba saca a la persona o invasión de las cifras; no borra nada y se puede quitar.",
    }


SYSTEM_HINT = re.compile(r"\b(admin|administrador|sistema|system|root|soporte)\b", re.IGNORECASE)
LINK_COLLECTIONS = (("person_contacts", "person_id"), ("household_memberships", "person_id"), ("process_enrollments", "person_id"), ("person_attendance", "person_id"),
                    ("finance_contributions", "person_id"), ("outreach_visits", "person_id"), ("outreach_visits", "converted_person_id"), ("person_relationships", "person_id"),
                    ("person_relationships", "related_person_id"), ("ministry_assignments", "person_id"), ("mentor_badges", "person_id"), ("person_memberships", "person_id"))


async def _more_candidates(add, reasons: dict) -> None:
    """Revisión de producción: más candidatas, SOLO para revisar a mano (nada se marca solo).
    - cuentas del sistema (rol admin/superadmin, o «admin» en el nombre o el correo);
    - correos de prueba también cuando la persona está enlazada por persons.auth_user_id;
    - registros sueltos: sin teléfono ni correo, sin cuenta y sin ningún vínculo real;
    - dos personas con el mismo teléfono, nombres distintos, creadas el mismo día;
    - creadas sin teléfono en un día en que se crearon 3 o más registros de prueba."""
    from report_period import TEST_HINT
    users = {str(user["_id"]): user async for user in db.users.find({}, {"_id": 1, "person_id": 1, "email": 1, "nombre": 1, "rol": 1, "role": 1})}
    linked = {}
    async for person in db.persons.find({"auth_user_id": {"$nin": [None, ""]}}, {"_id": 1, "auth_user_id": 1}):
        linked[str(person["_id"])] = users.get(str(person["auth_user_id"]))
    for user in users.values():
        if user.get("person_id"):
            linked.setdefault(user["person_id"], user)
    for person_id, user in linked.items():
        if not user:
            continue
        roles = {str(user.get("rol") or "").lower(), str(user.get("role") or "").lower()}
        if roles & {"admin", "superadmin"} or SYSTEM_HINT.search(user.get("nombre") or "") or SYSTEM_HINT.search((user.get("email") or "").split("@")[0]):
            add(person_id, "Cuenta del sistema (admin)")
        if TEST_HINT.search(user.get("email") or ""):
            add(person_id, f"Correo de prueba ({user.get('email')})")
    # Registros sueltos (sin teléfono, correo, cuenta ni vínculo alguno).
    with_links = set(linked)
    for collection, field in LINK_COLLECTIONS:
        with_links |= {str(value) for value in await db[collection].distinct(field) if value}
    created_by_day: dict[str, list] = {}
    async for person in db.persons.find({"is_archived": {"$ne": True}}, {"_id": 1, "created_at": 1, "nombre": 1, "apellido": 1}):
        person_id = str(person["_id"])
        if person_id not in with_links:
            add(person_id, "Registro suelto: sin teléfono ni correo, sin cuenta y sin ningún vínculo")
        if isinstance(person.get("created_at"), datetime):
            created_by_day.setdefault(person["created_at"].date().isoformat(), []).append(person_id)
    day_of = {pid: day for day, ids in created_by_day.items() for pid in ids}
    # Mismo teléfono, nombres distintos, creadas el mismo día (como una prueba hecha en la tableta).
    phones = set(await db.person_contacts.distinct("person_id", {"tipo": "telefono"}))
    async for row in db.person_contacts.aggregate([{"$match": {"tipo": "telefono", "valor_normalizado": {"$nin": [None, ""]}}},
                                                   {"$group": {"_id": "$valor_normalizado", "ids": {"$addToSet": "$person_id"}}}, {"$match": {"ids.1": {"$exists": True}}}]):
        days: dict[str, list] = {}
        for pid in row["ids"]:
            if day_of.get(pid):
                days.setdefault(day_of[pid], []).append(pid)
        for day, ids in days.items():
            if len(ids) > 1:
                for pid in ids:
                    add(pid, f"Mismo teléfono ({row['_id']}) que otra persona creada el mismo día ({day})")
    # Días de pruebas: 3 o más candidatas creadas ese día; las demás de ese día SIN teléfono, a revisar.
    flagged_days: dict[str, int] = {}
    for pid in list(reasons):
        if day_of.get(pid):
            flagged_days[day_of[pid]] = flagged_days.get(day_of[pid], 0) + 1
    for day, count in flagged_days.items():
        if count >= 3:
            for pid in created_by_day.get(day, []):
                if pid not in reasons and pid not in phones:
                    add(pid, f"Creada sin teléfono el {day}, día en que se crearon {count} registros de prueba")


@router.get("/inventory", response_model=dict)
async def get_inventory(current_user: dict = Depends(get_current_user)):
    require_manager(current_user)
    return await inventory()


class MarkInput(BaseModel):
    kind: Literal["person", "campaign"]
    ids: list[str] = Field(min_length=1, max_length=200)
    is_test: bool
    reason: str = Field(min_length=3, max_length=300)


async def _log(kind: str, target_id: str, field: str, before, after, reason: str, current_user: dict) -> None:
    await db.test_data_marks.insert_one({"mark_id": str(uuid4()), "kind": kind, "target_id": target_id, "field": field, "before": before, "after": after,
                                         "reason": reason, "by_user_id": current_user["user_id"], "at": datetime.now(timezone.utc)})


@router.post("/mark", response_model=dict)
async def mark(payload: MarkInput, current_user: dict = Depends(get_current_user)):
    """Pone o quita la marca `is_test` (reversible; queda en el historial)."""
    require_manager(current_user)
    now = datetime.now(timezone.utc)
    stamp = {"is_test": payload.is_test, "is_test_marked_by": current_user["user_id"], "is_test_marked_at": now, "is_test_reason": payload.reason}
    if payload.kind == "person" and payload.is_test:
        oids = [ObjectId(item) for item in payload.ids if ObjectId.is_valid(item)]
        real = [_name(doc) async for doc in db.persons.find({"_id": {"$in": oids}, "confirmed_real.active": True}, {"nombre": 1, "apellido": 1})]
        if real:
            raise HTTPException(status_code=409, detail=f"No se marcó nada: {', '.join(real)} está confirmada como persona real. Para marcarla como prueba, el pastor debe quitar antes esa marca.")
    changed = 0
    for target in dict.fromkeys(payload.ids):
        if payload.kind == "person":
            if not ObjectId.is_valid(target):
                continue
            collection, query = db.persons, {"_id": ObjectId(target)}
        else:
            collection, query = db.outreach_campaigns, {"campaign_id": target}
        before = await collection.find_one(query, {"is_test": 1})
        if before is None:
            continue
        if bool(before.get("is_test")) != payload.is_test:
            await collection.update_one(query, {"$set": stamp})
            await _log(payload.kind, target, "is_test", bool(before.get("is_test")), payload.is_test, payload.reason, current_user)
            changed += 1
    return {"changed": changed, "inventory": await inventory()}


class ArchiveInput(BaseModel):
    archived: bool
    reason: str = Field(min_length=3, max_length=300)


@router.post("/campaigns/{campaign_id}/archive", response_model=dict)
async def archive_campaign(campaign_id: str, payload: ArchiveInput, current_user: dict = Depends(get_current_user)):
    """Archiva (o desarchiva) una invasión: deja de salir en Estadísticas y en «Reporte para la pastora».
    Sus visitas, viviendas y libros quedan intactos."""
    require_manager(current_user)
    doc = await db.outreach_campaigns.find_one({"campaign_id": campaign_id}, {"_id": 0, "archived": 1})
    if doc is None:
        raise HTTPException(status_code=404, detail="Invasión no encontrada")
    if bool(doc.get("archived")) != payload.archived:
        now = datetime.now(timezone.utc)
        await db.outreach_campaigns.update_one({"campaign_id": campaign_id}, {"$set": {"archived": payload.archived, "archived_at": now if payload.archived else None,
                                                                                     "archived_by_user_id": current_user["user_id"], "archive_reason": payload.reason}})
        await _log("campaign", campaign_id, "archived", bool(doc.get("archived")), payload.archived, payload.reason, current_user)
    return {"campaign_id": campaign_id, "archived": payload.archived}


class RealPersonInput(BaseModel):
    person_id: str
    confirmed: bool
    reason: str = Field(min_length=3, max_length=300)


@router.post("/real-person", response_model=dict)
async def set_real_person(payload: RealPersonInput, current_user: dict = Depends(get_current_user)):
    """«Es persona real»: solo el pastor. Reversible y con historial; no toca la cuenta, el rol ni el correo."""
    if not is_global_pastoral_authority(current_user):
        raise HTTPException(status_code=403, detail="Solo el pastor confirma que alguien es una persona real")
    if not ObjectId.is_valid(payload.person_id):
        raise HTTPException(status_code=404, detail="Persona no encontrada")
    person = await db.persons.find_one({"_id": ObjectId(payload.person_id)}, {"is_test": 1, "confirmed_real": 1})
    if not person:
        raise HTTPException(status_code=404, detail="Persona no encontrada")
    if payload.confirmed and person.get("is_test"):
        raise HTTPException(status_code=409, detail="Está marcada como prueba: quite primero esa marca")
    before = bool((person.get("confirmed_real") or {}).get("active"))
    if before != payload.confirmed:
        now = datetime.now(timezone.utc)
        await db.persons.update_one({"_id": person["_id"]}, {"$set": {"confirmed_real": {"active": payload.confirmed, "by_user_id": current_user["user_id"], "at": now, "reason": payload.reason}}})
        await _log("person", payload.person_id, "confirmed_real", before, payload.confirmed, payload.reason, current_user)
    return await inventory()


@router.get("/history", response_model=dict)
async def history(current_user: dict = Depends(get_current_user)):
    require_manager(current_user)
    return {"items": [{**row, "at": row["at"].isoformat()} for row in await db.test_data_marks.find({}, {"_id": 0}).sort("at", -1).limit(200).to_list(200)]}
