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
        "people": people_rows, "campaigns": campaigns,
        "visitor_registrations_marked": await db.visitor_registrations.count_documents({"test_data": True}),
        "counts": {"people": len(people_rows), "people_marked": sum(1 for row in people_rows if row["is_test"]),
                   "campaigns": len(campaigns), "campaigns_marked": sum(1 for row in campaigns if row["is_test"])},
        "note": "Solo lectura. Marcar como prueba saca a la persona o invasión de las cifras; no borra nada y se puede quitar.",
    }


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


@router.get("/history", response_model=dict)
async def history(current_user: dict = Depends(get_current_user)):
    require_manager(current_user)
    return {"items": [{**row, "at": row["at"].isoformat()} for row in await db.test_data_marks.find({}, {"_id": 0}).sort("at", -1).limit(200).to_list(200)]}
