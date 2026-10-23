# T1 cleanup for seed_t1_add_mentors.py data (+ standard qa_demo_cleanup), then recreate coreqa accounts.
import asyncio, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
from motor.motor_asyncio import AsyncIOMotorClient
from qa_demo_cleanup import delete_qa_artifacts, qa_preview


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    cids = await db.outreach_campaigns.distinct("campaign_id", {"name": {"$regex": "^TEST_T1 "}})
    for coll in ("outreach_households", "outreach_visits", "outreach_participations"):
        await db[coll].delete_many({"campaign_id": {"$in": cids}})
    await db.outreach_campaigns.delete_many({"campaign_id": {"$in": cids}})
    await db.library_movements.delete_many({"qa_t1": True})
    gids = await db.front_groups.distinct("front_group_id", {"name": {"$regex": "^QA T1 "}})
    await db.front_group_assignments.delete_many({"front_group_id": {"$in": gids}})
    await db.front_groups.delete_many({"front_group_id": {"$in": gids}})
    preview = await qa_preview(db)
    await delete_qa_artifacts(db, preview["preview_token"], preview["confirmation_phrase"])
    print("cleaned campaigns", len(cids), "groups", len(gids))

asyncio.run(main())
from conftest import ensure_qa_accounts
ensure_qa_accounts()
print("coreqa accounts recreated")
