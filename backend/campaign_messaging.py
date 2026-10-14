"""Mensajería a donantes de Ven y Come: redacción de mensajes (agradecimiento /
recordatorio / invitación) con IA, listas de "quién falta" (pendientes de pago y
quienes aún no han donado), y registro de contacto. El envío real y automático
por SMS vía Univerge Blue Connect requiere credenciales del proveedor
(UB_CLIENT_ID, UB_CLIENT_SECRET, UB_REFRESH_TOKEN, UB_SCOPE, UB_SMS_SEND_PATH,
UB_FROM_NUMBER) que aún no están configuradas; mientras tanto, el envío se hace
manualmente desde el teléfono del operador (enlace sms:) con el texto redactado
aquí."""
import os
from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from campaign_venycome import operator, get_settings
from person_domains import contact_items
from server import db

router = APIRouter(prefix="/api/campaigns/venycome/messages", tags=["campaign-messaging"])


def now_utc():
    return datetime.now(timezone.utc)


async def primary_phone(person_id: str) -> Optional[str]:
    contacts = await contact_items(person_id)
    phone = next((c for c in contacts if c.get("tipo") in {"telefono", "whatsapp"} and c.get("es_principal")), None) \
        or next((c for c in contacts if c.get("tipo") in {"telefono", "whatsapp"}), None)
    return phone.get("valor") if phone else None


async def last_contact(person_id: str, kind: str) -> Optional[datetime]:
    log = await db.campaign_message_log.find_one({"person_id": person_id, "kind": kind}, sort=[("created_at", -1)])
    return log["created_at"] if log else None


@router.get("/pending", response_model=dict)
async def list_pending(current_user: dict = Depends(operator)):
    """Donantes con un donativo activo (promesa o recibido) que aún no ha sido
    verificado/sellado — a quienes hay que recordarles completar el pago."""
    cursor = db.campaign_donations.find({
        "status": {"$ne": "voided"}, "verified": {"$ne": True},
        "anonymous": {"$ne": True}, "person_id": {"$ne": None},
    })
    items, seen = [], set()
    async for doc in cursor:
        pid = doc.get("person_id")
        if not pid or pid in seen:
            continue
        seen.add(pid)
        phone = await primary_phone(pid)
        if not phone:
            continue
        items.append({
            "person_id": pid, "donation_id": doc["donation_id"], "name": doc.get("donor_name"),
            "phone": phone, "amount_cents": doc["amount_cents"],
            "last_contacted_at": await last_contact(pid, "reminder"),
        })
    return {"items": items}


@router.get("/never-donated", response_model=dict)
async def list_never_donated(current_user: dict = Depends(operator)):
    """Personas 360 con teléfono registrado que aún no tienen ningún donativo
    (activo) en esta campaña — candidatos a invitar."""
    donated_ids = set(await db.campaign_donations.distinct("person_id", {"status": {"$ne": "voided"}, "person_id": {"$ne": None}}))
    items = []
    async for person in db.persons.find({}, {"_id": 1, "nombre": 1, "apellido": 1}).limit(500):
        pid = str(person["_id"])
        if pid in donated_ids:
            continue
        phone = await primary_phone(pid)
        if not phone:
            continue
        items.append({
            "person_id": pid, "name": f"{person.get('nombre', '')} {person.get('apellido', '')}".strip(),
            "phone": phone, "last_contacted_at": await last_contact(pid, "invite"),
        })
    return {"items": items}


class DraftRequest(BaseModel):
    kind: Literal["thank_you", "reminder", "invite"]
    person_id: str
    name: str
    amount_cents: Optional[int] = None


@router.post("/draft", response_model=dict)
async def draft_message(payload: DraftRequest, current_user: dict = Depends(operator)):
    from emergentintegrations.llm.chat import LlmChat, UserMessage, TextDelta, StreamDone

    api_key = os.environ.get("EMERGENT_LLM_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="Falta configurar la clave de IA (EMERGENT_LLM_KEY)")
    settings = await get_settings()
    zelle = settings.get("zelle_info") or "el Zelle de la iglesia (pendiente de configurar en Configuración de campaña)"
    name = payload.name.strip() or "hermano/a"
    prompts = {
        "thank_you": (
            f"Escribe un mensaje de texto (SMS) corto, cálido y cortés en español para {name}, "
            f"agradeciéndole su donativo de ${((payload.amount_cents or 0) / 100):.2f} a la campaña "
            f"'Ven y Come' (bus de comida de la iglesia). Máximo 300 caracteres, sin emojis, firmado 'Iglesia'."
        ),
        "reminder": (
            f"Escribe un mensaje de texto (SMS) corto, amable y respetuoso en español para {name}, "
            f"recordándole con cortesía que prometió un donativo a la campaña 'Ven y Come' (bus de comida) "
            f"que aún no se ha recibido. Invítalo a completarlo por Zelle a {zelle}. "
            f"Máximo 300 caracteres, sin presionar, sin emojis, firmado 'Iglesia'."
        ),
        "invite": (
            f"Escribe un mensaje de texto (SMS) corto, cálido e invitador en español para {name}, "
            f"invitándolo a sumarse con un donativo a la campaña 'Ven y Come' (bus de comida) de la iglesia, "
            f"por Zelle a {zelle}. Máximo 300 caracteres, sin presionar, sin emojis, firmado 'Iglesia'."
        ),
    }
    chat = LlmChat(
        api_key=api_key, session_id=f"campaign-msg-{payload.person_id}-{int(now_utc().timestamp())}",
        system_message="Eres un asistente que redacta mensajes de texto cortos, cálidos y respetuosos para una iglesia. Responde SOLO con el texto del mensaje, sin comillas ni explicaciones adicionales.",
    ).with_model("anthropic", "claude-sonnet-5-5")
    parts = []
    async for event in chat.stream_message(UserMessage(text=prompts[payload.kind])):
        if isinstance(event, TextDelta):
            parts.append(event.content)
        elif isinstance(event, StreamDone):
            break
    draft = "".join(parts).strip().strip('"')
    if not draft:
        raise HTTPException(status_code=502, detail="La IA no pudo redactar el mensaje, intenta de nuevo")
    return {"text": draft[:480]}


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
