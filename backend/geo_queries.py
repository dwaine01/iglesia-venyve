"""Consultas geográficas autorizadas y serializadores sin ObjectId."""
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone

from bson import ObjectId

from cellular_engine import cellular_scope
from geo_service import zone_for
from process_engine import access_person_ids


def _iso(value) -> str | None:
    if not value: return None
    if isinstance(value, str): return value
    if value.tzinfo is None: value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def _as_datetime(value):
    if not value: return None
    if isinstance(value, datetime): return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
    try: return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError: return None


def _haversine_miles(lat1, lng1, lat2, lng2):
    radius = 3958.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat, dlng = math.radians(lat2 - lat1), math.radians(lng2 - lng1)
    value = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlng / 2) ** 2
    return radius * 2 * math.asin(math.sqrt(value))


def _address_text(item: dict) -> str:
    return ", ".join(str(value) for value in [
        item.get("linea1") or item.get("address"), item.get("linea2"), item.get("ciudad"),
        item.get("provincia"), item.get("codigo_postal"),
    ] if value)


async def person_features(db, current_user: dict, filters: dict) -> list[dict]:
    query = {
        "location.type": "Point", "coordinates_stale": {"$ne": True},
        "verification_status": {"$in": ["verified", "manual_verified"]},
    }
    if filters.get("verification_status"):
        query["verification_status"] = filters["verification_status"]
    address_docs = await db.person_addresses.find(query, {"_id": 0}).sort([("es_principal", -1), ("updated_at", -1)]).to_list(30000)
    selected = {}
    for address in address_docs:
        selected.setdefault(address["person_id"], address)
    allowed = await access_person_ids(db, current_user)
    person_ids = [person_id for person_id in selected if allowed is None or person_id in allowed]
    object_ids = [ObjectId(item) for item in person_ids if ObjectId.is_valid(item)]
    people = await db.persons.find({"_id": {"$in": object_ids}, "status": {"$ne": "archived"}}, {
        "_id": 1, "person_number": 1, "nombre": 1, "apellido": 1, "created_at": 1,
    }).to_list(30000)
    person_ids = [str(item["_id"]) for item in people]
    memberships = await db.person_memberships.find({"person_id": {"$in": person_ids}, "status": "active"}, {"_id": 0}).to_list(30000)
    membership_by_person = {item["person_id"]: item for item in memberships}
    enrollments = await db.process_enrollments.find({"person_id": {"$in": person_ids}, "process_key": {"$in": ["consolidation", "discipleship"]}}, {"_id": 0}).to_list(60000)
    enrollment_by_person = defaultdict(list)
    for item in enrollments: enrollment_by_person[item["person_id"]].append(item)
    group_assignments = await db.front_group_assignments.find({"person_id": {"$in": person_ids}, "active": True}, {"_id": 0}).to_list(30000)
    group_by_person = {item["person_id"]: item["front_group_id"] for item in group_assignments}
    cell_memberships = await db.cell_memberships.find({"person_id": {"$in": person_ids}, "active": True, "membership_type": "primary"}, {"_id": 0}).to_list(30000)
    cell_by_person = {item["person_id"]: item["cell_id"] for item in cell_memberships}
    contacts = await db.person_contacts.find({"person_id": {"$in": person_ids}, "es_principal": True}, {"_id": 0, "person_id": 1, "valor": 1}).to_list(30000)
    phone_by_person = {item["person_id"]: item.get("valor") for item in contacts}
    requested_categories = set(filters.get("categories") or [])
    period_start, period_end = _as_datetime(filters.get("period_start")), _as_datetime(filters.get("period_end"))
    features = []
    for person in people:
        person_id = str(person["_id"]); address = selected[person_id]
        created_at = _as_datetime(person.get("created_at"))
        if period_start and (not created_at or created_at < period_start): continue
        if period_end and (not created_at or created_at > period_end): continue
        person_enrollments = enrollment_by_person.get(person_id, [])
        active_consolidation = next((item for item in person_enrollments if item.get("process_key") == "consolidation" and item.get("status") in {"planned", "active", "paused"}), None)
        discipleship = next((item for item in person_enrollments if item.get("process_key") == "discipleship" and item.get("status") in {"planned", "active", "completed"}), None)
        categories = set()
        if person_id in membership_by_person: categories.add("members")
        if created_at and (datetime.now(timezone.utc) - created_at).days <= 90: categories.add("new")
        if active_consolidation: categories.add("consolidation")
        if discipleship: categories.add("discipleship")
        if person_id in group_by_person: categories.add("front_group")
        if person_id in cell_by_person: categories.add("cell")
        if requested_categories and not categories.intersection(requested_categories): continue
        stage = active_consolidation.get("current_stage_key") if active_consolidation else None
        if filters.get("stage") and stage != filters["stage"]: continue
        group_id = group_by_person.get(person_id) or (active_consolidation or {}).get("front_group_id")
        if filters.get("front_group_id") and group_id != filters["front_group_id"]: continue
        cell_id = cell_by_person.get(person_id)
        if filters.get("cell_id") and cell_id != filters["cell_id"]: continue
        coordinates = address["location"]["coordinates"]
        zone = address.get("zone_key") or zone_for(coordinates[1], coordinates[0])
        if filters.get("zone") and zone != filters["zone"]: continue
        features.append({
            "type": "Feature", "geometry": {"type": "Point", "coordinates": coordinates},
            "properties": {
                "entity_kind": "person", "entity_id": person_id,
                "name": f"{person.get('nombre', '')} {person.get('apellido', '')}".strip(),
                "person_number": person.get("person_number"), "phone": phone_by_person.get(person_id),
                "address": _address_text(address), "zone": zone, "categories": sorted(categories),
                "stage": stage, "front_group_id": group_id, "cell_id": cell_id,
                "verification_status": address.get("verification_status"), "created_at": _iso(person.get("created_at")),
            },
        })
    return features


async def cell_features(db, current_user: dict, filters: dict) -> list[dict]:
    scope = await cellular_scope(db, current_user)
    query = {"location.type": "Point", "coordinates_stale": {"$ne": True}, "verification_status": {"$in": ["verified", "manual_verified"]}, "status": {"$ne": "closed"}}
    if not scope["global"]: query["cell_id"] = {"$in": scope["cell_ids"]}
    if filters.get("cell_id"): query["cell_id"] = filters["cell_id"]
    cells = await db.cells.find(query, {"_id": 0}).to_list(10000)
    cell_ids = [item["cell_id"] for item in cells]
    roles = await db.cell_role_assignments.find({"cell_id": {"$in": cell_ids}, "active": True, "role": "cell_leader"}, {"_id": 0}).to_list(10000)
    person_ids = [item["person_id"] for item in roles if ObjectId.is_valid(item.get("person_id", ""))]
    people = await db.persons.find({"_id": {"$in": [ObjectId(item) for item in person_ids]}}, {"_id": 1, "nombre": 1, "apellido": 1}).to_list(10000)
    names = {str(item["_id"]): f"{item.get('nombre', '')} {item.get('apellido', '')}".strip() for item in people}
    leaders = {item["cell_id"]: names.get(item["person_id"]) for item in roles}
    membership_counts = Counter(await db.cell_memberships.distinct("cell_id", {"cell_id": {"$in": cell_ids}, "active": True}))
    for cell_id in cell_ids:
        membership_counts[cell_id] = await db.cell_memberships.count_documents({"cell_id": cell_id, "active": True})
    features = []
    for cell in cells:
        coordinates = cell["location"]["coordinates"]
        zone = cell.get("zone_key") or zone_for(coordinates[1], coordinates[0])
        if filters.get("zone") and zone != filters["zone"]: continue
        features.append({
            "type": "Feature", "geometry": {"type": "Point", "coordinates": coordinates},
            "properties": {
                "entity_kind": "cell", "entity_id": cell["cell_id"], "name": cell["name"],
                "code": cell.get("code"), "address": cell.get("address"), "zone": zone,
                "leader": leaders.get(cell["cell_id"]), "meeting_day": cell.get("meeting_day"),
                "meeting_time": cell.get("meeting_time"), "capacity": cell.get("capacity"),
                "members": membership_counts[cell["cell_id"]], "status": cell.get("status"),
            },
        })
    return features


def aggregate_features(features: list[dict], minimum: int = 3) -> list[dict]:
    buckets = defaultdict(list)
    for feature in features:
        lng, lat = feature["geometry"]["coordinates"]
        buckets[(round(lng, 2), round(lat, 2), feature["properties"].get("zone"))].append(feature)
    output = []
    for (lng, lat, zone), items in buckets.items():
        if len(items) < minimum: continue
        category_counts = Counter(category for item in items for category in item["properties"].get("categories", []))
        output.append({
            "type": "Feature", "geometry": {"type": "Point", "coordinates": [lng, lat]},
            "properties": {"count": len(items), "zone": zone, "categories": dict(category_counts), "entity_kind": items[0]["properties"].get("entity_kind")},
        })
    return output


async def enrich_coverage(db, features: list[dict]) -> list[dict]:
    cells = await db.cells.find({"location.type": "Point", "coordinates_stale": {"$ne": True}, "status": "active"}, {"_id": 0, "location": 1}).to_list(10000)
    cell_points = [item["location"]["coordinates"] for item in cells]
    for feature in features:
        lng, lat = feature["geometry"]["coordinates"]
        distances = [_haversine_miles(lat, lng, point[1], point[0]) for point in cell_points]
        nearest = round(min(distances), 1) if distances else None
        feature["properties"]["nearest_cell_miles"] = nearest
        feature["properties"]["coverage_gap"] = nearest is None or nearest > 3
    return features


async def geographic_summary(db, current_user: dict) -> dict:
    people = await person_features(db, current_user, {})
    cells = await cell_features(db, current_user, {})
    return {
        "people_total": len(people), "cells_total": len(cells),
        "zones": {zone: {"people": sum(item["properties"]["zone"] == zone for item in people), "cells": sum(item["properties"]["zone"] == zone for item in cells)} for zone in ["north", "east", "south", "west"]},
        "review_total": await db.geo_review_queue.count_documents({"status": "open"}),
        "pending_total": await db.geo_jobs.count_documents({"status": {"$in": ["pending", "processing", "retry"]}}),
    }