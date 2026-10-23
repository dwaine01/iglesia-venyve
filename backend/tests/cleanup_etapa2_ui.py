"""Limpieza de datos QA de Etapa 2 (seed_etapa2_ui.py + pruebas de verificación).

Borra campañas QA por nombre, grupos 'QA Rama/SubRama Etapa2 UI' y luego corre
qa_demo_cleanup; recrea las cuentas canónicas coreqa.* al final.
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import server  # noqa: E402
from qa_demo_cleanup import delete_qa_artifacts, qa_preview  # noqa: E402
from conftest import ensure_qa_accounts  # noqa: E402


async def main():
    db = server.db
    camp = await db.outreach_campaigns.find({"name": {"$regex": r"^QA Invasi"}}, {"_id": 0, "campaign_id": 1}).to_list(1000)
    cids = [c["campaign_id"] for c in camp]
    if cids:
        for coll in ("outreach_participations", "outreach_households", "outreach_visits", "outreach_visit_events"):
            await db[coll].delete_many({"campaign_id": {"$in": cids}})
        await db.outreach_campaigns.delete_many({"campaign_id": {"$in": cids}})
    groups = await db.front_groups.find({"name": {"$in": ["QA Rama Etapa2 UI", "QA SubRama Etapa2 UI"]}}, {"_id": 0, "front_group_id": 1}).to_list(100)
    gids = [g["front_group_id"] for g in groups]
    if gids:
        await db.front_group_assignments.delete_many({"front_group_id": {"$in": gids}})
        await db.front_groups.delete_many({"front_group_id": {"$in": gids}})
    preview = await qa_preview(db)
    result = await delete_qa_artifacts(db, preview["preview_token"], preview["confirmation_phrase"])
    print({"campaigns": len(cids), "groups": len(gids), "qa_cleanup_deleted": result["deleted_documents"]})


if __name__ == "__main__":
    asyncio.run(main())
    ensure_qa_accounts()
