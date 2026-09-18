"""Persistencia, versionado y revisión de ubicaciones geográficas."""
import math
import os
from datetime import datetime, timezone
from uuid import uuid4

from bson import ObjectId
from pymongo import ReturnDocument

from geo_provider import get_geocoding_provider


CHURCH_LAT = float(os.environ.get("GEO_CHURCH_LAT") or "39.941105761181")
CHURCH_LNG = float(os.environ.get("GEO_CHURCH_LNG") or "-83.089529154066")
CHURCH_ADDRESS = os.environ.get("GEO_CHURCH_ADDRESS") or "640 Demorest Rd, Columbus, OH 43204"

ADDRESS_FIELDS = {"linea1", "linea2", "sector", "ciudad", "provincia", "codigo_postal", "pais"}


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def zone_for(latitude: float, longitude: float) -> str:
    bearing = math.degrees(math.atan2(longitude - CHURCH_LNG, latitude - CHURCH_LAT)) % 360
    if bearing >= 315 or bearing < 45: return "north"
    if bearing < 135: return "east"
    if bearing < 225: return "south"
    return "west"


def zones_geojson() -> dict:
    west, south, east, north = -83.30, 39.75, -82.75, 40.20
    center = [CHURCH_LNG, CHURCH_LAT]
    definitions = {
        "north": [center, [west, north], [east, north], center],
        "east": [center, [east, north], [east, south], center],
        "south": [center, [east, south], [west, south], center],
        "west": [center, [west, south], [west, north], center],
    }
    return {"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[*points]]}, "properties": {"zone": key}}
        for key, points in definitions.items()
    ]}


def pending_geo_fields(version: int) -> dict:
    return {
        "address_version": version, "geocoding_status": "pending",
        "verification_status": "pending", "coordinates_stale": True,
        "geocoding_source": None, "manual_override": False,
    }


async def archive_location(db, entity_type: str, entity_id: str, doc: dict, actor_user_id: str) -> None:
    if not doc.get("location"):
        return
    snapshot = {
        "history_id": str(uuid4()), "entity_type": entity_type, "entity_id": entity_id,
        "address_version": doc.get("address_version", 1), "location": doc.get("location"),
        "zone_key": doc.get("zone_key"), "geocoding_provider": doc.get("geocoding_provider"),
        "geocoding_source": doc.get("geocoding_source"), "verification_status": "obsolete",
        "accuracy": doc.get("geocoding_accuracy"), "confidence": doc.get("geocoding_confidence"),
        "archived_by_user_id": actor_user_id, "archived_at": now_utc(),
    }
    await db.geo_location_history.insert_one(snapshot)


async def enqueue_geo_job(db, entity_type: str, entity_id: str, address_version: int, actor_user_id: str) -> str:
    job_id = f"{entity_type}:{entity_id}:{address_version}"
    await db.geo_jobs.update_one(
        {"job_id": job_id},
        {"$setOnInsert": {
            "job_id": job_id, "entity_type": entity_type, "entity_id": entity_id,
            "address_version": address_version, "status": "pending", "attempts": 0,
            "created_by_user_id": actor_user_id, "created_at": now_utc(),
        }}, upsert=True,
    )
    return job_id


async def _entity(db, entity_type: str, entity_id: str) -> dict | None:
    if entity_type == "person_address" and ObjectId.is_valid(entity_id):
        return await db.person_addresses.find_one({"_id": ObjectId(entity_id)})
    if entity_type == "cell":
        return await db.cells.find_one({"cell_id": entity_id})
    return None


def _provider_input(entity_type: str, doc: dict) -> dict:
    if entity_type == "cell":
        return {"full_address": doc.get("address")}
    state = doc.get("provincia") or "OH"
    return {
        "street": " ".join(filter(None, [doc.get("linea1"), doc.get("linea2")])),
        "city": doc.get("ciudad"), "state": state, "zip": doc.get("codigo_postal"),
    }


async def _queue_review(db, job: dict, doc: dict, result) -> None:
    review_id = f"review:{job['job_id']}"
    await db.geo_review_queue.update_one(
        {"review_id": review_id},
        {"$set": {
            "review_id": review_id, "entity_type": job["entity_type"], "entity_id": job["entity_id"],
            "address_version": job["address_version"], "reason": result.status, "status": "open",
            "person_id": doc.get("person_id"), "updated_at": now_utc(),
            "candidate_location": {"latitude": result.latitude, "longitude": result.longitude} if result.latitude is not None and result.longitude is not None else None,
            "candidate_confidence": result.confidence, "candidate_confidence_score": result.confidence_score,
        }, "$setOnInsert": {"created_at": now_utc()}}, upsert=True,
    )


async def process_geo_job(db, job_id: str) -> dict:
    job = await db.geo_jobs.find_one_and_update(
        {"job_id": job_id, "status": {"$in": ["pending", "retry"]}},
        {"$set": {"status": "processing", "started_at": now_utc()}, "$inc": {"attempts": 1}},
        return_document=ReturnDocument.AFTER,
    )
    if not job:
        return {"job_id": job_id, "status": "skipped"}
    doc = await _entity(db, job["entity_type"], job["entity_id"])
    if not doc or doc.get("address_version", 1) != job["address_version"] or doc.get("manual_override"):
        await db.geo_jobs.update_one({"job_id": job_id}, {"$set": {"status": "obsolete", "completed_at": now_utc()}})
        return {"job_id": job_id, "status": "obsolete"}
    result = await get_geocoding_provider().geocode(_provider_input(job["entity_type"], doc))
    latest = await _entity(db, job["entity_type"], job["entity_id"])
    if not latest or latest.get("address_version", 1) != job["address_version"] or latest.get("manual_override"):
        await db.geo_jobs.update_one({"job_id": job_id}, {"$set": {"status": "obsolete", "completed_at": now_utc()}})
        return {"job_id": job_id, "status": "obsolete"}
    query = {"_id": doc["_id"]}
    if result.status == "matched":
        fields = {
            "location": {"type": "Point", "coordinates": [result.longitude, result.latitude]},
            "latitude": result.latitude, "longitude": result.longitude,
            "zone_key": zone_for(result.latitude, result.longitude), "geocoding_provider": "census",
            "geocoding_provider_id": result.provider_result_id, "geocoded_at": now_utc(),
            "geocoding_accuracy": result.accuracy, "geocoding_confidence": result.confidence,
            "geocoding_confidence_score": result.confidence_score, "geocoding_status": "geocoded",
            "verification_status": "verified", "coordinates_stale": False,
            "geocoding_source": "automatic", "census_benchmark": (result.provider_metadata or {}).get("benchmark"),
            "census_matched_address": result.matched_address,
        }
        await (db.person_addresses if job["entity_type"] == "person_address" else db.cells).update_one(query, {"$set": fields})
        await db.geo_review_queue.update_many({"entity_type": job["entity_type"], "entity_id": job["entity_id"], "status": "open"}, {"$set": {"status": "resolved", "resolved_at": now_utc(), "resolution": "automatic"}})
    else:
        fields = {"geocoding_status": result.status, "verification_status": "needs_verification", "coordinates_stale": True}
        await (db.person_addresses if job["entity_type"] == "person_address" else db.cells).update_one(query, {"$set": fields})
        await _queue_review(db, job, doc, result)
    await db.geo_jobs.update_one({"job_id": job_id}, {"$set": {"status": "completed", "result_status": result.status, "completed_at": now_utc()}})
    return {"job_id": job_id, "status": result.status}


async def process_geo_jobs(db, job_ids: list[str]) -> None:
    for job_id in job_ids:
        await process_geo_job(db, job_id)


async def enqueue_backfill(db, actor_user_id: str, limit: int) -> list[str]:
    jobs = []
    addresses = await db.person_addresses.find(
        {"$or": [{"geocoding_status": {"$exists": False}}, {"geocoding_status": {"$in": ["pending", "provider_error"]}}]},
        {"_id": 1, "address_version": 1},
    ).limit(limit).to_list(limit)
    for item in addresses:
        version = item.get("address_version", 1)
        await db.person_addresses.update_one({"_id": item["_id"]}, {"$set": pending_geo_fields(version)})
        jobs.append(await enqueue_geo_job(db, "person_address", str(item["_id"]), version, actor_user_id))
    remaining = max(0, limit - len(jobs))
    cells = await db.cells.find(
        {"address": {"$nin": [None, ""]}, "$or": [{"geocoding_status": {"$exists": False}}, {"geocoding_status": {"$in": ["pending", "provider_error"]}}]},
        {"_id": 1, "cell_id": 1, "address_version": 1},
    ).limit(remaining).to_list(remaining)
    for item in cells:
        version = item.get("address_version", 1)
        await db.cells.update_one({"cell_id": item["cell_id"]}, {"$set": pending_geo_fields(version)})
        jobs.append(await enqueue_geo_job(db, "cell", item["cell_id"], version, actor_user_id))
    return jobs


async def ensure_geo_indexes(db) -> None:
    await db.person_addresses.create_index([("location", "2dsphere")], sparse=True)
    await db.cells.create_index([("location", "2dsphere")], sparse=True)
    await db.geo_jobs.create_index("job_id", unique=True)
    await db.geo_jobs.create_index([("status", 1), ("created_at", 1)])
    await db.geo_review_queue.create_index("review_id", unique=True)
    await db.geo_review_queue.create_index([("status", 1), ("created_at", 1)])
    await db.geo_location_history.create_index([("entity_type", 1), ("entity_id", 1), ("address_version", -1)])
    await db.geo_audit_log.create_index([("actor_user_id", 1), ("occurred_at", -1)])