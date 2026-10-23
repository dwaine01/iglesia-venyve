"""Limpia la data creada por seed_etapa3_ui.py y restaura existencias de Central."""
import asyncio, json, os, sys
sys.path.insert(0, os.path.dirname(__file__)); sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import server  # noqa: E402
from test_etapa3_invasion_consolidation_library import cleanup, set_central  # noqa: E402


async def main():
    s = json.load(open("/tmp/etapa3_seed.json"))
    await server.db.front_groups.delete_one({"front_group_id": s["gid"]})
    await server.db.front_group_assignments.delete_many({"front_group_id": s["gid"]})
    await server.db.library_movements.delete_many({"campaign_id": s["campaign_id"]})
    await cleanup()
    for book_id, qty in s["saved_central"].items():
        await set_central(book_id, qty)
    print("cleanup ok")

asyncio.run(main())
