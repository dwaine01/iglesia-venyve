"""Complete Person Profile 360 modular block tests."""
import base64
import os
import uuid

import bcrypt
import pytest
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "ley7semanas_test_db")
os.environ.setdefault("JWT_SECRET", "test-secret-do-not-use-in-prod")

import server  # noqa: E402
from access_control import access_defaults_for_role  # noqa: E402

PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


@pytest.mark.asyncio
async def test_complete_profile_block_is_modular_visible_and_persistent():
    unique = uuid.uuid4().hex
    email = f"profile360.{unique}@example.com"
    password = "Profile360TestPass!"
    user = {
        "nombre": "Profile Tester",
        "email": email,
        "password": bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode(),
        "rol": "lider",
        "is_active": True,
        "token_version": 1,
        **access_defaults_for_role("lider"),
    }
    user_result = await server.db.users.insert_one(user)
    user_id = str(user_result.inserted_id)
    transport = ASGITransport(app=server.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        login = await client.post("/api/auth/login", json={"email": email, "password": password})
        assert login.status_code == 200
        client.headers.update({"Authorization": f"Bearer {login.json()['token']}"})
        created = await client.post(
            "/api/core/persons",
            json={
                "nombre": "Ana",
                "apellido": "Guzmán",
                "fecha_nacimiento": "1990-03-12",
                "idempotency_key": str(uuid.uuid4()),
            },
        )
        assert created.status_code == 201, created.text
        person_id = created.json()["person_id"]

        try:
            basics = await client.put(
                f"/api/core/persons/{person_id}/profile-basics",
                json={
                    "nombre": "Ana María",
                    "apellido": "Guzmán",
                    "fecha_nacimiento": "1990-03-12",
                    "genero": "femenino",
                    "estado_civil": "casada",
                    "ocupacion": "Docente",
                },
            )
            assert basics.status_code == 200, basics.text

            household = await client.put(
                f"/api/core/persons/{person_id}/household",
                json={
                    "nombre_hogar": "Hogar Guzmán",
                    "rol_en_hogar": "Madre",
                    "tipo_vivienda": "Propia",
                    "miembros_estimados": 4,
                    "notas": "Registro verificable",
                },
            )
            family = await client.post(
                f"/api/core/persons/{person_id}/family",
                json={
                    "nombre": "Carlos Guzmán",
                    "relacion": "Hermano",
                    "alcance": "extendida",
                    "telefono": "809-555-0199",
                },
            )
            arrival = await client.put(
                f"/api/core/persons/{person_id}/arrival",
                json={
                    "fecha_llegada": "2024-01-14",
                    "tipo": "invitado" if False else "visitante",
                    "lugar_origen": "Santiago",
                    "invitado_por": "Equipo de bienvenida",
                    "motivo": "Primera visita",
                },
            )
            attendance = await client.post(
                f"/api/core/persons/{person_id}/attendance",
                json={
                    "fecha": "2025-06-15",
                    "actividad": "Servicio dominical",
                    "estado": "presente",
                },
            )
            note = await client.post(
                f"/api/core/persons/{person_id}/notes",
                json={"contenido": "Seguimiento pastoral acordado.", "categoria": "seguimiento"},
            )
            assert household.status_code == 200
            assert family.status_code == 201
            assert arrival.status_code == 200
            assert attendance.status_code == 201
            assert note.status_code == 201

            init = await client.post(
                f"/api/core/persons/{person_id}/photo/uploads",
                json={"content_type": "image/png", "total_size": len(PNG_1X1), "total_chunks": 1},
            )
            assert init.status_code == 201, init.text
            upload_id = init.json()["upload_id"]
            chunk = await client.put(
                f"/api/core/persons/{person_id}/photo/uploads/{upload_id}/chunks/0",
                content=PNG_1X1,
                headers={"Authorization": client.headers["Authorization"], "Content-Type": "application/octet-stream"},
            )
            complete = await client.post(
                f"/api/core/persons/{person_id}/photo/uploads/{upload_id}/complete"
            )
            photo = await client.get(f"/api/core/persons/{person_id}/photo")
            assert chunk.status_code == 200
            assert complete.status_code == 200
            assert photo.status_code == 200
            assert photo.headers["content-type"] == "image/png"
            assert photo.content == PNG_1X1

            profile = await client.get(f"/api/core/persons/{person_id}/profile")
            assert profile.status_code == 200, profile.text
            body = profile.json()
            assert body["sections_available"] == [
                "resumen", "contacto", "direcciones", "household",
                "familia", "procesos", "asistencia", "historial",
            ]
            assert body["sections_planned"] == []
            assert body["profile_can_write"] is True
            assert body["header"]["photo_available"] is True
            assert body["header"]["nombre_completo"] == "Ana María Guzmán"
            assert body["header"]["genero"] == "femenino"
            assert body["header"]["estado_civil"] == "casada"
            assert body["header"]["ocupacion"] == "Docente"
            assert body["household"]["nombre_hogar"] == "Hogar Guzmán"
            assert body["familia"][0]["alcance"] == "extendida"
            assert body["llegada_origen"]["lugar_origen"] == "Santiago"
            assert body["asistencia"][0]["actividad"] == "Servicio dominical"
            assert body["notas"][0]["categoria"] == "seguimiento"
            assert len(body["historial"]) >= 6
            assert len(body["procesos"]) == 9
            assert {item["status_code"] for item in body["procesos"]} == {"module_unavailable"}

            statuses = {item["section_key"]: item["status_code"] for item in body["sections"]}
            for built in ("llegada_origen", "familia", "household", "asistencia", "historial"):
                assert statuses[built] == "has_summary"
            for unavailable in (
                "membership", "bautismo", "bienvenida", "consolidacion", "ley7",
                "discipulado", "mentor_acompanamiento", "celula", "ministerio_servicio",
            ):
                assert statuses[unavailable] == "module_unavailable"

            person_doc = await server.db.persons.find_one({"_id": created.json()["_id"]}) if "_id" in created.json() else await server.db.persons.find_one({"person_number": created.json()["person_number"]})
            for forbidden in ("household", "familia", "asistencia", "notas", "procesos"):
                assert forbidden not in person_doc
        finally:
            for collection in (
                server.db.person_households,
                server.db.person_family,
                server.db.person_arrivals,
                server.db.person_attendance,
                server.db.person_notes,
                server.db.person_activity,
                server.db.person_photos,
                server.db.person_photo_uploads,
            ):
                await collection.delete_many({"person_id": person_id})
            await server.db.person_photo_chunks.delete_many({"upload_id": upload_id if 'upload_id' in locals() else None})
            from bson import ObjectId
            await server.db.persons.delete_one({"_id": ObjectId(person_id)})
    await server.db.users.delete_one({"_id": user_result.inserted_id})
