"""API del Mega-Bloque F — Cuidado Pastoral."""
from datetime import datetime
from typing import Optional
import re
from uuid import uuid4

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, status

from access_control import CARE_AUDIT_READ, CARE_MANAGE, has_capability
from care_alerts import evaluate_care_alerts
from care_crypto import vault_configured
from care_models import (
    CareAlertAction, CareAssignmentCreate, CareCaseCreate, CareCaseResponse,
    CareCaseUpdate, CareContactCreate, CareEntityResponse, CareEscalation,
    CareListResponse, CareNoteAddendum, CareNoteCreate, CareTransition,
    Op72Create, Op72LifecycleAction, Op72Response, VisitComplete, VisitCreate,
    VisitResponse,
)
from care_service import (
    ACTIVE_CASE_STATUSES, add_contact, assign_case, case_accessible, complete_visit,
    create_case_record, create_note, create_op72, create_visit, enrich_case,
    escalate_case, has_care_entry, is_care_authority, list_notes, load_case,
    now_utc, pause_op72, person_summary, reactivate_op72, record_audit, serialize,
    transition_case, visible_case_query, visit_detail,
)
from server import db, get_current_user


router = APIRouter(prefix="/api/care", tags=["pastoral-care"])


def require_care(current_user: dict = Depends(get_current_user)) -> dict:
    if not has_care_entry(current_user):
        raise HTTPException(status_code=403, detail="Acceso pastoral restringido")
    return current_user


def require_manage(current_user: dict = Depends(get_current_user)) -> dict:
    if not is_care_authority(current_user) or not has_capability(current_user, CARE_MANAGE):
        raise HTTPException(status_code=403, detail="Gestión pastoral restringida")
    return current_user


async def scoped_case_ids(current_user: dict) -> list[str] | None:
    if is_care_authority(current_user):
        return None
    return await db.pastoral_case_assignments.distinct("case_id", {"assignee_person_id": current_user.get("person_id"), "active": True})


@router.get("/dashboard", response_model=CareEntityResponse)
async def dashboard(current_user: dict = Depends(require_care)):
    await evaluate_care_alerts(db)
    query = await visible_case_query(db, current_user)
    cases = await db.pastoral_cases.find(query, {"_id": 0}).sort("updated_at", -1).to_list(10000)
    case_ids = [item["case_id"] for item in cases]
    alerts = await db.care_alerts.find({"case_id": {"$in": case_ids}, "status": {"$in": ["open", "acknowledged"]}}, {"_id": 0}).sort([("severity", 1), ("due_at", 1)]).limit(20).to_list(20) if case_ids else []
    op72_items = await db.op72_records.find({"case_id": {"$in": case_ids}}, {"_id": 0}).sort("contact_deadline_at", 1).limit(20).to_list(20) if case_ids else []
    visit_query = {"status": {"$in": ["scheduled", "in_progress"]}}
    if not is_care_authority(current_user): visit_query["visitor_person_ids"] = current_user.get("person_id")
    visits = await db.pastoral_visitations.find(visit_query, {"_id": 0}).sort("scheduled_at", 1).limit(12).to_list(12)
    metrics = {
        "active_cases": sum(item.get("status") in ACTIVE_CASE_STATUSES for item in cases),
        "urgent_cases": sum(item.get("status") in ACTIVE_CASE_STATUSES and item.get("priority") == "urgent" for item in cases),
        "escalated_cases": sum(item.get("status") == "escalated" for item in cases),
        "open_alerts": len(alerts),
        "op72_active": sum(item.get("status") == "active" for item in op72_items),
        "op72_paused": sum(item.get("status") == "paused" for item in op72_items),
        "upcoming_visits": len(visits),
    }
    return {"metrics": metrics, "alerts": serialize(alerts), "op72": serialize(op72_items), "visits": serialize(visits), "recent_cases": [await enrich_case(db, item, current_user) for item in cases[:8]], "permissions": {"manage": is_care_authority(current_user), "vault_configured": vault_configured()}}


@router.get("/catalog", response_model=CareEntityResponse)
async def catalog(current_user: dict = Depends(require_care)):
    users = await db.users.find({"person_id": {"$exists": True}, "is_active": {"$ne": False}, "rol": {"$in": ["pastor", "lider"]}}, {"_id": 0, "person_id": 1, "nombre": 1, "rol": 1, "role": 1, "access_level": 1, "capabilities": 1, "access_scope": 1}).sort("nombre", 1).to_list(2000)
    assignees = [{"person_id": item["person_id"], "name": item.get("nombre") or "Responsable", "role": item.get("access_level") or item.get("rol"), "authority": is_care_authority(item)} for item in users]
    return {"assignees": assignees, "authorities": [item for item in assignees if item["authority"]], "permissions": {"manage": is_care_authority(current_user), "audit": is_care_authority(current_user) and has_capability(current_user, CARE_AUDIT_READ), "vault_configured": vault_configured()}}


@router.get("/people/search", response_model=CareListResponse)
async def search_people(q: str = Query(min_length=2, max_length=100), current_user: dict = Depends(require_care)):
    pattern = re.escape(q.strip()); normalized = " ".join(q.strip().lower().split())
    people = await db.persons.find({"is_archived": {"$ne": True}, "$or": [{"search_key": {"$regex": re.escape(normalized)}}, {"nombre": {"$regex": pattern, "$options": "i"}}, {"apellido": {"$regex": pattern, "$options": "i"}}, {"person_number": {"$regex": pattern, "$options": "i"}}]}, {"_id": 1, "nombre": 1, "apellido": 1, "person_number": 1}).sort([("apellido", 1), ("nombre", 1)]).limit(25).to_list(25)
    items = [{"person_id": str(item["_id"]), "name": f"{item.get('nombre', '')} {item.get('apellido', '')}".strip(), "person_number": item.get("person_number"), "profile_path": f"/personas/{item['_id']}"} for item in people]
    return {"items": items, "total": len(items)}


@router.get("/households/by-person/{person_id}", response_model=CareEntityResponse)
async def household_by_person(person_id: str, current_user: dict = Depends(require_care)):
    membership = await db.household_memberships.find_one({"person_id": person_id}, {"_id": 0})
    if not membership: return {"household": None, "members": []}
    household = await db.households.find_one({"_id": membership["household_id"]}, {"_id": 0})
    member_ids = await db.household_memberships.distinct("person_id", {"household_id": membership["household_id"]})
    household_response = serialize(household) if household else None
    if household_response is not None: household_response["household_id"] = membership["household_id"]
    return {"household": household_response, "members": [await person_summary(db, item) for item in member_ids]}


@router.get("/cases", response_model=CareListResponse)
async def list_cases(case_status: Optional[str] = Query(default=None, alias="status"), priority: Optional[str] = None, person_id: Optional[str] = None, current_user: dict = Depends(require_care)):
    base = {}
    if case_status: base["status"] = case_status
    if priority: base["priority"] = priority
    if person_id: base["person_id"] = person_id
    query = await visible_case_query(db, current_user, base)
    docs = await db.pastoral_cases.find(query, {"_id": 0}).sort([("priority", -1), ("updated_at", -1)]).to_list(10000)
    return {"items": [await enrich_case(db, item, current_user) for item in docs], "total": len(docs)}


@router.post("/cases", response_model=CareCaseResponse, status_code=status.HTTP_201_CREATED)
async def create_case(payload: CareCaseCreate, current_user: dict = Depends(require_manage)):
    if payload.case_type == "first_conversion":
        raise HTTPException(status_code=409, detail="La primera conversión se registra exclusivamente desde Operación 72")
    return await create_case_record(db, payload.model_dump(), current_user)


@router.get("/cases/{case_id}", response_model=CareCaseResponse)
async def get_case(case_id: str, current_user: dict = Depends(require_care)):
    case = await load_case(db, case_id, current_user)
    result = await enrich_case(db, case, current_user)
    result["contacts"] = serialize(await db.pastoral_contact_attempts.find({"case_id": case_id}, {"_id": 0}).sort("occurred_at", -1).to_list(1000))
    result["alerts"] = serialize(await db.care_alerts.find({"case_id": case_id, "status": {"$in": ["open", "acknowledged"]}}, {"_id": 0}).sort("due_at", 1).to_list(100))
    return result


@router.patch("/cases/{case_id}", response_model=CareCaseResponse)
async def update_case(case_id: str, payload: CareCaseUpdate, current_user: dict = Depends(require_care)):
    case = await load_case(db, case_id, current_user, write=True); updates = payload.model_dump(exclude_unset=True)
    if not updates: return await enrich_case(db, case, current_user)
    updates.update({"updated_at": now_utc(), "updated_by_user_id": current_user["user_id"]})
    await db.pastoral_cases.update_one({"case_id": case_id}, {"$set": updates, "$inc": {"version": 1}})
    await record_audit(db, current_user, "case_updated", "pastoral_case", case_id, {"fields": sorted(updates.keys() - {"updated_at", "updated_by_user_id"})})
    await evaluate_care_alerts(db)
    return await enrich_case(db, await db.pastoral_cases.find_one({"case_id": case_id}, {"_id": 0}), current_user)


@router.post("/cases/{case_id}/transition", response_model=CareCaseResponse)
async def change_case_status(case_id: str, payload: CareTransition, current_user: dict = Depends(require_care)):
    result = await transition_case(db, await load_case(db, case_id, current_user, write=True), payload.status, payload.reason, current_user)
    await evaluate_care_alerts(db); return result


@router.post("/cases/{case_id}/assignments", response_model=CareEntityResponse, status_code=status.HTTP_201_CREATED)
async def create_assignment(case_id: str, payload: CareAssignmentCreate, current_user: dict = Depends(require_manage)):
    assignment = await assign_case(db, await load_case(db, case_id, current_user), payload.model_dump(), current_user)
    await evaluate_care_alerts(db); return assignment


@router.post("/cases/{case_id}/contacts", response_model=CareEntityResponse, status_code=status.HTTP_201_CREATED)
async def create_contact(case_id: str, payload: CareContactCreate, current_user: dict = Depends(require_care)):
    result = await add_contact(db, await load_case(db, case_id, current_user, write=True), payload.model_dump(), current_user)
    await evaluate_care_alerts(db); return result


@router.post("/cases/{case_id}/escalate", response_model=CareCaseResponse)
async def escalate(case_id: str, payload: CareEscalation, current_user: dict = Depends(require_care)):
    case = await load_case(db, case_id, current_user, write=True)
    result = await escalate_case(db, case, payload.authority_person_id, payload.reason, current_user)
    await evaluate_care_alerts(db); return result


@router.get("/cases/{case_id}/notes", response_model=CareListResponse)
async def get_notes(case_id: str, current_user: dict = Depends(require_care)):
    notes = await list_notes(db, await load_case(db, case_id, current_user), current_user)
    return {"items": notes, "total": len(notes)}


@router.post("/cases/{case_id}/notes", response_model=CareEntityResponse, status_code=status.HTTP_201_CREATED)
async def add_note(case_id: str, payload: CareNoteCreate, current_user: dict = Depends(require_care)):
    return await create_note(db, await load_case(db, case_id, current_user), payload.content, payload.visibility, current_user)


@router.post("/cases/{case_id}/notes/{note_id}/addendum", response_model=CareEntityResponse, status_code=status.HTTP_201_CREATED)
async def add_note_addendum(case_id: str, note_id: str, payload: CareNoteAddendum, current_user: dict = Depends(require_care)):
    case = await load_case(db, case_id, current_user)
    parent = await db.pastoral_case_notes.find_one({"note_id": note_id, "case_id": case_id}, {"_id": 0, "visibility": 1})
    if not parent: raise HTTPException(status_code=404, detail="Nota original no encontrada")
    return await create_note(db, case, payload.content, parent["visibility"], current_user, note_id)


@router.get("/op72", response_model=CareListResponse)
async def list_op72(op_status: Optional[str] = Query(default=None, alias="status"), current_user: dict = Depends(require_care)):
    ids = await scoped_case_ids(current_user); query = {}
    if ids is not None: query["case_id"] = {"$in": ids}
    if op_status: query["status"] = op_status
    docs = await db.op72_records.find(query, {"_id": 0}).sort("first_conversion_at", -1).to_list(10000)
    items = []
    for doc in docs:
        doc["person"] = await person_summary(db, doc["person_id"])
        doc["has_primary_assignment"] = bool(await db.pastoral_case_assignments.find_one({"case_id": doc["case_id"], "assignment_role": "primary", "active": True}, {"_id": 1}))
        items.append(serialize(doc))
    return {"items": items, "total": len(items)}


@router.post("/op72", response_model=CareEntityResponse, status_code=status.HTTP_201_CREATED)
async def register_op72(payload: Op72Create, current_user: dict = Depends(require_manage)):
    item, created = await create_op72(db, payload.model_dump(), current_user)
    await evaluate_care_alerts(db); return {"created": created, "record": item}


@router.get("/op72/{op72_id}", response_model=Op72Response)
async def get_op72(op72_id: str, current_user: dict = Depends(require_care)):
    item = await db.op72_records.find_one({"op72_id": op72_id}, {"_id": 0})
    if not item: raise HTTPException(status_code=404, detail="Operación 72 no encontrada")
    await load_case(db, item["case_id"], current_user)
    item["person"] = await person_summary(db, item["person_id"])
    item["case"] = await enrich_case(db, await db.pastoral_cases.find_one({"case_id": item["case_id"]}, {"_id": 0}), current_user)
    return serialize(item)


@router.post("/op72/{op72_id}/pause", response_model=Op72Response)
async def pause_operation(op72_id: str, payload: Op72LifecycleAction, current_user: dict = Depends(require_manage)):
    item = await db.op72_records.find_one({"op72_id": op72_id}, {"_id": 0})
    if not item: raise HTTPException(status_code=404, detail="Operación 72 no encontrada")
    return await pause_op72(db, item, payload.reason, current_user)


@router.post("/op72/{op72_id}/reactivate", response_model=CareEntityResponse)
async def reactivate_operation(op72_id: str, payload: Op72LifecycleAction, current_user: dict = Depends(require_manage)):
    item = await db.op72_records.find_one({"op72_id": op72_id}, {"_id": 0})
    if not item: raise HTTPException(status_code=404, detail="Operación 72 no encontrada")
    result = await reactivate_op72(db, item, payload.reason, current_user)
    await evaluate_care_alerts(db); return result


@router.get("/visitations", response_model=CareListResponse)
async def list_visitations(visit_status: Optional[str] = Query(default=None, alias="status"), current_user: dict = Depends(require_care)):
    query = {}
    if visit_status: query["status"] = visit_status
    if not is_care_authority(current_user): query["visitor_person_ids"] = current_user.get("person_id")
    docs = await db.pastoral_visitations.find(query, {"_id": 0}).sort("scheduled_at", -1).to_list(10000)
    return {"items": [await visit_detail(db, item["visit_id"], current_user) for item in docs], "total": len(docs)}


@router.post("/visitations", response_model=VisitResponse, status_code=status.HTTP_201_CREATED)
async def schedule_visitation(payload: VisitCreate, current_user: dict = Depends(require_manage)):
    return await create_visit(db, payload.model_dump(), current_user)


@router.get("/visitations/{visit_id}", response_model=VisitResponse)
async def get_visitation(visit_id: str, current_user: dict = Depends(require_care)):
    return await visit_detail(db, visit_id, current_user)


@router.post("/visitations/{visit_id}/start", response_model=VisitResponse)
async def start_visitation(visit_id: str, current_user: dict = Depends(require_care)):
    visit = await visit_detail(db, visit_id, current_user)
    if visit["status"] == "scheduled":
        await db.pastoral_visitations.update_one({"visit_id": visit_id}, {"$set": {"status": "in_progress", "started_at": now_utc(), "updated_at": now_utc()}})
        await record_audit(db, current_user, "visitation_started", "pastoral_visitation", visit_id)
    return await visit_detail(db, visit_id, current_user)


@router.post("/visitations/{visit_id}/complete", response_model=VisitResponse)
async def close_visitation(visit_id: str, payload: VisitComplete, current_user: dict = Depends(require_care)):
    visit = await visit_detail(db, visit_id, current_user)
    if payload.confidential_summary and not is_care_authority(current_user):
        raise HTTPException(status_code=403, detail="El resumen de bóveda requiere autoridad pastoral")
    result = await complete_visit(db, visit, payload.model_dump(), current_user)
    await evaluate_care_alerts(db); return result


@router.get("/alerts", response_model=CareListResponse)
async def list_alerts(alert_status: str = Query(default="open", alias="status"), current_user: dict = Depends(require_care)):
    await evaluate_care_alerts(db); ids = await scoped_case_ids(current_user); query = {"status": alert_status}
    if ids is not None: query["case_id"] = {"$in": ids}
    docs = await db.care_alerts.find(query, {"_id": 0}).sort([("severity", 1), ("due_at", 1)]).to_list(10000)
    return {"items": serialize(docs), "total": len(docs)}


@router.post("/alerts/{alert_id}", response_model=CareEntityResponse)
async def handle_alert(alert_id: str, payload: CareAlertAction, current_user: dict = Depends(require_care)):
    alert = await db.care_alerts.find_one({"alert_id": alert_id}, {"_id": 0})
    if not alert: raise HTTPException(status_code=404, detail="Alerta no encontrada")
    await load_case(db, alert["case_id"], current_user, write=True)
    now = now_utc(); updates = {"status": payload.status, "resolution": payload.resolution, "handled_by_user_id": current_user["user_id"], "updated_at": now}
    if payload.status == "resolved": updates["resolved_at"] = now
    else: updates["acknowledged_at"] = now
    await db.care_alerts.update_one({"alert_id": alert_id}, {"$set": updates})
    await record_audit(db, current_user, "care_alert_updated", "care_alert", alert_id, {"status": payload.status})
    return serialize(await db.care_alerts.find_one({"alert_id": alert_id}, {"_id": 0}))


@router.get("/audit", response_model=CareListResponse)
async def audit_log(limit: int = Query(default=200, ge=1, le=1000), current_user: dict = Depends(require_manage)):
    if not has_capability(current_user, CARE_AUDIT_READ): raise HTTPException(status_code=403, detail="Auditoría pastoral restringida")
    docs = await db.care_audit_events.find({}, {"_id": 0}).sort("occurred_at", -1).limit(limit).to_list(limit)
    return {"items": serialize(docs), "total": len(docs)}


@router.get("/migrations/legacy/dry-run", response_model=CareEntityResponse)
async def legacy_migration_dry_run(current_user: dict = Depends(require_manage)):
    legacy_notes = await db.person_notes.count_documents({"categoria": "pastoral"})
    historical_conversions = await db.cell_meetings.aggregate([{"$project": {"count": {"$size": {"$ifNull": ["$conversion_person_ids", []]}}}}, {"$group": {"_id": None, "total": {"$sum": "$count"}}}]).to_list(1)
    return {"dry_run": True, "writes_performed": False, "legacy_pastoral_notes": legacy_notes, "historical_cell_conversion_references": historical_conversions[0]["total"] if historical_conversions else 0, "message": "No se migró ningún dato. La ejecución permanece bloqueada hasta aprobación posterior a la revisión en producción."}
