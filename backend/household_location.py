"""Ubicación de las casas de una invasión: dirección + GPS + mapa con puntos.

Campos nuevos en `outreach_households` (opcionales; las casas anteriores siguen
funcionando sin coordenadas):
    latitude, longitude, location_accuracy_m,
    location_source ∈ {gps, geocoded, manual}, location_reference (texto libre:
    "casa azul junto a la bodega"), geocoding_status ∈ {pending, matched,
    needs_verification, not_found, ambiguous, provider_error, not_configured},
    geocoding_provider, geocoded_at, location_updated_at.

Visibilidad (backend, no solo en pantalla):
- Ven TODAS las casas de la invasión: pastor/coordinador general, líderes de
  invasiones (capability de asignación), el organizador y los encargados
  (general y de logística) de esa invasión.
- Un mentor del roster ve SOLO sus casas y las disponibles de esa invasión.
- Coordenadas exactas: con `geo.view_precise` (o autoridad pastoral), y siempre
  para la casa propia o disponible (las necesita para llegar). En los demás
  casos se entregan aproximadas (~100 m) y marcadas como tales.

Geocodificación: usa el proveedor existente (`geo_provider`: Census y respaldo
Geocodio), solo en el servidor y en segundo plano; nunca bloquea el registro."""
import asyncio
import math
import re
import unicodedata
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator

from access_control import GEO_VIEW_PRECISE, has_capability, is_global_pastoral_authority
from geo_provider import geocoding_is_configured, get_geocoding_provider
from geo_service import CHURCH_ADDRESS
from mentorship_outreach import (
    can_manage_outreach_campaigns, can_use_outreach, enrich_households, is_outreach_leader, load_household, now_utc, serialize,
)
from server import db, get_current_user

router = APIRouter(prefix="/api/mentorship/outreach", tags=["household-location"])

DUPLICATE_RADIUS_M = 25
LOW_ACCURACY_M = 100
APPROX_DECIMALS = 3  # ~110 m
LOCATED_STATUSES = {"matched", "needs_verification"}


class LocationInput(BaseModel):
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)
    accuracy_m: Optional[float] = Field(default=None, ge=0, le=100000)
    source: Literal["gps", "manual"] = "manual"
    reference: Optional[str] = Field(default=None, max_length=300)

    @model_validator(mode="after")
    def both_or_none(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("Indique latitud y longitud juntas")
        return self


class DuplicateCheckInput(BaseModel):
    campaign_id: str
    address_line1: Optional[str] = Field(default=None, max_length=220)
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)
    exclude_household_id: Optional[str] = None


def distance_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Distancia haversine en metros."""
    radius = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(a))


def normalize_address(value: Optional[str]) -> str:
    raw = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", raw).strip()


def _church_city_state() -> tuple[Optional[str], Optional[str]]:
    # "640 Demorest Rd, Columbus, OH 43204" → ("Columbus", "OH")
    parts = [part.strip() for part in CHURCH_ADDRESS.split(",")]
    if len(parts) >= 3:
        return parts[-2], parts[-1].split(" ")[0]
    return None, None


def geocoding_address(household: dict) -> Optional[dict]:
    line1 = (household.get("address_line1") or "").strip()
    if not line1:
        return None
    default_city, default_state = _church_city_state()
    city = household.get("address_city") or default_city
    state = household.get("address_state") or default_state
    full = ", ".join(part for part in [line1, household.get("address_line2"), city, " ".join(filter(None, [state, household.get("address_zip")]))] if part)
    return {"street": line1, "city": city, "state": state, "zip": household.get("address_zip"), "full_address": full}


def has_coordinates(household: dict) -> bool:
    return household.get("latitude") is not None and household.get("longitude") is not None


# ---------------------------------------------------------------- geocodificación en segundo plano
_tasks: set = set()
_semaphore = asyncio.Semaphore(2)


async def geocode_household(household_id: str) -> str:
    household = await db.outreach_households.find_one({"household_id": household_id}, {"_id": 0})
    if not household or has_coordinates(household):
        return "skipped"
    address = geocoding_address(household)
    if not address:
        return "skipped"
    if not geocoding_is_configured():
        await db.outreach_households.update_one({"household_id": household_id}, {"$set": {"geocoding_status": "not_configured"}})
        return "not_configured"
    async with _semaphore:
        try:
            result = await get_geocoding_provider().geocode(address)
        except Exception:  # el proveedor nunca debe romper el registro
            await db.outreach_households.update_one({"household_id": household_id}, {"$set": {"geocoding_status": "provider_error", "geocoded_at": now_utc()}})
            return "provider_error"
    update = {"geocoding_status": result.status, "geocoding_provider": result.provider, "geocoded_at": now_utc()}
    if result.status in LOCATED_STATUSES and result.latitude is not None:
        update.update({"latitude": result.latitude, "longitude": result.longitude, "location_source": "geocoded",
                       "location_accuracy_m": None, "location_updated_at": now_utc()})
    # Solo si nadie puso coordenadas mientras tanto (GPS o manual ganan siempre);
    # `latitude: None` también coincide con casas sin el campo.
    await db.outreach_households.update_one({"household_id": household_id, "latitude": None}, {"$set": update})
    return result.status


def schedule_geocoding(household_ids: list[str]) -> None:
    """Lanza la geocodificación sin esperar (no bloquea la respuesta)."""
    async def run():
        for household_id in household_ids:
            await geocode_household(household_id)
    try:
        task = asyncio.get_running_loop().create_task(run())
    except RuntimeError:
        return
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


async def mark_pending_and_geocode(household_ids: list[str]) -> None:
    """Para casas con dirección y sin coordenadas: estado pendiente + geocodificar."""
    if not household_ids:
        return
    query = {"household_id": {"$in": household_ids}, "address_line1": {"$nin": [None, ""]}, "latitude": None}
    ids = await db.outreach_households.distinct("household_id", query)
    if not ids:
        return
    await db.outreach_households.update_many({"household_id": {"$in": ids}}, {"$set": {"geocoding_status": "pending"}})
    schedule_geocoding(ids)


# ---------------------------------------------------------------- permisos
async def campaign_doc(campaign_id: Optional[str]) -> dict:
    if not campaign_id:
        return {}
    return await db.outreach_campaigns.find_one({"campaign_id": campaign_id}, {"_id": 0}) or {}


def sees_whole_campaign(current_user: dict, campaign: dict) -> bool:
    if is_outreach_leader(current_user) or can_manage_outreach_campaigns(current_user):
        return True
    if campaign.get("created_by_user_id") and campaign.get("created_by_user_id") == current_user.get("user_id"):
        return True
    person_id = current_user.get("person_id")
    return bool(person_id and person_id in {campaign.get("general_lead_person_id"), campaign.get("logistics_lead_person_id")})


def sees_precise(current_user: dict) -> bool:
    return is_global_pastoral_authority(current_user) or has_capability(current_user, GEO_VIEW_PRECISE)


def can_edit_location(current_user: dict, household: dict, campaign: dict) -> bool:
    if household.get("mentor_person_id") and household.get("mentor_person_id") == current_user.get("person_id"):
        return True
    return sees_whole_campaign(current_user, campaign)


def point(household: dict, current_user: dict, full: bool) -> dict:
    me = current_user.get("person_id")
    attempts = household.get("attempts") or 0
    mine = household.get("mentor_person_id") == me and me is not None
    if household.get("mentor_person_id") is None:
        category = "available"
    elif attempts:
        category = "visited"
    else:
        category = "mine" if mine else "assigned"
    exact = sees_precise(current_user) or mine or category == "available"
    lat, lng = household.get("latitude"), household.get("longitude")
    if lat is not None and not exact:
        lat, lng = round(lat, APPROX_DECIMALS), round(lng, APPROX_DECIMALS)
    return {
        "household_id": household["household_id"], "campaign_id": household.get("campaign_id"),
        "category": category, "mine": mine, "status": household.get("status"),
        "address_line1": household.get("address_line1"), "address_line2": household.get("address_line2"), "sector": household.get("sector"),
        "location_reference": household.get("location_reference"), "note": household.get("note") if (mine or full) else None,
        "latitude": lat, "longitude": lng, "approximate": lat is not None and (not exact or bool(household.get("location_approx"))),
        "location_approx": bool(household.get("location_approx")),
        "door_status": household.get("door_status"), "last_result": household.get("last_result"), "last_attempt_at": household.get("last_attempt_at"),
        "followup_date": household.get("followup_date"), "unit": household.get("unit"),
        "location_source": household.get("location_source"), "location_accuracy_m": household.get("location_accuracy_m"),
        "geocoding_status": household.get("geocoding_status"),
        "attempts": attempts, "last_occurred_at": household.get("last_occurred_at"),
        "mentor_person_id": household.get("mentor_person_id") if full or mine else None,
        "can_claim": category == "available", "can_register_visit": mine,
        "can_edit_location": mine or full,
    }


async def visible_households(campaign: dict, current_user: dict) -> tuple[list[dict], bool]:
    """(casas visibles, ve_todo). Lanza 403 si no participa en la invasión."""
    full = sees_whole_campaign(current_user, campaign)
    query: dict = {"campaign_id": campaign["campaign_id"], "archived": {"$ne": True}}
    if not full:
        me = current_user.get("person_id")
        if not me or me not in (campaign.get("assigned_mentor_ids") or []):
            raise HTTPException(status_code=403, detail="No participa en esta invasión")
        query["$or"] = [{"mentor_person_id": me}, {"mentor_person_id": None}]
    households = await db.outreach_households.find(query, {"_id": 0}).sort("created_at", 1).to_list(2000)
    return await enrich_households(households), full


# ---------------------------------------------------------------- endpoints
@router.get("/campaigns/{campaign_id}/households/map", response_model=dict)
async def households_map(campaign_id: str, current_user: dict = Depends(get_current_user)):
    campaign = await campaign_doc(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Invasión no encontrada")
    if not sees_whole_campaign(current_user, campaign) and not await can_use_outreach(current_user):
        raise HTTPException(status_code=403, detail="Sin permiso para consultar hogares")
    households, full = await visible_households(campaign, current_user)
    points = [point(item, current_user, full) for item in households]
    # Resultado de cada casa (para colorear el mapa del reporte) y, para quien ve
    # todo, el nombre del mentor (filtro por mentor). Dos consultas en lote.
    house_ids = [item["household_id"] for item in points]
    best: dict[str, str] = {}
    rank = {"seven_weeks": 4, "followup": 3, "contacted": 2}
    async for visit in db.outreach_visits.find({"household_id": {"$in": house_ids}, "archived": {"$ne": True}}, {"_id": 0, "household_id": 1, "status": 1, "enrollment_id": 1}):
        result = "seven_weeks" if visit.get("enrollment_id") else "followup" if visit.get("status") == "wants_followup" else "contacted"
        if rank[result] > rank.get(best.get(visit["household_id"]), 0):
            best[visit["household_id"]] = result
    mentor_names = {}
    if full:
        from mentorship_outreach import person_display_name
        for mentor_id in {item["mentor_person_id"] for item in points if item.get("mentor_person_id")}:
            mentor_names[mentor_id] = await person_display_name(mentor_id)
    for item in points:
        item["result"] = best.get(item["household_id"]) or ("no_answer" if item["attempts"] else "available" if item["category"] == "available" else "pending")
        item["mentor_name"] = mentor_names.get(item.get("mentor_person_id"))
    located = [item for item in points if item["latitude"] is not None]
    unlocated = [item for item in points if item["latitude"] is None]
    counts = {key: sum(1 for item in points if item["category"] == key) for key in ("mine", "available", "visited", "assigned")}
    return {
        "campaign": {"campaign_id": campaign_id, "name": campaign.get("name"), "location": campaign.get("location"), "site_meeting_point": campaign.get("site_meeting_point")},
        "scope": "all" if full else "mine", "precise": sees_precise(current_user),
        "points": located, "unlocated": unlocated, "counts": {**counts, "total": len(points), "unlocated": len(unlocated)},
        "geocoding_configured": geocoding_is_configured(),
    }


@router.put("/households/{household_id}/location", response_model=dict)
async def set_household_location(household_id: str, payload: LocationInput, current_user: dict = Depends(get_current_user)):
    """El mentor responsable (o quien ve toda la invasión) guarda la ubicación:
    'Usar mi ubicación actual' (gps, con precisión) o un punto/texto manual."""
    household = await load_household(household_id)
    campaign = await campaign_doc(household.get("campaign_id"))
    if not can_edit_location(current_user, household, campaign):
        raise HTTPException(status_code=403, detail="Solo el mentor responsable o un líder de la invasión ubica esta casa")
    update: dict = {"location_updated_at": now_utc(), "location_updated_by_user_id": current_user["user_id"], "updated_at": now_utc()}
    if "reference" in payload.model_fields_set:
        update["location_reference"] = (payload.reference or "").strip() or None
    if payload.latitude is not None:
        update.update({"latitude": payload.latitude, "longitude": payload.longitude, "location_accuracy_m": payload.accuracy_m,
                       "location_source": payload.source, "geocoding_status": None, "location_approx": False})
        if household.get("location_approx") and "reference" not in payload.model_fields_set and (household.get("location_reference") or "").startswith(("Aproximada", "Ubicación aproximada")):
            update["location_reference"] = None  # ya no es el punto aproximado de la calle
    elif "reference" not in payload.model_fields_set:
        raise HTTPException(status_code=422, detail="Indique coordenadas o una referencia")
    await db.outreach_households.update_one({"household_id": household_id}, {"$set": update})
    refreshed = await load_household(household_id)
    duplicates = await find_duplicates(refreshed.get("campaign_id"), refreshed.get("address_line1"), refreshed.get("latitude"), refreshed.get("longitude"), household_id, current_user)
    return {"household": serialize(refreshed), "low_accuracy": bool(payload.accuracy_m and payload.accuracy_m > LOW_ACCURACY_M), "duplicates": duplicates}


async def find_duplicates(campaign_id: Optional[str], address: Optional[str], lat: Optional[float], lng: Optional[float], exclude_id: Optional[str], current_user: dict) -> dict:
    if not campaign_id:
        return {"items": [], "hidden": 0}
    campaign = await campaign_doc(campaign_id)
    full = sees_whole_campaign(current_user, campaign) if campaign else False
    me = current_user.get("person_id")
    wanted = normalize_address(address)
    items, hidden = [], 0
    async for other in db.outreach_households.find({"campaign_id": campaign_id, "archived": {"$ne": True}, "household_id": {"$ne": exclude_id}}, {"_id": 0}):
        same_address = bool(wanted) and normalize_address(other.get("address_line1")) == wanted
        near = None
        if lat is not None and lng is not None and has_coordinates(other):
            near = distance_m(lat, lng, other["latitude"], other["longitude"])
        if not same_address and not (near is not None and near <= DUPLICATE_RADIUS_M):
            continue
        visible = full or other.get("mentor_person_id") in {None, me}
        if not visible:
            hidden += 1
            continue
        items.append({"household_id": other["household_id"], "address_line1": other.get("address_line1"), "location_reference": other.get("location_reference"),
                      "same_address": same_address, "distance_m": round(near, 1) if near is not None else None,
                      "category": "available" if other.get("mentor_person_id") is None else ("mine" if other.get("mentor_person_id") == me else "assigned")})
    return {"items": items, "hidden": hidden}


@router.post("/households/duplicates-check", response_model=dict)
async def check_duplicates(payload: DuplicateCheckInput, current_user: dict = Depends(get_current_user)):
    """Antes de agregar una casa: ¿ya hay una con la misma dirección o a menos
    de 25 m en esta invasión? Solo detalla las casas que la cuenta puede ver."""
    if not await can_use_outreach(current_user):
        raise HTTPException(status_code=403, detail="Sin permiso para consultar hogares")
    result = await find_duplicates(payload.campaign_id, payload.address_line1, payload.latitude, payload.longitude, payload.exclude_household_id, current_user)
    return {**result, "radius_m": DUPLICATE_RADIUS_M}


@router.post("/campaigns/{campaign_id}/households/geocode", response_model=dict)
async def geocode_campaign_households(campaign_id: str, current_user: dict = Depends(get_current_user)):
    """Reintenta ubicar (en segundo plano) las casas con dirección y sin coordenadas."""
    campaign = await campaign_doc(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Invasión no encontrada")
    if not sees_whole_campaign(current_user, campaign):
        raise HTTPException(status_code=403, detail="Solo un líder de la invasión puede reintentar la ubicación")
    ids = await db.outreach_households.distinct("household_id", {
        "campaign_id": campaign_id, "archived": {"$ne": True}, "address_line1": {"$nin": [None, ""]},
        "latitude": None,
    })
    await mark_pending_and_geocode(ids)
    return {"queued": len(ids), "geocoding_configured": geocoding_is_configured()}


async def ensure_indexes() -> None:
    await db.outreach_households.create_index([("campaign_id", 1), ("mentor_person_id", 1)])
    await db.outreach_households.create_index([("campaign_id", 1), ("geocoding_status", 1)])
