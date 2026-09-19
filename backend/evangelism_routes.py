"""Minicenso evangelístico: casas detectadas y ciclo de visitas."""
from datetime import datetime, timezone
import re
from typing import Literal, Optional
from uuid import uuid4

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator
from pymongo import ReturnDocument

from access_control import GEO_MANAGE_LOCATIONS, GEO_VIEW_PRECISE, has_capability, is_global_pastoral_authority
from geo_address import normalize_address_document
from geo_provider import geocoding_is_configured, get_geocoding_provider
from geo_sector_service import sector_assignment_fields
from geo_service import CHURCH_ADDRESS, CHURCH_LAT, CHURCH_LNG, geographic_classification, subzones_geojson, zones_geojson
from server import db, get_current_user


router = APIRouter(prefix="/api/geo/evangelism", tags=["evangelism-minicensus"])
TargetStatus = Literal["detected", "assigned", "visited", "follow_up", "connected", "do_not_visit"]
Language = Literal["spanish", "english", "bilingual", "other", "unknown"]


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _clean(value: Optional[str]) -> Optional[str]:
    cleaned = str(value or "").strip()
    return cleaned or None


class TargetCreate(BaseModel):
    house_number: str = Field(min_length=1, max_length=20, pattern=r"^[0-9A-Za-z-]+$")
    street_name: str = Field(min_length=2, max_length=180)
    address2: Optional[str] = Field(default=None, max_length=100)
    city: str = Field(default="Columbus", min_length=2, max_length=100)
    state: str = Field(default="OH", min_length=2, max_length=40)
    zip: Optional[str] = Field(default=None, max_length=15)
    language: Language = "unknown"
    notes: Optional[str] = Field(default=None, max_length=1000)
    pastoral_notes: Optional[str] = Field(default=None, max_length=2000)
    assigned_to_user_id: Optional[str] = None

    @field_validator("street_name", "city", "state")
    @classmethod
    def clean_required(cls, value: str) -> str:
        return value.strip()

    @field_validator("address2", "zip", "notes", "pastoral_notes")
    @classmethod
    def clean_optional(cls, value: Optional[str]) -> Optional[str]:
        return _clean(value)


class TargetUpdate(BaseModel):
    house_number: Optional[str] = Field(default=None, min_length=1, max_length=20, pattern=r"^[0-9A-Za-z-]+$")
    street_name: Optional[str] = Field(default=None, min_length=2, max_length=180)
    address2: Optional[str] = Field(default=None, max_length=100)
    city: Optional[str] = Field(default=None, min_length=2, max_length=100)
    state: Optional[str] = Field(default=None, min_length=2, max_length=40)
    zip: Optional[str] = Field(default=None, max_length=15)
    language: Optional[Language] = None
    notes: Optional[str] = Field(default=None, max_length=1000)
    pastoral_notes: Optional[str] = Field(default=None, max_length=2000)
    status: Optional[TargetStatus] = None
    assigned_to_user_id: Optional[str] = None


class TargetResponse(BaseModel):
    target_id: str
    house_number: Optional[str] = None
    street_name: str
    address2: Optional[str] = None
    city: str
    state: str
    zip: Optional[str] = None
    full_address: str
    language: str
    notes: Optional[str] = None
    pastoral_notes: Optional[str] = None
    status: str
    assigned_to_user_id: Optional[str] = None
    assigned_to_name: Optional[str] = None
    geocoding_status: str
    verification_status: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    zone_key: Optional[str] = None
    zone_number: Optional[int] = None
    subzone_key: Optional[str] = None
    sector_id: Optional[str] = None
    sector_name: Optional[str] = None
    created_by_user_id: str
    created_at: str
    updated_at: str
    can_view_precise: bool
    can_view_pastoral_notes: bool
    can_manage_details: bool


def _iso(value) -> str:
    if isinstance(value, str): return value
    if value.tzinfo is None: value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def _can_view_precise(doc: dict, current_user: dict) -> bool:
    return bool(
        is_global_pastoral_authority(current_user)
        or has_capability(current_user, GEO_VIEW_PRECISE)
        or current_user.get("user_id") in {doc.get("created_by_user_id"), doc.get("assigned_to_user_id")}
    )


def _can_manage_details(doc: dict, current_user: dict) -> bool:
    return bool(
        is_global_pastoral_authority(current_user)
        or has_capability(current_user, GEO_MANAGE_LOCATIONS)
        or current_user.get("user_id") in {doc.get("created_by_user_id"), doc.get("assigned_to_user_id")}
    )


def _item(doc: dict, current_user: dict) -> dict:
    precise = _can_view_precise(doc, current_user); pastoral = is_global_pastoral_authority(current_user)
    item = {
        "target_id": doc["target_id"], "house_number": doc["house_number"], "street_name": doc["street_name"],
        "address2": doc.get("address2"), "city": doc["city"], "state": doc["state"], "zip": doc.get("zip"),
        "full_address": doc["full_address"], "language": doc.get("language", "unknown"), "notes": doc.get("notes"), "pastoral_notes": doc.get("pastoral_notes") if pastoral else None,
        "status": doc["status"], "assigned_to_user_id": doc.get("assigned_to_user_id"), "assigned_to_name": doc.get("assigned_to_name"),
        "geocoding_status": doc.get("geocoding_status", "pending"), "verification_status": doc.get("verification_status", "pending"),
        "latitude": doc.get("latitude"), "longitude": doc.get("longitude"), "zone_key": doc.get("zone_key"),
        "zone_number": doc.get("zone_number"), "subzone_key": doc.get("subzone_key"), "sector_id": doc.get("sector_id"),
        "sector_name": doc.get("sector_name"), "created_by_user_id": doc["created_by_user_id"],
        "created_at": _iso(doc["created_at"]), "updated_at": _iso(doc["updated_at"]),
        "can_view_precise": precise, "can_view_pastoral_notes": pastoral, "can_manage_details": _can_manage_details(doc, current_user),
    }
    if not precise:
        item.update({"house_number": None, "address2": None, "zip": None, "full_address": ", ".join(filter(None, [doc["street_name"], doc["city"], doc["state"]])), "latitude": None, "longitude": None})
    return item


def _feature(doc: dict, current_user: dict) -> dict:
    item = _item(doc, current_user)
    return {"type": "Feature", "geometry": doc["location"], "properties": {"entity_kind": "evangelism_target", "entity_id": doc["target_id"], "name": item["full_address"], "address": item["full_address"], **item}}


async def _assignee(user_id: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    if not user_id:
        return None, None
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=422, detail="La persona asignada no es válida")
    user = await db.users.find_one({"_id": ObjectId(user_id), "is_active": {"$ne": False}}, {"_id": 1, "nombre": 1})
    if not user:
        raise HTTPException(status_code=422, detail="La persona asignada no tiene una cuenta activa")
    return str(user["_id"]), str(user.get("nombre") or "Usuario")


def _address_fields(values: dict) -> dict:
    full_address = " ".join(filter(None, [values["house_number"], values["street_name"]])).strip()
    document = {"linea1": full_address, "linea2": values.get("address2"), "ciudad": values["city"], "provincia": values["state"], "codigo_postal": values.get("zip"), "pais": "US"}
    return {"full_address": ", ".join(filter(None, [full_address, values.get("address2"), values["city"], values["state"], values.get("zip")])), **normalize_address_document(document)}


async def _geocode(values: dict) -> dict:
    result = await get_geocoding_provider().geocode({"street": f"{values['house_number']} {values['street_name']}", "city": values["city"], "state": values["state"], "zip": values.get("zip")})
    fields = {
        "geocoding_status": result.status,
        "verification_status": "verified" if result.status == "matched" else "needs_verification",
        "geocoding_provider": result.provider,
        "geocoding_accuracy": result.accuracy,
        "geocoding_confidence_score": result.confidence_score,
        "geocoding_matched_address": result.matched_address,
        "geocoded_at": now_utc(),
    }
    if result.latitude is not None and result.longitude is not None:
        classification = geographic_classification(result.latitude, result.longitude)
        fields.update({"location": {"type": "Point", "coordinates": [result.longitude, result.latitude]}, "latitude": result.latitude, "longitude": result.longitude, **classification, **await sector_assignment_fields(db, result.latitude, result.longitude, classification["zone_key"])})
    return fields


async def _audit(target_id: str, current_user: dict, action: str, before: Optional[dict] = None, after: Optional[dict] = None) -> None:
    event_id = str(uuid4())
    await db.evangelism_target_events.insert_one({"_id": event_id, "event_id": event_id, "target_id": target_id, "action": action, "actor_user_id": current_user["user_id"], "before": before or {}, "after": after or {}, "occurred_at": now_utc()})


@router.get("/config", response_model=dict)
async def evangelism_config(current_user: dict = Depends(get_current_user)):
    return {"center": {"address": CHURCH_ADDRESS, "latitude": CHURCH_LAT, "longitude": CHURCH_LNG}, "zones": zones_geojson(), "subzones": subzones_geojson(), "permissions": {"view_aggregate": False, "view_precise": has_capability(current_user, GEO_VIEW_PRECISE) or is_global_pastoral_authority(current_user), "manage_locations": has_capability(current_user, GEO_MANAGE_LOCATIONS) or is_global_pastoral_authority(current_user), "evangelism_manage": True, "view_pastoral_notes": is_global_pastoral_authority(current_user)}, "map_policy": {"geocoding_configured": geocoding_is_configured()}}


@router.get("/assignees", response_model=dict)
async def evangelism_assignees(q: Optional[str] = Query(default=None, max_length=80), current_user: dict = Depends(get_current_user)):
    query = {"is_active": {"$ne": False}}
    if q: query["nombre"] = {"$regex": re.escape(q), "$options": "i"}
    users = await db.users.find(query, {"_id": 1, "nombre": 1}).sort("nombre", 1).limit(200).to_list(200)
    return {"items": [{"user_id": str(item["_id"]), "name": item.get("nombre") or "Usuario"} for item in users]}


@router.get("", response_model=dict)
async def list_evangelism_targets(target_status: Optional[TargetStatus] = Query(default=None, alias="status"), assigned_to_user_id: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    query = {"archived": {"$ne": True}}
    if target_status: query["status"] = target_status
    if assigned_to_user_id: query["assigned_to_user_id"] = assigned_to_user_id
    docs = await db.evangelism_targets.find(query, {"_id": 0}).sort("updated_at", -1).limit(5000).to_list(5000)
    counts = {key: 0 for key in ["detected", "assigned", "visited", "follow_up", "connected", "do_not_visit"]}
    for item in docs: counts[item["status"]] = counts.get(item["status"], 0) + 1
    visible_features = [_feature(item, current_user) for item in docs if item.get("location") and _can_view_precise(item, current_user)]
    return {"type": "FeatureCollection", "features": visible_features, "items": [_item(item, current_user) for item in docs], "meta": {"total": len(docs), "unlocated": sum(not item.get("location") for item in docs), "restricted_precise": sum(bool(item.get("location")) and not _can_view_precise(item, current_user) for item in docs), "statuses": counts}}


@router.post("", response_model=TargetResponse, status_code=status.HTTP_201_CREATED)
async def create_evangelism_target(payload: TargetCreate, current_user: dict = Depends(get_current_user)):
    values = payload.model_dump(); assigned_id, assigned_name = await _assignee(values.pop("assigned_to_user_id"))
    if values.get("pastoral_notes") and not is_global_pastoral_authority(current_user):
        raise HTTPException(status_code=403, detail="Las notas pastorales están restringidas")
    address = _address_fields(values)
    existing = await db.evangelism_targets.find_one({"normalized_address_key": address["normalized_address_key"], "archived": {"$ne": True}}, {"_id": 0, "target_id": 1})
    if existing: raise HTTPException(status_code=409, detail="Esta casa ya está registrada en el Minicenso")
    now = now_utc(); target_id = str(uuid4())
    doc = {"_id": target_id, "target_id": target_id, **values, **address, "assigned_to_user_id": assigned_id, "assigned_to_name": assigned_name, "status": "assigned" if assigned_id else "detected", "created_by_user_id": current_user["user_id"], "updated_by_user_id": current_user["user_id"], "created_at": now, "updated_at": now, "archived": False, **await _geocode(values)}
    await db.evangelism_targets.insert_one(doc)
    await _audit(target_id, current_user, "created", after={"status": doc["status"], "assigned_to_user_id": assigned_id})
    return TargetResponse(**_item(doc, current_user))


@router.patch("/{target_id}", response_model=TargetResponse)
async def update_evangelism_target(target_id: str, payload: TargetUpdate, current_user: dict = Depends(get_current_user)):
    existing = await db.evangelism_targets.find_one({"target_id": target_id, "archived": {"$ne": True}}, {"_id": 0})
    if not existing: raise HTTPException(status_code=404, detail="Casa del Minicenso no encontrada")
    update = payload.model_dump(exclude_unset=True)
    if "pastoral_notes" in update and not is_global_pastoral_authority(current_user):
        raise HTTPException(status_code=403, detail="Las notas pastorales están restringidas")
    if "assigned_to_user_id" in update:
        update["assigned_to_user_id"], update["assigned_to_name"] = await _assignee(update["assigned_to_user_id"])
        if update["assigned_to_user_id"] and "status" not in update and existing["status"] == "detected": update["status"] = "assigned"
    if update.get("status") == "assigned" and not update.get("assigned_to_user_id", existing.get("assigned_to_user_id")):
        raise HTTPException(status_code=422, detail="Seleccione a quién se asignará la visita")
    address_keys = {"house_number", "street_name", "address2", "city", "state", "zip"}
    if address_keys.intersection(update):
        if not _can_manage_details(existing, current_user):
            raise HTTPException(status_code=403, detail="La dirección precisa solo puede editarla el creador, responsable o autoridad geográfica")
        values = {**existing, **update}; address = _address_fields(values)
        duplicate = await db.evangelism_targets.find_one({"normalized_address_key": address["normalized_address_key"], "target_id": {"$ne": target_id}, "archived": {"$ne": True}}, {"_id": 0, "target_id": 1})
        if duplicate: raise HTTPException(status_code=409, detail="Otra casa ya usa esta dirección")
        update.update(address); update.update(await _geocode(values))
    update.update({"updated_by_user_id": current_user["user_id"], "updated_at": now_utc()})
    result = await db.evangelism_targets.find_one_and_update({"target_id": target_id}, {"$set": update}, return_document=ReturnDocument.AFTER, projection={"_id": 0})
    await _audit(target_id, current_user, "updated", before={"status": existing.get("status"), "assigned_to_user_id": existing.get("assigned_to_user_id")}, after={"status": result.get("status"), "assigned_to_user_id": result.get("assigned_to_user_id")})
    return TargetResponse(**_item(result, current_user))


@router.delete("/{target_id}", response_model=dict)
async def archive_evangelism_target(target_id: str, current_user: dict = Depends(get_current_user)):
    target = await db.evangelism_targets.find_one({"target_id": target_id, "archived": {"$ne": True}}, {"_id": 0})
    if not target: raise HTTPException(status_code=404, detail="Casa del Minicenso no encontrada")
    if not _can_manage_details(target, current_user): raise HTTPException(status_code=403, detail="Solo creador, responsable o autoridad geográfica puede archivar")
    result = await db.evangelism_targets.update_one({"target_id": target_id, "archived": {"$ne": True}}, {"$set": {"archived": True, "archived_at": now_utc(), "archived_by_user_id": current_user["user_id"], "updated_at": now_utc()}})
    if result.modified_count != 1: raise HTTPException(status_code=404, detail="Casa del Minicenso no encontrada")
    await _audit(target_id, current_user, "archived")
    return {"target_id": target_id, "archived": True}


async def ensure_evangelism_indexes() -> None:
    await db.evangelism_targets.create_index("target_id", unique=True)
    await db.evangelism_targets.create_index("normalized_address_key", unique=True, partialFilterExpression={"archived": False})
    await db.evangelism_targets.create_index([("location", "2dsphere")], sparse=True)
    await db.evangelism_targets.create_index([("status", 1), ("updated_at", -1)])
    await db.evangelism_targets.create_index([("assigned_to_user_id", 1), ("status", 1)])
    await db.evangelism_target_events.create_index("event_id", unique=True)
    await db.evangelism_target_events.create_index([("target_id", 1), ("occurred_at", -1)])