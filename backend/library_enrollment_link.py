"""R2 · El libro queda unido al expediente de Consolidación.

- Al entregar un libro a una persona que tiene un expediente de Consolidación abierto, la entrega guarda ese
  `enrollment_id` (o el de la visita, si la visita ya abrió uno).
- Si el libro se entregó ANTES de abrir el expediente (en la puerta, antes de aceptar), al abrirlo se unen
  las entregas de esa persona que no tienen expediente y son posteriores al cierre de su expediente anterior.
- Solo agrega un campo; nada se borra. Cada enlace dice quién lo puso (`enrollment_link_source`), así se
  puede deshacer."""
from datetime import datetime
from typing import Optional

DELIVERY_TYPES = ["DELIVERY", "LOAN", "DELIVERY_PENDING"]
OPEN = ["planned", "active", "paused"]


async def enrollment_for_delivery(db, person_id: Optional[str], visit_id: Optional[str] = None) -> Optional[str]:
    if visit_id:
        visit = await db.outreach_visits.find_one({"visit_id": visit_id}, {"_id": 0, "enrollment_id": 1})
        if visit and visit.get("enrollment_id"):
            return visit["enrollment_id"]
    if not person_id:
        return None
    enrollment = await db.process_enrollments.find_one({"process_key": "consolidation", "person_id": person_id, "status": {"$in": OPEN}},
                                                       {"_id": 0, "enrollment_id": 1}, sort=[("created_at", -1)])
    return (enrollment or {}).get("enrollment_id")


def _as_dt(value):
    return value if isinstance(value, datetime) else None


async def link_prior_deliveries(db, enrollment: dict) -> int:
    """Al abrir un expediente: une las entregas de la persona que aún no tienen expediente."""
    if enrollment.get("process_key") != "consolidation" or not enrollment.get("person_id"):
        return 0
    previous = await db.process_enrollments.find({"process_key": "consolidation", "person_id": enrollment["person_id"], "enrollment_id": {"$ne": enrollment["enrollment_id"]}},
                                                 {"_id": 0, "completed_at": 1, "updated_at": 1, "created_at": 1}).to_list(100)
    ends = [_as_dt(item.get("completed_at")) or _as_dt(item.get("updated_at")) or _as_dt(item.get("created_at")) for item in previous]
    ends = [value for value in ends if value]
    query = {"person_id": enrollment["person_id"], "movement_type": {"$in": DELIVERY_TYPES}, "enrollment_id": None, "is_reversal": {"$ne": True}}
    if ends:
        query["occurred_at"] = {"$gt": max(ends)}
    result = await db.library_movements.update_many(query, {"$set": {"enrollment_id": enrollment["enrollment_id"], "enrollment_link_source": "enrollment_opened"}})
    return result.modified_count


async def unlinked_history_count(db) -> dict:
    """Solo lectura, para la propuesta al dueño: entregas a personas que siguen sin expediente unido."""
    total = await db.library_movements.count_documents({"movement_type": {"$in": DELIVERY_TYPES}, "is_reversal": {"$ne": True}, "person_id": {"$nin": [None, ""]}})
    unlinked = await db.library_movements.count_documents({"movement_type": {"$in": DELIVERY_TYPES}, "is_reversal": {"$ne": True}, "person_id": {"$nin": [None, ""]}, "enrollment_id": None})
    return {"deliveries_to_people": total, "without_enrollment": unlinked}
