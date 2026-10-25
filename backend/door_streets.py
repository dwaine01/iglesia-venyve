"""Puerta a puerta · calles: «Comenzar calle», «Cambiar calle», «Terminar
calle», «Reabrir» y «Mis calles».

Sin colecciones nuevas: el historial vive en `outreach_participations`
(la participación del mentor en esa invasión):
- `active_street` = la ÚNICA calle activa del mentor (con `street_session_id`).
- `street_sessions[]` = cada tramo trabajado en una calle (inicio, fin,
  motivo de cierre). Reabrir una calle agrega un tramo nuevo con la misma
  `street_key`; las viviendas son las mismas (no se duplica nada).

Reglas:
- Solo una calle activa por mentor. Cambiar de calle o reabrir otra cierra la
  anterior automáticamente (motivo `changed`), sin calles huérfanas.
- Terminar es idempotente (doble toque): si esa calle ya estaba cerrada
  devuelve el mismo resumen.
- Si el mentor olvidó terminarla, se cierra sola al terminar la jornada
  (cambio de día en la zona horaria de la iglesia) o al cerrarse la invasión,
  y se le avisa (motivo `auto`)."""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from mentorship_outreach import ensure_participation, now_utc, serialize
from outreach_doors import StreetInput, _norm, _participant_check
from server import db, get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/mentorship/outreach", tags=["outreach-door-streets"])

END_REASONS = {"finished": "Terminada", "changed": "Cerrada al cambiar de calle", "auto": "Cerrada automáticamente"}


class FinishInput(BaseModel):
    street_session_id: Optional[str] = Field(default=None, max_length=80)


class ReopenInput(BaseModel):
    street_key: str = Field(min_length=1, max_length=200)


def _aware(value: Optional[datetime]) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return None


async def _zone() -> ZoneInfo:
    from consolidation_activities import get_church_timezone
    try:
        return ZoneInfo(await get_church_timezone())
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


def _new_session(name: str, location: dict, reopened_from: Optional[str] = None) -> dict:
    return {"street_session_id": str(uuid4()), "street_name": name.strip(), "street_key": _norm(name), "started_at": now_utc(), "ended_at": None, "end_reason": None,
            "latitude": location.get("latitude"), "longitude": location.get("longitude"), "location_accuracy_m": location.get("location_accuracy_m"),
            "location_source": location.get("location_source") if location.get("latitude") is not None else None, "reopened_from": reopened_from}


async def _participation(campaign_id: str, mentor_person_id: str) -> dict:
    """Carga la participación y adopta una calle activa anterior a este cambio
    (sin `street_session_id`) como su primer tramo."""
    doc = await db.outreach_participations.find_one({"campaign_id": campaign_id, "mentor_person_id": mentor_person_id}, {"_id": 0, "active_street": 1, "street_sessions": 1}) or {}
    active = doc.get("active_street")
    if active and not active.get("street_session_id"):
        session = {**_new_session(active.get("street_name") or "Calle", active), "started_at": active.get("started_at") or now_utc()}
        result = await db.outreach_participations.update_one(
            {"campaign_id": campaign_id, "mentor_person_id": mentor_person_id, "active_street.street_session_id": {"$exists": False}},
            {"$set": {"active_street": session}, "$push": {"street_sessions": session}})
        if result.modified_count:
            doc["active_street"] = session
            doc["street_sessions"] = [*(doc.get("street_sessions") or []), session]
        else:
            doc = await db.outreach_participations.find_one({"campaign_id": campaign_id, "mentor_person_id": mentor_person_id}, {"_id": 0, "active_street": 1, "street_sessions": 1}) or {}
    return doc


async def close_active(campaign_id: str, mentor_person_id: str, session_id: str, reason: str, ended_at: Optional[datetime] = None) -> bool:
    """Cierra el tramo activo solo si sigue siendo ese (dos toques no cierran dos veces)."""
    result = await db.outreach_participations.update_one(
        {"campaign_id": campaign_id, "mentor_person_id": mentor_person_id, "active_street.street_session_id": session_id},
        {"$set": {"active_street": None, "street_sessions.$[s].ended_at": ended_at or now_utc(), "street_sessions.$[s].end_reason": reason, "updated_at": now_utc()}},
        array_filters=[{"s.street_session_id": session_id}])
    return bool(result.modified_count)


async def _start(campaign_id: str, mentor_person_id: str, session: dict) -> None:
    await db.outreach_participations.update_one({"campaign_id": campaign_id, "mentor_person_id": mentor_person_id},
                                               {"$set": {"active_street": session, "updated_at": now_utc()}, "$push": {"street_sessions": session}})


# ------------------------------------------------------------------ cierre automático
async def _stale(session: dict, campaign: dict, zone: ZoneInfo) -> bool:
    started = _aware(session.get("started_at"))
    if campaign.get("status") == "closed":
        return True
    if not started:
        return False
    return started.astimezone(zone).date() < datetime.now(zone).date()


async def _auto_close(campaign: dict, mentor_person_id: str, session: dict) -> bool:
    # Fin = la última vivienda registrada en ese tramo (o el inicio si no hubo ninguna).
    last = await db.outreach_visit_events.find_one({"street_session_id": session["street_session_id"]}, {"_id": 0, "occurred_at": 1}, sort=[("occurred_at", -1)])
    closed = await close_active(campaign["campaign_id"], mentor_person_id, session["street_session_id"], "auto", (last or {}).get("occurred_at") or session.get("started_at"))
    if closed:
        from portal_notifications import notify_persons
        await notify_persons([mentor_person_id], "door_street_auto_closed", "Calle cerrada automáticamente",
                             f"La calle «{session.get('street_name')}» se cerró al terminar la jornada. Sus viviendas quedan guardadas; puedes reabrirla desde «Mis calles».",
                             f"/mentoria/puerta-a-puerta?invasion={campaign['campaign_id']}", {"type": "door_street", "id": session["street_session_id"]})
    return closed


async def close_if_stale(campaign_id: str, mentor_person_id: str) -> None:
    doc = await _participation(campaign_id, mentor_person_id)
    active = doc.get("active_street")
    if not active:
        return
    campaign = await db.outreach_campaigns.find_one({"campaign_id": campaign_id}, {"_id": 0, "campaign_id": 1, "status": 1}) or {"campaign_id": campaign_id}
    if await _stale(active, campaign, await _zone()):
        await _auto_close(campaign, mentor_person_id, active)


async def close_stale_streets() -> int:
    """Barrido periódico: calles que quedaron abiertas de otra jornada."""
    zone = await _zone()
    closed = 0
    async for doc in db.outreach_participations.find({"active_street.street_session_id": {"$exists": True}}, {"_id": 0, "campaign_id": 1, "mentor_person_id": 1, "active_street": 1}):
        campaign = await db.outreach_campaigns.find_one({"campaign_id": doc["campaign_id"]}, {"_id": 0, "campaign_id": 1, "status": 1}) or {"campaign_id": doc["campaign_id"]}
        if await _stale(doc["active_street"], campaign, zone):
            closed += int(await _auto_close(campaign, doc["mentor_person_id"], doc["active_street"]))
    return closed


async def _close_loop() -> None:
    while True:
        try:
            await close_stale_streets()
        except Exception:  # noqa: BLE001
            logger.warning("calles: cierre automático falló", exc_info=True)
        await asyncio.sleep(15 * 60)


# ------------------------------------------------------------------ «Mis calles»
def _minutes(sessions: list[dict]) -> int:
    now = now_utc()
    total = 0.0
    for item in sessions:
        start, end = _aware(item.get("started_at")), _aware(item.get("ended_at")) or _aware(now)
        if start and end and end > start:
            total += (end - start).total_seconds() / 60
    return round(total)


def street_timing(sessions: list[dict]) -> dict[str, dict]:
    """Inicio, fin y duración por calle (para «Mis calles» y los reportes por calle)."""
    grouped: dict[str, list] = {}
    for item in sessions:
        grouped.setdefault(item.get("street_key") or "", []).append(item)
    timing = {}
    for key, items in grouped.items():
        active = any(not item.get("ended_at") for item in items)
        ends = [item["ended_at"] for item in items if item.get("ended_at")]
        timing[key] = {"started_at": min(item["started_at"] for item in items), "ended_at": None if active else max(ends), "duration_minutes": _minutes(items),
                       "sessions": len(items), "active": active}
    return timing


async def my_streets(campaign_id: str, mentor_person_id: str, doc: dict) -> list[dict]:
    sessions = doc.get("street_sessions") or []
    if not sessions:
        return []
    houses = await db.outreach_households.find({"campaign_id": campaign_id, "mentor_person_id": mentor_person_id, "archived": {"$ne": True}},
                                               {"_id": 0, "street_name": 1, "attempts_count": 1, "opened_ever": 1, "books_total": 1, "door_status": 1}).to_list(5000)
    stats: dict[str, dict] = {}
    for house in houses:
        row = stats.setdefault(_norm(house.get("street_name")), {"houses": 0, "visited": 0, "opened": 0, "books": 0, "pending_revisit": 0})
        row["houses"] += 1
        row["visited"] += int((house.get("attempts_count") or 0) > 0)
        row["opened"] += int(bool(house.get("opened_ever")))
        row["books"] += house.get("books_total") or 0
        row["pending_revisit"] += int(house.get("door_status") == "pending_revisit")
    zone = await _zone()
    today = datetime.now(zone).date()
    timing = street_timing(sessions)
    rows = []
    for key, item in timing.items():
        last = max((entry for entry in sessions if (entry.get("street_key") or "") == key), key=lambda entry: _aware(entry["started_at"]))
        rows.append({"street_key": key, "street_name": last["street_name"], "status": "active" if item["active"] else "finished",
                     "end_reason": None if item["active"] else last.get("end_reason"), "today": _aware(last["started_at"]).astimezone(zone).date() == today,
                     **{field: item[field] for field in ("started_at", "ended_at", "duration_minutes", "sessions")},
                     **stats.get(key, {"houses": 0, "visited": 0, "opened": 0, "books": 0, "pending_revisit": 0})})
    rows.sort(key=lambda row: (row["status"] != "active", -_aware(row["started_at"]).timestamp()))
    return serialize(rows)


async def _state(campaign_id: str, mentor_person_id: str, **extra) -> dict:
    doc = await _participation(campaign_id, mentor_person_id)
    return {"active_street": serialize(doc.get("active_street")), "streets": await my_streets(campaign_id, mentor_person_id, doc), **extra}


# ------------------------------------------------------------------ API
@router.get("/campaigns/{campaign_id}/my-street", response_model=dict)
async def get_my_street(campaign_id: str, current_user: dict = Depends(get_current_user)):
    mentor_person_id = await _participant_check(campaign_id, current_user)
    await close_if_stale(campaign_id, mentor_person_id)
    return await _state(campaign_id, mentor_person_id)


@router.put("/campaigns/{campaign_id}/my-street", response_model=dict)
async def set_my_street(campaign_id: str, payload: StreetInput, current_user: dict = Depends(get_current_user)):
    """«Comenzar calle» / «Cambiar calle»: cierra la anterior y deja esta activa."""
    mentor_person_id = await _participant_check(campaign_id, current_user)
    await ensure_participation(campaign_id, mentor_person_id)
    await close_if_stale(campaign_id, mentor_person_id)
    doc = await _participation(campaign_id, mentor_person_id)
    active = doc.get("active_street")
    if active and active.get("street_key") == _norm(payload.street_name):
        # Doble toque o la misma calle: se mantiene el tramo (se actualiza la ubicación si llegó).
        if payload.latitude is not None:
            await db.outreach_participations.update_one(
                {"campaign_id": campaign_id, "mentor_person_id": mentor_person_id, "active_street.street_session_id": active["street_session_id"]},
                {"$set": {"active_street.latitude": payload.latitude, "active_street.longitude": payload.longitude, "active_street.location_accuracy_m": payload.location_accuracy_m,
                          "active_street.location_source": payload.location_source}})
        return await _state(campaign_id, mentor_person_id)
    if active:
        await close_active(campaign_id, mentor_person_id, active["street_session_id"], "changed")
    previous = next((item for item in reversed(doc.get("street_sessions") or []) if item.get("street_key") == _norm(payload.street_name)), None)
    await _start(campaign_id, mentor_person_id, _new_session(payload.street_name, payload.model_dump(), previous["street_session_id"] if previous else None))
    return await _state(campaign_id, mentor_person_id)


@router.post("/campaigns/{campaign_id}/my-street/finish", response_model=dict)
async def finish_my_street(campaign_id: str, payload: FinishInput, current_user: dict = Depends(get_current_user)):
    """«Terminar calle»: queda cerrada con su historial; idempotente."""
    mentor_person_id = await _participant_check(campaign_id, current_user)
    doc = await _participation(campaign_id, mentor_person_id)
    active = doc.get("active_street")
    session_id = payload.street_session_id or (active or {}).get("street_session_id")
    session = next((item for item in doc.get("street_sessions") or [] if item["street_session_id"] == session_id), None) if session_id else None
    if not session:
        raise HTTPException(status_code=409, detail="No tienes una calle activa")
    closed = bool(active and active.get("street_session_id") == session_id) and await close_active(campaign_id, mentor_person_id, session_id, "finished")
    state = await _state(campaign_id, mentor_person_id)
    summary = next((row for row in state["streets"] if row["street_key"] == session.get("street_key")), None)
    return {**state, "finished": summary, "already_finished": not closed}


@router.post("/campaigns/{campaign_id}/my-street/reopen", response_model=dict)
async def reopen_my_street(campaign_id: str, payload: ReopenInput, current_user: dict = Depends(get_current_user)):
    """Reabrir una calle anterior para agregar más viviendas (sus viviendas ya
    registradas siguen siendo las mismas)."""
    mentor_person_id = await _participant_check(campaign_id, current_user)
    await close_if_stale(campaign_id, mentor_person_id)
    doc = await _participation(campaign_id, mentor_person_id)
    previous = next((item for item in reversed(doc.get("street_sessions") or []) if item.get("street_key") == payload.street_key), None)
    if not previous:
        raise HTTPException(status_code=404, detail="Esa calle no está en tus calles de esta invasión")
    active = doc.get("active_street")
    if active and active.get("street_key") == payload.street_key:
        return await _state(campaign_id, mentor_person_id)
    if active:
        await close_active(campaign_id, mentor_person_id, active["street_session_id"], "changed")
    await _start(campaign_id, mentor_person_id, _new_session(previous["street_name"], previous, previous["street_session_id"]))
    return await _state(campaign_id, mentor_person_id)


_close_task: Optional[asyncio.Task] = None


async def ensure_indexes() -> None:
    global _close_task
    await db.outreach_participations.create_index("active_street.street_session_id", sparse=True)
    await db.outreach_visit_events.create_index("street_session_id", sparse=True)
    if _close_task is None:
        _close_task = asyncio.create_task(_close_loop())
