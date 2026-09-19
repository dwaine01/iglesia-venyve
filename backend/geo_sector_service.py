"""Geometría, asignación point-in-polygon e índices de sectores territoriales."""
from datetime import datetime, timezone


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _cross(a, b, c) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _on_segment(a, b, point) -> bool:
    return abs(_cross(a, b, point)) < 1e-10 and min(a[0], b[0]) <= point[0] <= max(a[0], b[0]) and min(a[1], b[1]) <= point[1] <= max(a[1], b[1])


def _segments_intersect(a, b, c, d) -> bool:
    values = (_cross(a, b, c), _cross(a, b, d), _cross(c, d, a), _cross(c, d, b))
    if values[0] * values[1] < 0 and values[2] * values[3] < 0:
        return True
    return any((abs(values[index]) < 1e-10 and _on_segment(*pair)) for index, pair in enumerate(((a, b, c), (a, b, d), (c, d, a), (c, d, b))))


def validate_polygon(geometry: dict) -> dict:
    if not isinstance(geometry, dict) or geometry.get("type") != "Polygon":
        raise ValueError("La geometría debe ser un polígono GeoJSON")
    coordinates = geometry.get("coordinates")
    if not isinstance(coordinates, list) or len(coordinates) != 1 or not isinstance(coordinates[0], list):
        raise ValueError("El sector debe contener un único límite exterior")
    ring = coordinates[0]
    if len(ring) < 4:
        raise ValueError("El polígono requiere al menos tres vértices")
    normalized = []
    for point in ring:
        if not isinstance(point, list) or len(point) != 2:
            raise ValueError("Cada vértice debe contener longitud y latitud")
        longitude, latitude = float(point[0]), float(point[1])
        if not -180 <= longitude <= 180 or not -90 <= latitude <= 90:
            raise ValueError("Un vértice está fuera del rango geográfico")
        normalized.append([round(longitude, 7), round(latitude, 7)])
    if normalized[0] != normalized[-1]:
        raise ValueError("El polígono GeoJSON debe estar cerrado")
    if len({tuple(item) for item in normalized[:-1]}) < 3:
        raise ValueError("El polígono requiere tres vértices distintos")
    area = abs(sum(normalized[index][0] * normalized[index + 1][1] - normalized[index + 1][0] * normalized[index][1] for index in range(len(normalized) - 1))) / 2
    if area < 1e-10:
        raise ValueError("El polígono no tiene un área válida")
    segments = [(normalized[index], normalized[index + 1]) for index in range(len(normalized) - 1)]
    for first, (a, b) in enumerate(segments):
        for second, (c, d) in enumerate(segments):
            if second <= first + 1 or (first == 0 and second == len(segments) - 1):
                continue
            if _segments_intersect(a, b, c, d):
                raise ValueError("El polígono se cruza consigo mismo")
    return {"type": "Polygon", "coordinates": [normalized]}


def point_in_polygon(longitude: float, latitude: float, geometry: dict) -> bool:
    ring = (geometry or {}).get("coordinates", [[]])[0]
    if len(ring) < 4:
        return False
    point = [longitude, latitude]
    inside = False
    previous = ring[-1]
    for current in ring:
        if _on_segment(previous, current, point):
            return True
        crosses = (current[1] > latitude) != (previous[1] > latitude)
        if crosses:
            intersect_x = (previous[0] - current[0]) * (latitude - current[1]) / (previous[1] - current[1]) + current[0]
            if longitude < intersect_x:
                inside = not inside
        previous = current
    return inside


async def sector_assignment_fields(db, latitude: float, longitude: float, zone_id: str | None = None) -> dict:
    query = {
        "status": "active",
        "geometry": {"$geoIntersects": {"$geometry": {"type": "Point", "coordinates": [longitude, latitude]}}},
    }
    if zone_id:
        query["zone_id"] = zone_id
    sectors = await db.geo_sectors.find(query, {"_id": 0, "sector_id": 1, "name": 1, "zone_id": 1, "order": 1}).sort([("order", 1), ("sector_id", 1)]).to_list(100)
    if not sectors:
        return {"sector_id": None, "sector_name": None, "sector_order": None, "sector_conflict_ids": []}
    selected = sectors[0]
    return {
        "sector_id": selected["sector_id"], "sector_name": selected["name"], "sector_order": selected["order"],
        "sector_conflict_ids": [item["sector_id"] for item in sectors[1:]], "sector_assigned_at": now_utc(),
    }


async def reassign_sector_memberships(db) -> dict:
    updated = {"person_addresses": 0, "cells": 0}
    for collection_name in updated:
        query = {"location.type": "Point", "coordinates_stale": {"$ne": True}}
        docs = await db[collection_name].find(query, {"_id": 1, "location": 1, "zone_key": 1}).to_list(50000)
        for doc in docs:
            longitude, latitude = doc["location"]["coordinates"]
            fields = await sector_assignment_fields(db, latitude, longitude, doc.get("zone_key"))
            await db[collection_name].update_one({"_id": doc["_id"]}, {"$set": fields})
            updated[collection_name] += 1
    return updated


async def ensure_sector_indexes(db) -> None:
    await db.geo_sectors.create_index("sector_id", unique=True)
    await db.geo_sectors.create_index([("zone_id", 1), ("order", 1)], unique=True)
    await db.geo_sectors.create_index([("geometry", "2dsphere")], sparse=True)
    await db.geo_sectors.create_index([("status", 1), ("zone_id", 1), ("order", 1)])
    await db.person_addresses.create_index("normalized_address_key", sparse=True)
    await db.person_addresses.create_index("sector_id", sparse=True)
    await db.cells.create_index("sector_id", sparse=True)