"""Mapa 360: endpoints agregados, precisos y de verificación manual."""
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

from bson import ObjectId
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from access_control import GEO_MANAGE_LOCATIONS, GEO_VIEW_AGGREGATE, GEO_VIEW_PRECISE, has_capability, is_global_pastoral_authority
from geo_queries import aggregate_features, cell_features, enrich_coverage, geographic_summary, person_features
from geo_provider import geocoding_is_configured
from geo_service import CHURCH_ADDRESS, CHURCH_LAT, CHURCH_LNG, archive_location, enqueue_backfill, enqueue_geo_job, now_utc, process_geo_job, process_geo_jobs, zones_geojson
from server import db, get_current_user


router = APIRouter(prefix="/api/geo", tags=["geo-360"])


class FeatureCollectionResponse(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[dict]
    meta: dict = Field(default_factory=dict)


class GeoConfigResponse(BaseModel):
    center: dict
    zones: dict
    permissions: dict
    map_policy: dict


class GeoSummaryResponse(BaseModel):
    people_total: int
    cells_total: int
    zones: dict
    review_total: int
    pending_total: int


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


def _filters(categories, stage, zone, front_group_id, cell_id, verification_status, period_start, period_end):
    return {
        "categories": [item for item in (categories or "").split(",") if item],
        "stage": stage, "zone": zone, "front_group_id": front_group_id, "cell_id": cell_id,
        "verification_status": verification_status, "period_start": period_start, "period_end": period_end,
    }


@router.get("/config", response_model=GeoConfigResponse)
async def geo_config(current_user: dict = Depends(require_any_geo)):
    return {
        "center": {"address": CHURCH_ADDRESS, "latitude": CHURCH_LAT, "longitude": CHURCH_LNG},
        "zones": zones_geojson(),
        "permissions": {
            "view_aggregate": True,
            "view_precise": is_global_pastoral_authority(current_user) or has_capability(current_user, GEO_VIEW_PRECISE),
            "manage_locations": is_global_pastoral_authority(current_user) or has_capability(current_user, GEO_MANAGE_LOCATIONS),
        },
        "map_policy": {"aggregate_minimum": 3, "coverage_gap_miles": 3, "renderer": "maplibre", "tiles": "openstreetmap", "geocoding_configured": geocoding_is_configured()},
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
    return await geographic_summary(db, current_user)


@router.get("/aggregate", response_model=FeatureCollectionResponse)
async def aggregate_map(
    entity_kind: Literal["people", "cells"] = "people", categories: Optional[str] = None,
    stage: Optional[str] = None, zone: Optional[str] = None, front_group_id: Optional[str] = None,
    cell_id: Optional[str] = None, verification_status: Optional[str] = None,
    period_start: Optional[datetime] = None, period_end: Optional[datetime] = None,
    current_user: dict = Depends(require_any_geo),
):
    filters = _filters(categories, stage, zone, front_group_id, cell_id, verification_status, period_start, period_end)
    precise = await (person_features(db, current_user, filters) if entity_kind == "people" else cell_features(db, current_user, filters))
    features = aggregate_features(precise, 3 if entity_kind == "people" else 2)
    if entity_kind == "people": features = await enrich_coverage(db, features)
    return {"features": features, "meta": {"entity_kind": entity_kind, "source_count": len(precise), "privacy": "k-anonymous"}}


@router.get("/precise", response_model=FeatureCollectionResponse)
async def precise_map(
    entity_kind: Literal["people", "cells"] = "people", categories: Optional[str] = None,
    stage: Optional[str] = None, zone: Optional[str] = None, front_group_id: Optional[str] = None,
    cell_id: Optional[str] = None, verification_status: Optional[str] = None,
    period_start: Optional[datetime] = None, period_end: Optional[datetime] = None,
    current_user: dict = Depends(require_precise),
):
    filters = _filters(categories, stage, zone, front_group_id, cell_id, verification_status, period_start, period_end)
    features = await (person_features(db, current_user, filters) if entity_kind == "people" else cell_features(db, current_user, filters))
    await db.geo_audit_log.insert_one({
        "audit_id": f"view:{current_user['user_id']}:{now_utc().timestamp()}", "actor_user_id": current_user["user_id"],
        "action": "precise_map_view", "entity_kind": entity_kind, "result_count": len(features), "occurred_at": now_utc(),
    })
    return {"features": features, "meta": {"entity_kind": entity_kind, "privacy": "precise", "audited": True}}


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
async def backfill_locations(background_tasks: BackgroundTasks, limit: int = Query(default=100, ge=1, le=1000), current_user: dict = Depends(require_manage)):
    job_ids = await enqueue_backfill(db, current_user["user_id"], limit)
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
    from geo_service import zone_for
    now = now_utc()
    await collection.update_one(query, {"$set": {
        "location": {"type": "Point", "coordinates": [payload.longitude, payload.latitude]},
        "latitude": payload.latitude, "longitude": payload.longitude, "zone_key": zone_for(payload.latitude, payload.longitude),
        "geocoding_provider": "manual", "geocoding_source": "manual", "geocoded_at": now,
        "geocoding_accuracy": "manual", "geocoding_confidence": "verified", "geocoding_status": "geocoded",
        "verification_status": "manual_verified", "coordinates_stale": False, "manual_override": True,
        "manual_override_reason": payload.reason, "manual_override_by_user_id": current_user["user_id"],
    }})
    await db.geo_review_queue.update_one({"review_id": review_id}, {"$set": {"status": "resolved", "resolution": "manual", "resolved_at": now, "resolved_by_user_id": current_user["user_id"]}})
    await db.geo_audit_log.insert_one({"audit_id": f"resolve:{review_id}:{now.timestamp()}", "actor_user_id": current_user["user_id"], "action": "manual_location_resolved", "entity_type": review["entity_type"], "entity_id": review["entity_id"], "reason": payload.reason, "occurred_at": now})
    return {"review_id": review_id, "status": "resolved", "verification_status": "manual_verified"}