"""Visitantes: formulario en español o inglés (idioma preferido para el seguimiento),
sexo para asignar el seguimiento (nunca en pantallas públicas), «¿Eres nuevo en esta
área?» y cumpleaños SIN año (día y mes) que no rompe la edad en Persona 360."""
import uuid

import pytest
from bson import ObjectId
from httpx import ASGITransport, AsyncClient

from tests.test_pastoral_front_group_5c import Fixture, server  # noqa: I001 — server primero
from tests.test_visitor_registry import cleanup, link, tablet, visitor

db = server.db


@pytest.mark.asyncio
async def test_language_sex_new_in_area_and_birthday_without_year():
    fx = Fixture()
    tag = uuid.uuid4().hex[:6]
    clients = []
    before_settings = await db.app_settings.find_one({"_id": "visitor_kiosk_settings"})
    before_texts = await db.app_settings.find_one({"_id": "visitor_texts"})
    try:
        pastora = await fx.account(await fx.person(f"Pastora{tag}"), "pastora")
        await pastora.put("/api/visitors/welcome/state", json={"today": True, "service_kind": "all"})
        pad = await tablet(pastora)
        tv = AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test", headers={"X-Link-Token": await link(pastora, "screen")})
        clients += [pad, tv]

        # La tableta recibe los textos en los dos idiomas; el año de nacimiento no se pide por defecto.
        config = (await pad.get("/api/kiosk/config")).json()
        assert config["ask_birth_year"] is False and config["texts_en"]["welcome"].startswith("Welcome") and config["texts"]["welcome"].startswith("¡Bienvenido")
        assert set(config["texts_en"]) == {"welcome", "privacy", "confirmation", "privacy_version"}

        # Registro en inglés: sexo, nuevo en el área y cumpleaños sin año.
        form = visitor(f"{tag}e", last_name="Smith", language="en", sex="female", new_in_area=True, birth_day=9, birth_month=7, phone="5553334444")
        assert (await pad.post("/api/kiosk/registrations/draft", json=form)).json() == {"ok": True}
        done = (await pad.post("/api/kiosk/registrations", json=form)).json()
        assert done["confirmation"].startswith("Thank you")
        doc = await db.visitor_registrations.find_one({"idempotency_key": form["idempotency_key"]})
        assert doc["language"] == "en" and doc["profile"]["sex"] == "female" and doc["visit"]["new_in_area"] is True
        assert doc["contact"]["birth_day"] == 9 and doc["contact"]["birth_month"] == 7 and doc["contact"]["birth_date"] is None
        # Persona 360: sexo y cumpleaños (día y mes) sin año; la edad no se inventa.
        person = await db.persons.find_one({"_id": ObjectId(doc["person_id"])})
        assert person["genero"] == "femenino" and person["cumpleanos_dia"] == 9 and person["cumpleanos_mes"] == 7 and not person.get("fecha_nacimiento")
        header = (await pastora.get(f"/api/core/persons/{doc['person_id']}/profile")).json()["header"]
        assert header["cumpleanos"] == {"dia": 9, "mes": 7} and not header.get("fecha_nacimiento") and header.get("age_years") is None

        # Seguimiento: idioma preferido y sexo visibles para el equipo; resumen legible.
        item = next(row for row in (await pastora.get("/api/visitors/followup")).json()["items"] if row["registration_id"] == doc["registration_id"])
        assert item["language"] == "en" and item["sex"] == "female" and item["new_in_area"] is True
        summary = {entry["label"]: entry["value"] for section in item["answers"] for entry in section["items"]}
        assert summary["Cumpleaños"] == "9 de julio" and summary["Sexo"] == "Femenino" and summary["Es nuevo en esta área"] == "Sí" and summary["Idioma preferido"].startswith("Inglés")

        # La pantalla de bienvenida NO recibe sexo ni idioma (el nombre no cambia).
        view = (await tv.get("/api/screen/welcome")).json()
        assert all(set(row) == {"id", "name", "invited_by", "registering"} for row in view["names"])
        assert any(row["name"] == f"Visit{tag}e Smith" for row in view["names"]) and "female" not in str(view)

        # Fechas: el 31 de abril no existe; el 29 de febrero sí (sin año).
        assert (await pad.post("/api/kiosk/registrations", json=visitor(f"{tag}x", birth_day=31, birth_month=4))).status_code == 422
        assert (await pad.post("/api/kiosk/registrations", json=visitor(f"{tag}y", birth_day=9))).status_code == 422
        leap = await pad.post("/api/kiosk/registrations", json=visitor(f"{tag}f", birth_day=29, birth_month=2, sex="male"))
        assert leap.status_code == 201 and leap.json()["confirmation"].startswith("¡Gracias")

        # Con año (si la administración lo activa) se guarda la fecha completa.
        settings = (await pastora.get("/api/visitors/kiosk-settings")).json()
        assert settings["ask_birth_year"] is False
        assert (await pastora.put("/api/visitors/kiosk-settings", json={**settings, "ask_birth_year": True})).json()["ask_birth_year"] is True
        assert (await pad.get("/api/kiosk/config")).json()["ask_birth_year"] is True
        full = visitor(f"{tag}g", birth_date="1990-03-05")
        assert (await pad.post("/api/kiosk/registrations", json=full)).status_code == 201
        full_doc = await db.visitor_registrations.find_one({"idempotency_key": full["idempotency_key"]})
        assert full_doc["contact"]["birth_date"] == "1990-03-05" and full_doc["contact"]["birth_month"] == 3 and full_doc["contact"]["birth_day"] == 5

        # Textos editables por idioma: cambiar el aviso en inglés sube la versión.
        texts = (await pastora.get("/api/visitors/texts")).json()
        changed = (await pastora.put("/api/visitors/texts", json={"welcome": texts["welcome"], "privacy": texts["privacy"], "confirmation": texts["confirmation"],
                                                                   "privacy_en": "We only use your information to serve you.\nWe never share it."})).json()
        assert changed["privacy_version"] == texts["privacy_version"] + 1 and changed["privacy_en"].startswith("We only") and changed["welcome_en"] == texts["welcome_en"]
        assert (await pad.get("/api/kiosk/config")).json()["texts_en"]["privacy"].startswith("We only")
    finally:
        await cleanup(tag)
        for key, saved in (("visitor_kiosk_settings", before_settings), ("visitor_texts", before_texts)):
            if saved:
                await db.app_settings.replace_one({"_id": key}, saved, upsert=True)
            else:
                await db.app_settings.delete_one({"_id": key})
        await db.app_settings.delete_many({"_id": "visitor_welcome_state"})
        for client in clients:
            await client.aclose()
        await fx.cleanup()
