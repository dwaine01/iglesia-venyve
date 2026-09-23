"""Mapa 360: endpoints agregados, precisos y de verificación manual."""
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional
from uuid import uuid4

from bson import ObjectId
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from pymongo import ReturnDocument

from access_control import GEO_MANAGE_LOCATIONS, GEO_VIEW_AGGREGATE, GEO_VIEW_PRECISE, has_capability, is_global_pastoral_authority
from geo_address import address_completeness_reasons, normalize_address_document
from geo_queries import aggregate_features, cell_features, enrich_coverage, front_group_centroid_features, geographic_summary, household_features, person_features, search_person_locations, unlocated_person_items
from geo_provider import geocoding_is_configured, geocoding_providers_status
from geo_service import CHURCH_ADDRESS, CHURCH_LAT, CHURCH_LNG, archive_location, enqueue_backfill, enqueue_geo_job, geographic_classification, now_utc, process_geo_job, process_geo_jobs, subzones_geojson, zones_geojson
from geo_sector_service import point_in_polygon, reassign_sector_memberships, sector_assignment_fields, validate_polygon
from process_engine import access_person_ids
from server import db, get_current_user


router = APIRouter(prefix="/api/geo", tags=["geo-360"])


class FeatureCollectionResponse(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[dict]
    meta: dict = Field(default_factory=dict)


class GeoConfigResponse(BaseModel):
    center: dict
    zones: dict
    subzones: dict
    permissions: dict
    map_policy: dict


class GeoSummaryResponse(BaseModel):
    people_total: int
    cells_total: int
    front_groups_total: int = 0
    zones: dict
    review_total: int
    pending_total: int
    unlocated_total: int = 0


class UnlocatedPerson(BaseModel):
    person_id: str
    person_number: Optional[str] = None
    name: str
    reason: str
    has_address: bool
    has_household: bool
    profile_path: str


class UnlocatedPeopleResponse(BaseModel):
    items: list[UnlocatedPerson]
    total: int
    reasons: dict[str, int]


class GeoCatalogResponse(BaseModel):
    front_groups: list[dict]
    cells: list[dict]
    stages: list[dict]


class ReviewListResponse(BaseModel):
    items: list[dict]
    total: int


class ManualLocation(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    reason: str = Field(min_length=3, max_length=1000)


class LocationConfirmation(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class LocationConfirmationResponse(BaseModel):
    person_id: str
    address_id: str
    verification_status: Literal["manual_verified"]
    confirmed_at: str


class SectorCreate(BaseModel):
    zone_id: Literal["north", "east", "south", "west"]
    name: Optional[str] = Field(default=None, max_length=120)
    description: Optional[str] = Field(default=None, max_length=1000)
    color: str = Field(default="#3B82F6", pattern=r"^#[0-9A-Fa-f]{6}$")
    geometry: dict
    allow_overlap: bool = False


class SectorUpdate(BaseModel):
    zone_id: Optional[Literal["north", "east", "south", "west"]] = None
    name: Optional[str] = Field(default=None, min_length=2, max_length=120)
    description: Optional[str] = Field(default=None, max_length=1000)
    color: Optional[str] = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    geometry: Optional[dict] = None
    status: Optional[Literal["active", "inactive"]] = None
    allow_overlap: bool = False


class SectorStats(BaseModel):
    people_count: int = 0
    households_count: int = 0
    leaders_count: int = 0
    cells_count: int = 0
    suppressed: bool = False


class SectorResponse(BaseModel):
    sector_id: str
    zone_id: str
    zone_number: int
    order: int
    name: str
    description: Optional[str] = None
    color: str
    geometry: dict
    status: str
    created_at: str
    updated_at: str
    created_by: str
    updated_by: str
    archived_at: Optional[str] = None
    archived_by: Optional[str] = None
    stats: SectorStats = Field(default_factory=SectorStats)


class SectorListResponse(BaseModel):
    items: list[SectorResponse]
    total: int
    privacy: str


class GeocodingAuditIssue(BaseModel):
    address_id: str
    person_id: Optional[str] = None
    reasons: list[str]
    provider: Optional[str] = None
    verification_status: Optional[str] = None
    confidence_score: Optional[float] = None
    accuracy: Optional[str] = None
    sector_id: Optional[str] = None


class GeocodingAuditResponse(BaseModel):
    total_addresses: int
    complete_addresses: int
    verified_coordinates: int
    review_required: int
    low_confidence: int
    without_sector: int
    providers: dict
    issues: list[GeocodingAuditIssue]
    audited_at: str


def require_geo(capability: str):
    def dependency(current_user: dict = Depends(get_current_user)) -> dict:
        if not is_global_pastoral_authority(current_user) and not has_capability(current_user, capability):
            raise HTTPException(status_code=403, detail="Sin permiso para este nivel del Mapa 360")
        return current_user
    return dependency


require_aggregate = require_geo(GEO_VIEW_AGGREGATE)
require_precise = require_geo(GEO_VIEW_PRECISE)
require_manage = require_geo(GEO_MANAGE_LOCATIONS)


def require_any_geo(current_user: dict = Depends(get_current_user)) -> dict:
    allowed = any(has_capability(current_user, item) for item in (GEO_VIEW_AGGREGATE, GEO_VIEW_PRECISE, GEO_MANAGE_LOCATIONS))
    if not is_global_pastoral_authority(current_user) and not allowed:
        raise HTTPException(status_code=403, detail="Sin permiso para abrir Mapa 360")
    return current_user


ZONE_NUMBERS = {"north": 1, "east": 2, "south": 3, "west": 4}


def _iso(value) -> str:
    if isinstance(value, str):
        return value
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def _sector_item(doc: dict, stats: Optional[dict] = None) -> dict:
    return {
        "sector_id": doc["sector_id"], "zone_id": doc["zone_id"], "zone_number": doc["zone_number"],
        "order": doc["order"], "name": doc["name"], "description": doc.get("description"),
        "color": doc["color"], "geometry": doc["geometry"], "status": doc["status"],
        "created_at": _iso(doc["created_at"]), "updated_at": _iso(doc["updated_at"]),
        "created_by": doc["created_by"], "updated_by": doc["updated_by"],
        "archived_at": _iso(doc["archived_at"]) if doc.get("archived_at") else None,
        "archived_by": doc.get("archived_by"), "stats": stats or {},
    }


async def _overlapping_sectors(zone_id: str, geometry: dict, exclude_sector_id: Optional[str] = None) -> list[dict]:
    query = {"zone_id": zone_id, "status": "active", "geometry": {"$geoIntersects": {"$geometry": geometry}}}
    if exclude_sector_id:
        query["sector_id"] = {"$ne": exclude_sector_id}
    return await db.geo_sectors.find(query, {"_id": 0, "sector_id": 1, "name": 1, "order": 1}).sort("order", 1).to_list(100)


async def _sector_statistics(sectors: list[dict], current_user: dict, precise: bool) -> dict[str, dict]:
    people = await person_features(db, current_user, {})
    households = await household_features(db, current_user, people)
    cells = await cell_features(db, current_user, {})
    person_ids = [item["properties"]["entity_id"] for item in people]
    leadership_docs = await db.person_leadership_status.find(
        {"person_id": {"$in": person_ids}, "status": {"$nin": ["inactive", "revoked", "archived"]}},
        {"_id": 0, "person_id": 1},
    ).to_list(50000) if person_ids else []
    leader_ids = {item["person_id"] for item in leadership_docs}
    output = {}
    for sector in sectors:
        geometry = sector["geometry"]
        sector_people = [item for item in people if point_in_polygon(*item["geometry"]["coordinates"], geometry)]
        sector_households = [item for item in households if point_in_polygon(*item["geometry"]["coordinates"], geometry)]
        sector_cells = [item for item in cells if point_in_polygon(*item["geometry"]["coordinates"], geometry)]
        stats = {
            "people_count": len(sector_people), "households_count": len(sector_households),
            "leaders_count": sum(item["properties"]["entity_id"] in leader_ids for item in sector_people),
            "cells_count": len(sector_cells), "suppressed": False,
        }
        if not precise and stats["people_count"] < 3:
            stats.update({"people_count": 0, "households_count": 0, "leaders_count": 0, "suppressed": True})
        output[sector["sector_id"]] = stats
    return output


async def _audit_sector_change(current_user: dict, action: str, sector_id: str, details: Optional[dict] = None) -> None:
    await db.geo_audit_log.insert_one({
        "audit_id": f"{action}:{sector_id}:{now_utc().timestamp()}", "actor_user_id": current_user["user_id"],
        "action": action, "entity_type": "geo_sector", "entity_id": sector_id,
        "details": details or {}, "occurred_at": now_utc(),
    })


def _filters(categories, stage, zone, subzone, front_group_id, cell_id, verification_status, period_start, period_end):
    return {
        "categories": [item for item in (categories or "").split(",") if item],
        "stage": stage, "zone": zone, "subzone": subzone, "front_group_id": front_group_id, "cell_id": cell_id,
        "verification_status": verification_status, "period_start": period_start, "period_end": period_end,
    }


@router.get("/config", response_model=GeoConfigResponse)
async def geo_config(current_user: dict = Depends(require_any_geo)):
    return {
        "center": {"address": CHURCH_ADDRESS, "latitude": CHURCH_LAT, "longitude": CHURCH_LNG},
        "zones": zones_geojson(),
        "subzones": subzones_geojson(),
        "permissions": {
            "view_aggregate": True,
            "view_precise": is_global_pastoral_authority(current_user) or has_capability(current_user, GEO_VIEW_PRECISE),
            "manage_locations": is_global_pastoral_authority(current_user) or has_capability(current_user, GEO_MANAGE_LOCATIONS),
        },
        "map_policy": {"aggregate_minimum": 3, "coverage_gap_miles": 3, "renderer": "maplibre", "tiles": "openstreetmap", "geocoding_configured": geocoding_is_configured(), "geocoding_providers": geocoding_providers_status(), "geocoding_order": ["census", "geocodio"]},
    }


@router.get("/catalog", response_model=GeoCatalogResponse)
async def geo_catalog(current_user: dict = Depends(require_any_geo)):
    groups = await db.front_groups.find({"status": {"$ne": "archived"}}, {"_id": 0, "front_group_id": 1, "name": 1}).sort("name", 1).to_list(1000)
    cells = await db.cells.find({"status": {"$ne": "closed"}}, {"_id": 0, "cell_id": 1, "name": 1, "code": 1}).sort("name", 1).to_list(10000)
    definition = await db.process_definitions.find_one({"process_key": "consolidation", "version": 2}, {"_id": 0, "stages": 1})
    stages = [{"stage_key": item["key"], "stage_name": item["name"], "stage_order": item["order"]} for item in (definition or {}).get("stages", [])]
    return {"front_groups": groups, "cells": cells, "stages": stages}


@router.get("/summary", response_model=GeoSummaryResponse)
async def geo_summary(current_user: dict = Depends(require_any_geo)):
    summary = await geographic_summary(db, current_user)
    if is_global_pastoral_authority(current_user) or has_capability(current_user, GEO_MANAGE_LOCATIONS):
        summary["unlocated_total"] = len(await unlocated_person_items(db, current_user))
    return summary


@router.get("/unlocated-persons", response_model=UnlocatedPeopleResponse)
async def unlocated_people(current_user: dict = Depends(require_manage)):
    items = await unlocated_person_items(db, current_user)
    reasons = {}
    for item in items: reasons[item["reason"]] = reasons.get(item["reason"], 0) + 1
    return {"items": items, "total": len(items), "reasons": reasons}


@router.get("/sectors", response_model=SectorListResponse)
async def list_sectors(
    zone_id: Optional[Literal["north", "east", "south", "west"]] = None,
    include_inactive: bool = False,
    current_user: dict = Depends(require_any_geo),
):
    can_manage = is_global_pastoral_authority(current_user) or has_capability(current_user, GEO_MANAGE_LOCATIONS)
    query = {}
    if zone_id: query["zone_id"] = zone_id
    if not include_inactive or not can_manage: query["status"] = "active"
    sectors = await db.geo_sectors.find(query, {"_id": 0}).sort([("zone_number", 1), ("order", 1)]).to_list(1000)
    precise = is_global_pastoral_authority(current_user) or has_capability(current_user, GEO_VIEW_PRECISE)
    stats = await _sector_statistics(sectors, current_user, precise)
    return {"items": [_sector_item(item, stats.get(item["sector_id"])) for item in sectors], "total": len(sectors), "privacy": "precise" if precise else "aggregate"}


@router.get("/sectors/locate", response_model=dict)
async def locate_sector(
    latitude: float = Query(ge=-90, le=90), longitude: float = Query(ge=-180, le=180),
    current_user: dict = Depends(require_any_geo),
):
    classification = geographic_classification(latitude, longitude)
    assignment = await sector_assignment_fields(db, latitude, longitude, classification["zone_key"])
    return {"latitude": latitude, "longitude": longitude, **classification, **assignment}


@router.get("/sectors/{sector_id}", response_model=SectorResponse)
async def get_sector(sector_id: str, current_user: dict = Depends(require_any_geo)):
    sector = await db.geo_sectors.find_one({"sector_id": sector_id, "status": {"$ne": "archived"}}, {"_id": 0})
    if not sector: raise HTTPException(status_code=404, detail="Sector no encontrado")
    precise = is_global_pastoral_authority(current_user) or has_capability(current_user, GEO_VIEW_PRECISE)
    stats = await _sector_statistics([sector], current_user, precise)
    return _sector_item(sector, stats[sector_id])


@router.post("/sectors", response_model=SectorResponse, status_code=status.HTTP_201_CREATED)
async def create_sector(payload: SectorCreate, current_user: dict = Depends(require_manage)):
    try: geometry = validate_polygon(payload.geometry)
    except ValueError as error: raise HTTPException(status_code=422, detail=str(error)) from error
    conflicts = await _overlapping_sectors(payload.zone_id, geometry)
    if conflicts and not payload.allow_overlap:
        raise HTTPException(status_code=409, detail={"code": "SECTOR_OVERLAP", "message": "El polígono se superpone con sectores activos de la misma Zona", "conflicts": conflicts})
    counter = await db.geo_sector_counters.find_one_and_update(
        {"_id": payload.zone_id}, {"$inc": {"sequence": 1}, "$setOnInsert": {"created_at": now_utc()}},
        upsert=True, return_document=ReturnDocument.AFTER,
    )
    order = counter["sequence"]; now = now_utc(); sector_id = str(uuid4())
    doc = {
        "sector_id": sector_id, "zone_id": payload.zone_id, "zone_number": ZONE_NUMBERS[payload.zone_id],
        "order": order, "name": (payload.name or f"Sector {ZONE_NUMBERS[payload.zone_id]}-{order}").strip(),
        "description": (payload.description or "").strip() or None, "color": payload.color.upper(),
        "geometry": geometry, "status": "active", "created_at": now, "updated_at": now,
        "created_by": current_user["user_id"], "updated_by": current_user["user_id"],
    }
    await db.geo_sectors.insert_one(doc)
    await reassign_sector_memberships(db)
    await _audit_sector_change(current_user, "sector_created", sector_id, {"zone_id": payload.zone_id, "overlap_authorized": bool(conflicts)})
    return _sector_item(doc)


@router.put("/sectors/{sector_id}", response_model=SectorResponse)
async def update_sector(sector_id: str, payload: SectorUpdate, current_user: dict = Depends(require_manage)):
    existing = await db.geo_sectors.find_one({"sector_id": sector_id, "status": {"$ne": "archived"}}, {"_id": 0})
    if not existing: raise HTTPException(status_code=404, detail="Sector no encontrado")
    update = payload.model_dump(exclude_none=True, exclude={"allow_overlap"})
    zone_id = update.get("zone_id", existing["zone_id"])
    geometry = existing["geometry"]
    if "geometry" in update:
        try: geometry = validate_polygon(update["geometry"])
        except ValueError as error: raise HTTPException(status_code=422, detail=str(error)) from error
        update["geometry"] = geometry
    conflicts = await _overlapping_sectors(zone_id, geometry, sector_id)
    if conflicts and update.get("status", existing["status"]) == "active" and not payload.allow_overlap:
        raise HTTPException(status_code=409, detail={"code": "SECTOR_OVERLAP", "message": "El polígono se superpone con sectores activos de la misma Zona", "conflicts": conflicts})
    if zone_id != existing["zone_id"]:
        counter = await db.geo_sector_counters.find_one_and_update(
            {"_id": zone_id}, {"$inc": {"sequence": 1}, "$setOnInsert": {"created_at": now_utc()}},
            upsert=True, return_document=ReturnDocument.AFTER,
        )
        update.update({"zone_number": ZONE_NUMBERS[zone_id], "order": counter["sequence"]})
    if "name" in update: update["name"] = update["name"].strip()
    if "description" in update: update["description"] = update["description"].strip() or None
    if "color" in update: update["color"] = update["color"].upper()
    update.update({"updated_at": now_utc(), "updated_by": current_user["user_id"]})
    result = await db.geo_sectors.find_one_and_update({"sector_id": sector_id}, {"$set": update}, return_document=ReturnDocument.AFTER, projection={"_id": 0})
    await reassign_sector_memberships(db)
    await _audit_sector_change(current_user, "sector_updated", sector_id, {"changed_fields": sorted(update), "overlap_authorized": bool(conflicts)})
    return _sector_item(result)


@router.delete("/sectors/{sector_id}", response_model=SectorResponse)
async def deactivate_sector(sector_id: str, current_user: dict = Depends(require_manage)):
    now = now_utc()
    result = await db.geo_sectors.find_one_and_update(
        {"sector_id": sector_id, "status": {"$ne": "archived"}},
        {"$set": {"status": "inactive", "archived_at": now, "archived_by": current_user["user_id"], "updated_at": now, "updated_by": current_user["user_id"]}},
        return_document=ReturnDocument.AFTER, projection={"_id": 0},
    )
    if not result: raise HTTPException(status_code=404, detail="Sector no encontrado")
    await reassign_sector_memberships(db)
    await _audit_sector_change(current_user, "sector_deactivated", sector_id)
    return _sector_item(result)


@router.get("/geocoding-audit", response_model=GeocodingAuditResponse)
async def geocoding_audit(current_user: dict = Depends(require_manage)):
    allowed = await access_person_ids(db, current_user)
    query = {} if allowed is None else {"person_id": {"$in": list(allowed)}}
    docs = await db.person_addresses.find(query, {
        "_id": 1, "person_id": 1, "linea1": 1, "linea2": 1, "ciudad": 1, "provincia": 1, "codigo_postal": 1, "pais": 1,
        "location": 1, "latitude": 1, "longitude": 1, "geocoding_provider": 1, "geocoding_confidence_score": 1,
        "geocoding_accuracy": 1, "verification_status": 1, "sector_id": 1,
    }).to_list(50000)
    active_sector_count = await db.geo_sectors.count_documents({"status": "active"})
    issues = []; providers = {}; complete = verified = low_confidence = without_sector = 0
    broad_accuracy = {"place", "county", "state", "street_center", "intersection"}
    for doc in docs:
        reasons = address_completeness_reasons(doc); normalized = normalize_address_document(doc)
        if normalized["address_complete"]: complete += 1
        location = doc.get("location") or {}; coordinates = location.get("coordinates") or []
        valid_coordinates = location.get("type") == "Point" and len(coordinates) == 2 and -180 <= coordinates[0] <= 180 and -90 <= coordinates[1] <= 90
        if not valid_coordinates: reasons.append("coordinates_missing_or_invalid")
        score = doc.get("geocoding_confidence_score")
        accuracy = str(doc.get("geocoding_accuracy") or "unknown").lower()
        if score is not None and score < 0.8: reasons.append("confidence_below_0_8"); low_confidence += 1
        if accuracy in broad_accuracy: reasons.append(f"accuracy_type_{accuracy}")
        if doc.get("verification_status") not in {"verified", "manual_verified"}: reasons.append("verification_required")
        if valid_coordinates and doc.get("verification_status") in {"verified", "manual_verified"} and not reasons: verified += 1
        if active_sector_count and valid_coordinates and not doc.get("sector_id"): reasons.append("sector_unassigned"); without_sector += 1
        provider = doc.get("geocoding_provider") or "unknown"; providers[provider] = providers.get(provider, 0) + 1
        if reasons:
            issues.append({
                "address_id": str(doc["_id"]), "person_id": doc.get("person_id"), "reasons": sorted(set(reasons)),
                "provider": doc.get("geocoding_provider"), "verification_status": doc.get("verification_status"),
                "confidence_score": score, "accuracy": doc.get("geocoding_accuracy"), "sector_id": doc.get("sector_id"),
            })
    return {
        "total_addresses": len(docs), "complete_addresses": complete, "verified_coordinates": verified,
        "review_required": len(issues), "low_confidence": low_confidence, "without_sector": without_sector,
        "providers": providers, "issues": issues, "audited_at": now_utc().isoformat(),
    }


@router.get("/aggregate", response_model=FeatureCollectionResponse)
async def aggregate_map(
    entity_kind: Literal["people", "cells"] = "people", categories: Optional[str] = None,
    stage: Optional[str] = None, zone: Optional[str] = None, subzone: Optional[str] = None, front_group_id: Optional[str] = None,
    cell_id: Optional[str] = None, verification_status: Optional[str] = None,
    period_start: Optional[datetime] = None, period_end: Optional[datetime] = None,
    current_user: dict = Depends(require_any_geo),
):
    filters = _filters(categories, stage, zone, subzone, front_group_id, cell_id, verification_status, period_start, period_end)
    precise = await (person_features(db, current_user, filters) if entity_kind == "people" else cell_features(db, current_user, filters))
    features = aggregate_features(precise, 3 if entity_kind == "people" else 2)
    if entity_kind == "people": features = await enrich_coverage(db, features)
    return {"features": features, "meta": {"entity_kind": entity_kind, "source_count": len(precise), "privacy": "k-anonymous"}}


@router.get("/precise", response_model=FeatureCollectionResponse)
async def precise_map(
    entity_kind: Literal["people", "cells"] = "people", categories: Optional[str] = None,
    stage: Optional[str] = None, zone: Optional[str] = None, subzone: Optional[str] = None, front_group_id: Optional[str] = None,
    cell_id: Optional[str] = None, verification_status: Optional[str] = None,
    period_start: Optional[datetime] = None, period_end: Optional[datetime] = None,
    current_user: dict = Depends(require_precise),
):
    filters = _filters(categories, stage, zone, subzone, front_group_id, cell_id, verification_status, period_start, period_end)
    if entity_kind == "people":
        people = await person_features(db, current_user, filters)
        features = await household_features(db, current_user, people)
        features.extend(await front_group_centroid_features(db, current_user, filters))
    else:
        features = await cell_features(db, current_user, filters)
    await db.geo_audit_log.insert_one({
        "audit_id": f"view:{current_user['user_id']}:{now_utc().timestamp()}", "actor_user_id": current_user["user_id"],
        "action": "precise_map_view", "entity_kind": entity_kind, "result_count": len(features), "occurred_at": now_utc(),
    })
    return {"features": features, "meta": {"entity_kind": entity_kind, "privacy": "precise", "audited": True}}


@router.get("/search", response_model=dict)
async def search_locations(q: str = Query(min_length=2, max_length=120), limit: int = Query(default=10, ge=1, le=25), current_user: dict = Depends(require_precise)):
    items = await search_person_locations(db, current_user, q, limit)
    return {"items": items, "total": len(items)}


@router.post("/persons/{person_id}/confirm-location", response_model=LocationConfirmationResponse)
async def confirm_person_location(
    person_id: str,
    payload: LocationConfirmation,
    current_user: dict = Depends(require_manage),
):
    if not ObjectId.is_valid(person_id):
        raise HTTPException(status_code=404, detail="Persona no encontrada")
    person = await db.persons.find_one({"_id": ObjectId(person_id), "status": {"$ne": "archived"}}, {"_id": 1})
    if not person:
        raise HTTPException(status_code=404, detail="Persona no encontrada")
    address = await db.person_addresses.find_one(
        {"person_id": person_id, "location.type": "Point", "coordinates_stale": {"$ne": True}},
        sort=[("es_principal", -1), ("updated_at", -1)],
    )
    if not address:
        raise HTTPException(status_code=409, detail="La persona no tiene una dirección ubicable para confirmar")
    coordinates = (address.get("location") or {}).get("coordinates") or []
    if len(coordinates) != 2 or abs(coordinates[0] - payload.longitude) > 0.00075 or abs(coordinates[1] - payload.latitude) > 0.00075:
        raise HTTPException(status_code=409, detail="El punto seleccionado no coincide con la dirección actual de la persona")
    now = now_utc()
    await db.person_addresses.update_one({"_id": address["_id"]}, {"$set": {
        "verification_status": "manual_verified", "coordinates_stale": False,
        "location_confirmed_at": now, "location_confirmed_by_user_id": current_user["user_id"],
        "location_confirmation_source": "map_360",
    }})
    await db.geo_audit_log.insert_one({
        "audit_id": f"location_confirmed:{person_id}:{now.timestamp()}", "actor_user_id": current_user["user_id"],
        "action": "person_location_confirmed", "entity_type": "person_address", "entity_id": str(address["_id"]),
        "person_id": person_id, "coordinates": [payload.longitude, payload.latitude], "occurred_at": now,
    })
    return {
        "person_id": person_id, "address_id": str(address["_id"]),
        "verification_status": "manual_verified", "confirmed_at": now.isoformat(),
    }


@router.get("/comparison", response_model=dict)
async def geographic_comparison(days: int = Query(default=90, ge=7, le=730), current_user: dict = Depends(require_any_geo)):
    now = datetime.now(timezone.utc); current_start = now - timedelta(days=days); previous_start = current_start - timedelta(days=days)
    current = await person_features(db, current_user, {"period_start": current_start, "period_end": now})
    previous = await person_features(db, current_user, {"period_start": previous_start, "period_end": current_start})
    zones = {}
    for zone in ["north", "east", "south", "west"]:
        current_count = sum(item["properties"]["zone"] == zone for item in current)
        previous_count = sum(item["properties"]["zone"] == zone for item in previous)
        zones[zone] = {"current": current_count, "previous": previous_count, "change": current_count - previous_count}
    return {"days": days, "current_total": len(current), "previous_total": len(previous), "zones": zones}


@router.get("/review-queue", response_model=ReviewListResponse)
async def review_queue(current_user: dict = Depends(require_manage)):
    docs = await db.geo_review_queue.find({"status": "open"}, {"_id": 0}).sort("created_at", 1).to_list(5000)
    items = []
    for item in docs:
        if item["entity_type"] == "person_address" and ObjectId.is_valid(item["entity_id"]):
            entity = await db.person_addresses.find_one({"_id": ObjectId(item["entity_id"])}, {"_id": 0})
            person = await db.persons.find_one({"_id": ObjectId(entity["person_id"])}, {"_id": 0, "nombre": 1, "apellido": 1}) if entity and ObjectId.is_valid(entity.get("person_id", "")) else None
            label = f"{(person or {}).get('nombre', '')} {(person or {}).get('apellido', '')}".strip() or "Persona"
            address = ", ".join(str(value) for value in [entity.get("linea1"), entity.get("ciudad"), entity.get("provincia"), entity.get("codigo_postal")] if value) if entity else None
        else:
            entity = await db.cells.find_one({"cell_id": item["entity_id"]}, {"_id": 0})
            label = entity.get("name", "Célula") if entity else "Célula"
            address = entity.get("address") if entity else None
        items.append({**item, "label": label, "address": address})
    return {"items": items, "total": len(items)}


@router.post("/backfill", status_code=status.HTTP_202_ACCEPTED, response_model=dict)
async def backfill_locations(
    background_tasks: BackgroundTasks, limit: int = Query(default=100, ge=1, le=1000),
    include_verified: bool = Query(default=False), current_user: dict = Depends(require_manage),
):
    job_ids = await enqueue_backfill(db, current_user["user_id"], limit, include_verified=include_verified)
    background_tasks.add_task(process_geo_jobs, db, job_ids)
    return {"queued": len(job_ids), "status": "processing"}


@router.post("/review-queue/{review_id}/retry", status_code=status.HTTP_202_ACCEPTED, response_model=dict)
async def retry_location(review_id: str, background_tasks: BackgroundTasks, current_user: dict = Depends(require_manage)):
    review = await db.geo_review_queue.find_one({"review_id": review_id, "status": "open"}, {"_id": 0})
    if not review: raise HTTPException(status_code=404, detail="Ubicación pendiente no encontrada")
    job_id = await enqueue_geo_job(db, review["entity_type"], review["entity_id"], review["address_version"], current_user["user_id"])
    await db.geo_jobs.update_one({"job_id": job_id}, {"$set": {"status": "retry"}})
    background_tasks.add_task(process_geo_job, db, job_id)
    return {"job_id": job_id, "status": "retry"}


@router.post("/review-queue/{review_id}/resolve", response_model=dict)
async def resolve_location(review_id: str, payload: ManualLocation, current_user: dict = Depends(require_manage)):
    review = await db.geo_review_queue.find_one({"review_id": review_id, "status": "open"}, {"_id": 0})
    if not review: raise HTTPException(status_code=404, detail="Ubicación pendiente no encontrada")
    if review["entity_type"] == "person_address":
        if not ObjectId.is_valid(review["entity_id"]): raise HTTPException(status_code=404, detail="Dirección no encontrada")
        collection, query = db.person_addresses, {"_id": ObjectId(review["entity_id"])}
    else:
        collection, query = db.cells, {"cell_id": review["entity_id"]}
    entity = await collection.find_one(query)
    if not entity or entity.get("address_version", 1) != review["address_version"]:
        raise HTTPException(status_code=409, detail="La dirección cambió; vuelva a revisar la versión actual")
    await archive_location(db, review["entity_type"], review["entity_id"], entity, current_user["user_id"])
    now = now_utc()
    classification = geographic_classification(payload.latitude, payload.longitude)
    sector_fields = await sector_assignment_fields(db, payload.latitude, payload.longitude, classification["zone_key"])
    normalized_fields = normalize_address_document(entity) if review["entity_type"] == "person_address" else {}
    await collection.update_one(query, {"$set": {
        "location": {"type": "Point", "coordinates": [payload.longitude, payload.latitude]},
        "latitude": payload.latitude, "longitude": payload.longitude, **classification,
        "geocoding_provider": "manual", "geocoding_source": "manual", "geocoded_at": now,
        "geocoding_accuracy": "manual", "geocoding_confidence": "verified", "geocoding_status": "geocoded",
        "verification_status": "manual_verified", "coordinates_stale": False, "manual_override": True,
        "manual_override_reason": payload.reason, "manual_override_by_user_id": current_user["user_id"],
        **normalized_fields, **sector_fields,
    }})
    await db.geo_review_queue.update_one({"review_id": review_id}, {"$set": {"status": "resolved", "resolution": "manual", "resolved_at": now, "resolved_by_user_id": current_user["user_id"]}})
    await db.geo_audit_log.insert_one({"audit_id": f"resolve:{review_id}:{now.timestamp()}", "actor_user_id": current_user["user_id"], "action": "manual_location_resolved", "entity_type": review["entity_type"], "entity_id": review["entity_id"], "reason": payload.reason, "occurred_at": now})
    return {"review_id": review_id, "status": "resolved", "verification_status": "manual_verified"}