"""C9/E (Etapa 4): historial de borrados administrativos — quién, cuándo y
por qué se borró algo de forma total y permanente. Lee la MISMA colección
`admin_deletions` que ya usan front_groups.py y mentorship_outreach.py al
borrar; solo pastoral/coordinador general puede consultarla."""
from fastapi import APIRouter, Depends, HTTPException, Query

from access_control import is_general_coordinator, is_global_pastoral_authority
from process_engine import serialize
from server import db, get_current_user

router = APIRouter(prefix="/api/admin/audit", tags=["admin-audit"])


def require_pastoral(current_user: dict = Depends(get_current_user)) -> dict:
    if is_global_pastoral_authority(current_user) or is_general_coordinator(current_user):
        return current_user
    raise HTTPException(status_code=403, detail="Solo la pastora/pastor o un coordinador general puede ver el historial de borrados")


@router.get("/deletions", response_model=dict)
async def list_deletions(skip: int = Query(default=0, ge=0), limit: int = Query(default=50, ge=1, le=200), current_user: dict = Depends(require_pastoral)):
    total = await db.admin_deletions.count_documents({})
    items = await db.admin_deletions.find({}, {"_id": 0}).sort("deleted_at", -1).skip(skip).limit(limit).to_list(limit)
    return {"total": total, "items": serialize(items)}
