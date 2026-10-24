"""Botón rojo «Necesito ayuda» durante la salida (invasión activa).

- Lo lanzan solo participantes de una invasión ACTIVA hoy (mentores,
  colaboradores y encargados; no la pastora, que supervisa).
- Lo ven y resuelven: autoridad pastoral, coordinadores generales, el
  organizador y el encargado general (`can_edit_participants`).
- Aviso en el portal (campana) a esos responsables; el push sale solo cuando
  el dueño lo active (notify_users ya llama al gancho de push_notifications).
- Idempotente por `client_request_id` y máximo 1 alerta por persona cada 30 s.
- No sustituye al 911: la interfaz lo dice explícitamente.
Colección: `invasion_help_alerts`."""
from datetime import date, datetime, timedelta, timezone
from typing import Literal, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from pymongo.errors import DuplicateKeyError

from invasion_participants import can_edit_participants, load_campaign
from mentorship_outreach import now_utc, person_display_name, serialize
from participation_scope import principal_authority_person_ids
from portal_notifications import notify_persons, notify_users
from server import db, get_current_user

router = APIRouter(prefix="/api/invasions", tags=["invasion-help"])

REASONS = {"support": "Necesito apoyo", "risk": "Situación de riesgo", "prayer": "Persona necesita oración", "urgent_info": "Información urgente"}
RATE_LIMIT_SECONDS = 30


class HelpInput(BaseModel):
    client_request_id: str = Field(min_length=8, max_length=80)
    reason: Literal["support", "risk", "prayer", "urgent_info"]
    note: Optional[str] = Field(default=None, max_length=500)
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)
    accuracy_m: Optional[float] = Field(default=None, ge=0, le=100000)


class HelpUpdate(BaseModel):
    status: Literal["acknowledged", "resolved"]
    note: Optional[str] = Field(default=None, max_length=500)


def is_active_today(campaign: dict) -> bool:
    today = date.today().isoformat()
    start = campaign.get("start_date") or ""
    end = campaign.get("end_date") or start
    return campaign.get("status") != "closed" and start <= today <= end


async def is_participant(campaign: dict, person_id: Optional[str]) -> bool:
    if not person_id or person_id in await principal_authority_person_ids(db):
        return False
    if person_id in (campaign.get("assigned_mentor_ids") or []) or person_id in (campaign.get("general_lead_person_id"), campaign.get("logistics_lead_person_id")):
        return True
    row = await db.invasion_participants.find_one({"campaign_id": campaign["campaign_id"], "person_id": person_id}, {"_id": 0, "status": 1})
    return bool(row and row.get("status") != "declined")


def _aware(value):
    return value.replace(tzinfo=timezone.utc) if isinstance(value, datetime) and value.tzinfo is None else value


def alert_view(alert: dict) -> dict:
    item = serialize(alert)
    created = _aware(alert.get("created_at"))
    acknowledged = _aware(alert.get("acknowledged_at") or alert.get("resolved_at"))
    item["reason_label"] = REASONS.get(alert.get("reason"), alert.get("reason"))
    item["response_minutes"] = round((acknowledged - created).total_seconds() / 60, 1) if created and acknowledged else None
    return item


async def responders(campaign: dict) -> tuple[list[str], list[str]]:
    """(user_ids, person_ids) de quienes deben recibir el aviso."""
    from invasion_planning import authority_users
    user_ids = [str(user["_id"]) for user in await authority_users()]
    if campaign.get("created_by_user_id"):
        user_ids.append(campaign["created_by_user_id"])
    return user_ids, [campaign.get("general_lead_person_id")]


@router.post("/{campaign_id}/help", response_model=dict, status_code=201)
async def send_help(campaign_id: str, payload: HelpInput, current_user: dict = Depends(get_current_user)):
    existing = await db.invasion_help_alerts.find_one({"client_request_id": payload.client_request_id}, {"_id": 0})
    if existing:
        if existing.get("created_by_user_id") != current_user["user_id"]:
            raise HTTPException(status_code=409, detail="Esa clave de aviso ya fue usada")
        return {**alert_view(existing), "duplicate": True}
    campaign = await load_campaign(campaign_id)
    person_id = current_user.get("person_id")
    if not await is_participant(campaign, person_id):
        raise HTTPException(status_code=403, detail="Solo los participantes de esta invasión pueden pedir ayuda")
    if not is_active_today(campaign):
        raise HTTPException(status_code=409, detail="La invasión no está activa hoy")
    now = now_utc()
    recent = await db.invasion_help_alerts.find_one({"person_id": person_id, "created_at": {"$gte": now - timedelta(seconds=RATE_LIMIT_SECONDS)}}, {"_id": 0, "created_at": 1})
    if recent:
        raise HTTPException(status_code=429, detail="Ya enviaste un aviso hace unos segundos; los responsables ya lo recibieron")
    name = await person_display_name(person_id) or current_user.get("nombre") or "Un participante"
    alert_id = str(uuid4())
    alert = {
        "_id": alert_id, "alert_id": alert_id, "campaign_id": campaign_id, "client_request_id": payload.client_request_id,
        "person_id": person_id, "person_name": name, "created_by_user_id": current_user["user_id"],
        "reason": payload.reason, "note": (payload.note or "").strip() or None,
        "latitude": payload.latitude, "longitude": payload.longitude, "accuracy_m": payload.accuracy_m if payload.latitude is not None else None,
        "status": "open", "created_at": now, "acknowledged_at": None, "acknowledged_by_name": None, "resolved_at": None, "resolved_by_name": None,
    }
    try:
        await db.invasion_help_alerts.insert_one(alert)
    except DuplicateKeyError:
        return {**alert_view(await db.invasion_help_alerts.find_one({"client_request_id": payload.client_request_id}, {"_id": 0})), "duplicate": True}
    user_ids, person_ids = await responders(campaign)
    title = f"🚨 {REASONS[payload.reason]}: {name}"
    message = f"Invasión «{campaign.get('name')}»" + (f" · {alert['note']}" if alert["note"] else "") + (" · con ubicación" if payload.latitude is not None else "")
    link = f"/invasiones/{campaign_id}/ayuda"
    ref = {"campaign_id": campaign_id, "alert_id": alert_id}
    sent = await notify_users(user_ids, "invasion_help", title, message, link, ref)
    sent += await notify_persons([item for item in person_ids if item and item != person_id], "invasion_help", title, message, link, ref)
    await db.invasion_help_alerts.update_one({"alert_id": alert_id}, {"$set": {"notified": sent}})
    return {**alert_view({**alert, "notified": sent}), "duplicate": False}


@router.get("/{campaign_id}/help", response_model=dict)
async def list_help(campaign_id: str, current_user: dict = Depends(get_current_user)):
    campaign = await load_campaign(campaign_id)
    if not can_edit_participants(current_user, campaign):
        raise HTTPException(status_code=403, detail="Solo los responsables de la invasión ven las alertas de ayuda")
    alerts = await db.invasion_help_alerts.find({"campaign_id": campaign_id}, {"_id": 0}).sort("created_at", -1).to_list(500)
    alerts.sort(key=lambda item: item.get("status") == "resolved")
    return {"campaign_id": campaign_id, "name": campaign.get("name"), "items": [alert_view(item) for item in alerts],
            "open": sum(1 for item in alerts if item.get("status") != "resolved")}


@router.put("/{campaign_id}/help/{alert_id}", response_model=dict)
async def update_help(campaign_id: str, alert_id: str, payload: HelpUpdate, current_user: dict = Depends(get_current_user)):
    """«Ya atendí» (acknowledged) o «Resuelto»; se registra quién y cuándo."""
    campaign = await load_campaign(campaign_id)
    if not can_edit_participants(current_user, campaign):
        raise HTTPException(status_code=403, detail="Solo los responsables de la invasión resuelven las alertas")
    alert = await db.invasion_help_alerts.find_one({"campaign_id": campaign_id, "alert_id": alert_id}, {"_id": 0})
    if not alert:
        raise HTTPException(status_code=404, detail="Alerta no encontrada")
    now = now_utc()
    who = await person_display_name(current_user.get("person_id")) or current_user.get("nombre") or "Responsable"
    update = {"updated_at": now}
    if not alert.get("acknowledged_at"):
        update.update({"acknowledged_at": now, "acknowledged_by_name": who})
    if payload.status == "resolved":
        update.update({"status": "resolved", "resolved_at": now, "resolved_by_name": who, "resolution_note": (payload.note or "").strip() or None})
    elif alert.get("status") == "open":
        update["status"] = "acknowledged"
    await db.invasion_help_alerts.update_one({"alert_id": alert_id}, {"$set": update})
    updated = await db.invasion_help_alerts.find_one({"alert_id": alert_id}, {"_id": 0})
    if not alert.get("acknowledged_at"):
        await notify_users([alert["created_by_user_id"]], "invasion_help_ack", f"{who} recibió tu aviso", REASONS.get(alert["reason"], ""), None, {"campaign_id": campaign_id, "alert_id": alert_id})
    return alert_view(updated)


async def help_summary(campaign_id: str) -> dict:
    """Para el Reporte de invasión: número de alertas y tiempo de respuesta."""
    alerts = await db.invasion_help_alerts.find({"campaign_id": campaign_id}, {"_id": 0}).sort("created_at", 1).to_list(500)
    views = [alert_view(item) for item in alerts]
    times = [item["response_minutes"] for item in views if item["response_minutes"] is not None]
    by_reason = [{"reason": key, "label": label, "total": sum(1 for item in alerts if item.get("reason") == key)} for key, label in REASONS.items()]
    return {"total": len(alerts), "resolved": sum(1 for item in alerts if item.get("status") == "resolved"),
            "open": sum(1 for item in alerts if item.get("status") != "resolved"),
            "avg_response_minutes": round(sum(times) / len(times), 1) if times else None, "by_reason": by_reason,
            "items": [{key: item.get(key) for key in ("alert_id", "person_name", "reason_label", "note", "created_at", "status", "response_minutes", "acknowledged_by_name", "resolved_by_name")} for item in views]}


async def ensure_indexes() -> None:
    await db.invasion_help_alerts.create_index("client_request_id", unique=True)
    await db.invasion_help_alerts.create_index([("campaign_id", 1), ("created_at", -1)])
    await db.invasion_help_alerts.create_index([("person_id", 1), ("created_at", -1)])
