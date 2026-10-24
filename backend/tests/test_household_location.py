"""Ubicación de las casas de una invasión: permisos entre dos mentores (en el
backend), casas con y sin coordenadas, duplicados a <25 m y geocodificación
en segundo plano con el proveedor existente (sin bloquear el registro)."""
import asyncio
import uuid
from datetime import date, timedelta

import pytest

from tests.test_pastoral_front_group_5c import Fixture, server  # noqa: I001 (primero: carga el servidor)
import geo_provider  # noqa: E402
import household_location  # noqa: E402

BASE_LAT, BASE_LNG = 39.941105, -83.089529


class FakeProvider:
    def __init__(self):
        self.calls = []

    async def geocode(self, address):
        self.calls.append(address)
        if "No Existe" in address.get("street", ""):
            return geo_provider.GeocodeResult(status="not_found", provider="census")
        return geo_provider.GeocodeResult(status="matched", latitude=BASE_LAT + 0.01, longitude=BASE_LNG, provider="census")


async def wait_for(predicate, timeout=5):
    for _ in range(int(timeout / 0.05)):
        if await predicate():
            return True
        await asyncio.sleep(0.05)
    return False


@pytest.mark.asyncio
async def test_two_mentors_map_permissions_coordinates_duplicates_and_geocoding(monkeypatch):
    fake = FakeProvider()
    geo_provider.set_geocoding_provider_for_tests(fake)
    monkeypatch.setattr(household_location, "geocoding_is_configured", lambda: True)
    fx = Fixture()
    tag = uuid.uuid4().hex[:8]
    campaign_id = None
    try:
        pastora = await fx.account(await fx.person(f"Pastora{tag}"), "pastora")
        ana_id, beto_id, lead_id = [await fx.person(f"{name}{tag}") for name in ("Ana", "Beto", "Encargado")]
        ana = await fx.account(ana_id, "persona")
        beto = await fx.account(beto_id, "persona")
        lead = await fx.account(lead_id, "persona")
        outsider = await fx.account(await fx.person(f"Ajeno{tag}"), "persona")
        for person_id in (ana_id, beto_id):
            await server.db.mentor_badges.insert_one({"_id": f"badge-{tag}-{person_id}", "person_id": person_id, "active": True})
        start = date.today() + timedelta(days=3)
        created = await pastora.post("/api/invasions", json={
            "name": f"Invasión {tag}", "location": "Lincoln Park", "start_date": start.isoformat(), "end_date": start.isoformat(),
            "general_lead_person_id": lead_id, "mentor_person_ids": [ana_id, beto_id],
        })
        assert created.status_code == 201, created.text
        campaign_id = created.json()["campaign_id"]

        # Casa de Ana con GPS (precisión guardada) y casa de Beto con GPS.
        ana_house = await ana.post("/api/mentorship/outreach/households", json={
            "campaign_id": campaign_id, "address_line1": "100 Main St", "latitude": BASE_LAT, "longitude": BASE_LNG,
            "location_accuracy_m": 8, "location_source": "gps", "location_reference": "Casa azul junto a la bodega",
        })
        assert ana_house.status_code == 201, ana_house.text
        ana_house = ana_house.json()
        assert ana_house["location_source"] == "gps" and ana_house["location_accuracy_m"] == 8 and ana_house["location_reference"] == "Casa azul junto a la bodega"
        beto_house = (await beto.post("/api/mentorship/outreach/households", json={
            "campaign_id": campaign_id, "address_line1": "500 Oak Ave", "latitude": BASE_LAT + 0.004, "longitude": BASE_LNG + 0.004, "location_source": "gps",
        })).json()
        # Casas importadas solo con dirección (disponibles): se geocodifican en segundo plano.
        imported = await pastora.post(f"/api/mentorship/outreach/campaigns/{campaign_id}/households/import", json={"entries": [
            {"address_line1": "200 Elm St"}, {"address_line1": "1 Calle No Existe"},
        ]})
        assert imported.status_code == 201 and imported.json()["created"] == 2

        async def geocoded():
            docs = await server.db.outreach_households.find({"campaign_id": campaign_id, "mentor_person_id": None}, {"geocoding_status": 1}).to_list(10)
            return all(doc.get("geocoding_status") not in (None, "pending") for doc in docs)
        assert await wait_for(geocoded)
        assert {call["street"] for call in fake.calls} == {"200 Elm St", "1 Calle No Existe"}
        assert all(call["city"] == "Columbus" and call["state"] == "OH" for call in fake.calls)  # ciudad de la iglesia por defecto

        # Mentor Ana: solo SUS casas y las disponibles (filtrado en el backend).
        ana_map = (await ana.get(f"/api/mentorship/outreach/campaigns/{campaign_id}/households/map")).json()
        ids = {item["household_id"] for item in ana_map["points"] + ana_map["unlocated"]}
        assert ana_map["scope"] == "mine" and ana_house["household_id"] in ids and beto_house["household_id"] not in ids
        located = {item["address_line1"]: item for item in ana_map["points"]}
        assert located["100 Main St"]["category"] == "mine" and located["100 Main St"]["latitude"] == BASE_LAT and located["100 Main St"]["approximate"] is False
        assert located["200 Elm St"]["category"] == "available" and located["200 Elm St"]["location_source"] == "geocoded"
        assert [item["address_line1"] for item in ana_map["unlocated"]] == ["1 Calle No Existe"] and ana_map["unlocated"][0]["geocoding_status"] == "not_found"
        # Ana no puede ubicar ni ver la casa de Beto; un ajeno no ve el mapa.
        assert (await ana.put(f"/api/mentorship/outreach/households/{beto_house['household_id']}/location", json={"latitude": 1, "longitude": 1})).status_code == 403
        assert (await outsider.get(f"/api/mentorship/outreach/campaigns/{campaign_id}/households/map")).status_code == 403

        # Encargado general: ve todas; sin geo.view_precise las casas ajenas salen aproximadas.
        lead_map = (await lead.get(f"/api/mentorship/outreach/campaigns/{campaign_id}/households/map")).json()
        assert lead_map["scope"] == "all" and lead_map["counts"]["total"] == 4 and lead_map["precise"] is False
        beto_point = next(item for item in lead_map["points"] if item["household_id"] == beto_house["household_id"])
        assert beto_point["approximate"] is True and beto_point["latitude"] == round(BASE_LAT + 0.004, 3)
        # La pastora (ubicación exacta) ve coordenadas exactas.
        pastora_map = (await pastora.get(f"/api/mentorship/outreach/campaigns/{campaign_id}/households/map")).json()
        assert next(item for item in pastora_map["points"] if item["household_id"] == beto_house["household_id"])["approximate"] is False

        # Duplicados: misma dirección o a menos de 25 m; lo ajeno solo se cuenta.
        near = await ana.post("/api/mentorship/outreach/households/duplicates-check", json={"campaign_id": campaign_id, "latitude": BASE_LAT + 0.0001, "longitude": BASE_LNG})
        assert [item["household_id"] for item in near.json()["items"]] == [ana_house["household_id"]] and near.json()["items"][0]["distance_m"] < 25
        same = await ana.post("/api/mentorship/outreach/households/duplicates-check", json={"campaign_id": campaign_id, "address_line1": "500 OAK  ave"})
        assert same.json()["items"] == [] and same.json()["hidden"] == 1
        far = await ana.post("/api/mentorship/outreach/households/duplicates-check", json={"campaign_id": campaign_id, "latitude": BASE_LAT + 0.01, "longitude": BASE_LNG + 0.01})
        assert far.json()["items"] == [] and far.json()["hidden"] == 0

        # Tomar una casa disponible sin coordenadas y ubicarla con "mi ubicación".
        unlocated_id = ana_map["unlocated"][0]["household_id"]
        assert (await ana.post(f"/api/mentorship/outreach/households/{unlocated_id}/claim")).status_code == 200
        placed = await ana.put(f"/api/mentorship/outreach/households/{unlocated_id}/location", json={"latitude": BASE_LAT + 0.02, "longitude": BASE_LNG, "accuracy_m": 150, "source": "gps"})
        assert placed.status_code == 200 and placed.json()["low_accuracy"] is True
        assert placed.json()["household"]["location_source"] == "gps" and placed.json()["household"]["geocoding_status"] is None
        # Casa antigua sin campos de ubicación sigue apareciendo (sin ubicar) y se puede editar.
        legacy_id = f"legacy-{tag}"
        await server.db.outreach_households.insert_one({"_id": legacy_id, "household_id": legacy_id, "campaign_id": campaign_id, "mentor_person_id": ana_id, "status": "assigned", "address_line1": None, "sector": "Sector viejo", "archived": False})
        legacy_map = (await ana.get(f"/api/mentorship/outreach/campaigns/{campaign_id}/households/map")).json()
        assert any(item["household_id"] == legacy_id for item in legacy_map["unlocated"])
        assert (await ana.put(f"/api/mentorship/outreach/households/{legacy_id}/location", json={"reference": "Frente al parque"})).json()["household"]["location_reference"] == "Frente al parque"
        # Visitada: con un intento registrado cambia de color.
        await ana.post(f"/api/mentorship/outreach/households/{ana_house['household_id']}/events", json={"result": "no_answer"})
        visited = (await ana.get(f"/api/mentorship/outreach/campaigns/{campaign_id}/households/map")).json()
        assert next(item for item in visited["points"] if item["household_id"] == ana_house["household_id"])["category"] == "visited"
    finally:
        geo_provider.set_geocoding_provider_for_tests(None)
        if campaign_id:
            for collection in ("outreach_households", "outreach_visit_events", "outreach_visits", "outreach_participations", "invasion_participants", "outreach_campaigns"):
                await server.db[collection].delete_many({"campaign_id": campaign_id})
        await server.db.mentor_badges.delete_many({"_id": {"$regex": f"^badge-{tag}"}})
        await server.db.portal_notifications.delete_many({"recipient_user_id": {"$in": [str(item) for item in fx.user_ids]}})
        await fx.cleanup()
