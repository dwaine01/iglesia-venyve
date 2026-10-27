"""Nuevo flujo de Finanzas · P1: roles independientes (registrar, verificar, Tesorería, ver aportes por
persona), la pastora solo consulta, y «ver aportes por persona» solo por asignación explícita."""
import uuid

import pytest

from tests.test_pastoral_front_group_5c import Fixture, server  # noqa: I001 — server primero

db = server.db
FLOW = ["finance.collection.record", "finance.collection.verify", "finance.treasury", "finance.donors.read"]


@pytest.mark.asyncio
async def test_finance_roles_assignment_and_pastoral_read_only():
    from access_control import capability_catalog_keys
    from core_governance import access_defaults
    from finance_engine import ensure_indexes_and_seed
    await ensure_indexes_and_seed()
    assert set(FLOW) <= capability_catalog_keys()
    # El grupo Finanzas por defecto da Consultar/Administrar, nunca los roles de la colecta ni ver aportes.
    assert not set(FLOW) & set(access_defaults("tesorero", ["finance"])["capabilities"])

    fx, tag = Fixture(), uuid.uuid4().hex[:8]
    try:
        pastora = await fx.account(await fx.person(f"PastoraR{tag}"), "pastora")
        coord = await fx.account(await fx.person(f"CoordR{tag}"), "lider", access_level="coordinador_general", capabilities=["core.access.manage"])
        wanda_id = await fx.person(f"WandaR{tag}")
        wanda = await fx.account(wanda_id, "lider", privilege_groups=["finance"], capabilities=["finance.read", "finance.manage"], permissions_mode="manual")
        wanda_user = await db.users.find_one({"person_id": wanda_id})
        donor = await fx.person(f"DonanteR{tag}")

        # La pastora: solo lectura en la colecta; sí ve aportes por persona.
        roles = (await pastora.get("/api/finance/my-roles")).json()
        assert roles == {"read": True, "manage": False, "record": False, "verify": False, "treasury": False, "donors": True, "pastoral_read_only": True}
        # Wanda sin roles asignados: consulta, pero no registra ni ve aportes por persona.
        roles = (await wanda.get("/api/finance/my-roles")).json()
        assert roles["read"] and not (roles["record"] or roles["verify"] or roles["treasury"] or roles["donors"])
        assert (await wanda.get(f"/api/finance/contributors/{donor}")).status_code == 403

        # Solo la pastora (o el dueño) asigna roles: el coordinador general no puede.
        body = {"access_level": "lider", "is_active": True, "privilege_groups": ["finance"], "capabilities": ["finance.read", "finance.manage", *FLOW]}
        await db.users.update_one({"_id": wanda_user["_id"]}, {"$set": {"parent_user_id": str((await db.users.find_one({"person_id": {"$in": fx.person_ids}, "access_level": "coordinador_general"}))["_id"])}})
        assert (await coord.put(f"/api/core/governance/users/{wanda_user['_id']}/access", json=body)).status_code == 403
        granted = await pastora.put(f"/api/core/governance/users/{wanda_user['_id']}/access", json=body)
        assert granted.status_code == 200, granted.text
        assert set(FLOW) <= set(granted.json()["capabilities"])

        # Sin el grupo Finanzas los roles no sirven aunque estén guardados.
        from finance_engine import can_see_donors, has_finance_role
        assert not has_finance_role({"user_id": "x", "rol": "lider", "privilege_groups": [], "capabilities": FLOW}, "finance.collection.record")
        assert not can_see_donors({"user_id": "x", "rol": "lider", "privilege_groups": [], "capabilities": FLOW})

        # Con «Ver aportes por persona» asignado: ve el detalle y la consulta queda registrada.
        from httpx import ASGITransport, AsyncClient
        from tests.test_pastoral_front_group_5c import PASSWORD
        client = AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test")
        fx.clients.append(client)
        login = await client.post("/api/auth/login", json={"email": wanda_user["email"], "password": PASSWORD})
        client.headers.update({"Authorization": f"Bearer {login.json()['token']}"})
        roles = (await client.get("/api/finance/my-roles")).json()
        assert roles["record"] and roles["verify"] and roles["treasury"] and roles["donors"] and not roles["pastoral_read_only"]
        before = await db.finance_audit_events.count_documents({"action": "donor_data_viewed", "entity_id": donor})
        assert (await client.get(f"/api/finance/contributors/{donor}")).status_code == 200
        assert await db.finance_audit_events.count_documents({"action": "donor_data_viewed", "entity_id": donor}) == before + 1
        from core_profile import _can_see_donors  # Perfil 360 · Finanzas usa la misma regla
        assert _can_see_donors({**(await db.users.find_one({"_id": wanda_user["_id"]})), "user_id": str(wanda_user["_id"])}) is True
    finally:
        await db.finance_audit_events.delete_many({"action": "donor_data_viewed", "entity_id": {"$in": fx.person_ids}})
        await fx.cleanup()
