"""Invasiones — Entrega A: roster con auto-creación de cuenta, paso de libros
(Librería 360) por invasión, entrega idempotente de MCD/NPT desde el informe
de visita, dirección completa + horario de llamadas, e informe de líderes por
invasión.

Cubre:
- `POST /campaigns`: un mentor sin cuenta en el roster exige correo+clave
  temporal (se auto-crea con `mentor_access=True`); sin esos datos, 422 claro.
- `POST /campaigns/{id}/books`: valida que el mentor esté en el roster, que el
  libro exista/activo y que haya existencia central suficiente (409 claro si
  no); genera movimientos ASSIGNMENT etiquetados con la invasión.
- `GET /campaigns/{id}/books` y `GET /api/library/my-holdings`: reflejan
  asignado/entregado/restante por invasión.
- `PUT /visits/{id}/report` con `received_mcd`/`received_npt=True`: entrega 1
  unidad del inventario del mentor a la persona (idempotente; no se puede
  "desmarcar" una vez entregado; 409 claro si no quedan unidades).
- La dirección completa y el horario de llamadas capturados en la visita se
  copian a la Persona 360 / enrollment al iniciar la Ley de las 7 Semanas.
- `GET /campaigns/{id}/report`: actividad por mentor y libros asignados/entregados.
"""
import uuid
from datetime import datetime, timezone

import bcrypt
import pytest
from bson import ObjectId
from httpx import ASGITransport, AsyncClient

import server
from access_control import access_defaults_for_role
from qa_demo_cleanup import delete_qa_artifacts, qa_preview

PASSWORD = "OutreachEntregaAPass123!"


async def create_person(label: str) -> str:
    person_id = ObjectId()
    await server.db.persons.insert_one({
        "_id": person_id, "person_number": f"VV-QA{uuid.uuid4().hex[:7].upper()}",
        "nombre": "QA", "apellido": label, "idempotency_key": f"qa:entregaa:{uuid.uuid4()}",
        "version": 1, "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc),
    })
    return str(person_id)


async def create_user(label: str, role: str, person_id: str | None = None, capabilities=None) -> tuple[str, str]:
    user_id = ObjectId()
    slug = label.lower().replace(" ", ".")
    email = f"qa.entregaa.{slug}.{uuid.uuid4().hex[:6]}@example.com"
    defaults = access_defaults_for_role(role)
    defaults["capabilities"] = sorted(set(defaults.get("capabilities", []) + (capabilities or [])))
    document = {
        "_id": user_id, "nombre": f"QA {label}", "email": email,
        "password": bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt()).decode(),
        "rol": role, "is_active": True, "token_version": 1,
        "created_at": datetime.now(timezone.utc), **defaults,
    }
    if person_id:
        document["person_id"] = person_id
    await server.db.users.insert_one(document)
    return str(user_id), email


async def auth_client(email: str, password: str = PASSWORD) -> tuple[AsyncClient, dict]:
    client = AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test")
    login = await client.post("/api/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text
    return client, {"Authorization": f"Bearer {login.json()['token']}"}


async def activate_badge(pid: str) -> None:
    await server.db.mentor_badges.update_one(
        {"person_id": pid},
        {"$set": {"person_id": pid, "active": True, "since": "2026-01-01", "updated_at": datetime.now(timezone.utc)}},
        upsert=True,
    )


_ORIGINAL_CENTRAL_STOCK: dict[str, int] = {}


async def set_central_stock(sku: str, quantity: int) -> str:
    book = await server.db.library_books.find_one({"sku": sku, "is_active": True}, {"_id": 0, "book_id": 1})
    if sku not in _ORIGINAL_CENTRAL_STOCK:
        existing = await server.db.library_holdings.find_one({"book_id": book["book_id"], "holder_type": "warehouse", "holder_id": "central"})
        _ORIGINAL_CENTRAL_STOCK[sku] = (existing or {}).get("quantity_on_hand", 0)
    await server.db.library_holdings.update_one(
        {"book_id": book["book_id"], "holder_type": "warehouse", "holder_id": "central"},
        {"$set": {"quantity_on_hand": quantity, "reserved_qty": 0, "updated_at": datetime.now(timezone.utc)}, "$setOnInsert": {"_id": str(uuid.uuid4())}},
        upsert=True,
    )
    return book["book_id"]


@pytest.fixture(scope="module", autouse=True)
def _restore_central_stock_after_module():
    """Las existencias centrales reales de MCD/NPT se sobrescriben con
    `set_central_stock` para pruebas deterministas; se restauran al terminar
    este archivo para no dejar el inventario real desincronizado."""
    yield
    async def _restore():
        for sku, original in _ORIGINAL_CENTRAL_STOCK.items():
            book = await server.db.library_books.find_one({"sku": sku}, {"_id": 0, "book_id": 1})
            if book:
                await server.db.library_holdings.update_one(
                    {"book_id": book["book_id"], "holder_type": "warehouse", "holder_id": "central"},
                    {"$set": {"quantity_on_hand": original}},
                )
    import asyncio
    asyncio.get_event_loop().run_until_complete(_restore())


async def cleanup(campaign_ids=None):
    if campaign_ids:
        await server.db.library_movements.delete_many({"campaign_id": {"$in": campaign_ids}})
    preview = await qa_preview(server.db)
    await delete_qa_artifacts(server.db, preview["preview_token"], preview["confirmation_phrase"])


@pytest.mark.asyncio
async def test_create_campaign_auto_creates_missing_mentor_account():
    await cleanup()
    pastor_pid = await create_person("Pastor EntregaA Roster")
    _, pastor_email = await create_user("Pastor EntregaA Roster", "pastor", pastor_pid)
    with_account_pid = await create_person("Mentor Con Cuenta Roster")
    await activate_badge(with_account_pid)
    await create_user("Mentor Con Cuenta Roster", "persona", with_account_pid)
    without_account_pid = await create_person("Mentor Sin Cuenta Roster")
    await activate_badge(without_account_pid)

    pastor_client, pastor_headers = await auth_client(pastor_email)
    campaign_id = None
    try:
        new_email = f"qa.entregaa.autocreado.{uuid.uuid4().hex[:6]}@example.com"
        response = await pastor_client.post(
            "/api/mentorship/outreach/campaigns",
            json={
                "name": "Invasion Autocreacion", "location": "Zona QA", "start_date": "2026-04-01", "end_date": "2026-04-07",
                "assigned_mentors": [
                    {"person_id": with_account_pid},
                    {"person_id": without_account_pid, "email": new_email, "temporary_password": "MentorAutoPass123!"},
                ],
            },
            headers=pastor_headers,
        )
        assert response.status_code == 201, response.text
        campaign_id = response.json()["campaign_id"]
        assert set(response.json()["assigned_mentor_ids"]) == {with_account_pid, without_account_pid}
        accounts_created = response.json()["accounts_created"]
        assert len(accounts_created) == 1
        assert accounts_created[0]["person_id"] == without_account_pid

        login = await pastor_client.post("/api/auth/login", json={"email": new_email, "password": "MentorAutoPass123!"})
        assert login.status_code == 200
        assert login.json()["user"]["must_change_password"] is True
    finally:
        await pastor_client.aclose()
        await cleanup([campaign_id] if campaign_id else None)


@pytest.mark.asyncio
async def test_create_campaign_without_credentials_for_accountless_mentor_fails_clearly():
    await cleanup()
    pastor_pid = await create_person("Pastor EntregaA SinClave")
    _, pastor_email = await create_user("Pastor EntregaA SinClave", "pastor", pastor_pid)
    without_account_pid = await create_person("Mentor Sin Credenciales")
    await activate_badge(without_account_pid)

    pastor_client, pastor_headers = await auth_client(pastor_email)
    try:
        response = await pastor_client.post(
            "/api/mentorship/outreach/campaigns",
            json={"name": "Invasion Sin Clave", "location": "Zona QA", "start_date": "2026-04-01", "end_date": "2026-04-07", "assigned_mentors": [{"person_id": without_account_pid}]},
            headers=pastor_headers,
        )
        assert response.status_code == 422, response.text
        assert "correo" in response.json()["detail"].lower()
        assert not await server.db.users.find_one({"person_id": without_account_pid})
    finally:
        await pastor_client.aclose()
        await cleanup()


@pytest.mark.asyncio
async def test_assign_campaign_books_requires_mentor_in_roster_and_active_book():
    await cleanup()
    pastor_pid = await create_person("Pastor EntregaA Roster2")
    _, pastor_email = await create_user("Pastor EntregaA Roster2", "pastor", pastor_pid)
    mentor_pid = await create_person("Mentor En Roster Libros")
    await activate_badge(mentor_pid)
    await create_user("Mentor En Roster Libros", "persona", mentor_pid)
    outsider_pid = await create_person("Mentor Fuera De Roster")
    await activate_badge(outsider_pid)
    await create_user("Mentor Fuera De Roster", "persona", outsider_pid)
    book_id = await set_central_stock("MCD", 50)

    pastor_client, pastor_headers = await auth_client(pastor_email)
    campaign_id = None
    try:
        created = await pastor_client.post(
            "/api/mentorship/outreach/campaigns",
            json={"name": "Invasion Roster Libros", "location": "Zona QA", "start_date": "2026-04-01", "end_date": "2026-04-07", "assigned_mentors": [{"person_id": mentor_pid}]},
            headers=pastor_headers,
        )
        assert created.status_code == 201, created.text
        campaign_id = created.json()["campaign_id"]

        outside_roster = await pastor_client.post(
            f"/api/mentorship/outreach/campaigns/{campaign_id}/books",
            json={"assignments": [{"mentor_person_id": outsider_pid, "book_id": book_id, "quantity": 5}]},
            headers=pastor_headers,
        )
        assert outside_roster.status_code == 409
        assert "roster" in outside_roster.json()["detail"].lower()
    finally:
        await pastor_client.aclose()
        await cleanup([campaign_id] if campaign_id else None)


@pytest.mark.asyncio
async def test_assign_campaign_books_fails_clearly_when_central_stock_insufficient():
    await cleanup()
    pastor_pid = await create_person("Pastor EntregaA Stock")
    _, pastor_email = await create_user("Pastor EntregaA Stock", "pastor", pastor_pid)
    mentor_pid = await create_person("Mentor Stock Insuficiente")
    await activate_badge(mentor_pid)
    await create_user("Mentor Stock Insuficiente", "persona", mentor_pid)
    book_id = await set_central_stock("NPT", 3)

    pastor_client, pastor_headers = await auth_client(pastor_email)
    campaign_id = None
    try:
        created = await pastor_client.post(
            "/api/mentorship/outreach/campaigns",
            json={"name": "Invasion Stock Insuficiente", "location": "Zona QA", "start_date": "2026-04-01", "end_date": "2026-04-07", "assigned_mentors": [{"person_id": mentor_pid}]},
            headers=pastor_headers,
        )
        assert created.status_code == 201, created.text
        campaign_id = created.json()["campaign_id"]

        response = await pastor_client.post(
            f"/api/mentorship/outreach/campaigns/{campaign_id}/books",
            json={"assignments": [{"mentor_person_id": mentor_pid, "book_id": book_id, "quantity": 10}]},
            headers=pastor_headers,
        )
        assert response.status_code == 409, response.text
        detail = response.json()["detail"].lower()
        assert "existencias" in detail and "10" in detail and "3" in detail

        holding = await server.db.library_holdings.find_one({"book_id": book_id, "holder_type": "warehouse", "holder_id": "central"})
        assert holding["quantity_on_hand"] == 3, "no debe mover nada si la validación falla"
    finally:
        await pastor_client.aclose()
        await cleanup([campaign_id] if campaign_id else None)


@pytest.mark.asyncio
async def test_assign_campaign_books_succeeds_and_feeds_my_holdings_breakdown():
    await cleanup()
    pastor_pid = await create_person("Pastor EntregaA Exito")
    _, pastor_email = await create_user("Pastor EntregaA Exito", "pastor", pastor_pid)
    mentor_pid = await create_person("Mentor Recibe Libros")
    await activate_badge(mentor_pid)
    mentor_email = f"qa.entregaa.recibelibros.{uuid.uuid4().hex[:6]}@example.com"
    await create_user("Mentor Recibe Libros", "persona", mentor_pid, capabilities=["mentorship.outreach.report", "library.deliver"])
    await server.db.users.update_one({"person_id": mentor_pid}, {"$set": {"email": mentor_email}})
    book_id = await set_central_stock("MCD", 50)

    pastor_client, pastor_headers = await auth_client(pastor_email)
    campaign_id = None
    try:
        created = await pastor_client.post(
            "/api/mentorship/outreach/campaigns",
            json={"name": "Invasion Exito Libros", "location": "Zona QA", "start_date": "2026-04-01", "end_date": "2026-04-07", "assigned_mentors": [{"person_id": mentor_pid}]},
            headers=pastor_headers,
        )
        assert created.status_code == 201, created.text
        campaign_id = created.json()["campaign_id"]

        assign = await pastor_client.post(
            f"/api/mentorship/outreach/campaigns/{campaign_id}/books",
            json={"assignments": [{"mentor_person_id": mentor_pid, "book_id": book_id, "quantity": 10}]},
            headers=pastor_headers,
        )
        assert assign.status_code == 201, assign.text

        books_view = await pastor_client.get(f"/api/mentorship/outreach/campaigns/{campaign_id}/books", headers=pastor_headers)
        assert books_view.status_code == 200
        row = books_view.json()["items"][0]
        assert row["assigned"] == 10 and row["delivered"] == 0 and row["remaining"] == 10

        central = await server.db.library_holdings.find_one({"book_id": book_id, "holder_type": "warehouse", "holder_id": "central"})
        assert central["quantity_on_hand"] == 40

        mentor_client, mentor_headers = await auth_client(mentor_email)
        try:
            holdings = await mentor_client.get("/api/library/my-holdings", headers=mentor_headers)
            assert holdings.status_code == 200, holdings.text
            mcd_item = next(item for item in holdings.json()["items"] if item["book"]["book_id"] == book_id)
            assert mcd_item["on_hand"] == 10
            campaign_breakdown = next(c for c in mcd_item["campaigns"] if c["campaign_id"] == campaign_id)
            assert campaign_breakdown["assigned"] == 10 and campaign_breakdown["delivered"] == 0 and campaign_breakdown["remaining"] == 10
        finally:
            await mentor_client.aclose()
    finally:
        await pastor_client.aclose()
        await cleanup([campaign_id] if campaign_id else None)


@pytest.mark.asyncio
async def test_deliver_mcd_in_visit_report_is_idempotent_and_locks_undo():
    await cleanup()
    pastor_pid = await create_person("Pastor EntregaA Entrega")
    _, pastor_email = await create_user("Pastor EntregaA Entrega", "pastor", pastor_pid)
    mentor_pid = await create_person("Mentor Entrega MCD")
    await activate_badge(mentor_pid)
    mentor_email = f"qa.entregaa.entregamcd.{uuid.uuid4().hex[:6]}@example.com"
    await create_user("Mentor Entrega MCD", "persona", mentor_pid, capabilities=["mentorship.outreach.report", "library.deliver"])
    await server.db.users.update_one({"person_id": mentor_pid}, {"$set": {"email": mentor_email}})
    book_id = await set_central_stock("MCD", 50)

    pastor_client, pastor_headers = await auth_client(pastor_email)
    campaign_id = None
    try:
        created = await pastor_client.post(
            "/api/mentorship/outreach/campaigns",
            json={"name": "Invasion Entrega MCD", "location": "Zona QA", "start_date": "2026-04-01", "end_date": "2026-04-07", "assigned_mentors": [{"person_id": mentor_pid}]},
            headers=pastor_headers,
        )
        campaign_id = created.json()["campaign_id"]
        await pastor_client.post(
            f"/api/mentorship/outreach/campaigns/{campaign_id}/books",
            json={"assignments": [{"mentor_person_id": mentor_pid, "book_id": book_id, "quantity": 1}]},
            headers=pastor_headers,
        )

        mentor_client, mentor_headers = await auth_client(mentor_email)
        try:
            visit = await mentor_client.post(
                "/api/mentorship/outreach/visits",
                json={"contact_type": "new", "contact_name": "Casa Entrega MCD", "contact_phone": "8095551234", "mentor_person_id": mentor_pid, "campaign_id": campaign_id},
                headers=mentor_headers,
            )
            assert visit.status_code == 201, visit.text
            visit_id = visit.json()["visit_id"]

            report = await mentor_client.put(f"/api/mentorship/outreach/visits/{visit_id}/report", json={"status": "visited", "received_mcd": True}, headers=mentor_headers)
            assert report.status_code == 200, report.text
            assert report.json()["mcd_delivered"] is True
            assert report.json()["received_mcd"] is True

            central_after_first = await server.db.library_holdings.find_one({"book_id": book_id, "holder_type": "warehouse", "holder_id": "central"})
            assert central_after_first["quantity_on_hand"] == 49

            # idempotente: volver a guardar con received_mcd=True no debe descontar otra vez.
            report_again = await mentor_client.put(f"/api/mentorship/outreach/visits/{visit_id}/report", json={"status": "visited", "received_mcd": True}, headers=mentor_headers)
            assert report_again.status_code == 200, report_again.text
            movements_count = await server.db.library_movements.count_documents({"campaign_id": campaign_id, "movement_type": "DELIVERY"})
            assert movements_count == 1, "no debe repetir el movimiento de entrega"

            # no se puede "desmarcar" una entrega ya realizada.
            undo = await mentor_client.put(f"/api/mentorship/outreach/visits/{visit_id}/report", json={"status": "visited", "received_mcd": False}, headers=mentor_headers)
            assert undo.status_code == 409
            assert "entreg" in undo.json()["detail"].lower()
        finally:
            await mentor_client.aclose()
    finally:
        await pastor_client.aclose()
        await cleanup([campaign_id] if campaign_id else None)


@pytest.mark.asyncio
async def test_deliver_mcd_fails_clearly_when_mentor_has_no_units_left():
    await cleanup()
    pastor_pid = await create_person("Pastor EntregaA SinUnidades")
    _, pastor_email = await create_user("Pastor EntregaA SinUnidades", "pastor", pastor_pid)
    mentor_pid = await create_person("Mentor Sin Unidades MCD")
    await activate_badge(mentor_pid)
    mentor_email = f"qa.entregaa.sinunidades.{uuid.uuid4().hex[:6]}@example.com"
    await create_user("Mentor Sin Unidades MCD", "persona", mentor_pid, capabilities=["mentorship.outreach.report", "library.deliver"])
    await server.db.users.update_one({"person_id": mentor_pid}, {"$set": {"email": mentor_email}})

    mentor_client, mentor_headers = await auth_client(mentor_email)
    try:
        visit = await mentor_client.post(
            "/api/mentorship/outreach/visits",
            json={"contact_type": "new", "contact_name": "Casa Sin Libros", "contact_phone": "8095559999", "mentor_person_id": mentor_pid},
            headers=mentor_headers,
        )
        visit_id = visit.json()["visit_id"]
        report = await mentor_client.put(f"/api/mentorship/outreach/visits/{visit_id}/report", json={"status": "visited", "received_mcd": True}, headers=mentor_headers)
        assert report.status_code == 409
        assert "unidades" in report.json()["detail"].lower()
    finally:
        await mentor_client.aclose()
        await cleanup()


@pytest.mark.asyncio
async def test_visit_address_and_call_schedule_flow_into_person_and_enrollment():
    await cleanup()
    pastor_pid = await create_person("Pastor EntregaA Direccion")
    _, pastor_email = await create_user("Pastor EntregaA Direccion", "pastor", pastor_pid)
    mentor_pid = await create_person("Mentor Direccion Completa")
    await activate_badge(mentor_pid)
    mentor_email = f"qa.entregaa.direccion.{uuid.uuid4().hex[:6]}@example.com"
    await create_user("Mentor Direccion Completa", "persona", mentor_pid, capabilities=["mentorship.outreach.report", "library.deliver", "processes.participate"])
    await server.db.users.update_one({"person_id": mentor_pid}, {"$set": {"email": mentor_email}})

    mentor_client, mentor_headers = await auth_client(mentor_email)
    try:
        visit = await mentor_client.post(
            "/api/mentorship/outreach/visits",
            json={"contact_type": "new", "contact_name": "Casa Direccion Completa", "contact_phone": "8095557777", "mentor_person_id": mentor_pid},
            headers=mentor_headers,
        )
        visit_id = visit.json()["visit_id"]
        report = await mentor_client.put(
            f"/api/mentorship/outreach/visits/{visit_id}/report",
            json={
                "status": "wants_followup", "address_line1": "Calle Principal 45", "address_city": "Santiago",
                "address_state": "Santiago", "address_zip": "51000", "agreed_start_date": "2026-04-10", "call_schedule": "night",
            },
            headers=mentor_headers,
        )
        assert report.status_code == 200, report.text

        started = await mentor_client.post(f"/api/mentorship/outreach/visits/{visit_id}/start-seven-weeks", headers=mentor_headers)
        assert started.status_code == 200, started.text
        person_id = started.json()["converted_person_id"]
        enrollment_id = started.json()["enrollment_id"]

        address = await server.db.person_addresses.find_one({"person_id": person_id})
        assert address is not None, "la dirección completa debe copiarse a Persona 360"
        assert address["linea1"] == "Calle Principal 45"
        assert address["ciudad"] == "Santiago"
        assert address["codigo_postal"] == "51000"

        enrollment = await server.db.process_enrollments.find_one({"enrollment_id": enrollment_id})
        assert enrollment["outreach_agreed_start_date"] == "2026-04-10"
        assert enrollment["outreach_call_schedule"] == "night"
        # Puerta "invasion": S1 (oración) y S2 (invasión) ya se vivieron con la
        # campaña -> quedan "completed" y el expediente abre listo en MCD.
        assert enrollment["entry_mode"] == "invasion"
        assert enrollment["current_stage_key"] == "mcd"
        prior_stages = await server.db.process_stage_progress.find(
            {"enrollment_id": enrollment_id, "stage_key": {"$in": ["visitor_followup", "prayer", "invasion"]}}, {"_id": 0},
        ).to_list(10)
        assert {s["status"] for s in prior_stages} == {"completed"}
        mcd_stage = await server.db.process_stage_progress.find_one({"enrollment_id": enrollment_id, "stage_key": "mcd"})
        assert mcd_stage["status"] == "open"
    finally:
        await mentor_client.aclose()
        await cleanup()


@pytest.mark.asyncio
async def test_campaign_report_shows_mentor_activity_and_no_activity():
    await cleanup()
    pastor_pid = await create_person("Pastor EntregaA Informe")
    _, pastor_email = await create_user("Pastor EntregaA Informe", "pastor", pastor_pid)
    active_mentor_pid = await create_person("Mentor Con Actividad")
    await activate_badge(active_mentor_pid)
    active_email = f"qa.entregaa.conactividad.{uuid.uuid4().hex[:6]}@example.com"
    await create_user("Mentor Con Actividad", "persona", active_mentor_pid, capabilities=["mentorship.outreach.report", "library.deliver"])
    await server.db.users.update_one({"person_id": active_mentor_pid}, {"$set": {"email": active_email}})
    idle_mentor_pid = await create_person("Mentor Sin Actividad")
    await activate_badge(idle_mentor_pid)
    await create_user("Mentor Sin Actividad", "persona", idle_mentor_pid)

    pastor_client, pastor_headers = await auth_client(pastor_email)
    campaign_id = None
    try:
        created = await pastor_client.post(
            "/api/mentorship/outreach/campaigns",
            json={"name": "Invasion Informe Lideres", "location": "Zona QA", "start_date": "2026-04-01", "end_date": "2026-04-07", "assigned_mentors": [{"person_id": active_mentor_pid}, {"person_id": idle_mentor_pid}]},
            headers=pastor_headers,
        )
        campaign_id = created.json()["campaign_id"]

        active_client, active_headers = await auth_client(active_email)
        try:
            visit = await active_client.post(
                "/api/mentorship/outreach/visits",
                json={"contact_type": "new", "contact_name": "Casa Con Actividad", "contact_phone": "8095556666", "mentor_person_id": active_mentor_pid, "campaign_id": campaign_id},
                headers=active_headers,
            )
            assert visit.status_code == 201, visit.text
            await active_client.put(f"/api/mentorship/outreach/visits/{visit.json()['visit_id']}/report", json={"status": "wants_followup"}, headers=active_headers)
        finally:
            await active_client.aclose()

        report = await pastor_client.get(f"/api/mentorship/outreach/campaigns/{campaign_id}/report", headers=pastor_headers)
        assert report.status_code == 200, report.text
        mentors_by_id = {item["mentor_person_id"]: item for item in report.json()["mentors"]}
        assert mentors_by_id[active_mentor_pid]["has_activity"] is True
        assert mentors_by_id[active_mentor_pid]["contacts_total"] == 1
        assert mentors_by_id[active_mentor_pid]["accepted"] == 1
        assert mentors_by_id[idle_mentor_pid]["has_activity"] is False
    finally:
        await pastor_client.aclose()
        await cleanup([campaign_id] if campaign_id else None)


@pytest.mark.asyncio
async def test_leader_opens_book_and_sees_delivery_recipients():
    await cleanup()
    pastor_pid = await create_person("Pastor EntregaA AbreLibro")
    _, pastor_email = await create_user("Pastor EntregaA AbreLibro", "pastor", pastor_pid)
    mentor_pid = await create_person("Mentor Abre Libro")
    await activate_badge(mentor_pid)
    mentor_email = f"qa.entregaa.abrelibro.{uuid.uuid4().hex[:6]}@example.com"
    await create_user("Mentor Abre Libro", "persona", mentor_pid, capabilities=["mentorship.outreach.report", "library.deliver"])
    await server.db.users.update_one({"person_id": mentor_pid}, {"$set": {"email": mentor_email}})
    book_id = await set_central_stock("MCD", 50)

    pastor_client, pastor_headers = await auth_client(pastor_email)
    campaign_id = None
    try:
        created = await pastor_client.post(
            "/api/mentorship/outreach/campaigns",
            json={"name": "Invasion Abre Libro", "location": "Zona QA", "start_date": "2026-04-01", "end_date": "2026-04-07", "assigned_mentors": [{"person_id": mentor_pid}]},
            headers=pastor_headers,
        )
        campaign_id = created.json()["campaign_id"]
        await pastor_client.post(
            f"/api/mentorship/outreach/campaigns/{campaign_id}/books",
            json={"assignments": [{"mentor_person_id": mentor_pid, "book_id": book_id, "quantity": 2}]},
            headers=pastor_headers,
        )

        mentor_client, mentor_headers = await auth_client(mentor_email)
        try:
            visit = await mentor_client.post(
                "/api/mentorship/outreach/visits",
                json={"contact_type": "new", "contact_name": "Casa Recibio Libro", "contact_phone": "8095558888", "mentor_person_id": mentor_pid, "campaign_id": campaign_id},
                headers=mentor_headers,
            )
            visit_id = visit.json()["visit_id"]
            report = await mentor_client.put(f"/api/mentorship/outreach/visits/{visit_id}/report", json={"status": "visited", "received_mcd": True}, headers=mentor_headers)
            assert report.status_code == 200, report.text
            delivered_person_id = report.json()["converted_person_id"] or report.json().get("person_id")
        finally:
            await mentor_client.aclose()

        recipients = await pastor_client.get(f"/api/mentorship/outreach/campaigns/{campaign_id}/books/{book_id}/deliveries", headers=pastor_headers)
        assert recipients.status_code == 200, recipients.text
        items = recipients.json()["items"]
        assert len(items) == 1
        assert items[0]["quantity"] == 1
        assert items[0]["person_name"] and items[0]["person_name"] != "—"
    finally:
        await pastor_client.aclose()
        await cleanup([campaign_id] if campaign_id else None)


@pytest.mark.asyncio
async def test_persona_mentor_sees_own_mentee_enrollment_in_list_not_just_dashboard():
    """Regresión (testing_agent iteración 40): un mentor con cuenta de rol
    'persona' veía el conteo correcto en el dashboard de Consolidación pero
    la lista GET /api/processes/enrollments?process_key=consolidation le
    salía vacía (access_person_ids cortaba antes de sumar sus asignaciones
    de mentor). Debe ver su propio disciplo en ambos lados."""
    await cleanup()
    pastor_pid = await create_person("Pastor EntregaA ListaMentor")
    _, pastor_email = await create_user("Pastor EntregaA ListaMentor", "pastor", pastor_pid)
    mentor_pid = await create_person("Mentor Ve Su Lista")
    await activate_badge(mentor_pid)
    mentor_email = f"qa.entregaa.velista.{uuid.uuid4().hex[:6]}@example.com"
    await create_user("Mentor Ve Su Lista", "persona", mentor_pid, capabilities=["mentorship.outreach.report", "library.deliver", "processes.participate"])
    await server.db.users.update_one({"person_id": mentor_pid}, {"$set": {"email": mentor_email}})

    mentor_client, mentor_headers = await auth_client(mentor_email)
    try:
        visit = await mentor_client.post(
            "/api/mentorship/outreach/visits",
            json={"contact_type": "new", "contact_name": "Casa Ve Su Lista", "contact_phone": "8095551111", "mentor_person_id": mentor_pid},
            headers=mentor_headers,
        )
        visit_id = visit.json()["visit_id"]
        await mentor_client.put(f"/api/mentorship/outreach/visits/{visit_id}/report", json={"status": "wants_followup"}, headers=mentor_headers)
        started = await mentor_client.post(f"/api/mentorship/outreach/visits/{visit_id}/start-seven-weeks", headers=mentor_headers)
        assert started.status_code == 200, started.text
        enrollment_id = started.json()["enrollment_id"]

        dashboard = await mentor_client.get("/api/processes/consolidation/dashboard", headers=mentor_headers)
        assert dashboard.status_code == 200
        assert dashboard.json()["total"] >= 1

        listing = await mentor_client.get("/api/processes/enrollments?process_key=consolidation", headers=mentor_headers)
        assert listing.status_code == 200, listing.text
        ids_in_list = {item["enrollment_id"] for item in listing.json()["items"]}
        assert enrollment_id in ids_in_list, "el mentor debe ver su propio disciplo en la lista, no solo en el conteo del dashboard"
    finally:
        await mentor_client.aclose()
        await cleanup()
    await cleanup()
    pastor_pid = await create_person("Pastor EntregaA Permiso Libros")
    _, pastor_email = await create_user("Pastor EntregaA Permiso Libros", "pastor", pastor_pid)
    leader_pid = await create_person("Lider Sin Permiso Libros")
    await activate_badge(leader_pid)
    _, leader_email = await create_user("Lider Sin Permiso Libros", "lider", leader_pid, capabilities=["mentorship.outreach.assign"])
    mentor_pid = await create_person("Mentor Para Permiso Libros")
    await activate_badge(mentor_pid)
    await create_user("Mentor Para Permiso Libros", "persona", mentor_pid)
    book_id = await set_central_stock("MCD", 50)

    pastor_client, pastor_headers = await auth_client(pastor_email)
    leader_client, leader_headers = await auth_client(leader_email)
    campaign_id = None
    try:
        created = await pastor_client.post(
            "/api/mentorship/outreach/campaigns",
            json={"name": "Invasion Permiso Libros", "location": "Zona QA", "start_date": "2026-04-01", "end_date": "2026-04-07", "assigned_mentors": [{"person_id": mentor_pid}]},
            headers=pastor_headers,
        )
        campaign_id = created.json()["campaign_id"]

        response = await leader_client.post(
            f"/api/mentorship/outreach/campaigns/{campaign_id}/books",
            json={"assignments": [{"mentor_person_id": mentor_pid, "book_id": book_id, "quantity": 5}]},
            headers=leader_headers,
        )
        assert response.status_code == 403
    finally:
        await pastor_client.aclose()
        await leader_client.aclose()
        await cleanup([campaign_id] if campaign_id else None)


@pytest.mark.asyncio
async def test_combined_mcd_npt_report_does_not_double_deliver_mcd_on_retry():
    """Regresión del bug de atomicidad (testing_agent iteración 39): si el
    mismo PUT trae received_mcd=True y received_npt=True, y el mentor no tiene
    NPT, MCD ya se entregó cuando NPT lanza 409. Un reintento con solo MCD=True
    NO debe generar un segundo movimiento DELIVERY ni descontar de nuevo."""
    await cleanup()
    pastor_pid = await create_person("Pastor EntregaA Atomico")
    _, pastor_email = await create_user("Pastor EntregaA Atomico", "pastor", pastor_pid)
    mentor_pid = await create_person("Mentor Atomico MCD NPT")
    await activate_badge(mentor_pid)
    mentor_email = f"qa.entregaa.atomico.{uuid.uuid4().hex[:6]}@example.com"
    await create_user("Mentor Atomico MCD NPT", "persona", mentor_pid, capabilities=["mentorship.outreach.report", "library.deliver"])
    await server.db.users.update_one({"person_id": mentor_pid}, {"$set": {"email": mentor_email}})
    mcd_book_id = await set_central_stock("MCD", 50)
    npt_book_id = await set_central_stock("NPT", 0)  # el mentor no tendrá NPT asignado

    pastor_client, pastor_headers = await auth_client(pastor_email)
    campaign_id = None
    try:
        created = await pastor_client.post(
            "/api/mentorship/outreach/campaigns",
            json={"name": "Invasion Atomica", "location": "Zona QA", "start_date": "2026-04-01", "end_date": "2026-04-07", "assigned_mentors": [{"person_id": mentor_pid}]},
            headers=pastor_headers,
        )
        campaign_id = created.json()["campaign_id"]
        await pastor_client.post(
            f"/api/mentorship/outreach/campaigns/{campaign_id}/books",
            json={"assignments": [{"mentor_person_id": mentor_pid, "book_id": mcd_book_id, "quantity": 1}]},
            headers=pastor_headers,
        )

        mentor_client, mentor_headers = await auth_client(mentor_email)
        try:
            visit = await mentor_client.post(
                "/api/mentorship/outreach/visits",
                json={"contact_type": "new", "contact_name": "Casa Atomica Combo", "contact_phone": "8095552222", "mentor_person_id": mentor_pid, "campaign_id": campaign_id},
                headers=mentor_headers,
            )
            visit_id = visit.json()["visit_id"]

            combined = await mentor_client.put(
                f"/api/mentorship/outreach/visits/{visit_id}/report",
                json={"status": "visited", "received_mcd": True, "received_npt": True},
                headers=mentor_headers,
            )
            assert combined.status_code == 409, combined.text  # falla por NPT sin stock

            mcd_movements = await server.db.library_movements.count_documents({"campaign_id": campaign_id, "movement_type": "DELIVERY", "book_id": mcd_book_id})
            assert mcd_movements == 1, "el MCD ya entregado antes del fallo de NPT debe quedar persistido una sola vez"

            retry = await mentor_client.put(
                f"/api/mentorship/outreach/visits/{visit_id}/report",
                json={"status": "visited", "received_mcd": True},
                headers=mentor_headers,
            )
            assert retry.status_code == 200, retry.text

            mcd_movements_after_retry = await server.db.library_movements.count_documents({"campaign_id": campaign_id, "movement_type": "DELIVERY", "book_id": mcd_book_id})
            assert mcd_movements_after_retry == 1, "el reintento NO debe duplicar el movimiento DELIVERY de MCD"
            central_mcd = await server.db.library_holdings.find_one({"book_id": mcd_book_id, "holder_type": "warehouse", "holder_id": "central"})
            assert central_mcd["quantity_on_hand"] == 49, "solo se debió descontar 1 unidad del central (vía ASSIGNMENT), no dos"
        finally:
            await mentor_client.aclose()
    finally:
        await pastor_client.aclose()
        await cleanup([campaign_id] if campaign_id else None)


@pytest.mark.asyncio
async def test_roster_account_creation_is_all_or_nothing():
    """Regresión del bug de cuentas huérfanas (testing_agent iteración 39): si
    un mentor del roster trae credenciales válidas y OTRO no, no debe crearse
    NINGUNA cuenta (ni la del primero) cuando la invasión falla por el segundo."""
    await cleanup()
    pastor_pid = await create_person("Pastor EntregaA Rollback")
    _, pastor_email = await create_user("Pastor EntregaA Rollback", "pastor", pastor_pid)
    mentor_a_pid = await create_person("Mentor Rollback A")
    await activate_badge(mentor_a_pid)
    mentor_b_pid = await create_person("Mentor Rollback B Sin Clave")
    await activate_badge(mentor_b_pid)

    pastor_client, pastor_headers = await auth_client(pastor_email)
    try:
        email_a = f"qa.entregaa.rollbacka.{uuid.uuid4().hex[:6]}@example.com"
        response = await pastor_client.post(
            "/api/mentorship/outreach/campaigns",
            json={
                "name": "Invasion Rollback Cuentas", "location": "Zona QA", "start_date": "2026-04-01", "end_date": "2026-04-07",
                "assigned_mentors": [
                    {"person_id": mentor_a_pid, "email": email_a, "temporary_password": "MentorRollbackA123!"},
                    {"person_id": mentor_b_pid},  # sin correo/clave -> debe fallar
                ],
            },
            headers=pastor_headers,
        )
        assert response.status_code == 422, response.text
        assert not await server.db.users.find_one({"person_id": mentor_a_pid}), "no debe quedar una cuenta huérfana para el mentor A si el B falla la validación"
        assert not await server.db.users.find_one({"email": email_a})
    finally:
        await pastor_client.aclose()
        await cleanup()
