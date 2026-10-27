"""Fusión guiada y reversible de personas duplicadas (auditoría 10/10).

1. «Candidatos»: grupos de Perfiles 360 con el mismo teléfono o el mismo nombre completo.
2. «Revisar»: qué se movería de una persona a otra y qué no se puede mover (conflictos).
3. «Fusionar»: TODO lo que apunta a la persona duplicada pasa a la que se conserva. La duplicada
   NO se borra: queda archivada con `merged_into_person_id`. Se guarda un respaldo completo de
   ambas fichas y la lista exacta de cada cambio (`person_merge_changes`).
4. «Deshacer»: devuelve cada referencia movida y desarchiva la duplicada.

Lo que no se puede mover sin romper una regla única (dos cuentas, dos membresías, dos expedientes
abiertos, la misma insignia…) se deja en la duplicada y se lista como conflicto para resolverlo a mano.
Solo la autoridad pastoral o un coordinador general."""
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from pymongo.errors import DuplicateKeyError

from access_control import is_general_coordinator, is_global_pastoral_authority
from server import db, get_current_user

router = APIRouter(prefix="/api/person-merge", tags=["person-merge"])

FIELDS = ["person_id", "converted_person_id", "mentor_person_id", "responsible_person_id", "canonical_person_id", "assigned_person_id",
          "followup.assigned_person_id", "transfer_request.to_person_id", "primary_leader_person_id", "to_holder.id", "from_holder.id", "holder_id"]
ARRAY_FIELDS = ["assigned_mentor_ids", "possible_person_ids", "person_ids", "member_person_ids"]
SKIP = {"persons", "person_merges", "person_merge_changes", "test_data_marks", "system.views"}
HOLDER_FIELDS = {"to_holder.id": "to_holder.type", "from_holder.id": "from_holder.type", "holder_id": "holder_type"}


def require_merge_manager(current_user: dict) -> None:
    if not (is_global_pastoral_authority(current_user) or is_general_coordinator(current_user)):
        raise HTTPException(status_code=403, detail="Solo la autoridad pastoral o un coordinador general puede fusionar personas")


async def load(person_id: str) -> dict:
    doc = await db.persons.find_one({"_id": ObjectId(person_id)}) if ObjectId.is_valid(person_id) else None
    if not doc:
        raise HTTPException(status_code=404, detail="Persona no encontrada")
    return doc


def card(doc: dict) -> dict:
    return {"person_id": str(doc["_id"]), "name": " ".join(filter(None, [doc.get("nombre"), doc.get("apellido")])) or "Persona", "person_number": doc.get("person_number"),
            "fecha_nacimiento": doc.get("fecha_nacimiento"), "created_at": doc.get("created_at").isoformat() if isinstance(doc.get("created_at"), datetime) else doc.get("created_at"),
            "is_archived": bool(doc.get("is_archived"))}


def _query(field: str, person_id: str) -> dict:
    query = {field: person_id}
    if field in HOLDER_FIELDS:
        query[HOLDER_FIELDS[field]] = "person"  # en Librería solo los «dueños» que son personas
    return query


async def references(person_id: str) -> dict:
    """{colección.campo: cantidad} de todo lo que apunta a esta persona (solo lectura)."""
    counts = {}
    for name in sorted(set(await db.list_collection_names()) - SKIP):
        for field in FIELDS + ARRAY_FIELDS:
            count = await db[name].count_documents(_query(field, person_id), limit=10000)
            if count:
                counts[f"{name}.{field}"] = count
    return counts


async def conflicts(keep_id: str, merged_id: str) -> list[str]:
    found = []
    if await db.users.find_one({"person_id": keep_id}, {"_id": 1}) and await db.users.find_one({"person_id": merged_id}, {"_id": 1}):
        found.append("Las dos tienen cuenta en la plataforma: la cuenta de la duplicada queda con ella (desactívela si sobra).")
    if await db.person_memberships.find_one({"person_id": keep_id}, {"_id": 1}) and await db.person_memberships.find_one({"person_id": merged_id}, {"_id": 1}):
        found.append("Las dos tienen membresía: la de la duplicada queda con ella.")
    open_q = {"process_key": "consolidation", "status": {"$in": ["planned", "active", "paused"]}}
    if await db.process_enrollments.find_one({**open_q, "person_id": keep_id}, {"_id": 1}) and await db.process_enrollments.find_one({**open_q, "person_id": merged_id}, {"_id": 1}):
        found.append("Las dos tienen un expediente de Consolidación abierto: el de la duplicada queda con ella (archívelo o páuselo).")
    return found


def _name_key(person: dict) -> str:
    import unicodedata
    text = unicodedata.normalize("NFKD", person.get("name") or "").encode("ascii", "ignore").decode().lower()
    return " ".join(text.split())


def similar_names(people: list) -> bool:
    """¿Parecen la misma persona? Mismo nombre completo, o mismo primer nombre y mismo primer apellido.
    Mismo teléfono con nombres distintos suele ser familia (no se sugiere fusionar)."""
    keys = [_name_key(item).split() for item in people]
    if not all(keys):
        return False
    if len({" ".join(key) for key in keys}) == 1:
        return True
    firsts = {key[0] for key in keys}
    lasts = {key[1] if len(key) > 1 else "" for key in keys}
    return len(firsts) == 1 and len(lasts) == 1


def signature_of(person_ids) -> str:
    return "|".join(sorted(person_ids))


@router.get("/candidates", response_model=dict)
async def candidates(current_user: dict = Depends(get_current_user)):
    """Grupos de posibles duplicados: mismo teléfono o mismo nombre completo (solo lectura).
    Revisión de producción: el mismo teléfono con nombres distintos NO sugiere fusionar (puede ser
    familia); se ofrece «No es duplicado», que se guarda y se puede deshacer."""
    require_merge_manager(current_user)
    groups = []
    async for row in db.person_contacts.aggregate([
        {"$match": {"tipo": "telefono", "valor_normalizado": {"$nin": [None, ""]}}},
        {"$group": {"_id": "$valor_normalizado", "ids": {"$addToSet": "$person_id"}}}, {"$match": {"ids.1": {"$exists": True}}}, {"$limit": 200}]):
        groups.append(("Mismo teléfono", row["_id"], row["ids"]))
    async for row in db.persons.aggregate([
        {"$match": {"is_archived": {"$ne": True}, "nombre": {"$nin": [None, ""]}}},
        {"$group": {"_id": {"$toLower": {"$concat": [{"$ifNull": ["$nombre", ""]}, " ", {"$ifNull": ["$apellido", ""]}]}}, "ids": {"$addToSet": {"$toString": "$_id"}}}},
        {"$match": {"ids.1": {"$exists": True}}}, {"$limit": 200}]):
        groups.append(("Mismo nombre", row["_id"], row["ids"]))
    dismissed = {doc["signature"]: doc async for doc in db.person_duplicate_dismissals.find({"active": True}, {"_id": 0})}
    out, seen, hidden = [], set(), []
    for reason, key, ids in groups:
        oids = [ObjectId(pid) for pid in ids if pid and ObjectId.is_valid(pid)]
        people = [card(doc) async for doc in db.persons.find({"_id": {"$in": oids}, "is_archived": {"$ne": True}})]
        signature = signature_of(item["person_id"] for item in people)
        if len(people) < 2 or signature in seen:
            continue
        seen.add(signature)
        if signature in dismissed:
            hidden.append({"signature": signature, "people": [item["name"] for item in people], "reason": dismissed[signature].get("reason")})
            continue
        suggest = reason == "Mismo nombre" or similar_names(people)
        out.append({"reason": reason if suggest else "Mismo teléfono, nombres distintos (puede ser familia)", "key": key, "suggest_merge": suggest,
                    "signature": signature, "people": sorted(people, key=lambda item: item.get("created_at") or "")})
    out.sort(key=lambda group: not group["suggest_merge"])  # primero los que de verdad parecen la misma persona
    return {"groups": out[:200], "dismissed": hidden[:200]}


class NotDuplicateInput(BaseModel):
    person_ids: list[str] = Field(min_length=2, max_length=20)
    reason: str = Field(min_length=3, max_length=300)


@router.post("/not-duplicate", response_model=dict)
async def not_duplicate(payload: NotDuplicateInput, current_user: dict = Depends(get_current_user)):
    """«No es duplicado»: el grupo deja de aparecer. Se guarda quién y por qué; se puede deshacer."""
    require_merge_manager(current_user)
    signature = signature_of(payload.person_ids)
    now = datetime.now(timezone.utc)
    await db.person_duplicate_dismissals.update_one({"signature": signature}, {"$set": {"signature": signature, "person_ids": sorted(payload.person_ids), "active": True,
                                                                                         "reason": payload.reason.strip(), "by_user_id": current_user["user_id"], "at": now},
                                                                                "$push": {"history": {"action": "dismissed", "reason": payload.reason.strip(), "by_user_id": current_user["user_id"], "at": now}}}, upsert=True)
    return {"signature": signature, "active": True}


class UndoDismissInput(BaseModel):
    signature: str = Field(min_length=3, max_length=2000)


@router.post("/not-duplicate/undo", response_model=dict)
async def undo_not_duplicate(payload: UndoDismissInput, current_user: dict = Depends(get_current_user)):
    require_merge_manager(current_user)
    now = datetime.now(timezone.utc)
    result = await db.person_duplicate_dismissals.update_one({"signature": payload.signature, "active": True}, {"$set": {"active": False, "updated_at": now},
                                                                                                              "$push": {"history": {"action": "restored", "by_user_id": current_user["user_id"], "at": now}}})
    if not result.matched_count:
        raise HTTPException(status_code=404, detail="No hay una marca «No es duplicado» activa para ese grupo")
    return {"signature": payload.signature, "active": False}


class MergeInput(BaseModel):
    keep_person_id: str
    merged_person_id: str
    reason: Optional[str] = Field(default=None, max_length=500)


def _pair(payload: MergeInput) -> tuple[str, str]:
    if payload.keep_person_id == payload.merged_person_id:
        raise HTTPException(status_code=422, detail="Elija dos personas distintas")
    return payload.keep_person_id, payload.merged_person_id


@router.post("/preview", response_model=dict)
async def preview(payload: MergeInput, current_user: dict = Depends(get_current_user)):
    require_merge_manager(current_user)
    keep_id, merged_id = _pair(payload)
    keep, merged = await load(keep_id), await load(merged_id)
    if merged.get("merged_into_person_id"):
        raise HTTPException(status_code=409, detail="Esa persona ya fue fusionada")
    refs = await references(merged_id)
    return {"keep": card(keep), "merged": card(merged), "references": refs, "total": sum(refs.values()), "conflicts": await conflicts(keep_id, merged_id),
            "note": "La duplicada no se borra: queda archivada y la fusión se puede deshacer."}


FILL = ("fecha_nacimiento", "genero", "estado_civil", "photo_url")


@router.post("", response_model=dict)
async def merge(payload: MergeInput, current_user: dict = Depends(get_current_user)):
    require_merge_manager(current_user)
    keep_id, merged_id = _pair(payload)
    if not (payload.reason or "").strip() or len(payload.reason.strip()) < 3:
        raise HTTPException(status_code=422, detail="Escriba por qué son la misma persona")
    keep, merged = await load(keep_id), await load(merged_id)
    if merged.get("merged_into_person_id") or merged.get("is_archived") or keep.get("is_archived"):
        raise HTTPException(status_code=409, detail="Solo se fusionan personas activas del directorio")
    now = datetime.now(timezone.utc)
    merge_id = str(uuid4())
    filled = {field: merged[field] for field in FILL if merged.get(field) and not keep.get(field)}
    # Respaldo completo ANTES de tocar nada.
    await db.person_merges.insert_one({"merge_id": merge_id, "keep_person_id": keep_id, "merged_person_id": merged_id, "keep_snapshot": keep, "merged_snapshot": merged,
                                       "filled_fields": filled, "reason": payload.reason.strip(), "by_user_id": current_user["user_id"], "at": now, "status": "in_progress"})
    moved, conflict_rows = 0, []
    for name in sorted(set(await db.list_collection_names()) - SKIP):
        for field in FIELDS + ARRAY_FIELDS:
            is_array = field in ARRAY_FIELDS
            async for doc in db[name].find(_query(field, merged_id), {"_id": 1}):
                try:
                    update = {"$set": {f"{field}.$": keep_id}} if is_array else {"$set": {field: keep_id}}
                    result = await db[name].update_one({"_id": doc["_id"], field: merged_id}, update)
                except DuplicateKeyError:
                    conflict_rows.append({"collection": name, "field": field})
                    continue
                if result.modified_count:
                    moved += 1
                    await db.person_merge_changes.insert_one({"merge_id": merge_id, "collection": name, "doc_id": doc["_id"], "field": field, "array": is_array})
    if filled:
        await db.persons.update_one({"_id": keep["_id"]}, {"$set": {**filled, "updated_at": now}})
    await db.persons.update_one({"_id": merged["_id"]}, {"$set": {"is_archived": True, "archived_at": now, "archived_reason": "Fusionada con otra persona",
                                                                  "merged_into_person_id": keep_id, "merged_at": now, "merge_id": merge_id, "updated_at": now}})
    await db.person_merges.update_one({"merge_id": merge_id}, {"$set": {"status": "done", "moved": moved, "conflicts": conflict_rows, "finished_at": datetime.now(timezone.utc)}})
    return {"merge_id": merge_id, "moved": moved, "conflicts": conflict_rows, "keep": card(await load(keep_id))}


@router.post("/{merge_id}/undo", response_model=dict)
async def undo(merge_id: str, current_user: dict = Depends(get_current_user)):
    """Devuelve cada referencia movida a la persona duplicada y la desarchiva."""
    require_merge_manager(current_user)
    record = await db.person_merges.find_one({"merge_id": merge_id})
    if not record:
        raise HTTPException(status_code=404, detail="Fusión no encontrada")
    if record.get("status") == "undone":
        return {"merge_id": merge_id, "restored": 0, "already": True}
    keep_id, merged_id = record["keep_person_id"], record["merged_person_id"]
    restored, skipped = 0, 0
    async for change in db.person_merge_changes.find({"merge_id": merge_id}):
        field = change["field"]
        update = {"$set": {f"{field}.$": merged_id}} if change.get("array") else {"$set": {field: merged_id}}
        try:
            result = await db[change["collection"]].update_one({"_id": change["doc_id"], field: keep_id}, update)
            restored += result.modified_count
        except DuplicateKeyError:
            skipped += 1
    now = datetime.now(timezone.utc)
    previous = record.get("merged_snapshot") or {}
    await db.persons.update_one({"_id": ObjectId(merged_id)}, {"$set": {"is_archived": bool(previous.get("is_archived")), "updated_at": now},
                                                               "$unset": {"merged_into_person_id": "", "merged_at": "", "merge_id": "", "archived_reason": "", "archived_at": ""}})
    if record.get("filled_fields"):
        await db.persons.update_one({"_id": ObjectId(keep_id)}, {"$unset": {field: "" for field in record["filled_fields"]}})
    await db.person_merges.update_one({"merge_id": merge_id}, {"$set": {"status": "undone", "undone_at": now, "undone_by_user_id": current_user["user_id"], "restored": restored, "undo_skipped": skipped}})
    return {"merge_id": merge_id, "restored": restored, "skipped": skipped}


@router.get("/history", response_model=dict)
async def history(current_user: dict = Depends(get_current_user)):
    require_merge_manager(current_user)
    items = []
    async for row in db.person_merges.find({}, {"_id": 0, "keep_snapshot": 0, "merged_snapshot": 0}).sort("at", -1).limit(100):
        items.append({**row, "at": row["at"].isoformat(), "keep_name": None, "merged_name": None})
    names = {str(doc["_id"]): " ".join(filter(None, [doc.get("nombre"), doc.get("apellido")])) async for doc in db.persons.find(
        {"_id": {"$in": [ObjectId(pid) for row in items for pid in (row["keep_person_id"], row["merged_person_id"]) if ObjectId.is_valid(pid)]}}, {"nombre": 1, "apellido": 1})}
    for row in items:
        row["keep_name"], row["merged_name"] = names.get(row["keep_person_id"]), names.get(row["merged_person_id"])
        for key in ("finished_at", "undone_at"):
            if isinstance(row.get(key), datetime):
                row[key] = row[key].isoformat()
    return {"items": items}
