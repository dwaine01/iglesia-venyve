"""Entrega del trabajo de un líder o mentor antes de eliminar su cuenta, quitarle la insignia de mentor
o archivar su Perfil 360 (auditoría 5/10).

Antes se podía borrar la cuenta de alguien con discípulos en Consolidación, visitas y seguimientos de
tableta asignados, transferencias pendientes y libros en su poder: todo quedaba «huérfano» (asignado a
alguien que ya no existe). Ahora:

- `pending_work` lista lo que tiene (con nombres, para verlo antes de decidir).
- Si tiene algo, la acción exige elegir a quién pasarlo (`reassign_to_person_id`, un mentor activo).
- `hand_over` lo pasa todo, con historial y aviso al nuevo responsable. Nada se borra:
  quién hizo cada atención no cambia; solo cambia el responsable de lo que falta.
"""
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import HTTPException

from server import db

OPEN_FOLLOWUP = ["pending", "assigned", "in_progress"]
SAMPLE = 8  # nombres que se muestran por tipo en la vista previa


async def _account_ids(person_id: Optional[str], extra_user_ids: Optional[list[str]] = None) -> list[str]:
    ids = set(extra_user_ids or [])
    if person_id:
        ids |= {str(doc["_id"]) async for doc in db.users.find({"person_id": person_id}, {"_id": 1})}
    return sorted(ids)


async def _book_balances(user_ids: list[str]) -> list[dict]:
    """Libros que la caché de inventario tiene a nombre de esas cuentas (lo que se puede transferir)."""
    if not user_ids:
        return []
    rows = []
    async for doc in db.library_holdings.find({"holder_type": "user", "holder_id": {"$in": user_ids}, "quantity_on_hand": {"$gt": 0}},
                                              {"_id": 0, "book_id": 1, "holder_id": 1, "quantity_on_hand": 1, "reserved_qty": 1}):
        free = (doc.get("quantity_on_hand") or 0) - max(doc.get("reserved_qty") or 0, 0)
        if free > 0:
            rows.append({"book_id": doc["book_id"], "holder_id": doc["holder_id"], "quantity": free})
    titles = {doc["book_id"]: doc.get("name") async for doc in db.library_books.find({"book_id": {"$in": [row["book_id"] for row in rows]}}, {"_id": 0, "book_id": 1, "name": 1})}
    return [{**row, "title": titles.get(row["book_id"]) or "Libro"} for row in rows]


async def pending_work(person_id: Optional[str], extra_user_ids: Optional[list[str]] = None) -> dict:
    """Todo lo que quedaría sin responsable si esta persona deja de ser líder o mentor."""
    from my_work import pending_items
    from report_period import report_zone
    zone: ZoneInfo = await report_zone()
    items = await pending_items(person_id, None, zone) if person_id else []
    by_kind: dict[str, list[dict]] = {"person": [], "contact": [], "assigned_visit": [], "household": []}
    for item in items:
        by_kind.setdefault(item["kind"], []).append(item)
    followups = await db.visitor_registrations.find(
        {"followup.assigned_person_id": person_id, "followup.status": {"$in": OPEN_FOLLOWUP}, "status": {"$nin": ["discarded", "merged"]}},
        {"_id": 0, "registration_id": 1, "contact": 1, "person_snapshot": 1, "display_name": 1, "first_name": 1, "last_name": 1},
    ).to_list(500) if person_id else []
    transfers = await db.process_enrollments.find(
        {"transfer_request.status": "pending", "transfer_request.to_person_id": person_id}, {"_id": 0, "enrollment_id": 1, "person_id": 1},
    ).to_list(500) if person_id else []
    books = await _book_balances(await _account_ids(person_id, extra_user_ids))

    def names(rows: list[dict], key: str = "title") -> list[str]:
        return [row.get(key) or "Sin nombre" for row in rows[:SAMPLE]]

    followup_names = [" ".join(filter(None, [row.get("first_name"), row.get("last_name")])) or row.get("display_name") or "Visitante" for row in followups[:SAMPLE]]
    counts = {
        "disciples": len(by_kind["person"]), "contacts": len(by_kind["contact"]), "assigned_visits": len(by_kind["assigned_visit"]),
        "households": len(by_kind["household"]), "visitor_followups": len(followups), "transfers_pending": len(transfers),
        "books": sum(row["quantity"] for row in books),
    }
    return {
        "counts": counts, "total": sum(counts.values()), "blocking": sum(counts.values()) > 0,
        "samples": {"disciples": names(by_kind["person"]), "contacts": names(by_kind["contact"]), "assigned_visits": names(by_kind["assigned_visit"]),
                    "households": names(by_kind["household"]), "visitor_followups": followup_names, "books": [f"{row['title']} × {row['quantity']}" for row in books[:SAMPLE]]},
        "_items": items, "_followups": [row["registration_id"] for row in followups], "_transfers": [row["enrollment_id"] for row in transfers], "_books": books,
    }


def public(work: dict) -> dict:
    return {key: value for key, value in work.items() if not key.startswith("_")}


async def require_handover_target(person_id: Optional[str], target: Optional[str]) -> dict:
    """El nuevo responsable debe ser otra persona, mentor activo y con cuenta activa (recibe avisos y libros)."""
    from mentorship_outreach import is_active_mentor
    if not target:
        raise HTTPException(status_code=422, detail="Elija a quién pasar su trabajo")
    if target == person_id:
        raise HTTPException(status_code=422, detail="El nuevo responsable debe ser otra persona")
    if not await is_active_mentor(target):
        raise HTTPException(status_code=422, detail="El nuevo responsable debe ser un mentor activo")
    account = await db.users.find_one({"person_id": target, "is_active": {"$ne": False}}, {"_id": 1}, sort=[("created_at", -1)])
    if not account:
        raise HTTPException(status_code=422, detail="El nuevo responsable necesita una cuenta activa")
    return {"person_id": target, "user_id": str(account["_id"])}


def blocked(work: dict, action: str) -> HTTPException:
    return HTTPException(status_code=409, detail={
        "message": f"Antes de {action}, pase su trabajo a otro mentor: tiene pendientes que quedarían sin responsable.",
        "pending_work": public(work),
    })


async def hand_over(person_id: Optional[str], work: dict, target: dict, current_user: dict, reason: str) -> dict:
    """Pasa todo lo pendiente a `target` ({person_id, user_id}). Devuelve cuánto se movió de cada tipo."""
    from datetime import datetime, timezone
    from my_work import reassign_items
    now = datetime.now(timezone.utc)
    result = {"reassigned_items": 0, "visitor_followups": 0, "transfers": 0, "books_moved": 0}
    items = [{"kind": item["kind"], "id": item["id"]} for item in work["_items"]]
    for start in range(0, len(items), 200):
        result["reassigned_items"] += (await reassign_items(items[start:start + 200], target["person_id"], current_user, reason))["reassigned"]
    if work["_followups"]:
        entry = {"from_person_id": person_id, "to_person_id": target["person_id"], "by_user_id": current_user["user_id"], "at": now, "reason": reason}
        result["visitor_followups"] = (await db.visitor_registrations.update_many(
            {"registration_id": {"$in": work["_followups"]}},
            {"$set": {"followup.assigned_person_id": target["person_id"], "followup.assigned_at": now, "followup.assigned_by": current_user["user_id"]},
             "$push": {"followup.reassignments": entry}},
        )).modified_count
    if work["_transfers"]:
        result["transfers"] = (await db.process_enrollments.update_many(
            {"enrollment_id": {"$in": work["_transfers"]}, "transfer_request.status": "pending"},
            {"$set": {"transfer_request.to_person_id": target["person_id"], "transfer_request.redirected_at": now,
                      "transfer_request.redirected_from_person_id": person_id, "transfer_request.redirected_by_user_id": current_user["user_id"]}},
        )).modified_count
    if work["_books"]:
        from library_module import HolderInput, MovementInput, apply_movement
        for row in work["_books"]:
            await apply_movement(MovementInput(book_id=row["book_id"], movement_type="TRANSFER", quantity=row["quantity"],
                                               from_holder=HolderInput(type="user", id=row["holder_id"]), to_holder=HolderInput(type="user", id=target["user_id"]),
                                               notes=f"Entrega de trabajo: {reason}",
                                               idempotency_key=f"handover:{row['holder_id']}:{row['book_id']}:{now.isoformat()}"), current_user["user_id"])
            result["books_moved"] += row["quantity"]
    if work["_followups"] or work["_transfers"] or work["_books"]:
        from portal_notifications import notify_persons
        await notify_persons([target["person_id"]], "work_handover", "Recibiste trabajo de otro mentor",
                             f"Te pasaron seguimientos, transferencias o libros. Motivo: {reason}", "/mi-trabajo", {"type": "work_handover"})
    return result
