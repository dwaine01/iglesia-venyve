"""Consultas geográficas autorizadas y serializadores sin ObjectId."""
import math
import re
import hashlib
from collections import Counter, defaultdict
from datetime import datetime, timezone

from bson import ObjectId

from cellular_engine import cellular_scope
from geo_service import geographic_classification
from process_engine import access_person_ids
from geo_address import normalize_address_document
from front_group_tree import descendant_group_ids


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
    active_group_ids = set(await db.front_groups.distinct("front_group_id", {"status": {"$ne": "archived"}}))
    group_assignments = await db.front_group_assignments.find({"person_id": {"$in": person_ids}, "active": True, "front_group_id": {"$in": list(active_group_ids)}}, {"_id": 0}).to_list(30000)
    groups_by_person = defaultdict(set); member_groups_by_person = defaultdict(set); led_groups_by_person = defaultdict(set)
    for item in group_assignments:
        groups_by_person[item["person_id"]].add(item["front_group_id"])
        if item.get("role") == "leader": led_groups_by_person[item["person_id"]].add(item["front_group_id"])
        else: member_groups_by_person[item["person_id"]].add(item["front_group_id"])
    requested_group_ids = set(await descendant_group_ids(db, filters["front_group_id"])) if filters.get("front_group_id") else set()
    cell_memberships = await db.cell_memberships.find({"person_id": {"$in": person_ids}, "active": True, "membership_type": "primary"}, {"_id": 0}).to_list(30000)
    cell_by_person = {item["person_id"]: item["cell_id"] for item in cell_memberships}
    contacts = await db.person_contacts.find({"person_id": {"$in": person_ids}, "es_principal": True}, {"_id": 0, "person_id": 1, "valor": 1}).to_list(30000)
    household_memberships = await db.household_memberships.find({"person_id": {"$in": person_ids}}, {"_id": 0, "person_id": 1, "household_id": 1, "rol_en_hogar": 1}).to_list(30000)
    household_by_person = {item["person_id"]: item for item in household_memberships}
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
        if person_id in groups_by_person: categories.add("front_group")
        if person_id in cell_by_person: categories.add("cell")
        if requested_categories and not categories.intersection(requested_categories): continue
        stage = active_consolidation.get("current_stage_key") if active_consolidation else None
        if filters.get("stage") and stage != filters["stage"]: continue
        consolidation_group_id = (active_consolidation or {}).get("front_group_id")
        person_group_ids = set(groups_by_person.get(person_id, set()))
        if consolidation_group_id: person_group_ids.add(consolidation_group_id)
        primary_group_id = consolidation_group_id or next(iter(sorted(member_groups_by_person.get(person_id, set()))), None) or next(iter(sorted(led_groups_by_person.get(person_id, set()))), None)
        if requested_group_ids and not person_group_ids.intersection(requested_group_ids): continue
        cell_id = cell_by_person.get(person_id)
        if filters.get("cell_id") and cell_id != filters["cell_id"]: continue
        coordinates = address["location"]["coordinates"]
        classification = geographic_classification(coordinates[1], coordinates[0])
        zone = address.get("zone_key") or classification["zone_key"]
        subzone = address.get("subzone_key") or classification["subzone_key"]
        if filters.get("zone") and zone != filters["zone"]: continue
        if filters.get("subzone") and subzone != filters["subzone"]: continue
        normalized_address = normalize_address_document(address)
        household_membership = household_by_person.get(person_id, {})
        features.append({
            "type": "Feature", "geometry": {"type": "Point", "coordinates": coordinates},
            "properties": {
                "entity_kind": "person", "entity_id": person_id,
                "name": f"{person.get('nombre', '')} {person.get('apellido', '')}".strip(),
                "person_number": person.get("person_number"), "phone": phone_by_person.get(person_id),
                "address": _address_text(address), "zone": zone, "zone_number": classification["zone_number"],
                "subzone": subzone, "categories": sorted(categories),
                "stage": stage, "front_group_id": primary_group_id, "front_group_ids": sorted(person_group_ids),
                "member_front_group_ids": sorted(member_groups_by_person.get(person_id, set())),
                "led_front_group_ids": sorted(led_groups_by_person.get(person_id, set())), "cell_id": cell_id,
                "verification_status": address.get("verification_status"), "created_at": _iso(person.get("created_at")),
                "normalized_address_key": address.get("normalized_address_key") or normalized_address["normalized_address_key"],
                "normalized_unit": address.get("normalized_unit") or normalized_address["normalized_unit"],
                "household_id": household_membership.get("household_id"), "household_role": household_membership.get("rol_en_hogar"),
                "sector_id": address.get("sector_id"), "sector_name": address.get("sector_name"), "sector_order": address.get("sector_order"),
            },
        })
    return features


def _resident(feature: dict, address_inherited: bool = False) -> dict:
    item = feature["properties"]
    return {
        "person_id": item["entity_id"], "name": item.get("name"), "person_number": item.get("person_number"),
        "household_role": item.get("household_role"), "categories": item.get("categories", []),
        "stage": item.get("stage"), "address_inherited": address_inherited,
        "verification_status": item.get("verification_status"),
        "profile_path": f"/personas/{item['entity_id']}",
    }


async def household_features(db, current_user: dict, people: list[dict]) -> list[dict]:
    """Un pin por dirección normalizada, enriquecido con Household cuando es inequívoco."""
    grouped = defaultdict(list)
    for feature in people:
        item = feature["properties"]
        key = item.get("normalized_address_key") or f"person:{item['entity_id']}"
        grouped[key].append(feature)
    household_ids = sorted({item["properties"].get("household_id") for item in people if item["properties"].get("household_id")})
    memberships = await db.household_memberships.find({"household_id": {"$in": household_ids}}, {"_id": 0, "household_id": 1, "person_id": 1, "rol_en_hogar": 1}).to_list(50000) if household_ids else []
    allowed = await access_person_ids(db, current_user)
    member_ids = sorted({item["person_id"] for item in memberships if allowed is None or item["person_id"] in allowed})
    extra_people = await db.persons.find({"_id": {"$in": [ObjectId(item) for item in member_ids if ObjectId.is_valid(item)]}, "status": {"$ne": "archived"}}, {"_id": 1, "nombre": 1, "apellido": 1, "person_number": 1}).to_list(50000) if member_ids else []
    extra_by_id = {str(item["_id"]): item for item in extra_people}
    feature_by_person = {item["properties"]["entity_id"]: item for item in people}
    keys_by_household = defaultdict(set)
    for key, items in grouped.items():
        for item in items:
            household_id = item["properties"].get("household_id")
            if household_id: keys_by_household[household_id].add(key)
    memberships_by_household = defaultdict(list)
    for item in memberships: memberships_by_household[item["household_id"]].append(item)
    output = []
    for key, items in grouped.items():
        household_ids_at_address = sorted({item["properties"].get("household_id") for item in items if item["properties"].get("household_id")})
        residents = {_resident(item)["person_id"]: _resident(item) for item in items}
        for household_id in household_ids_at_address:
            if len(keys_by_household[household_id]) != 1:
                continue
            for membership in memberships_by_household[household_id]:
                if membership["person_id"] in residents or membership["person_id"] not in extra_by_id:
                    continue
                person = extra_by_id[membership["person_id"]]
                residents[membership["person_id"]] = {
                    "person_id": membership["person_id"], "name": f"{person.get('nombre', '')} {person.get('apellido', '')}".strip(),
                    "person_number": person.get("person_number"), "household_role": membership.get("rol_en_hogar"),
                    "categories": [], "stage": None, "address_inherited": True,
                    "profile_path": f"/personas/{membership['person_id']}",
                }
        first = items[0]; properties = first["properties"]
        longitude = sum(item["geometry"]["coordinates"][0] for item in items) / len(items)
        latitude = sum(item["geometry"]["coordinates"][1] for item in items) / len(items)
        entity_id = f"household:{household_ids_at_address[0]}" if len(household_ids_at_address) == 1 else f"address:{hashlib.sha256(key.encode()).hexdigest()[:20]}"
        output.append({
            "type": "Feature", "geometry": {"type": "Point", "coordinates": [longitude, latitude]},
            "properties": {
                "entity_kind": "household", "entity_id": entity_id, "name": f"Hogar · {properties.get('address') or 'Dirección verificada'}",
                "address": properties.get("address"), "resident_count": len(residents), "count": len(residents),
                "residents": sorted(residents.values(), key=lambda item: (item.get("name") or "")), "household_ids": household_ids_at_address,
                "verified_person_ids": sorted(item["person_id"] for item in residents.values() if item.get("verification_status") == "manual_verified"),
                "normalized_address_key": key if not key.startswith("person:") else None,
                "zone": properties.get("zone"), "zone_number": properties.get("zone_number"), "subzone": properties.get("subzone"),
                "sector_id": properties.get("sector_id"), "sector_name": properties.get("sector_name"), "sector_order": properties.get("sector_order"),
                "categories": sorted({category for item in items for category in item["properties"].get("categories", [])}),
            },
        })
    return output


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
        classification = geographic_classification(coordinates[1], coordinates[0])
        zone = cell.get("zone_key") or classification["zone_key"]
        subzone = cell.get("subzone_key") or classification["subzone_key"]
        if filters.get("zone") and zone != filters["zone"]: continue
        if filters.get("subzone") and subzone != filters["subzone"]: continue
        features.append({
            "type": "Feature", "geometry": {"type": "Point", "coordinates": coordinates},
            "properties": {
                "entity_kind": "cell", "entity_id": cell["cell_id"], "name": cell["name"],
                "code": cell.get("code"), "address": cell.get("address"), "zone": zone,
                "zone_number": classification["zone_number"], "subzone": subzone,
                "leader": leaders.get(cell["cell_id"]), "meeting_day": cell.get("meeting_day"),
                "meeting_time": cell.get("meeting_time"), "capacity": cell.get("capacity"),
                "members": membership_counts[cell["cell_id"]], "status": cell.get("status"),
            },
        })
    return features


async def front_group_centroid_features(db, current_user: dict, filters: dict) -> list[dict]:
    source_filters = {"front_group_id": filters.get("front_group_id"), "zone": filters.get("zone"), "subzone": filters.get("subzone")}
    people = await person_features(db, current_user, source_filters)
    grouped = defaultdict(list)
    for feature in people:
        group_id = feature["properties"].get("front_group_id")
        if group_id: grouped[group_id].append(feature)
    group_ids = list(grouped)
    groups = await db.front_groups.find({"front_group_id": {"$in": group_ids}, "status": "active"}, {"_id": 0, "front_group_id": 1, "name": 1, "linked_structures": 1, "converted_cell_id": 1}).to_list(10000)
    output = []
    for group in groups:
        converted = group.get("converted_cell_id") or any(item.get("type") == "cell" for item in group.get("linked_structures", []))
        if converted: continue
        points = grouped[group["front_group_id"]]
        longitude = sum(item["geometry"]["coordinates"][0] for item in points) / len(points)
        latitude = sum(item["geometry"]["coordinates"][1] for item in points) / len(points)
        classification = geographic_classification(latitude, longitude)
        output.append({
            "type": "Feature", "geometry": {"type": "Point", "coordinates": [longitude, latitude]},
            "properties": {
                "entity_kind": "front_group", "entity_id": group["front_group_id"], "name": group["name"],
                "members": len(points), "zone": classification["zone_key"], "zone_number": classification["zone_number"],
                "subzone": classification["subzone_key"], "centroid": True,
            },
        })
    return output


async def search_person_locations(db, current_user: dict, search: str, limit: int = 10) -> list[dict]:
    allowed = await access_person_ids(db, current_user)
    normalized = re.escape(" ".join(search.lower().split()))
    escaped = re.escape(search)
    query = {"status": {"$ne": "archived"}, "$or": [
        {"search_key": {"$regex": normalized}},
        {"nombre": {"$regex": escaped, "$options": "i"}},
        {"apellido": {"$regex": escaped, "$options": "i"}},
        {"person_number": {"$regex": escaped, "$options": "i"}},
    ]}
    if allowed is not None:
        query["_id"] = {"$in": [ObjectId(item) for item in allowed if ObjectId.is_valid(item)]}
    people = await db.persons.find(query, {"_id": 1, "person_number": 1, "nombre": 1, "apellido": 1}).sort([("nombre", 1), ("apellido", 1)]).limit(limit * 3).to_list(limit * 3)
    person_ids = [str(item["_id"]) for item in people]
    addresses = await db.person_addresses.find({"person_id": {"$in": person_ids}, "location.type": "Point", "coordinates_stale": {"$ne": True}, "verification_status": {"$in": ["verified", "manual_verified"]}}, {"_id": 0, "person_id": 1, "location": 1, "zone_key": 1, "subzone_key": 1}).sort("es_principal", -1).to_list(limit * 5)
    by_person = {}
    for item in addresses: by_person.setdefault(item["person_id"], item)
    output = []
    for person in people:
        person_id = str(person["_id"]); address = by_person.get(person_id)
        if not address: continue
        longitude, latitude = address["location"]["coordinates"]; classification = geographic_classification(latitude, longitude)
        output.append({
            "person_id": person_id, "person_number": person.get("person_number"),
            "name": f"{person.get('nombre', '')} {person.get('apellido', '')}".strip(),
            "latitude": latitude, "longitude": longitude,
            "zone": address.get("zone_key") or classification["zone_key"],
            "zone_number": classification["zone_number"],
            "subzone": address.get("subzone_key") or classification["subzone_key"],
        })
        if len(output) >= limit: break
    return output


async def unlocated_person_items(db, current_user: dict) -> list[dict]:
    """Personas sin una ubicación propia o familiar inequívoca, respetando scope."""
    allowed = await access_person_ids(db, current_user)
    query = {"status": {"$ne": "archived"}, "is_archived": {"$ne": True}}
    if allowed is not None:
        query["_id"] = {"$in": [ObjectId(item) for item in allowed if ObjectId.is_valid(item)]}
    people = await db.persons.find(query, {"_id": 1, "person_number": 1, "nombre": 1, "apellido": 1}).sort([("nombre", 1), ("apellido", 1)]).to_list(50000)
    person_ids = [str(item["_id"]) for item in people]
    addresses = await db.person_addresses.find({"person_id": {"$in": person_ids}}, {"_id": 0}).sort([("es_principal", -1), ("updated_at", -1)]).to_list(100000)
    memberships = await db.household_memberships.find({"person_id": {"$in": person_ids}}, {"_id": 0, "person_id": 1, "household_id": 1}).to_list(50000)
    household_ids = sorted({item["household_id"] for item in memberships})
    all_household_members = await db.household_memberships.find({"household_id": {"$in": household_ids}}, {"_id": 0, "person_id": 1, "household_id": 1}).to_list(100000) if household_ids else []
    household_person_ids = sorted({item["person_id"] for item in all_household_members})
    household_addresses = await db.person_addresses.find({"person_id": {"$in": household_person_ids}}, {"_id": 0}).sort([("es_principal", -1), ("updated_at", -1)]).to_list(100000) if household_person_ids else []
    addresses_by_person = defaultdict(list)
    for item in addresses + household_addresses:
        if item not in addresses_by_person[item["person_id"]]: addresses_by_person[item["person_id"]].append(item)
    household_by_person = {item["person_id"]: item["household_id"] for item in memberships}
    members_by_household = defaultdict(list)
    for item in all_household_members: members_by_household[item["household_id"]].append(item["person_id"])

    def usable(item):
        return (item.get("location") or {}).get("type") == "Point" and item.get("coordinates_stale") is not True and item.get("verification_status") in {"verified", "manual_verified"}

    output = []
    for person in people:
        person_id = str(person["_id"]); own = addresses_by_person.get(person_id, [])
        if any(usable(item) for item in own): continue
        household_id = household_by_person.get(person_id)
        household_usable = [item for member_id in members_by_household.get(household_id, []) for item in addresses_by_person.get(member_id, []) if usable(item)]
        household_keys = {normalize_address_document(item).get("normalized_address_key") for item in household_usable}
        household_keys.discard(None)
        if len(household_keys) == 1: continue
        if not own and not household_id: reason = "no_address_or_household"
        elif not own and household_id and not household_usable: reason = "household_without_location"
        elif not own and len(household_keys) > 1: reason = "household_address_conflict"
        else:
            primary = own[0]
            if not normalize_address_document(primary)["address_complete"]: reason = "incomplete_address"
            elif primary.get("verification_status") == "needs_verification": reason = "verification_required"
            elif primary.get("geocoding_status") in {"not_found", "provider_error", "ambiguous"}: reason = "geocoding_failed"
            else: reason = "geocoding_pending"
        output.append({
            "person_id": person_id, "person_number": person.get("person_number"),
            "name": f"{person.get('nombre', '')} {person.get('apellido', '')}".strip(),
            "reason": reason, "has_address": bool(own), "has_household": bool(household_id),
            "profile_path": f"/personas/{person_id}",
        })
    return output


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
    groups = await front_group_centroid_features(db, current_user, {})
    return {
        "people_total": len(people), "cells_total": len(cells), "front_groups_total": len(groups),
        "zones": {zone: {"people": sum(item["properties"]["zone"] == zone for item in people), "cells": sum(item["properties"]["zone"] == zone for item in cells)} for zone in ["north", "east", "south", "west"]},
        "review_total": await db.geo_review_queue.count_documents({"status": "open"}),
        "pending_total": await db.geo_jobs.count_documents({"status": {"$in": ["pending", "processing", "retry"]}}),
    }