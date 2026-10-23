"""Mensajería a donantes de Ven y Come: mensajes de texto (agradecimiento /
recordatorio / invitación) generados con plantillas fijas en el backend,
listas de "quién falta" (pendientes de pago y quienes aún no han donado), y
registro de contacto. El envío se hace manualmente desde el teléfono del
operador (enlace sms:) con el texto generado aquí; el envío automático real
por SMS (ej. Univerge Blue Connect) requeriría credenciales de un proveedor
que aún no están configuradas.

Nota de portabilidad: este módulo NO debe importar `emergentintegrations` ni
depender de `EMERGENT_LLM_KEY` — ese paquete no está instalado en producción
(Railway) a propósito (ver DEPLOYMENT.md y
tests/test_portability_auth_cors_public.py). Los mensajes se generan con
plantillas de texto normales en Python, sin ninguna llamada a IA."""
from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from campaign_venycome import operator, get_settings
from server import db

router = APIRouter(prefix="/api/campaigns/venycome/messages", tags=["campaign-messaging"])


def now_utc():
    return datetime.now(timezone.utc)


PHONE_TYPES = {"telefono", "whatsapp"}


async def primary_phones(person_ids: list[str]) -> dict[str, str]:
    """`primary_phone` para muchas personas con una sola consulta (mismo orden
    y misma regla: principal primero; si no, el primero registrado)."""
    if not person_ids:
        return {}
    first_any: dict[str, str] = {}
    first_main: dict[str, str] = {}
    cursor = db.person_contacts.find(
        {"person_id": {"$in": person_ids}, "tipo": {"$in": list(PHONE_TYPES)}},
        {"_id": 0, "person_id": 1, "valor": 1, "es_principal": 1},
    ).sort([("es_principal", -1), ("created_at", 1)])
    async for contact in cursor:
        pid = contact["person_id"]
        first_any.setdefault(pid, contact["valor"])
        if contact.get("es_principal"):
            first_main.setdefault(pid, contact["valor"])
    return {pid: first_main.get(pid) or first_any[pid] for pid in first_any}


async def last_contacts(person_ids: list[str], kind: str) -> dict[str, datetime]:
    """`last_contact` en lote: última fecha de contacto por persona."""
    if not person_ids:
        return {}
    rows = await db.campaign_message_log.aggregate([
        {"$match": {"person_id": {"$in": person_ids}, "kind": kind}},
        {"$group": {"_id": "$person_id", "created_at": {"$max": "$created_at"}}},
    ]).to_list(None)
    return {row["_id"]: row["created_at"] for row in rows}


@router.get("/pending", response_model=dict)
async def list_pending(current_user: dict = Depends(operator)):
    """Donantes con un donativo activo (promesa o recibido) que aún no ha sido
    verificado/sellado — a quienes hay que recordarles completar el pago."""
    cursor = db.campaign_donations.find({
        "status": {"$ne": "voided"}, "verified": {"$ne": True},
        "anonymous": {"$ne": True}, "person_id": {"$ne": None},
    })
    donations, seen = [], set()
    async for doc in cursor:
        pid = doc.get("person_id")
        if not pid or pid in seen:
            continue
        seen.add(pid)
        donations.append(doc)
    phones = await primary_phones([doc["person_id"] for doc in donations])
    contacted = await last_contacts(list(phones), "reminder")
    items = [{
        "person_id": doc["person_id"], "donation_id": doc["donation_id"], "name": doc.get("donor_name"),
        "phone": phones[doc["person_id"]], "amount_cents": doc["amount_cents"],
        "last_contacted_at": contacted.get(doc["person_id"]),
    } for doc in donations if doc["person_id"] in phones]
    return {"items": items}


@router.get("/never-donated", response_model=dict)
async def list_never_donated(current_user: dict = Depends(operator)):
    """Personas 360 con teléfono registrado que aún no tienen ningún donativo
    (activo) en esta campaña — candidatos a invitar."""
    donated_ids = set(await db.campaign_donations.distinct("person_id", {"status": {"$ne": "voided"}, "person_id": {"$ne": None}}))
    people = [
        person async for person in db.persons.find({}, {"_id": 1, "nombre": 1, "apellido": 1}).limit(500)
        if str(person["_id"]) not in donated_ids
    ]
    phones = await primary_phones([str(person["_id"]) for person in people])
    contacted = await last_contacts(list(phones), "invite")
    items = [{
        "person_id": str(person["_id"]), "name": f"{person.get('nombre', '')} {person.get('apellido', '')}".strip(),
        "phone": phones[str(person["_id"])], "last_contacted_at": contacted.get(str(person["_id"])),
    } for person in people if str(person["_id"]) in phones]
    return {"items": items}


class DraftRequest(BaseModel):
    kind: Literal["thank_you", "reminder", "invite"]
    person_id: str
    name: str
    amount_cents: Optional[int] = None


def build_message(kind: str, name: str, amount_cents: Optional[int], zelle: Optional[str]) -> str:
    first_name = (name or "hermano/a").strip().split(" ")[0]
    amount = f"${((amount_cents or 0) / 100):.2f}"
    if kind == "thank_you":
        text = f"Hola {first_name}, ¡gracias de corazón por tu donativo de {amount} a la campaña Ven y Come! Tu generosidad bendice a quienes más lo necesitan. — Iglesia"
    elif kind == "reminder":
        text = f"Hola {first_name}, te recordamos con cariño tu donativo prometido a Ven y Come, que aún no hemos recibido. Puedes completarlo por Zelle a {zelle}. ¡Gracias! — Iglesia"
    else:
        text = f"Hola {first_name}, te invitamos a sumarte a la campaña Ven y Come (bus de comida) con un donativo por Zelle a {zelle}. Cada aporte ayuda mucho. — Iglesia"
    return text[:300]


@router.post("/draft", response_model=dict)
async def draft_message(payload: DraftRequest, current_user: dict = Depends(operator)):
    settings = await get_settings()
    zelle = settings.get("zelle_info")
    if payload.kind in ("reminder", "invite") and not zelle:
        raise HTTPException(status_code=400, detail="Configura el Zelle de la iglesia en Configuración de campaña antes de generar este mensaje")
    text = build_message(payload.kind, payload.name, payload.amount_cents, zelle)
    return {"text": text}


class MarkContactedInput(BaseModel):
    kind: Literal["thank_you", "reminder", "invite"]
    text: str = Field(..., min_length=1, max_length=500)


@router.post("/{person_id}/mark-contacted", response_model=dict)
async def mark_contacted(person_id: str, payload: MarkContactedInput, current_user: dict = Depends(operator)):
    """Registra que ya se contactó a esta persona (envío manual desde el
    teléfono del operador), para no repetir el mismo recordatorio dos veces."""
    await db.campaign_message_log.insert_one({
        "person_id": person_id, "kind": payload.kind, "text": payload.text,
        "created_by_user_id": current_user["user_id"], "created_at": now_utc(),
    })
    return {"ok": True}
