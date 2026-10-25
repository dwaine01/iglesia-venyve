"""Los códigos cortos se crean una sola vez aunque lleguen varios pedidos a la vez
(antes, dos pedidos simultáneos podían dejar códigos distintos y la tableta quedaba
con uno que ya no valía). También para un documento anterior sin código."""
import asyncio

import pytest

from tests.test_pastoral_front_group_5c import server  # noqa: I001 — server primero
import visitor_registry  # noqa: E402

db = server.db


@pytest.mark.asyncio
async def test_link_codes_are_created_once_under_concurrency():
    saved = await db.app_settings.find_one({"_id": visitor_registry.LINKS_ID})
    try:
        await db.app_settings.delete_one({"_id": visitor_registry.LINKS_ID})
        results = await asyncio.gather(*(visitor_registry.load_links() for _ in range(10)))
        stored = await db.app_settings.find_one({"_id": visitor_registry.LINKS_ID})
        for kind in ("tablet", "screen"):
            assert {item[kind]["code"] for item in results} == {stored[kind]["code"]}
            assert {item[kind]["token"] for item in results} == {stored[kind]["token"]}
        # Documento de la versión anterior (solo token largo): se le agrega el código una vez y el token se conserva.
        await db.app_settings.replace_one({"_id": visitor_registry.LINKS_ID}, {"_id": visitor_registry.LINKS_ID, "tablet": {"token": "t" * 43}, "screen": {"token": "s" * 43}})
        results = await asyncio.gather(*(visitor_registry.load_links() for _ in range(10)))
        stored = await db.app_settings.find_one({"_id": visitor_registry.LINKS_ID})
        assert stored["tablet"]["token"] == "t" * 43 and stored["screen"]["token"] == "s" * 43
        assert {item["tablet"]["code"] for item in results} == {stored["tablet"]["code"]} and stored["tablet"]["code"] != stored["screen"]["code"]
    finally:
        if saved:
            await db.app_settings.replace_one({"_id": visitor_registry.LINKS_ID}, saved, upsert=True)
        else:
            await db.app_settings.delete_one({"_id": visitor_registry.LINKS_ID})
