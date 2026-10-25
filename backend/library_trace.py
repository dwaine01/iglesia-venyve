"""L3 · Consulta y recorrido de los libros (lee la bitácora única de L1/L2).

- Resumen por MENTOR o por MATERIAL: recibidos, entregados, disponibles,
  sin conciliar, destinatario identificado / por completar y con seguimiento.
- Cada cifra se abre: destinatario, dirección y apartamento, material, fecha
  y estado de seguimiento (con acceso al perfil).
- Recorrido de un libro: Librería → mentor → vivienda/persona → seguimiento →
  Consolidación.
- Permisos (backend): el mentor ve SOLO lo suyo; Librería
  (`library.inventory.manage`, `library.catalog.manage`,
  `library.reports.read`), encargados de Consolidación
  (`consolidation.assign`), autoridad pastoral y coordinador general ven
  todo. Pedir lo de otro sin esos permisos = 403."""
from collections import defaultdict
from datetime import datetime
from typing import Literal, Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException

from access_control import CONSOLIDATION_ASSIGN, LIBRARY_REPORTS_READ, has_capability, is_general_coordinator, is_global_pastoral_authority
from library_ledger import PENDING_TYPE
from library_module import is_library_manager, serialize
from server import db, get_current_user

router = APIRouter(prefix="/api/library/ledger/trace", tags=["library-trace"])

DELIVERY_TYPES = ["DELIVERY", "LOAN", PENDING_TYPE]
METRICS = ("received", "delivered", "pending", "identified", "unidentified", "followup")


def sees_all(current_user: dict) -> bool:
    return (is_library_manager(current_user) or has_capability(current_user, LIBRARY_REPORTS_READ) or has_capability(current_user, CONSOLIDATION_ASSIGN)
            or is_global_pastoral_authority(current_user) or is_general_coordinator(current_user))


def scoped_user(current_user: dict, mentor_user_id: Optional[str]) -> Optional[str]:
    """El mentor solo consulta lo suyo; pedir a otro sin permiso = 403."""
    if sees_all(current_user):
        return mentor_user_id
    if mentor_user_id and mentor_user_id != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Solo puede consultar sus propios libros")
    return current_user["user_id"]


async def _movements(mentor_user_id: Optional[str], book_id: Optional[str], campaign_id: Optional[str]) -> list[dict]:
    match: dict = {"$or": [{"to_holder.type": "user"}, {"from_holder.type": "user"}], "movement_type": {"$nin": ["RESERVATION", "RESERVATION_RELEASE", "RECIPIENT_COMPLETION"]}}
    if mentor_user_id:
        match["$or"] = [{"to_holder.type": "user", "to_holder.id": mentor_user_id}, {"from_holder.type": "user", "from_holder.id": mentor_user_id}]
    if book_id:
        match["book_id"] = book_id
    if campaign_id:
        match["campaign_id"] = campaign_id
    return await db.library_movements.find(match, {"_id": 0}).sort("occurred_at", -1).to_list(50000)


async def _followup_info(movements: list[dict]) -> dict[str, dict]:
    """Seguimiento por entrega: visita (aceptó, próxima acción) y Consolidación."""
    visit_ids = list({item["visit_id"] for item in movements if item.get("visit_id")})
    visits = {doc["visit_id"]: doc async for doc in db.outreach_visits.find({"visit_id": {"$in": visit_ids}}, {"_id": 0, "visit_id": 1, "status": 1, "followup_accepted": 1, "next_action": 1, "next_action_at": 1,
                                                                                                              "followup_responsible_person_id": 1, "enrollment_id": 1, "contact_name": 1, "contact_phone": 1,
                                                                                                              "person_id": 1, "converted_person_id": 1})} if visit_ids else {}
    person_ids = list({item["person_id"] for item in movements if item.get("person_id")} | {visit.get("converted_person_id") or visit.get("person_id") for visit in visits.values() if visit.get("converted_person_id") or visit.get("person_id")})
    enrollments = {doc["person_id"]: doc async for doc in db.process_enrollments.find({"person_id": {"$in": person_ids}, "process_key": "consolidation", "status": {"$in": ["active", "paused", "planned", "completed"]}},
                                                                                         {"_id": 0, "person_id": 1, "enrollment_id": 1, "current_stage_key": 1, "status": 1})} if person_ids else {}
    out = {}
    for item in movements:
        visit = visits.get(item.get("visit_id")) or {}
        person_id = item.get("person_id") or visit.get("converted_person_id") or visit.get("person_id")
        enrollment = enrollments.get(person_id) if person_id else None
        accepted = bool(visit.get("followup_accepted") or visit.get("status") == "wants_followup" or visit.get("enrollment_id") or enrollment)
        out[item["movement_id"]] = {"accepted": accepted, "next_action": visit.get("next_action"), "next_action_at": visit.get("next_action_at"),
                                    "responsible_person_id": visit.get("followup_responsible_person_id"), "contact_name": visit.get("contact_name"),
                                    "person_id": person_id, "enrollment_id": (enrollment or {}).get("enrollment_id") or visit.get("enrollment_id"),
                                    "stage_key": (enrollment or {}).get("current_stage_key")}
    return out


async def _names(user_ids=(), person_ids=()) -> tuple[dict, dict]:
    users = {str(doc["_id"]): doc async for doc in db.users.find({"_id": {"$in": [ObjectId(item) for item in set(user_ids) if item and ObjectId.is_valid(item)]}}, {"nombre": 1, "person_id": 1})}
    pids = {doc.get("person_id") for doc in users.values() if doc.get("person_id")} | set(person_ids)
    persons = {str(doc["_id"]): " ".join(filter(None, [doc.get("nombre"), doc.get("apellido")])) or "Persona"
               async for doc in db.persons.find({"_id": {"$in": [ObjectId(item) for item in pids if item and ObjectId.is_valid(item)]}}, {"nombre": 1, "apellido": 1})}
    user_names = {key: persons.get(doc.get("person_id")) or doc.get("nombre") or "Cuenta" for key, doc in users.items()}
    return user_names, persons


def _bucket() -> dict:
    return {"received": 0, "delivered": 0, "returned": 0, "transferred_out": 0, "other_out": 0, "corrections": 0, "pending": 0, "identified": 0, "unidentified": 0, "followup": 0}


@router.get("/summary", response_model=dict)
async def trace_summary(group_by: Literal["mentor", "material"] = "mentor", mentor_user_id: Optional[str] = None, book_id: Optional[str] = None,
                        campaign_id: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    """Cifras por mentor o por material (con filtro de invasión). Ej.: Luis: 12 recibidos · 9 entregados · 3 disponibles."""
    mentor_user_id = scoped_user(current_user, mentor_user_id)
    movements = await _movements(mentor_user_id, book_id, campaign_id)
    deliveries = [item for item in movements if item["movement_type"] in DELIVERY_TYPES and (item.get("from_holder") or {}).get("type") == "user"]
    follow = await _followup_info(deliveries)
    rows: dict[str, dict] = defaultdict(_bucket)
    for item in movements:
        kind, quantity = item["movement_type"], item.get("quantity") or 0
        to_holder, from_holder = item.get("to_holder") or {}, item.get("from_holder") or {}
        for holder, sign in ((to_holder, 1), (from_holder, -1)):
            if holder.get("type") != "user" or (mentor_user_id and holder.get("id") != mentor_user_id):
                continue
            key = holder["id"] if group_by == "mentor" else (item.get("book_id") or f"label:{item.get('book_name')}")
            row = rows[key]
            if kind == PENDING_TYPE:
                if sign < 0:
                    row["pending"] += quantity
                    row["identified" if item.get("recipient_status") == "identified" else "unidentified"] += quantity
                    row["followup"] += quantity if follow.get(item["movement_id"], {}).get("accepted") else 0
                continue
            if item.get("counts_in_balance") is False:
                continue
            if item.get("is_reversal"):
                row["corrections"] += quantity * sign
            elif sign > 0:
                row["received"] += quantity
            elif kind in {"DELIVERY", "LOAN"}:
                row["delivered"] += quantity
                row["identified" if item.get("recipient_status") == "identified" or item.get("person_id") else "unidentified"] += quantity
                row["followup"] += quantity if follow.get(item["movement_id"], {}).get("accepted") else 0
            elif kind == "RETURN":
                row["returned"] += quantity
            elif kind == "TRANSFER":
                row["transferred_out"] += quantity
            else:
                row["other_out"] += quantity
    user_names, _ = await _names(user_ids=[key for key in rows] if group_by == "mentor" else [])
    books = {doc["book_id"]: doc for doc in await db.library_books.find({"book_id": {"$in": [key for key in rows if not key.startswith("label:")]}}, {"_id": 0, "book_id": 1, "name": 1, "sku": 1}).to_list(2000)} if group_by == "material" else {}
    # «Disponibles» = saldo REAL en mano según la bitácora (no depende del filtro de invasión,
    # porque una asignación puede no llevar invasión).
    from library_ledger import ledger_balances
    balances = await ledger_balances([mentor_user_id] if mentor_user_id else None)
    available_by: dict[str, int] = defaultdict(int)
    for (user_id, balance_book), balance in balances.items():
        if book_id and balance_book != book_id:
            continue
        available_by[user_id if group_by == "mentor" else balance_book] += balance["balance"]
    out = []
    for key, row in rows.items():
        available = available_by.get(key, 0)
        name = user_names.get(key) if group_by == "mentor" else (books.get(key, {}).get("name") or key.replace("label:", "") or "Libro sin cargar")
        out.append({"key": key, "name": name or "Cuenta", "sku": books.get(key, {}).get("sku") if group_by == "material" else None, **row, "available": available,
                    "delivered_total": row["delivered"] + row["pending"]})
    out.sort(key=lambda row: (-row["delivered_total"], row["name"]))
    totals = _bucket()
    for row in out:
        for field in totals:
            totals[field] += row[field]
    totals["available"] = sum(row["available"] for row in out)
    totals["delivered_total"] = totals["delivered"] + totals["pending"]
    return {"group_by": group_by, "scope": "all" if sees_all(current_user) and not mentor_user_id else "mine" if not sees_all(current_user) else "filtered", "rows": out, "totals": totals}


@router.get("/items", response_model=dict)
async def trace_items(metric: str = "delivered", mentor_user_id: Optional[str] = None, book_id: Optional[str] = None, campaign_id: Optional[str] = None,
                      offset: int = 0, limit: int = 100, current_user: dict = Depends(get_current_user)):
    """Lo que hay detrás de cada cifra: destinatario, dirección/apartamento, material y seguimiento."""
    if metric not in METRICS:
        raise HTTPException(status_code=404, detail="Indicador desconocido")
    mentor_user_id = scoped_user(current_user, mentor_user_id)
    if book_id and book_id.startswith("label:"):
        book_id = None
    movements = await _movements(mentor_user_id, book_id, campaign_id)
    if metric == "received":
        rows = [item for item in movements if (item.get("to_holder") or {}).get("type") == "user" and (not mentor_user_id or item["to_holder"].get("id") == mentor_user_id)
                and item["movement_type"] not in DELIVERY_TYPES and not item.get("is_reversal")]
    else:
        rows = [item for item in movements if item["movement_type"] in DELIVERY_TYPES and (item.get("from_holder") or {}).get("type") == "user"
                and (not mentor_user_id or item["from_holder"].get("id") == mentor_user_id)
                and (item["movement_type"] == PENDING_TYPE or item.get("counts_in_balance", True) is not False)]
    follow = await _followup_info(rows)
    if metric == "pending":
        rows = [item for item in rows if item["movement_type"] == PENDING_TYPE]
    elif metric == "delivered":
        rows = [item for item in rows if item["movement_type"] != PENDING_TYPE]
    elif metric == "identified":
        rows = [item for item in rows if item.get("recipient_status") == "identified" or item.get("person_id")]
    elif metric == "unidentified":
        rows = [item for item in rows if not (item.get("recipient_status") == "identified" or item.get("person_id"))]
    elif metric == "followup":
        rows = [item for item in rows if follow.get(item["movement_id"], {}).get("accepted")]
    total = len(rows)
    page = rows[offset:offset + max(1, min(limit, 500))]
    houses = {doc["household_id"]: doc async for doc in db.outreach_households.find({"household_id": {"$in": list({item["household_id"] for item in page if item.get("household_id")})}},
                                                                                    {"_id": 0, "household_id": 1, "address_line1": 1, "address_line2": 1})}
    user_names, persons = await _names(user_ids=[(item.get("from_holder") or item.get("to_holder") or {}).get("id") for item in page],
                                       person_ids=[follow.get(item["movement_id"], {}).get("person_id") for item in page])
    items = []
    for item in page:
        info = follow.get(item["movement_id"], {})
        house = houses.get(item.get("household_id")) or {}
        holder = item.get("from_holder") if metric != "received" else item.get("to_holder")
        items.append({"movement_id": item["movement_id"], "movement_type": item["movement_type"], "book_id": item.get("book_id"), "book_name": item.get("book_name"), "quantity": item.get("quantity"),
                      "occurred_at": item.get("occurred_at"), "mentor_user_id": (holder or {}).get("id"), "mentor_name": user_names.get((holder or {}).get("id")),
                      "recipient_name": persons.get(info.get("person_id")) or info.get("contact_name") or (item.get("to_holder_label") if metric == "received" else None),
                      "person_id": info.get("person_id"), "recipient_status": item.get("recipient_status"), "address_line1": house.get("address_line1"), "address_line2": house.get("address_line2"),
                      "campaign_id": item.get("campaign_id"), "inventory_status": item.get("inventory_status"), "followup": {key: info.get(key) for key in ("accepted", "next_action", "next_action_at", "enrollment_id", "stage_key")},
                      "from_label": item.get("from_holder_label")})
    return {"metric": metric, "total": total, "items": serialize(items)}


@router.get("/movement/{movement_id}", response_model=dict)
async def trace_movement(movement_id: str, current_user: dict = Depends(get_current_user)):
    """Recorrido del libro: Librería → mentor → vivienda/persona → seguimiento → Consolidación."""
    movement = await db.library_movements.find_one({"movement_id": movement_id}, {"_id": 0})
    if not movement:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")
    mentor_user = (movement.get("from_holder") or {}).get("id") if (movement.get("from_holder") or {}).get("type") == "user" else None
    if not sees_all(current_user) and mentor_user != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Solo puede consultar sus propios libros")
    steps = []
    if mentor_user and movement.get("book_id"):
        origin = await db.library_movements.find_one({"book_id": movement["book_id"], "to_holder.type": "user", "to_holder.id": mentor_user, "movement_type": {"$in": ["ASSIGNMENT", "TRANSFER"]},
                                                      "occurred_at": {"$lte": movement.get("occurred_at") or datetime.max}}, {"_id": 0}, sort=[("occurred_at", -1)])
        if origin:
            steps.append({"step": "library", "title": f"Librería → {origin.get('to_holder_label')}", "detail": f"{origin['quantity']} × {origin.get('book_name')} ({origin.get('from_holder_label')})", "at": origin.get("occurred_at")})
    house = await db.outreach_households.find_one({"household_id": movement.get("household_id")}, {"_id": 0, "address_line1": 1, "address_line2": 1}) if movement.get("household_id") else None
    where = " · ".join(filter(None, [(house or {}).get("address_line1"), (house or {}).get("address_line2")]))
    steps.append({"step": "delivery", "title": f"{movement.get('from_holder_label') or 'Mentor'} → {where or movement.get('to_holder_label') or 'destinatario'}",
                  "detail": f"{movement.get('quantity')} × {movement.get('book_name')}" + (" · sin descuento (por conciliar)" if movement.get("movement_type") == PENDING_TYPE else ""), "at": movement.get("occurred_at")})
    info = (await _followup_info([movement])).get(movement_id, {})
    _, persons = await _names(person_ids=[info.get("person_id")])
    recipient = persons.get(info.get("person_id")) or info.get("contact_name")
    if movement.get("recipient_completed_at") or recipient:
        steps.append({"step": "recipient", "title": f"Destinatario: {recipient or 'por completar'}", "detail": "Completado después (sin volver a descontar)" if movement.get("recipient_completed_at") else "Identificado en la entrega",
                      "at": movement.get("recipient_completed_at") or movement.get("occurred_at"), "person_id": info.get("person_id")})
    else:
        steps.append({"step": "recipient", "title": "Destinatario por completar", "detail": "Libro entregado en la vivienda sin nombre", "at": None})
    if info.get("accepted"):
        steps.append({"step": "followup", "title": "Aceptó seguimiento", "detail": " · ".join(filter(None, [info.get("next_action"), serialize(info.get("next_action_at"))[:10] if info.get("next_action_at") else None])), "at": None})
    if info.get("enrollment_id"):
        steps.append({"step": "consolidation", "title": "En Consolidación", "detail": info.get("stage_key") or "", "at": None, "enrollment_id": info.get("enrollment_id")})
    return {"movement": serialize(movement), "steps": serialize(steps)}


async def campaign_books_summary(campaign_id: str) -> dict:
    """Para el Reporte de invasión: libros entregados, con destinatario y con seguimiento."""
    movements = await db.library_movements.find({"campaign_id": campaign_id, "movement_type": {"$in": DELIVERY_TYPES}, "from_holder.type": "user"}, {"_id": 0}).to_list(20000)
    follow = await _followup_info(movements)
    delivered = sum(item.get("quantity") or 0 for item in movements)
    identified = sum(item.get("quantity") or 0 for item in movements if item.get("recipient_status") == "identified" or item.get("person_id"))
    return {"delivered": delivered, "pending_reconciliation": sum(item.get("quantity") or 0 for item in movements if item["movement_type"] == PENDING_TYPE),
            "identified": identified, "unidentified": delivered - identified,
            "with_followup": sum(item.get("quantity") or 0 for item in movements if follow.get(item["movement_id"], {}).get("accepted"))}
