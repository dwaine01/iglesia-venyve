"""Reporte por día de la invasión y exclusión de cuentas de prueba.

- Día local de la iglesia: la zona configurada (Configuración → zona
  horaria); si sigue en UTC (sin configurar), se usa America/New_York (pedido
  del dueño). Así un registro hecho de noche cuenta en su día real.
- Exclusiones: la autoridad pastoral principal nunca cuenta; además, la
  autoridad pastoral o un coordinador general marca qué cuentas son de
  prueba (con sugerencias: correos de prueba) y esas personas no cuentan en
  ninguna cifra del reporte. Nada se borra."""
import re
from datetime import date, datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from access_control import is_general_coordinator, is_global_pastoral_authority
from participation_scope import principal_authority_person_ids
from server import db, get_current_user

router = APIRouter(prefix="/api/invasions/report-settings", tags=["invasion-report-settings"])

FALLBACK_ZONE = "America/New_York"
SETTINGS_ID = "invasion_report_exclusions"
TEST_HINT = re.compile(r"(@example\.(com|org)$|e2e|\bqa\b|qa\.|fixture|test|prueba)", re.IGNORECASE)


async def report_zone() -> ZoneInfo:
    from consolidation_activities import get_church_timezone
    name = await get_church_timezone()
    if not name or name.upper() == "UTC":
        name = FALLBACK_ZONE
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo(FALLBACK_ZONE)


def local_day(value, zone: ZoneInfo) -> Optional[str]:
    if isinstance(value, datetime):
        moment = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return moment.astimezone(zone).date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str) and value:
        if len(value) == 10:
            return value
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return local_day(parsed, zone)
        except ValueError:
            return value[:10]
    return None


async def excluded_person_ids() -> set:
    """Autoridad pastoral principal + cuentas marcadas como de prueba."""
    authorities = set(await principal_authority_person_ids(db))
    settings = await db.app_settings.find_one({"_id": SETTINGS_ID}, {"_id": 0, "person_ids": 1}) or {}
    # Personas marcadas `is_test` en «Datos de prueba» (auditoría 8/10): tampoco cuentan.
    marked = {str(doc["_id"]) async for doc in db.persons.find({"is_test": True}, {"_id": 1})}
    return authorities | set(settings.get("person_ids") or []) | marked


def require_manager(current_user: dict) -> None:
    if not (is_global_pastoral_authority(current_user) or is_general_coordinator(current_user)):
        raise HTTPException(status_code=403, detail="Solo la autoridad pastoral o un coordinador general")


async def _person_names(person_ids) -> dict:
    from bson import ObjectId
    oids = [ObjectId(item) for item in person_ids if item and ObjectId.is_valid(item)]
    return {str(doc["_id"]): " ".join(filter(None, [doc.get("nombre"), doc.get("apellido")])) or "Persona"
            async for doc in db.persons.find({"_id": {"$in": oids}}, {"nombre": 1, "apellido": 1})} if oids else {}


@router.get("/exclusions", response_model=dict)
async def get_exclusions(current_user: dict = Depends(get_current_user)):
    """Cuentas excluidas y sugerencias (correos de prueba) para confirmar con un toque."""
    require_manager(current_user)
    settings = await db.app_settings.find_one({"_id": SETTINGS_ID}, {"_id": 0}) or {}
    excluded = list(settings.get("person_ids") or [])
    suggestions = []
    async for user in db.users.find({"person_id": {"$nin": [None, ""]}}, {"_id": 0, "person_id": 1, "email": 1, "nombre": 1}):
        if TEST_HINT.search(user.get("email") or "") and user["person_id"] not in excluded:
            suggestions.append({"person_id": user["person_id"], "email": user.get("email"), "name": user.get("nombre")})
    names = await _person_names(excluded)
    emails = {doc["person_id"]: doc.get("email") async for doc in db.users.find({"person_id": {"$in": excluded}}, {"_id": 0, "person_id": 1, "email": 1})}
    return {"excluded": [{"person_id": pid, "name": names.get(pid) or "Persona", "email": emails.get(pid)} for pid in excluded],
            "suggestions": suggestions[:200], "updated_at": settings.get("updated_at")}


class ExclusionsInput(BaseModel):
    person_ids: list[str] = Field(default_factory=list, max_length=500)


@router.put("/exclusions", response_model=dict)
async def set_exclusions(payload: ExclusionsInput, current_user: dict = Depends(get_current_user)):
    require_manager(current_user)
    ids = sorted({item for item in payload.person_ids if item})
    await db.app_settings.update_one({"_id": SETTINGS_ID}, {"$set": {"person_ids": ids, "updated_at": datetime.now(timezone.utc), "updated_by_user_id": current_user["user_id"]}}, upsert=True)
    return await get_exclusions(current_user)


@router.get("/presentable", response_model=dict)
async def presentable_campaigns(current_user: dict = Depends(get_current_user)):
    """Invasiones cuyo reporte completo puede presentar este usuario (para el botón
    «Reporte para la pastora»): la activa o más reciente primero, con sus días y el
    día sugerido (el de hoy o el último ya trabajado). Mismo permiso que el reporte."""
    from invasion_participants import can_edit_participants
    from invasion_report import campaign_period_days, campaign_state
    zone = await report_zone()
    today = datetime.now(zone).date().isoformat()
    items = []
    async for campaign in db.outreach_campaigns.find({"archived": {"$ne": True}, "deleted": {"$ne": True}, "is_test": {"$ne": True}}, {"_id": 0}).sort("start_date", -1).limit(200):
        if not can_edit_participants(current_user, campaign):
            continue
        state = campaign_state(campaign)
        if state == "upcoming":
            continue
        days = campaign_period_days(campaign)
        worked = [item for item in days if item["day"] <= today]
        items.append({"campaign_id": campaign["campaign_id"], "name": campaign.get("name") or "Invasión", "location": campaign.get("location"), "start_date": campaign.get("start_date"),
                      "end_date": campaign.get("end_date"), "state": state, "days": days, "suggested_day": worked[-1]["index"] if worked else (1 if days else 0)})
    items.sort(key=lambda item: item["state"] != "active")  # estable: luego la más reciente
    return {"items": items}
