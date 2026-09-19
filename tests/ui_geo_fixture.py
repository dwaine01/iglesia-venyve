"""Fixture visual efímero para Mapa 360; ejecutar cleanup al terminar."""
import asyncio
import json
import sys
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
from bson import ObjectId

sys.path.insert(0, "/app/backend")
import server  # noqa: E402
from access_control import access_defaults_for_role  # noqa: E402
from geo_service import zone_for  # noqa: E402
from geo_address import normalize_address_document  # noqa: E402


EMAIL = "qa.geo.ui@example.com"
PASSWORD = "GeoUI2026!"


async def cleanup():
    users = await server.db.users.find({"email": EMAIL}, {"_id": 1}).to_list(10)
    user_ids = [str(item["_id"]) for item in users]
    people = await server.db.persons.find({"person_number": {"$regex": "^VV-QM"}}, {"_id": 1}).to_list(100)
    person_ids = [str(item["_id"]) for item in people]
    addresses = await server.db.person_addresses.find({"person_id": {"$in": person_ids}}, {"_id": 1}).to_list(100)
    address_ids = [str(item["_id"]) for item in addresses]
    await server.db.geo_jobs.delete_many({"$or": [{"entity_id": {"$in": address_ids}}, {"entity_id": {"$regex": "^qa-geo-cell"}}]})
    await server.db.geo_review_queue.delete_many({"$or": [{"entity_id": {"$in": address_ids}}, {"entity_id": {"$regex": "^qa-geo-cell"}}]})
    await server.db.geo_location_history.delete_many({"$or": [{"entity_id": {"$in": address_ids}}, {"entity_id": {"$regex": "^qa-geo-cell"}}]})
    await server.db.geo_audit_log.delete_many({"actor_user_id": {"$in": user_ids}})
    qa_sectors = await server.db.geo_sectors.find({"created_by": {"$in": user_ids}}, {"_id": 0, "zone_id": 1}).to_list(100)
    await server.db.geo_sectors.delete_many({"created_by": {"$in": user_ids}})
    for zone_id in {item["zone_id"] for item in qa_sectors}:
        latest = await server.db.geo_sectors.find_one({"zone_id": zone_id}, {"_id": 0, "order": 1}, sort=[("order", -1)])
        if latest: await server.db.geo_sector_counters.update_one({"_id": zone_id}, {"$set": {"sequence": latest["order"]}}, upsert=True)
        else: await server.db.geo_sector_counters.delete_one({"_id": zone_id})
    for collection in ["person_addresses", "person_contacts", "person_memberships", "process_enrollments", "front_group_assignments", "cell_memberships", "cell_role_assignments"]:
        await server.db[collection].delete_many({"person_id": {"$in": person_ids}})
    memberships = await server.db.household_memberships.find({"person_id": {"$in": person_ids}}, {"_id": 0, "household_id": 1}).to_list(100)
    household_ids = list({item["household_id"] for item in memberships})
    await server.db.household_memberships.delete_many({"person_id": {"$in": person_ids}})
    await server.db.households.delete_many({"_id": {"$in": household_ids}})
    await server.db.cells.delete_many({"cell_id": {"$regex": "^qa-geo-cell"}})
    await server.db.front_groups.delete_many({"front_group_id": {"$regex": "^qa-geo-group"}})
    await server.db.persons.delete_many({"_id": {"$in": [item["_id"] for item in people]}})
    await server.db.users.delete_many({"email": EMAIL})
    return {"people": len(person_ids), "addresses": len(address_ids)}


def geo_fields(lat, lng):
    return {
        "location": {"type": "Point", "coordinates": [lng, lat]}, "latitude": lat, "longitude": lng,
        "zone_key": zone_for(lat, lng), "geocoding_provider": "census", "geocoding_source": "automatic",
        "geocoding_status": "geocoded", "verification_status": "verified", "coordinates_stale": False,
        "geocoding_accuracy": "address_range_interpolated", "geocoding_confidence": "high", "address_version": 1,
        "geocoded_at": datetime.now(timezone.utc), "manual_override": False,
    }


async def setup():
    await cleanup(); now = datetime.now(timezone.utc)
    defaults = access_defaults_for_role("pastor")
    user_id = ObjectId()
    await server.db.users.insert_one({"_id": user_id, "nombre": "QA Pastor Mapa", "email": EMAIL, "password": bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt()).decode(), "rol": "pastor", "is_active": True, "token_version": 1, "created_at": now, **defaults})
    group_id = "qa-geo-group-central"
    await server.db.front_groups.insert_one({"_id": group_id, "front_group_id": group_id, "name": "Grupo Frontal QA Oeste", "status": "active", "created_at": now})
    locations = [
        ("Ana Norte", 40.025, -83.08, 15), ("Luis Este", 39.96, -82.98, 40),
        ("Marta Sur", 39.86, -83.08, 70), ("Carlos Oeste", 39.95, -83.19, 110),
        ("Elena Central", 40.025, -83.08, 8),
    ]
    person_ids = []; address_ids = []
    for index, (name, lat, lng, days) in enumerate(locations):
        first, last = name.split(" ", 1); person_id = ObjectId(); person_ids.append(str(person_id))
        await server.db.persons.insert_one({"_id": person_id, "person_number": f"VV-QM{index + 1:04d}", "nombre": first, "apellido": last, "search_key": name.lower(), "idempotency_key": f"qa:geo:{uuid.uuid4()}", "status": "active", "created_at": now - timedelta(days=days), "updated_at": now})
        address_fields = {"linea1": "640 Demorest Rd" if index in {0, 4} else f"{640 + index * 10} Demorest Rd", "ciudad": "Columbus", "provincia": "OH", "codigo_postal": "43204", "pais": "Estados Unidos"}
        address = await server.db.person_addresses.insert_one({"person_id": str(person_id), "tipo": "casa", **address_fields, **normalize_address_document(address_fields), "es_principal": True, "created_at": now, "updated_at": now, **geo_fields(lat, lng)})
        address_ids.append(str(address.inserted_id))
        await server.db.person_memberships.insert_one({"membership_id": str(uuid.uuid4()), "member_number": f"MBR-QG{index + 1:04d}", "person_id": str(person_id), "status": "active", "created_at": now})
        await server.db.front_group_assignments.insert_one({"assignment_id": str(uuid.uuid4()), "front_group_id": group_id, "person_id": str(person_id), "active": True, "created_at": now})
    household_id = f"qa-household-{uuid.uuid4()}"
    await server.db.households.insert_one({"_id": household_id, "nombre_hogar": "Hogar Norte QA", "created_at": now, "updated_at": now})
    await server.db.household_memberships.insert_many([
        {"_id": str(uuid.uuid4()), "household_id": household_id, "person_id": person_ids[0], "rol_en_hogar": "Responsable", "created_at": now},
        {"_id": str(uuid.uuid4()), "household_id": household_id, "person_id": person_ids[4], "rol_en_hogar": "Integrante", "created_at": now},
    ])
    search_id = ObjectId(); person_ids.append(str(search_id))
    await server.db.persons.insert_one({"_id": search_id, "person_number": "VV-QM9999", "nombre": "Josué", "apellido": "Rivera", "search_key": "josue rivera", "idempotency_key": f"qa:geo:{uuid.uuid4()}", "status": "active", "created_at": now, "updated_at": now})
    await server.db.person_contacts.insert_one({"person_id": str(search_id), "tipo": "telefono", "valor": "6145553600", "es_principal": True, "created_at": now, "updated_at": now})
    review_address = ObjectId()
    await server.db.person_addresses.insert_one({"_id": review_address, "person_id": str(search_id), "tipo": "casa", "linea1": "Dirección incompleta QA", "ciudad": "Columbus", "provincia": "OH", "pais": "Estados Unidos", "es_principal": True, "address_version": 1, "geocoding_status": "not_found", "verification_status": "needs_verification", "coordinates_stale": True, "created_at": now, "updated_at": now})
    review_id = f"review:person_address:{review_address}:1"
    await server.db.geo_review_queue.insert_one({"_id": review_id, "review_id": review_id, "entity_type": "person_address", "entity_id": str(review_address), "person_id": str(search_id), "address_version": 1, "reason": "not_found", "status": "open", "created_at": now, "updated_at": now})
    cells = [("qa-geo-cell-west", "Célula Vida Oeste", 39.95, -83.16, person_ids[3]), ("qa-geo-cell-east", "Célula Esperanza Este", 39.965, -83.01, person_ids[1])]
    for idx, (cell_id, name, lat, lng, leader_id) in enumerate(cells):
        await server.db.cells.insert_one({"_id": cell_id, "cell_id": cell_id, "code": f"QA-C{idx + 1}", "name": name, "network_id": "qa-network", "address": f"{700 + idx * 100} Broad St, Columbus, OH 43204", "meeting_day": "Miércoles", "meeting_time": "19:00", "capacity": 18, "status": "active", "opened_at": now.isoformat(), "created_at": now, "updated_at": now, **geo_fields(lat, lng)})
        await server.db.cell_role_assignments.insert_one({"assignment_id": str(uuid.uuid4()), "cell_id": cell_id, "person_id": leader_id, "role": "cell_leader", "active": True, "created_at": now})
        for person_id in (person_ids[:3] if idx == 0 else person_ids[3:5]):
            await server.db.cell_memberships.insert_one({"membership_id": str(uuid.uuid4()), "cell_id": cell_id, "person_id": person_id, "membership_type": "primary", "active": True, "created_at": now})
    print(json.dumps({"email": EMAIL, "password": PASSWORD, "search_person": str(search_id), "live_address_id": address_ids[0], "live_person_id": person_ids[0], "review_id": review_id}))


if __name__ == "__main__":
    asyncio.run(setup() if len(sys.argv) > 1 and sys.argv[1] == "setup" else cleanup())