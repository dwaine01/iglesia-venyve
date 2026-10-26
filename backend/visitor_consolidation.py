"""Tableta → Consolidación (auditoría 10/10).

Desde el seguimiento de visitantes, «Pasar a Consolidación» abre (o reutiliza) el expediente de la
persona con el mentor asignado al seguimiento y cierra el seguimiento. Así el visitante no queda en
dos listas ni se pierde entre la tableta y Consolidación. Lo usa quien administra el seguimiento o
el mentor asignado."""
from fastapi import APIRouter, Depends, HTTPException

from access_control import VISITORS_FOLLOWUP_MANAGE
from server import db, get_current_user

router = APIRouter(prefix="/api/visitors", tags=["visitors"])


@router.post("/registrations/{registration_id}/to-consolidation", response_model=dict)
async def to_consolidation(registration_id: str, current_user: dict = Depends(get_current_user)):
    from consolidation_service import assign_mentor, configure_entry_stages
    from mentorship_outreach import is_active_mentor
    from process_engine import create_enrollment, now_utc, record_event
    from visitor_registry import audit, can, followup_reply, is_assignee, load_registration
    doc = await load_registration(registration_id)
    if not (can(current_user, VISITORS_FOLLOWUP_MANAGE) or is_assignee(doc, current_user)):
        raise HTTPException(status_code=403, detail="Solo quien administra el seguimiento o la persona asignada")
    person_id = doc.get("person_id")
    if not person_id:
        raise HTTPException(status_code=422, detail="Primero vincule este registro a su Persona 360 (revise la coincidencia)")
    mentor_id = (doc.get("followup") or {}).get("assigned_person_id")
    if not mentor_id or not await is_active_mentor(mentor_id):
        raise HTTPException(status_code=422, detail="Asigne el seguimiento a un mentor con insignia activa antes de pasarlo a Consolidación")
    if await db.process_enrollments.find_one({"process_key": "consolidation", "person_id": person_id, "status": "completed"}, {"_id": 1}) \
            and not await db.process_enrollments.find_one({"process_key": "consolidation", "person_id": person_id, "status": {"$in": ["planned", "active", "paused"]}}, {"_id": 1}):
        raise HTTPException(status_code=409, detail="Esta persona ya terminó Consolidación")
    enrollment, created = await create_enrollment(db, "consolidation", person_id, mentor_id, current_user["user_id"], status="active",
                                                  next_action="Dar seguimiento al visitante", source="visitor_registry", source_id=registration_id)
    if created:
        await configure_entry_stages(db, enrollment, "visitor_followup", current_user["user_id"], mentor_person_id=mentor_id)
        enrollment = await db.process_enrollments.find_one({"enrollment_id": enrollment["enrollment_id"]}, {"_id": 0})
    if not enrollment.get("mentor_person_id"):
        await assign_mentor(db, enrollment, mentor_id, current_user["user_id"], f"Seguimiento del visitante {doc.get('visitor_number')}")
    await record_event(db, enrollment, current_user["user_id"], "visitor_followup_linked", "Viene del registro de visitantes", doc.get("visitor_number") or registration_id)
    await db.visitor_registrations.update_one({"registration_id": registration_id}, {"$set": {
        "followup.status": "done", "followup.enrollment_id": enrollment["enrollment_id"], "followup.closed_reason": "Pasó a Consolidación", "followup.updated_at": now_utc()}})
    await audit("followup_to_consolidation", current_user["user_id"], {"registration_id": registration_id, "enrollment_id": enrollment["enrollment_id"], "reused": not created})
    return {**await followup_reply(registration_id, current_user), "enrollment_id": enrollment["enrollment_id"], "reused_enrollment": not created}
